"""
Base repository class with common CRUD operations.
"""
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, and_, or_
from services.database.models.base import Base

T = TypeVar('T', bound=Base)


class BaseRepository(Generic[T]):
    """Base repository with CRUD operations for any model."""
    
    def __init__(self, model: Type[T], db: Session):
        """
        Initialize repository.
        
        Args:
            model: SQLAlchemy model class
            db: Database session
        """
        self.model = model
        self.db = db
    
    # ============= CREATE Operations =============
    
    def create(self, **kwargs) -> T:
        """
        Create a new record.
        
        Args:
            **kwargs: Model field values
            
        Returns:
            Created instance
            
        Example:
            user = user_repo.create(
                email="user@example.com",
                username="user1",
                hashed_password="..."
            )
        """
        instance = self.model(**kwargs)
        self.db.add(instance)
        self.db.flush()  # Get ID without committing
        self.db.refresh(instance)
        return instance
    
    def create_many(self, items: List[Dict[str, Any]]) -> List[T]:
        """
        Bulk create multiple records.
        
        Args:
            items: List of dictionaries with field values
            
        Returns:
            List of created instances
        """
        instances = [self.model(**item) for item in items]
        self.db.add_all(instances)
        self.db.flush()
        return instances
    
    # ============= READ Operations =============
    
    def get_by_id(self, id: int) -> Optional[T]:
        """
        Get record by primary key.
        
        Args:
            id: Primary key value
            
        Returns:
            Instance or None if not found
        """
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def get_by_field(self, field: str, value: Any) -> Optional[T]:
        """
        Get first record matching field value.
        
        Args:
            field: Field name
            value: Field value
            
        Returns:
            Instance or None
            
        Example:
            user = user_repo.get_by_field('email', 'user@example.com')
        """
        return self.db.query(self.model).filter(getattr(self.model, field) == value).first()
    
    def get_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: Optional[str] = None,
        descending: bool = False
    ) -> List[T]:
        """
        Get all records with optional filtering and pagination.
        
        Args:
            filters: Dictionary of field:value pairs
            limit: Maximum number of records
            offset: Number of records to skip
            order_by: Field name to order by
            descending: Order descending if True
            
        Returns:
            List of instances
            
        Example:
            users = user_repo.get_all(
                filters={'is_active': True},
                limit=10,
                order_by='created_at',
                descending=True
            )
        """
        query = self.db.query(self.model)
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                query = query.filter(getattr(self.model, field) == value)
        
        # Apply ordering
        if order_by:
            order_field = getattr(self.model, order_by)
            query = query.order_by(order_field.desc() if descending else order_field)
        
        # Apply pagination
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records matching filters.
        
        Args:
            filters: Dictionary of field:value pairs
            
        Returns:
            Count of matching records
        """
        query = self.db.query(self.model)
        
        if filters:
            for field, value in filters.items():
                query = query.filter(getattr(self.model, field) == value)
        
        return query.count()
    
    def exists(self, **kwargs) -> bool:
        """
        Check if record exists with given fields.
        
        Args:
            **kwargs: Field values to check
            
        Returns:
            True if exists
            
        Example:
            exists = user_repo.exists(email='user@example.com')
        """
        query = self.db.query(self.model)
        for field, value in kwargs.items():
            query = query.filter(getattr(self.model, field) == value)
        return query.first() is not None
    
    # ============= UPDATE Operations =============
    
    def update(self, id: int, **kwargs) -> Optional[T]:
        """
        Update record by ID.
        
        Args:
            id: Primary key value
            **kwargs: Fields to update
            
        Returns:
            Updated instance or None if not found
            
        Example:
            user = user_repo.update(1, full_name="John Doe", is_verified=True)
        """
        instance = self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            self.db.flush()
            self.db.refresh(instance)
        return instance
    
    def update_many(self, filters: Dict[str, Any], **kwargs) -> int:
        """
        Bulk update records matching filters.
        
        Args:
            filters: Filter conditions
            **kwargs: Fields to update
            
        Returns:
            Number of updated records
            
        Example:
            count = user_repo.update_many(
                {'is_active': False},
                is_verified=False
            )
        """
        query = self.db.query(self.model)
        for field, value in filters.items():
            query = query.filter(getattr(self.model, field) == value)
        
        result = query.update(kwargs)
        self.db.flush()
        return result
    
    # ============= DELETE Operations =============
    
    def delete(self, id: int) -> bool:
        """
        Delete record by ID.
        
        Args:
            id: Primary key value
            
        Returns:
            True if deleted, False if not found
        """
        instance = self.get_by_id(id)
        if instance:
            self.db.delete(instance)
            self.db.flush()
            return True
        return False
    
    def delete_many(self, filters: Dict[str, Any]) -> int:
        """
        Bulk delete records matching filters.
        
        Args:
            filters: Filter conditions
            
        Returns:
            Number of deleted records
        """
        query = self.db.query(self.model)
        for field, value in filters.items():
            query = query.filter(getattr(self.model, field) == value)
        
        count = query.count()
        query.delete()
        self.db.flush()
        return count
    
    # ============= Utility Methods =============
    
    def refresh(self, instance: T) -> T:
        """Refresh instance from services.database."""
        self.db.refresh(instance)
        return instance
    
    def commit(self):
        """Commit current transaction."""
        self.db.commit()
    
    def rollback(self):
        """Rollback current transaction."""
        self.db.rollback()
    
    def flush(self):
        """Flush pending changes without committing."""
        self.db.flush()
