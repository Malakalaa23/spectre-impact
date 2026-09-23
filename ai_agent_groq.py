"""
AI Agent for Spectre Impact â€“ Uses Multiple AI Models + RAG for Code Review.
Ensemble system cross-validates outputs for higher accuracy.
"""

import os
import json
import logging
import re
from typing import List, Dict, Any, Optional
from collections import Counter
from dotenv import load_dotenv
import groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# -------------------------------------------------------------------
# Model Configuration
# -------------------------------------------------------------------
MODELS = [
    "openai/gpt-oss-120b",              # Primary - most reliable for JSON
    "openai/gpt-oss-20b",               # Validator 1 - smaller, faster
    "qwen/qwen3.8-27b",                 # Validator 2 - good quality
]

MAX_RETRIES = 2
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
        "simulation": f"âš ï¸ [AI Offline] Manual review needed for {', '.join(services) if services else 'unknown_service'}.",
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
        "overall_verdict": "Manual Review Required",
        "confidence": 0,
        "disagreements": []
    }


def extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON from mixed text with robust error handling."""
    if not text:
        raise ValueError("Empty text")
    
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    
    if not text:
        raise ValueError("Empty text after cleaning")
    
    start = text.find('{')
    end = text.rfind('}')
    
    if start == -1 or end == -1:
        raise ValueError("No JSON object found")
    
    json_str = text[start:end+1]
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        open_braces = json_str.count('{') - json_str.count('}')
        if open_braces > 0:
            json_str = json_str + '}' * open_braces
            return json.loads(json_str)
        raise e


# -------------------------------------------------------------------
# RAG System â€“ Business Context Retrieval
# -------------------------------------------------------------------

class RAGSystem:
    """RAG system for business-specific context."""
    
    def __init__(self, knowledge_file: str = None):
        self.business_knowledge = {}
        if knowledge_file and os.path.exists(knowledge_file):
            self._load_from_file(knowledge_file)
        else:
            self._load_default_knowledge()
    
    def _load_from_file(self, knowledge_file: str):
        try:
            with open(knowledge_file, 'r', encoding='utf-8') as f:
                self.business_knowledge = json.load(f)
            logger.info(f"âœ… Loaded business knowledge from {knowledge_file}")
        except Exception as e:
            logger.warning(f"âš ï¸ Failed to load knowledge file: {e}")
            self._load_default_knowledge()
    
    def _load_default_knowledge(self):
        self.business_knowledge = {
            "payment_service": {
                "criticality": "HIGHEST",
                "description": "Handles all financial transactions",
                "compliance": "PCI-DSS compliant",
                "rollback_policy": "Must rollback within 5 minutes",
                "owner": "Payment Team",
                "revenue_impact": "$1M/day",
                "sla": "99.99% uptime required",
            },
            "login_service": {
                "criticality": "HIGH",
                "description": "Handles user authentication",
                "compliance": "SOC2 compliant",
                "rollback_policy": "Rollback within 15 minutes",
                "owner": "Auth Team",
                "revenue_impact": "Prevents user access",
                "sla": "99.95% uptime required",
            },
            "checkout_service": {
                "criticality": "HIGH",
                "description": "Orchestrates order placement",
                "compliance": "GDPR compliant",
                "rollback_policy": "Rollback within 10 minutes",
                "owner": "Checkout Team",
                "revenue_impact": "$500K/day",
                "sla": "99.95% uptime required",
            },
            "customer_database": {
                "criticality": "CRITICAL",
                "description": "Core customer data store",
                "compliance": "GDPR + PCI-DSS",
                "rollback_policy": "Requires database migration rollback",
                "owner": "Data Team",
                "revenue_impact": "All services depend on this",
                "sla": "99.99% uptime required",
            },
            "profile_service": {
                "criticality": "MEDIUM",
                "description": "Manages user profiles",
                "compliance": "GDPR compliant",
                "rollback_policy": "Rollback within 30 minutes",
                "owner": "Profile Team",
                "revenue_impact": "Limited",
                "sla": "99.9% uptime required",
            }
        }
        logger.info("âœ… Loaded default business knowledge")
    
    def retrieve_context(self, services: List[str]) -> str:
        if not services:
            return "No services affected."
        
        context_parts = []
        for service in services:
            if service in self.business_knowledge:
                info = self.business_knowledge[service]
                context_parts.append(
                    f"- {service}: {info['description']}\n"
                    f"  Criticality: {info['criticality']}\n"
                    f"  Compliance: {info['compliance']}\n"
                    f"  Rollback Policy: {info['rollback_policy']}\n"
                    f"  Owner: {info['owner']}\n"
                    f"  Revenue Impact: {info.get('revenue_impact', 'Unknown')}\n"
                    f"  SLA: {info.get('sla', 'Unknown')}"
                )
            else:
                matched = False
                for key in self.business_knowledge:
                    if key in service or service in key:
                        info = self.business_knowledge[key]
                        context_parts.append(
                            f"- {service} â†’ {key}: {info['description']}\n"
                            f"  Criticality: {info['criticality']}\n"
                            f"  Compliance: {info['compliance']}\n"
                            f"  Rollback Policy: {info['rollback_policy']}\n"
                            f"  Owner: {info['owner']}"
                        )
                        matched = True
                        break
                if not matched:
                    context_parts.append(f"- {service}: No business context available")
        
        return "\n".join(context_parts) if context_parts else "No business context available."


# -------------------------------------------------------------------
# Consensus Engine
# -------------------------------------------------------------------

class ConsensusEngine:
    """Aggregates and validates multiple AI reviews."""
    
    @staticmethod
    def _flatten_and_stringify(items: list) -> list:
        result = []
        for item in items:
            if isinstance(item, list):
                result.extend(ConsensusEngine._flatten_and_stringify(item))
            elif isinstance(item, dict):
                result.append(json.dumps(item, sort_keys=True))
            else:
                result.append(str(item))
        return result
    
    @staticmethod
    def merge_reviews(reviews: List[Dict]) -> Dict:
        if not reviews:
            return {
                "code_quality": "Unable to Analyze",
                "bugs_found": [],
                "security_issues": [],
                "missing_tests": [],
                "suggestions": [],
                "overall_verdict": "Manual Review Required",
                "confidence": 0,
                "disagreements": []
            }
        
        all_bugs = []
        all_security = []
        all_tests = []
        all_suggestions = []
        all_verdicts = []
        all_quality = []
        
        for review in reviews:
            if not isinstance(review, dict):
                continue
                
            bugs = review.get("bugs_found", [])
            if isinstance(bugs, list):
                all_bugs.extend(ConsensusEngine._flatten_and_stringify(bugs))
            
            security = review.get("security_issues", [])
            if isinstance(security, list):
                all_security.extend(ConsensusEngine._flatten_and_stringify(security))
            
            tests = review.get("missing_tests", [])
            if isinstance(tests, list):
                all_tests.extend(ConsensusEngine._flatten_and_stringify(tests))
            
            suggestions = review.get("suggestions", [])
            if isinstance(suggestions, list):
                all_suggestions.extend(ConsensusEngine._flatten_and_stringify(suggestions))
            
            verdict = review.get("overall_verdict", "Unknown")
            if verdict:
                all_verdicts.append(str(verdict))
            
            quality = review.get("code_quality", "Unknown")
            if quality:
                all_quality.append(str(quality))
        
        if not all_bugs and not all_security and not all_tests and not all_suggestions:
            return {
                "code_quality": "Unable to Analyze",
                "bugs_found": [],
                "security_issues": [],
                "missing_tests": [],
                "suggestions": [],
                "overall_verdict": "Manual Review Required",
                "confidence": 0,
                "disagreements": []
            }
        
        bug_counts = Counter(all_bugs)
        security_counts = Counter(all_security)
        test_counts = Counter(all_tests)
        suggestion_counts = Counter(all_suggestions)
        
        num_reviews = len(reviews)
        
        high_conf_bugs = [b for b, count in bug_counts.items() if count == num_reviews]
        medium_conf_bugs = [b for b, count in bug_counts.items() if count >= 2 and count < num_reviews]
        low_conf_bugs = [b for b, count in bug_counts.items() if count == 1]
        
        merged_bugs = []
        for bug in high_conf_bugs:
            merged_bugs.append(f"âœ… {bug}")
        for bug in medium_conf_bugs:
            merged_bugs.append(f"ðŸŸ¡ {bug}")
        for bug in low_conf_bugs:
            merged_bugs.append(f"ðŸ”„ {bug}")
        
        if all_verdicts:
            verdict_counts = Counter(all_verdicts)
            final_verdict = verdict_counts.most_common(1)[0][0]
        else:
            final_verdict = "Manual Review Required"
        
        confidence = 0
        if len(set(all_verdicts)) == 1:
            confidence += 30
        if len(set(all_quality)) == 1:
            confidence += 20
        if high_conf_bugs:
            confidence += min(len(high_conf_bugs) * 10, 30)
        if medium_conf_bugs:
            confidence += min(len(medium_conf_bugs) * 5, 20)
        
        if all_quality:
            quality_counts = Counter(all_quality)
            code_quality = quality_counts.most_common(1)[0][0]
        else:
            code_quality = "Unknown"
        
        return {
            "code_quality": code_quality,
            "bugs_found": merged_bugs,
            "security_issues": list(security_counts.keys()) if security_counts else [],
            "missing_tests": list(test_counts.keys()) if test_counts else [],
            "suggestions": list(suggestion_counts.keys()) if suggestion_counts else [],
            "overall_verdict": final_verdict,
            "confidence": min(confidence, 100),
            "disagreements": []
        }


# -------------------------------------------------------------------
# Core AI Functions
# -------------------------------------------------------------------

def generate_insights(services: List[str], business_impact: int) -> Dict[str, Any]:
    """Generate deployment insights using AI."""
    if not GROQ_API_KEY:
        logger.warning("âŒ GROQ_API_KEY not set â€“ using fallback.")
        return _fallback_insights(services, business_impact)

    prompt = f"""
