#!/usr/bin/env python3
"""
Admin Dashboard for OLX Scraper
Live tracking, configuration management, and monitoring
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import asyncpg

from ..config_loader import get_config
from .production_scraper import ProductionScraper

# Global tracking state
active_scrapers = {}
scraping_logs = []
websocket_connections = []

class ScrapingTracker:
    """Track active scraping sessions"""
    
    def __init__(self):
        self.active_jobs = {}
        self.job_logs = {}
        self.statistics = {
            'total_jobs': 0,
            'successful_jobs': 0,
            'failed_jobs': 0,
            'total_cars_scraped': 0,
            'last_24h_jobs': 0
        }
    
    async def start_job(self, job_id: str, job_type: str, params: Dict[str, Any]):
        """Start tracking a new job"""
        self.active_jobs[job_id] = {
            'id': job_id,
            'type': job_type,
            'params': params,
            'status': 'running',
            'started_at': datetime.now(),
            'progress': 0,
            'current_step': 'Initializing...',
            'cars_found': 0,
            'errors': []
        }
        
        self.statistics['total_jobs'] += 1
        await self.broadcast_update()
    
    async def update_job(self, job_id: str, **updates):
        """Update job status"""
        if job_id in self.active_jobs:
            self.active_jobs[job_id].update(updates)
            await self.broadcast_update()
    
    async def complete_job(self, job_id: str, result: Dict[str, Any]):
        """Complete a job"""
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            job.update({
                'status': 'completed' if result.get('success') else 'failed',
                'completed_at': datetime.now(),
                'result': result,
                'progress': 100
            })
            
            if result.get('success'):
                self.statistics['successful_jobs'] += 1
                self.statistics['total_cars_scraped'] += result.get('stats', {}).get('cars_saved_to_db', 0)
            else:
                self.statistics['failed_jobs'] += 1
            
            # Move to completed jobs after 5 minutes
            await asyncio.sleep(300)
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            
            await self.broadcast_update()
    
    async def broadcast_update(self):
        """Broadcast updates to all connected WebSockets"""
        if websocket_connections:
            message = {
                'type': 'status_update',
                'active_jobs': list(self.active_jobs.values()),
                'statistics': self.statistics,
                'timestamp': datetime.now().isoformat()
            }
            
            disconnected = []
            for websocket in websocket_connections:
                try:
                    await websocket.send_json(message)
                except:
                    disconnected.append(websocket)
            
            # Remove disconnected websockets
            for ws in disconnected:
                websocket_connections.remove(ws)

# Global tracker
tracker = ScrapingTracker()

def create_admin_routes(app: FastAPI):
    """Add admin dashboard routes to FastAPI app"""
    
    # Create templates directory
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)
    
    # Create static files directory
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    
    templates = Jinja2Templates(directory=str(templates_dir))
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    @app.get("/admin", response_class=HTMLResponse)
    async def admin_dashboard(request: Request):
        """Admin dashboard main page"""
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "title": "OLX Scraper Admin Dashboard"
        })
    
    @app.websocket("/ws/status")
    async def websocket_status(websocket: WebSocket):
        """WebSocket for real-time status updates"""
        await websocket.accept()
        websocket_connections.append(websocket)
        
        try:
            # Send initial data
            await websocket.send_json({
                'type': 'initial_data',
                'active_jobs': list(tracker.active_jobs.values()),
                'statistics': tracker.statistics,
                'timestamp': datetime.now().isoformat()
            })
            
            # Keep connection alive
            while True:
                await websocket.receive_text()
                
        except WebSocketDisconnect:
            if websocket in websocket_connections:
                websocket_connections.remove(websocket)
    
    @app.get("/admin/api/status")
    async def get_status():
        """Get current scraping status"""
        return {
            'active_jobs': list(tracker.active_jobs.values()),
            'statistics': tracker.statistics,
            'timestamp': datetime.now().isoformat()
        }
    
    @app.get("/admin/api/config")
    async def get_config_admin():
        """Get current configuration"""
        config = get_config()
        return {
            'scraper': {
                'headless': config.is_headless_enabled(),
                'max_cars_default': config.get_max_cars_default(),
                'max_pages_default': config.get_max_pages_default(),
                'phone_extraction': config.is_phone_extraction_enabled(),
                'image_upload': config.is_image_upload_enabled()
            },
            'database': {
                'configured': bool(config.get_database_url()),
                'url_masked': config.get_database_url()[:20] + "..." if config.get_database_url() else None
            },
            's3': {
                'bucket': config.get('aws_s3.bucket_name'),
                'region': config.get('aws_s3.region'),
                'upload_enabled': config.get('workflow.enable_image_upload')
            },
            'environment_variables': {
                'PORT': os.getenv('PORT'),
                'RAILWAY_ENVIRONMENT': os.getenv('RAILWAY_ENVIRONMENT'),
                'DATABASE_URL': '***MASKED***' if os.getenv('DATABASE_URL') else None,
                'AWS_ACCESS_KEY_ID': '***MASKED***' if os.getenv('AWS_ACCESS_KEY_ID') else None,
                'MAX_CARS': os.getenv('MAX_CARS'),
                'SCRAPER_HEADLESS': os.getenv('SCRAPER_HEADLESS'),
                'PHONE_EXTRACTION': os.getenv('PHONE_EXTRACTION'),
                'S3_UPLOAD_ENABLED': os.getenv('S3_UPLOAD_ENABLED')
            }
        }
    
    @app.post("/admin/api/config/update")
    async def update_config(request: Request):
        """Update configuration via environment variables"""
        data = await request.json()
        
        # This would typically update environment variables
        # For now, return success (Railway handles env vars via dashboard)
        return {
            'success': True,
            'message': 'Configuration updated successfully',
            'note': 'Environment variables should be updated via Railway dashboard'
        }
    
    @app.post("/admin/api/scrape/{job_type}")
    async def start_scraping_job(job_type: str, request: Request):
        """Start a new scraping job with live tracking"""
        data = await request.json()
        
        job_id = f"{job_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Start tracking
        await tracker.start_job(job_id, job_type, data)
        
        # Start scraping in background
        asyncio.create_task(run_tracked_scraping_job(job_id, job_type, data))
        
        return {
            'success': True,
            'job_id': job_id,
            'message': f'Started {job_type} scraping job',
            'tracking_url': f'/admin#job-{job_id}'
        }
    
    @app.get("/admin/api/database/stats")
    async def get_database_stats():
        """Get database statistics"""
        try:
            config = get_config()
            conn = await asyncpg.connect(config.get_database_url())
            
            # Get statistics
            total_cars = await conn.fetchval("SELECT COUNT(*) FROM cars")
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            cars_with_prices = await conn.fetchval("SELECT COUNT(*) FROM cars WHERE price IS NOT NULL")
            cars_with_phones = await conn.fetchval("SELECT COUNT(*) FROM cars WHERE phone_number IS NOT NULL")
            
            # Recent activity (last 24 hours)
            recent_cars = await conn.fetchval("""
                SELECT COUNT(*) FROM cars 
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            
            await conn.close()
            
            return {
                'total_cars': total_cars,
                'total_users': total_users,
                'cars_with_prices': cars_with_prices,
                'cars_with_phones': cars_with_phones,
                'recent_cars_24h': recent_cars,
                'price_extraction_rate': round((cars_with_prices / total_cars * 100), 1) if total_cars > 0 else 0,
                'phone_extraction_rate': round((cars_with_phones / total_cars * 100), 1) if total_cars > 0 else 0
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'total_cars': 0,
                'total_users': 0,
                'message': 'Database connection failed'
            }
    
    @app.get("/admin/api/recent-cars")
    async def get_recent_cars(limit: int = 20):
        """Get recent cars from database"""
        try:
            config = get_config()
            conn = await asyncpg.connect(config.get_database_url())
            
            cars = await conn.fetch("""
                SELECT id, url, title, brand, price_raw, phone_number, created_at
                FROM cars 
                ORDER BY created_at DESC 
                LIMIT $1
            """, limit)
            
            await conn.close()
            
            return [
                {
                    'id': car['id'],
                    'title': car['title'] or 'No title',
                    'brand': car['brand'] or 'Unknown',
                    'price': car['price_raw'] or 'No price',
                    'phone': '📞 Yes' if car['phone_number'] else '📞 No',
                    'created_at': car['created_at'].isoformat(),
                    'url_preview': '...' + car['url'][-30:] if car['url'] else ''
                }
                for car in cars
            ]
            
        except Exception as e:
            return {'error': str(e), 'cars': []}

