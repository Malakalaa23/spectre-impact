"""
Project Diagnostic Check
Run this to see what's built and what's missing
"""

import os
import sys
import importlib
from pathlib import Path

# ANSI colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def check_file_exists(filepath):
    """Check if a file exists in the project."""
    full_path = Path(filepath)
    exists = full_path.exists()
    if exists:
        size = full_path.stat().st_size
        print_success(f"{filepath} ({size} bytes)")
    else:
        print_error(f"{filepath} (MISSING)")
    return exists

def check_import(module_name):
    """Check if a module can be imported."""
    try:
        importlib.import_module(module_name)
        print_success(f"{module_name} (imported successfully)")
        return True
    except ImportError as e:
        print_error(f"{module_name} (import failed: {e})")
        return False
    except Exception as e:
        print_error(f"{module_name} (error: {e})")
        return False

def check_directory_exists(dirpath):
    """Check if a directory exists."""
    full_path = Path(dirpath)
    exists = full_path.exists() and full_path.is_dir()
    if exists:
        print_success(f"{dirpath}/ (directory exists)")
    else:
        print_error(f"{dirpath}/ (MISSING)")
    return exists

def test_ai_agent():
    """Test if the AI agent works."""
    print_info("Testing AI Agent...")
    try:
        from ai_agent_groq import generate_insights
        result = generate_insights(["payment_service", "login_service"], 85)
        if result and "severity" in result:
            print_success(f"AI Agent working! (Severity: {result['severity']})")
            return True
        else:
            print_error("AI Agent returned invalid response")
            return False
    except ImportError as e:
        print_error(f"AI Agent import failed: {e}")
        return False
    except Exception as e:
        print_error(f"AI Agent test failed: {e}")
        return False

def test_multi_level_summary():
    """Test if multi-level summaries work."""
    print_info("Testing Multi-Level Summaries...")
    try:
        from multi_level_summary import generate_full_report
        result = generate_full_report(["payment_service", "login_service"], 85)
        if result and "devops" in result and "executive" in result:
            print_success("Multi-Level Summaries working!")
            return True
        else:
            print_error("Multi-Level Summaries returned invalid response")
            return False
    except ImportError as e:
        print_error(f"Multi-Level Summaries import failed: {e}")
        return False
    except Exception as e:
        print_error(f"Multi-Level Summaries test failed: {e}")
        return False

def check_env_file():
    """Check if .env file has required keys."""
    env_path = Path(".env")
    if not env_path.exists():
        print_error(".env file MISSING")
        return False
    
    try:
        with open(env_path, 'r') as f:
            content = f.read()
        
        checks = {
            "GROQ_API_KEY": "GROQ_API_KEY=" in content,
        }
        
        all_passed = True
        for key, found in checks.items():
            if found:
                print_success(f"{key} found in .env")
            else:
                print_warning(f"{key} NOT found in .env (might need to be added)")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print_error(f"Error reading .env: {e}")
        return False

def main():
    print_header("SPECTRE IMPACT - PROJECT DIAGNOSTIC CHECK")
    
    # =========================================================
    # 1. CHECK CORE FILES (Your Part - Malak)
    # =========================================================
    print_header("📂 1. CORE FILES (Malak's AI Agent)")
    
    core_files = [
        "ai_agent_groq.py",
        "multi_level_summary.py",
        "integration.py",
        "test_ai_agent.py",
        "config.py",
        "main.py"
    ]
    
    for file in core_files:
        check_file_exists(file)
    
    # =========================================================
    # 2. CHECK ADVANCED FILES
    # =========================================================
    print_header("📂 2. ADVANCED FEATURES")
    
    advanced_files = [
        "advanced/__init__.py",
        "advanced/post_incident_report.py",
        "advanced/rca_simulator.py",
        "advanced/team_recommendations.py",
        "advanced/change_detector.py"
    ]
    
    advanced_exists = False
    for file in advanced_files:
        if check_file_exists(file):
            advanced_exists = True
    
    # =========================================================
    # 3. CHECK DATA FILES
    # =========================================================
    print_header("📂 3. DATA FILES")
    
    data_files = [
        "data/dependency_map.yaml",
        "data/business_map.yaml"
    ]
    
    for file in data_files:
        check_file_exists(file)
    
    # =========================================================
    # 4. CHECK ENVIRONMENT
    # =========================================================
    print_header("🔧 4. ENVIRONMENT")
    
    check_env_file()
    
    # =========================================================
    # 5. CHECK IMPORTS
    # =========================================================
    print_header("📦 5. MODULE IMPORTS")
    
    required_modules = [
        "groq",
        "pydantic",
        "yaml",
        "fastapi",
        "uvicorn",
        "streamlit"
    ]
    
    for module in required_modules:
        check_import(module)
    
    # =========================================================
    # 6. TEST AI AGENT FUNCTIONALITY
    # =========================================================
    print_header("🧠 6. AI AGENT FUNCTIONALITY")
    
    test_ai_agent()
    test_multi_level_summary()
    
    # =========================================================
    # 7. SUMMARY
    # =========================================================
    print_header("📊 SUMMARY")
    
    print_info(f"Project Path: {os.getcwd()}")
    print_info(f"Python Version: {sys.version}")
    
    # Check if virtual environment is active
    if sys.prefix != sys.base_prefix:
        print_success(f"Virtual Environment: {sys.prefix}")
    else:
        print_warning("No virtual environment detected")
    
    print("\n" + "="*60)
    print("✅ Diagnostic Complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()