---
name: "realtime-mlops-quickstart-implementation"
created: "2026-02-19T18:18:44.400Z"
status: pending
---

# Real-Time MLOps Quickstart Implementation Plan

## Overview

This plan guides the deployment of a **sub-100ms Real-Time ML Inference Pipeline** using Snowflake's native MLOps capabilities:

- **Snowpark Container Services (SPCS)** - Always-running FastAPI container
- **Model Registry** - Native Snowflake ML for model versioning and deployment
- **Internal DNS** - Service-to-service communication (\~17ms latency)
- **Online Feature Store** - Hybrid Tables for real-time feature serving
- **Streamlit Dashboard** - Real-time monitoring UI

```
flowchart TB
    subgraph Request [Request Flow]
        A[SQL Function Call] --> B[SPCS API Service]
    end
    
    subgraph SPCS [SPCS API Container]
        B --> C[Parse XML]
        C --> D[Extract 105 Features]
        D --> E{Call Model}
    end
    
    subgraph ModelService [Model Registry Service]
        E -->|Internal DNS| F[Model Inference]
        F -->|~17ms| G[Return Prediction]
    end
    
    subgraph MLOps [MLOps Storage - Async]
        G --> H[Feature Store]
        G --> I[Predictions Table]
    end
    
    G --> J[Return Response]
```

---

## Skill Mapping Reference

The following Cortex Code skills are mapped to tasks in this quickstart:

| Skill                       | Use Case                                              | Tasks            |
| --------------------------- | ----------------------------------------------------- | ---------------- |
| `machine-learning`          | Model training, registry, deployment, log\_model API  | 4, 5             |
| `deploy-to-spcs`            | Docker builds, SPCS services, image registry          | 3, 6, 7          |
| `developing-with-streamlit` | Streamlit app development and deployment              | Optional Phase 7 |
| `dcm`                       | Infrastructure-as-code for databases, schemas, tables | 2                |
| `verification-skill`        | SQL validation and testing                            | 8                |
| `cost-management`           | Monitor SPCS and compute pool costs                   | Troubleshooting  |

---

## Prerequisites Verification

Before starting, verify these prerequisites:

| Requirement       | How to Check               |
| ----------------- | -------------------------- |
| Docker Desktop    | `docker --version`         |
| Snowflake CLI     | `snow --version`           |
| SPCS Enabled      | Check with Snowflake admin |
| ACCOUNTADMIN Role | `SELECT CURRENT_ROLE();`   |

---

## Phase 1: Environment Configuration

### Task 1.1: Replace Placeholder Values

**Recommended Skill:** None (manual text replacement)

Search and replace these placeholders across all files:

| Placeholder         | Replace With                      | Files to Update                |
| ------------------- | --------------------------------- | ------------------------------ |
| `YOUR_DATABASE`     | `REALTIME_ML_PIPELINE`            | All SQL files, main.py         |
| `YOUR_WAREHOUSE`    | `ML_INFERENCE_WH`                 | SQL files                      |
| `YOUR_COMPUTE_POOL` | `ML_INFERENCE_POOL`               | 04, 06 SQL files               |
| `YOUR_ACCOUNT`      | Your Snowflake account identifier | SPCS deployment                |
| `YOUR_MODEL_NAME`   | `EVIDENCE_RISK_MODEL`             | 06\_deploy\_model\_service.sql |
| `YOUR_MODEL_SVC`    | `RISK_MODEL_SVC`                  | 04, 06 SQL files               |

**Files requiring updates:**

- sql/01\_setup\_database.sql
- sql/02\_setup\_tables.sql
- sql/03\_setup\_compute\_pool.sql
- sql/04\_deploy\_spcs\_service.sql
- sql/05\_deploy\_streamlit.sql
- sql/06\_deploy\_model\_service.sql
- spcs/app/main.py

---

## Phase 2: Database Infrastructure Setup

### Task 2.1: Create Database and Schemas

**Recommended Skill:** `dcm` (Database Change Management)

- Use for infrastructure-as-code approach to database, schema, and warehouse creation
- Provides idempotent deployments and change tracking

Execute sql/01\_setup\_database.sql:

```
snow sql -f sql/01_setup_database.sql --connection default
```

This creates:

- Database: `REALTIME_ML_PIPELINE`
- Schemas: `SPCS`, `FEATURE_STORE`, `ML_MODELS`, `STREAMLIT_APP`
- Warehouse: `ML_INFERENCE_WH` (X-SMALL, auto-suspend 60s)

**Verification:**

```
SHOW SCHEMAS IN DATABASE REALTIME_ML_PIPELINE;
-- Expected: SPCS, FEATURE_STORE, ML_MODELS, STREAMLIT_APP
```

### Task 2.2: Create Feature Store and Prediction Tables

