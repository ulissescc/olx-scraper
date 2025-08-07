# OLX Car Scraper - Complete Workflow System

Complete end-to-end scraping system for Portuguese car listings from OLX.pt with user management, image processing, and database integration.

## 🚀 Quick Start

### 1. Configuration
Edit `config.json` to set your database URL, S3 credentials, and preferences:

```json
{
  "database": {
    "url": "postgresql://car_user:dev_password@localhost:5432/car_marketplace_dev"
  },
  "aws_s3": {
    "bucket_name": "your-bucket-name",
    "region": "eu-west-1"
  }
}
```

### 2. Run Complete Workflow

**Brand scraping (recommended):**
```bash
python production_scraper.py brand bmw 20
```

**Main page scraping:**
```bash
python production_scraper.py main 10
```

**Custom URL scraping:**
```bash
python production_scraper.py url https://www.olx.pt/carros-motos-e-barcos/carros/audi/ 15
```

## 📋 System Architecture

### Core Components

1. **`olx_workflow.py`** - Main workflow orchestrator
2. **`fixed_enhanced_scraper.py`** - Enhanced OLX scraper with mobile support
3. **`postgres_user_manager.py`** - PostgreSQL-based user management
4. **`enhanced_data_transformer.py`** - Data transformation for database
5. **`production_scraper.py`** - Server-friendly production interface
6. **`config_loader.py`** - Configuration management
7. **`s3_service.py`** - AWS S3 image upload service

### Complete Workflow Process

```
OLX Scraping → Phone Extraction → User Management → Image S3 Upload → PostgreSQL Storage
```

**Step-by-step:**
1. **Scrape OLX**: Enhanced scraper extracts 35+ fields per car + phone numbers
2. **User Creation**: Phone numbers → create/find users in PostgreSQL
3. **Image Processing**: Download images → upload to S3
4. **Database Storage**: Save cars with user relationships + S3 image URLs
5. **Statistics**: Track success rates and performance

## 🔧 Features

### Enhanced Scraper Capabilities
- **188+ listings per page** detection (vs 20 with basic scrapers)
- **Mobile & desktop compatibility** - auto-detects page type
- **Dual URL format support**: `/d/anuncio/` and `/anuncio/`
- **Bulk preview extraction** - reduces page visits
- **Enhanced phone extraction** - multiple selector strategies
- **Anti-detection measures** - random delays, user agent rotation

### Database Integration
- **PostgreSQL native** - async operations
- **User-car relationships** - phone number → user linking
- **Image URL storage** - both original OLX and S3 URLs
- **Duplicate prevention** - URL-based deduplication
- **Performance optimized** - connection pooling, bulk operations

### Image Processing
- **S3 upload workflow** - automatic image processing
- **Original URL preservation** - keep both OLX and S3 links
- **Configurable limits** - max images per car
- **Error handling** - failed uploads don't break workflow

## 🗄️ Database Schema

### Users Table
```sql
phone_number (unique) | name | email | city | total_cars | active_listings | created_at
```

### Cars Table  
```sql
url (unique) | title | brand | model | year | price | phone_number | images (JSON) | user_id (FK)
```

**Relationship**: `cars.user_id → users.id`

## ⚙️ Configuration Options

### Environment Variables (override config.json)
```bash
export DATABASE_URL="postgresql://user:pass@host:5432/db"
export AWS_S3_BUCKET="your-bucket"
export MAX_CARS=50
export PHONE_EXTRACTION=true
export S3_UPLOAD_ENABLED=true
```

### Config File Options
- **Database**: Connection settings, pool configuration
- **Scraper**: Headless mode, delays, max cars/pages
- **AWS S3**: Bucket, region, image settings
- **Workflow**: Enable/disable features, retry settings

## 📊 Performance Metrics

