"""Communication modules"""

from .http_client import HTTPClient
from .grpc_client import GRPCClient
from .dataset_sharder_client import DatasetSharderClient
from .task_orchestrator_client import TaskOrchestratorClient
from .model_registry_client import ModelRegistryClient

__all__ = [
    'HTTPClient',
    'GRPCClient',
    'DatasetSharderClient',
    'TaskOrchestratorClient',
    'ModelRegistryClient',
]
