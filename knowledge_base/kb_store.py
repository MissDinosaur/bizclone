"""
Knowledge Base Store - Database operations for KB management.
Handles version control, current KB caching, and feedback logging.
"""

import logging
import os
from datetime import datetime
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from database.orm_models import KnowledgeBase, KBFeedback

logger = logging.getLogger(__name__)


class KBStore:
    """Manage KB storage, versioning, and current state in PostgreSQL."""
    
    def __init__(self, db_url: str = None):
        """
        Initialize KB store with PostgreSQL.
        Args:
            db_url: PostgreSQL connection URL.
                   Defaults to DATABASE_URL environment variable (required).
        Raises:
            ValueError: If DATABASE_URL is not set or not a valid PostgreSQL URL.
        """
        if db_url is None:
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                raise ValueError(
                    "DATABASE_URL environment variable is required and must be set. "
                    "Example: postgresql://user:password@host:5432/database"
                )
        
        if not db_url.startswith("postgresql://") and not db_url.startswith("postgres://"):
            raise ValueError(
                f"Invalid database URL. Only PostgreSQL is supported. "
                f"Got: {db_url[:50]}..."
            )
        
        self.engine = create_engine(db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        logger.info("KBStore initialized with PostgreSQL database")
    
    def save_version(self, kb_field: str, item_key: str, detail: dict, change_desc: str = None, updated_by: str = None, activate: bool = True) -> int:
        """
        Save new KB version for a specific item.
        When activate=True (default), this method atomically:
        - Deactivates the current active version of this item
        - Creates and activates the new version
        
        Args:
            kb_field: 'faq', 'policy', or 'service'
            item_key: Unique key for this item (e.g., "emergency_plumbing" for service)
            detail: JSONB content for this item
            change_desc: Description of changes made
            updated_by: Who made the change (system/user)
            activate: Whether to activate this version immediately (default True)
            
        Returns: version_id (auto-generated or reused)
        """
        if kb_field not in ['faq', 'policy', 'service']:
            raise ValueError(f"Invalid kb_field: {kb_field}. Must be 'faq', 'policy', or 'service'")
        
        session = self.Session()
        try:
            # If activating, deactivate the current active version of this item
            if activate:
                session.query(KnowledgeBase).filter(
                    KnowledgeBase.kb_field == kb_field,
                    KnowledgeBase.item_key == item_key,
                    KnowledgeBase.is_active == True
                ).update({KnowledgeBase.is_active: False})
            
            now = datetime.utcnow()
            
            # Get the next version_id
            max_version = session.query(KnowledgeBase).order_by(
                desc(KnowledgeBase.version_id)
            ).first()
            next_version_id = (max_version.version_id + 1) if max_version else 1
            
            # Create new KB version for this item
            updated_kb = KnowledgeBase(
                version_id=next_version_id,
                kb_field=kb_field,
                item_key=item_key,
                detail=detail,
                change_description=change_desc,
                updated_by=updated_by,
                is_active=activate,
                timestamp=now,
                last_updated=now,
                created_at=now
            )
            session.add(updated_kb)
            session.commit()
            
            version_id = updated_kb.version_id
            if activate:
                logger.info(f"Saved and activated KB version {version_id} for {kb_field}[{item_key}]")
            else:
                logger.info(f"Saved KB version {version_id} for {kb_field}[{item_key}] (not activated)")
            return version_id
        except SQLAlchemyError as e:
            logger.error(f"Error saving KB version: {e}")
            session.rollback()
            return None
        finally:
            session.close()
    
    def get_version(self, version_id: int) -> dict:
        """Get specific KB version by version_id."""
        session = self.Session()
        try:
            version = session.query(KnowledgeBase).filter(
                KnowledgeBase.version_id == version_id
            ).first()
            return version.to_dict() if version else None
        finally:
            session.close()
    
    def get_latest_version(self) -> dict:
        """Get latest KB version."""
        session = self.Session()
        try:
            version = session.query(KnowledgeBase)\
                .order_by(desc(KnowledgeBase.version_id))\
                .first()
            return version.to_dict() if version else None
        finally:
            session.close()
    
    def get_version_history(self, limit: int = 10) -> list:
        """Get KB version history (most recent first)."""
        session = self.Session()
        try:
            versions = session.query(KnowledgeBase)\
                .order_by(desc(KnowledgeBase.timestamp))\
                .limit(limit)\
                .all()
            return [v.to_dict() for v in versions]
        finally:
            session.close()
    
    def set_current_kb(self, version_id: int) -> bool:
        """
        Activate an existing KB version. Deactivates all other versions.
        Used when rolling back to a previous version or manual activation.
        
        For creating and activating a new version in one atomic operation,
        use save_version(..., activate=True) instead.
        
        Args:
            version_id: ID of existing version to activate
        
        Returns: True if successful, False otherwise
        """
        session = self.Session()
        try:
            # Get target version
            target = session.query(KnowledgeBase).filter(
                KnowledgeBase.version_id == version_id
            ).first()
            
            if not target:
                logger.error(f"Version {version_id} not found")
                return False
            
            # Deactivate all versions and activate target (atomic)
            session.query(KnowledgeBase).update({KnowledgeBase.is_active: False})
            target.is_active = True
            target.last_updated = datetime.utcnow()
            
            session.commit()
            logger.info(f"Activated KB version {version_id}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error activating KB version: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_current_kb(self) -> dict:
        """Get currently active KB by combining all active items into structured format."""
        session = self.Session()
        try:
            # Get all active items
            active_items = session.query(KnowledgeBase).filter(
                KnowledgeBase.is_active == True
            ).all()
            
            # Reconstruct full KB from active items
            kb_data = {
                "services": {},
                "policies": {},
                "faqs": []
            }
            
            for item in active_items:
                if item.kb_field == 'service':
                    kb_data["services"][item.item_key] = item.detail
                elif item.kb_field == 'policy':
                    kb_data["policies"][item.item_key] = item.detail
                elif item.kb_field == 'faq':
                    kb_data["faqs"].append(item.detail)
            
            return kb_data
        finally:
            session.close()
    
    def save_feedback(self, feedback_entry: dict, kb_version_id: int = None) -> int:
        """
        Log KB feedback/update.
        Returns: feedback_id
        """
        session = self.Session()
        try:
            feedback = KBFeedback(
                operation=feedback_entry.get("operation", ""),
                kb_field=feedback_entry.get("kb_field", ""),
                customer_question=feedback_entry.get("customer_question", ""),
                owner_correction=feedback_entry.get("owner_correction", ""),
                service_name=feedback_entry.get("service_name", ""),
                service_description=feedback_entry.get("service_description", ""),
                service_price=feedback_entry.get("service_price", ""),
                policy_name=feedback_entry.get("policy_name", ""),
                kb_version_id=kb_version_id,
                created_at=datetime.utcnow()
            )
            session.add(feedback)
            session.commit()
            
            logger.info(f"Saved KB feedback: {feedback_entry.get('operation', '')} on {feedback_entry.get('kb_field', '')}")
            return feedback.id
        except SQLAlchemyError as e:
            logger.error(f"Error saving KB feedback: {e}")
            session.rollback()
            return None
        finally:
            session.close()
    
    def get_feedback_history(self, limit: int = 20) -> list:
        """Get KB feedback history (most recent first)."""
        session = self.Session()
        try:
            feedbacks = session.query(KBFeedback)\
                .order_by(desc(KBFeedback.created_at))\
                .limit(limit)\
                .all()
            return [f.to_dict() for f in feedbacks]
        finally:
            session.close()
    
    def rollback_to_version(self, version_id: int) -> bool:
        """Restore KB to previous version."""
        session = self.Session()
        try:
            # Get target version
            target = session.query(KnowledgeBase).filter(
                KnowledgeBase.version_id == version_id
            ).first()
            
            if not target:
                logger.error(f"Version {version_id} not found")
                return False
            
            # Activate the previous version
            self.set_current_kb(version_id)
            logger.info(f"Rolled back to version {version_id}")
            return True
        except Exception as e:
            logger.error(f"Error rolling back KB: {e}")
            return False
        finally:
            session.close()
    
    def get_stats(self) -> dict:
        """Get KB storage statistics."""
        session = self.Session()
        try:
            total_versions = session.query(KnowledgeBase).count()
            total_feedback = session.query(KBFeedback).count()
            latest = session.query(KnowledgeBase).order_by(
                desc(KnowledgeBase.version_id)
            ).first()
            
            return {
                "total_versions": total_versions,
                "total_feedback": total_feedback,
                "latest_version_id": latest.version_id if latest else None,
                "latest_updated": latest.timestamp.isoformat() if latest else None
            }
        finally:
            session.close()
