#!/bin/bash
# start.sh — runs both FastAPI and Streamlit in one container for Render.

set -e

echo "Starting FastAPI on internal port 8000..."
uvicorn main:app --host 0.0.0.0 --port 8000 &

echo "Starting Streamlit on Render port $PORT..."
# Streamlit entry point is app.py in the root directory
streamlit run app.py \
    --server.port $PORT \
    --server.address 0.0.0.0 \
    --server.headless true