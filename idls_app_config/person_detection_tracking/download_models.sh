#!/usr/bin/env bash

set -e

DOWNLOADER=$INTEL_OPENVINO_DIR/deployment_tools/open_model_zoo/tools/downloader/downloader.py
MODELS_PATH=$(dirname "$0")

echo Downloading models to folder "$MODELS_PATH"

python3 $DOWNLOADER --name person-detection-retail-0013 -o $MODELS_PATH
