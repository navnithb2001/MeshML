"""Test CRUD operations with all repositories."""
import sys
from pathlib import Path

# Add database service to path
sys.path.insert(0, str(Path(__file__).parent))

from session import get_db_context
from repositories import (
    UserRepository,
    GroupRepository,
    GroupMemberRepository,
    GroupInvitationRepository,
    ModelRepository,
    WorkerRepository,
    JobRepository,
    DataBatchRepository,
    transaction,
    execute_in_transaction
)
from models.group import GroupRole, InvitationStatus
from models.model import ModelStatus
from models.worker import WorkerStatus, WorkerType
from models.job import JobStatus
from models.data_batch import BatchStatus
from datetime import datetime, timedelta


def test_user_operations():
    """Test user CRUD operations."""
    print("\n" + "=" * 50)
    print("Testing User Operations")
    print("=" * 50)
    
    with get_db_context() as db:
        user_repo = UserRepository(db)
        
        # Create user
        user = user_repo.create(
            email="test@example.com",
            username="testuser",
            hashed_password="hashed_pw_123",
            full_name="Test User"
        )
        print(f"✅ Created user: {user.username} (ID: {user.id})")
        
        # Get by email
        found = user_repo.get_by_email("test@example.com")
        print(f"✅ Found by email: {found.email}")
        
        # Check existence
        exists = user_repo.email_exists("test@example.com")
        print(f"✅ Email exists check: {exists}")
        
        # Update user
        updated = user_repo.verify_user(user.id)
        print(f"✅ Verified user: is_verified={updated.is_verified}")
        
        # Clean up
        user_repo.delete(user.id)
        print(f"✅ Deleted user")


def test_group_operations():
    """Test group and membership operations."""
    print("\n" + "=" * 50)
    print("Testing Group Operations")
    print("=" * 50)
    
    with get_db_context() as db:
        user_repo = UserRepository(db)
        group_repo = GroupRepository(db)
        member_repo = GroupMemberRepository(db)
        
        # Create owner
        owner = user_repo.create(
            email="owner@example.com",
            username="owner",
            hashed_password="pw"
        )
        
        # Create group
        group = group_repo.create(
            name="Test Group",
            description="A test group",
            owner_id=owner.id
        )
        print(f"✅ Created group: {group.name} (ID: {group.id})")
        
        # Add owner as member
        membership = member_repo.add_member(group.id, owner.id, GroupRole.OWNER)
        print(f"✅ Added owner as member: role={membership.role}")
        
        # Create another member
        member_user = user_repo.create(
            email="member@example.com",
            username="member",
            hashed_password="pw"
        )
        member_repo.add_member(group.id, member_user.id, GroupRole.MEMBER)
        
        # Check membership
        is_member = member_repo.is_member(group.id, member_user.id)
        is_owner = member_repo.is_owner(group.id, owner.id)
        print(f"✅ Membership checks: is_member={is_member}, is_owner={is_owner}")
        
        # Get all members
        members = member_repo.get_group_members(group.id)
        print(f"✅ Group has {len(members)} members")
        
        # Clean up
        member_repo.remove_member(group.id, member_user.id)
        member_repo.remove_member(group.id, owner.id)
        group_repo.delete(group.id)
        user_repo.delete(owner.id)
        user_repo.delete(member_user.id)
        print(f"✅ Cleaned up")


def test_model_operations():
    """Test model repository operations."""
    print("\n" + "=" * 50)
    print("Testing Model Operations")
    print("=" * 50)
    
    with get_db_context() as db:
        user_repo = UserRepository(db)
        group_repo = GroupRepository(db)
        model_repo = ModelRepository(db)
        
        # Setup
        user = user_repo.create(email="ml@example.com", username="mluser", hashed_password="pw")
        group = group_repo.create(name="ML Group", owner_id=user.id)
        
        # Create model
        model = model_repo.create(
            name="CustomResNet",
            description="Custom ResNet architecture",
            uploaded_by_id=user.id,
            group_id=group.id,
            gcs_path="gs://meshml-models/1/model.py",
            status=ModelStatus.UPLOADING,
            version="1.0.0"
        )
        print(f"✅ Created model: {model.name} (status={model.status})")
        
        # Update lifecycle
        model_repo.set_validating(model.id)
        model_repo.set_ready(model.id, metadata={'layers': 50, 'params': '25M'})
        updated = model_repo.get_by_id(model.id)
        print(f"✅ Model lifecycle: {updated.status}, metadata={updated.model_metadata}")
        
        # Get ready models
        ready = model_repo.get_ready_models(group.id)
        print(f"✅ Ready models for group: {len(ready)}")
        
        # Clean up
        model_repo.delete(model.id)
        group_repo.delete(group.id)
        user_repo.delete(user.id)
        print(f"✅ Cleaned up")


