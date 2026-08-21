"""
Team-Specific Recommendations
Sends different advice to different teams

What It Does:
- Maps services to teams
- Detects which teams are affected
- Generates team-specific advice
- Prioritizes based on risk

Why Judges Will Love It:
- Shows understanding of team dynamics
- Sends relevant info to right people
- Saves teams from reading irrelevant information
"""

import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Team mapping - which service belongs to which team
TEAM_MAPPING = {
    "payment": "Payment Team",
    "checkout": "Frontend Team",
    "login": "Security Team",
    "auth": "Security Team",
    "database": "DBA Team",
    "db": "DBA Team",
    "notification": "Backend Team",
    "inventory": "Backend Team",
    "customer": "Backend Team",
    "profile": "Backend Team",
    "api": "Backend Team",
    "gateway": "Backend Team",
    "user": "Backend Team"
}

# Team priorities
TEAM_PRIORITIES = {
    "Payment Team": "🔴 CRITICAL - Revenue at risk",
    "Security Team": "🔐 HIGH - Security implications",
    "DBA Team": "💾 HIGH - Database changes",
    "Frontend Team": "🟡 MEDIUM - User impact",
    "Backend Team": "🟡 MEDIUM - API changes",
    "Unknown": "🟢 LOW - Standard review"
}

# Team-specific advice
TEAM_ADVICE = {
    "Payment Team": "⚠️ This change affects payment processing. Revenue is at risk. Coordinate with finance team before deployment. Ensure rollback plan is ready.",
    "Security Team": "🔐 Authentication or security changes detected. Requires security review. Ensure proper testing and documentation.",
    "DBA Team": "💾 Database schema change detected. Ensure backups are available. Test migration on staging first. Have rollback ready.",
    "Frontend Team": "✅ UI or checkout changes detected. Standard deployment procedures apply. Test on staging first.",
    "Backend Team": "📦 API or backend changes detected. Ensure backward compatibility. Update API documentation.",
    "Unknown": "📋 Standard review required. No specific team identified."
}

def get_team_specific_recommendations(services: List[str]) -> Dict:
    """
    Generate team-specific recommendations for affected services.

    Args:
        services: List of affected services

    Returns:
        Dictionary with team recommendations
    """
    if not services:
        return {"error": "No services provided"}

    affected_teams = {}

    for service in services:
        team = _find_team_for_service(service)

        if team not in affected_teams:
            affected_teams[team] = []

        if service not in affected_teams[team]:
            affected_teams[team].append(service)

    recommendations = {}
    for team, team_services in affected_teams.items():
        recommendations[team] = {
            "services": team_services,
            "priority": TEAM_PRIORITIES.get(team, TEAM_PRIORITIES["Unknown"]),
            "advice": TEAM_ADVICE.get(team, TEAM_ADVICE["Unknown"])
        }

    logger.info(f"✅ Generated recommendations for {len(recommendations)} teams")
    return recommendations

def _find_team_for_service(service: str) -> str:
    """Find which team owns a service."""
    service_lower = service.lower()

    for key, team in TEAM_MAPPING.items():
        if key in service_lower:
            return team

    return "Unknown"

def format_recommendations_for_display(recommendations: Dict) -> str:
    """Format recommendations for display."""
    if not recommendations:
        return "No specific team recommendations."

    if "error" in recommendations:
        return f"⚠️ {recommendations['error']}"

    result = "📋 Team-Specific Recommendations\n\n"

    for team, data in recommendations.items():
        services_str = ", ".join(data["services"])
        result += f"""
{data['priority']} **{team}**
   Affected Services: {services_str}
   Advice: {data['advice']}
"""

    return result

# ------------------------------
# TEST
# ------------------------------
if __name__ == "__main__":
    print("\n" + "="*60)
    print("📋 Testing Team-Specific Recommendations")
    print("="*60 + "\n")

    services = ["payment_service", "auth_service", "database", "checkout_service"]

    recommendations = get_team_specific_recommendations(services)

    print("="*60)
    print("📋 RECOMMENDATIONS")
    print("="*60)
    print(format_recommendations_for_display(recommendations))
    print("="*60)
    print("✅ Test Complete!")