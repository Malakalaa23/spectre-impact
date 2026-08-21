import logging
logging.basicConfig(level=logging.INFO)
from main import run_analysis_pipeline

run_analysis_pipeline(99, "test/repo", "opened", ["terraform/customer_database.tf"])