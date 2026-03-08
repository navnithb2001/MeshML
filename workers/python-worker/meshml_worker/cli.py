"""
CLI for MeshML Worker

Commands:
- init: Initialize worker configuration
- train: Start training on a model
- status: Check worker status
- config: Manage configuration
"""

import sys
from pathlib import Path
from typing import Optional
import click

from meshml_worker.config import WorkerConfig, load_config
from meshml_worker.worker import MeshMLWorker


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """MeshML Worker - Federated Learning Worker"""
    pass


@main.command()
@click.option(
    "--parameter-server-url",
    default="http://localhost:8000",
    help="Parameter Server HTTP URL"
)
@click.option(
    "--grpc-url",
    default="localhost:50051",
    help="Parameter Server gRPC URL"
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
    grpc_url: str,
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
    config.parameter_server.grpc_url = grpc_url
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
    click.echo(f"  Device: {device}")
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Review configuration: cat .meshml/config.yaml")
    click.echo("  2. Start training: meshml-worker train --model-id <model-id>")


@main.command()
@click.option(
    "--model-id",
    required=True,
    help="Model ID to train"
)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Configuration file path"
)
@click.option(
    "--epochs",
    type=int,
    default=None,
    help="Number of training epochs (overrides config)"
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
@click.option(
    "--checkpoint",
    type=click.Path(path_type=Path),
    default=None,
    help="Resume from checkpoint"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Dry run (validate setup without training)"
)
def train(
    model_id: str,
    config: Optional[Path],
    epochs: Optional[int],
    batch_size: Optional[int],
    device: Optional[str],
    checkpoint: Optional[Path],
    dry_run: bool
) -> None:
    """Start training on a model"""
    
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
    
    click.echo(f"Starting training on model: {model_id}")
    click.echo(f"Worker ID: {worker_config.worker.id}")
    click.echo(f"Device: {worker_config.training.device}")
    click.echo(f"Batch size: {worker_config.training.batch_size}")
    
    if dry_run:
        click.echo("\n[DRY RUN] Setup validation passed ✓")
        return
    
    # Create and run worker
    try:
        worker = MeshMLWorker(worker_config)
        worker.train(
            model_id=model_id,
            epochs=epochs,
            checkpoint_path=checkpoint
        )
    except KeyboardInterrupt:
        click.echo("\n\nTraining interrupted by user")
        sys.exit(0)
    except Exception as e:
        click.echo(f"\nError during training: {e}", err=True)
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
