"""
Database initialization module.
Handles PostgreSQL connection validation, schema creation, and initial data loading.
"""

import os
import json
import logging
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from config.config import INITIAL_KB_JSON_PATH, REQUIRED_TABLES

logger = logging.getLogger(__name__)


def init_database():
    """
    Initialize database and validate PostgreSQL connection.
    - Validates DATABASE_URL environment variable
    - Creates missing tables if needed (fallback)
    - Loads initial KB data into knowledge_base table if it's empty (first run)
    """
    db_url = os.getenv("DATABASE_URL")
    
    # Validate DATABASE_URL is set
    if not db_url:
        error_msg = (
            "FATAL: DATABASE_URL environment variable is not set.\n"
            "This application requires PostgreSQL.\n"
            "Example: postgresql://user:password@host:5432/bizclone_db"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    # Validate it's a PostgreSQL URL
    if not (db_url.startswith("postgresql://") or db_url.startswith("postgres://")):
        error_msg = (
            f"FATAL: Invalid DATABASE_URL. Only PostgreSQL is supported.\n"
            f"Got: {db_url[:60]}...\n"
            f"Expected format: postgresql://user:password@host:port/database"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        # Create engine
        engine = create_engine(db_url, echo=False)
        
        # Test connection before proceeding
        logger.info("Validating PostgreSQL connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            logger.info(f"✓ PostgreSQL connected: {version.split(',')[0]}")
        
        # Verify required tables exist
        logger.info("Verifying database schema...")
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        missing_tables = set(REQUIRED_TABLES) - set(existing_tables)
        if missing_tables:
            logger.warning(f"Missing tables: {', '.join(missing_tables)}")
            logger.info("Creating tables from ORM models (fallback)...")
            from database.orm_models import Base
            Base.metadata.create_all(engine)
            logger.info("✓ Database tables created")
        else:
            logger.info(f"✓ All {len(REQUIRED_TABLES)} required tables exist")
        
        # Initialize knowledge_base table with data from initial_email_kb.json if empty
        logger.info("Checking if knowledge_base needs initialization...")
        _initialize_knowledge_base(engine)
        
    except Exception as e:
        error_msg = f"FATAL: Database initialization failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise RuntimeError(error_msg)


def _initialize_knowledge_base(engine):
    """
    Load initial KB data from initial_email_kb.json into knowledge_base table.
    Uses ORM to properly handle JSON serialization.
    """
    from database.orm_models import KnowledgeBase
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check if knowledge_base is already populated
        kb_count = session.query(KnowledgeBase).count()
        
        if kb_count > 0:
            logger.info(f"✓ knowledge_base already initialized with {kb_count} record(s)")
            session.close()
            return
        
        # Load KB data from file
        kb_file_path = INITIAL_KB_JSON_PATH
        
        if not os.path.exists(kb_file_path):
            logger.warning(f"KB file not found at {kb_file_path}, skipping KB initialization")
            session.close()
            return
        
        with open(kb_file_path, 'r', encoding='utf-8') as f:
            kb_data = json.load(f)
        
        # Extract services, policies, faqs
        services = kb_data.get("services", {})
        policies = kb_data.get("policies", {})
        faqs = kb_data.get("faqs", [])
        
        now = datetime.utcnow()
        change_desc = "Initial KB loaded from initial_email_kb.json"
        
        # Insert each service using ORM
        for service_key, service_detail in services.items():
            kb_entry = KnowledgeBase(
                version_id=1,
                kb_field="service",
                item_key=service_key,
                detail=service_detail,  # ORM handles JSON serialization
                change_description=change_desc,
                updated_by="system",
                is_active=True,
                timestamp=now,
                last_updated=now,
                created_at=now
            )
            session.add(kb_entry)
        
        # Insert each policy using ORM
        for policy_key, policy_detail in policies.items():
            kb_entry = KnowledgeBase(
                version_id=1,
                kb_field="policy",
                item_key=policy_key,
                detail=policy_detail,  # ORM handles JSON serialization
                change_description=change_desc,
                updated_by="system",
                is_active=True,
                timestamp=now,
                last_updated=now,
                created_at=now
            )
            session.add(kb_entry)
        
        # Insert each FAQ using ORM
        for i, faq in enumerate(faqs):
            faq_key = f"faq_{i:03d}"
            # Ensure consistent field order: q before a
            ordered_faq = {"q": faq.get("q"), "a": faq.get("a")}
            kb_entry = KnowledgeBase(
                version_id=1,
                kb_field="faq",
                item_key=faq_key,
                detail=ordered_faq,  # ORM handles JSON serialization
                change_description=change_desc,
                updated_by="system",
                is_active=True,
                timestamp=now,
                last_updated=now,
                created_at=now
            )
            session.add(kb_entry)
        
        session.commit()
        
        logger.info(f"✓ knowledge_base initialized with version_id=1")
        logger.info(f"  - Services: {len(services)} items")
        logger.info(f"  - Policies: {len(policies)} items")
        logger.info(f"  - FAQs: {len(faqs)} items")
        logger.info(f"  - Total records: {len(services) + len(policies) + len(faqs)}")
        
    except json.JSONDecodeError as e:
        logger.error(f"✗ Failed to parse KB file: {str(e)}")
        session.rollback()
    except Exception as e:
        logger.error(f"✗ KB initialization failed: {str(e)}", exc_info=True)
        session.rollback()
    finally:
        session.close()
