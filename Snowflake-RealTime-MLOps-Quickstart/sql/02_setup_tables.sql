-- ============================================================================
-- STEP 2: Create Tables for Feature Store and Model Predictions
-- ============================================================================
-- Customize: Modify column names/types to match your feature schema

USE DATABASE REALTIME_ML_PIPELINE;

-- ============================================================================
-- Online Feature Store (Hybrid Table for low-latency reads/writes)
-- ============================================================================

CREATE OR REPLACE HYBRID TABLE FEATURE_STORE.ONLINE_FEATURES (
    -- Primary key
    POLICY_NUMBER VARCHAR(100) PRIMARY KEY,
    
    -- Data availability flags
    HAS_MIB_DATA BOOLEAN DEFAULT FALSE,
    HAS_RX_DATA BOOLEAN DEFAULT FALSE,
    
    -- MIB Features (customize for your domain)
    MIB_HIT_COUNT NUMBER DEFAULT 0,
    MIB_CODE_COUNT NUMBER DEFAULT 0,
    MIB_AVG_BMI FLOAT DEFAULT 0,
    MIB_MAX_BMI FLOAT DEFAULT 0,
    MIB_RISK_SCORE FLOAT DEFAULT 0,
    
    -- RX Features (customize for your domain)
    RX_TOTAL_FILLS NUMBER DEFAULT 0,
    RX_UNIQUE_DRUGS NUMBER DEFAULT 0,
    RX_UNIQUE_SPECIALTIES NUMBER DEFAULT 0,
    RX_DRUG_OPIOID BOOLEAN DEFAULT FALSE,
    RX_DRUG_BENZODIAZEPINE BOOLEAN DEFAULT FALSE,
    RX_DRUG_STATIN BOOLEAN DEFAULT FALSE,
    RX_DRUG_INSULIN BOOLEAN DEFAULT FALSE,
    RX_DRUG_METFORMIN BOOLEAN DEFAULT FALSE,
    RX_RISK_SCORE FLOAT DEFAULT 0,
    
    -- Risk flags (customize for your domain)
    FLAG_OPIOID_AND_BENZO BOOLEAN DEFAULT FALSE,
    FLAG_POLYPHARMACY_5 BOOLEAN DEFAULT FALSE,
    FLAG_POLYPHARMACY_10 BOOLEAN DEFAULT FALSE,
    FLAG_HIGH_RISK BOOLEAN DEFAULT FALSE,
    
    -- Combined scores
    COMBINED_RISK_SCORE FLOAT DEFAULT 0,
    
    -- Timestamps
    FEATURE_CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    FEATURE_UPDATED_AT TIMESTAMP_NTZ
);

-- ============================================================================
-- Model Predictions Table (stores all predictions with lineage)
-- ============================================================================

CREATE OR REPLACE TABLE ML_MODELS.MODEL_PREDICTIONS (
    -- Unique prediction ID
    PREDICTION_ID VARCHAR(100) PRIMARY KEY,
    
    -- Reference to entity
    POLICY_NUMBER VARCHAR(100) NOT NULL,
    
    -- Prediction output
    PREDICTION FLOAT,
    PREDICTION_CLASS VARCHAR(20),  -- HIGH, MEDIUM, LOW
    
    -- Model lineage
    MODEL_NAME VARCHAR(100),
    MODEL_VERSION VARCHAR(50),
    
    -- Timestamps
    SCORE_DATE TIMESTAMP_NTZ,
    CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    
    -- Index for fast lookups
    INDEX idx_policy (POLICY_NUMBER),
    INDEX idx_created (CREATED_AT)
);

-- ============================================================================
-- Raw Evidence Table (optional - for storing raw input)
-- ============================================================================

CREATE OR REPLACE HYBRID TABLE FEATURE_STORE.RAW_EVIDENCE (
    EVIDENCE_ID VARCHAR(100) PRIMARY KEY,
    POLICY_NUMBER VARCHAR(100),
    MIB_XML VARCHAR(16777216),  -- Raw MIB XML
    RX_XML VARCHAR(16777216),   -- Raw RX XML
    PROCESSING_STATUS VARCHAR(20) DEFAULT 'PENDING',
    CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PROCESSED_AT TIMESTAMP_NTZ,
    
    INDEX idx_policy (POLICY_NUMBER),
    INDEX idx_status (PROCESSING_STATUS)
);

-- Verify tables created
SHOW TABLES IN SCHEMA FEATURE_STORE;
SHOW TABLES IN SCHEMA ML_MODELS;

SELECT 'Tables setup complete!' AS status;

