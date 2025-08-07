#!/usr/bin/env python3
"""
Complete OLX Scraping Workflow
Orchestrates: Scraping → User Management → Image Processing → Database Storage

Full workflow: OLX scrape → phone extraction → user creation/linking → S3 image upload → PostgreSQL storage
"""

import asyncio
import asyncpg
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys

# Import our components
from .fixed_enhanced_scraper import FixedEnhancedOLXScraper
from ..database.postgres_user_manager import PostgreSQLUserManager, UserManagerContext
from .enhanced_data_transformer import EnhancedCarDataTransformer, transform_enhanced_scraped_data
from ..services.s3_service import S3Service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('olx_workflow.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OLXWorkflowOrchestrator:
    """Complete OLX scraping workflow orchestrator"""
    
    def __init__(self, 
                 database_url: str = "postgresql://car_user:dev_password@localhost:5432/car_marketplace_dev",
                 cookies_file: str = "cookies.txt"):
        """Initialize workflow orchestrator"""
        self.database_url = database_url
        self.cookies_file = cookies_file if Path(cookies_file).exists() else None
        
        # Initialize components
        self.scraper = FixedEnhancedOLXScraper(
            use_selenium=True,
            headless=True,
            cookies_file=self.cookies_file
        )
        self.user_manager = PostgreSQLUserManager(database_url)
        self.data_transformer = EnhancedCarDataTransformer()
        self.s3_service = S3Service()
        
        # Database connection pool
        self.db_pool = None
        
        # Stats tracking
        self.session_stats = {
            'started_at': datetime.now(),
            'cars_scraped': 0,
            'cars_saved_to_db': 0,
            'users_created': 0,
            'users_linked': 0,
            'images_uploaded': 0,
            'errors': []
        }
        
        logger.info(f"🚀 OLX Workflow Orchestrator initialized")
        logger.info(f"📞 Phone extraction: {'✅ Enabled' if self.cookies_file else '❌ Disabled (no cookies)'}")
    
    async def initialize(self):
        """Initialize async components"""
        try:
            # Initialize database connection pool
            self.db_pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            
            # Initialize user manager
            await self.user_manager.initialize_pool()
            
            logger.info("✅ Workflow components initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize workflow: {e}")
            raise
    
    async def close(self):
        """Clean up resources"""
        try:
            if self.db_pool:
                await self.db_pool.close()
            
            await self.user_manager.close_pool()
            
            if self.scraper:
                self.scraper.close()
            
            logger.info("🏁 Workflow components closed")
            
        except Exception as e:
            logger.error(f"⚠️ Error during cleanup: {e}")
    
    async def run_complete_workflow(self, 
                                  page_url: str,
                                  max_pages: int = 2,
                                  max_cars: int = 20,
                                  upload_images: bool = True) -> Dict[str, Any]:
        """
        Run the complete OLX scraping workflow
        
        Args:
            page_url: OLX URL to scrape (brand page or main cars page)
            max_pages: Maximum pages to scrape
            max_cars: Maximum cars to process
            upload_images: Whether to upload images to S3
            
        Returns:
            Dictionary with workflow results and statistics
        """
        logger.info(f"🚀 Starting complete OLX workflow")
        logger.info(f"📄 Target: {max_cars} cars from {max_pages} pages")
        logger.info(f"🔗 URL: {page_url}")
        logger.info(f"🖼️ Image upload: {'✅' if upload_images else '❌'}")
        
        workflow_results = {
            'success': False,
            'stats': self.session_stats.copy(),
            'cars_processed': [],
            'errors': []
        }
        
        try:
            # Step 1: Scrape cars from OLX
            logger.info("📋 Step 1: Scraping cars from OLX...")
            scraped_cars = await self._scrape_cars_step(page_url, max_pages, max_cars)
            
            if not scraped_cars:
                workflow_results['errors'].append("No cars scraped from OLX")
                return workflow_results
            
            self.session_stats['cars_scraped'] = len(scraped_cars)
            logger.info(f"✅ Step 1 complete: {len(scraped_cars)} cars scraped")
            
            # Step 2: Process each car through the complete workflow
            for i, car_data in enumerate(scraped_cars, 1):
                logger.info(f"🚗 Processing car {i}/{len(scraped_cars)}")
                
                try:
                    # Process single car through workflow
                    car_result = await self._process_single_car_workflow(car_data, upload_images)
                    
                    if car_result['success']:
                        workflow_results['cars_processed'].append(car_result)
                        self.session_stats['cars_saved_to_db'] += 1
                        
                        if car_result.get('user_created'):
                            self.session_stats['users_created'] += 1
                        if car_result.get('user_linked'):
                            self.session_stats['users_linked'] += 1
                        if car_result.get('images_uploaded', 0) > 0:
                            self.session_stats['images_uploaded'] += car_result['images_uploaded']
                    else:
                        workflow_results['errors'].append(f"Car {i}: {car_result.get('error', 'Unknown error')}")
                        self.session_stats['errors'].append(car_result.get('error', 'Unknown error'))
                
                except Exception as e:
                    error_msg = f"Car {i} processing failed: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    workflow_results['errors'].append(error_msg)
                    self.session_stats['errors'].append(error_msg)
            
            # Calculate final stats
            self.session_stats['completed_at'] = datetime.now()
            self.session_stats['duration_seconds'] = (
                self.session_stats['completed_at'] - self.session_stats['started_at']
            ).total_seconds()
            
            workflow_results['success'] = self.session_stats['cars_saved_to_db'] > 0
            workflow_results['stats'] = self.session_stats
            
            # Log final summary
            logger.info(f"🎉 Workflow complete!")
            logger.info(f"📊 Final stats:")
            logger.info(f"  🚗 Cars scraped: {self.session_stats['cars_scraped']}")
            logger.info(f"  💾 Cars saved to DB: {self.session_stats['cars_saved_to_db']}")
            logger.info(f"  👥 Users created: {self.session_stats['users_created']}")
            logger.info(f"  🔗 Users linked: {self.session_stats['users_linked']}")
            logger.info(f"  🖼️ Images uploaded: {self.session_stats['images_uploaded']}")
            logger.info(f"  ❌ Errors: {len(self.session_stats['errors'])}")
            logger.info(f"  ⏱️ Duration: {self.session_stats['duration_seconds']:.1f}s")
            
            return workflow_results
            
        except Exception as e:
            error_msg = f"Workflow failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            workflow_results['errors'].append(error_msg)
            return workflow_results
    
    async def _scrape_cars_step(self, page_url: str, max_pages: int, max_cars: int) -> List[Dict[str, Any]]:
        """Step 1: Scrape cars from OLX"""
        try:
            # Use the enhanced scraper to get cars
            cars = self.scraper.scrape_with_fixed_enhanced_method(
                page_url=page_url,
                max_pages=max_pages,
                max_cars=max_cars
            )
            
            return cars
            
        except Exception as e:
            logger.error(f"❌ Scraping step failed: {e}")
            return []
    
    async def _process_single_car_workflow(self, car_data: Dict[str, Any], upload_images: bool = True) -> Dict[str, Any]:
        """Process a single car through the complete workflow"""
        car_url = car_data.get('url', 'Unknown URL')
        car_title = car_data.get('title', 'Unknown car')[:50]
        
        result = {
            'success': False,
            'car_url': car_url,
            'car_title': car_title,
            'car_id': None,
            'user_id': None,
            'user_created': False,
            'user_linked': False,
            'images_uploaded': 0,
            'error': None
        }
        
        try:
            # Step A: Transform data for database
            logger.debug(f"  🔄 Transforming data for: {car_title}")
            transformed_data = transform_enhanced_scraped_data(car_data)
            
            # Step B: Save car to database
            logger.debug(f"  💾 Saving to database: {car_title}")
            car_id = await self._save_car_to_database(transformed_data)
            
            if not car_id:
                result['error'] = "Failed to save car to database"
                return result
            
            result['car_id'] = car_id
            
            # Step C: Handle user management (if phone number available)
            phone_number = car_data.get('phone_number')
            if phone_number:
                logger.debug(f"  👤 Processing user for phone: {phone_number}")
                user_result = await self._handle_user_management(car_id, phone_number, car_data)
                result.update(user_result)
            else:
                logger.debug(f"  📞 No phone number available for: {car_title}")
            
            # Step D: Process images (if enabled and available)
            if upload_images and car_data.get('images'):
                logger.debug(f"  🖼️ Processing {len(car_data['images'])} images for: {car_title}")
                images_result = await self._handle_image_processing(car_id, car_data)
                result['images_uploaded'] = images_result.get('uploaded_count', 0)
            
            result['success'] = True
            logger.debug(f"  ✅ Completed workflow for: {car_title}")
            return result
            
        except Exception as e:
            error_msg = f"Single car workflow failed for {car_title}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            result['error'] = error_msg
            return result
    
    async def _save_car_to_database(self, transformed_data: Dict[str, Any]) -> Optional[int]:
        """Save transformed car data to PostgreSQL database"""
        try:
            async with self.db_pool.acquire() as conn:
                # Check for duplicate URL
                existing_car = await conn.fetchval(
                    "SELECT id FROM cars WHERE url = $1",
                    transformed_data['url']
                )
                
                if existing_car:
                    logger.debug(f"  ⚠️ Car already exists with ID {existing_car}")
                    return existing_car
                
                # Prepare insert statement
                columns = list(transformed_data.keys())
                placeholders = [f"${i+1}" for i in range(len(columns))]
                values = list(transformed_data.values())
                
                # Convert JSON fields to proper format
                for i, (key, value) in enumerate(zip(columns, values)):
                    if key in ['images', 'features', 'equipment_list'] and value is not None:
                        values[i] = json.dumps(value) if not isinstance(value, str) else value
                
                query = f"""
                INSERT INTO cars ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING id
                """
                
                car_id = await conn.fetchval(query, *values)
                logger.debug(f"  💾 Saved car to database with ID: {car_id}")
                return car_id
                
        except Exception as e:
            logger.error(f"❌ Database save failed: {e}")
            return None
    
    async def _handle_user_management(self, car_id: int, phone_number: str, car_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user creation/linking for the car"""
        result = {
            'user_id': None,
            'user_created': False,
            'user_linked': False
        }
        
        try:
            # Use the user manager to link car to user
            link_result = await self.user_manager.link_car_to_user(car_id, phone_number, car_data)
            
            if link_result['success']:
                result['user_id'] = link_result['user_id']
                result['user_created'] = link_result.get('user_created', False)
                result['user_linked'] = True
                logger.debug(f"    👤 User {result['user_id']} linked to car {car_id}")
            else:
                logger.warning(f"    ⚠️ Failed to link user: {link_result['error']}")
            
        except Exception as e:
            logger.error(f"❌ User management failed: {e}")
        
        return result
    
    async def _handle_image_processing(self, car_id: int, car_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle image upload to S3 and database update"""
        result = {
            'uploaded_count': 0,
            's3_urls': [],
            'errors': []
        }
        
        try:
            images = car_data.get('images', [])
            if not images:
                return result
            
            s3_urls = []
            
            # Process up to 5 images per car
            for i, image_url in enumerate(images[:5]):
                try:
                    # Generate S3 key
                    s3_key = f"cars/{car_id}/image_{i+1}.jpg"
                    
                    # Upload image to S3
                    s3_url = self.s3_service.upload_image_from_url(image_url, s3_key)
                    
                    if s3_url:
                        s3_urls.append({
                            'original_url': image_url,
                            's3_url': s3_url,
                            's3_key': s3_key,
                            'index': i+1
                        })
                        result['uploaded_count'] += 1
                    else:
                        result['errors'].append(f"Failed to upload image {i+1}")
                        
                except Exception as e:
                    error_msg = f"Image {i+1} upload failed: {str(e)}"
                    result['errors'].append(error_msg)
                    logger.warning(f"    ⚠️ {error_msg}")
            
            # Update car record with S3 URLs
            if s3_urls:
                await self._update_car_images(car_id, s3_urls, images)
                result['s3_urls'] = s3_urls
                logger.debug(f"    🖼️ Uploaded {len(s3_urls)} images to S3")
            
        except Exception as e:
            logger.error(f"❌ Image processing failed: {e}")
            result['errors'].append(str(e))
        
        return result
    
    async def _update_car_images(self, car_id: int, s3_urls: List[Dict], original_images: List[str]):
        """Update car record with S3 image URLs"""
        try:
            # Prepare images JSON with both original and S3 URLs
            images_data = {
                'original_urls': original_images,
                's3_images': s3_urls,
                'processed_at': datetime.now().isoformat(),
                'total_uploaded': len(s3_urls)
            }
            
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE cars SET images = $1 WHERE id = $2",
                    json.dumps(images_data),
                    car_id
                )
            
            logger.debug(f"    💾 Updated car {car_id} with S3 image URLs")
            
        except Exception as e:
            logger.error(f"❌ Failed to update car images: {e}")

# Workflow factory functions
async def run_brand_workflow(brand_name: str, max_cars: int = 20, upload_images: bool = True) -> Dict[str, Any]:
    """Run workflow for a specific brand"""
    brand_url = f"https://www.olx.pt/carros-motos-e-barcos/carros/{brand_name.lower()}/"
    
    orchestrator = OLXWorkflowOrchestrator()
    
    try:
        await orchestrator.initialize()
        result = await orchestrator.run_complete_workflow(
            page_url=brand_url,
            max_pages=2,
            max_cars=max_cars,
            upload_images=upload_images
        )
        return result
    finally:
        await orchestrator.close()

async def run_main_page_workflow(max_cars: int = 10, upload_images: bool = True) -> Dict[str, Any]:
    """Run workflow on main OLX cars page"""
    main_url = "https://www.olx.pt/carros-motos-e-barcos/carros/"
    
    orchestrator = OLXWorkflowOrchestrator()
    
    try:
        await orchestrator.initialize()
        result = await orchestrator.run_complete_workflow(
            page_url=main_url,
            max_pages=1,
            max_cars=max_cars,
            upload_images=upload_images
        )
        return result
    finally:
        await orchestrator.close()

# CLI interface
async def main():
    """CLI interface for the workflow"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OLX Complete Workflow')
    parser.add_argument('--brand', type=str, help='Brand to scrape (e.g., bmw, audi)')
    parser.add_argument('--max-cars', type=int, default=20, help='Maximum cars to process')
    parser.add_argument('--no-images', action='store_true', help='Skip image upload')
    parser.add_argument('--url', type=str, help='Custom OLX URL to scrape')
    parser.add_argument('--max-pages', type=int, default=2, help='Maximum pages to scrape')
    
    args = parser.parse_args()
    
    print("🚀 OLX Complete Workflow")
    print("=" * 50)
    
    try:
        if args.url:
            # Custom URL
            orchestrator = OLXWorkflowOrchestrator()
            await orchestrator.initialize()
            
            result = await orchestrator.run_complete_workflow(
                page_url=args.url,
                max_pages=args.max_pages,
                max_cars=args.max_cars,
                upload_images=not args.no_images
            )
            
            await orchestrator.close()
            
        elif args.brand:
            # Brand-specific workflow
            result = await run_brand_workflow(
                args.brand,
                max_cars=args.max_cars,
                upload_images=not args.no_images
            )
        else:
            # Main page workflow
            result = await run_main_page_workflow(
                max_cars=args.max_cars,
                upload_images=not args.no_images
            )
        
        # Print results
        if result['success']:
            print(f"✅ Workflow completed successfully!")
            print(f"📊 Cars processed: {result['stats']['cars_saved_to_db']}")
            print(f"👥 Users created: {result['stats']['users_created']}")
            print(f"🖼️ Images uploaded: {result['stats']['images_uploaded']}")
        else:
            print(f"❌ Workflow failed")
            print(f"Errors: {len(result['errors'])}")
            for error in result['errors'][:3]:
                print(f"  - {error}")
        
    except KeyboardInterrupt:
        print("\n🛑 Workflow interrupted by user")
    except Exception as e:
        print(f"❌ Workflow error: {e}")

if __name__ == "__main__":
    asyncio.run(main())