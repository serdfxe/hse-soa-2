#!/usr/bin/env bash
# Generates Pydantic models from the OpenAPI specification.
# Run this script to regenerate app/generated/models.py.
# Usage: bash generate.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "${SCRIPT_DIR}/app/generated"

datamodel-codegen \
  --input "${SCRIPT_DIR}/openapi/spec.yaml" \
  --input-file-type openapi \
  --output "${SCRIPT_DIR}/app/generated/models.py" \
  --output-model-type pydantic_v2.BaseModel \
  --use-standard-collections \
  --field-constraints \
  --strict-nullable \
  --target-python-version 3.12 \
  --collapse-root-models

echo "✓ Generated app/generated/models.py from openapi/spec.yaml"