You are a senior DevOps engineer reviewing a deployment change.

Affected services: {', '.join(services) if services else 'None detected'}
Business impact: {business_impact}% (estimated)

Provide a structured analysis in JSON ONLY. The JSON must have these exact keys:
- "simulation": a concise whatâ€‘if scenario (string)
- "severity": one of "Low", "Medium", "High", or "Critical"
- "rollback": a list of concrete rollback steps (list of strings)
- "validation": a list of verification commands (list of strings)

Do not include any other text. Only valid JSON.
Example: {{"simulation": "Database fails -> checkout fails.", "severity": "High", "rollback": ["git revert", "restart"], "validation": ["curl /health"]}}
"""

    client = groq.Groq(api_key=GROQ_API_KEY, timeout=TIMEOUT)

    for model in MODELS:
        try:
            logger.info(f"ðŸ§  Trying model {model} for insights")
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

            logger.info(f"âœ… Insights generated with model: {model}")
            return data

        except Exception as e:
            logger.error(f"âŒ Insight error with {model}: {e}")

    logger.warning("ðŸ’¾ All models failed for insights â€“ using fallback.")
    return _fallback_insights(services, business_impact)


def generate_inline_suggestions(diff: str, changed_files: list, affected_services: list) -> list:
    """Generate lineâ€‘specific suggestions based on the commit diff."""
    if not affected_services or affected_services == ["unknown_service"]:
        return []
    
    if not diff or len(diff) < 10:
        return []
    
    if len(diff) > 8000:
        diff = diff[:8000] + "\n... (truncated)"
    
    prompt = f"""
