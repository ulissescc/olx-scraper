#!/usr/bin/env python3
"""
Simplified startup script for Railway deployment
"""

import os
import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

def main():
    try:
        import uvicorn
        print("✅ uvicorn imported successfully")
        
        # Import our app
        from api.main import app
        print("✅ FastAPI app imported successfully")
        
        # Get port from environment
        port = int(os.getenv("PORT", 8000))
        host = "0.0.0.0"
        
        print(f"🚀 Starting OLX Scraper API on {host}:{port}")
        print(f"📊 Environment: {os.getenv('RAILWAY_ENVIRONMENT', 'local')}")
        print(f"🗄️ Database: {'✅ Configured' if os.getenv('DATABASE_URL') else '❌ Not configured'}")
        print(f"☁️ S3: {'✅ Configured' if os.getenv('AWS_ACCESS_KEY_ID') else '❌ Not configured'}")
        
        # Start the server
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print(f"Python path: {sys.path}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Files in current directory: {os.listdir('.')}")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Startup error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()