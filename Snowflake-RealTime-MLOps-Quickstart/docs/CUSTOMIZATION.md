# Customization Guide

This guide explains how to customize the Real-Time ML Pipeline for your specific use case.

## Table of Contents

1. [XML Schema Changes](#xml-schema-changes)
2. [Feature Engineering](#feature-engineering)
3. [Model Registry Integration](#model-registry-integration)
4. [Internal DNS Configuration](#internal-dns-configuration)
5. [Risk Scoring Logic](#risk-scoring-logic)
6. [Performance Tuning](#performance-tuning)

---

## XML Schema Changes

### Modifying MIB XML Parsing

Edit `spcs/app/main.py` - function `parse_mib_xml()`:

```python
def parse_mib_xml(xml_str: str) -> dict:
    """
    Customize this function for your MIB XML schema.
    """
    features = {
        # Add your custom features here
        'your_custom_feature': 0,
    }
    
    if not xml_str:
        return features
    
    # Add your parsing logic
    # Example: Extract custom elements
    custom_values = re.findall(r'<YourElement>([^<]+)</YourElement>', xml_str)
    features['your_custom_feature'] = len(custom_values)
    
    return features
```

### Modifying RX XML Parsing

Edit `spcs/app/main.py` - function `parse_rx_xml()`:

```python
def parse_rx_xml(xml_str: str) -> dict:
    """
    Customize this function for your RX XML schema.
    """
    features = {
        # Add your custom drug detection patterns
        'rx_drug_your_category': False,
    }
    
    # Add your parsing logic
    drugs = set(re.findall(r'<YourDrugElement>([^<]+)</YourDrugElement>', xml_str))
    
    # Custom drug detection
    drug_str = ' '.join(drugs).upper()
    features['rx_drug_your_category'] = 'YOUR_DRUG' in drug_str
    
    return features
```

---

## Feature Engineering

### Adding New Features to the Feature Store

1. **Update the table schema** (`sql/02_setup_tables.sql`):

```sql
ALTER TABLE YOUR_DATABASE.FEATURE_STORE.ONLINE_FEATURES ADD COLUMN
    YOUR_NEW_FEATURE FLOAT DEFAULT 0;
```

2. **Update the parsing function** to extract the new feature

3. **Update the MERGE statement** in the Streamlit app to save the new feature

### Feature Categories

Organize features into logical groups:

| Category | Examples |
|----------|----------|
| **Core Metrics** | counts, totals, unique values |
| **Boolean Flags** | has_condition, is_high_risk |
| **Ratios** | hit_ratio, fill_frequency |
| **Temporal** | days_since_last, recency_score |
| **Derived Scores** | risk_score, severity_score |

---

## Model Registry Integration

### Option 1: Internal DNS (Recommended - Fastest)

Deploy your model as an inference service and call via internal DNS:

```python
# In spcs/app/main.py

# Configure model service URL (same schema = simple DNS)
MODEL_SERVICE_URL = 'http://your-model-svc:5000/predict'

async def call_model_service(features: dict) -> float:
    """Call Model Registry service via internal DNS."""
    import httpx
    
    # Prepare features in Model Registry format
    inference_input = {
        "data": [[0, {
            "FEATURE_1": features['feature_1'],
            "FEATURE_2": features['feature_2'],
            # ... all features your model expects
        }]]
    }
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            MODEL_SERVICE_URL,
            json=inference_input
        )
        result = response.json()
        
        # Extract prediction: {"data": [[index, {"output_feature_0": prediction}]]}
        prediction = result["data"][0][1].get("output_feature_0", 0)
        return float(prediction)
```

### Deploying Your Model as a Service

```python
# In a stored procedure or notebook

from snowflake.ml.registry import Registry

def deploy_model_service(session):
    # Get your model from registry
    registry = Registry(
        session=session,
        database_name='YOUR_DATABASE',
        schema_name='ML_MODELS'
    )
    
    model = registry.get_model('YOUR_MODEL_NAME')
    mv = model.version('V1')  # or 'default'
    
    # Deploy as always-running service
    service = mv.create_service(
        service_name='YOUR_MODEL_SVC',
        service_compute_pool='YOUR_COMPUTE_POOL',
        image_repo='YOUR_DATABASE.ML_MODELS.MODEL_IMAGES',
        ingress_enabled=True,
        max_instances=2
    )
    
    return service
```

### Option 2: Load Model in Container

For simpler deployments, load the model directly in the container:

```python
# In spcs/app/main.py

from snowflake.ml.registry import Registry

_model = None

def load_model_on_startup():
    global _model
    registry = Registry(session=get_session())
    model = registry.get_model('YOUR_MODEL')
    _model = model.version('V1').load()

def predict(features: dict) -> float:
    """Use loaded model for prediction."""
    import pandas as pd
    df = pd.DataFrame([features])
    prediction = _model.predict(df)
    return float(prediction[0])
```

**Note**: This adds cold-start latency when the container restarts.

---

## Internal DNS Configuration

### DNS Name Formats

Services in the same schema can communicate using these DNS patterns:

| Format | Example | When to Use |
|--------|---------|-------------|
| Simple name | `your-model-svc` | Same schema (fastest) |
| With schema | `your-model-svc.ml-models` | Cross-schema in same DB |
| Full path | `your-model-svc.ml-models.svc.spcs.internal` | Full qualification |

### Testing DNS Resolution

Add a debug endpoint to test DNS from inside your container:

```python
@app.get("/dns_debug")
async def dns_debug():
    import socket
    
    dns_candidates = [
        "your-model-svc",
        "your-model-svc.ml-models",
        "your-model-svc.ml-models.svc.spcs.internal",
    ]
    
    results = {}
    for dns_name in dns_candidates:
        try:
            ip = socket.gethostbyname(dns_name)
            results[dns_name] = f"✅ RESOLVED: {ip}"
        except socket.gaierror as e:
            results[dns_name] = f"❌ {str(e)}"
    
    return results
```

### Troubleshooting DNS

If DNS resolution fails:

1. **Verify both services are in the same schema**:
```sql
SHOW SERVICES IN SCHEMA YOUR_DATABASE.ML_MODELS;
```

2. **Check service status**:
```sql
CALL SYSTEM$GET_SERVICE_STATUS('YOUR_DATABASE.ML_MODELS.YOUR_MODEL_SVC');
```

3. **Try simple DNS name first** (just the service name)

---

## Risk Scoring Logic

### Rule-Based Scoring (Fallback)

Edit `spcs/app/main.py` - function `calculate_rule_based_score()`:

```python
def calculate_rule_based_score(features: dict) -> float:
    """
    Fallback scoring when model service unavailable.
    """
    score = 0.0
    
    # High-impact factors (weight: 0.15-0.25)
    if features.get('your_high_risk_flag', False):
        score += 0.25
    
    # Medium-impact factors (weight: 0.05-0.15)
    score += min(0.15, features.get('some_count', 0) * 0.02)
    
    # Combination rules
    if features.get('flag_a') and features.get('flag_b'):
        score += 0.30  # Dangerous combination
    
    return min(1.0, score)
```

### Threshold Configuration

Define risk levels:

```python
def get_risk_level(score: float) -> str:
    if score >= 0.7:
        return 'CRITICAL'
    elif score >= 0.5:
        return 'HIGH'
    elif score >= 0.3:
        return 'MEDIUM'
    elif score >= 0.1:
        return 'LOW'
    else:
        return 'MINIMAL'
```

---

## Performance Tuning

### Latency Optimization Checklist

| Optimization | Impact | Effort | Notes |
|--------------|--------|--------|-------|
| Use internal DNS | **Very High** | Medium | ~17ms vs 10+ seconds |
| Keep model service warm | High | Low | Set `max_instances >= 1` |
| Pre-compile regex patterns | Medium | Low | Run once at startup |
| Async Feature Store writes | High | Low | Don't block on writes |
| Reduce feature count | Medium | Medium | Only extract what's needed |

### Internal DNS vs SQL Calls

| Method | Latency | Use Case |
|--------|---------|----------|
| **Internal DNS** | ~17ms | Real-time inference (recommended) |
| SQL `MODEL!PREDICT()` | 10-15 seconds | Batch processing |
| Rule-based UDF | ~1-5ms | Fallback / simple scoring |

### Pre-compiled Regex Example

```python
# At module level (runs once at startup)
import re

PATTERNS = {
    'drug_names': re.compile(r'<DrugGenericName>([^<]+)</DrugGenericName>'),
    'bmi_values': re.compile(r'<BMI>(\d+\.?\d*)</BMI>'),
}

def parse_xml(xml_str: str) -> dict:
    # Use pre-compiled patterns - much faster!
    drugs = set(PATTERNS['drug_names'].findall(xml_str))
    bmi = PATTERNS['bmi_values'].findall(xml_str)
```

### Container Resource Tuning

In your service specification:

```yaml
spec:
  containers:
    - name: api
      image: /your_db/spcs/images/your-api:v1
      resources:
        requests:
          memory: 2G    # Increase for complex models
          cpu: 2        # Increase for parallel processing
        limits:
          memory: 4G
          cpu: 4
```

---

## Testing Changes

### Local Testing

```bash
cd spcs
pip install -r app/requirements.txt
uvicorn app.main:app --reload

# Test endpoint
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"data": [[0, "TEST-001", "<mib_xml>", "<rx_xml>"]]}'
```

### Snowflake Testing

```sql
-- Test after deployment
SELECT YOUR_DATABASE.ML_MODELS.FN_API_PREDICT(
    'TEST-001',
    '<your_test_mib_xml>',
    '<your_test_rx_xml>'
)::variant AS result;

-- Check model version used
SELECT 
    result:model_version::string AS model,
    result:inference_ms::float AS latency
FROM (SELECT YOUR_DATABASE.ML_MODELS.FN_API_PREDICT('TEST', '<r/>', '<r/>') AS result);
```

---

## Common Customizations

### 1. Different XML Schema

- Update regex patterns in parsing functions
- Test with sample XML files
- Validate feature extraction

### 2. Your Own ML Model

1. Train and register in Model Registry
2. Deploy as service with `mv.create_service()`
3. Update `MODEL_SERVICE_URL` in container
4. Match feature names to model's expected input

### 3. Different Output Format

- Modify the response structure in `predict()` function
- Update Streamlit display accordingly

### 4. Multiple Model Versions

```python
# A/B testing example
import random

MODEL_A_URL = 'http://model-v1-svc:5000/predict'
MODEL_B_URL = 'http://model-v2-svc:5000/predict'

def get_model_url():
    # 80% V1, 20% V2
    if random.random() < 0.8:
        return MODEL_A_URL, "V1"
    else:
        return MODEL_B_URL, "V2"
```

---

## MLOps Best Practices

### 1. Always Track Model Version

```python
response = {
    "prediction": score,
    "model_version": "REGISTRY_V2",  # Always include this!
    "model_name": "EVIDENCE_RISK_MODEL"
}
```

### 2. Store Features for Reproducibility

```sql
-- Every prediction should have corresponding features
INSERT INTO FEATURE_STORE.ONLINE_FEATURES (...)
VALUES (...);
```

### 3. Log All Predictions

```sql
-- Full lineage for compliance
INSERT INTO ML_MODELS.MODEL_PREDICTIONS 
(POLICY_NUMBER, PREDICTION, MODEL_NAME, MODEL_VERSION, SCORE_DATE)
VALUES ('...', 0.45, 'EVIDENCE_RISK_MODEL', 'V2', CURRENT_TIMESTAMP());
```

### 4. Handle Model Service Failures

```python
try:
    score = await call_model_service(features)
    model_version = "REGISTRY_V2"
except Exception as e:
    # Fallback to rule-based
    score = calculate_rule_based_score(features)
    model_version = "RULE_BASED_FALLBACK"
    log_error(e)
```

---

## Support

For additional customization help, contact your Snowflake account team.
