-- ============================================================================
-- STEP 5: Deploy Streamlit Dashboard (Optional)
-- ============================================================================

USE DATABASE REALTIME_ML_PIPELINE;

-- Create stage for Streamlit files
CREATE STAGE IF NOT EXISTS STREAMLIT_APP.STREAMLIT_STAGE
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');

-- Upload streamlit_app.py to stage first:
-- snow stage copy streamlit/streamlit_app.py @REALTIME_ML_PIPELINE.STREAMLIT_APP.STREAMLIT_STAGE/

-- Create Streamlit app
CREATE OR REPLACE STREAMLIT STREAMLIT_APP.ML_PIPELINE_MONITOR
    ROOT_LOCATION = '@STREAMLIT_APP.STREAMLIT_STAGE'
    MAIN_FILE = '/streamlit_app.py'
    QUERY_WAREHOUSE = ML_INFERENCE_WH
    COMMENT = 'Real-Time ML Pipeline Monitor - Test & Monitor Dashboard';

-- Grant access
GRANT USAGE ON STREAMLIT STREAMLIT_APP.ML_PIPELINE_MONITOR TO ROLE ACCOUNTADMIN;

-- Get Streamlit URL
SHOW STREAMLITS IN SCHEMA STREAMLIT_APP;

SELECT 'Streamlit deployed! Access from Snowsight.' AS status;

