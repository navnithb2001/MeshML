"""
Model upload endpoints for API Gateway.

Implements user-facing model upload and registry registration.
"""

import hashlib
import logging
import os
from typing import Optional

import httpx
from app.clients.model_registry_client import ModelRegistryClient
from app.models.user import User
from app.proto import model_registry_pb2
from app.routers.auth import get_current_user
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_model(
    file: UploadFile = File(...),
    name: str = Form(...),
    group_id: str = Form(...),
    description: Optional[str] = Form(None),
    architecture_type: Optional[str] = Form(None),
    dataset_type: Optional[str] = Form(None),
    version: Optional[str] = Form("1.0.0"),
    current_user: User = Depends(get_current_user),
):
    """
    Upload model.py via API Gateway.

    Flow:
    1. Register model in Model Registry (gRPC)
    2. Upload file to signed URL (HTTP PUT)
    3. Finalize upload (gRPC)
    """
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Missing filename")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    file_hash = hashlib.sha256(content).hexdigest()
    file_size = len(content)

    client = ModelRegistryClient()
    try:
        registration = await client.register_new_model(
            model_registry_pb2.RegisterModelRequest(
                name=name,
                description=description or "",
                group_id=group_id,
                created_by_user_id=str(current_user.id),
                architecture_type=architecture_type or "",
                dataset_type=dataset_type or "",
                version=version or "1.0.0",
                metadata={},
            )
        )
    except Exception as e:
        logger.error(f"Model registration failed: {e}")
        raise HTTPException(status_code=502, detail="Model registry registration failed")

    try:
        async with httpx.AsyncClient(timeout=60) as http_client:
            put_resp = await http_client.put(
                registration.upload_url, content=content, headers={"Content-Type": "text/x-python"}
            )
            if put_resp.status_code not in (200, 201):
                raise HTTPException(
                    status_code=502, detail=f"Signed upload failed: {put_resp.status_code}"
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload to signed URL failed: {e}")
        raise HTTPException(status_code=502, detail="Signed upload failed")

    try:
        await client.finalize_model_upload(
            model_registry_pb2.FinalizeModelUploadRequest(
                model_id=registration.model_id,
                gcs_path=registration.gcs_path,
                file_size_bytes=file_size,
                file_hash=file_hash,
            )
        )
    except Exception as e:
        logger.error(f"Finalize model upload failed: {e}")
        raise HTTPException(status_code=502, detail="Finalize upload failed")

    return {
        "model_id": registration.model_id,
        "gcs_path": registration.gcs_path,
        "file_size_bytes": file_size,
        "file_hash": file_hash,
    }


@router.get("/{model_id}/download")
async def download_final_model(model_id: int, current_user: User = Depends(get_current_user)):
    """
    Get signed download URL for final model artifact.
    """
    client = ModelRegistryClient()
    response = await client.get_final_model_download_url(model_id=model_id)
    if not response.found:
        raise HTTPException(status_code=404, detail="Final model not found")
    return {
        "model_id": model_id,
        "download_url": response.download_url,
        "storage_path": response.storage_path,
        "expires_in_seconds": response.expires_in_seconds,
    }


@router.get("/{model_id}/checkpoints/{version}")
async def download_checkpoint(
    model_id: int, version: str, current_user: User = Depends(get_current_user)
):
    """
    Get signed download URL for a specific checkpoint version.
    """
    base_url = os.getenv("MODEL_REGISTRY_URL", "http://model-registry:8004")
    url = f"{base_url}/api/v1/models/{model_id}/checkpoints/{version}"
    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.get(url)
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Checkpoint not found")
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail="Model registry error")
            return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Checkpoint download lookup failed: {e}")
        raise HTTPException(status_code=502, detail="Model registry unavailable")
