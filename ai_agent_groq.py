"""
AI Agent for Spectre Impact – uses Groq API to generate insights.
Tries multiple models in order. Falls back to deterministic response if all fail.
"""

import os
import json
import logging
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import groq

load_dotenv()

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Models in order of preference
# openai/gpt-oss-120b is most reliable for JSON output
MODELS = [
    "openai/gpt-oss-120b",      # most reliable for JSON
    "qwen/qwen3.6-27b",         # fallback
]

MAX_RETRIES = 1
MAX_TOKENS = 800
TIMEOUT = 30.0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------
def _fallback_insights(services: List[str], impact: int) -> Dict[str, Any]:
    """Deterministic fallback when AI is unavailable."""
    severity = "High" if impact > 70 else "Medium" if impact > 30 else "Low"
    return {
        "simulation": f"⚠️ [AI Offline] Manual review needed for {', '.join(services) if services else 'unknown_service'}.",
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
        ],
        "tokens_used": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    }


def _fallback_code_review() -> dict:
    """Fallback response when code review fails."""
    return {
        "code_quality": "Unable to Analyze",
        "bugs_found": [],
        "security_issues": [],
        "missing_tests": [],
        "suggestions": ["AI code review failed. Manual review recommended."],
        "overall_verdict": "Manual Review Required"
    }


def extract_json(text: str) -> Dict[str, Any]:
    """
    Extract a JSON object from mixed text, repairing truncated JSON if needed.
    
    Handles:
    - <think> tags
    - Extra text before/after JSON
    - Truncated JSON (adds missing braces)
    - Markdown code blocks
    """
    # Remove <think> tags and content
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # Remove markdown code blocks
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    text = text.strip()
    
    if not text:
        raise ValueError("Empty text after cleaning")
    
    # Find the first '{' and last '}'
    start = text.find('{')
    end = text.rfind('}')
    
    if start == -1 or end == -1:
        raise ValueError("No JSON object found")
    
    json_str = text[start:end+1]
    
    # Try to parse
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Count open braces and close if needed
        open_braces = json_str.count('{') - json_str.count('}')
        if open_braces > 0:
            json_str = json_str + '}' * open_braces
            return json.loads(json_str)
        raise e


# -------------------------------------------------------------------
# Main AI Functions
# -------------------------------------------------------------------
def generate_insights(services: List[str], business_impact: int) -> Dict[str, Any]:
    """Generate deployment insights using AI."""
    if not GROQ_API_KEY:
        logger.warning("❌ GROQ_API_KEY not set – using fallback.")
        return _fallback_insights(services, business_impact)

    prompt = f"""
You are a senior DevOps engineer reviewing a deployment change.

Affected services: {', '.join(services) if services else 'None detected'}
Business impact: {business_impact}% (estimated)

Provide a structured analysis in JSON ONLY. The JSON must have these exact keys:
- "simulation": a concise what‑if scenario (string)
- "severity": one of "Low", "Medium", "High", or "Critical"
- "rollback": a list of concrete rollback steps (list of strings)
- "validation": a list of verification commands (list of strings)

Do not include any other text. Only valid JSON.
Example: {{"simulation": "Database fails -> checkout fails.", "severity": "High", "rollback": ["git revert", "restart"], "validation": ["curl /health"]}}
"""

    client = groq.Groq(api_key=GROQ_API_KEY, timeout=TIMEOUT)

    for model in MODELS:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"🧠 Trying model {model} (attempt {attempt}) for: {services}")
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=MAX_TOKENS,
                        response_format={"type": "json_object"}
                    )
                except Exception:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=MAX_TOKENS,
                    )
                
                content = response.choices[0].message.content
                data = extract_json(content)

                # Ensure all required keys exist
                required = ["simulation", "severity", "rollback", "validation"]
                for key in required:
                    if key not in data:
                        data[key] = _fallback_insights(services, business_impact)[key]

                tokens_used = {
                    "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "output_tokens": getattr(response.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0)
                }
                data["tokens_used"] = tokens_used

                logger.info(f"✅ AI insights generated with model: {model}")
                return data

            except Exception as e:
                logger.error(f"❌ AI error with {model} (attempt {attempt}): {e}")

        logger.info(f"🔄 Model {model} failed, trying next...")

    logger.warning("💾 All AI models failed – using fallback.")
    return _fallback_insights(services, business_impact)


