-- ============================================================================
-- STEP 3: Create SPCS Compute Pool and Image Repository
-- ============================================================================
-- Note: Requires ACCOUNTADMIN or appropriate privileges

USE DATABASE REALTIME_ML_PIPELINE;

-- ============================================================================
-- Create Compute Pool for SPCS
-- ============================================================================

CREATE COMPUTE POOL IF NOT EXISTS ML_INFERENCE_POOL
    MIN_NODES = 1
    MAX_NODES = 2
    INSTANCE_FAMILY = CPU_X64_XS  -- Smallest instance for cost efficiency
    AUTO_RESUME = TRUE
    AUTO_SUSPEND_SECS = 300;      -- Suspend after 5 minutes of inactivity

-- Check compute pool status
DESCRIBE COMPUTE POOL ML_INFERENCE_POOL;

-- ============================================================================
-- Create Image Repository for Docker images
-- ============================================================================

CREATE IMAGE REPOSITORY IF NOT EXISTS SPCS.IMAGES;

-- Get repository URL (you'll need this for Docker push)
SHOW IMAGE REPOSITORIES IN SCHEMA SPCS;

-- ============================================================================
-- Create Stage for SPCS specifications (optional)
-- ============================================================================

CREATE STAGE IF NOT EXISTS SPCS.SPECS
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');

-- ============================================================================
-- Grant necessary permissions
-- ============================================================================

GRANT USAGE ON COMPUTE POOL ML_INFERENCE_POOL TO ROLE ACCOUNTADMIN;
GRANT READ ON IMAGE REPOSITORY SPCS.IMAGES TO ROLE ACCOUNTADMIN;
GRANT WRITE ON IMAGE REPOSITORY SPCS.IMAGES TO ROLE ACCOUNTADMIN;

-- ============================================================================
-- Display repository URL for Docker push
-- ============================================================================

SELECT 
    repository_url,
    'docker tag your-image:tag ' || repository_url || '/evidence-api:v1' AS tag_command,
    'docker push ' || repository_url || '/evidence-api:v1' AS push_command
FROM (
    SELECT CONCAT(
        CURRENT_ACCOUNT(), 
        '.registry.snowflakecomputing.com/',
        LOWER(CURRENT_DATABASE()),
        '/spcs/images'
    ) AS repository_url
);

SELECT 'Compute pool setup complete!' AS status;

