#!/usr/bin/env python3
"""
Test the pipeline with a real Pull Request using the GitHub API.
No ngrok required.
"""

import os
from dotenv import load_dotenv
from github import Github, GithubException, Auth

# Load environment variables
load_dotenv()

# Import the pipeline function from main.py
from main import run_analysis_pipeline

# -------------------------------------------------------------------
# CONFIGURATION – CHANGE THESE IF NEEDED
# -------------------------------------------------------------------
REPO_NAME = "Malakalaa23/spectre-test"
PR_NUMBER = 2   # 👈 This is your new PR (real Terraform change)

# -------------------------------------------------------------------
# Main test
# -------------------------------------------------------------------
def main():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN not set in .env")
        return

    try:
        auth = Auth.Token(token)
        g = Github(auth=auth)
        repo = g.get_repo(REPO_NAME)
        pr = repo.get_pull(PR_NUMBER)
        
        # Fetch the list of changed files
        files = [f.filename for f in pr.get_files()]
        
        print(f"✅ Found PR #{PR_NUMBER} in {REPO_NAME}")
        print(f"📄 Changed files: {files}")
        print("🚀 Running pipeline...")
        print("-" * 40)
        
        # Call the pipeline directly (it will fetch files again, but that's fine)
        run_analysis_pipeline(PR_NUMBER, REPO_NAME, "opened")
        
        print("-" * 40)
        print("✅ Pipeline completed!")
        print("📝 Check the PR on GitHub – a comment should appear.")
        print("💾 Check the database: sqlite3 history.db 'SELECT * FROM analyses ORDER BY id DESC LIMIT 1;'")
        
    except GithubException as e:
        print(f"❌ GitHub API error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()