def generate_inline_suggestions(diff: str, changed_files: list, affected_services: list) -> list:
    """
    Generate line‑specific suggestions based on the commit diff.
    Returns: [
        {"file": "app.py", "line": 42, "severity": "High", "suggestion": "Add null check"}
    ]
    """
    if not affected_services or affected_services == ["unknown_service"]:
        return []
    
    if not diff or len(diff) < 10:
        return []
    
    if len(diff) > 8000:
        diff = diff[:8000] + "\n... (truncated)"
    
    prompt = f"""
You are a senior DevOps engineer reviewing code changes in real‑time.

Changed files: {', '.join(changed_files)}
Affected services: {', '.join(affected_services)}

Here is the diff:
{diff}

Analyze these changes and return line‑specific feedback in JSON format:
[
    {{
        "file": "path/to/file.py",
        "line": 42,
        "severity": "High",
        "suggestion": "Add null check"
    }}
]

RULES:
1. ONLY return suggestions that are operational risks:
   - Database migrations (backward compatibility)
   - API changes (breaking changes)  
   - Infrastructure changes (Terraform/K8s)
   - Critical service dependencies
2. Severity: ONLY use "High" or "Critical" (no Low/Medium for inline)
3. Ignore style issues, formatting, or minor code quality concerns
4. Return ONLY valid JSON array – no other text
"""
    
    try:
        client = groq.Groq(api_key=GROQ_API_KEY, timeout=TIMEOUT)
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=400,
        )
        raw_content = response.choices[0].message.content
        
        # Remove <think> tags
        cleaned_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL)
        cleaned_content = cleaned_content.strip()
        
        # Try to parse JSON
        try:
            suggestions = json.loads(cleaned_content)
            if isinstance(suggestions, list):
                return _filter_suggestions(suggestions)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON array
        match = re.search(r'\[\s*\{.*\}\s*\]', cleaned_content, re.DOTALL)
        if match:
            try:
                suggestions = json.loads(match.group())
                if isinstance(suggestions, list):
                    return _filter_suggestions(suggestions)
            except json.JSONDecodeError:
                pass
        
        return []
    
    except Exception as e:
        logger.error(f"❌ Inline suggestion failed: {e}")
        return []


def _filter_suggestions(suggestions: list) -> list:
    """Filter to only High/Critical suggestions, limit to 5."""
    filtered = []
    for s in suggestions:
        if isinstance(s, dict):
            severity = s.get("severity", "").lower()
            if severity in ("high", "critical"):
                filtered.append(s)
    return filtered[:5]


def generate_code_review(diff_content: str, changed_files: list, services: list) -> dict:
    """
    Generate a code review that evaluates the code itself, not just dependencies.
    This is the feature that makes Spectre Impact truly valuable.
    """
    if not diff_content or len(diff_content) < 10:
        return {
            "code_quality": "No Code to Review",
            "bugs_found": [],
            "security_issues": [],
            "missing_tests": [],
            "suggestions": ["No code changes detected to review."],
            "overall_verdict": "No Code Changes"
        }
    
    if len(diff_content) > 10000:
        diff_content = diff_content[:10000] + "\n... (truncated)"
    
    services_str = ", ".join(services) if services else "None detected"
    changed_files_str = ", ".join(changed_files)
    
    prompt = f"""
You are a senior code reviewer evaluating a Pull Request. Your job is to find REAL bugs, security issues, and logic errors in the code.

CHANGED FILES:
{changed_files_str}

AFFECTED SERVICES:
{services_str}

DIFF CONTENT:
{diff_content}

EVALUATE THE CODE ITSELF (not just dependencies):
1. Are there syntax errors?
2. Are there logic errors (null pointers, undefined variables, off-by-one)?
3. Are there security vulnerabilities (hardcoded secrets, SQL injection, XSS)?
4. Are tests missing for changed functions?

OUTPUT FORMAT. Return ONLY valid JSON. No other text.

{{
    "code_quality": "Good",
    "bugs_found": [],
    "security_issues": [],
    "missing_tests": [],
    "suggestions": [],
    "overall_verdict": "Approved"
}}
"""

    try:
        client = groq.Groq(api_key=GROQ_API_KEY, timeout=TIMEOUT)
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        
        # Extract JSON
        data = extract_json(content)
        
        # Ensure all required keys exist
        required_keys = ["code_quality", "bugs_found", "security_issues", "missing_tests", "suggestions", "overall_verdict"]
        for key in required_keys:
            if key not in data:
                data[key] = []
        
        return data
        
    except Exception as e:
        logger.error(f"❌ Code review failed: {e}")
        return _fallback_code_review()


# -------------------------------------------------------------------
# Quick test
# -------------------------------------------------------------------
if __name__ == "__main__":
    print("🧪 Testing generate_insights...")
    result = generate_insights(["payment_service", "checkout_service"], 80)
    print(json.dumps(result, indent=2))
    
    print("\n" + "=" * 60)
    print("🧪 Testing generate_code_review...")
    print("=" * 60)
    test_diff = """
def process_payment(amount, user):
    if not user:
        raise ValueError("User cannot be None")
    return user.balance - amount
"""
    test_files = ["app.py"]
    test_services = ["payment_service"]
    review = generate_code_review(test_diff, test_files, test_services)
    print(json.dumps(review, indent=2))