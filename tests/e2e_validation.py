#!/usr/bin/env python3
"""
MeshML end-to-end validation script.

Flow:
1. Ingest dataset through API Gateway
2. Trigger training job through API Gateway
3. Verify Task Orchestrator worker heartbeat gRPC path
4. Verify Parameter Server model version increments for the created job
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import time
import traceback
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import grpc
import httpx

# Reuse generated stubs from python worker package.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workers" / "python-worker"))
from meshml_worker.proto import (  # noqa: E402
    parameter_server_pb2,
    parameter_server_pb2_grpc,
    task_orchestrator_pb2,
    task_orchestrator_pb2_grpc,
)


@dataclass
class Config:
    api_gateway_url: str = os.getenv("API_GATEWAY_URL", "http://localhost:8000")
    task_orchestrator_grpc_url: str = os.getenv("TASK_ORCHESTRATOR_GRPC_URL", "localhost:50051")
    parameter_server_grpc_url: str = os.getenv("PARAMETER_SERVER_GRPC_URL", "localhost:50052")
    user_email: str = os.getenv("E2E_USER_EMAIL", f"e2e-{uuid.uuid4().hex[:8]}@gmail.com")
    user_password: str = os.getenv("E2E_USER_PASSWORD", "meshml_e2e_password")
    model_name: str = os.getenv("E2E_MODEL_NAME", f"e2e-model-{uuid.uuid4().hex[:8]}")
    dataset_name: str = os.getenv("E2E_DATASET_NAME", f"e2e-dataset-{uuid.uuid4().hex[:8]}")
    wait_dataset_seconds: int = int(os.getenv("E2E_WAIT_DATASET_SECONDS", "120"))
    wait_version_seconds: int = int(os.getenv("E2E_WAIT_VERSION_SECONDS", "180"))


def _log(message: str) -> None:
    print(f"[e2e] {message}", flush=True)


def _create_imagefolder_zip() -> bytes:
    """
    Build a tiny ImageFolder-compatible ZIP archive in memory.

    Files are dummy bytes with image-like extensions; validator checks structure/extensions.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("class_a/sample_1.jpg", b"fake-jpg-bytes-a")
        archive.writestr("class_b/sample_2.png", b"fake-png-bytes-b")
    buffer.seek(0)
    return buffer.read()


async def _auth_headers(client: httpx.AsyncClient, cfg: Config) -> Dict[str, str]:
    token = os.getenv("MESHML_API_TOKEN")
    if token:
        me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        me.raise_for_status()
        _log(f"Using provided token for user {me.json().get('email')}")
        return {"Authorization": f"Bearer {token}"}

    register_payload = {
        "email": cfg.user_email,
        "password": cfg.user_password,
        "full_name": "E2E Validation User",
    }
    register = await client.post("/api/auth/register", json=register_payload)
    if register.status_code not in (201, 400):
        raise RuntimeError(f"User register failed: {register.status_code} {register.text}")

    login = await client.post(
        "/api/auth/login",
        json={"email": cfg.user_email, "password": cfg.user_password},
    )
    login.raise_for_status()
    token = login.json()["access_token"]
    _log(f"Authenticated as {cfg.user_email}")
    return {"Authorization": f"Bearer {token}"}


async def _create_group(client: httpx.AsyncClient, headers: Dict[str, str]) -> str:
    payload = {
        "name": f"e2e-group-{uuid.uuid4().hex[:8]}",
        "description": "E2E validation group",
        "is_public": False,
    }
    response = await client.post("/api/groups", headers=headers, json=payload)
    response.raise_for_status()
    group_id = response.json()["id"]
    _log(f"Created group: {group_id}")
    return group_id


async def _upload_model(
    client: httpx.AsyncClient, headers: Dict[str, str], group_id: str, cfg: Config
) -> str:
    model_code = (
        "import torch\n"
        "import torch.nn as nn\n\n"
        "class TinyModel(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.l = nn.Linear(4, 2)\n\n"
        "    def forward(self, x):\n"
        "        return self.l(x)\n\n"
        "def create_model(**kwargs):\n"
        "    return TinyModel()\n"
    )

    files = {"file": ("model.py", model_code, "text/x-python")}
    data = {
        "name": cfg.model_name,
        "group_id": group_id,
        "description": "E2E validation model",
        "architecture_type": "tiny",
        "dataset_type": "imagefolder",
        "version": "1.0.0",
    }
    response = await client.post("/api/models/upload", headers=headers, data=data, files=files)
    response.raise_for_status()
    model_id = str(response.json()["model_id"])
    _log(f"Uploaded model: {model_id}")
    return model_id


async def _upload_dataset(client: httpx.AsyncClient, headers: Dict[str, str], cfg: Config) -> str:
    archive_bytes = _create_imagefolder_zip()
    files = [("files", ("dataset.zip", archive_bytes, "application/zip"))]
    data = {"dataset_name": cfg.dataset_name}
    response = await client.post("/api/datasets/upload", headers=headers, data=data, files=files)
    response.raise_for_status()
    dataset_id = response.json()["dataset_id"]
    _log(f"Uploaded dataset: {dataset_id}")
    return dataset_id


