# Real-Time ML Inference with Snowpark Container Services (SPCS)

## Overview

This quickstart demonstrates how to build a **sub-100ms real-time ML inference pipeline** using Snowflake's native MLOps capabilities:

- **Snowpark Container Services (SPCS)** - Always-running FastAPI container for ultra-low latency
- **Model Registry** - Native Snowflake ML for model versioning, deployment, and inference
- **Internal DNS** - Service-to-service communication within Snowflake for minimal latency
- **Online Feature Store** - Hybrid Tables for real-time feature serving and audit trails
- **Streamlit Dashboard** - Real-time monitoring and testing UI

## Performance Achieved

| Mode | Latency | Description |
|------|---------|-------------|
| **SPCS + Model Registry** | **~50-100ms** | Full MLOps with internal DNS |
| Model Inference Only | ~17ms | Model Registry service via internal DNS |
| Feature Store Write | ~30-50ms | Async write to Hybrid Table |
| Legacy Batch | ~30+ seconds | Traditional batch processing |

## Architecture (Per MLOps Best Practices)

This architecture follows Snowflake MLOps best practices for real-time inference:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    REAL-TIME ML INFERENCE PIPELINE                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐                                                            │
│   │   Request   │  Policy application with MIB/RX data                       │
│   └──────┬──────┘                                                            │
│          │                                                                   │
│          ▼                                                                   │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                    SPCS API SERVICE                                   │  │
│   │              (evidence-api container)                                 │  │
│   │                                                                       │  │
│   │   1. Receive request via SQL function                                │  │
│   │   2. Parse XML and extract 100+ features                             │  │
│   │   3. Call Model Registry Service via internal DNS ───────────────┐   │  │
│   │   4. Return prediction to caller                                 │   │  │
│   │   5. Async: Write to Feature Store & Predictions table           │   │  │
│   │                                                                   │   │  │
│   └───────────────────────────────────────────────────────────────────┼──┘  │
│                          │                                            │      │
│                          │ (async)                                    │      │
│                          ▼                                            ▼      │
│   ┌─────────────────────────────────┐    ┌────────────────────────────────┐ │
│   │       FEATURE STORE             │    │    MODEL REGISTRY SERVICE      │ │
│   │    (HT_ONLINE_FEATURES)         │    │      (risk-model-svc)          │ │
│   │                                 │    │                                │ │
│   │  • Hybrid Table for OLTP        │    │  • EVIDENCE_RISK_MODEL V2      │ │
│   │  • 100+ features per policy     │    │  • Deployed via mv.create_     │ │
│   │  • Full audit trail             │    │    service()                   │ │
│   │  • Real-time writes             │    │  • Internal DNS: risk-model-   │ │
│   └─────────────────────────────────┘    │    svc:5000/predict            │ │
│                                          │  • ~17ms inference latency     │ │
│   ┌─────────────────────────────────┐    └────────────────────────────────┘ │
│   │      PREDICTIONS TABLE          │                                       │
│   │    (MODEL_PREDICTIONS)          │                                       │
│   │                                 │                                       │
│   │  • Every prediction logged      │                                       │
│   │  • Model name & version tracked │                                       │
│   │  • Full lineage for compliance  │                                       │
│   └─────────────────────────────────┘                                       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Key Innovation: Internal DNS for Model Inference

The critical optimization is using **internal DNS** to call the Model Registry service:

```
┌─────────────────────┐         ┌─────────────────────┐
│  SPCS API Service   │  HTTP   │  Model Registry     │
│  (evidence-api)     │ ──────▶ │  (risk-model-svc)   │
│                     │         │                     │
│  Extracts features  │  DNS:   │  EVIDENCE_RISK_     │
│  Calls model        │  risk-  │  MODEL V2           │
│  Returns response   │  model- │                     │
│                     │  svc:   │  ~17ms inference    │
│                     │  5000   │                     │
└─────────────────────┘         └─────────────────────┘
```

**Why Internal DNS?**
- No network egress (stays within Snowflake)
- Eliminates cold start issues (model service always warm)
- ~17ms model inference (vs 10+ seconds for SQL-based model calls)
- True Model Registry integration with full lineage

## Prerequisites

- Snowflake account with SPCS enabled
- Docker Desktop installed
- Snowflake CLI (`snow`) installed
- ACCOUNTADMIN role (for initial setup)

## Quick Start

### Step 1: Configure Connection

```bash
# Set your Snowflake credentials
export SNOWFLAKE_ACCOUNT="your-account"
export SNOWFLAKE_USER="your-user"
export SNOWFLAKE_PASSWORD="your-password"

# Or use Snowflake CLI connection
snow connection add --connection-name default
```

### Step 2: Run Setup SQL

```bash
# Execute setup scripts in order
snow sql -f sql/01_setup_database.sql --connection default
snow sql -f sql/02_setup_tables.sql --connection default
snow sql -f sql/03_setup_compute_pool.sql --connection default
```

