-- ============================================================================
-- STEP 1: Database, Schemas, and Warehouse Setup
-- ============================================================================
-- Customize: Replace YOUR_DATABASE with your desired database name

-- Variables (customize these)
SET database_name = 'REALTIME_ML_PIPELINE';
SET warehouse_name = 'ML_INFERENCE_WH';

-- Create database
CREATE DATABASE IF NOT EXISTS IDENTIFIER($database_name);
USE DATABASE IDENTIFIER($database_name);

-- Create schemas
CREATE SCHEMA IF NOT EXISTS SPCS;           -- SPCS service functions
CREATE SCHEMA IF NOT EXISTS FEATURE_STORE;  -- Online feature store (Hybrid Tables)
CREATE SCHEMA IF NOT EXISTS ML_MODELS;      -- Model predictions & registry
CREATE SCHEMA IF NOT EXISTS STREAMLIT_APP;  -- Streamlit dashboard

-- Create warehouse for inference
CREATE WAREHOUSE IF NOT EXISTS IDENTIFIER($warehouse_name)
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE;

-- Grant usage
GRANT USAGE ON DATABASE IDENTIFIER($database_name) TO ROLE ACCOUNTADMIN;
GRANT USAGE ON ALL SCHEMAS IN DATABASE IDENTIFIER($database_name) TO ROLE ACCOUNTADMIN;
GRANT USAGE ON WAREHOUSE IDENTIFIER($warehouse_name) TO ROLE ACCOUNTADMIN;

-- Verify setup
SHOW SCHEMAS IN DATABASE IDENTIFIER($database_name);

SELECT 'Database setup complete!' AS status;

