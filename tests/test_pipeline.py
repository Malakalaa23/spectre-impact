from main import run_analysis_pipeline

run_analysis_pipeline(
    pr_number=99,
    repo_name="test/repo",
    action="opened",
    changed_files=["terraform/customer_database.tf"]
)