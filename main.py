import sys
import os
import json
import yaml
import traceback
import hashlib
from datetime import datetime
from fastapi import BackgroundTasks, FastAPI, Request
from dotenv import load_dotenv
from github import Github, GithubException, Auth

# Force UTF‑8 for Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
LOG_FILE = "webhook.log"

def log(msg: str):
    timestamp = datetime.utcnow().isoformat()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(msg, flush=True)

# -------------------------------------------------------------------
# Import dependencies (from your existing project)
# -------------------------------------------------------------------
from database import get_all_analyses, get_pr_analysis, save_analysis, is_commit_analyzed, save_commit_analysis
from github_client import post_github_comment, post_inline_comment, get_pr_for_branch, fetch_commit_diff

# Import AI agent
try:
    from ai_agent_groq import generate_insights, generate_inline_suggestions
    log("✅ AI agent imported successfully")
except ImportError as e:
    log(f"⚠️ AI agent import failed: {e}")
    def generate_insights(services, impact):
        return {
            "simulation": "AI unavailable – using fallback.",
            "severity": "Medium",
            "rollback": ["Revert changes", "Restart services"],
            "validation": ["Check health endpoints"],
            "tokens_used": {}
        }
    def generate_inline_suggestions(diff, changed_files, affected_services):
        return []
    log("⚠️ Using fallback AI.")

# Import cache
try:
    from cache import get_cached_diff_suggestions, cache_diff_suggestions, get_cache_key_for_diff
    log("✅ Cache imported successfully")
except ImportError as e:
    log(f"⚠️ Cache import failed: {e}")
    def get_cached_diff_suggestions(key): return None
    def cache_diff_suggestions(key, suggestions): pass
    def get_cache_key_for_diff(diff): return hashlib.md5(diff.encode()).hexdigest()
    log("⚠️ Using fallback cache")

# -------------------------------------------------------------------
# BFS ENGINE – Cached for performance
# -------------------------------------------------------------------
_DEPENDENCY_CACHE = None

def load_dependency_graph_cached():
    """Load dependency graph once and cache it in memory"""
    global _DEPENDENCY_CACHE
    if _DEPENDENCY_CACHE is None:
        graph_path = "backend/data/dependency_graph.yaml"
        resource_path = "backend/data/resource_map.json"
        business_path = "backend/data/business_map.yaml"
        
        graph = {}
        resource_map = {}
        business_map = {}
        
        if os.path.exists(graph_path):
            with open(graph_path, "r", encoding="utf-8") as f:
                graph = yaml.safe_load(f) or {}
            log("✅ Loaded dependency_graph.yaml")
        else:
            log("⚠️ dependency_graph.yaml not found")
        
        if os.path.exists(resource_path):
            with open(resource_path, "r", encoding="utf-8") as f:
                resource_map = json.load(f) or {}
            log("✅ Loaded resource_map.json")
        else:
            log("⚠️ resource_map.json not found")
        
        if os.path.exists(business_path):
            with open(business_path, "r", encoding="utf-8") as f:
                business_map = yaml.safe_load(f) or {}
            log("✅ Loaded business_map.yaml")
        else:
            log("⚠️ business_map.yaml not found")
        
        _DEPENDENCY_CACHE = (graph, resource_map, business_map)
    
    return _DEPENDENCY_CACHE

def calculate_blast_radius(changed_files: list):
    """Optimized BFS – uses cached graph (sub‑millisecond performance)"""
    graph, resource_map, business_map = load_dependency_graph_cached()
    
    if not graph or not changed_files:
        return {
            "changed_resource": "unknown",
            "affected_services": ["unknown_service"],
            "business_impact": 0
        }
    
    # Map files to resources
    resources = set()
    for file in changed_files:
        for resource, patterns in resource_map.items():
            for pattern in patterns:
                if file.endswith(pattern) or pattern in file:
                    resources.add(resource)
                    break
            if resource in resources:
                break
    
    if not resources:
        return {
            "changed_resource": "unknown",
            "affected_services": ["unknown_service"],
            "business_impact": 0
        }
    
    # BFS: find all services affected
    affected_services = set()
    for resource in resources:
        for service, info in graph.get("services", {}).items():
            for dep in info.get("dependencies", []):
                dep_resource = dep.get("resource") or dep.get("name")
                if dep_resource == resource:
                    affected_services.add(service)
            if resource in info.get("resources", []):
                affected_services.add(service)
    
    if not affected_services:
        affected_services = {"unknown_service"}
    
    # Compute business impact
    max_percentage = 0
    for service in affected_services:
        pct = business_map.get(service, {}).get("users_percentage", 0)
        if pct > max_percentage:
            max_percentage = pct
    
    if max_percentage == 0 and affected_services != {"unknown_service"}:
        max_percentage = min(len(affected_services) * 10, 100)
    
    return {
        "changed_resource": ", ".join(resources),
        "affected_services": list(affected_services),
        "business_impact": max_percentage
    }

