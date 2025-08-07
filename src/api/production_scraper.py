#!/usr/bin/env python3
"""
Production OLX Scraper - Server-side script
Simple interface for server-side scraping operations
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..config_loader import get_config
from ..scraper.olx_workflow import OLXWorkflowOrchestrator, run_brand_workflow, run_main_page_workflow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProductionScraper:
    """Production scraper for server-side operations"""
    
    def __init__(self):
        self.config = get_config()
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
    
    async def scrape_brand(self, brand: str, max_cars: int = None, upload_images: bool = None) -> Dict[str, Any]:
        """Scrape a specific brand"""
        max_cars = max_cars or self.config.get_max_cars_default()
        upload_images = upload_images if upload_images is not None else self.config.is_image_upload_enabled()
        
        logger.info(f"🚀 Starting brand scraping: {brand}")
        logger.info(f"📊 Max cars: {max_cars}, Images: {'✅' if upload_images else '❌'}")
        
        try:
            result = await run_brand_workflow(
                brand_name=brand,
                max_cars=max_cars,
                upload_images=upload_images
            )
            
            # Save results
            self._save_results(f"brand_{brand}", result)
            
            return {
                'success': result['success'],
                'brand': brand,
                'stats': result['stats'],
                'error_count': len(result.get('errors', [])),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Brand scraping failed for {brand}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'brand': brand,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
    
    async def scrape_main_page(self, max_cars: int = None, upload_images: bool = None) -> Dict[str, Any]:
        """Scrape main cars page"""
        max_cars = max_cars or self.config.get_max_cars_default()
        upload_images = upload_images if upload_images is not None else self.config.is_image_upload_enabled()
        
        logger.info(f"🚀 Starting main page scraping")
        logger.info(f"📊 Max cars: {max_cars}, Images: {'✅' if upload_images else '❌'}")
        
        try:
            result = await run_main_page_workflow(
                max_cars=max_cars,
                upload_images=upload_images
            )
            
            # Save results
            self._save_results("main_page", result)
            
            return {
                'success': result['success'],
                'source': 'main_page',
                'stats': result['stats'],
                'error_count': len(result.get('errors', [])),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Main page scraping failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'source': 'main_page',
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
    
    async def scrape_custom_url(self, url: str, max_cars: int = None, max_pages: int = None, upload_images: bool = None) -> Dict[str, Any]:
        """Scrape a custom OLX URL"""
        max_cars = max_cars or self.config.get_max_cars_default()
        max_pages = max_pages or self.config.get_max_pages_default()
        upload_images = upload_images if upload_images is not None else self.config.is_image_upload_enabled()
        
        logger.info(f"🚀 Starting custom URL scraping: {url}")
        logger.info(f"📊 Max cars: {max_cars}, Max pages: {max_pages}, Images: {'✅' if upload_images else '❌'}")
        
        orchestrator = OLXWorkflowOrchestrator(
            database_url=self.config.get_database_url(),
            cookies_file=self.config.get_cookies_file()
        )
        
        try:
            await orchestrator.initialize()
            
            result = await orchestrator.run_complete_workflow(
                page_url=url,
                max_pages=max_pages,
                max_cars=max_cars,
                upload_images=upload_images
            )
            
            # Save results
            url_name = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
            self._save_results(f"custom_{url_name}", result)
            
            return {
                'success': result['success'],
                'source': 'custom_url',
                'url': url,
                'stats': result['stats'],
                'error_count': len(result.get('errors', [])),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Custom URL scraping failed for {url}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'source': 'custom_url',
                'url': url,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
        finally:
            await orchestrator.close()
    
    def _save_results(self, prefix: str, result: Dict[str, Any]):
        """Save scraping results to file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.results_dir / f"{prefix}_results_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"📁 Results saved to: {filename}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save results: {e}")
    
    def get_recent_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent scraping results"""
        try:
            result_files = sorted(
                self.results_dir.glob("*_results_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            results = []
            for file_path in result_files[:limit]:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    results.append({
                        'filename': file_path.name,
                        'created_at': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                        'success': data.get('success', False),
                        'stats': data.get('stats', {}),
                        'source': data.get('source', 'unknown')
                    })
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to read result file {file_path}: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to get recent results: {e}")
            return []

# Server-friendly functions
async def quick_brand_scrape(brand: str, max_cars: int = 10) -> Dict[str, Any]:
    """Quick brand scraping for server use"""
    scraper = ProductionScraper()
    return await scraper.scrape_brand(brand, max_cars)

async def quick_main_scrape(max_cars: int = 10) -> Dict[str, Any]:
    """Quick main page scraping for server use"""
    scraper = ProductionScraper()
    return await scraper.scrape_main_page(max_cars)

# Simple CLI for testing
async def main():
    """Simple CLI for testing"""
    import sys
    
    if len(sys.argv) < 2:
        print("📋 OLX Production Scraper")
        print("Usage:")
        print("  python production_scraper.py brand <brand_name> [max_cars]")
        print("  python production_scraper.py main [max_cars]")
        print("  python production_scraper.py url <olx_url> [max_cars]")
        print("")
        print("Examples:")
        print("  python production_scraper.py brand bmw 15")
        print("  python production_scraper.py main 10")
        print("  python production_scraper.py url https://www.olx.pt/carros-motos-e-barcos/carros/audi/ 20")
        return
    
    scraper = ProductionScraper()
    command = sys.argv[1].lower()
    
    try:
        if command == "brand" and len(sys.argv) >= 3:
            brand = sys.argv[2]
            max_cars = int(sys.argv[3]) if len(sys.argv) > 3 else None
            result = await scraper.scrape_brand(brand, max_cars)
            
        elif command == "main":
            max_cars = int(sys.argv[2]) if len(sys.argv) > 2 else None
            result = await scraper.scrape_main_page(max_cars)
            
        elif command == "url" and len(sys.argv) >= 3:
            url = sys.argv[2]
            max_cars = int(sys.argv[3]) if len(sys.argv) > 3 else None
            result = await scraper.scrape_custom_url(url, max_cars)
            
        else:
            print("❌ Invalid command or missing arguments")
            return
        
        # Print summary
        print(f"\n{'='*50}")
        if result['success']:
            stats = result.get('stats', {})
            print(f"✅ Scraping completed successfully!")
            print(f"📊 Cars saved to DB: {stats.get('cars_saved_to_db', 0)}")
            print(f"👥 Users created: {stats.get('users_created', 0)}")
            print(f"🔗 Users linked: {stats.get('users_linked', 0)}")
            print(f"🖼️ Images uploaded: {stats.get('images_uploaded', 0)}")
            print(f"⏱️ Duration: {stats.get('duration_seconds', 0):.1f}s")
        else:
            print(f"❌ Scraping failed")
            print(f"Error: {result.get('error', 'Unknown error')}")
            print(f"Errors: {result.get('error_count', 0)}")
        
    except KeyboardInterrupt:
        print("\n🛑 Scraping interrupted by user")
    except Exception as e:
        print(f"❌ Scraping error: {e}")

if __name__ == "__main__":
    asyncio.run(main())