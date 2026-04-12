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
    thread_id VARCHAR(255),
    message_id VARCHAR(255),
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
-- KB storage with item-level versioning
-- Each record represents a version of a specific KB item (individual service, policy, or faq)
-- Multiple items can share the same version_id when initialized together
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_base (
    version_id INTEGER NOT NULL DEFAULT nextval('knowledge_base_version_number_seq'),
    kb_field VARCHAR(50) NOT NULL CHECK (kb_field IN ('faq', 'policy', 'service')),
    item_key VARCHAR(255) NOT NULL,
    detail JSON NOT NULL,
    change_description TEXT,
    updated_by VARCHAR(255),
    is_active BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (version_id, kb_field, item_key)
);

CREATE INDEX IF NOT EXISTS idx_kb_field_active ON knowledge_base(kb_field, is_active);
CREATE INDEX IF NOT EXISTS idx_kb_item_active ON knowledge_base(kb_field, item_key, is_active);
CREATE INDEX IF NOT EXISTS idx_kb_field_item_version ON knowledge_base(kb_field, item_key, version_id);
CREATE INDEX IF NOT EXISTS idx_timestamp ON knowledge_base(timestamp);
CREATE INDEX IF NOT EXISTS idx_is_active ON knowledge_base(is_active);
CREATE INDEX IF NOT EXISTS idx_last_updated ON knowledge_base(last_updated);

-- ============================================================
-- Table: kb_feedback
-- Complete audit trail of KB modifications (feedback history)
-- Foreign Key: (kb_version_id, kb_field, item_key) REFERENCES knowledge_base (version_id, kb_field, item_key)
-- ============================================================
CREATE SEQUENCE IF NOT EXISTS kb_feedback_id_seq START 1;

CREATE TABLE IF NOT EXISTS kb_feedback (
    id INTEGER PRIMARY KEY DEFAULT nextval('kb_feedback_id_seq'),
    operation VARCHAR(50),
    kb_field VARCHAR(100),
    item_key VARCHAR(255),
    kb_version_id INTEGER,
    customer_question TEXT,
    owner_correction TEXT,
    service_name VARCHAR(255),
    service_description TEXT,
    service_price VARCHAR(100),
    policy_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_kb_feedback_knowledge_base 
        FOREIGN KEY (kb_version_id, kb_field, item_key) 
        REFERENCES knowledge_base(version_id, kb_field, item_key)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_kb_feedback_kb_field ON kb_feedback(kb_field);
CREATE INDEX IF NOT EXISTS idx_kb_feedback_timestamp ON kb_feedback(created_at);
CREATE INDEX IF NOT EXISTS idx_kb_feedback_timestamp_operation ON kb_feedback(created_at, operation);
CREATE INDEX IF NOT EXISTS idx_kb_feedback_version_key ON kb_feedback(kb_version_id, kb_field, item_key);

-- ============================================================
-- Table: customer
-- Customer profile information for birthday reminders and personalized service
-- ============================================================
CREATE TABLE IF NOT EXISTS customer (
    customer_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(20),
    date_of_birth DATE,
    home_address TEXT,
    city VARCHAR(100),
    state_province VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    preferred_contact_method VARCHAR(50) DEFAULT 'email',
    notification_opt_in BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_contacted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_customer_email ON customer(email);
CREATE INDEX IF NOT EXISTS idx_customer_dob ON customer(date_of_birth);
CREATE INDEX IF NOT EXISTS idx_customer_created ON customer(created_at);
CREATE INDEX IF NOT EXISTS idx_customer_contact_pref ON customer(preferred_contact_method);

-- ============================================================
-- Table: calendar_account
-- Stores OAuth tokens and calendar integration configuration for staff/users
-- ============================================================
CREATE TABLE IF NOT EXISTS calendar_account (
    account_id SERIAL PRIMARY KEY,
    staff_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('google', 'outlook')),
    email VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_calendar_account_provider_email ON calendar_account(provider, email);
CREATE INDEX IF NOT EXISTS idx_calendar_account_staff ON calendar_account(staff_id, provider);
CREATE INDEX IF NOT EXISTS idx_calendar_account_active ON calendar_account(is_active);

-- ============================================================
-- Grant table permissions to application user
-- ============================================================
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bizclone_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bizclone_user;

-- Database is ready for application
COMMENT ON DATABASE bizclone_db IS 'BizClone AI Email Assistant Database - PostgreSQL backend';
