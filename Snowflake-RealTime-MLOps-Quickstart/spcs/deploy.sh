#!/bin/bash
# ============================================================================
# SPCS Deployment Script
# ============================================================================
# Usage: ./deploy.sh [account] [database]
#
# Prerequisites:
# - Docker Desktop running
# - Snowflake CLI (snow) installed and configured
# - Logged into Snowflake image registry

set -e

# Configuration - CUSTOMIZE THESE
ACCOUNT="${1:-your-account}"
DATABASE="${2:-REALTIME_ML_PIPELINE}"
IMAGE_NAME="evidence-api"
IMAGE_TAG="v1"

# Derived values
REGISTRY_URL="${ACCOUNT}.registry.snowflakecomputing.com"
FULL_IMAGE="${REGISTRY_URL}/${DATABASE,,}/spcs/images/${IMAGE_NAME}:${IMAGE_TAG}"

echo "=============================================="
echo "SPCS Deployment"
echo "=============================================="
echo "Account: ${ACCOUNT}"
echo "Database: ${DATABASE}"
echo "Image: ${FULL_IMAGE}"
echo "=============================================="

# Step 1: Build Docker image
echo ""
echo "Step 1: Building Docker image..."
docker build --platform linux/amd64 -t ${IMAGE_NAME}:${IMAGE_TAG} .

# Step 2: Login to Snowflake registry
echo ""
echo "Step 2: Logging into Snowflake registry..."
snow spcs image-registry login

# Step 3: Tag image
echo ""
echo "Step 3: Tagging image..."
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${FULL_IMAGE}

# Step 4: Push image
echo ""
echo "Step 4: Pushing image to Snowflake..."
docker push ${FULL_IMAGE}

# Step 5: Deploy service
echo ""
echo "Step 5: Deploying SPCS service..."
snow sql -q "
DROP SERVICE IF EXISTS ${DATABASE}.SPCS.INFERENCE_SERVICE;

CREATE SERVICE ${DATABASE}.SPCS.INFERENCE_SERVICE
    IN COMPUTE POOL ML_INFERENCE_POOL
    FROM SPECIFICATION \$\$
spec:
  containers:
    - name: api
      image: /${DATABASE,,}/spcs/images/${IMAGE_NAME}:${IMAGE_TAG}
      env:
        SNOWFLAKE_DATABASE: ${DATABASE}
        SNOWFLAKE_SCHEMA: FEATURE_STORE
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
\$\$
    MIN_INSTANCES = 1
    MAX_INSTANCES = 2;
"

# Step 6: Wait for service to start
echo ""
echo "Step 6: Waiting for service to start..."
sleep 20

# Step 7: Check status
echo ""
echo "Step 7: Checking service status..."
snow sql -q "CALL SYSTEM\$GET_SERVICE_STATUS('${DATABASE}.SPCS.INFERENCE_SERVICE');"

echo ""
echo "=============================================="
echo "Deployment complete!"
echo "=============================================="
echo ""
echo "Test with:"
echo "  SELECT ${DATABASE}.SPCS.FN_PREDICT('TEST-001', '<mib_xml>', '<rx_xml>');"

