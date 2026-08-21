markdown
# 🤖 AI Agent - Spectre Impact

## Overview

The AI Agent is the **brain** of Spectre Impact. It generates deployment risk reports from a list of affected services, acting like a Senior DevOps Engineer reviewing a pull request.

**What it does:**
- Takes a list of services and impact percentage
- Generates a dramatic "domino effect" simulation
- Assigns a severity level (Critical, High, Medium, Low)
- Provides rollback commands
- Provides validation/health-check commands
- Tracks token usage for efficiency monitoring
- Caches results to avoid duplicate API calls

**Why it matters:**
Instead of just saying "these services changed," the AI tells you:
- What could go wrong
- How bad it could be
- How to rollback
- How to verify it's working

---

## How It Works
User calls generate_insights(services, impact_percentage)
↓
Check if result is cached
↓
Build prompt for Groq API
↓
Call Groq API (llama-3.3-70b)
↓
Extract JSON from markdown wrapper
↓
Parse JSON into Python dictionary
↓
Add token usage tracking
↓
Store in cache
↓
Return structured result

text

---

## API Contract

### Input Parameters

| Parameter | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `services` | `List[str]` | List of affected services | `["payment_service", "login_service"]` |
| `impact_percentage` | `int` | Percentage of users affected (0-100) | `85` |

### Output Structure

