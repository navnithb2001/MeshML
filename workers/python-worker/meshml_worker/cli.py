"""
CLI for MeshML Worker

Commands:
- init: Initialize worker configuration
- run: Run worker with platform integration (Task Orchestrator, Model Registry, Dataset Sharder)
- login: Login to MeshML platform
- join: Join a group using invitation code
- status: Check worker status
- config: Manage configuration
"""

import sys
from pathlib import Path
from typing import Optional
import click

from meshml_worker.config import WorkerConfig, load_config
from meshml_worker.main import MeshMLWorker


@click.group()
@click.version_option(version="0.2.0")
def main() -> None:
    """MeshML Worker - Federated Learning Worker"""
    pass


@main.command()
@click.option(
    "--parameter-server-url",
    default="http://localhost:8003",
    help="Parameter Server HTTP URL"
)
@click.option(
    "--task-orchestrator-url",
    default="localhost:50051",
    help="Task Orchestrator gRPC URL"
)
@click.option(
    "--worker-id",
    default=None,
    help="Worker ID (auto-generated if not provided)"
)
@click.option(
    "--worker-name",
    default="MeshML Worker",
    help="Worker name"
)
@click.option(
    "--device",
    type=click.Choice(["auto", "cuda", "cpu", "mps"]),
    default="auto",
    help="Training device"
)
@click.option(
    "--batch-size",
    type=int,
    default=32,
    help="Training batch size"
)
@click.option(
    "--config-dir",
    type=click.Path(path_type=Path),
    default=Path(".meshml"),
    help="Configuration directory"
)
@click.option(
    "--force",
    is_flag=True,
    help="Force overwrite existing configuration"
)
def init(
    parameter_server_url: str,
    task_orchestrator_url: str,
    worker_id: Optional[str],
    worker_name: str,
    device: str,
    batch_size: int,
    config_dir: Path,
    force: bool
) -> None:
    """Initialize worker configuration"""
    
    config_path = config_dir / "config.yaml"
    
    # Check if config already exists
    if config_path.exists() and not force:
        click.echo(f"Configuration already exists at {config_path}")
        click.echo("Use --force to overwrite")
        sys.exit(1)
    
    # Create configuration
    config = WorkerConfig()
    config.worker.id = worker_id
    config.worker.name = worker_name
    config.parameter_server.url = parameter_server_url
    config.task_orchestrator.grpc_url = task_orchestrator_url
    config.training.device = device
    config.training.batch_size = batch_size
    config.storage.base_dir = config_dir
    
    # Setup and save
    config.setup()
    config.save_to_file(config_path)
    
    click.echo(f"✓ Worker initialized successfully!")
    click.echo(f"  Worker ID: {config.worker.id}")
    click.echo(f"  Config: {config_path}")
    click.echo(f"  Parameter Server: {parameter_server_url}")
    click.echo(f"  Task Orchestrator: {task_orchestrator_url}")
    click.echo(f"  Device: {device}")
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Review configuration: cat .meshml/config.yaml")
    click.echo("  2. Login: meshml-worker login")
    click.echo("  3. Run worker: meshml-worker run --user-id <user_id>")


@main.command()
@click.option(
    "--email",
    prompt=True,
    help="User email"
)
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    help="User password"
)
@click.option(
    "--api-url",
    default="http://34.69.215.43",
    help="API Gateway URL"
)
def login(email: str, password: str, api_url: str) -> None:
    """Login to MeshML platform"""
    
    try:
        from meshml_worker.registration import WorkerRegistration
        
        # Create minimal config object for authentication
        class AuthConfig:
            def __init__(self):
                self.worker = type('Worker', (), {'worker_id': 'temp', 'user_email': None})()
        
        config = AuthConfig()
        config.api_base_url = api_url
        
        # Initialize registration manager
        registration = WorkerRegistration(config)
        
        # Attempt login
        click.echo(f"Logging in as {email}...")
        registration.login(email, password)
        
        click.echo("\n✓ Login successful!")
        click.echo(f"  User: {email}")
        click.echo(f"  Token saved to: ~/.meshml/auth.json")
        click.echo()
        click.echo("Next steps:")
        click.echo("  1. Join a group: meshml-worker join --invitation-code <code> --worker-id <id>")
        click.echo("  2. Start training: meshml-worker run --user-id <user_id>")
        
    except Exception as e:
        click.echo(f"\n✗ Login failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--invitation-code",
    prompt=True,
    help="Group invitation code"
)
@click.option(
    "--worker-id",
    prompt=True,
    help="Worker device ID (e.g., laptop-1, gpu-server-2)"
)
@click.option(
    "--api-url",
    default="http://34.69.215.43",
    help="API Gateway URL"
)
def join(invitation_code: str, worker_id: str, api_url: str) -> None:
    """Join a group using invitation code (requires prior login)"""
    
    try:
        from meshml_worker.registration import WorkerRegistration
        
        # Create minimal config object
        class AuthConfig:
            def __init__(self):
                self.worker = type('Worker', (), {'worker_id': worker_id, 'user_email': None})()
        
        config = AuthConfig()
        config.api_base_url = api_url
        
        # Initialize registration manager (will load saved auth token)
        registration = WorkerRegistration(config)
        
        # Check if logged in
        if not registration.auth_token:
            click.echo("✗ Not logged in. Please run 'meshml-worker login' first.", err=True)
            sys.exit(1)
        
        # Join group
        click.echo(f"Joining group with invitation code...")
        result = registration.join_group_by_invitation(invitation_code)
        
        click.echo("\n✓ Successfully joined group!")
        click.echo(f"  Group: {result.get('group_name')}")
        click.echo(f"  Worker ID: {worker_id}")
        click.echo(f"  User: {registration.user_email}")
        click.echo()
        click.echo("Next steps:")
        click.echo("  1. Start training: meshml-worker run --user-id <user_id>")
        
    except Exception as e:
        click.echo(f"\n✗ Failed to join group: {e}", err=True)
        sys.exit(1)