**Recommended Skill:** `dcm` (Database Change Management)

- Manages table definitions with version control
- Handles Hybrid Table creation for Feature Store

Execute sql/02\_setup\_tables.sql:

```
snow sql -f sql/02_setup_tables.sql --connection default
```

Creates:

- **FEATURE\_STORE.ONLINE\_FEATURES** - Hybrid Table for low-latency reads
- **ML\_MODELS.MODEL\_PREDICTIONS** - Prediction lineage tracking
- **FEATURE\_STORE.RAW\_EVIDENCE** - Raw XML storage (optional)

**Verification:**

```
SHOW TABLES IN SCHEMA REALTIME_ML_PIPELINE.FEATURE_STORE;
SHOW TABLES IN SCHEMA REALTIME_ML_PIPELINE.ML_MODELS;
```

---

## Phase 3: SPCS Infrastructure

### Task 3.1: Create Compute Pool and Image Repository

**Recommended Skill:** `deploy-to-spcs`

- Specialized knowledge for SPCS compute pool configuration
- Handles image repository creation and permissions
- Knows SPCS-specific instance families and auto-scaling

Execute sql/03\_setup\_compute\_pool.sql:

```
snow sql -f sql/03_setup_compute_pool.sql --connection default
```

Creates:

- Compute Pool: `ML_INFERENCE_POOL` (CPU\_X64\_XS, 1-2 nodes)
- Image Repository: `SPCS.IMAGES`
- Stage: `SPCS.SPECS`

**Verification:**

```
SHOW COMPUTE POOLS;
-- Should show ML_INFERENCE_POOL with state ACTIVE or IDLE

SHOW IMAGE REPOSITORIES IN SCHEMA REALTIME_ML_PIPELINE.SPCS;
```

---

## Phase 4: Model Registry Setup

### Task 4.1: Train and Register Model

**Recommended Skill:** `machine-learning` **\[REQUIRED]**

- Essential for Model Registry API usage (log\_model, get\_model)
- Knows target\_platform options (WAREHOUSE vs SNOWPARK\_CONTAINER\_SERVICES)
- Handles conda\_dependencies and sample\_input\_data correctly
- Understands model versioning best practices

Create a notebook or stored procedure to train and register the model:

```
from snowflake.ml.registry import Registry
from sklearn.ensemble import GradientBoostingClassifier
import pandas as pd

# Create training data (customize for your use case)
X_train = pd.DataFrame({
    'MIB_TOTAL_RECORDS': [0, 2, 5, 1, 8],
    'MIB_HIT_COUNT': [0, 1, 1, 0, 2],
    'MIB_HAS_HIT': [0, 1, 1, 0, 1],
    'MIB_AVG_BMI': [24.5, 28.0, 32.5, 22.0, 35.2],
    'RX_TOTAL_FILLS': [2, 8, 15, 0, 22],
    'RX_UNIQUE_DRUGS': [1, 4, 8, 0, 12],
    'RX_DRUG_OPIOID': [0, 0, 1, 0, 1],
    'HAS_MIB_EVIDENCE': [0, 1, 1, 1, 1],
    'HAS_RX_EVIDENCE': [1, 1, 1, 0, 1],
    'COMBINED_RISK_SCORE': [0.1, 0.3, 0.6, 0.05, 0.8]
})
y_train = [0, 0, 1, 0, 1]  # 0=low risk, 1=high risk

# Train model
model = GradientBoostingClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Register to Model Registry
registry = Registry(
    session=session,
    database_name='REALTIME_ML_PIPELINE',
    schema_name='ML_MODELS'
)

mv = registry.log_model(
    model=model,
    model_name='EVIDENCE_RISK_MODEL',
    version_name='V2',
    sample_input_data=X_train.iloc[:1]
)

print(f"Model registered: {mv.model_name} version {mv.version_name}")
```

**Verification:**

```
SHOW MODELS IN SCHEMA REALTIME_ML_PIPELINE.ML_MODELS;
-- Should show EVIDENCE_RISK_MODEL with versions ["V2"]
```

### Task 4.2: Deploy Model as Inference Service

**Recommended Skills:** `machine-learning` + `deploy-to-spcs`

- `machine-learning`: mv.create\_service() API, model deployment patterns
- `deploy-to-spcs`: Service configuration, internal DNS setup

Execute sql/06\_deploy\_model\_service.sql:

```
snow sql -f sql/06_deploy_model_service.sql --connection default
```

**Critical: Get the internal DNS URL:**

```
DESC SERVICE REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC;
-- Note the service name for internal DNS
```

**Wait for service to be READY:**

```
SELECT 
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC'))[0]['status']::string AS status;
-- Wait until status = 'READY' (may take 1-2 minutes)
```

---

## Phase 5: SPCS API Container Deployment