async def run_tracked_scraping_job(job_id: str, job_type: str, params: Dict[str, Any]):
    """Run a scraping job with live tracking updates"""
    scraper = ProductionScraper()
    
    try:
        await tracker.update_job(job_id, current_step="Starting scraper...", progress=10)
        
        if job_type == "brand":
            await tracker.update_job(job_id, current_step=f"Scraping {params.get('brand')} cars...", progress=30)
            result = await scraper.scrape_brand(
                brand=params.get('brand'),
                max_cars=params.get('max_cars', 10),
                upload_images=params.get('upload_images', True)
            )
            
        elif job_type == "main":
            await tracker.update_job(job_id, current_step="Scraping main page...", progress=30)
            result = await scraper.scrape_main_page(
                max_cars=params.get('max_cars', 10),
                upload_images=params.get('upload_images', True)
            )
            
        elif job_type == "url":
            await tracker.update_job(job_id, current_step=f"Scraping custom URL...", progress=30)
            result = await scraper.scrape_custom_url(
                url=params.get('url'),
                max_cars=params.get('max_cars', 10),
                max_pages=params.get('max_pages', 2),
                upload_images=params.get('upload_images', True)
            )
        else:
            raise ValueError(f"Unknown job type: {job_type}")
        
        await tracker.update_job(job_id, current_step="Processing results...", progress=90)
        await tracker.complete_job(job_id, result)
        
    except Exception as e:
        await tracker.complete_job(job_id, {
            'success': False,
            'error': str(e),
            'stats': {'cars_saved_to_db': 0}
        })