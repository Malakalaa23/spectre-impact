import json
import logging
from typing import List

from google import genai
from google.genai import types
from pydantic import BaseModel
from config import get_google_api_key

# Setup logging so you can see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------
# 1. CONFIGURE GEMINI
# ------------------------------
try:
    client = genai.Client(api_key=get_google_api_key())
    logger.info("✅ Gemini configured successfully.")
except Exception as e:
    logger.error(f"❌ Failed to configure Gemini: {e}")

# ------------------------------
# 2. DEFINE THE EXACT OUTPUT SHAPE (Pydantic Schema)
# ------------------------------
class ImpactReport(BaseModel):
    simulation: str          # The "domino effect" story
    severity: str            # Critical, High, Medium, Low
    rollback: List[str]      # 3 specific steps
    validation: List[str]    # 3 health-check commands

# ------------------------------
# 3. THE MASTER PROMPT (Your "Senior SRE" Persona)
# ------------------------------
def build_prompt(services: List[str], impact_percentage: int) -> str:
    services_str = ", ".join(services)
    return f"""
You are a Senior Staff DevOps Engineer with 20 years of experience.

A developer is changing code that affects these services: **{services_str}**.
This impacts **{impact_percentage}%** of users.

Generate a deployment risk report.

RULES:
1. Severity: "Critical" if >70% users, "High" if >40%, "Medium" if >10%, else "Low".
2. Simulation: A dramatic 2-3 sentence "domino effect" story.
3. Rollback: 3 specific terminal/kubectl commands.
4. Validation: 3 specific health-check curl/kubectl commands.

Return ONLY valid JSON matching the schema.
"""

# ------------------------------
# 4. THE CORE FUNCTION (Ahmed & Abu Bakr will call this)
# ------------------------------
def generate_insights(services: List[str], impact_percentage: int) -> dict:
    """The main entry point for the AI Agent."""
    if not services:
        logger.warning("No services provided. Returning fallback.")
        return get_fallback(["Unknown"], 0)
    
    logger.info(f"🧠 Generating insights for: {services}")
    
    try:
        prompt = build_prompt(services, impact_percentage)
        
        # Call Gemini with the new SDK
        response = client.models.generate_content(
          model='models/gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=500,
                response_mime_type="application/json",
                response_schema=ImpactReport
            )
        )
        
        # Parse the response
        parsed = json.loads(response.text)
        return {
            "simulation": parsed["simulation"],
            "severity": parsed["severity"],
            "rollback": parsed["rollback"],
            "validation": parsed["validation"]
        }
        
    except Exception as e:
        logger.error(f"❌ AI Error: {e}")
        return get_fallback(services, impact_percentage)

# ------------------------------
# 5. THE FALLBACK (Keeps demo alive if API fails)
# ------------------------------
def get_fallback(services: List[str], impact_percentage: int) -> dict:
    severity = "High" if impact_percentage > 50 else "Medium"
    return {
        "simulation": f"⚠️ [AI Offline] Manual review needed for {', '.join(services)}.",
        "severity": severity,
        "rollback": [
            "git revert HEAD --no-edit",
            "kubectl rollout undo deployment -n production",
            "kubectl rollout status deployment -n production"
        ],
        "validation": [
            "curl -f https://api.your-app.com/health",
            "kubectl get pods -n production | grep Running",
            "kubectl logs -l app=your-service --tail=50"
        ]
    }

# ------------------------------
# 6. YOUR LOCAL TEST (Run this right now!)
# ------------------------------
if __name__ == "__main__":
    print("\n🚀 Testing your AI Agent locally...")
    
    # Simulate Abu Bakr's BFS output (you don't need him yet!)
    dummy_services = ["payment_service", "login_service"]
    dummy_impact = 85
    
    result = generate_insights(dummy_services, dummy_impact)
    
    print("\n" + "="*60)
    print("🤖 YOUR AI AGENT RESPONSE:")
    print("="*60)
    print(f"📈 Severity:   {result['severity']}")
    print(f"🔮 Simulation: {result['simulation']}")
    print(f"🔄 Rollback:   {result['rollback']}")
    print(f"✅ Validation: {result['validation']}")
    print("="*60)