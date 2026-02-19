# Setup Checklist

## Real-Time ML Inference Pipeline with SPCS & Model Registry

Use this checklist to deploy the pipeline in your environment. Check off each step as you complete it.

---

## Prerequisites

### Local Machine
- [ ] **Docker Desktop** installed and running
- [ ] **Snowflake CLI** (`snow`) installed ([Install Guide](https://docs.snowflake.com/en/developer-guide/snowflake-cli))
- [ ] **Git** (to clone this repo, if needed)

### Snowflake Account
- [ ] SPCS (Snowpark Container Services) enabled
- [ ] ACCOUNTADMIN role access (for initial setup)
- [ ] Compute pool quota available

### Verify CLI Connection
```bash
# Test your Snowflake connection
snow connection test --connection default

# Expected: Connection successful
```

---

## Step 1: Configure Your Environment

### 1.1 Update Placeholder Values

Search and replace these placeholders in all SQL files:

| Placeholder | Replace With | Example |
|-------------|--------------|---------|
| `YOUR_DATABASE` | Your database name | `ML_INFERENCE_DB` |
| `YOUR_ACCOUNT` | Your Snowflake account | `abc12345.us-east-1` |
| `YOUR_WAREHOUSE` | Your warehouse name | `COMPUTE_WH` |
| `YOUR_COMPUTE_POOL` | Your compute pool name | `ML_INFERENCE_POOL` |
| `YOUR_MODEL_NAME` | Your model name | `RISK_SCORING_MODEL` |
| `YOUR_MODEL_SVC` | Your model service name | `risk-scoring-svc` |

### Verification
- [ ] All `YOUR_*` placeholders replaced in `sql/*.sql`
- [ ] All `YOUR_*` placeholders replaced in `spcs/app/main.py`
- [ ] All `your-*` placeholders replaced in environment variables

---

## Step 2: Create Database Structure

### 2.1 Run Setup Scripts

```bash
# Create database, schemas, and warehouse
snow sql -f sql/01_setup_database.sql --connection default

# Create Feature Store and Predictions tables
snow sql -f sql/02_setup_tables.sql --connection default

# Create compute pool for SPCS
snow sql -f sql/03_setup_compute_pool.sql --connection default
```

### Verification
- [ ] Database created: `SHOW DATABASES LIKE 'YOUR_DATABASE';`
- [ ] Schemas exist: `SHOW SCHEMAS IN DATABASE YOUR_DATABASE;`
- [ ] Tables created: `SHOW TABLES IN SCHEMA YOUR_DATABASE.ML_MODELS;`
- [ ] Compute pool created: `SHOW COMPUTE POOLS;`

```sql
-- Verify compute pool is ACTIVE or IDLE
SELECT name, state FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE name = 'YOUR_COMPUTE_POOL';
```

---

## Step 3: Train and Register Your Model

### 3.1 Register Model to Model Registry

Use your existing model training notebook/script, or create one:

```python
from snowflake.ml.registry import Registry
from sklearn.ensemble import GradientBoostingClassifier

# Train your model
model = GradientBoostingClassifier()
model.fit(X_train, y_train)

# Register to Model Registry
registry = Registry(session=session, database_name='YOUR_DATABASE', schema_name='ML_MODELS')
mv = registry.log_model(
    model=model,
    model_name='YOUR_MODEL_NAME',
    version_name='V1',
    sample_input_data=X_train.iloc[:1]
)
```

### Verification
- [ ] Model registered: `SHOW MODELS IN SCHEMA YOUR_DATABASE.ML_MODELS;`
- [ ] Model version exists: Check "versions" column shows `["V1"]`

---

## Step 4: Deploy Model as Inference Service

### 4.1 Deploy Model Service

```bash
# Deploy model from registry as always-running service
snow sql -f sql/06_deploy_model_service.sql --connection default
```

### 4.2 Wait for Service to Start

```sql
-- Check status (wait until "READY")
SELECT 
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('YOUR_DATABASE.ML_MODELS.YOUR_MODEL_SVC'))[0]['status']::string AS status;
```

### Verification
- [ ] Model service status: `READY`
- [ ] Service has endpoint: `SHOW ENDPOINTS IN SERVICE YOUR_DATABASE.ML_MODELS.YOUR_MODEL_SVC;`

---

## Step 4.5: Get Model Service Internal DNS URL ⚠️ CRITICAL

> **This step is required for internal DNS to work!** You must get the model service URL and update your SPCS configuration before deploying.

### 4.5.1 Get the Internal DNS Name

Run this query to get the model service's internal DNS name:

```sql
-- Option 1: Use DESC SERVICE to get the DNS name
DESC SERVICE YOUR_DATABASE.ML_MODELS.YOUR_MODEL_SVC;

-- Look for the "dns_name" field in the output
-- Example output: your-model-svc.ml-models.your-database.snowflakecomputing.internal
```

Or use SHOW ENDPOINTS:

```sql
-- Option 2: Show endpoints
SHOW ENDPOINTS IN SERVICE YOUR_DATABASE.ML_MODELS.YOUR_MODEL_SVC;

-- Look for the "ingress_url" column for internal access
```

### 4.5.2 Construct the Model Service URL

The internal DNS URL format is:
```
http://<service-name>:<port>/predict
```

**Important Notes:**
- Use `http://` (not `https://`) for internal DNS
- The port is typically `5000` for model inference services
- When services are in the **same schema**, use just the service name (e.g., `your-model-svc`)
- When services are in **different schemas**, use the full DNS name

**Examples:**

| Scenario | MODEL_SERVICE_URL |
|----------|-------------------|
| Same schema (recommended) | `http://your-model-svc:5000/predict` |
| Different schema | `http://your-model-svc.ml-models.your-database.snowflakecomputing.internal:5000/predict` |

### 4.5.3 Update the SPCS Service Configuration

**Option A: Update in SQL (Recommended)**

Edit `sql/04_deploy_spcs_service.sql` and update the `MODEL_SERVICE_URL` environment variable:

```sql
-- Find this section in the spec:
      env:
        SNOWFLAKE_DATABASE: YOUR_DATABASE
        SNOWFLAKE_SCHEMA: ML_MODELS
        USE_MODEL_REGISTRY: 'true'
        # ⚠️ UPDATE THIS LINE with your model service name:
        MODEL_SERVICE_URL: 'http://your-model-svc:5000/predict'
```

**Option B: Update in Python (Alternative)**

If you prefer, edit `spcs/app/main.py` directly (line ~33):

```python
# Change this line:
MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://your-model-svc:5000/predict")

# To use your actual service name:
MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://risk-scoring-svc:5000/predict")
```

### 4.5.4 Verify Your Configuration

Before proceeding, confirm:

```bash
# Check that MODEL_SERVICE_URL is set correctly in sql/04_deploy_spcs_service.sql
grep "MODEL_SERVICE_URL" sql/04_deploy_spcs_service.sql
```

### Verification
- [ ] Got internal DNS name from `DESC SERVICE` or `SHOW ENDPOINTS`
- [ ] Constructed URL format: `http://<service-name>:5000/predict`
- [ ] Updated `MODEL_SERVICE_URL` in `sql/04_deploy_spcs_service.sql`
- [ ] `USE_MODEL_REGISTRY` is set to `'true'`

---

## Step 5: Build and Deploy SPCS Container

### 5.1 Build Docker Image

```bash
cd spcs

# Build for AMD64 (required for Snowflake)
docker build --platform linux/amd64 -t evidence-api:v1 .
```

### 5.2 Push to Snowflake Registry

```bash
# Login to Snowflake image registry
snow spcs image-registry login --connection default

# Tag image
docker tag evidence-api:v1 YOUR_ACCOUNT.registry.snowflakecomputing.com/your_database/ml_models/images/evidence-api:v1

# Push image
docker push YOUR_ACCOUNT.registry.snowflakecomputing.com/your_database/ml_models/images/evidence-api:v1
```

### 5.3 Deploy SPCS Service

```bash
# Deploy the service
snow sql -f ../sql/04_deploy_spcs_service.sql --connection default
```

### Verification
- [ ] Image pushed successfully (no errors)
- [ ] SPCS service status: `READY`

```sql
SELECT 
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('YOUR_DATABASE.ML_MODELS.INFERENCE_SERVICE'))[0]['status']::string AS status;
```

---

## Step 6: Test End-to-End Pipeline

### 6.1 Test API Function

```sql
-- Test prediction
SELECT YOUR_DATABASE.ML_MODELS.FN_API_PREDICT(
    'TEST-001',
    '<?xml version="1.0"?><Response><ResponseData>CODE1</ResponseData></Response>',
    '<?xml version="1.0"?><IntelRXResponse><DrugFill><DrugGenericName>METFORMIN</DrugGenericName></DrugFill></IntelRXResponse>'
)::variant AS result;
```

### 6.2 Verify Model Registry Is Being Used

```sql
-- Check model_version = "REGISTRY_V2" (not "RULE_BASED")
SELECT 
    result:model_version::string AS model_version,
    result:risk_score::float AS risk_score,
    result:inference_ms::float AS latency_ms
FROM (
    SELECT YOUR_DATABASE.ML_MODELS.FN_API_PREDICT('TEST-002', '<r/>', '<r/>') AS result
);
```

### Expected Output
| model_version | risk_score | latency_ms |
|---------------|------------|------------|
| REGISTRY_V2   | 0.xx       | ~20-50     |

### Verification
- [ ] `model_version` shows `REGISTRY_V2`
- [ ] `latency_ms` is under 100ms
- [ ] No errors in response

---

## Step 7: Verify MLOps Integration

### 7.1 Check Feature Store

```sql
SELECT * 
FROM YOUR_DATABASE.ML_MODELS.HT_ONLINE_FEATURES 
WHERE POLICY_NUMBER = 'TEST-001';
```

### 7.2 Check Predictions Table

```sql
SELECT * 
FROM YOUR_DATABASE.ML_MODELS.MODEL_PREDICTIONS 
WHERE POLICY_NUMBER = 'TEST-001';
```

### Verification
- [ ] Feature Store has record for TEST-001
- [ ] Predictions table has record with MODEL_VERSION = 'V2'

---

## Step 8: Deploy Streamlit Dashboard (Optional)

### 8.1 Deploy Dashboard

```bash
# Upload Streamlit app
snow stage copy streamlit/streamlit_app.py @YOUR_DATABASE.STREAMLIT.STAGE/ --connection default

# Create Streamlit app
snow sql -f sql/05_deploy_streamlit.sql --connection default
```

### Verification
- [ ] Streamlit app accessible in Snowsight
- [ ] Can run predictions from UI
- [ ] Shows "REGISTRY_V2" in results

---

## Troubleshooting

### DNS Resolution Issues

If you see "Name or service not known":

```sql
-- 1. Verify both services are in the same schema
SHOW SERVICES IN SCHEMA YOUR_DATABASE.ML_MODELS;
-- Both INFERENCE_SERVICE and YOUR_MODEL_SVC should be listed

-- 2. Verify the model service DNS name
DESC SERVICE YOUR_DATABASE.ML_MODELS.YOUR_MODEL_SVC;
-- Check the "dns_name" field

-- 3. Test from the API service logs
CALL SYSTEM$GET_SERVICE_LOGS('YOUR_DATABASE.ML_MODELS.INFERENCE_SERVICE', 0, 'api', 50);
-- Look for connection errors
```

**Common DNS Fixes:**

| Error | Solution |
|-------|----------|
| `Name or service not known` | Verify MODEL_SERVICE_URL uses correct service name |
| `Connection refused` | Model service may be suspended - resume it |
| `404 Not Found` | Check endpoint path is `/predict` |
| `500 Internal Server Error` | Check model service logs for errors |

**Verifying Internal DNS:**

```sql
-- Both services must show "READY" status
SELECT 
    'API_SERVICE' AS service,
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('YOUR_DATABASE.ML_MODELS.INFERENCE_SERVICE'))[0]['status']::string AS status
UNION ALL
SELECT 
    'MODEL_SERVICE' AS service,
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('YOUR_DATABASE.ML_MODELS.YOUR_MODEL_SVC'))[0]['status']::string AS status;
```

### Model Service 500 Errors

```sql
-- Check model service logs
CALL SYSTEM$GET_SERVICE_LOGS('YOUR_DATABASE.ML_MODELS.YOUR_MODEL_SVC', 0, 'model-inference', 50);
```

### API Service Errors

```sql
-- Check API service logs
CALL SYSTEM$GET_SERVICE_LOGS('YOUR_DATABASE.ML_MODELS.INFERENCE_SERVICE', 0, 'api', 50);
```

### Service Not Starting

```sql
-- Check compute pool status
SHOW COMPUTE POOLS;

-- Ensure it's ACTIVE or IDLE, not SUSPENDED
ALTER COMPUTE POOL YOUR_COMPUTE_POOL RESUME;
```

---

## Cost Management

### Suspend Services When Not in Use

```sql
-- Suspend both services (stops all charges)
ALTER SERVICE YOUR_DATABASE.ML_MODELS.INFERENCE_SERVICE SUSPEND;
ALTER SERVICE YOUR_DATABASE.ML_MODELS.YOUR_MODEL_SVC SUSPEND;

-- Also suspend compute pool
ALTER COMPUTE POOL YOUR_COMPUTE_POOL SUSPEND;
```

### Resume Services

```sql
-- Resume compute pool first
ALTER COMPUTE POOL YOUR_COMPUTE_POOL RESUME;

-- Then resume services
ALTER SERVICE YOUR_DATABASE.ML_MODELS.YOUR_MODEL_SVC RESUME;
ALTER SERVICE YOUR_DATABASE.ML_MODELS.INFERENCE_SERVICE RESUME;
```

---

## Final Checklist

### Core Functionality
- [ ] Database and schemas created
- [ ] Feature Store table exists
- [ ] Predictions table exists
- [ ] Model registered in Model Registry
- [ ] Model deployed as inference service
- [ ] SPCS API container deployed
- [ ] End-to-end test successful
- [ ] Model version shows "REGISTRY_V2"

### MLOps Integration
- [ ] Features saved to Feature Store
- [ ] Predictions logged with model version
- [ ] Latency under 100ms

### Documentation Reviewed
- [ ] README.md read and understood
- [ ] CUSTOMIZATION.md reviewed for your use case

---

## Success! 🎉

If all checks pass, your Real-Time ML Inference Pipeline is ready for production!

**Next Steps:**
1. Replace sample XML parsing with your actual schema
2. Train your production model and register it
3. Set up monitoring and alerting
4. Configure auto-scaling based on load

For customization help, see `docs/CUSTOMIZATION.md`.

