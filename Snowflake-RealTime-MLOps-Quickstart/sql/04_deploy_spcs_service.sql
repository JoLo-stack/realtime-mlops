-- ============================================================================
-- STEP 4: Deploy SPCS Service and Create Service Functions
-- ============================================================================
-- Run AFTER:
--   1. Pushing Docker image to repository (Step 5 in checklist)
--   2. Deploying model service (Step 4 / sql/06_deploy_model_service.sql)
--   3. Getting MODEL_SERVICE_URL from DESC SERVICE (Step 4.5 in checklist)

USE DATABASE REALTIME_ML_PIPELINE;

-- ============================================================================
-- ⚠️ IMPORTANT: Get Model Service URL First!
-- ============================================================================
-- Before running this script, you MUST get the model service internal DNS name.
-- Run this query and note the service name:
--
--   DESC SERVICE REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC;
--
-- Then construct the URL: http://<service-name>:5000/predict
-- Example: http://risk-scoring-svc:5000/predict
--
-- Update the MODEL_SERVICE_URL below with YOUR service name!
-- ============================================================================

-- Drop existing service if needed
DROP SERVICE IF EXISTS ML_MODELS.INFERENCE_SERVICE;

-- Create the service with Model Registry integration
CREATE SERVICE ML_MODELS.INFERENCE_SERVICE
    IN COMPUTE POOL ML_INFERENCE_POOL
    FROM SPECIFICATION $$
spec:
  containers:
    - name: api
      image: /realtime_ml_pipeline/spcs/images/evidence-api:v1
      env:
        SNOWFLAKE_DATABASE: REALTIME_ML_PIPELINE
        SNOWFLAKE_SCHEMA: ML_MODELS
        # Enable Model Registry integration (set to 'true' to use model service)
        USE_MODEL_REGISTRY: 'true'
        # ============================================================
        # ⚠️ UPDATE THIS URL WITH YOUR MODEL SERVICE NAME!
        # ============================================================
        # Format: http://<your-model-service-name>:5000/predict
        # 
        # To get your service name:
        #   1. Run: DESC SERVICE REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC;
        #   2. Use the service name (e.g., 'risk-scoring-svc')
        #   3. Format: http://risk-scoring-svc:5000/predict
        #
        # Note: Use http:// (not https://) for internal DNS
        # Note: Port 5000 is the default model service port
        # ============================================================
        MODEL_SERVICE_URL: 'http://risk-model-svc:5000/predict'
      resources:
        requests:
          memory: 1G
          cpu: 1
        limits:
          memory: 2G
          cpu: 2
  endpoints:
    - name: api
      port: 8000
      public: true
$$
    MIN_INSTANCES = 1
    MAX_INSTANCES = 2;

-- Wait for service to start (check status)
CALL SYSTEM$GET_SERVICE_STATUS('ML_MODELS.INFERENCE_SERVICE');

-- ============================================================================
-- Create Service Function for SQL Access
-- ============================================================================

CREATE OR REPLACE FUNCTION ML_MODELS.FN_API_PREDICT(
    policy_number VARCHAR,
    mib_xml VARCHAR,
    rx_xml VARCHAR
)
RETURNS VARIANT
SERVICE = ML_MODELS.INFERENCE_SERVICE
ENDPOINT = api
AS '/predict';

-- ============================================================================
-- Create Health Check Function
-- ============================================================================

CREATE OR REPLACE FUNCTION ML_MODELS.FN_HEALTH()
RETURNS VARIANT
SERVICE = ML_MODELS.INFERENCE_SERVICE
ENDPOINT = api
AS '/health';

-- ============================================================================
-- Test the Service
-- ============================================================================

-- Test health endpoint
SELECT ML_MODELS.FN_HEALTH() AS health_check;

-- Test prediction endpoint with Model Registry
SELECT ML_MODELS.FN_API_PREDICT(
    'TEST-001',
    '<?xml version="1.0"?><Response><ResponseData>CODE1</ResponseData></Response>',
    '<?xml version="1.0"?><IntelRXResponse><DrugFill><DrugGenericName>METFORMIN</DrugGenericName></DrugFill></IntelRXResponse>'
)::variant AS prediction_result;

-- Verify Model Registry was used
SELECT 
    result:model_version::string AS model_version,
    result:risk_score::float AS risk_score,
    result:inference_ms::float AS latency_ms
FROM (
    SELECT ML_MODELS.FN_API_PREDICT('TEST-002', '<r/>', '<r/>') AS result
);

-- Expected output:
-- MODEL_VERSION    | RISK_SCORE | LATENCY_MS
-- REGISTRY_V2      | 0.xx       | ~17-50

-- ============================================================================
-- Useful Management Commands
-- ============================================================================

-- Check service status
-- CALL SYSTEM$GET_SERVICE_STATUS('ML_MODELS.INFERENCE_SERVICE');

-- View service logs (check for Model Registry calls)
-- CALL SYSTEM$GET_SERVICE_LOGS('ML_MODELS.INFERENCE_SERVICE', 0, 'api', 100);

-- Suspend service (stop costs)
-- ALTER SERVICE ML_MODELS.INFERENCE_SERVICE SUSPEND;

-- Resume service
-- ALTER SERVICE ML_MODELS.INFERENCE_SERVICE RESUME;

-- Get service endpoint URL
-- SHOW ENDPOINTS IN SERVICE ML_MODELS.INFERENCE_SERVICE;

-- ============================================================================
-- Verify Both Services Are Running (Required for Internal DNS)
-- ============================================================================

SELECT 
    'API_SERVICE' AS service,
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('REALTIME_ML_PIPELINE.ML_MODELS.INFERENCE_SERVICE'))[0]['status']::string AS status
UNION ALL
SELECT 
    'MODEL_SERVICE' AS service,
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC'))[0]['status']::string AS status;

-- Both should show "READY" for internal DNS to work

SELECT 'SPCS service deployed with Model Registry integration!' AS status;