### Step 3: Train and Register Model

```sql
-- Register your trained model to the Model Registry
-- This example uses a GradientBoostingClassifier

CALL YOUR_DATABASE.ML_MODELS.SP_TRAIN_AND_REGISTER_MODEL();

-- Verify model is registered
SHOW MODELS IN SCHEMA YOUR_DATABASE.ML_MODELS;
```

### Step 4: Deploy Model as Inference Service

```sql
-- Deploy the model as an always-running inference service
-- This creates the internal DNS endpoint

CALL YOUR_DATABASE.ML_MODELS.SP_DEPLOY_MODEL_SERVICE();

-- Verify service is running
CALL SYSTEM$GET_SERVICE_STATUS('YOUR_DATABASE.ML_MODELS.RISK_MODEL_SVC');
```

### Step 4.5: Get Model Service URL (⚠️ Critical!)

**Before deploying the API container, you MUST get the model service URL:**

```sql
-- Get the internal DNS name for your model service
DESC SERVICE YOUR_DATABASE.ML_MODELS.RISK_MODEL_SVC;
-- Note the service name (e.g., 'risk-model-svc')
```

Then update `sql/04_deploy_spcs_service.sql` with your model service URL:

```yaml
# In the spec section, update MODEL_SERVICE_URL:
MODEL_SERVICE_URL: 'http://risk-model-svc:5000/predict'
#                        ^^^^^^^^^^^^^^ Your service name here
```

**URL Format:** `http://<service-name>:5000/predict`
- Use `http://` (not `https://`) for internal DNS
- Port `5000` is the default for model services
- When in the same schema, use just the service name

See `SETUP_CHECKLIST.md` Step 4.5 for detailed instructions.

### Step 5: Deploy SPCS API Container

```bash
cd spcs

# Build and push Docker image
docker build --platform linux/amd64 -t evidence-api:v1 .

# Login to Snowflake image registry
snow spcs image-registry login --connection default

# Tag and push
docker tag evidence-api:v1 YOUR_ACCOUNT.registry.snowflakecomputing.com/your_database/spcs/images/evidence-api:v1
docker push YOUR_ACCOUNT.registry.snowflakecomputing.com/your_database/spcs/images/evidence-api:v1

# Deploy service
snow sql -f ../sql/04_deploy_spcs_service.sql --connection default
```

### Step 6: Test the Pipeline

```sql
-- Test end-to-end inference
SELECT YOUR_DATABASE.ML_MODELS.FN_API_PREDICT(
    'TEST-001',
    '<?xml version="1.0"?><Response><ResponseData>CODE1</ResponseData></Response>',
    '<?xml version="1.0"?><IntelRXResponse><DrugFill><DrugGenericName>METFORMIN</DrugGenericName></DrugFill></IntelRXResponse>'
)::variant AS result;

-- Check the result
SELECT 
    result:policy_number::string AS policy,
    result:risk_score::float AS score,
    result:model_version::string AS model,
    result:inference_ms::float AS latency_ms
FROM (SELECT YOUR_DATABASE.ML_MODELS.FN_API_PREDICT('TEST-002', '<r/>', '<r/>') AS result);
```

### Step 7: Deploy Streamlit Dashboard (Optional)

```bash
snow stage copy streamlit/streamlit_app.py @YOUR_DATABASE.STREAMLIT.STAGE/ --connection default
snow sql -f sql/05_deploy_streamlit.sql --connection default
```

## MLOps Features

### Model Registry Integration

Every prediction is tracked with full lineage:

```sql
-- View predictions with model info
SELECT 
    POLICY_NUMBER,
    PREDICTION,
    MODEL_NAME,
    MODEL_VERSION,
    SCORE_DATE
FROM YOUR_DATABASE.ML_MODELS.MODEL_PREDICTIONS
ORDER BY SCORE_DATE DESC
LIMIT 10;
```

### Feature Store for Audit & Reproducibility

All input features are stored for compliance:

```sql
-- View features used for a specific prediction
SELECT *
FROM YOUR_DATABASE.HYBRID_REALTIME.HT_ONLINE_FEATURES
WHERE POLICY_NUMBER = 'TEST-001';
```

### Model Versioning

Deploy new model versions without downtime:

```sql
-- Register new model version
CALL YOUR_DATABASE.ML_MODELS.SP_REGISTER_MODEL_V3();

-- Update the model service to use new version
ALTER SERVICE YOUR_DATABASE.ML_MODELS.RISK_MODEL_SVC 
SET DEFAULT_VERSION = 'V3';
```

## File Structure