# -------------------------------------------------------------------
# FastAPI app
# -------------------------------------------------------------------
app = FastAPI(title="Spectre Impact")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# -------------------------------------------------------------------
# Health check
# -------------------------------------------------------------------
@app.get("/ping")
def ping():
    return {"status": "alive"}

# -------------------------------------------------------------------
# Parse GitHub webhook payload
# -------------------------------------------------------------------
def parse_payload(payload: dict):
    pr_number = payload.get("pull_request", {}).get("number")
    repo_full_name = payload.get("repository", {}).get("full_name")
    action = payload.get("action")
    return pr_number, repo_full_name, action

# -------------------------------------------------------------------
# Fetch changed files from GitHub API
# -------------------------------------------------------------------
def fetch_changed_files(repo_full_name: str, pr_number: int) -> list:
    if not GITHUB_TOKEN:
        log("⚠️ GITHUB_TOKEN missing – cannot fetch files.")
        return []
    try:
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        files = [f.filename for f in pr.get_files()]
        return files
    except GithubException as e:
        log(f"❌ GitHub API error: {e}")
        return []
    except Exception as e:
        log(f"❌ Unexpected error fetching files: {e}")
        return []

# -------------------------------------------------------------------
# PR Analysis Pipeline (existing)
# -------------------------------------------------------------------
def run_analysis_pipeline(pr_number: int, repo_name: str, action: str):
    log(f"🚀 Pipeline started for PR #{pr_number} in {repo_name}")
    changed_files = fetch_changed_files(repo_name, pr_number)
    log(f"📄 Changed files: {changed_files}")

    try:
        blast = calculate_blast_radius(changed_files)
        log(f"💥 Blast radius: {blast}")
    except Exception as e:
        log(f"❌ BFS failed: {e}")
        log(traceback.format_exc())
        return

    try:
        insights = generate_insights(blast["affected_services"], blast["business_impact"])
        log(f"🤖 Insights generated: {insights.get('severity', 'Unknown')}")
    except Exception as e:
        log(f"❌ AI agent failed: {e}")
        log(traceback.format_exc())
        insights = {
            "simulation": "AI unavailable – using fallback.",
            "severity": "Medium",
            "rollback": ["Revert changes", "Restart services"],
            "validation": ["Check health endpoints"],
            "tokens_used": {}
        }

    try:
        save_analysis(pr_number, repo_name, blast, insights)
        log(f"💾 Saved analysis for PR #{pr_number}")
    except Exception as e:
        log(f"❌ Database save failed: {e}")
        log(traceback.format_exc())

    try:
        post_github_comment(pr_number, repo_name, blast, insights)
        log(f"📝 Comment posted to PR #{pr_number}")
    except Exception as e:
        log(f"❌ GitHub comment failed: {e}")
        log(traceback.format_exc())