### Task 5.1: Update MODEL\_SERVICE\_URL

**Recommended Skill:** `deploy-to-spcs`

- Knows internal DNS naming conventions
- Understands service-to-service communication patterns

Before building the container, update sql/04\_deploy\_spcs\_service.sql with your model service URL:

```
# Find this section in the spec:
env:
  SNOWFLAKE_DATABASE: REALTIME_ML_PIPELINE
  SNOWFLAKE_SCHEMA: ML_MODELS
  USE_MODEL_REGISTRY: 'true'
  MODEL_SERVICE_URL: 'http://risk-model-svc:5000/predict'  # <-- UPDATE THIS
```

**URL Format:** `http://<service-name>:5000/predict`

- Use `http://` (not `https://`) for internal DNS
- Port 5000 is the default for model services
- When in the same schema, use just the service name

### Task 5.2: Build Docker Image

**Recommended Skill:** `deploy-to-spcs`

- Handles platform-specific builds (linux/amd64)
- Knows Dockerfile best practices for SPCS

```
cd Snowflake-RealTime-MLOps-Quickstart/spcs

# Build for AMD64 (required for Snowflake)
docker build --platform linux/amd64 -t evidence-api:v1 .
```

### Task 5.3: Push to Snowflake Registry

**Recommended Skill:** `deploy-to-spcs`

- Handles image registry authentication
- Knows correct image tagging format

```
# Login to Snowflake image registry
snow spcs image-registry login --connection default

# Get your account and repository URL
# Format: <account>.registry.snowflakecomputing.com/<database>/<schema>/images/<image>:<tag>

# Tag image (replace YOUR_ACCOUNT with actual account)
docker tag evidence-api:v1 YOUR_ACCOUNT.registry.snowflakecomputing.com/realtime_ml_pipeline/spcs/images/evidence-api:v1

# Push image
docker push YOUR_ACCOUNT.registry.snowflakecomputing.com/realtime_ml_pipeline/spcs/images/evidence-api:v1
```

### Task 5.4: Deploy SPCS Service

**Recommended Skill:** `deploy-to-spcs`

- Service specification expertise
- Resource limits and scaling configuration

```
cd ..
snow sql -f sql/04_deploy_spcs_service.sql --connection default
```

**Wait for service to be READY:**

```
CALL SYSTEM$GET_SERVICE_STATUS('REALTIME_ML_PIPELINE.ML_MODELS.INFERENCE_SERVICE');
-- Wait until status = 'READY'
```

---

## Phase 6: Testing and Verification

### Task 6.1: Test Health Endpoint

**Recommended Skill:** `verification-skill`

- SQL validation and testing workflows
- Read-only verification patterns

```
SELECT REALTIME_ML_PIPELINE.ML_MODELS.FN_HEALTH() AS health_check;
-- Expected: {"status": "healthy", ...}
```

### Task 6.2: Test Prediction with Model Registry

```
SELECT REALTIME_ML_PIPELINE.ML_MODELS.FN_API_PREDICT(
    'TEST-001',
    '<?xml version="1.0"?><Response><ResponseData>CODE1</ResponseData></Response>',
    '<?xml version="1.0"?><IntelRXResponse><DrugFill><DrugGenericName>METFORMIN</DrugGenericName></DrugFill></IntelRXResponse>'
)::variant AS result;
```

### Task 6.3: Verify Model Registry Integration

```
SELECT 
    result:model_version::string AS model_version,
    result:risk_score::float AS risk_score,
    result:inference_ms::float AS latency_ms
FROM (
    SELECT REALTIME_ML_PIPELINE.ML_MODELS.FN_API_PREDICT('TEST-002', '<r/>', '<r/>') AS result
);

-- Expected output:
-- MODEL_VERSION    | RISK_SCORE | LATENCY_MS
-- REGISTRY_V2      | 0.xx       | ~17-50
```

**Success Criteria:**

- `model_version` = `REGISTRY_V2` (not `RULE_BASED`)
- `latency_ms` < 100ms
- No errors in response

---

## Phase 7: Deploy Streamlit Dashboard (Optional)

### Task 7.1: Upload and Deploy Streamlit

**Recommended Skill:** `developing-with-streamlit` **\[REQUIRED for Streamlit tasks]**

- Streamlit-in-Snowflake deployment patterns
- Session management and Snowpark integration
- UI component best practices

```
# Upload Streamlit app to stage
snow stage copy streamlit/streamlit_app.py @REALTIME_ML_PIPELINE.STREAMLIT_APP.STREAMLIT_STAGE/ --connection default

# Create Streamlit app
snow sql -f sql/05_deploy_streamlit.sql --connection default
```

**Verification:**

- Access Streamlit in Snowsight
- Run test predictions from UI
- Verify "REGISTRY\_V2" appears in results

---

