"""
Real-Time ML Inference API
==========================
FastAPI application for SPCS deployment.
Extracts 105 features from XML and performs risk scoring.

Customize:
- parse_mib_xml(): Modify for your MIB XML schema
- parse_rx_xml(): Modify for your RX XML schema  
- calculate_risk_score(): Implement your scoring logic
"""

import os
import re
import time
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

# ============================================================================
# CONFIGURATION
# ============================================================================

SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "REALTIME_ML_PIPELINE")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "FEATURE_STORE")

# Model Registry Service URL (internal DNS - same schema = simple name)
# Deploy model using mv.create_service() then set this URL
USE_MODEL_REGISTRY = os.getenv("USE_MODEL_REGISTRY", "false").lower() == "true"
MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://your-model-svc:5000/predict")

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class PredictRequest(BaseModel):
    policy_number: str
    mib_xml: Optional[str] = None
    rx_xml: Optional[str] = None

class PredictResponse(BaseModel):
    policy_number: str
    risk_score: float
    risk_level: str
    inference_ms: float
    feature_count: int = 105

# ============================================================================
# XML PARSING - CUSTOMIZE FOR YOUR SCHEMA
# ============================================================================

def parse_mib_xml(xml_str: str) -> dict:
    """
    Parse MIB XML and extract features.
    
    CUSTOMIZE THIS FUNCTION for your XML schema.
    Returns dict with 40 MIB features.
    """
    features = {
        # Core MIB metrics
        'mib_hit_count': 0,
        'mib_try_count': 0,
        'mib_code_count': 0,
        'mib_total_records': 0,
        'mib_has_hit': False,
        
        # BMI features
        'mib_avg_bmi': 0.0,
        'mib_max_bmi': 0.0,
        'mib_min_bmi': 0.0,
        'mib_bmi_over_30': False,
        'mib_bmi_over_35': False,
        
        # Build data
        'mib_avg_height': 0.0,
        'mib_avg_weight': 0.0,
        'mib_max_weight': 0.0,
        'mib_weight_over_200': False,
        
        # Condition codes
        'mib_has_cardiac_code': False,
        'mib_has_diabetes_code': False,
        'mib_has_cancer_code': False,
        'mib_has_respiratory_code': False,
        'mib_has_mental_health_code': False,
        'mib_has_substance_abuse_code': False,
        'mib_has_liver_code': False,
        'mib_has_kidney_code': False,
        'mib_has_neurological_code': False,
        'mib_has_autoimmune_code': False,
        'mib_has_blood_disorder_code': False,
        'mib_has_gastrointestinal_code': False,
        'mib_has_musculoskeletal_code': False,
        'mib_has_endocrine_code': False,
        'mib_has_infectious_code': False,
        
        # Risk indicators
        'mib_high_risk_code_count': 0,
        'mib_medium_risk_code_count': 0,
        'mib_low_risk_code_count': 0,
        'mib_hit_ratio': 0.0,
        'mib_multiple_hits': False,
        
        # Derived scores
        'mib_risk_score': 0.0,
        'mib_severity_score': 0.0,
        'mib_complexity_score': 0.0,
        'mib_overall_score': 0.0,
    }
    
    if not xml_str:
        return features
    
    # Parse response codes
    codes = re.findall(r'<ResponseData>([^<]+)</ResponseData>', xml_str)
    features['mib_code_count'] = len(codes)
    features['mib_total_records'] = len(codes)
    
    # Check for HIT
    if 'HIT' in xml_str or 'RelationRoleCode>HIT<' in xml_str:
        features['mib_hit_count'] = 1
        features['mib_has_hit'] = True
    
    # Parse BMI
    bmi_values = re.findall(r'<BMI>(\d+\.?\d*)</BMI>', xml_str)
    if bmi_values:
        bmi_floats = [float(b) for b in bmi_values]
        features['mib_avg_bmi'] = sum(bmi_floats) / len(bmi_floats)
        features['mib_max_bmi'] = max(bmi_floats)
        features['mib_min_bmi'] = min(bmi_floats)
        features['mib_bmi_over_30'] = features['mib_max_bmi'] > 30
        features['mib_bmi_over_35'] = features['mib_max_bmi'] > 35
    
    # Check condition codes (customize patterns for your schema)
    code_str = ' '.join(codes).upper()
    features['mib_has_cardiac_code'] = any(c in code_str for c in ['CARDIAC', 'HEART', 'CVD'])
    features['mib_has_diabetes_code'] = any(c in code_str for c in ['DIABETES', 'DM', 'INSULIN'])
    features['mib_has_cancer_code'] = any(c in code_str for c in ['CANCER', 'TUMOR', 'MALIG'])
    features['mib_has_respiratory_code'] = any(c in code_str for c in ['COPD', 'ASTHMA', 'PULM'])
    features['mib_has_mental_health_code'] = any(c in code_str for c in ['MENTAL', 'PSYCH', 'DEPRESS'])
    features['mib_has_substance_abuse_code'] = any(c in code_str for c in ['SUBSTANCE', 'ALCOHOL', 'DRUG'])
    
    # Calculate risk scores
    high_risk = sum([features['mib_has_cancer_code'], features['mib_has_cardiac_code'], 
                     features['mib_has_substance_abuse_code']])
    features['mib_high_risk_code_count'] = high_risk
    features['mib_risk_score'] = min(1.0, high_risk * 0.3 + features['mib_hit_count'] * 0.2)
    
    return features


