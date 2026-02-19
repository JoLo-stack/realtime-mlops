-- ============================================================================
-- 06_deploy_model_service.sql
-- Deploy Model from Model Registry as an Always-Running Inference Service
-- ============================================================================

USE DATABASE REALTIME_ML_PIPELINE;
USE SCHEMA ML_MODELS;
USE WAREHOUSE ML_INFERENCE_WH;

-- ============================================================================
-- Step 1: Create Image Repository for Model Service
-- ============================================================================

CREATE IMAGE REPOSITORY IF NOT EXISTS MODEL_IMAGES;

-- ============================================================================
-- Step 2: Create Procedure to Deploy Model as Service
-- ============================================================================

CREATE OR REPLACE PROCEDURE ML_MODELS.SP_DEPLOY_MODEL_SERVICE()
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'snowflake-ml-python>=1.5.0')
HANDLER = 'main'
EXECUTE AS OWNER
AS
$$
from snowflake.ml.registry import Registry
from snowflake.snowpark import Session
from datetime import datetime

def main(session: Session):
    """
    Deploy the trained model from Model Registry as an always-running
    inference service that can be called via internal DNS.
    """
    results = {
        'status': 'SUCCESS',
        'timestamp': datetime.now().isoformat(),
        'steps': []
    }
    
    try:
        # Initialize Model Registry
        registry = Registry(
            session=session,
            database_name='REALTIME_ML_PIPELINE',
            schema_name='ML_MODELS'
        )
        results['steps'].append('✅ Registry initialized')
        
        # Get the model
        model = registry.get_model('EVIDENCE_RISK_MODEL')
        mv = model.default  # or model.version('V2')
        
        results['model_name'] = 'EVIDENCE_RISK_MODEL'
        results['model_version'] = str(mv.version_name)
        results['steps'].append(f'✅ Got model version: {mv.version_name}')
        
        # Check for existing services
        try:
            existing = mv.list_services()
            if not existing.empty:
                results['steps'].append('ℹ️ Service already exists')
                results['existing_services'] = existing.to_dict()
                return results
        except Exception as e:
            results['steps'].append(f'ℹ️ No existing services: {e}')
        
        # Deploy as inference service
        # This creates an always-running container that serves the model
        service = mv.create_service(
            service_name='RISK_MODEL_SVC',
            service_compute_pool='ML_INFERENCE_POOL',
            image_repo='REALTIME_ML_PIPELINE.ML_MODELS.MODEL_IMAGES',
            ingress_enabled=True,
            max_instances=2
        )
        
        results['service_name'] = 'RISK_MODEL_SVC'
        results['steps'].append('✅ Model service deployed!')
        
        # Internal DNS will be: your-model-svc:5000/predict
        results['internal_dns'] = 'risk-model-svc:5000/predict'
        
    except Exception as e:
        results['status'] = 'ERROR'
        results['error'] = str(e)[:500]
    
    return results
$$;

-- ============================================================================
-- Step 3: Deploy the Model Service
-- ============================================================================

-- Run this to deploy your model as a service
CALL ML_MODELS.SP_DEPLOY_MODEL_SERVICE();

-- ============================================================================
-- Step 4: Verify Service is Running
-- ============================================================================

-- Check service status
SELECT 
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC'))[0]['status']::string AS status;

-- List services in schema
SHOW SERVICES IN SCHEMA ML_MODELS;

-- View service endpoints
SHOW ENDPOINTS IN SERVICE REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC;

-- ============================================================================
-- Step 5: Test Model Service (Optional)
-- ============================================================================

-- You can test the model service using the public endpoint or via your SPCS API
-- The SPCS API will call it via internal DNS: http://your-model-svc:5000/predict

-- ============================================================================
-- Useful Commands
-- ============================================================================

-- Suspend model service (saves costs when not in use)
-- ALTER SERVICE REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC SUSPEND;

-- Resume model service
-- ALTER SERVICE REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC RESUME;

-- View service logs
-- CALL SYSTEM$GET_SERVICE_LOGS('REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC', 0, 'model-inference', 50);

-- Drop service if needed
-- DROP SERVICE REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC;

