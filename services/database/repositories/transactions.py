"""
Transaction management utilities for database operations.
"""
from typing import Callable, TypeVar, Any
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from database.session import get_db_context
import logging

T = TypeVar('T')
logger = logging.getLogger(__name__)


class TransactionError(Exception):
    """Custom exception for transaction errors."""
    pass


class DuplicateRecordError(TransactionError):
    """Raised when trying to create a duplicate record."""
    pass


@contextmanager
def transaction(db: Session, auto_commit: bool = True):
    """
    Context manager for database transactions with automatic rollback.
    
    Args:
        db: Database session
        auto_commit: Whether to commit automatically on success
        
    Raises:
        TransactionError: If transaction fails
        
    Example:
        with transaction(db):
            user_repo.create(email="...", username="...")
            group_repo.create(name="...", owner_id=user.id)
            # Auto-commits on success, auto-rollbacks on exception
    """
    try:
        yield db
        if auto_commit:
            db.commit()
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error in transaction: {e}")
        raise DuplicateRecordError(f"Record already exists or constraint violated: {e}")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error in transaction: {e}")
        raise TransactionError(f"Transaction failed: {e}")
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error in transaction: {e}")
        raise


def execute_in_transaction(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Execute a function within a transaction context.
    
    Args:
        func: Function to execute (must accept db as first argument)
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Function return value
        
    Raises:
        TransactionError: If transaction fails
        
    Example:
        def create_user_and_group(db: Session, email: str, group_name: str):
            user_repo = UserRepository(db)
            group_repo = GroupRepository(db)
            
            user = user_repo.create(email=email, username=email.split('@')[0])
            group = group_repo.create(name=group_name, owner_id=user.id)
            return user, group
        
        user, group = execute_in_transaction(
            create_user_and_group,
            email="user@example.com",
            group_name="My Group"
        )
    """
    with get_db_context() as db:
        try:
            result = func(db, *args, **kwargs)
            db.commit()
            return result
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error: {e}")
            raise DuplicateRecordError(f"Record already exists: {e}")
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error: {e}")
            raise TransactionError(f"Transaction failed: {e}")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error: {e}")
            raise


def batch_insert(db: Session, items: list, batch_size: int = 1000):
    """
    Insert items in batches for better performance.
    
    Args:
        db: Database session
        items: List of SQLAlchemy model instances
        batch_size: Number of items per batch
        
    Returns:
        Total number of items inserted
        
    Example:
        workers = [
            Worker(worker_id=f"worker-{i}", name=f"Worker {i}", ...)
            for i in range(10000)
        ]
        count = batch_insert(db, workers, batch_size=500)
    """
    total = len(items)
    inserted = 0
    
    try:
        for i in range(0, total, batch_size):
            batch = items[i:i + batch_size]
            db.bulk_save_objects(batch)
            db.flush()
            inserted += len(batch)
            logger.info(f"Inserted batch {i // batch_size + 1}: {len(batch)} items")
        
        db.commit()
        logger.info(f"Total inserted: {inserted} items")
        return inserted
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Batch insert failed: {e}")
        raise TransactionError(f"Batch insert failed: {e}")


def retry_transaction(
    func: Callable[..., T],
    max_retries: int = 3,
    *args,
    **kwargs
) -> T:
    """
    Retry a transaction function on failure.
    
    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Function return value
        
    Raises:
        TransactionError: If all retries fail
        
    Example:
        def update_job_progress(db: Session, job_id: int, progress: float):
            job_repo = JobRepository(db)
            return job_repo.update_progress(job_id, progress, ...)
        
        job = retry_transaction(update_job_progress, job_id=42, progress=67.5)
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return execute_in_transaction(func, *args, **kwargs)
        except DuplicateRecordError:
            # Don't retry on duplicate records
            raise
        except TransactionError as e:
            last_error = e
            logger.warning(f"Transaction attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying... ({max_retries - attempt - 1} attempts left)")
    
    logger.error(f"All {max_retries} transaction attempts failed")
    raise TransactionError(f"Transaction failed after {max_retries} attempts: {last_error}")


@contextmanager
def savepoint(db: Session, name: str = "savepoint"):
    """
    Create a savepoint for nested transactions.
    
    Args:
        db: Database session
        name: Savepoint name
        
    Example:
        with transaction(db):
            user_repo.create(...)  # Outer transaction
            
            try:
                with savepoint(db, "group_creation"):
                    group_repo.create(...)  # Nested transaction
                    # If this fails, only rolls back to savepoint
            except Exception:
                pass  # Outer transaction can still commit
    """
    sp = db.begin_nested()
    try:
        yield sp
        sp.commit()
    except Exception as e:
        sp.rollback()
        logger.warning(f"Savepoint '{name}' rolled back: {e}")
        raise
