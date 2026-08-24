"""
AI Agent for Spectre Impact – Uses Multiple AI Models + RAG for Code Review.
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
# Primary model first, then validators in order of preference
# All models listed here are confirmed working as of August 2026
MODELS = [
    "openai/gpt-oss-120b",              # Primary - most reliable for JSON
    "openai/gpt-oss-20b",               # Validator 1 - smaller, faster
    "qwen/qwen3.6-27b",                 # Validator 2 - good quality
]

MAX_RETRIES = 2
MAX_TOKENS = 800
TIMEOUT = 30.0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# RAG System – Business Context Retrieval
# -------------------------------------------------------------------

class RAGSystem:
    """
    RAG (Retrieval-Augmented Generation) System for Spectre Impact.
    
    WHAT IT DOES:
    =============
    The RAG system stores and retrieves business-specific knowledge about
    your services. When the AI reviews code, it uses this context to make
    better, more relevant recommendations.
    
    HOW IT WORKS:
    =============
    1. Store business knowledge about each service:
       - Criticality (HIGHEST, HIGH, MEDIUM, LOW)
       - Description of what the service does
       - Compliance requirements (PCI-DSS, GDPR, SOC2)
       - Rollback policies
       - Team ownership
    
    2. When a PR changes a service, the RAG system retrieves
       the relevant business context and injects it into the AI prompt.
    
    3. The AI uses this context to give more accurate recommendations.
    
    WHY IT MATTERS:
    ===============
    Without RAG:
    - AI says: "The function has a null pointer bug."
    - Developer thinks: "Okay, I'll fix it later."
    
    With RAG:
    - AI says: "The function has a null pointer bug. This is the payment
                service that processes $1M/day. It is PCI-DSS compliant.
                Fix this immediately. The Payment Team owns this service."
    - Developer thinks: "Oh! This is critical. I need to fix this NOW."
    
    IN PRODUCTION:
    ==============
    The RAG system can be extended with:
    - Vector database (Chroma, Pinecone, Weaviate) for semantic search
    - Company-specific knowledge bases
    - Historical incident data
    - Service-level agreements (SLAs)
    """
    
    def __init__(self, knowledge_file: str = None):
        self.business_knowledge = {}
        if knowledge_file and os.path.exists(knowledge_file):
            self._load_from_file(knowledge_file)
        else:
            self._load_default_knowledge()
    
    def _load_from_file(self, knowledge_file: str):
        """Load business knowledge from a JSON file."""
        try:
            with open(knowledge_file, 'r', encoding='utf-8') as f:
                self.business_knowledge = json.load(f)
            logger.info(f"✅ Loaded business knowledge from {knowledge_file}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load knowledge file: {e}")
            self._load_default_knowledge()
    
    def _load_default_knowledge(self):
        """Load default business knowledge."""
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
        logger.info("✅ Loaded default business knowledge")
    
    def retrieve_context(self, services: List[str]) -> str:
        """
        Retrieve business context for affected services.
        
        Args:
            services: List of service names to retrieve context for.
        
        Returns:
            A formatted string with business context for each service.
        """
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
                # Try fuzzy matching
                matched = False
                for key in self.business_knowledge:
                    if key in service or service in key:
                        info = self.business_knowledge[key]
                        context_parts.append(
                            f"- {service} → {key}: {info['description']}\n"
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
    """
    Aggregates and validates multiple AI reviews.
    
    HOW IT WORKS:
    =============
    1. Each AI model generates a review independently.
    2. The Consensus Engine collects all reviews.
    3. It counts how many models agree on each finding.
    4. It assigns confidence levels:
       - ✅ = ALL models agree (High confidence)
       - 🟡 = 2+ models agree (Medium confidence)
       - 🔄 = Only 1 model found this (Low confidence)
    5. It merges everything into a single final review.
    
    WHY IT MATTERS:
    ===============
    - Reduces hallucinations: If 3 models agree, it's likely true.
    - Builds trust: Developers can see confidence levels.
    - Flags uncertainty: Low-confidence items need manual review.
    """
    
    @staticmethod
    def _flatten_and_stringify(items: list) -> list:
        """Flatten nested lists and convert all items to strings."""
        result = []
        for item in items:
            if isinstance(item, list):
                result.extend(ConsensusEngine._flatten_and_stringify(item))
            elif isinstance(item, dict):
                # Convert dict to a string representation
                result.append(json.dumps(item, sort_keys=True))
            else:
                result.append(str(item))
        return result
    
    @staticmethod
    def merge_reviews(reviews: List[Dict]) -> Dict:
        """
        Merge multiple reviews into a consensus.
        Items present in ALL reviews → High confidence (✅)
        Items present in ≥2 reviews → Medium confidence (🟡)
        Items present in 1 review → Low confidence (🔄)
        """
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
        
        # Aggregate findings
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
        
        # If no valid data was collected, return fallback
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
        
        # Count occurrences
        bug_counts = Counter(all_bugs)
        security_counts = Counter(all_security)
        test_counts = Counter(all_tests)
        suggestion_counts = Counter(all_suggestions)
        
        num_reviews = len(reviews)
        
        # Determine confidence levels
        high_conf_bugs = [b for b, count in bug_counts.items() if count == num_reviews]
        medium_conf_bugs = [b for b, count in bug_counts.items() if count >= 2 and count < num_reviews]
        low_conf_bugs = [b for b, count in bug_counts.items() if count == 1]
        
        # Merge with confidence indicators
        merged_bugs = []
        for bug in high_conf_bugs:
            merged_bugs.append(f"✅ {bug}")
        for bug in medium_conf_bugs:
            merged_bugs.append(f"🟡 {bug}")
        for bug in low_conf_bugs:
            merged_bugs.append(f"🔄 {bug}")
        
        # Determine final verdict
        if all_verdicts:
            verdict_counts = Counter(all_verdicts)
            final_verdict = verdict_counts.most_common(1)[0][0]
        else:
            final_verdict = "Manual Review Required"
        
        # Calculate confidence score (0-100)
        confidence = 0
        
        # Based on agreement between models
        if len(set(all_verdicts)) == 1:
            confidence += 30
        if len(set(all_quality)) == 1:
            confidence += 20
        
        # Based on bug agreement
        if high_conf_bugs:
            confidence += min(len(high_conf_bugs) * 10, 30)
        if medium_conf_bugs:
            confidence += min(len(medium_conf_bugs) * 5, 20)
        
        # Determine code quality (most common)
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
# Helper Functions
# -------------------------------------------------------------------

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
    
    # Remove <think> tags
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
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Try to repair truncated JSON
        open_braces = json_str.count('{') - json_str.count('}')
        if open_braces > 0:
            json_str = json_str + '}' * open_braces
            return json.loads(json_str)
        raise e


# -------------------------------------------------------------------
# Core AI Functions
# -------------------------------------------------------------------

def generate_code_review_with_rag(diff_content: str, changed_files: list, services: list) -> dict:
    """
    Generate a code review using multiple AI models + RAG enrichment.
    This is the advanced version with cross-validation.
    """
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
    
    # Step 1: Get business context (RAG)
    rag = RAGSystem()
    business_context = rag.retrieve_context(services)
    
    services_str = ", ".join(services) if services else "None detected"
    changed_files_str = ", ".join(changed_files)
    
    # Step 2: Build the prompt with RAG context
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
        logger.warning("❌ GROQ_API_KEY not set")
        return _fallback_code_review()

    client = groq.Groq(api_key=GROQ_API_KEY, timeout=TIMEOUT)
    reviews = []
    
    # Step 3: Run multiple models
    for model in MODELS:
        try:
            logger.info(f"🧠 Running model: {model}")
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
            logger.info(f"✅ Model {model} completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Model {model} failed: {e}")
    
    # Step 4: If no models worked, return fallback
    if not reviews:
        return _fallback_code_review()
    
    # Step 5: Use Consensus Engine to merge reviews
    consensus = ConsensusEngine.merge_reviews(reviews)
    
    # Step 6: Add RAG context to the output
    consensus["business_context"] = business_context
    consensus["models_used"] = len(reviews)
    consensus["confidence"] = consensus.get("confidence", 0)
    
    logger.info(f"🔍 Consensus review: {consensus['overall_verdict']} (confidence: {consensus['confidence']}%)")
    
    return consensus


# Keep backward compatibility
def generate_code_review(diff_content: str, changed_files: list, services: list) -> dict:
    """
    Backward-compatible wrapper for generate_code_review_with_rag.
    """
    return generate_code_review_with_rag(diff_content, changed_files, services)


# -------------------------------------------------------------------
# Quick test
# -------------------------------------------------------------------
if __name__ == "__main__":
    print("🧪 Testing Multi-Model + RAG Code Review...")
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