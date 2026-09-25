#!/bin/bash
# start.sh — runs both FastAPI and Streamlit in one container.

set -e

echo "Starting FastAPI on internal port 8000..."
uvicorn main:app --host 0.0.0.0 --port 8000 &

echo "Starting Streamlit on port $PORT..."
streamlit run frontend/app.py \
    --server.port $PORT \
    --server.address 0.0.0.0 \
    --server.headless true