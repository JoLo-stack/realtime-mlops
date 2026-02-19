# ============================================================================
# Real-Time ML Pipeline Monitor
# ============================================================================
# Streamlit dashboard for testing and monitoring SPCS inference pipeline

import streamlit as st
from snowflake.snowpark.context import get_active_session
from datetime import datetime
import json

# Initialize session
session = get_active_session()

# ============================================================================
# CONFIGURATION - UPDATE THESE FOR YOUR ENVIRONMENT
# ============================================================================
SERVICE_SCHEMA = "ML_MODELS"
SERVICE_NAME = "INFERENCE_SERVICE"
FULL_SERVICE_NAME = f"{SERVICE_SCHEMA}.{SERVICE_NAME}"
FEATURE_TABLE = "FEATURE_STORE.ONLINE_FEATURES"
PREDICTIONS_TABLE = "ML_MODELS.MODEL_PREDICTIONS"

# Page config
st.set_page_config(
    page_title="Real-Time ML Pipeline",
    page_icon="🚀",
    layout="wide"
)

# Custom styling
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); }
    h1, h2, h3 { color: #e0e0ff !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def run_spcs_inference(policy_number: str, mib_xml: str, rx_xml: str) -> dict:
    """Call SPCS inference service."""
    try:
        # Escape single quotes for SQL
        mib_escaped = mib_xml.replace("'", "''")
        rx_escaped = rx_xml.replace("'", "''")
        
        result = session.sql(f"""
            SELECT {SERVICE_SCHEMA}.FN_API_PREDICT(
                '{policy_number}',
                '{mib_escaped}',
                '{rx_escaped}'
            ) AS result
        """).collect()
        
        if result:
            data = result[0][0]
            if isinstance(data, str):
                data = json.loads(data)
            return data
    except Exception as e:
        st.error(f"SPCS Error: {str(e)}")
    return None

def save_to_feature_store(policy_number: str, risk_score: float):
    """Save features to online feature store."""
    try:
        session.sql(f"""
            MERGE INTO {FEATURE_TABLE} AS t
            USING (SELECT '{policy_number}' AS POLICY_NUMBER) AS s 
            ON t.POLICY_NUMBER = s.POLICY_NUMBER
            WHEN NOT MATCHED THEN INSERT 
                (POLICY_NUMBER, HAS_MIB_DATA, HAS_RX_DATA, COMBINED_RISK_SCORE, FEATURE_CREATED_AT)
            VALUES ('{policy_number}', TRUE, TRUE, {risk_score}, CURRENT_TIMESTAMP())
            WHEN MATCHED THEN UPDATE SET 
                COMBINED_RISK_SCORE = {risk_score},
                FEATURE_UPDATED_AT = CURRENT_TIMESTAMP()
        """).collect()
        return True
    except Exception as e:
        st.error(f"Feature Store Error: {str(e)}")
        return False

def save_prediction(policy_number: str, risk_score: float, risk_level: str):
    """Save prediction to model predictions table."""
    try:
        prediction_id = f"PRED-{policy_number}"
        session.sql(f"""
            INSERT INTO {PREDICTIONS_TABLE}
            (PREDICTION_ID, POLICY_NUMBER, PREDICTION, PREDICTION_CLASS, 
             MODEL_NAME, MODEL_VERSION, SCORE_DATE, CREATED_AT)
            VALUES ('{prediction_id}', '{policy_number}', {risk_score}, '{risk_level}', 
                    'EVIDENCE_RISK_MODEL', 'V2', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())
        """).collect()
        return True
    except Exception as e:
        st.error(f"Prediction Save Error: {str(e)}")
        return False

def get_spcs_status() -> str:
    """Get SPCS service status with robust error handling."""
    try:
        result = session.sql(f"""
            SELECT SYSTEM$GET_SERVICE_STATUS('{FULL_SERVICE_NAME}')
        """).collect()
        
        if result and result[0][0]:
            status_json = result[0][0]
            if isinstance(status_json, str):
                import json
                parsed = json.loads(status_json)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed[0].get('status', 'UNKNOWN')
                elif isinstance(parsed, list) and len(parsed) == 0:
                    return 'SUSPENDED'
            return 'UNKNOWN'
        return 'SUSPENDED'
    except Exception as e:
        error_msg = str(e).lower()
        if 'does not exist' in error_msg:
            return 'NOT_DEPLOYED'
        elif 'suspended' in error_msg:
            return 'SUSPENDED'
        return 'UNAVAILABLE'

def suspend_service():
    """Suspend SPCS service."""
    try:
        session.sql(f"ALTER SERVICE {FULL_SERVICE_NAME} SUSPEND").collect()
        return True, "Service suspended successfully!"
    except Exception as e:
        return False, f"Error: {str(e)}"

def resume_service():
    """Resume SPCS service."""
    try:
        session.sql(f"ALTER SERVICE {FULL_SERVICE_NAME} RESUME").collect()
        return True, "Service resuming... (may take 20-30 seconds)"
    except Exception as e:
        return False, f"Error: {str(e)}"

# ============================================================================
# MAIN UI
# ============================================================================

st.title("🚀 Real-Time ML Pipeline")
st.markdown("**SPCS-Powered Inference** | Sub-300ms Latency | Full MLOps")

# Top metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    status = get_spcs_status()
    if status == "READY":
        status_display = "🟢 READY"
    elif status == "PENDING":
        status_display = "🟡 STARTING"
    elif status == "SUSPENDED":
        status_display = "🟠 SUSPENDED"
    elif status == "NOT_DEPLOYED":
        status_display = "⚪ NOT DEPLOYED"
    else:
        status_display = f"🔴 {status}"
    st.metric("SPCS Status", status_display)

with col2:
    st.metric("Target SLA", "< 300ms")

with col3:
    st.metric("Features", "105")

with col4:
    st.metric("MLOps", "✅ Enabled")

# SPCS Controls in sidebar
st.sidebar.header("🎛️ SPCS Controls")
st.sidebar.markdown(f"**Service:** `{FULL_SERVICE_NAME}`")
st.sidebar.markdown(f"**Status:** {status}")

if status == "READY":
    if st.sidebar.button("⏸️ Suspend Service", use_container_width=True):
        success, msg = suspend_service()
        if success:
            st.sidebar.success(msg)
            st.rerun()
        else:
            st.sidebar.error(msg)
elif status in ["SUSPENDED", "NOT_DEPLOYED", "UNAVAILABLE"]:
    if st.sidebar.button("▶️ Resume Service", use_container_width=True):
        success, msg = resume_service()
        if success:
            st.sidebar.info(msg)
            st.rerun()
        else:
            st.sidebar.error(msg)
else:
    st.sidebar.info("Service is starting...")

st.sidebar.markdown("---")
st.sidebar.info("""
**💰 Cost Info:**
- SPCS charges per-second while running
- Suspend when not in use
- Resume takes ~20-30 seconds
""")

st.markdown("---")

# ============================================================================
# INFERENCE SECTION
# ============================================================================

st.header("🧪 Test Inference")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Input")
    
    policy_prefix = st.selectbox("Policy Prefix", ["TEST", "DEMO", "PROD"])
    
    mode = st.radio(
        "Mode",
        ["SPCS Only (~150ms)", "SPCS + MLOps (~500ms)"],
        help="SPCS Only: Fast inference\nSPCS + MLOps: Inference + saves to Feature Store & Model Registry"
    )
    
    # Sample XML data
    mib_xml = st.text_area(
        "MIB XML", 
        value='<?xml version="1.0"?><Response><ResponseData>CODE1</ResponseData></Response>',
        height=100
    )
    
    rx_xml = st.text_area(
        "RX XML",
        value='<?xml version="1.0"?><IntelRXResponse><DrugFill><DrugGenericName>METFORMIN</DrugGenericName></DrugFill></IntelRXResponse>',
        height=100
    )
    
    # Check if service is ready before allowing inference
    if status != "READY":
        st.warning(f"⚠️ Service is {status}. Resume service to run inference.")
        run_button = st.button("🚀 Run Inference", use_container_width=True, disabled=True)
    else:
        run_button = st.button("🚀 Run Inference", use_container_width=True)

with col2:
    st.subheader("Results")
    
    if run_button and status == "READY":
        import time
        start_time = time.time()
        
        # Generate policy number
        policy_number = f"{policy_prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]}"
        
        with st.spinner("Running SPCS inference..."):
            result = run_spcs_inference(policy_number, mib_xml, rx_xml)
        
        if result:
            spcs_time = round((time.time() - start_time) * 1000, 2)
            
            risk_score = result.get("risk_score", 0)
            risk_level = result.get("risk_level", "LOW")
            inference_ms = result.get("inference_ms", 0)
            model_version = result.get("model_version", "UNKNOWN")
            
            # Display metrics
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Risk Score", f"{risk_score:.3f}")
            with m2:
                color = "🔴" if risk_level == "HIGH" else ("🟡" if risk_level == "MEDIUM" else "🟢")
                st.metric("Risk Level", f"{color} {risk_level}")
            with m3:
                st.metric("Inference", f"{inference_ms}ms")
            with m4:
                st.metric("Total", f"{spcs_time}ms")
            
            st.success(f"✅ Policy: `{policy_number}` | Model: `{model_version}`")
            
            # MLOps writes if selected
            if "MLOps" in mode:
                with st.spinner("Syncing to MLOps..."):
                    mlops_start = time.time()
                    
                    fs_success = save_to_feature_store(policy_number, risk_score)
                    pred_success = save_prediction(policy_number, risk_score, risk_level)
                    
                    mlops_time = round((time.time() - mlops_start) * 1000, 2)
                    
                    if fs_success and pred_success:
                        st.info(f"📊 Feature Store + Model Predictions synced ({mlops_time}ms)")
                    
                    total_time = spcs_time + mlops_time
                    st.markdown(f"**Total Pipeline Time: {total_time}ms**")
            
            # Show full response
            with st.expander("Full Response"):
                st.json(result)
        else:
            st.error("No result returned from SPCS")

# ============================================================================
# MLOPS EXPLORER
# ============================================================================

st.markdown("---")
st.header("📊 MLOps Explorer")

tab1, tab2, tab3 = st.tabs(["Feature Store", "Predictions", "SPCS Controls"])

with tab1:
    st.subheader("Online Feature Store")
    st.caption(f"Table: `{FEATURE_TABLE}`")
    
    try:
        features = session.sql(f"""
            SELECT POLICY_NUMBER, COMBINED_RISK_SCORE, HAS_MIB_DATA, HAS_RX_DATA, 
                   FEATURE_CREATED_AT
            FROM {FEATURE_TABLE}
            ORDER BY FEATURE_CREATED_AT DESC
            LIMIT 10
        """).collect()
        
        if features:
            import pandas as pd
            df = pd.DataFrame([{
                "Policy": r[0],
                "Risk Score": f"{r[1]:.3f}" if r[1] else "N/A",
                "MIB": "✅" if r[2] else "❌",
                "RX": "✅" if r[3] else "❌",
                "Created": r[4].strftime("%H:%M:%S") if r[4] else "N/A"
            } for r in features])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No features stored yet. Run inference with MLOps mode.")
    except Exception as e:
        st.warning(f"Could not load features: {str(e)}")
        st.caption("Make sure the FEATURE_STORE.ONLINE_FEATURES table exists.")

with tab2:
    st.subheader("Model Predictions")
    st.caption(f"Table: `{PREDICTIONS_TABLE}`")
    
    try:
        predictions = session.sql(f"""
            SELECT POLICY_NUMBER, PREDICTION, PREDICTION_CLASS, MODEL_VERSION, CREATED_AT
            FROM {PREDICTIONS_TABLE}
            ORDER BY CREATED_AT DESC
            LIMIT 10
        """).collect()
        
        if predictions:
            import pandas as pd
            df = pd.DataFrame([{
                "Policy": r[0],
                "Score": f"{r[1]:.3f}" if r[1] else "N/A",
                "Level": r[2] or "N/A",
                "Model": r[3] or "N/A",
                "Created": r[4].strftime("%H:%M:%S") if r[4] else "N/A"
            } for r in predictions])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No predictions stored yet. Run inference with MLOps mode.")
    except Exception as e:
        st.warning(f"Could not load predictions: {str(e)}")
        st.caption("Make sure the ML_MODELS.MODEL_PREDICTIONS table exists.")

with tab3:
    st.subheader("SPCS Service Controls")
    
    st.markdown(f"""
    | Setting | Value |
    |---------|-------|
    | Service Name | `{FULL_SERVICE_NAME}` |
    | Current Status | **{status}** |
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Refresh Status", use_container_width=True):
            st.rerun()
    
    with col2:
        suspend_disabled = status != "READY"
        if st.button("⏸️ Suspend", disabled=suspend_disabled, use_container_width=True):
            success, msg = suspend_service()
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    
    with col3:
        resume_disabled = status == "READY" or status == "PENDING"
        if st.button("▶️ Resume", disabled=resume_disabled, use_container_width=True):
            success, msg = resume_service()
            if success:
                st.info(msg)
                st.rerun()
            else:
                st.error(msg)
    
    st.markdown("---")
    
    st.markdown("""
    ### 💡 Tips
    - **Suspend** when not using to save costs
    - **Resume** takes 20-30 seconds to start
    - Service auto-scales between MIN and MAX instances
    
    ### 📊 Monitoring Commands (run in Snowsight)
    ```sql
    -- Check service status
    CALL SYSTEM$GET_SERVICE_STATUS('ML_MODELS.INFERENCE_SERVICE');
    
    -- View service logs
    CALL SYSTEM$GET_SERVICE_LOGS('ML_MODELS.INFERENCE_SERVICE', 0, 'api', 100);
    
    -- Check endpoints
    SHOW ENDPOINTS IN SERVICE ML_MODELS.INFERENCE_SERVICE;
    ```
    """)

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888;'>
    Real-Time ML Pipeline | SPCS + Feature Store + Model Registry<br>
    <small>Internal DNS: ~17ms inference | Total: ~300ms</small>
</div>
""", unsafe_allow_html=True)