You are a senior DevOps engineer reviewing code changes in realâ€‘time.

Changed files: {', '.join(changed_files)}
Affected services: {', '.join(affected_services)}

Here is the diff:
{diff}

Analyze these changes and return lineâ€‘specific feedback in JSON format:
[
    {{
        "file": "path/to/file.py",
        "line": 42,
        "severity": "High",
        "suggestion": "Add null check"
    }}
]

RULES:
1. ONLY return suggestions that are operational risks
2. Severity: ONLY use "High" or "Critical"
3. Ignore style issues
4. Return ONLY valid JSON array
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
        
        cleaned_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL)
        cleaned_content = cleaned_content.strip()
        
        try:
            suggestions = json.loads(cleaned_content)
            if isinstance(suggestions, list):
                return _filter_suggestions(suggestions)
        except json.JSONDecodeError:
            pass
        
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
        logger.error(f"âŒ Inline suggestion failed: {e}")
        return []


def _filter_suggestions(suggestions: list) -> list:
    filtered = []
    for s in suggestions:
        if isinstance(s, dict):
            severity = s.get("severity", "").lower()
            if severity in ("high", "critical"):
                filtered.append(s)
    return filtered[:5]


def generate_code_review_with_rag(diff_content: str, changed_files: list, services: list) -> dict:
    """Generate code review with multiple AI models + RAG enrichment."""
    if not diff_content or len(diff_content) < 10:
        return {
            "code_quality": "No Code to Review",
            "bugs_found": [],
            "security_issues": [],
            "missing_tests": [],
            "suggestions": ["No code changes detected to review."],
            "overall_verdict": "No Code Changes",
            "confidence": 100,
            "disagreements": []
        }
    
    if len(diff_content) > 10000:
        diff_content = diff_content[:10000] + "\n... (truncated)"
    
    rag = RAGSystem()
    business_context = rag.retrieve_context(services)
    
    services_str = ", ".join(services) if services else "None detected"
    changed_files_str = ", ".join(changed_files)
    
    prompt = f"""You are a senior code reviewer evaluating a Pull Request. Your job is to find REAL bugs, security issues, and logic errors in the code.

CHANGED FILES:
{changed_files_str}

AFFECTED SERVICES:
{services_str}

BUSINESS CONTEXT (Use this to assess impact):
{business_context}

DIFF CONTENT:
{diff_content}

EVALUATE THE CODE ITSELF (not just dependencies):
1. Are there syntax errors?
2. Are there logic errors (null pointers, undefined variables, off-by-one)?
3. Are there security vulnerabilities (hardcoded secrets, SQL injection, XSS)?
4. Are tests missing for changed functions?
5. Given the business context, how critical are these issues?

OUTPUT FORMAT. Return ONLY valid JSON. No other text.

{{
    "code_quality": "Good",
    "bugs_found": [],
    "security_issues": [],
    "missing_tests": [],
    "suggestions": [],
    "overall_verdict": "Approved"
}}"""

    if not GROQ_API_KEY:
        logger.warning("âŒ GROQ_API_KEY not set")
        return _fallback_code_review()

    client = groq.Groq(api_key=GROQ_API_KEY, timeout=TIMEOUT)
    reviews = []
    
    for model in MODELS:
        try:
            logger.info(f"ðŸ§  Running model: {model}")
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800,
                response_format={"type": "json_object"} if model == MODELS[0] else None
            )
            content = response.choices[0].message.content
            
            data = extract_json(content)
            
            required_keys = ["code_quality", "bugs_found", "security_issues", "missing_tests", "suggestions", "overall_verdict"]
            for key in required_keys:
                if key not in data:
                    data[key] = []
            
            reviews.append(data)
            logger.info(f"âœ… Model {model} completed successfully")
            
        except Exception as e:
            logger.error(f"âŒ Model {model} failed: {e}")
    
    if not reviews:
        return _fallback_code_review()
    
    consensus = ConsensusEngine.merge_reviews(reviews)
    consensus["business_context"] = business_context
    consensus["models_used"] = len(reviews)
    consensus["confidence"] = consensus.get("confidence", 0)
    
    logger.info(f"ðŸ” Consensus review: {consensus['overall_verdict']} (confidence: {consensus['confidence']}%)")
    
    return consensus


def generate_code_review(diff_content: str, changed_files: list, services: list) -> dict:
    """Backward-compatible wrapper for generate_code_review_with_rag."""
    return generate_code_review_with_rag(diff_content, changed_files, services)


# -------------------------------------------------------------------
# Quick test
# -------------------------------------------------------------------
if __name__ == "__main__":
    print("ðŸ§ª Testing Multi-Model + RAG Code Review...")
    print("=" * 60)
    
    test_diff = """
def process_payment(amount, user):
    if not user:
        raise ValueError("User cannot be None")
    return user.balance - amount
"""
    test_files = ["app.py"]
    test_services = ["payment_service", "customer_database"]
    
    result = generate_code_review(test_diff, test_files, test_services)
    print(json.dumps(result, indent=2))
    
    print("\nðŸ§ª Testing generate_insights...")
    insights = generate_insights(["payment_service", "login_service"], 80)
    print(json.dumps(insights, indent=2))