def parse_rx_xml(xml_str: str) -> dict:
    """
    Parse RX XML and extract features.
    
    CUSTOMIZE THIS FUNCTION for your XML schema.
    Returns dict with 65 RX features.
    """
    features = {
        # Core RX metrics
        'rx_total_fills': 0,
        'rx_unique_drugs': 0,
        'rx_unique_ndcs': 0,
        'rx_unique_specialties': 0,
        'rx_unique_prescribers': 0,
        
        # Drug category flags
        'rx_drug_statin': False,
        'rx_drug_metformin': False,
        'rx_drug_insulin': False,
        'rx_drug_opioid': False,
        'rx_drug_benzo': False,
        'rx_drug_antidepressant': False,
        'rx_drug_antipsychotic': False,
        'rx_drug_blood_thinner': False,
        'rx_drug_ace_inhibitor': False,
        'rx_drug_beta_blocker': False,
        'rx_drug_calcium_blocker': False,
        'rx_drug_diuretic': False,
        'rx_drug_ppi': False,
        'rx_drug_thyroid': False,
        'rx_drug_antibiotic': False,
        'rx_drug_steroid': False,
        'rx_drug_immunosuppressant': False,
        'rx_drug_chemo': False,
        'rx_drug_biologic': False,
        'rx_drug_adhd': False,
        'rx_drug_sleep': False,
        'rx_drug_muscle_relaxant': False,
        'rx_drug_gabapentin': False,
        'rx_drug_suboxone': False,
        
        # Specialty flags
        'rx_specialty_cardiology': False,
        'rx_specialty_endocrinology': False,
        'rx_specialty_oncology': False,
        'rx_specialty_psychiatry': False,
        'rx_specialty_neurology': False,
        'rx_specialty_pain_management': False,
        'rx_specialty_rheumatology': False,
        'rx_specialty_pulmonology': False,
        'rx_specialty_gastroenterology': False,
        'rx_specialty_nephrology': False,
        'rx_specialty_primary_care': False,
        'rx_specialty_emergency': False,
        
        # Risk flags
        'flag_opioid_and_benzo': False,
        'flag_polypharmacy_5': False,
        'flag_polypharmacy_10': False,
        'flag_high_risk_combo': False,
        'flag_multiple_controlled': False,
        'flag_multiple_prescribers': False,
        
        # Derived scores
        'rx_risk_score': 0.0,
        'rx_complexity_score': 0.0,
        'rx_cardiac_risk_score': 0.0,
        'rx_metabolic_risk_score': 0.0,
        'rx_mental_health_risk_score': 0.0,
        'rx_pain_risk_score': 0.0,
        'rx_overall_score': 0.0,
    }
    
    if not xml_str:
        return features
    
    # Parse fills
    fills = re.findall(r'<DrugFill>', xml_str)
    features['rx_total_fills'] = len(fills)
    
    # Parse drugs
    drugs = set(re.findall(r'<DrugGenericName>([^<]+)</DrugGenericName>', xml_str))
    features['rx_unique_drugs'] = len(drugs)
    
    # Parse specialties
    specialties = set(re.findall(r'<PhysicianSpecialty>([^<]+)</PhysicianSpecialty>', xml_str))
    features['rx_unique_specialties'] = len(specialties)
    
    drug_str = ' '.join(drugs).upper()
    spec_str = ' '.join(specialties).upper()
    
    # Drug detection (customize patterns for your formulary)
    features['rx_drug_statin'] = any(d in drug_str for d in ['STATIN', 'ATORVASTATIN', 'SIMVASTATIN'])
    features['rx_drug_metformin'] = 'METFORMIN' in drug_str
    features['rx_drug_insulin'] = 'INSULIN' in drug_str
    features['rx_drug_opioid'] = any(d in drug_str for d in ['OXYCODONE', 'HYDROCODONE', 'MORPHINE', 'FENTANYL'])
    features['rx_drug_benzo'] = any(d in drug_str for d in ['ALPRAZOLAM', 'DIAZEPAM', 'LORAZEPAM', 'CLONAZEPAM'])
    features['rx_drug_antidepressant'] = any(d in drug_str for d in ['SERTRALINE', 'FLUOXETINE', 'ESCITALOPRAM'])
    features['rx_drug_antipsychotic'] = any(d in drug_str for d in ['QUETIAPINE', 'RISPERIDONE', 'ARIPIPRAZOLE'])
    features['rx_drug_blood_thinner'] = any(d in drug_str for d in ['WARFARIN', 'ELIQUIS', 'XARELTO'])
    features['rx_drug_gabapentin'] = 'GABAPENTIN' in drug_str or 'PREGABALIN' in drug_str
    features['rx_drug_suboxone'] = any(d in drug_str for d in ['SUBOXONE', 'BUPRENORPHINE'])
    
    # Risk flags
    features['flag_opioid_and_benzo'] = features['rx_drug_opioid'] and features['rx_drug_benzo']
    features['flag_polypharmacy_5'] = features['rx_unique_drugs'] >= 5
    features['flag_polypharmacy_10'] = features['rx_unique_drugs'] >= 10
    features['flag_high_risk_combo'] = features['flag_opioid_and_benzo'] or (features['rx_drug_opioid'] and features['rx_drug_gabapentin'])
    
    # Calculate risk scores
    features['rx_pain_risk_score'] = min(1.0, (0.15 if features['rx_drug_opioid'] else 0) + 
                                         (0.10 if features['rx_drug_benzo'] else 0) +
                                         (0.25 if features['flag_opioid_and_benzo'] else 0))
    features['rx_complexity_score'] = min(1.0, features['rx_unique_drugs'] * 0.08)
    features['rx_risk_score'] = (features['rx_pain_risk_score'] * 0.5 + features['rx_complexity_score'] * 0.5)
    
    return features