```python
{
    "simulation": "The payment_service update triggers a cascade failure...",
    "severity": "Critical",  # Critical, High, Medium, Low
    "rollback": [
        "kubectl rollout undo deployment payment_service",
        "git revert --hard HEAD~1 && git push origin main",
        "kubectl restart deployment login_service"
    ],
    "validation": [
        "curl -X GET https://example.com/payment/health",
        "kubectl get pods -n payment-service -o wide",
        "tail -f /var/log/payment-service.log"
    ],
    "tokens_used": {
        "input_tokens": 242,
        "output_tokens": 169,
        "total_tokens": 411
    }
}
Severity Levels
Severity	Criteria
Critical	>70% users affected
High	>40% users affected
Medium	>10% users affected
Low	<10% users affected
Integration
Import the Function
python
from ai_agent_groq import generate_insights
Basic Usage
python
# Example: Analyze payment_service with 85% user impact
result = generate_insights(["payment_service", "login_service"], 85)

# Access the results
print(result["severity"])      # "Critical"
print(result["simulation"])    # "The payment_service update triggers..."
print(result["rollback"])      # ["kubectl rollout undo...", ...]
print(result["validation"])    # ["curl /health...", ...]
print(result["tokens_used"])   # {"input_tokens": 242, "output_tokens": 169, "total_tokens": 411}
Integration with BFS (Abu Bakr's Engine)
python
# After BFS calculates affected services
bfs_result = {
    "affected_services": ["payment_service", "login_service"],
    "business_impact": 85
}

# Pass to AI agent
ai_result = generate_insights(
    services=bfs_result["affected_services"],
    impact_percentage=bfs_result["business_impact"]
)
Integration with Webhook (Ahmed's Backend)
python
# In main.py webhook handler
from ai_agent_groq import generate_insights

@app.post("/webhook")
async def webhook(request: Request):
    # ... get PR data ...
    
    # After BFS calculation
    bfs_result = calculate_blast_radius(changed_files)
    
    # Get AI insights
    ai_result = generate_insights(
        services=bfs_result["affected_services"],
        impact_percentage=bfs_result["business_impact"]
    )
    
    # Save to database
    save_analysis(pr_number, bfs_result, ai_result)
    
    # Post comment to GitHub
    post_github_comment(pr_number, ai_result)
Multi-Level Summaries
The AI Agent also supports generating two versions of the same analysis:

1. DevOps View (Technical)
python
from multi_level_summary import generate_devops_summary

devops_view = generate_devops_summary(ai_result)
# Returns: Technical summary with commands and service details
2. Executive View (Business-Friendly)
python
from multi_level_summary import generate_executive_summary

executive_view = generate_executive_summary(ai_result)
# Returns: Plain English summary focusing on business impact
Full Report
python
from multi_level_summary import generate_full_report

report = generate_full_report(["payment_service", "login_service"], 85)
print(report["devops"])      # Technical version
print(report["executive"])   # Business version
Features
✅ Cache System
Results are cached by (services, impact_percentage)

Prevents duplicate API calls during demo

Message: 📦 Using cached response

✅ Token Tracking
Tracks input tokens, output tokens, and total tokens

Returns tokens_used in the output

Helps monitor API usage and costs

✅ Fallback System
If API is offline or rate-limited

Returns structured fallback data

Demo never breaks

✅ Error Handling
Handles JSON parse errors gracefully

Handles API errors gracefully

Always returns structured data

Setup
1. Get a Groq API Key
Go to: https://console.groq.com/keys

Sign up (free, no credit card)

Create an API key (starts with gsk_...)

2. Add to .env
env
GROQ_API_KEY=gsk_...your-key-here...
3. Install Dependencies
bash
pip install groq
4. Test the AI Agent
bash
python ai_agent_groq.py
5. Run Integration Tests
bash
python test_integration.py
Testing
Run the AI Agent Test
bash
python ai_agent_groq.py
Expected Output:

text
============================================================
🚀 Testing AI Agent with Groq
============================================================

✅ Groq configured successfully.
🧠 Generating fresh insights for: ['payment_service', 'login_service']
✅ Received response from Groq (799 characters)
📝 Extracted JSON (799 characters)
📊 Token Usage: {'input_tokens': 242, 'output_tokens': 169, 'total_tokens': 411}

============================================================
🤖 AI AGENT RESPONSE
============================================================
📈 Severity:   Critical
🔮 Simulation: The payment database migration fails...
🔄 Rollback:   ['kubectl rollout undo deployment payment_service', ...]
✅ Validation: ['curl -X GET https://example.com/payment/health', ...]
📊 Tokens:     411 total (242 input, 169 output)
============================================================
Run Integration Tests
bash
python test_integration.py
Expected Output:

text
============================================================
🚀 Running Integration Tests
============================================================

🧪 Test 1: Basic AI Agent
✅ Passed

🧪 Test 2: Multi-Level Summaries
✅ Passed

🧪 Test 3: Cache System
✅ Passed

🧪 Test 4: Different Inputs
✅ Passed

============================================================
✅ All tests complete!
============================================================
Troubleshooting
Problem	Solution
ModuleNotFoundError: No module named 'groq'	Run pip install groq
GROQ_API_KEY not found	Add GROQ_API_KEY to .env file
JSON parse error	Check if Groq returned valid JSON. The extract_json() function handles markdown.
Rate limit error	Add caching. Wait a few minutes. Upgrade to paid tier if needed.
📦 Using cached response	That's normal! It means the cache is working.
File Structure
text
spectre-impact/
├── ai_agent_groq.py          # Core AI agent with cache + token tracking
├── multi_level_summary.py    # DevOps + Executive summaries
├── test_integration.py       # Integration test suite
├── README_AI_AGENT.md        # This file
├── config.py                 # Environment variables
├── .env                      # API keys (gitignored)
└── data/
    ├── dependency_map.yaml   # Service dependency graph
    └── business_map.yaml     # Service → Business feature mapping
Contributors
Role	Name	Responsibilities
AI Engineer	Malak	AI Agent development, prompt engineering, multi-level summaries
Backend Developer	Ahmed	FastAPI webhook, GitHub integration, database
Backend Developer	Abu Bakr	BFS engine, dependency maps
Frontend Developer	Merna	Streamlit dashboard
Frontend Developer	Habiba	Dashboard UI, data visualization
License
This project is built for the DevOpsDays Cairo 2026 Hackathon.

Quick Reference
One-Line Summary
The AI Agent takes services and impact percentage, returns simulation, severity, rollback, and validation.

Key Functions
Function	Purpose
generate_insights(services, impact)	Main function for AI analysis
generate_devops_summary(result)	Technical summary
generate_executive_summary(result)	Business summary
generate_full_report(services, impact)	Both summaries
Important Files
File	Purpose
ai_agent_groq.py	Core AI agent
multi_level_summary.py	Summaries
test_integration.py	Tests
Ready to integrate! 🚀