@main.command()
@click.option(
    "--user-id",
    required=True,
    help="User ID for authentication with Task Orchestrator"
)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Configuration file path"
)
@click.option(
    "--preferred-jobs",
    default=None,
    help="Comma-separated list of preferred job IDs (optional)"
)
@click.option(
    "--batch-size",
    type=int,
    default=None,
    help="Batch size (overrides config)"
)
@click.option(
    "--device",
    type=click.Choice(["auto", "cuda", "cpu", "mps"]),
    default=None,
    help="Training device (overrides config)"
)
def run(
    user_id: str,
    config: Optional[Path],
    preferred_jobs: Optional[str],
    batch_size: Optional[int],
    device: Optional[str]
) -> None:
    """Run worker with full Task Orchestrator integration (production mode)
    
    This command:
    1. Registers with Task Orchestrator
    2. Requests task assignment
    3. Downloads model from Model Registry
    4. Downloads data from Dataset Sharder
    5. Trains and reports progress
    
    Example:
        meshml-worker run --user-id user_123
    """
    import asyncio
    
    # Load configuration
    try:
        worker_config = load_config(config)
    except FileNotFoundError:
        click.echo("Error: Worker not initialized. Run 'meshml-worker init' first.", err=True)
        sys.exit(1)
    
    # Override config with CLI options
    if batch_size is not None:
        worker_config.training.batch_size = batch_size
    if device is not None:
        worker_config.training.device = device
    
    # Parse preferred jobs
    preferred_job_ids = None
    if preferred_jobs:
        preferred_job_ids = [j.strip() for j in preferred_jobs.split(",")]
    
    click.echo("=" * 60)
    click.echo("MeshML Worker - Orchestrated Mode")
    click.echo("=" * 60)
    click.echo(f"Worker ID: {worker_config.worker.id}")
    click.echo(f"User ID: {user_id}")
    click.echo(f"Device: {worker_config.training.device}")
    click.echo(f"Batch size: {worker_config.training.batch_size}")
    click.echo()
    click.echo("Service Endpoints:")
    click.echo(f"  Task Orchestrator: {worker_config.task_orchestrator.grpc_url}")
    click.echo(f"  Model Registry: {worker_config.model_registry.url}")
    click.echo(f"  Dataset Sharder: {worker_config.dataset_sharder.url}")
    click.echo(f"  Parameter Server: {worker_config.parameter_server.url}")
    click.echo("=" * 60)
    click.echo()
    
    # Create and run worker
    try:
        worker = MeshMLWorker(worker_config)
        
        # Run orchestrated training with platform integration
        asyncio.run(worker.run(
            user_id=user_id,
            preferred_job_ids=preferred_job_ids
        ))
        
        click.echo("\n✓ Training completed successfully!")
        
    except KeyboardInterrupt:
        click.echo("\n\n✗ Training interrupted by user")
        sys.exit(0)
    except Exception as e:
        click.echo(f"\n✗ Error during training: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@main.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Configuration file path"
)
def status(config: Optional[Path]) -> None:
    """Check worker status"""
    
    try:
        worker_config = load_config(config)
    except FileNotFoundError:
        click.echo("Error: Worker not initialized. Run 'meshml-worker init' first.", err=True)
        sys.exit(1)
    
    click.echo("Worker Status:")
    click.echo(f"  ID: {worker_config.worker.id}")
    click.echo(f"  Name: {worker_config.worker.name}")
    click.echo(f"  Parameter Server: {worker_config.parameter_server.url}")
    click.echo(f"  Device: {worker_config.training.device}")
    click.echo(f"  Batch Size: {worker_config.training.batch_size}")
    click.echo(f"  Mixed Precision: {worker_config.training.mixed_precision}")
    click.echo(f"  Storage: {worker_config.storage.base_dir}")
    
    # Check device availability
    try:
        import torch
        click.echo("\nDevice Availability:")
        click.echo(f"  CUDA: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            click.echo(f"  CUDA Device: {torch.cuda.get_device_name(0)}")
        click.echo(f"  MPS (Apple Silicon): {torch.backends.mps.is_available()}")
    except ImportError:
        click.echo("\nPyTorch not installed")


@main.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Configuration file path"
)
@click.option(
    "--show",
    is_flag=True,
    help="Show current configuration"
)
def config_cmd(config: Optional[Path], show: bool) -> None:
    """Manage configuration"""
    
    try:
        worker_config = load_config(config)
    except FileNotFoundError:
        click.echo("Error: Worker not initialized. Run 'meshml-worker init' first.", err=True)
        sys.exit(1)
    
    if show:
        config_path = worker_config.get_config_path()
        click.echo(f"Configuration file: {config_path}")
        click.echo()
        with open(config_path, "r") as f:
            click.echo(f.read())


# Register config command with proper name
main.add_command(config_cmd, name="config")


if __name__ == "__main__":
    main()