def test_worker_operations():
    """Test worker repository operations."""
    print("\n" + "=" * 50)
    print("Testing Worker Operations")
    print("=" * 50)
    
    with get_db_context() as db:
        worker_repo = WorkerRepository(db)
        
        # Create worker
        worker = worker_repo.create(
            worker_id="worker-uuid-123",
            name="GPU Worker 1",
            worker_type=WorkerType.PYTHON,
            status=WorkerStatus.ONLINE,
            capabilities={
                'gpu': 'NVIDIA RTX 3080',
                'ram_gb': 16,
                'cpu_cores': 8
            },
            ip_address="192.168.1.100",
            port=8080,
            last_heartbeat=datetime.utcnow()
        )
        print(f"✅ Created worker: {worker.name} (ID: {worker.worker_id})")
        
        # Update heartbeat
        updated_worker = worker_repo.update_heartbeat(worker.worker_id)
        print(f"✅ Updated heartbeat: status={updated_worker.status}")
        
        # Get online workers
        online = worker_repo.get_online_workers()
        print(f"✅ Online workers: {len(online)}")
        
        # Clean up
        worker_repo.delete(worker.id)
        print(f"✅ Cleaned up")


def test_job_operations():
    """Test job repository operations."""
    print("\n" + "=" * 50)
    print("Testing Job Operations")
    print("=" * 50)
    
    with get_db_context() as db:
        user_repo = UserRepository(db)
        group_repo = GroupRepository(db)
        model_repo = ModelRepository(db)
        job_repo = JobRepository(db)
        batch_repo = DataBatchRepository(db)
        
        # Setup
        user = user_repo.create(email="trainer@example.com", username="trainer", hashed_password="pw")
        group = group_repo.create(name="Training Group", owner_id=user.id)
        model = model_repo.create(
            name="TestModel",
            uploaded_by_id=user.id,
            group_id=group.id,
            gcs_path="gs://path",
            status=ModelStatus.READY,
            version="1.0.0"
        )
        
        # Create job
        job = job_repo.create(
            name="MNIST Training",
            group_id=group.id,
            model_id=model.id,
            status=JobStatus.PENDING,
            config={'epochs': 10, 'batch_size': 32},
            dataset_path="gs://datasets/mnist",
            progress=0.0,
            current_epoch=0,
            total_epochs=10
        )
        print(f"✅ Created job: {job.name} (status={job.status})")
        
        # Update progress
        job_repo.update_progress(job.id, progress=50.0, current_epoch=5, metrics={'loss': 0.5})
        updated_job = job_repo.get_by_id(job.id)
        print(f"✅ Job progress: {updated_job.progress}%, epoch {updated_job.current_epoch}/{updated_job.total_epochs}")
        
        # Create batches
        for i in range(5):
            batch_repo.create(
                job_id=job.id,
                batch_index=i,
                shard_path=f"gs://batches/shard-{i}.pt",
                size_bytes=1024000,
                checksum=f"sha256-{i}",
                status=BatchStatus.PENDING,
                retry_count=0,
                max_retries=3
            )
        print(f"✅ Created 5 batches")
        
        # Get pending batches
        pending = batch_repo.get_pending_batches(job.id, limit=10)
        print(f"✅ Pending batches: {len(pending)}")
        
        # Calculate completion
        completion = batch_repo.get_job_completion_percentage(job.id)
        print(f"✅ Job completion: {completion}%")
        
        # Clean up
        batch_repo.delete_many({'job_id': job.id})
        job_repo.delete(job.id)
        model_repo.delete(model.id)
        group_repo.delete(group.id)
        user_repo.delete(user.id)
        print(f"✅ Cleaned up")


def test_transaction():
    """Test transaction management."""
    print("\n" + "=" * 50)
    print("Testing Transaction Management")
    print("=" * 50)
    
    def create_user_and_group(db, email: str, group_name: str):
        user_repo = UserRepository(db)
        group_repo = GroupRepository(db)
        member_repo = GroupMemberRepository(db)
        
        # All operations in same transaction
        user = user_repo.create(email=email, username=email.split('@')[0], hashed_password="pw")
        group = group_repo.create(name=group_name, owner_id=user.id)
        member_repo.add_member(group.id, user.id, GroupRole.OWNER)
        
        return user, group
    
    # Execute in transaction
    user, group = execute_in_transaction(
        create_user_and_group,
        email="trans@example.com",
        group_name="Transaction Test Group"
    )
    print(f"✅ Transaction completed: user={user.username}, group={group.name}")
    
    # Clean up
    with get_db_context() as db:
        member_repo = GroupMemberRepository(db)
        group_repo = GroupRepository(db)
        user_repo = UserRepository(db)
        
        member_repo.remove_member(group.id, user.id)
        group_repo.delete(group.id)
        user_repo.delete(user.id)
    
    print(f"✅ Cleaned up")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print(" DATABASE ACCESS LAYER TEST SUITE")
    print("=" * 70)
    
    try:
        test_user_operations()
        test_group_operations()
        test_model_operations()
        test_worker_operations()
        test_job_operations()
        test_transaction()
        
        print("\n" + "=" * 70)
        print(" ✅ ALL TESTS PASSED")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    main()
