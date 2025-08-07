#!/usr/bin/env python3
"""
Main entry point for OLX Scraper
Handles both CLI and web service modes
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Determine if we should run as web service or CLI
if __name__ == "__main__":
    # Check if we have web service arguments or PORT env var
    if os.getenv("PORT") or "--web" in sys.argv:
        # Run as web service
        from api.main import app
        import uvicorn
        
        port = int(os.getenv("PORT", 8000))
        host = "0.0.0.0"
        
        print(f"🚀 Starting OLX Scraper Web Service on {host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info")
        
    else:
        # Run as CLI
        from api.production_scraper import main
        import asyncio
        
        asyncio.run(main())