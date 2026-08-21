import sys
import os
import json
import yaml
import traceback
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

LOG_FILE = "webhook.log"

def log(msg: str):
    timestamp = datetime.utcnow().isoformat()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(msg, flush=True)

# -------------------------------------------------------------------
# BFS ENGINE – now with business impact
# -------------------------------------------------------------------
def load_dependency_graph():
    """Load dependency graph and business map."""
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
        log("⚠️  dependency_graph.yaml not found – using empty graph.")
    
    if os.path.exists(resource_path):
        with open(resource_path, "r", encoding="utf-8") as f:
            resource_map = json.load(f) or {}
        log("✅ Loaded resource_map.json")
    else:
        log("⚠️  resource_map.json not found – using empty map.")
    
    if os.path.exists(business_path):
        with open(business_path, "r", encoding="utf-8") as f:
            business_map = yaml.safe_load(f) or {}
        log("✅ Loaded business_map.yaml")
    else:
        log("⚠️  business_map.yaml not found – using empty business map.")
    
    return graph, resource_map, business_map

def calculate_blast_radius(changed_files: list):
    graph, resource_map, business_map = load_dependency_graph()
    
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
            if any(file.endswith(pattern) or pattern in file for pattern in patterns):
                resources.add(resource)
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
                if dep.get("resource") == resource or dep.get("name") == resource:
                    affected_services.add(service)
            if resource in info.get("resources", []):
                affected_services.add(service)
    
    if not affected_services:
        affected_services = {"unknown_service"}
    
    # Compute business impact: maximum user percentage among affected services
    max_percentage = 0
    for service in affected_services:
        # Look up in business map (case-insensitive? We'll keep exact)
        pct = business_map.get(service, {}).get("users_percentage", 0)
        if pct > max_percentage:
            max_percentage = pct
    
    # If no percentage found, fallback to len(services)*10 (capped at 100)
    if max_percentage == 0 and affected_services != {"unknown_service"}:
        max_percentage = min(len(affected_services) * 10, 100)
    
    return {
        "changed_resource": ", ".join(resources),
        "affected_services": list(affected_services),
        "business_impact": max_percentage
    }

# -------------------------------------------------------------------
# AI agent and other modules
# -------------------------------------------------------------------
from database import get_all_analyses, get_pr_analysis, save_analysis
from github_client import post_github_comment

try:
    from ai_agent_groq import generate_insights
    log("✅ AI agent imported successfully")
except ImportError as e:
    log(f"⚠️  AI agent import failed: {e}")
    def generate_insights(services, impact):
        return {
            "simulation": "AI unavailable – using fallback.",
            "severity": "Medium",
            "rollback": ["Revert changes", "Restart services"],
            "validation": ["Check health endpoints"],
            "tokens_used": {}
        }
    log("⚠️  Using fallback AI.")

app = FastAPI(title="Spectre Impact")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

@app.get("/ping")
def ping():
    return {"status": "alive"}

def parse_payload(payload: dict):
    pr_number = payload.get("pull_request", {}).get("number")
    repo_full_name = payload.get("repository", {}).get("full_name")
    action = payload.get("action")
    return pr_number, repo_full_name, action

def fetch_changed_files(repo_full_name: str, pr_number: int) -> list:
    if not GITHUB_TOKEN:
        log("⚠️  GITHUB_TOKEN missing – cannot fetch files.")
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

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored"}
    if not isinstance(payload, dict):
        return {"status": "ignored"}
    if "pull_request" not in payload:
        return {"status": "ignored"}
    pr_number, repo_name, action = parse_payload(payload)
    if pr_number is None or repo_name is None or action != "opened":
        return {"status": "ignored"}
    log(f"🔥 Webhook received: PR #{pr_number}, {repo_name}, action={action}")
    background_tasks.add_task(run_analysis_pipeline, pr_number, repo_name, action)
    return {"received": True}

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

if __name__ == "__main__":
    import uvicorn
    log("🚀 Starting Spectre Impact server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)