```
quickstart/
├── README.md                     # This file
├── sql/
│   ├── 01_setup_database.sql     # Database, schemas, warehouse
│   ├── 02_setup_tables.sql       # Feature Store & Predictions tables
│   ├── 03_setup_compute_pool.sql # SPCS compute pool
│   ├── 04_deploy_spcs_service.sql # SPCS service deployment
│   ├── 05_deploy_streamlit.sql   # Streamlit app deployment
│   └── 06_deploy_model_service.sql # Model Registry service (NEW!)
├── spcs/
│   ├── app/
│   │   ├── main.py               # FastAPI app with internal DNS calls
│   │   └── requirements.txt      # Python dependencies
│   ├── Dockerfile                # Container definition
│   └── deploy.sh                 # Deployment script
├── streamlit/
│   └── streamlit_app.py          # Monitoring dashboard
└── docs/
    └── CUSTOMIZATION.md          # How to customize for your use case
```

## Performance Tuning

### Keep Model Service Warm

```sql
-- Set min_instances to 1 when deploying model service
-- This keeps the model loaded and eliminates cold starts

-- In your deployment procedure:
service = mv.create_service(
    service_name='RISK_MODEL_SVC',
    service_compute_pool='YOUR_COMPUTE_POOL',
    max_instances=2,
    -- min_instances=1  -- Keeps service warm (if supported)
)
```

### Internal DNS Resolution

Services in the same schema can communicate using simple hostnames:

| DNS Format | Example |
|------------|---------|
| Simple name | `risk-model-svc` |
| With schema | `risk-model-svc.ml-models` |
| Full path | `risk-model-svc.ml-models.svc.spcs.internal` |

**Tip**: Simple name (`risk-model-svc`) is fastest and works within the same schema.

### Async Writes

Feature Store and Prediction writes happen after returning the response:

```python
# In FastAPI app
@app.post("/predict")
async def predict(request, background_tasks: BackgroundTasks):
    # 1. Get prediction (fast)
    prediction = call_model_service(features)
    
    # 2. Return immediately to user
    response = {"prediction": prediction}
    
    # 3. Write to Feature Store in background (async)
    background_tasks.add_task(write_to_feature_store, features)
    
    return response
```

## Cost Considerations

SPCS containers charge per-second while running:

| Resource | Approximate Cost |
|----------|------------------|
| XS Compute Pool | ~$0.07-0.10/hour |
| Model Service (XS) | ~$0.07-0.10/hour |
| **Total (both running)** | ~$0.15-0.20/hour |

### Cost Management

```sql
-- Suspend services when not in use
ALTER SERVICE YOUR_DATABASE.ML_MODELS.EVIDENCE_API_SERVICE SUSPEND;
ALTER SERVICE YOUR_DATABASE.ML_MODELS.RISK_MODEL_SVC SUSPEND;

-- Resume when needed
ALTER SERVICE YOUR_DATABASE.ML_MODELS.EVIDENCE_API_SERVICE RESUME;
ALTER SERVICE YOUR_DATABASE.ML_MODELS.RISK_MODEL_SVC RESUME;

-- Check current status
SELECT 
    'API_SERVICE' AS service,
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('YOUR_DATABASE.ML_MODELS.EVIDENCE_API_SERVICE'))[0]['status']::string AS status
UNION ALL
SELECT 
    'MODEL_SERVICE' AS service,
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('YOUR_DATABASE.ML_MODELS.RISK_MODEL_SVC'))[0]['status']::string AS status;
```

## Troubleshooting

### DNS Resolution Issues

If you get "Name or service not known" errors:

```sql
-- Check both services are in the same schema
SHOW SERVICES IN SCHEMA YOUR_DATABASE.ML_MODELS;

-- Test DNS from API container using debug endpoint
SELECT YOUR_DATABASE.ML_MODELS.FN_DNS_DEBUG();
```

### Model Service 500 Errors

Check the model service logs:

```sql
CALL SYSTEM$GET_SERVICE_LOGS('YOUR_DATABASE.ML_MODELS.RISK_MODEL_SVC', 0, 'model-inference', 50);
```

### Verify Model Registry Integration

```sql
-- Check if model is registered
SHOW MODELS IN SCHEMA YOUR_DATABASE.ML_MODELS;

-- Check model versions
SELECT * FROM YOUR_DATABASE.ML_MODELS.YOUR_MODEL;

-- View model functions
CALL YOUR_DATABASE.ML_MODELS.SP_GET_MODEL_INFO();
```

## Support

For questions or issues, contact your Snowflake account team.

---

## Summary: The MLOps Way

| Before | After (This Architecture) |
|--------|---------------------------|
| Stored procedures with model.load() | Model deployed as service |
| SQL UDF calls (slow) | Internal DNS HTTP calls (fast) |
| No model versioning | Full Model Registry lineage |
| No feature tracking | Feature Store with audit trail |
| 10+ second latency | <100ms latency |

**This is enterprise-grade, production-ready MLOps on Snowflake!** 🚀
