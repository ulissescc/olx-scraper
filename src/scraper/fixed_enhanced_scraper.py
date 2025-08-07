#!/usr/bin/env python3
"""
Fixed Enhanced OLX Car Scraper
Handles both brand pages with listings and individual /d/anuncio/ URLs
"""

import os
import re
import time
import json
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse

import requests
import pandas as pd
from bs4 import BeautifulSoup, Tag
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Remove dependency on removed base scraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fixed_enhanced_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FixedEnhancedOLXScraper:
    """
    Fixed Enhanced OLX scraper that properly handles:
    1. Brand pages with listings (https://www.olx.pt/carros-motos-e-barcos/carros/bmw/)
    2. Individual listing URLs (/d/anuncio/ format)
    3. Mobile vs desktop detection
    4. Bulk preview data extraction
    """
    
    def __init__(self, use_selenium: bool = True, headless: bool = True, cookies_file: str = None):
        """Initialize fixed enhanced scraper"""
        self.use_selenium = use_selenium
        self.headless = headless
        self.cookies_file = cookies_file
        self.driver = None
        self.session = None
        self.ua = UserAgent()
        
        self.mobile_mode = False
        self.extracted_previews = []
        
        logger.info("🔧 Fixed Enhanced OLX Scraper initialized")
        
        # Initialize scraped cars list
        self.scraped_cars = []
        
        # Initialize session and driver if requested
        self._initialize_session()
        if self.use_selenium:
            self._initialize_driver()
    
    def _initialize_session(self):
        """Initialize HTTP session"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-PT,pt;q=0.8,en;q=0.6',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
    
    def _initialize_driver(self):
        """Initialize Selenium WebDriver"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument('--headless')
            
            # Railway/Docker compatibility options
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')
            chrome_options.add_argument('--disable-javascript')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--remote-debugging-port=9222')
            chrome_options.add_argument('--single-process')
            chrome_options.add_argument('--no-zygote')
            chrome_options.add_argument(f'--user-agent={self.ua.random}')
            
            self.driver = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            # Load cookies if provided
            if self.cookies_file and Path(self.cookies_file).exists():
                self.driver.get('https://www.olx.pt')
                with open(self.cookies_file, 'r') as f:
                    cookies = f.read().strip().split('\n')
                    for cookie_line in cookies:
                        if cookie_line.strip() and not cookie_line.startswith('#'):
                            parts = cookie_line.split('\t')
                            if len(parts) >= 7:
                                cookie = {
                                    'name': parts[5],
                                    'value': parts[6],
                                    'domain': parts[0],
                                    'path': parts[2]
                                }
                                try:
                                    self.driver.add_cookie(cookie)
                                except Exception:
                                    pass
                
            logger.info("🌐 WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize WebDriver: {e}")
            logger.warning("⚠️ Falling back to HTTP-only scraping (no phone extraction)")
            self.driver = None
            self.use_selenium = False
    
    def get_corrected_listing_urls(self, page_url: str, max_pages: int = 3) -> List[Dict[str, Any]]:
        """
        Fixed listing URL extraction that handles both:
        - Brand pages with direct listings
        - Individual /d/anuncio/ URLs
        """
        logger.info(f"🔍 Fixed listing extraction from: {page_url}")
        all_listings = []
        
        try:
            for page_num in range(1, max_pages + 1):
                # Build page URL
                if page_num == 1:
                    current_url = page_url
                else:
                    separator = "&" if "?" in page_url else "?"
                    current_url = f"{page_url}{separator}page={page_num}"
                
                logger.info(f"📄 Page {page_num}: {current_url}")
                
                # Load page
                if self.driver:
                    self.driver.get(current_url)
                    time.sleep(4)  # Wait for page load
                    
                    final_url = self.driver.current_url
                    page_source = self.driver.page_source
                else:
                    response = self.session.get(current_url, timeout=15)
                    response.raise_for_status()
                    page_source = response.text
                    final_url = current_url
                
                # Detect mobile mode
                self.mobile_mode = 'm.olx.pt' in final_url
                logger.info(f"📱 Mobile mode: {self.mobile_mode}")
                
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Extract listings with corrected approach
                page_listings = self._extract_corrected_listings(soup, page_num)
                
                if not page_listings:
                    logger.warning(f"⚠️ No listings found on page {page_num}")
                    break
                
                all_listings.extend(page_listings)
                logger.info(f"✅ Page {page_num}: {len(page_listings)} listings found")
                
                if page_num < max_pages:
                    time.sleep(random.uniform(2, 4))
            
            # Remove duplicates by URL
            unique_listings = []
            seen_urls = set()
            for listing in all_listings:
                url = listing['url']
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_listings.append(listing)
            
            logger.info(f"🎯 Total unique listings: {len(unique_listings)}")
            return unique_listings
            
        except Exception as e:
            logger.error(f"❌ Error in corrected listing extraction: {e}")
            return []
    
    def _extract_corrected_listings(self, soup: BeautifulSoup, page_num: int) -> List[Dict[str, Any]]:
        """Extract listings with corrected selectors for both mobile and desktop"""
        listings = []
        
        # Strategy 1: Look for /d/anuncio/ links (CONFIRMED FORMAT)
        anuncio_links = soup.find_all('a', href=re.compile(r'/d/anuncio/.*ID[A-Za-z0-9]+\.html'))
        if anuncio_links:
            logger.info(f"  📋 Found {len(anuncio_links)} /d/anuncio/ links")
            for i, link in enumerate(anuncio_links):
                listing_data = self._extract_listing_from_link(link, i, page_num, 'd_anuncio')
                if listing_data:
                    listings.append(listing_data)
        
        # Strategy 2: Look for regular /anuncio/ links (ALTERNATIVE FORMAT)  
        regular_links = soup.find_all('a', href=re.compile(r'/anuncio/.*ID[A-Za-z0-9]+'))
        if regular_links:
            logger.info(f"  📋 Found {len(regular_links)} regular /anuncio/ links")
            for i, link in enumerate(regular_links):
                listing_data = self._extract_listing_from_link(link, i, page_num, 'regular_anuncio')
                if listing_data:
                    listings.append(listing_data)
        
        # Strategy 3: Look for mobile-specific selectors
        if self.mobile_mode:
            mobile_cards = soup.find_all(['a', 'div'], class_=re.compile(r'css-.*'))
            mobile_listings = []
            for element in mobile_cards:
                # Check if element contains a link to listing
                if element.name == 'a':
                    href = element.get('href', '')
                else:
                    link = element.find('a', href=True)
                    href = link.get('href', '') if link else ''
                
                if href and ('/d/anuncio/' in href or '/anuncio/' in href):
                    listing_data = self._extract_listing_from_link(element, len(mobile_listings), page_num, 'mobile_card')
                    if listing_data:
                        mobile_listings.append(listing_data)
            
            if mobile_listings:
                logger.info(f"  📱 Found {len(mobile_listings)} mobile card listings")
                listings.extend(mobile_listings)
        
        # Strategy 4: Fallback - any link with ID pattern
        if not listings:
            all_links = soup.find_all('a', href=True)
            fallback_listings = []
            for link in all_links:
                href = link.get('href', '')
                if re.search(r'ID[A-Za-z0-9]+', href) and ('anuncio' in href or 'carros' in href):
                    listing_data = self._extract_listing_from_link(link, len(fallback_listings), page_num, 'fallback')
                    if listing_data:
                        fallback_listings.append(listing_data)
            
            if fallback_listings:
                logger.info(f"  🔄 Fallback found {len(fallback_listings)} listings")
                listings.extend(fallback_listings)
        
        return listings
    
    def _extract_listing_from_link(self, element: Tag, index: int, page_num: int, method: str) -> Optional[Dict[str, Any]]:
        """Extract listing data from a link element"""
        try:
            # Get URL
            if element.name == 'a':
                href = element.get('href', '')
            else:
                link = element.find('a', href=True)
                href = link.get('href', '') if link else ''
            
            if not href:
                return None
            
            # Make absolute URL
            if href.startswith('/'):
                url = f"https://www.olx.pt{href}"
            elif href.startswith('http'):
                url = href
            else:
                return None
            
            # Validate URL format
            if not ('/anuncio/' in url and 'ID' in url):
                return None
            
            # Extract listing ID
            listing_id_match = re.search(r'ID([A-Za-z0-9]+)', url)
            listing_id = listing_id_match.group(1) if listing_id_match else f"unknown_{index}"
            
            # Get preview data from element
            preview_data = self._extract_preview_data_from_element(element)
            
            listing_data = {
                'url': url,
                'listing_id': listing_id,
                'page_number': page_num,
                'index': index,
                'extraction_method': method,
                'mobile_mode': self.mobile_mode,
                'preview_data': preview_data
            }
            
            return listing_data
            
        except Exception as e:
            logger.warning(f"⚠️ Error extracting from element {index}: {e}")
            return None
    
    def _extract_preview_data_from_element(self, element: Tag) -> Dict[str, Any]:
        """Extract preview data from listing element"""
        preview_data = {}
        
        # Get container (element itself or parent)
        container = element.parent if element.parent else element
        
        try:
            # Extract title
            title = None
            
            # Try title attribute
            if element.get('title'):
                title = element.get('title').strip()
            
            # Try image alt text
            if not title:
                img = container.find('img', alt=True)
                if img and img.get('alt') and len(img.get('alt')) > 10:
                    title = img.get('alt').strip()
            
            # Try text content
            if not title:
                text = element.get_text(strip=True) if hasattr(element, 'get_text') else ''
                if text and len(text) > 5 and len(text) < 200:
                    title = text
            
            if title:
                preview_data['title'] = title
                # Parse brand/model from title
                brand_model = self._parse_brand_model_from_title(title)
                preview_data.update(brand_model)
            
            # Extract image
            img = container.find('img')
            if img:
                src = img.get('src') or img.get('data-src') or img.get('data-original')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    preview_data['image'] = src
            
            # Extract price
            price_text = self._find_price_in_element(container)
            if price_text:
                preview_data['price_text'] = price_text
                preview_data['price'] = self._parse_price(price_text)
            
            # Extract year
            year_match = re.search(r'\b(19|20)\d{2}\b', container.get_text())
            if year_match:
                preview_data['year'] = int(year_match.group(0))
            
        except Exception as e:
            logger.debug(f"Preview data extraction error: {e}")
        
        return preview_data
    
    def _find_price_in_element(self, element: Tag) -> Optional[str]:
        """Find price in element"""
        if not hasattr(element, 'get_text'):
            return None
        
        text = element.get_text()
        
        # Price patterns
        price_patterns = [
            r'€\s*(\d{1,3}(?:[\.\s]\d{3})*(?:,\d{2})?)',
            r'(\d{1,3}(?:[\.\s]\d{3})*)\s*€',
            r'(\d{1,3}(?:\.\d{3})+)\s*€'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return None
    
    def scrape_with_fixed_enhanced_method(self, page_url: str, max_pages: int = 2, max_cars: int = 10) -> List[Dict[str, Any]]:
        """
        Main method: scrape cars with fixed enhanced approach
        """
        # Ensure parameters are integers
        max_cars = int(max_cars) if max_cars is not None else 10
        max_pages = int(max_pages) if max_pages is not None else 2
        
        logger.info(f"🚀 Starting FIXED enhanced scraping")
        logger.info(f"📊 Target: {max_cars} cars from {max_pages} pages")
        logger.info(f"🔗 URL: {page_url}")
        
        # Step 1: Get listings with corrected method
        listing_data_list = self.get_corrected_listing_urls(page_url, max_pages)
        
        if not listing_data_list:
            logger.warning("⚠️ No listings found with fixed method")
            return []
        
        # Step 2: Show preview data
        logger.info(f"📋 Preview data extracted:")
        for i, listing in enumerate(listing_data_list[:5]):  # Show first 5
            preview = listing.get('preview_data', {})
            title = preview.get('title', 'No title')[:40]
            price = preview.get('price_text', 'No price')
            method = listing.get('extraction_method', 'unknown')
            logger.info(f"  {i+1}. {title} - {price} ({method})")
        
        # Step 3: Prioritize listings
        prioritized = sorted(listing_data_list, key=lambda x: len(x.get('preview_data', {})), reverse=True)
        selected_listings = prioritized[:max_cars]
        
        # Step 4: Scrape individual cars
        scraped_cars = []
        for i, listing_data in enumerate(selected_listings, 1):
            url = listing_data['url']
            logger.info(f"🚗 Scraping car {i}/{len(selected_listings)}: {url}")
            
            # Use original scrape_car_details method
            car_data = self.scrape_car_details(url)
            
            if car_data:
                # Add enhancement metadata
                car_data['enhancement_metadata'] = {
                    'extraction_method': listing_data.get('extraction_method'),
                    'mobile_mode': listing_data.get('mobile_mode'),
                    'preview_data': listing_data.get('preview_data'),
                    'page_number': listing_data.get('page_number'),
                    'fixed_enhanced': True
                }
                
                scraped_cars.append(car_data)
                self.scraped_cars.append(car_data)
                
                # Show quick result
                title = car_data.get('title', 'No title')[:50]
                price = car_data.get('price_raw', 'No price')
                phone = "📞" if car_data.get('phone_number') else "❌"
                logger.info(f"  ✅ {title} - {price} {phone}")
            
            # Delay between cars
            self._random_delay(2, 4)
        
        logger.info(f"✅ Fixed enhanced scraping complete: {len(scraped_cars)} cars")
        return scraped_cars
    
    def scrape_car_details(self, url: str) -> Dict[str, Any]:
        """Basic car details scraping method - simplified version"""
        try:
            if self.driver:
                self.driver.get(url)
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            else:
                headers = {'User-Agent': self.ua.random}
                response = self.session.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract basic details with better selectors
            title = self._extract_title_from_soup(soup)
            price = self._extract_price_from_soup(soup)
            
            # Parse price data
            price_data = self._parse_price_data(price)
            
            return {
                'url': url,
                'title': title.get_text().strip() if title else 'No title',
                'price_raw': price.get_text().strip() if price else 'No price',
                'price': price_data['price'],
                'price_negotiable': price_data['negotiable'],
                'scraped_at': datetime.now().isoformat(),
                'source': 'scrape_car_details'
            }
        except Exception as e:
            logger.error(f"❌ Error scraping {url}: {e}")
            return {
                'url': url,
                'error': str(e),
                'scraped_at': datetime.now().isoformat()
            }
    
    def _random_delay(self, min_seconds: int = 2, max_seconds: int = 4):
        """Random delay between operations"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def _extract_title_from_soup(self, soup):
        """Extract title using multiple selectors"""
        title_selectors = [
            'h1[data-testid="listing-title"]',
            'h1.css-r9zjja-Text',
            'h1',
            '[data-testid="listing-title"]',
            'h1[class*="title"]'
        ]
        
        for selector in title_selectors:
            title = soup.select_one(selector)
            if title and title.get_text().strip():
                return title
        return None
    
    def _extract_price_from_soup(self, soup):
        """Extract price using multiple selectors"""
        price_selectors = [
            '[data-testid*="price"]',
            'h3[data-testid*="price"]', 
            'span[data-testid*="price"]',
            'h3.css-okktvh-Text',
            '[class*="price"]',
            'h3[class*="price"]',
            '.price'
        ]
        
        for selector in price_selectors:
            price = soup.select_one(selector)
            if price and price.get_text().strip():
                text = price.get_text().strip()
                # Check if it looks like a price (contains € or numbers)
                if '€' in text or any(char.isdigit() for char in text):
                    return price
        return None
    
    def _parse_price_data(self, price_element):
        """Parse price element to extract clean price and negotiable status"""
        if not price_element:
            return {'price': None, 'negotiable': False}
        
        price_text = price_element.get_text().strip()
        
        # Check if negotiable
        negotiable = 'negociável' in price_text.lower()
        
        # Extract numeric price
        import re
        
        # Remove "Negociável" and clean the text
        clean_text = re.sub(r'negociável', '', price_text, flags=re.IGNORECASE).strip()
        
        # Find price pattern like "14.000 €" or "14000€" or "14 000 €"
        price_patterns = [
            r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*€',  # 14.000 € or 14.000,50 €
            r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*€',  # 14 000 € or 14 000,50 €
            r'(\d+(?:,\d{2})?)\s*€',                   # 14000€ or 14000,50€
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, clean_text)
            if match:
                price_str = match.group(1)
                
                # Convert to standardized format (remove dots/spaces, handle comma as decimal)
                try:
                    # Handle formats like "14.000" -> "14000" or "14 000" -> "14000"
                    price_str = re.sub(r'[\.\s]', '', price_str)
                    
                    # Handle comma as decimal separator "14000,50" -> "14000.50"
                    if ',' in price_str:
                        price_str = price_str.replace(',', '.')
                    
                    price_value = float(price_str)
                    return {
                        'price': price_value,
                        'negotiable': negotiable
                    }
                except ValueError:
                    pass
        
        # If no price pattern found, return None
        return {'price': None, 'negotiable': negotiable}

    def close(self):
        """Close browser/session resources"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
            if self.session:
                self.session.close()
                self.session = None
            logger.info("🔒 Scraper resources closed")
        except Exception as e:
            logger.error(f"❌ Error closing scraper: {e}")
    
    def test_brand_page(self, brand_url: str = "https://www.olx.pt/carros-motos-e-barcos/carros/bmw/") -> List[Dict[str, Any]]:
        """Test scraping from a specific brand page"""
        logger.info(f"🧪 Testing brand page: {brand_url}")
        return self.scrape_with_fixed_enhanced_method(brand_url, max_pages=2, max_cars=5)


def main():
    """Test the fixed enhanced scraper"""
    print("🚀 Fixed Enhanced OLX Car Scraper Test")
    print("🔧 Handles /d/anuncio/ URLs and brand pages with listings")
    
    # Initialize with cookies
    cookies_file = "cookies.txt" if Path("cookies.txt").exists() else None
    scraper = FixedEnhancedOLXScraper(
        use_selenium=True,
        headless=True,
        cookies_file=cookies_file
    )
    
    try:
        print("\n📋 Test 1: BMW brand page")
        bmw_cars = scraper.test_brand_page("https://www.olx.pt/carros-motos-e-barcos/carros/bmw/")
        
        if bmw_cars:
            print(f"✅ BMW test successful: {len(bmw_cars)} cars")
            for i, car in enumerate(bmw_cars, 1):
                title = car.get('title', 'No title')[:50]
                price = car.get('price_raw', 'No price')
                phone = "📞 YES" if car.get('phone_number') else "📞 NO"
                mobile = "📱" if car.get('enhancement_metadata', {}).get('mobile_mode') else "💻"
                print(f"  {i}. {title} - {price} - {phone} {mobile}")
        
        print("\n📋 Test 2: Main cars page")
        main_cars = scraper.scrape_with_fixed_enhanced_method(
            "https://www.olx.pt/carros-motos-e-barcos/carros/",
            max_pages=1,
            max_cars=3
        )
        
        if main_cars:
            print(f"✅ Main page test successful: {len(main_cars)} cars")
            for i, car in enumerate(main_cars, 1):
                title = car.get('title', 'No title')[:50]
                price = car.get('price_raw', 'No price')
                print(f"  {i}. {title} - {price}")
        
        # Export results if any
        all_cars = bmw_cars + main_cars
        if all_cars:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_file = Path(f"scraped_data/fixed_enhanced_test_{timestamp}.json")
            json_file.parent.mkdir(exist_ok=True)
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(all_cars, f, ensure_ascii=False, indent=2)
            
            print(f"\n📁 Results saved: {json_file}")
            print(f"🎯 Total cars scraped: {len(all_cars)}")
        else:
            print("\n❌ No cars scraped in any test")
    
    finally:
        scraper.close()

if __name__ == "__main__":
    main()