# -------------------------------------------------------------------
# NEW: Commit Analysis Pipeline (for inline feedback)
# -------------------------------------------------------------------
def run_commit_analysis(repo_name: str, commit_sha: str, branch: str, changed_files: list):
    log(f"🚀 Auto-analyzing commit {commit_sha[:7]} on {branch}")
    log(f"📄 Changed files: {changed_files}")
    
    # 1. BFS – compute blast radius
    try:
        blast = calculate_blast_radius(changed_files)
        log(f"💥 Blast radius: {blast}")
    except Exception as e:
        log(f"❌ BFS failed: {e}")
        log(traceback.format_exc())
        return
    
    # 2. Get diff for inline analysis
    diff = fetch_commit_diff(repo_name, commit_sha)
    if not diff:
        log("⚠️ No diff available – skipping inline analysis")
        return
    
    # 3. Check cache for this diff
    diff_key = get_cache_key_for_diff(diff)
    cached_suggestions = get_cached_diff_suggestions(diff_key)
    
    if cached_suggestions is not None:
        log(f"📦 Using cached suggestions ({len(cached_suggestions)} items)")
        suggestions = cached_suggestions
    else:
        # 4. AI – generate inline suggestions
        try:
            suggestions = generate_inline_suggestions(diff, changed_files, blast["affected_services"])
            log(f"💡 Generated {len(suggestions)} inline suggestions")
            if suggestions:
                cache_diff_suggestions(diff_key, suggestions)
        except Exception as e:
            log(f"❌ AI generation failed: {e}")
            log(traceback.format_exc())
            suggestions = []
    
    # 5. Post inline comments
    if suggestions:
        for s in suggestions:
            try:
                post_inline_comment(
                    repo_name, 
                    commit_sha, 
                    s.get("file"), 
                    s.get("line"), 
                    s.get("suggestion"), 
                    s.get("severity", "High")
                )
                log(f"📝 Posted inline comment on {s.get('file')}:{s.get('line')}")
            except Exception as e:
                log(f"❌ Failed to post inline comment: {e}")
    else:
        log("💡 No inline suggestions generated")
    
    # 6. Check if PR exists for this branch
    try:
        pr_number = get_pr_for_branch(repo_name, branch)
        if pr_number:
            log(f"🔍 Found PR #{pr_number} for this branch")
            insights = generate_insights(blast["affected_services"], blast["business_impact"])
            post_github_comment(pr_number, repo_name, blast, insights)
            log(f"📝 Posted PR comment on #{pr_number}")
        else:
            log("ℹ️ No open PR found for this branch")
    except Exception as e:
        log(f"⚠️ PR comment failed: {e}")
    
    # 7. Save to database
    try:
        save_commit_analysis(
            commit_sha, 
            repo_name, 
            branch, 
            changed_files,
            blast["affected_services"], 
            blast["business_impact"], 
            suggestions
        )
        log(f"💾 Saved analysis for commit {commit_sha[:7]}")
    except Exception as e:
        log(f"❌ Database save failed: {e}")
        log(traceback.format_exc())
    
    log(f"✅ Commit analysis complete for {commit_sha[:7]}")

# -------------------------------------------------------------------
# Webhook endpoint
# -------------------------------------------------------------------
@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored"}
    
    if not isinstance(payload, dict):
        return {"status": "ignored"}
    
    event_type = request.headers.get("X-GitHub-Event")
    
    # NEW: Push event handler
    if event_type == "push":
        repo_name = payload["repository"]["full_name"]
        branch = payload["ref"].replace("refs/heads/", "")
        commit_sha = payload["after"]
        
        changed_files = []
        for commit in payload.get("commits", []):
            changed_files.extend(commit.get("added", []))
            changed_files.extend(commit.get("modified", []))
        changed_files = list(set(changed_files))
        
        if not changed_files:
            return {"status": "no files changed"}
        
        if is_commit_analyzed(commit_sha):
            return {"status": "already analyzed"}
        
        background_tasks.add_task(
            run_commit_analysis,
            repo_name, commit_sha, branch, changed_files
        )
        
        return {"status": "analyzing", "commit": commit_sha}
    
    # Existing PR webhook handler
    if "pull_request" not in payload:
        return {"status": "ignored"}
    
    pr_number, repo_name, action = parse_payload(payload)
    if pr_number is None or repo_name is None or action != "opened":
        return {"status": "ignored"}
    
    log(f"🔥 Webhook received: PR #{pr_number}, {repo_name}, action={action}")
    background_tasks.add_task(run_analysis_pipeline, pr_number, repo_name, action)
    return {"received": True}

# -------------------------------------------------------------------
# Dashboard API endpoints
# -------------------------------------------------------------------
@app.get("/api/analyses")
def list_analyses(limit: int = 50):
    return get_all_analyses(limit)

@app.get("/api/analyses/{pr_number}")
def read_pr_analysis(pr_number: int):
    return get_pr_analysis(pr_number)

@app.get("/api/metrics")
def metrics():
    analyses = get_all_analyses(limit=1000)
    total_prs = len(analyses)
    high_risk_prs = sum(1 for a in analyses if a.get("severity") in ("Critical", "High"))
    return {"total_prs": total_prs, "high_risk_prs": high_risk_prs}

# -------------------------------------------------------------------
# Run the server
# -------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    log("🚀 Starting Spectre Impact server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)