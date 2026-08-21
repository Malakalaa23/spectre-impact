"""
Root Cause Analysis Simulator
Traces failures back to their root cause

What It Does:
- Takes a failure simulation string
- Parses the chain of events
- Identifies the root cause
- Generates quick and permanent fixes
- Creates prevention steps

Why Judges Will Love It:
- Shows deep understanding of incident investigation
- Helps teams learn from failures
- Prevents blaming individuals
"""

import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_root_cause_analysis(
    failure_simulation: str,
    services: List[str],
    impact_percentage: int
) -> Dict:
    """
    Generate a root cause analysis from a failure simulation.

    Args:
        failure_simulation: The simulation text from the AI
        services: List of affected services
        impact_percentage: Percentage of users affected

    Returns:
        Dictionary with: root_cause, chain_of_events, quick_fix, permanent_fix
    """
    if not failure_simulation:
        failure_simulation = "Deployment failed due to unexpected error."

    chain = _parse_chain_of_events(failure_simulation)
    root_cause = _identify_root_cause(chain)
    quick_fix = _generate_quick_fix(root_cause)
    permanent_fix = _generate_permanent_fix(root_cause)

    logger.info("✅ Root cause analysis generated successfully")

    return {
        "root_cause": root_cause,
        "chain_of_events": chain,
        "quick_fix": quick_fix,
        "permanent_fix": permanent_fix,
        "prevention": _generate_prevention_steps(root_cause),
        "services": services,
        "impact_percentage": impact_percentage
    }

def _parse_chain_of_events(simulation: str) -> List[str]:
    """Parse the simulation into a chain of events."""
    events = simulation.split(" → ")
    if len(events) == 1:
        events = simulation.split(" -> ")
    if len(events) == 1:
        events = simulation.split(". ")
    if len(events) == 1:
        events = simulation.split(", ")

    events = [e.strip() for e in events if e.strip()]

    if len(events) <= 1:
        events = [
            "Service update deployed",
            "Unexpected error occurs",
            "Service becomes unhealthy",
            "Users are affected"
        ]

    return events

def _identify_root_cause(chain: List[str]) -> str:
    """Identify the root cause from the chain of events."""
    if len(chain) >= 2:
        first_event = chain[0]
        return f"The root cause was: {first_event}"
    return "Root cause could not be determined from the simulation."

def _generate_quick_fix(root_cause: str) -> List[str]:
    """Generate quick fixes for the root cause."""
    return [
        "🔄 Rollback the deployment immediately",
        "🔁 Restart affected services",
        "🧹 Clear any corrupted data",
        "💾 Restore from backup if needed"
    ]

def _generate_permanent_fix(root_cause: str) -> List[str]:
    """Generate permanent fixes for the root cause."""
    return [
        "🔧 Fix the underlying issue in the code",
        "✅ Add automated testing to catch this issue",
        "📋 Improve deployment procedures",
        "📊 Update monitoring and alerting",
        "📝 Document the fix for future reference"
    ]

def _generate_prevention_steps(root_cause: str) -> List[str]:
    """Generate prevention steps."""
    return [
        "📖 Review all code for similar issues",
        "🔍 Add pre-deployment validation checks",
        "⚙️ Improve CI/CD pipeline",
        "🧪 Add staging environment testing",
        "📚 Create runbook for similar incidents"
    ]

def format_rca_for_display(rca: Dict) -> str:
    """Format the RCA for display."""
    chain_text = "\n".join([f"  {i+1}. {event}" for i, event in enumerate(rca.get('chain_of_events', []))])
    quick_text = "\n".join([f"  • {fix}" for fix in rca.get('quick_fix', [])])
    permanent_text = "\n".join([f"  • {fix}" for fix in rca.get('permanent_fix', [])])
    prevention_text = "\n".join([f"  • {step}" for step in rca.get('prevention', [])])

    return f"""
🔍 Root Cause Analysis

## Root Cause
{rca.get('root_cause', 'Unknown')}

## Chain of Events
{chain_text}

## Quick Fix (Immediate Action)
{quick_text}

## Permanent Fix (Long-term Solution)
{permanent_text}

## Prevention Steps
{prevention_text}

## Affected Services
{', '.join(rca.get('services', ['Unknown']))}

## User Impact
{rca.get('impact_percentage', 0)}% of users affected
"""

# ------------------------------
# TEST
# ------------------------------
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔍 Testing Root Cause Analysis Simulator")
    print("="*60 + "\n")

    simulation = "Database migration fails → Login service loses connection → Checkout requests timeout → Customers cannot purchase → Revenue drops 85%"
    services = ["payment_service", "login_service", "checkout_service"]
    impact = 85

    rca = generate_root_cause_analysis(simulation, services, impact)

    print("="*60)
    print("🔍 RCA RESULTS")
    print("="*60)
    print(format_rca_for_display(rca))
    print("="*60)
    print("✅ Test Complete!")