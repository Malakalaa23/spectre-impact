"""
Check if all required packages are installed.
Run with: python check_packages.py
"""

import importlib
import sys

# List of packages to check: (import_name, pip_name)
PACKAGES = [
    ("streamlit", "streamlit"),
    ("pandas", "pandas"),
    ("plotly", "plotly"),
    ("requests", "requests"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("streamlit_autorefresh", "streamlit-autorefresh"),
]

def check_package(import_name, pip_name):
    """Check if a package is installed and return its version."""
    try:
        module = importlib.import_module(import_name)
        version = getattr(module, "__version__", "unknown")
        return True, version
    except ImportError:
        return False, None

def main():
    print("\n" + "="*60)
    print("📦 PACKAGE CHECKER")
    print("="*60 + "\n")
    
    installed = []
    missing = []
    
    for import_name, pip_name in PACKAGES:
        is_installed, version = check_package(import_name, pip_name)
        if is_installed:
            print(f"✅ {pip_name:25} version {version}")
            installed.append(pip_name)
        else:
            print(f"❌ {pip_name:25} NOT INSTALLED")
            missing.append(pip_name)
    
    print("\n" + "="*60)
    print(f"✅ Installed: {len(installed)}/{len(PACKAGES)}")
    print(f"❌ Missing:   {len(missing)}/{len(PACKAGES)}")
    print("="*60)
    
    if missing:
        print("\n📋 Install missing packages with:")
        print(f"pip install {' '.join(missing)}")
    else:
        print("\n🎉 All packages are installed!")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()