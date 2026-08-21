import os
import json
import logging
import re
import ast
from typing import List, Dict, Any
from dotenv import load_dotenv
import groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# As of Aug 2026, these are confirmed active.
MODELS = [
    "openai/gpt-oss-120b",          # highest quality
    "qwen/qwen3.6-27b",             # solid fallback
    "canopylabs/orpheus-v1-english",# extra (needs terms acceptance)
]

MAX_RETRIES = 1
MAX_TOKENS = 800  # increased to avoid truncation

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
# Robust JSON extraction with automatic truncation repair
# -------------------------------------------------------------------
def extract_json(text: str) -> Dict[str, Any]:
    """Extract a JSON object from mixed text, repairing truncated JSON if needed."""
    # 1. Try to find a ```json ... ``` code block
    code_block = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if code_block:
        json_str = code_block.group(1)
    else:
        # 2. Try to find the first '{' and match braces (nested support)
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
        # If braces are unbalanced, we'll try to repair by appending missing '}'
        if end is None:
            # Count open braces minus close braces
            open_braces = text[start:].count('{') - text[start:].count('}')
            if open_braces > 0:
                # Append the missing closing braces
                json_str = text[start:] + '}' * open_braces
                logger.warning(f"Repaired truncated JSON by adding {open_braces} closing brace(s).")
            else:
                raise ValueError("Unbalanced braces and cannot repair")
        else:
            json_str = text[start:end]

    # 3. Try to parse as JSON (handles double quotes)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # 4. If that fails, try ast.literal_eval (handles single quotes)
        try:
            return ast.literal_eval(json_str)
        except (SyntaxError, ValueError):
            # 5. Last resort: replace single quotes with double quotes
            try:
                fixed = json_str.replace("'", '"')
                return json.loads(fixed)
            except:
                raise ValueError(f"Could not parse JSON from: {json_str[:100]}...")

# -------------------------------------------------------------------
# Main AI function
# -------------------------------------------------------------------
def generate_insights(services: List[str], business_impact: int) -> Dict[str, Any]:
    if not GROQ_API_KEY:
        logger.warning("❌ GROQ_API_KEY not set – using fallback.")
        return _fallback_insights(services, business_impact)

    prompt = f"""You are a senior DevOps engineer reviewing a deployment change.

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
                # Try with response_format if the model supports it
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=MAX_TOKENS,
                        response_format={"type": "json_object"}  # some models support this
                    )
                except Exception:
                    # Fallback: some models don't support response_format
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=MAX_TOKENS,
                    )
                content = response.choices[0].message.content

                # Debug: print raw response
                print("\n" + "=" * 60)
                print(f"📝 RAW RESPONSE from {model}:")
                print(content)
                print("=" * 60 + "\n")

                # Extract JSON from the response
                data = extract_json(content)

                # Ensure required keys exist
                required = ["simulation", "severity", "rollback", "validation"]
                for key in required:
                    if key not in data:
                        data[key] = _fallback_insights(services, business_impact)[key]

                # Add token usage
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

if __name__ == "__main__":
    test_services = ["payment_service", "checkout_service", "login_service"]
    result = generate_insights(test_services, 100)
    print("\n✅ FINAL RESULT:")
    print(json.dumps(result, indent=2))