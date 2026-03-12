"""
Database seeding utilities for development and testing.

This module provides:
- Seed data for all models (users, groups, models, workers, jobs, batches)
- Configurable seed data generation
- Idempotent seeding (can run multiple times safely)
- Cleanup utilities for test data
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from services.database.models.user import User
from services.database.models.group import Group, GroupMember, GroupInvitation, GroupRole, InvitationStatus
from services.database.models.model import Model, ModelStatus
from services.database.models.worker import Worker, WorkerType, WorkerStatus
from services.database.models.job import Job, JobStatus
from services.database.models.data_batch import DataBatch, BatchStatus
from services.database.repositories import (
    UserRepository, GroupRepository, GroupMemberRepository, GroupInvitationRepository,
    ModelRepository, WorkerRepository, JobRepository, DataBatchRepository
)
from services.database.repositories.transactions import transaction

logger = logging.getLogger(__name__)


class DatabaseSeeder:
    """Main seeder class for populating database with test data."""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.group_repo = GroupRepository(db)
        self.member_repo = GroupMemberRepository(db)
        self.invitation_repo = GroupInvitationRepository(db)
        self.model_repo = ModelRepository(db)
        self.worker_repo = WorkerRepository(db)
        self.job_repo = JobRepository(db)
        self.batch_repo = DataBatchRepository(db)
        
        # Store created entities for reference
        self.users: List[User] = []
        self.groups: List[Group] = []
        self.models: List[Model] = []
        self.workers: List[Worker] = []
        self.jobs: List[Job] = []
    
    def seed_all(self, num_users: int = 5, num_groups: int = 3, num_workers: int = 10) -> Dict[str, Any]:
        """
        Seed all database tables with test data.
        
        Args:
            num_users: Number of users to create
            num_groups: Number of groups to create
            num_workers: Number of workers to create
        
        Returns:
            Dictionary with counts of created entities
        """
        logger.info("Starting database seeding...")
        
        with transaction(self.db):
            # Seed in order of dependencies
            self.seed_users(num_users)
            self.seed_groups(num_groups)
            self.seed_group_members()
            self.seed_group_invitations()
            self.seed_models()
            self.seed_workers(num_workers)
            self.seed_jobs()
            self.seed_data_batches()
        
        stats = {
            'users': len(self.users),
            'groups': len(self.groups),
            'models': len(self.models),
            'workers': len(self.workers),
            'jobs': len(self.jobs),
            'batches': self.batch_repo.count()
        }
        
        logger.info(f"Seeding complete: {stats}")
        return stats
    
    def seed_users(self, count: int = 5) -> List[User]:
        """Create test users."""
        logger.info(f"Seeding {count} users...")
        
        users_data = [
            {
                'email': 'alice@university.edu',
                'username': 'alice',
                'hashed_password': 'hashed_password_123',  # In production, use proper hashing
                'full_name': 'Alice Johnson',
                'is_verified': True,
                'is_active': True
            },
            {
                'email': 'bob@university.edu',
                'username': 'bob',
                'hashed_password': 'hashed_password_456',
                'full_name': 'Bob Smith',
                'is_verified': True,
                'is_active': True
            },
            {
                'email': 'charlie@university.edu',
                'username': 'charlie',
                'hashed_password': 'hashed_password_789',
                'full_name': 'Charlie Davis',
                'is_verified': True,
                'is_active': True
            },
            {
                'email': 'diana@university.edu',
                'username': 'diana',
                'hashed_password': 'hashed_password_abc',
                'full_name': 'Diana Martinez',
                'is_verified': False,
                'is_active': True
            },
            {
                'email': 'eve@university.edu',
                'username': 'eve',
                'hashed_password': 'hashed_password_def',
                'full_name': 'Eve Wilson',
                'is_verified': True,
                'is_active': False
            }
        ]
        
        for i, user_data in enumerate(users_data[:count]):
            # Check if user already exists
            existing = self.user_repo.get_by_email(user_data['email'])
            if not existing:
                user = self.user_repo.create(**user_data)
                self.users.append(user)
                logger.debug(f"Created user: {user.username}")
            else:
                self.users.append(existing)
                logger.debug(f"User already exists: {existing.username}")
        
        return self.users
    
    def seed_groups(self, count: int = 3) -> List[Group]:
        """Create test groups."""
        logger.info(f"Seeding {count} groups...")
        
        if not self.users:
            raise ValueError("Users must be seeded before groups")
        
        groups_data = [
            {
                'name': 'AI Research Lab',
                'description': 'Deep learning and computer vision research',
                'owner_id': self.users[0].id
            },
            {
                'name': 'ML Study Group',
                'description': 'Collaborative ML learning and projects',
                'owner_id': self.users[1].id
            },
            {
                'name': 'Computer Vision Team',
                'description': 'Image classification and object detection',
                'owner_id': self.users[2].id
            }
        ]
        
        for group_data in groups_data[:count]:
            group = self.group_repo.create(**group_data)
            self.groups.append(group)
            logger.debug(f"Created group: {group.name}")
        
        return self.groups
    
    def seed_group_members(self) -> List[GroupMember]:
        """Add members to groups."""
        logger.info("Seeding group members...")
        
        if not self.groups or not self.users:
            raise ValueError("Users and groups must be seeded before members")
        
        members = []
        
        # AI Research Lab - Alice (owner), Bob (admin), Charlie (member)
        if len(self.groups) > 0 and len(self.users) >= 3:
            group = self.groups[0]
            # Owner is automatically added, add others
            members.append(self.member_repo.add_member(group.id, self.users[1].id, GroupRole.ADMIN))
            members.append(self.member_repo.add_member(group.id, self.users[2].id, GroupRole.MEMBER))
        
        # ML Study Group - Bob (owner), Alice (admin), Diana (member)
        if len(self.groups) > 1 and len(self.users) >= 4:
            group = self.groups[1]
            members.append(self.member_repo.add_member(group.id, self.users[0].id, GroupRole.ADMIN))
            members.append(self.member_repo.add_member(group.id, self.users[3].id, GroupRole.MEMBER))
        
        # Computer Vision Team - Charlie (owner), Alice (member)
        if len(self.groups) > 2 and len(self.users) >= 1:
            group = self.groups[2]
            members.append(self.member_repo.add_member(group.id, self.users[0].id, GroupRole.MEMBER))
        
        logger.info(f"Created {len(members)} group memberships")
        return members
    
    def seed_group_invitations(self) -> List[GroupInvitation]:
        """Create pending invitations."""
        logger.info("Seeding group invitations...")
        
        if not self.groups or not self.users:
            raise ValueError("Users and groups must be seeded before invitations")
        
        invitations = []
        
        # Pending invitation to AI Research Lab
        if len(self.groups) > 0:
            import uuid
            inv = self.invitation_repo.create(
                group_id=self.groups[0].id,
                invited_by_id=self.users[0].id,
                email='newstudent@university.edu',
                token=f'invite-token-{uuid.uuid4().hex[:12]}',
                role=GroupRole.MEMBER,
                status=InvitationStatus.PENDING,
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            invitations.append(inv)
        
        # Expired invitation
        if len(self.groups) > 1:
            inv = self.invitation_repo.create(
                group_id=self.groups[1].id,
                invited_by_id=self.users[1].id,
                email='expired@university.edu',
                token='invite-token-expired',
                role=GroupRole.MEMBER,
                status=InvitationStatus.EXPIRED,
                expires_at=datetime.utcnow() - timedelta(days=1)
            )
            invitations.append(inv)
        
        logger.info(f"Created {len(invitations)} invitations")
        return invitations
    
    def seed_models(self) -> List[Model]:
        """Create test models."""
        logger.info("Seeding models...")
        
        if not self.groups or not self.users:
            raise ValueError("Users and groups must be seeded before models")
        
        models_data = [
            {
                'name': 'resnet50-custom',
                'description': 'Custom ResNet-50 for image classification',
                'group_id': self.groups[0].id,
                'uploaded_by_id': self.users[0].id,
                'gcs_path': 'gs://meshml-models/resnet50/model.py',
                'status': ModelStatus.READY,
                'model_metadata': {
                    'architecture': 'ResNet-50',
                    'parameters': 25557032,
                    'input_shape': [3, 224, 224],
                    'num_classes': 1000
                },
                'version': 1
            },
            {
                'name': 'vgg16-transfer',
                'description': 'VGG16 with transfer learning',
                'group_id': self.groups[0].id,
                'uploaded_by_id': self.users[1].id,
                'gcs_path': 'gs://meshml-models/vgg16/model.py',
                'status': ModelStatus.VALIDATING,
                'version': 1
            },
            {
                'name': 'mobilenet-v2',
                'description': 'Lightweight MobileNetV2',
                'group_id': self.groups[1].id,
                'uploaded_by_id': self.users[1].id,
                'gcs_path': 'gs://meshml-models/mobilenet/model.py',
                'status': ModelStatus.READY,
                'model_metadata': {
                    'architecture': 'MobileNetV2',
                    'parameters': 3504872,
                    'input_shape': [3, 224, 224]
                },
                'version': 1
            },
            {
                'name': 'custom-cnn',
                'description': 'Simple CNN for CIFAR-10',
                'group_id': self.groups[2].id if len(self.groups) > 2 else self.groups[0].id,
                'uploaded_by_id': self.users[2].id,
                'gcs_path': 'gs://meshml-models/custom-cnn/model.py',
                'status': ModelStatus.FAILED,
                'validation_error': 'Invalid forward() method signature',
                'version': 1
            }
        ]
        
        for model_data in models_data:
            model = self.model_repo.create(**model_data)
            self.models.append(model)
            logger.debug(f"Created model: {model.name} ({model.status})")
        
        return self.models
    
    def seed_workers(self, count: int = 10) -> List[Worker]:
        """Create test workers."""
        logger.info(f"Seeding {count} workers...")
        
        worker_templates = [
            {
                'worker_id': 'worker-laptop-001',
                'name': 'Alice Laptop',
                'worker_type': WorkerType.PYTHON,
                'status': WorkerStatus.ONLINE,
                'capabilities': {
                    'gpu': 'NVIDIA RTX 3080',
                    'ram_gb': 32,
                    'cpu_cores': 16,
                    'network_mbps': 1000
                },
                'ip_address': '192.168.1.101'
            },
            {
                'worker_id': 'worker-laptop-002',
                'name': 'Bob Laptop',
                'worker_type': WorkerType.PYTHON,
                'status': WorkerStatus.BUSY,
                'capabilities': {
                    'gpu': 'NVIDIA GTX 1660',
                    'ram_gb': 16,
                    'cpu_cores': 8,
                    'network_mbps': 500
                },
                'ip_address': '192.168.1.102'
            },
            {
                'worker_id': 'worker-mobile-001',
                'name': 'Charlie Phone',
                'worker_type': WorkerType.JAVASCRIPT,
                'status': WorkerStatus.ONLINE,
                'capabilities': {
                    'ram_gb': 6,
                    'cpu_cores': 8,
                    'network_mbps': 100
                },
                'ip_address': '192.168.1.201'
            },
            {
                'worker_id': 'worker-desktop-001',
                'name': 'Lab Desktop',
                'worker_type': WorkerType.CPP,
                'status': WorkerStatus.ONLINE,
                'capabilities': {
                    'gpu': 'NVIDIA RTX 4090',
                    'ram_gb': 64,
                    'cpu_cores': 32,
                    'network_mbps': 1000
                },
                'ip_address': '192.168.1.50'
            },
            {
                'worker_id': 'worker-offline-001',
                'name': 'Offline Device',
                'worker_type': WorkerType.PYTHON,
                'status': WorkerStatus.OFFLINE,
                'capabilities': {
                    'ram_gb': 8,
                    'cpu_cores': 4,
                    'network_mbps': 100
                },
                'ip_address': '192.168.1.150'
            }
        ]
        
        for i in range(count):
            if i < len(worker_templates):
                worker_data = worker_templates[i]
            else:
                # Generate additional workers
                worker_data = {
                    'worker_id': f'worker-auto-{i:03d}',
                    'name': f'Auto Worker {i}',
                    'worker_type': WorkerType.PYTHON,
                    'status': WorkerStatus.ONLINE if i % 3 != 0 else WorkerStatus.OFFLINE,
                    'capabilities': {
                        'ram_gb': 8 + (i % 4) * 8,
                        'cpu_cores': 4 + (i % 3) * 4,
                        'network_mbps': 100 + (i % 5) * 200
                    },
                    'ip_address': f'192.168.1.{100 + i}'
                }
            
            worker = self.worker_repo.create(**worker_data)
            self.workers.append(worker)
            logger.debug(f"Created worker: {worker.worker_id} ({worker.status})")
        
        return self.workers
    
    def seed_jobs(self) -> List[Job]:
        """Create test training jobs."""
        logger.info("Seeding jobs...")
        
        if not self.groups or not self.models:
            raise ValueError("Groups and models must be seeded before jobs")
        
        # Get ready models only
        ready_models = [m for m in self.models if m.status == ModelStatus.READY]
        
        if not ready_models:
            logger.warning("No ready models available, skipping job seeding")
            return []
        
        jobs_data = [
            {
                'name': 'ImageNet Training - ResNet50',
                'description': 'Full ImageNet classification training',
                'group_id': self.groups[0].id,
                'model_id': ready_models[0].id,
                'config': {
                    'learning_rate': 0.001,
                    'batch_size': 64,
                    'optimizer': 'Adam',
                    'loss_function': 'CrossEntropyLoss'
                },
                'dataset_path': 'gs://meshml-data/imagenet/train',
                'total_epochs': 100,
                'current_epoch': 25,
                'progress': 25.0,
                'status': JobStatus.RUNNING,
                'metrics': {
                    'train_loss': 0.342,
                    'train_accuracy': 87.5,
                    'val_loss': 0.456,
                    'val_accuracy': 84.2
                }
            },
            {
                'name': 'CIFAR-10 Transfer Learning',
                'description': 'Transfer learning on CIFAR-10',
                'group_id': self.groups[1].id if len(self.groups) > 1 else self.groups[0].id,
                'model_id': ready_models[-1].id if len(ready_models) > 1 else ready_models[0].id,
                'config': {
                    'learning_rate': 0.0001,
                    'batch_size': 128,
                    'optimizer': 'SGD',
                    'loss_function': 'CrossEntropyLoss'
                },
                'dataset_path': 'gs://meshml-data/cifar10/train',
                'total_epochs': 50,
                'current_epoch': 0,
                'progress': 0.0,
                'status': JobStatus.PENDING
            },
            {
                'name': 'Completed Training Run',
                'description': 'Successfully completed training',
                'group_id': self.groups[0].id,
                'model_id': ready_models[0].id,
                'config': {
                    'learning_rate': 0.001,
                    'batch_size': 32,
                    'optimizer': 'Adam'
                },
                'dataset_path': 'gs://meshml-data/custom/train',
                'total_epochs': 10,
                'current_epoch': 10,
                'progress': 100.0,
                'status': JobStatus.COMPLETED,
                'metrics': {
                    'final_train_loss': 0.123,
                    'final_train_accuracy': 95.8,
                    'final_val_loss': 0.145,
                    'final_val_accuracy': 94.3
                }
            }
        ]
        
        for job_data in jobs_data:
            job = self.job_repo.create(**job_data)
            self.jobs.append(job)
            logger.debug(f"Created job: {job.name} ({job.status})")
        
        return self.jobs
    
    def seed_data_batches(self) -> List[DataBatch]:
        """Create data batches for jobs."""
        logger.info("Seeding data batches...")
        
        if not self.jobs or not self.workers:
            raise ValueError("Jobs and workers must be seeded before batches")
        
        batches = []
        
        # Get running job
        running_jobs = [j for j in self.jobs if j.status == JobStatus.RUNNING]
        
        if running_jobs:
            job = running_jobs[0]
            online_workers = [w for w in self.workers if w.status == WorkerStatus.ONLINE]
            
            # Create 100 batches for the running job
            for i in range(100):
                status = BatchStatus.PENDING
                worker_id = None
                
                # Assign some batches to workers
                if i < 30 and online_workers:
                    worker_id = online_workers[i % len(online_workers)].id
                    if i < 10:
                        status = BatchStatus.COMPLETED
                    elif i < 20:
                        status = BatchStatus.PROCESSING
                    else:
                        status = BatchStatus.ASSIGNED
                
                batch = self.batch_repo.create(
                    job_id=job.id,
                    worker_id=worker_id,
                    batch_index=i,
                    shard_path=f'gs://meshml-data/imagenet/train/shard-{i:04d}.pt',
                    size_bytes=10240000 + (i * 1024),  # ~10MB per shard
                    checksum=f'{i:064x}',  # 64-char hex string
                    status=status,
                    retry_count=1 if i == 50 else 0  # One batch has been retried
                )
                batches.append(batch)
            
            logger.info(f"Created {len(batches)} data batches for job {job.id}")
        
        return batches
    
    def clear_all(self) -> Dict[str, int]:
        """
        Clear all seed data from database (for testing).
        Use with caution!
        
        Returns:
            Dictionary with counts of deleted entities
        """
        logger.warning("Clearing all data from services.database...")
        
        with transaction(self.db):
            # Delete in reverse order of dependencies
            batch_count = self.batch_repo.delete_many({})
            job_count = self.job_repo.delete_many({})
            worker_count = self.worker_repo.delete_many({})
            model_count = self.model_repo.delete_many({})
            # Group invitations and members will cascade delete
            group_count = self.group_repo.delete_many({})
            user_count = self.user_repo.delete_many({})
        
        stats = {
            'batches': batch_count,
            'jobs': job_count,
            'workers': worker_count,
            'models': model_count,
            'groups': group_count,
            'users': user_count
        }
        
        logger.info(f"Cleared all data: {stats}")
        return stats


def seed_database(db: Session, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to seed database with test data.
    
    Args:
        db: Database session
        **kwargs: Arguments to pass to seed_all()
    
    Returns:
        Dictionary with seeding statistics
    """
    seeder = DatabaseSeeder(db)
    return seeder.seed_all(**kwargs)


def clear_database(db: Session) -> Dict[str, int]:
    """
    Convenience function to clear all data from services.database.
    
    Args:
        db: Database session
    
    Returns:
        Dictionary with deletion statistics
    """
    seeder = DatabaseSeeder(db)
    return seeder.clear_all()
