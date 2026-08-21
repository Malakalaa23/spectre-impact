"""
AI Agent for Spectre Impact – uses Groq API to generate insights.
Location: C:/Users/Malak/spectre-impact/ai_agent_groq.py
"""

import os
import json
import logging
import re
from typing import List, Dict, Any
from dotenv import load_dotenv
import groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Models that are currently active and support JSON output
MODELS = [
    "openai/gpt-oss-120b",      # best quality
    "qwen/qwen3.6-27b",         # good fallback
]

MAX_RETRIES = 1
MAX_TOKENS = 800

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Deterministic fallback
# -------------------------------------------------------------------
def _fallback_insights(services: List[str], impact: int) -> Dict[str, Any]:
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

# -------------------------------------------------------------------
# JSON extraction with truncation repair
# -------------------------------------------------------------------
def extract_json(text: str) -> Dict[str, Any]:
    """Extract a JSON object from mixed text, repairing truncated JSON if needed."""
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found")
    
    stack = 0
    end = None
    for i, ch in enumerate(text[start:], start):
        if ch == '{':
            stack += 1
        elif ch == '}':
            stack -= 1
            if stack == 0:
                end = i + 1
                break
    
    if end is None:
        open_braces = text[start:].count('{') - text[start:].count('}')
        if open_braces > 0:
            json_str = text[start:] + '}' * open_braces
            logger.warning(f"Repaired truncated JSON by adding {open_braces} closing brace(s).")
        else:
            raise ValueError("Unbalanced braces and cannot repair")
    else:
        json_str = text[start:end]
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        raise ValueError(f"Could not parse JSON from: {json_str[:100]}...")

# -------------------------------------------------------------------
# Main AI function for PR analysis
# -------------------------------------------------------------------
def generate_insights(services: List[str], business_impact: int) -> Dict[str, Any]:
    if not GROQ_API_KEY:
        logger.warning("❌ GROQ_API_KEY not set – using fallback.")
        return _fallback_insights(services, business_impact)

    prompt = f"""
You are a senior DevOps engineer reviewing a deployment change.

Affected services: {', '.join(services) if services else 'None detected'}
Business impact: {business_impact}% (estimated)

Provide a structured analysis in **JSON ONLY**. The JSON must have these exact keys:
- "simulation": a concise what‑if scenario (string)
- "severity": one of "Low", "Medium", "High", or "Critical"
- "rollback": a list of concrete rollback steps (list of strings)
- "validation": a list of verification commands (list of strings)

Do not include any other text, markdown, or explanation. Only valid JSON.
Example:
{{"simulation": "Database fails → checkout fails.", "severity": "High", "rollback": ["git revert", "restart"], "validation": ["curl /health"]}}
"""

    client = groq.Groq(api_key=GROQ_API_KEY)

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

# -------------------------------------------------------------------
# NEW: Inline AI prompt for commit analysis
# -------------------------------------------------------------------
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
        client = groq.Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=400,
        )
        content = response.choices[0].message.content
        
        suggestions = json.loads(content)
        
        filtered = []
        for s in suggestions:
            if s.get("severity", "").lower() in ("high", "critical"):
                filtered.append(s)
        
        return filtered[:5]
        
    except Exception as e:
        print(f"❌ AI inline suggestion failed: {e}")
        return []

# -------------------------------------------------------------------
# Quick test
# -------------------------------------------------------------------
if __name__ == "__main__":
    result = generate_insights(["payment_service", "checkout_service"], 80)
    print(json.dumps(result, indent=2))