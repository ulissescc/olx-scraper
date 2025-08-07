# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an OLX car scraper system for Portuguese car listings that extracts comprehensive vehicle data from OLX.pt. The system includes web scraping, image processing, user management, data transformation, and database integration.

## Core Architecture

**Main Components:**
- `olx_scraper.py` - Core scraper class with Selenium/requests-based extraction (2100+ lines)
- **`fixed_enhanced_scraper.py` - ENHANCED scraper with mobile support and bulk extraction (RECOMMENDED)**
- `scheduled_scraper.py` - Automated scraper that runs every 60 seconds with production defaults
- `run_scraper.py` - CLI interface with argument parsing for manual scraping operations
- `analyze_olx_page.py` - Live page analysis script for discovering new selectors
- `user_management.py` - Phone-number-based user tracking system using Redis
- `redis_service.py` - Redis caching service for presigned URLs and metadata
- `s3_service.py` - AWS S3 integration for image uploads and presigned URL generation
- `image_processor.py` - Image download and processing pipeline
- `data_transformer.py` - Transforms scraped data to database schema format

**Key Features:**
- Extracts 35+ data fields per car listing including phone numbers (with cookie authentication)
- Anti-detection measures with user agent rotation, random delays, and headless browser support
- Automatic brand selection from top OLX brands
- Phone number extraction via JavaScript button clicking (requires cookies)
- Image processing and S3 upload with presigned URL caching
- User mapping based on extracted phone numbers
- Database integration with car model persistence

## Common Commands

### Running the Original Scraper

**Manual scraping:**
```bash
# Basic test with 3 cars
python run_scraper.py --test

# List available brands
python run_scraper.py --list-brands

# Scrape specific brand
python run_scraper.py --brand bmw --max-cars 20 --max-pages 3

# Extract phone numbers (requires cookies)
python run_scraper.py --brand audi --cookies cookies.txt --extract-phone
```

**Scheduled scraping:**
```bash
# Run continuously every 60 seconds
python scheduled_scraper.py

# Single test run
python scheduled_scraper.py once
```

### Running the Enhanced Scraper (RECOMMENDED)

**Fixed Enhanced Scraper with Mobile Support:**
```bash
# Test enhanced scraper with BMW brand page
python fixed_enhanced_scraper.py

# Use the FixedEnhancedOLXScraper class in your own scripts
from fixed_enhanced_scraper import FixedEnhancedOLXScraper

scraper = FixedEnhancedOLXScraper(cookies_file="cookies.txt")
cars = scraper.scrape_with_fixed_enhanced_method("https://www.olx.pt/carros-motos-e-barcos/carros/bmw/", max_pages=2, max_cars=10)
```

### Environment Setup

The system uses `.venv` for Python environment management:
```bash
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### Dependencies

Key Python packages required:
- `selenium` + `webdriver-manager` for browser automation
- `requests` + `beautifulsoup4` for HTTP requests and HTML parsing  
- `boto3` for AWS S3 integration
- `redis` for caching and user management
- `pandas` for data export
- `fake-useragent` for user agent rotation

### Cookie Authentication

For phone number extraction, export cookies from Brave browser:
1. Login to OLX in browser
2. F12 > Application > Cookies > olx.pt
3. Export to Netscape format as `cookies.txt`
4. Use `--cookies cookies.txt --extract-phone`

## Code Patterns

**Scraper Architecture:**
- Primary scraper class (`OLXCarScraper`) handles both Selenium and requests-based extraction
- **NEW: Enhanced scraper (`FixedEnhancedOLXScraper`)** with mobile support and bulk extraction
- Extensive field extraction with Portuguese-to-English mapping for car specifications
- Enhanced extraction methods with multiple fallback strategies for robustness
- Built-in anti-detection with random delays, user agent rotation, and headless operation

**Enhanced Data Flow (NEW):**
1. **Adaptive page detection** (mobile vs desktop automatically detected)
2. **Bulk listing extraction** from brand pages with preview data (100+ listings per page)
3. **Smart prioritization** based on available preview data
4. **Enhanced URL handling** for both `/d/anuncio/` and `/anuncio/` formats
5. Individual car detail extraction (35+ fields) with preview data fallbacks
6. **Improved phone extraction** with multiple selector strategies
7. Enhanced metadata tracking and analysis

**Mobile vs Desktop Support:**
```python
# Automatic detection and adaptive selectors
if 'm.olx.pt' in final_url:
    self.mobile_mode = True
    selectors = self.mobile_selectors
else:
    selectors = self.desktop_selectors
```

**Enhanced Extraction Results:**
- **188 listings found** per brand page (vs ~10-20 with original)
- **Mobile/desktop compatibility** automatically handled
- **Preview data extraction** reduces unnecessary page visits
- **Phone extraction success rate improved** from 33% to 40% with enhanced selectors

**Configuration Pattern:**
Services are initialized with dependency injection:
```python
redis_service = RedisService()
user_manager = UserManager(redis_service)

# Original scraper
scraper = OLXCarScraper(cookies_file="cookies.txt")

# Enhanced scraper (recommended)
enhanced_scraper = FixedEnhancedOLXScraper(cookies_file="cookies.txt")
```

## Development Notes

- The scraper uses Chromium browser installed via snap (`/snap/bin/chromium`)
- ChromeDriver version 138.0.7204.183 is specifically configured for compatibility
- Anti-detection includes disabled automation indicators and webdriver property hiding
- Phone extraction requires authenticated session (cookies) and JavaScript execution
- Random delays (1-5 seconds) between operations prevent rate limiting
- WSL2 compatibility settings included for headless browser operation

## Database Integration

The system integrates with a FastAPI backend using:
- `Car` model for database persistence
- `CarDataTransformer` for field mapping between scraped and database formats
- Async database sessions to avoid concurrency issues
- Duplicate detection based on car URL

## Error Handling

- Comprehensive exception handling with detailed logging
- Graceful fallbacks when services are unavailable (Redis, S3, etc.)
- Session cleanup and resource management
- Validation for extracted data (price ranges, year validation, etc.)