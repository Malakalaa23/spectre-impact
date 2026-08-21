import logging
from typing import Dict, List
from ai_agent_groq import generate_insights

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_devops_summary(ai_result: Dict) -> str:
    """
    Technical summary for DevOps engineers.
    Focuses on commands, services, and technical details.
    """
    severity_emoji = {
        "Critical": "🚨",
        "High": "🔴",
        "Medium": "🟡",
        "Low": "🟢"
    }.get(ai_result["severity"], "⚪")
    
    summary = f"""
### 👨‍💻 DevOps View

{severity_emoji} **Severity:** {ai_result['severity']}

**Impact Simulation:**
{ai_result['simulation']}

**Rollback Commands:**
{chr(10).join([f"  - `{cmd}`" for cmd in ai_result['rollback']])}

**Validation Commands:**
{chr(10).join([f"  - `{cmd}`" for cmd in ai_result['validation']])}
"""
    return summary

def generate_executive_summary(ai_result: Dict) -> str:
    """
    Plain English summary for business stakeholders.
    Focuses on business impact and high-level actions.
    """
    severity_emoji = {
        "Critical": "🚨",
        "High": "🔴",
        "Medium": "🟡",
        "Low": "🟢"
    }.get(ai_result["severity"], "⚪")
    
    # Simplify severity for business
    severity_map = {
        "Critical": "⚠️ Urgent - Immediate attention required",
        "High": "⚠️ High priority - Needs review before deployment",
        "Medium": "📋 Medium priority - Can proceed with caution",
        "Low": "✅ Low priority - Safe to deploy"
    }
    
    summary = f"""
### 📊 Executive Summary

{severity_emoji} **Risk Level:** {severity_map.get(ai_result['severity'], 'Unknown')}

**What Could Happen:**
{ai_result['simulation']}

**Action Required:**
- Rollback is available if needed
- Validation checks are ready
- Monitor system health post-deployment
"""
    return summary

def generate_full_report(services: List[str], impact_percentage: int) -> Dict:
    """
    Generate both DevOps and Executive summaries.
    """
    # Get AI insights
    ai_result = generate_insights(services, impact_percentage)
    
    # Generate summaries
    devops = generate_devops_summary(ai_result)
    executive = generate_executive_summary(ai_result)
    
    return {
        "raw": ai_result,
        "devops": devops,
        "executive": executive
    }

# ------------------------------
# TEST THE MULTI-LEVEL SUMMARIES
# ------------------------------
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Testing Multi-Level Summaries")
    print("="*60 + "\n")
    
    # Test data
    services = ["payment_service", "login_service"]
    impact = 85
    
    report = generate_full_report(services, impact)
    
    print("="*60)
    print("👨‍💻 DEVOPS VIEW")
    print("="*60)
    print(report["devops"])
    
    print("\n" + "="*60)
    print("📊 EXECUTIVE VIEW")
    print("="*60)
    print(report["executive"])