## Troubleshooting Guide

**Recommended Skill:** `cost-management` (for cost-related issues)

### DNS Resolution Issues ("Name or service not known")

```
-- 1. Verify both services are in the same schema
SHOW SERVICES IN SCHEMA REALTIME_ML_PIPELINE.ML_MODELS;
-- Both INFERENCE_SERVICE and RISK_MODEL_SVC should be listed

-- 2. Check both services are READY
SELECT 
    'API_SERVICE' AS service,
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('REALTIME_ML_PIPELINE.ML_MODELS.INFERENCE_SERVICE'))[0]['status']::string AS status
UNION ALL
SELECT 
    'MODEL_SERVICE' AS service,
    PARSE_JSON(SYSTEM$GET_SERVICE_STATUS('REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC'))[0]['status']::string AS status;
```

### Model Service 500 Errors

```
-- Check model service logs
CALL SYSTEM$GET_SERVICE_LOGS('REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC', 0, 'model-inference', 50);
```

### API Service Errors

```
-- Check API service logs
CALL SYSTEM$GET_SERVICE_LOGS('REALTIME_ML_PIPELINE.ML_MODELS.INFERENCE_SERVICE', 0, 'api', 50);
```

---

## Cost Management

**Recommended Skill:** `cost-management`

- Monitor SPCS compute costs
- Track credit consumption
- Optimize resource allocation

### Suspend Services When Not in Use

```
-- Suspend both services (stops all charges)
ALTER SERVICE REALTIME_ML_PIPELINE.ML_MODELS.INFERENCE_SERVICE SUSPEND;
ALTER SERVICE REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC SUSPEND;

-- Also suspend compute pool
ALTER COMPUTE POOL ML_INFERENCE_POOL SUSPEND;
```

### Resume Services

```
-- Resume compute pool first
ALTER COMPUTE POOL ML_INFERENCE_POOL RESUME;

-- Then resume services
ALTER SERVICE REALTIME_ML_PIPELINE.ML_MODELS.RISK_MODEL_SVC RESUME;
ALTER SERVICE REALTIME_ML_PIPELINE.ML_MODELS.INFERENCE_SERVICE RESUME;
```

---

## Success Checklist

- [ ] Database and schemas created
- [ ] Feature Store Hybrid Table exists
- [ ] Predictions table exists
- [ ] Compute pool active
- [ ] Model registered in Model Registry
- [ ] Model deployed as inference service (READY)
- [ ] Docker image pushed to Snowflake registry
- [ ] SPCS API service deployed (READY)
- [ ] Health endpoint returns healthy
- [ ] Prediction returns `model_version = REGISTRY_V2`
- [ ] Inference latency < 100ms
- [ ] (Optional) Streamlit dashboard accessible

---

## Architecture Reference

```
REALTIME_ML_PIPELINE/
├── SPCS/
│   ├── IMAGES (Image Repository)
│   └── SPECS (Stage)
├── FEATURE_STORE/
│   ├── ONLINE_FEATURES (Hybrid Table)
│   └── RAW_EVIDENCE (Hybrid Table)
├── ML_MODELS/
│   ├── MODEL_PREDICTIONS (Table)
│   ├── EVIDENCE_RISK_MODEL (Model)
│   ├── RISK_MODEL_SVC (Service)
│   ├── INFERENCE_SERVICE (Service)
│   ├── FN_API_PREDICT (Function)
│   └── FN_HEALTH (Function)
└── STREAMLIT_APP/
    ├── STREAMLIT_STAGE (Stage)
    └── ML_PIPELINE_MONITOR (Streamlit)
```

---

## Context Window Management Note

This implementation plan is designed for incremental execution across multiple context windows. After completing each major phase:

1. Update task status in this plan
2. Save progress notes to memory
3. If context window usage is high, suggest creating a new window to continue

**Recommended breakpoints:**

- After Phase 2 (Database setup)
- After Phase 4 (Model Registry setup)
- After Phase 6 (Testing complete)

---

## Quick Skill Invocation Reference

When starting each task, invoke the appropriate skill:

| Task                     | Skill Command                                          |
| ------------------------ | ------------------------------------------------------ |
| Task 2 (Database/Tables) | `/skill dcm`                                           |
| Task 3 (Compute Pool)    | `/skill deploy-to-spcs`                                |
| Task 4 (Model Training)  | `/skill machine-learning`                              |
| Task 5 (Model Service)   | `/skill machine-learning` then `/skill deploy-to-spcs` |
| Task 6-7 (Docker/SPCS)   | `/skill deploy-to-spcs`                                |
| Task 8 (Testing)         | `/skill verification-skill`                            |
| Phase 7 (Streamlit)      | `/skill developing-with-streamlit`                     |
| Cost Issues              | `/skill cost-management`                               |