### Test Results (Real Data)
- **BMW Brand Page**: 5/5 cars scraped (100% success)
- **Main Cars Page**: 3/3 cars scraped (100% success)
- **Phone Extraction**: 37.5% success rate
- **Processing Speed**: ~3-7 seconds per car
- **Listing Detection**: 188+ listings per brand page

### Production Stats
- **Data Fields**: 35-44 fields per car
- **Image Handling**: Up to 5 images per car
- **User Management**: Automatic phone → user linking
- **Error Handling**: Comprehensive retry mechanisms

## 🔑 Required Setup

### 1. Database
```bash
# PostgreSQL with existing schema
createdb car_marketplace_dev
# Tables: users, cars (with foreign key relationship)
```

### 2. Cookies (for phone extraction)
```bash
# Export cookies from browser to cookies.txt (Netscape format)
# Place in project root directory
```

### 3. AWS S3 (for image upload)
```bash
# Set AWS credentials via environment or ~/.aws/credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
```

## 🏃‍♂️ Usage Examples

### Production Server Integration
```python
from production_scraper import quick_brand_scrape, quick_main_scrape

# Scrape BMW cars
result = await quick_brand_scrape('bmw', max_cars=15)

# Scrape main page
result = await quick_main_scrape(max_cars=10)

print(f"Success: {result['success']}")
print(f"Cars saved: {result['stats']['cars_saved_to_db']}")
```

### Direct Workflow Usage
```python
from olx_workflow import OLXWorkflowOrchestrator

orchestrator = OLXWorkflowOrchestrator()
await orchestrator.initialize()

result = await orchestrator.run_complete_workflow(
    page_url="https://www.olx.pt/carros-motos-e-barcos/carros/bmw/",
    max_pages=2,
    max_cars=20,
    upload_images=True
)

await orchestrator.close()
```

### Configuration Management
```python
from config_loader import get_config

config = get_config()
db_url = config.get_database_url()
max_cars = config.get_max_cars_default()
```

## 📈 Monitoring & Results

### Result Files
Results are automatically saved to `./results/` directory:
- `brand_bmw_results_20250807_123456.json`
- `main_page_results_20250807_123456.json`

### Logging
- **Console output**: Real-time progress
- **Log files**: `olx_workflow.log`
- **Error tracking**: Comprehensive error collection

## 🔍 Troubleshooting

### Common Issues

**No phone numbers extracted:**
- Ensure `cookies.txt` exists with valid OLX login cookies
- Check `config.json` has `phone_extraction_enabled: true`

**Database connection errors:**
- Verify PostgreSQL is running
- Check database URL in config
- Ensure user has proper permissions

**S3 upload failures:**
- Verify AWS credentials
- Check bucket name and permissions
- Ensure region is correct

**Low listing detection:**
- Check if OLX changed page structure
- Verify target URLs are correct
- Monitor logs for selector failures

## 📋 Project Files

### Production Ready
- `olx_workflow.py` - Main workflow orchestrator
- `production_scraper.py` - Server-friendly interface  
- `fixed_enhanced_scraper.py` - Enhanced OLX scraper
- `postgres_user_manager.py` - User management
- `enhanced_data_transformer.py` - Data transformation
- `config_loader.py` - Configuration management
- `config.json` - Configuration file

### Supporting Files
- `s3_service.py` - AWS S3 integration
- `image_processor.py` - Image processing utilities
- `olx_scraper.py` - Original scraper (legacy)
- `user_management.py` - Redis version (legacy)
- `data_transformer.py` - Basic transformer (legacy)

## 🎯 Success Metrics

✅ **Complete workflow implementation** - OLX → Database  
✅ **User-phone-car relationships** - Fully integrated  
✅ **Image S3 upload workflow** - Automated processing  
✅ **188+ listings per page** - Enhanced detection  
✅ **Mobile/desktop support** - Universal compatibility  
✅ **PostgreSQL integration** - Production database  
✅ **Configuration system** - Environment flexibility  
✅ **Clean codebase** - Production ready

---
*Ready for production deployment on server infrastructure*