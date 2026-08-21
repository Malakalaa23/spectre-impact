"""
Package Checker for Spectre Impact
Maps pip names to correct import names
"""

import importlib
import sys

# Mapping: pip name → import name
PACKAGE_MAP = {
    "groq": "groq",
    "pydantic": "pydantic",
    "python-dotenv": "dotenv",     # pip name → import name
    "PyYAML": "yaml",              # pip name → import name
    "networkx": "networkx",
    "matplotlib": "matplotlib",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "httpx": "httpx",
    "PyGithub": "github",          # pip name → import name
    "streamlit": "streamlit",
    "pandas": "pandas",
    "plotly": "plotly",
    "pytest": "pytest",
}

DESCRIPTIONS = {
    "groq": "Groq API client",
    "pydantic": "Data validation",
    "python-dotenv": "Environment variables",
    "PyYAML": "YAML parsing",
    "networkx": "Graph analysis",
    "matplotlib": "Visualization",
    "fastapi": "Web framework",
    "uvicorn": "ASGI server",
    "httpx": "HTTP client",
    "PyGithub": "GitHub API",
    "streamlit": "Dashboard framework",
    "pandas": "Data manipulation",
    "plotly": "Interactive charts",
    "pytest": "Testing framework",
}

def check_package(pip_name, import_name):
    """Try to import the package using its import name."""
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False

def main():
    print("\n" + "="*60)
    print("📦 SPECTRE IMPACT - PACKAGE CHECKER (FIXED)")
    print("="*60 + "\n")
    
    installed = []
    missing = []
    
    for pip_name, import_name in PACKAGE_MAP.items():
        desc = DESCRIPTIONS.get(pip_name, "")
        if check_package(pip_name, import_name):
            installed.append(pip_name)
            print(f"✅ {pip_name:15} - {desc}")
        else:
            missing.append(pip_name)
            print(f"❌ {pip_name:15} - {desc} (MISSING)")
    
    print("\n" + "="*60)
    print(f"✅ Installed: {len(installed)}/{len(PACKAGE_MAP)}")
    print(f"❌ Missing:   {len(missing)}/{len(PACKAGE_MAP)}")
    print("="*60)
    
    if missing:
        print("\n📋 Install missing packages with:")
        print(f"pip install {' '.join(missing)}")
    else:
        print("\n🎉 All packages are installed!")
    
    print("\n" + "="*60)
    print("✅ Check Complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()