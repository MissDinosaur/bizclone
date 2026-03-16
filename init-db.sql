-- PostgreSQL initialization script for BizClone
-- Creates all tables and configures the database
-- This runs automatically when the postgres container starts

-- Create schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS public;

-- Grant privileges to the application user
GRANT ALL PRIVILEGES ON SCHEMA public TO bizclone_user;

-- Create extensions needed by the application
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Set default privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO bizclone_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO bizclone_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO bizclone_user;

-- ============================================================
-- Table: email_history
-- Stores customer email conversations for context retrieval
-- ============================================================
CREATE TABLE IF NOT EXISTS email_history (
    id SERIAL PRIMARY KEY,
    customer_email VARCHAR(255) NOT NULL,
    sender_category VARCHAR(50),
    subject VARCHAR(500),
    body TEXT NOT NULL,
    our_reply TEXT,
    intent VARCHAR(100),
    channel VARCHAR(50) DEFAULT 'email',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_email_history_customer_email ON email_history(customer_email);
CREATE INDEX IF NOT EXISTS idx_email_history_timestamp ON email_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_email_history_intent ON email_history(intent);
CREATE INDEX IF NOT EXISTS idx_email_history_customer_timestamp ON email_history(customer_email, timestamp);

-- ============================================================
-- Table: booking
-- Stores appointment bookings across multiple channels
-- ============================================================
CREATE TABLE IF NOT EXISTS booking (
    id VARCHAR(50) PRIMARY KEY,
    customer_email VARCHAR(255) NOT NULL,
    slot TIMESTAMP NOT NULL,
    channel VARCHAR(50),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'confirmed',
    booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reminder_sent BOOLEAN DEFAULT FALSE,
    cancellation_reason TEXT,
    cancelled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_booking_customer_email ON booking(customer_email);
CREATE INDEX IF NOT EXISTS idx_booking_slot ON booking(slot);
CREATE INDEX IF NOT EXISTS idx_booking_status ON booking(status);
CREATE INDEX IF NOT EXISTS idx_booking_customer_slot ON booking(customer_email, slot);
CREATE INDEX IF NOT EXISTS idx_booking_status_booked ON booking(status, booked_at);

-- ============================================================
-- Sequence: knowledge_base_version_number
-- Auto-increment for knowledge_base version tracking
-- ============================================================
CREATE SEQUENCE IF NOT EXISTS knowledge_base_version_number_seq START 1;

-- ============================================================
-- Table: knowledge_base
-- Consolidated KB storage (merged from kb_version and kb_current)
-- Tracks all versions with is_active flag for the current version
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_base (
    version_id INTEGER PRIMARY KEY DEFAULT nextval('knowledge_base_version_number_seq'),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    kb_data JSONB NOT NULL,
    services JSONB,
    policies JSONB,
    faqs JSONB,
    change_description TEXT,
    updated_by VARCHAR(255),
    is_active BOOLEAN DEFAULT FALSE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_knowledge_base_timestamp ON knowledge_base(timestamp);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_is_active ON knowledge_base(is_active);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_last_updated ON knowledge_base(last_updated);

-- ============================================================
-- Table: kb_feedback
-- Complete audit trail of KB modifications
-- ============================================================
CREATE SEQUENCE IF NOT EXISTS kb_feedback_id_seq START 1;

CREATE TABLE IF NOT EXISTS kb_feedback (
    id INTEGER PRIMARY KEY DEFAULT nextval('kb_feedback_id_seq'),
    operation VARCHAR(50),
    kb_field VARCHAR(100),
    customer_question TEXT,
    owner_correction TEXT,
    service_name VARCHAR(255),
    service_description TEXT,
    service_price VARCHAR(100),
    kb_version_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kb_version_id) REFERENCES knowledge_base(version_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_kb_feedback_kb_field ON kb_feedback(kb_field);
CREATE INDEX IF NOT EXISTS idx_kb_feedback_timestamp ON kb_feedback(created_at);
CREATE INDEX IF NOT EXISTS idx_kb_feedback_timestamp_operation ON kb_feedback(created_at, operation);

-- ============================================================
-- Grant table permissions to application user
-- ============================================================
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bizclone_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bizclone_user;

-- Database is ready for application
COMMENT ON DATABASE bizclone_db IS 'BizClone AI Email Assistant Database - PostgreSQL backend';
