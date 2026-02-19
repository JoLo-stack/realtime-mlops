#!/bin/bash
# Export Docker Image from Snowflake Registry
# Run this script to pull and save the image for customer delivery

set -e

# Configuration
REGISTRY="sfsenorthamerica-jlong-aws1.registry.snowflakecomputing.com"
IMAGE_PATH="evidence_feature_pipeline/spcs/images/evidence-api"
IMAGE_TAG="v1"
OUTPUT_DIR="$(dirname "$0")"
OUTPUT_FILE="${OUTPUT_DIR}/evidence-api-${IMAGE_TAG}.tar"

echo "🔐 Step 1: Login to Snowflake Registry"
echo "   You'll be prompted for your password (use your PAT token)"
docker login ${REGISTRY} -u SERVICE_USER

echo ""
echo "📥 Step 2: Pulling image from Snowflake..."
docker pull ${REGISTRY}/${IMAGE_PATH}:${IMAGE_TAG}

echo ""
echo "💾 Step 3: Saving image to tar file..."
docker save -o "${OUTPUT_FILE}" ${REGISTRY}/${IMAGE_PATH}:${IMAGE_TAG}

echo ""
echo "📦 Step 4: Compressing..."
gzip -f "${OUTPUT_FILE}"

echo ""
echo "✅ Done! Image saved to:"
echo "   ${OUTPUT_FILE}.gz"
echo ""
echo "📋 Customer Instructions:"
echo "   1. gunzip evidence-api-${IMAGE_TAG}.tar.gz"
echo "   2. docker load -i evidence-api-${IMAGE_TAG}.tar"
echo "   3. docker tag ${REGISTRY}/${IMAGE_PATH}:${IMAGE_TAG} evidence-api:${IMAGE_TAG}"

# Show file size
ls -lh "${OUTPUT_FILE}.gz"

