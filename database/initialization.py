"""
Database initialization module.
Handles PostgreSQL connection validation, schema creation, session management,
and initial data loading.
"""

import json
import logging
import os
from datetime import datetime

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from config.config import INITIAL_KB_JSON_PATH, REQUIRED_TABLES
from database.orm_models import Base as ORMBase, KnowledgeBase

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "FATAL: DATABASE_URL environment variable is not set. "
        "Expected format: postgresql://user:password@host:port/database"
    )

if not (
    DATABASE_URL.startswith("postgresql://")
    or DATABASE_URL.startswith("postgres://")
):
    raise ValueError(
        f"FATAL: Invalid DATABASE_URL. Only PostgreSQL is supported. Got: {DATABASE_URL[:60]}..."
    )

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """
    Initialize database and validate PostgreSQL connection.
    """
    try:
        logger.info("Validating PostgreSQL connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            logger.info(f"✓ PostgreSQL connected: {version.split(',')[0]}")

        logger.info("Verifying database schema...")
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        missing_tables = set(REQUIRED_TABLES) - set(existing_tables)

        if missing_tables:
            logger.warning(f"Missing tables: {', '.join(missing_tables)}")
            logger.info("Creating tables from ORM models...")
            ORMBase.metadata.create_all(engine)
            logger.info("✓ Tables created")
        else:
            logger.info(f"✓ All {len(REQUIRED_TABLES)} required tables exist")

        logger.info("Checking knowledge base initialization...")
        _initialize_knowledge_base()

    except Exception as e:
        logger.error(f"FATAL: Database initialization failed: {str(e)}", exc_info=True)
        raise


def _initialize_knowledge_base():
    """
    Load initial KB data if empty.
    """
    session = SessionLocal()

    try:
        kb_count = session.query(KnowledgeBase).count()

        if kb_count > 0:
            logger.info(f"✓ knowledge_base already initialized ({kb_count} records)")
            return

        if not os.path.exists(INITIAL_KB_JSON_PATH):
            logger.warning("KB file not found, skipping initialization")
            return

        with open(INITIAL_KB_JSON_PATH, "r", encoding="utf-8") as f:
            kb_data = json.load(f)

        services = kb_data.get("services", {})
        policies = kb_data.get("policies", {})
        faqs = kb_data.get("faqs", [])

        now = datetime.utcnow()

        for key, detail in services.items():
            session.add(
                KnowledgeBase(
                    version_id=1,
                    kb_field="service",
                    item_key=key,
                    detail=detail,
                    is_active=True,
                    timestamp=now,
                    last_updated=now,
                )
            )

        for key, detail in policies.items():
            session.add(
                KnowledgeBase(
                    version_id=1,
                    kb_field="policy",
                    item_key=key,
                    detail=detail,
                    is_active=True,
                    timestamp=now,
                    last_updated=now,
                )
            )

        for i, faq in enumerate(faqs):
            session.add(
                KnowledgeBase(
                    version_id=1,
                    kb_field="faq",
                    item_key=f"faq_{i}",
                    detail={"q": faq.get("q"), "a": faq.get("a")},
                    is_active=True,
                    timestamp=now,
                    last_updated=now,
                )
            )

        session.commit()

        logger.info("✓ Knowledge base initialized")

    except Exception as e:
        logger.error(f"KB init failed: {str(e)}", exc_info=True)
        session.rollback()
    finally:
        session.close()