def calculate_risk_score(features: dict) -> float:
    """
    Calculate overall risk score from extracted features.
    
    CUSTOMIZE THIS FUNCTION with your scoring logic.
    Can integrate with ML model or use rule-based scoring.
    """
    score = 0.0
    
    # MIB factors
    score += features.get('mib_hit_count', 0) * 0.15
    score += min(0.15, features.get('mib_code_count', 0) * 0.025)
    score += 0.1 if features.get('mib_bmi_over_35', False) else 0
    score += 0.1 if features.get('mib_has_cardiac_code', False) else 0
    score += 0.15 if features.get('mib_has_cancer_code', False) else 0
    score += 0.12 if features.get('mib_has_substance_abuse_code', False) else 0
    
    # RX factors
    score += min(0.15, features.get('rx_total_fills', 0) * 0.02)
    score += min(0.12, features.get('rx_unique_drugs', 0) * 0.02)
    score += 0.15 if features.get('rx_drug_opioid', False) else 0
    score += 0.10 if features.get('rx_drug_benzo', False) else 0
    score += 0.12 if features.get('rx_drug_insulin', False) else 0
    
    # High-risk combinations
    score += 0.25 if features.get('flag_opioid_and_benzo', False) else 0
    score += 0.15 if features.get('flag_high_risk_combo', False) else 0
    score += 0.10 if features.get('flag_polypharmacy_10', False) else 0
    
    return min(1.0, score)


