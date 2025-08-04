#!/usr/bin/env python3
"""
Dashboard CLI - Launch the price change dashboard
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Launch the FastAPI dashboard using UV."""
    project_root = Path(__file__).parent.parent
    
    print("🚀 Starting Price Change Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:8000")
    print("")
    
    try:
        # Run uvicorn through UV
        cmd = [
            "uv", "run", "uvicorn", 
            "dashboard.app:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ]
        
        subprocess.run(cmd, cwd=project_root, check=True)
        
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting dashboard: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ UV not found. Please make sure UV is installed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
