"""
Integration tests for database layer (TASK-1.5).

Tests the complete database stack:
- PostgreSQL schema (TASK-1.1)
- Redis cache (TASK-1.2)
- Repository pattern (TASK-1.3)
- Database seeding (TASK-1.4)

These tests verify that all components work together correctly.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from services.database.session import get_db_context
from services.database.seed import DatabaseSeeder
from services.database.repositories import (
    UserRepository, GroupRepository, GroupMemberRepository, GroupInvitationRepository,
    ModelRepository, WorkerRepository, JobRepository, DataBatchRepository
)
from services.database.repositories.transactions import (
    transaction, execute_in_transaction, batch_insert, retry_transaction, savepoint,
    TransactionError, DuplicateRecordError
)
from services.database.models.group import GroupRole, InvitationStatus
from services.database.models.model import ModelStatus
from services.database.models.worker import WorkerStatus, WorkerType
from services.database.models.job import JobStatus
from services.database.models.data_batch import BatchStatus


@pytest.fixture(scope="function")
def db_session():
    """Provide a clean database session for each test."""
    with get_db_context() as db:
        yield db
        # Cleanup after test
        db.rollback()


@pytest.fixture(scope="function")
def seeded_db():
    """Provide a database session with seeded test data."""
    with get_db_context() as db:
        seeder = DatabaseSeeder(db)
        seeder.seed_all(num_users=5, num_groups=3, num_workers=10)
        yield db, seeder
        # Cleanup
        seeder.clear_all()


class TestUserOperations:
    """Test user CRUD operations and constraints."""
    
    def test_create_user(self, db_session):
        """Test user creation."""
        user_repo = UserRepository(db_session)
        
        user = user_repo.create(
            email='test@example.com',
            username='testuser',
            hashed_password='hashed_pw',
            full_name='Test User'
        )
        
        assert user.id is not None
        assert user.email == 'test@example.com'
        assert user.username == 'testuser'
        assert user.is_active is True
        assert user.is_verified is False
        
        # Cleanup
        user_repo.delete(user.id)
    
    def test_unique_email_constraint(self, db_session):
        """Test that duplicate emails are rejected."""
        user_repo = UserRepository(db_session)
        
        user1 = user_repo.create(
            email='duplicate@example.com',
            username='user1',
            hashed_password='pw1'
        )
        db_session.commit()  # Commit first user
        
        # Try to create another user with same email
        with pytest.raises(Exception):  # Should raise IntegrityError
            user_repo.create(
                email='duplicate@example.com',
                username='user2',
                hashed_password='pw2'
            )
            db_session.commit()  # Try to commit duplicate
        
        # Rollback the failed transaction
        db_session.rollback()
        
        # Cleanup
        user_repo.delete(user1.id)
        db_session.commit()
    
    def test_user_verification_workflow(self, db_session):
        """Test user verification flow."""
        user_repo = UserRepository(db_session)
        
        user = user_repo.create(
            email='verify@example.com',
            username='verifyuser',
            hashed_password='pw'
        )
        
        assert user.is_verified is False
        
        # Verify user
        verified = user_repo.verify_user(user.id)
        assert verified.is_verified is True
        
        # Deactivate user
        deactivated = user_repo.deactivate_user(user.id)
        assert deactivated.is_active is False
        
        # Cleanup
        user_repo.delete(user.id)


class TestGroupCollaboration:
    """Test group collaboration features with RBAC."""
    
    def test_create_group_with_members(self, db_session):
        """Test group creation and member management."""
        user_repo = UserRepository(db_session)
        group_repo = GroupRepository(db_session)
        member_repo = GroupMemberRepository(db_session)
        
        # Create users
        owner = user_repo.create(email='owner@ex.com', username='owner', hashed_password='pw')
        admin = user_repo.create(email='admin@ex.com', username='admin', hashed_password='pw')
        member = user_repo.create(email='member@ex.com', username='member', hashed_password='pw')
        
        # Create group
        group = group_repo.create(name='Test Group', owner_id=owner.id)
        
        # Add members with different roles
        member_repo.add_member(group.id, admin.id, GroupRole.ADMIN)
        member_repo.add_member(group.id, member.id, GroupRole.MEMBER)
        
        # Verify roles
        assert member_repo.is_owner(group.id, owner.id) is False  # Owner not in members table
        assert member_repo.is_admin(group.id, admin.id) is True
        assert member_repo.is_member(group.id, member.id) is True
        
        # Get all members
        members = member_repo.get_group_members(group.id)
        assert len(members) == 2  # admin and member (owner is separate)
        
        # Cleanup
        group_repo.delete(group.id)
        user_repo.delete(owner.id)
        user_repo.delete(admin.id)
        user_repo.delete(member.id)
    
    def test_group_invitation_flow(self, db_session):
        """Test group invitation acceptance flow."""
        user_repo = UserRepository(db_session)
        group_repo = GroupRepository(db_session)
        invitation_repo = GroupInvitationRepository(db_session)
        
        # Create user and group
        owner = user_repo.create(email='owner@ex.com', username='owner', hashed_password='pw')
        group = group_repo.create(name='Test Group', owner_id=owner.id)
        
        # Create invitation
        invitation = invitation_repo.create(
            group_id=group.id,
            invited_by_id=owner.id,
            email='newuser@ex.com',
            token='unique-token-123',
            role=GroupRole.MEMBER,
            status=InvitationStatus.PENDING,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        # Verify invitation
        found = invitation_repo.get_by_token('unique-token-123')
        assert found is not None
        assert found.status == InvitationStatus.PENDING
        
        # Accept invitation
        accepted = invitation_repo.accept_invitation(invitation.id)
        assert accepted.status == InvitationStatus.ACCEPTED
        
        # Cleanup
        group_repo.delete(group.id)
        user_repo.delete(owner.id)


class TestModelLifecycle:
    """Test model lifecycle management (uploading → validating → ready/failed)."""
    
    def test_model_lifecycle_success(self, db_session):
        """Test successful model lifecycle."""
        user_repo = UserRepository(db_session)
        group_repo = GroupRepository(db_session)
        model_repo = ModelRepository(db_session)
        
        # Setup
        user = user_repo.create(email='uploader@ex.com', username='uploader', hashed_password='pw')
        group = group_repo.create(name='Test Group', owner_id=user.id)
        
        # Create model in uploading state
        model = model_repo.create(
            name='test-model',
            group_id=group.id,
            uploaded_by_id=user.id,
            gcs_path='gs://models/test.py',
            status=ModelStatus.UPLOADING
        )
        
        assert model.status == ModelStatus.UPLOADING
        
        # Move to validating
        validating = model_repo.set_validating(model.id)
        assert validating.status == ModelStatus.VALIDATING
        
        # Mark as ready with metadata
        ready = model_repo.set_ready(model.id, metadata={'params': 1000, 'size_bytes': 4096})
        assert ready.status == ModelStatus.READY
        assert ready.model_metadata['params'] == 1000
        
        # Cleanup
        model_repo.delete(model.id)
        group_repo.delete(group.id)
        user_repo.delete(user.id)
    
    def test_model_lifecycle_failure(self, db_session):
        """Test model validation failure."""
        user_repo = UserRepository(db_session)
        group_repo = GroupRepository(db_session)
        model_repo = ModelRepository(db_session)
        
        # Setup
        user = user_repo.create(email='uploader@ex.com', username='uploader', hashed_password='pw')
        group = group_repo.create(name='Test Group', owner_id=user.id)
        
        # Create model
        model = model_repo.create(
            name='bad-model',
            group_id=group.id,
            uploaded_by_id=user.id,
            gcs_path='gs://models/bad.py',
            status=ModelStatus.VALIDATING
        )
        
        # Mark as failed
        failed = model_repo.set_failed(model.id, error='Invalid forward() method')
        assert failed.status == ModelStatus.FAILED
        assert failed.validation_error == 'Invalid forward() method'
        
        # Cleanup
        model_repo.delete(model.id)
        group_repo.delete(group.id)
        user_repo.delete(user.id)


class TestJobWorkflow:
    """Test complete training job workflow."""
    
    def test_job_creation_and_progress(self, db_session):
        """Test job creation and progress tracking."""
        user_repo = UserRepository(db_session)
        group_repo = GroupRepository(db_session)
        model_repo = ModelRepository(db_session)
        job_repo = JobRepository(db_session)
        
        # Setup
        user = user_repo.create(email='trainer@ex.com', username='trainer', hashed_password='pw')
        group = group_repo.create(name='Test Group', owner_id=user.id)
        model = model_repo.create(
            name='model',
            group_id=group.id,
            uploaded_by_id=user.id,
            gcs_path='gs://models/m.py',
            status=ModelStatus.READY
        )
        
        # Create job
        job = job_repo.create(
            name='Test Job',
            group_id=group.id,
            model_id=model.id,
            config={'lr': 0.001},
            dataset_path='gs://data/train',
            total_epochs=10,
            status=JobStatus.PENDING
        )
        
        assert job.status == JobStatus.PENDING
        assert job.progress == 0.0
        
        # Start job
        running = job_repo.set_status(job.id, JobStatus.RUNNING)
        assert running.status == JobStatus.RUNNING
        
        # Update progress
        progressed = job_repo.update_progress(job.id, progress=50.0, current_epoch=5)
        assert progressed.progress == 50.0
        assert progressed.current_epoch == 5
        
        # Complete job
        completed = job_repo.mark_as_completed(job.id, final_metrics={'accuracy': 0.95})
        assert completed.status == JobStatus.COMPLETED
        
        # Cleanup
        job_repo.delete(job.id)
        model_repo.delete(model.id)
        group_repo.delete(group.id)
        user_repo.delete(user.id)
    
    def test_job_cancellation(self, db_session):
        """Test job cancellation workflow."""
        user_repo = UserRepository(db_session)
        group_repo = GroupRepository(db_session)
        model_repo = ModelRepository(db_session)
        job_repo = JobRepository(db_session)
        
        # Setup
        user = user_repo.create(email='trainer@ex.com', username='trainer', hashed_password='pw')
        group = group_repo.create(name='Test Group', owner_id=user.id)
        model = model_repo.create(
            name='model',
            group_id=group.id,
            uploaded_by_id=user.id,
            gcs_path='gs://models/m.py',
            status=ModelStatus.READY
        )
        
        # Create and start job
        job = job_repo.create(
            name='Job to Cancel',
            group_id=group.id,
            model_id=model.id,
            config={'lr': 0.001},
            dataset_path='gs://data/train',
            total_epochs=10,
            status=JobStatus.RUNNING
        )
        
        # Cancel job
        cancelled = job_repo.cancel_job(job.id)
        assert cancelled.status == JobStatus.CANCELLED
        
        # Cleanup
        job_repo.delete(job.id)
        model_repo.delete(model.id)
        group_repo.delete(group.id)
        user_repo.delete(user.id)


class TestWorkerManagement:
    """Test worker registration and heartbeat tracking."""
    
    def test_worker_heartbeat(self, db_session):
        """Test worker heartbeat updates."""
        worker_repo = WorkerRepository(db_session)
        
        # Register worker
        worker = worker_repo.create(
            worker_id='test-worker-001',
            name='Test Worker',
            worker_type=WorkerType.PYTHON,
            status=WorkerStatus.ONLINE,
            capabilities={'gpu': 'RTX 3080', 'ram_gb': 16},
            ip_address='192.168.1.100'
        )
        
        # Update heartbeat
        updated = worker_repo.update_heartbeat(worker.worker_id)
        assert updated.last_heartbeat is not None
        
        # Cleanup
        worker_repo.delete(worker.id)
    
    def test_stale_worker_detection(self, db_session):
        """Test marking stale workers as offline."""
        worker_repo = WorkerRepository(db_session)
        
        # Create worker with old heartbeat
        worker = worker_repo.create(
            worker_id='stale-worker-001',
            name='Stale Worker',
            worker_type=WorkerType.PYTHON,
            status=WorkerStatus.ONLINE,
            capabilities={'ram_gb': 8},
            ip_address='192.168.1.200'
        )
        db_session.commit()
        
        # Set heartbeat to 10 minutes ago
        from datetime import timezone
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        worker_repo.update(worker.id, last_heartbeat=old_time)
        db_session.commit()
        db_session.expire_all()  # Refresh from database
        
        # Mark stale workers (threshold: 5 minutes = 300 seconds)
        marked = worker_repo.mark_stale_workers_offline(timeout_seconds=300)
        
        # Verify worker is now offline
        db_session.expire_all()  # Refresh from database
        updated = worker_repo.get_by_id(worker.id)
        assert updated.status == WorkerStatus.OFFLINE
        
        # Cleanup
        worker_repo.delete(worker.id)
        db_session.commit()


class TestBatchDistribution:
    """Test data batch assignment and tracking."""
    
    def test_batch_assignment_workflow(self, db_session):
        """Test batch assignment to workers."""
        user_repo = UserRepository(db_session)
        group_repo = GroupRepository(db_session)
        model_repo = ModelRepository(db_session)
        job_repo = JobRepository(db_session)
        worker_repo = WorkerRepository(db_session)
        batch_repo = DataBatchRepository(db_session)
        
        # Setup
        user = user_repo.create(email='user@ex.com', username='user', hashed_password='pw')
        group = group_repo.create(name='Group', owner_id=user.id)
        model = model_repo.create(
            name='model',
            group_id=group.id,
            uploaded_by_id=user.id,
            gcs_path='gs://m.py',
            status=ModelStatus.READY
        )
        job = job_repo.create(
            name='Job',
            group_id=group.id,
            model_id=model.id,
            config={},
            dataset_path='gs://data',
            total_epochs=10,
            status=JobStatus.RUNNING
        )
        worker = worker_repo.create(
            worker_id='worker-001',
            name='Worker',
            worker_type=WorkerType.PYTHON,
            status=WorkerStatus.ONLINE,
            capabilities={'ram_gb': 8},
            ip_address='192.168.1.100'
        )
        
        # Create batch
        batch = batch_repo.create(
            job_id=job.id,
            batch_index=0,
            shard_path='gs://data/shard-0.pt',
            size_bytes=1024000,
            checksum='a' * 64,
            status=BatchStatus.PENDING
        )
        
        assert batch.status == BatchStatus.PENDING
        assert batch.worker_id is None
        
        # Assign to worker
        assigned = batch_repo.assign_to_worker(batch.id, worker.id)
        assert assigned.status == BatchStatus.ASSIGNED
        assert assigned.worker_id == worker.id
        
        # Mark processing
        processing = batch_repo.mark_processing(batch.id)
        assert processing.status == BatchStatus.PROCESSING
        
        # Mark completed
        completed = batch_repo.mark_completed(batch.id)
        assert completed.status == BatchStatus.COMPLETED
        
        # Cleanup
        batch_repo.delete(batch.id)
        worker_repo.delete(worker.id)
        job_repo.delete(job.id)
        model_repo.delete(model.id)
        group_repo.delete(group.id)
        user_repo.delete(user.id)
    
    def test_job_completion_percentage(self, db_session):
        """Test job completion percentage calculation."""
        user_repo = UserRepository(db_session)
        group_repo = GroupRepository(db_session)
        model_repo = ModelRepository(db_session)
        job_repo = JobRepository(db_session)
        batch_repo = DataBatchRepository(db_session)
        
        # Setup
        user = user_repo.create(email='user@ex.com', username='user', hashed_password='pw')
        group = group_repo.create(name='Group', owner_id=user.id)
        model = model_repo.create(
            name='model',
            group_id=group.id,
            uploaded_by_id=user.id,
            gcs_path='gs://m.py',
            status=ModelStatus.READY
        )
        job = job_repo.create(
            name='Job',
            group_id=group.id,
            model_id=model.id,
            config={},
            dataset_path='gs://data',
            total_epochs=10
        )
        
        # Create 10 batches
        for i in range(10):
            status = BatchStatus.COMPLETED if i < 3 else BatchStatus.PENDING
            batch_repo.create(
                job_id=job.id,
                batch_index=i,
                shard_path=f'gs://data/shard-{i}.pt',
                size_bytes=1024000,
                checksum='a' * 64,
                status=status
            )
        
        # Calculate completion percentage
        percentage = batch_repo.get_job_completion_percentage(job.id)
        assert percentage == 30.0  # 3 out of 10 completed
        
        # Cleanup
        job_repo.delete(job.id)
        model_repo.delete(model.id)
        group_repo.delete(group.id)
        user_repo.delete(user.id)


class TestTransactionManagement:
    """Test transaction utilities."""
    
    def test_transaction_commit(self, db_session):
        """Test transaction commit."""
        user_repo = UserRepository(db_session)
        
        with transaction(db_session):
            user = user_repo.create(email='tx@ex.com', username='tx', hashed_password='pw')
            assert user.id is not None
        
        # Verify committed
        found = user_repo.get_by_email('tx@ex.com')
        assert found is not None
        
        # Cleanup
        user_repo.delete(found.id)
    
    def test_transaction_rollback(self, db_session):
        """Test transaction rollback on error."""
        user_repo = UserRepository(db_session)
        
        try:
            with transaction(db_session):
                user_repo.create(email='rollback@ex.com', username='rollback', hashed_password='pw')
                raise Exception("Intentional error")
        except:
            pass
        
        # Verify rolled back
        found = user_repo.get_by_email('rollback@ex.com')
        assert found is None
    
    def test_execute_in_transaction(self, db_session):
        """Test execute_in_transaction utility."""
        def create_user_and_group(db):
            user_repo = UserRepository(db)
            group_repo = GroupRepository(db)
            user = user_repo.create(email='func@ex.com', username='func', hashed_password='pw')
            group = group_repo.create(name='Func Group', owner_id=user.id)
            return user, group
        
        user, group = execute_in_transaction(create_user_and_group)
        
        assert user.id is not None
        assert group.id is not None
        assert group.owner_id == user.id
        
        # Cleanup using db_session
        user_repo = UserRepository(db_session)
        group_repo = GroupRepository(db_session)
        group_repo.delete(group.id)
        user_repo.delete(user.id)
        db_session.commit()
        
        # Cleanup
        group_repo.delete(group.id)
        user_repo.delete(user.id)
    
    def test_savepoint(self, db_session):
        """Test savepoint for nested transactions."""
        user_repo = UserRepository(db_session)
        group_repo = GroupRepository(db_session)
        
        with transaction(db_session):
            user = user_repo.create(email='sp@ex.com', username='sp', hashed_password='pw')
            
            try:
                with savepoint(db_session, "group_creation"):
                    group = group_repo.create(name='SP Group', owner_id=999999)  # Invalid ID
            except:
                pass  # Savepoint rolled back
            
            # User should still exist after savepoint rollback
            pass
        
        # Verify user was created
        found = user_repo.get_by_email('sp@ex.com')
        assert found is not None
        
        # Cleanup
        user_repo.delete(found.id)


class TestSeededData:
    """Test operations on seeded data."""
    
    def test_seeded_users(self, seeded_db):
        """Test seeded users are accessible."""
        db, seeder = seeded_db
        
        assert len(seeder.users) == 5
        
        user_repo = UserRepository(db)
        alice = user_repo.get_by_email('alice@university.edu')
        
        assert alice is not None
        assert alice.username == 'alice'
        assert alice.is_verified is True
    
    def test_seeded_groups(self, seeded_db):
        """Test seeded groups and memberships."""
        db, seeder = seeded_db
        
        assert len(seeder.groups) == 3
        
        member_repo = GroupMemberRepository(db)
        
        # AI Research Lab: Alice (owner), Bob (admin), Charlie (member)
        ai_lab = seeder.groups[0]
        members = member_repo.get_group_members(ai_lab.id)
        
        assert len(members) == 2  # Bob and Charlie (owner is separate)
    
    def test_seeded_jobs_and_batches(self, seeded_db):
        """Test seeded jobs have data batches."""
        db, seeder = seeded_db
        
        assert len(seeder.jobs) == 3
        
        batch_repo = DataBatchRepository(db)
        
        # Find running job
        running_jobs = [j for j in seeder.jobs if j.status == JobStatus.RUNNING]
        if running_jobs:
            job = running_jobs[0]
            batches = batch_repo.get_by_job(job.id)
            assert len(batches) == 100  # Seeder creates 100 batches for running job
    
    def test_query_across_seeded_data(self, seeded_db):
        """Test complex queries across seeded data."""
        db, seeder = seeded_db
        
        model_repo = ModelRepository(db)
        job_repo = JobRepository(db)
        
        # Get ready models
        ready_models = model_repo.get_ready_models()
        assert len(ready_models) >= 2  # At least 2 ready models seeded
        
        # Get active jobs
        active_jobs = job_repo.get_active_jobs()
        assert len(active_jobs) >= 1  # At least 1 active job seeded


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
