#!/usr/bin/env python3
"""
Railway Web API for OLX Scraper
FastAPI web service for running scraping jobs
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

from ..config_loader import get_config
from .production_scraper import ProductionScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="OLX Car Scraper API",
    description="Production API for scraping Portuguese car listings from OLX.pt",
    version="1.0.0"
)

# Global scraper instance
scraper = ProductionScraper()

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "OLX Car Scraper API",
        "version": "1.0.0",
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "health": "/health",
            "scrape_brand": "/scrape/brand/{brand}?max_cars=10",
            "scrape_main": "/scrape/main?max_cars=10",
            "scrape_url": "/scrape/url?url={url}&max_cars=10",
            "results": "/results",
            "config": "/config"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway"""
    config = get_config()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database_configured": bool(config.get_database_url()),
        "s3_configured": bool(config.get('aws_s3.bucket_name')),
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "development")
    }

@app.get("/config")
async def get_config_info():
    """Get configuration information (non-sensitive)"""
    config = get_config()
    
    return {
        "scraper": {
            "headless": config.is_headless_enabled(),
            "max_cars_default": config.get_max_cars_default(),
            "max_pages_default": config.get_max_pages_default(),
            "phone_extraction": config.is_phone_extraction_enabled()
        },
        "workflow": {
            "image_upload": config.is_image_upload_enabled(),
            "user_management": config.get('workflow.enable_user_management', True)
        },
        "s3": {
            "bucket_configured": bool(config.get('aws_s3.bucket_name')),
            "region": config.get('aws_s3.region')
        },
        "database": {
            "configured": bool(config.get_database_url())
        }
    }

@app.post("/scrape/brand/{brand}")
async def scrape_brand(brand: str, background_tasks: BackgroundTasks, max_cars: int = 10, upload_images: bool = True):
    """Scrape a specific car brand"""
    if max_cars > 50:
        raise HTTPException(status_code=400, detail="max_cars cannot exceed 50")
    
    try:
        logger.info(f"🚀 API request: scrape brand {brand}, max_cars={max_cars}")
        
        result = await scraper.scrape_brand(
            brand=brand.lower(),
            max_cars=max_cars,
            upload_images=upload_images
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Brand scraping error: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@app.post("/scrape/main")
async def scrape_main_page(background_tasks: BackgroundTasks, max_cars: int = 10, upload_images: bool = True):
    """Scrape main cars page"""
    if max_cars > 50:
        raise HTTPException(status_code=400, detail="max_cars cannot exceed 50")
    
    try:
        logger.info(f"🚀 API request: scrape main page, max_cars={max_cars}")
        
        result = await scraper.scrape_main_page(
            max_cars=max_cars,
            upload_images=upload_images
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Main page scraping error: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@app.post("/scrape/url")
async def scrape_custom_url(
    background_tasks: BackgroundTasks, 
    url: str, 
    max_cars: int = 10, 
    max_pages: int = 2,
    upload_images: bool = True
):
    """Scrape a custom OLX URL"""
    if max_cars > 50:
        raise HTTPException(status_code=400, detail="max_cars cannot exceed 50")
    
    if not url.startswith("https://www.olx.pt"):
        raise HTTPException(status_code=400, detail="URL must be from OLX.pt")
    
    try:
        logger.info(f"🚀 API request: scrape custom URL {url}")
        
        result = await scraper.scrape_custom_url(
            url=url,
            max_cars=max_cars,
            max_pages=max_pages,
            upload_images=upload_images
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Custom URL scraping error: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@app.get("/results")
async def get_recent_results(limit: int = 10):
    """Get recent scraping results"""
    try:
        results = scraper.get_recent_results(limit=min(limit, 50))
        return {
            "results": results,
            "total": len(results),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Error getting results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}")

# Railway startup
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = "0.0.0.0"
    
    logger.info(f"🚀 Starting OLX Scraper API on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info",
        reload=False
    )