def call_model_registry(features: dict) -> tuple:
    """
    Call Model Registry inference service via internal DNS.
    
    Returns:
        (risk_score, model_version) tuple
    
    This is the MLOps best practice per Caleb's recommendation:
    - Model deployed as service via mv.create_service()
    - Called via internal DNS (e.g., your-model-svc:5000/predict)
    - ~17ms latency vs 10+ seconds for SQL model calls
    """
    try:
        import httpx
        
        # Prepare features for Model Registry format
        feature_dict = {
            "MIB_TOTAL_RECORDS": features.get('mib_total_records', 0),
            "MIB_HIT_COUNT": features.get('mib_hit_count', 0),
            "MIB_HAS_HIT": 1 if features.get('mib_has_hit', False) else 0,
            "MIB_AVG_BMI": features.get('mib_avg_bmi', 25.0),
            "RX_TOTAL_FILLS": features.get('rx_total_fills', 0),
            "RX_UNIQUE_DRUGS": features.get('rx_unique_drugs', 0),
            "RX_DRUG_OPIOID": 1 if features.get('rx_drug_opioid', False) else 0,
            "HAS_MIB_EVIDENCE": 1 if features.get('mib_total_records', 0) > 0 else 0,
            "HAS_RX_EVIDENCE": 1 if features.get('rx_total_fills', 0) > 0 else 0,
            "COMBINED_RISK_SCORE": 0
        }
        
        # Model Registry format: {"data": [[index, feature_dict]]}
        inference_input = {"data": [[0, feature_dict]]}
        
        # Call via internal DNS
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                MODEL_SERVICE_URL,
                json=inference_input,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract prediction: {"data": [[index, {"output_feature_0": value}]]}
            if "data" in result and len(result["data"]) > 0:
                pred = result["data"][0]
                if isinstance(pred, list) and len(pred) > 1:
                    pred_value = pred[1]
                    if isinstance(pred_value, dict):
                        risk_score = float(pred_value.get("output_feature_0", 0))
                    else:
                        risk_score = float(pred_value)
                    return risk_score, "REGISTRY_V2"
        
        return calculate_risk_score(features), "RULE_BASED"
        
    except Exception as e:
        print(f"Model service error: {e}, using rule-based fallback")
        return calculate_risk_score(features), "RULE_BASED"


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print("Starting Real-Time ML Inference API...")
    yield
    print("Shutting down...")

app = FastAPI(
    title="Real-Time ML Inference API",
    description="SPCS-hosted API for real-time risk scoring",
    version="1.0.0",
    lifespan=lifespan
)


@app.post("/health")
async def health_check():
    """Health check endpoint for Snowflake service function."""
    return {"data": [[0, {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}]]}


@app.post("/predict")
async def predict(request: dict = None):
    """
    Main prediction endpoint.
    
    Called via Snowflake service function:
    SELECT FN_PREDICT('policy_id', '<mib_xml>', '<rx_xml>');
    """
    # Handle Snowflake service function format
    if request and "data" in request:
        results = []
        for row in request["data"]:
            row_num = row[0]
            policy_number = row[1] if len(row) > 1 else f"AUTO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            mib_xml = row[2] if len(row) > 2 else None
            rx_xml = row[3] if len(row) > 3 else None
            
            start_time = time.time()
            
            # Parse XML and extract features
            mib_features = parse_mib_xml(mib_xml) if mib_xml else {}
            rx_features = parse_rx_xml(rx_xml) if rx_xml else {}
            
            # Combine all features
            all_features = {**mib_features, **rx_features}
            
            # Calculate risk score - use Model Registry if configured
            if USE_MODEL_REGISTRY:
                risk_score, model_version = call_model_registry(all_features)
            else:
                risk_score = calculate_risk_score(all_features)
                model_version = "RULE_BASED"
            
            risk_level = 'HIGH' if risk_score >= 0.6 else ('MEDIUM' if risk_score >= 0.3 else 'LOW')
            
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            
            results.append([row_num, {
                "policy_number": policy_number,
                "risk_score": round(risk_score, 4),
                "risk_level": risk_level,
                "model_version": model_version,
                "inference_ms": elapsed_ms,
                "feature_count": 105,
                "features": {
                    "mib": mib_features,
                    "rx": rx_features
                }
            }])
        
        return {"data": results}
    
    return {"data": [[0, {"status": "ok", "message": "Use via Snowflake service function"}]]}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Real-Time ML Inference API",
        "version": "1.0.0",
        "features": 105,
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