async def _wait_for_dataset_available(
    client: httpx.AsyncClient, headers: Dict[str, str], dataset_id: str, timeout_seconds: int
) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = await client.get(f"/api/datasets/{dataset_id}", headers=headers)
        response.raise_for_status()
        payload = response.json()
        status_value = str(payload.get("status", "")).lower()
        if status_value == "available":
            _log(f"Dataset became available: {dataset_id}")
            return payload
        if status_value == "failed":
            raise RuntimeError(f"Dataset processing failed: {payload}")
        await asyncio.sleep(2)
    raise TimeoutError(f"Dataset {dataset_id} did not become available within timeout")


async def _create_job(
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    group_id: str,
    model_id: str,
    dataset_id: str,
) -> str:
    payload = {
        "group_id": group_id,
        "model_id": model_id,
        "dataset_id": dataset_id,
        "config": {
            "batch_size": 8,
            "num_epochs": 1,
            "learning_rate": 0.01,
            "optimizer": "sgd",
            "priority": "MEDIUM",
            "dataset_format": "imagefolder",
            "num_shards": 2,
            "shard_strategy": "stratified",
        },
    }
    response = await client.post("/api/jobs", headers=headers, json=payload)
    response.raise_for_status()
    job_id = response.json()["id"]
    _log(f"Created job: {job_id}")
    return job_id


async def _verify_worker_heartbeat(user_id: str, grpc_target: str) -> None:
    async with grpc.aio.insecure_channel(grpc_target) as channel:
        stub = task_orchestrator_pb2_grpc.TaskOrchestratorStub(channel)
        registration = await stub.RegisterWorker(
            task_orchestrator_pb2.WorkerCapabilities(
                user_id=user_id,
                device_type="python",
                os="darwin",
                arch="arm64",
                cpu_cores=4,
                ram_bytes=8 * 1024 * 1024 * 1024,
                gpus=[],
                frameworks={"pytorch": "2.x", "python": "3.11"},
                ip_address="127.0.0.1",
                worker_name=f"e2e-worker-{uuid.uuid4().hex[:6]}",
            )
        )
        ack = await stub.SendHeartbeat(
            task_orchestrator_pb2.Heartbeat(
                worker_id=registration.worker_id,
                status="idle",
                active_tasks=0,
                cpu_usage_percent=5.0,
                ram_usage_percent=12.0,
                gpu_usage_percent=0.0,
            )
        )
        if not ack.success:
            raise RuntimeError(f"Heartbeat not acknowledged: {ack.message}")
        _log(f"Heartbeat acknowledged for worker {registration.worker_id}")


async def _verify_parameter_version_increment(
    grpc_target: str, job_id: str, timeout_seconds: int
) -> None:
    async with grpc.aio.insecure_channel(grpc_target) as channel:
        stub = parameter_server_pb2_grpc.ParameterServerStub(channel)
        baseline = await stub.GetModelVersion(parameter_server_pb2.VersionRequest(job_id=job_id))
        baseline_version = baseline.current_version
        _log(f"Baseline parameter version for job {job_id}: {baseline_version}")

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            current = await stub.GetModelVersion(parameter_server_pb2.VersionRequest(job_id=job_id))
            if current.current_version > baseline_version:
                _log(
                    f"Parameter version increment verified: {baseline_version} -> {current.current_version}"
                )
                return
            await asyncio.sleep(3)

    raise TimeoutError(
        "Parameter version did not increment in time. "
        "Ensure at least one worker is running and pushing gradients."
    )


async def run() -> None:
    cfg = Config()
    _log(f"API Gateway: {cfg.api_gateway_url}")
    _log(f"Task Orchestrator gRPC: {cfg.task_orchestrator_grpc_url}")
    _log(f"Parameter Server gRPC: {cfg.parameter_server_grpc_url}")

    async with httpx.AsyncClient(
        base_url=cfg.api_gateway_url,
        timeout=60.0,
        trust_env=False,
    ) as client:
        headers = await _auth_headers(client, cfg)

        # Fetch current user id for orchestrator heartbeat registration.
        me_response = await client.get("/api/auth/me", headers=headers)
        me_response.raise_for_status()
        user_id = str(me_response.json()["id"])

        group_id = await _create_group(client, headers)
        model_id = await _upload_model(client, headers, group_id, cfg)
        dataset_id = await _upload_dataset(client, headers, cfg)
        await _wait_for_dataset_available(client, headers, dataset_id, cfg.wait_dataset_seconds)
        job_id = await _create_job(client, headers, group_id, model_id, dataset_id)

    await _verify_worker_heartbeat(user_id, cfg.task_orchestrator_grpc_url)
    await _verify_parameter_version_increment(
        cfg.parameter_server_grpc_url,
        job_id=job_id,
        timeout_seconds=cfg.wait_version_seconds,
    )

    _log("E2E validation passed.")


def main() -> None:
    try:
        asyncio.run(run())
    except Exception as exc:
        traceback.print_exc()
        _log(f"E2E validation failed: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
