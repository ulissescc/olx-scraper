# Railway Deployment Guide - OLX Car Scraper

## 🚀 Quick Railway Setup

### 1. Railway Project Setup
```bash
# Connect to Railway (install Railway CLI first)
railway login
railway init
railway link
```

### 2. Required Environment Variables
Set these in Railway dashboard or via CLI:

#### Database (Railway PostgreSQL)
```bash
# Railway automatically provides these:
# POSTGRES_URL - Database connection string
# DATABASE_URL - Same as POSTGRES_URL
```

#### AWS S3 Configuration
```bash
railway variables set AWS_ACCESS_KEY_ID="your-access-key"
railway variables set AWS_SECRET_ACCESS_KEY="your-secret-key" 
railway variables set AWS_S3_BUCKET="car-marketplace-images"
railway variables set AWS_REGION="eu-west-1"
```

#### Scraper Configuration
```bash
railway variables set MAX_CARS=20
railway variables set SCRAPER_HEADLESS=true
railway variables set PHONE_EXTRACTION=true
railway variables set S3_UPLOAD_ENABLED=true
# Note: PORT is automatically set by Railway
```

### 3. Deploy to Railway
```bash
# Deploy current directory
railway up

# Or deploy from Git
git add .
git commit -m "Initial Railway deployment"
git push
railway up
```

## 📋 API Endpoints

Once deployed, your Railway app will have these endpoints:

### Health Check
```
GET https://your-app.railway.app/health
```

### Scraping Endpoints
```bash
# Scrape BMW cars
POST https://your-app.railway.app/scrape/brand/bmw?max_cars=10

# Scrape main page
POST https://your-app.railway.app/scrape/main?max_cars=5

# Scrape custom URL
POST https://your-app.railway.app/scrape/url?url=https://www.olx.pt/carros-motos-e-barcos/carros/audi/&max_cars=15

# Get results
GET https://your-app.railway.app/results?limit=10

# Get configuration
GET https://your-app.railway.app/config
```

## 🗄️ Database Setup

Railway automatically provides PostgreSQL. The scraper expects these tables:

### Cars Table
```sql
CREATE TABLE cars (
    id SERIAL PRIMARY KEY,
    url VARCHAR UNIQUE NOT NULL,
    title VARCHAR,
    brand VARCHAR,
    model VARCHAR,
    year INTEGER,
    price DECIMAL(10,2),
    price_raw VARCHAR,
    price_negotiable BOOLEAN DEFAULT false,
    phone_number VARCHAR,
    user_id INTEGER,
    images JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    -- ... other fields
);
```

### Users Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR UNIQUE NOT NULL,
    name VARCHAR,
    city VARCHAR,
    total_cars INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 🔧 Configuration

The app uses `config.json` for defaults and environment variables for overrides:

### Default Configuration
- **Database**: Uses Railway's POSTGRES_URL automatically
- **Scraper**: Headless Chrome, 20 cars max, 2 pages max
- **S3**: EU-West-1 region, 5 images per car max
- **Workflow**: Phone extraction enabled, user management enabled

### Environment Variable Priority
1. Railway environment variables (highest priority)
2. .env file (if present)
3. config.json defaults (lowest priority)

## 📊 Usage Examples

### Curl Commands
```bash
# Health check
curl https://your-app.railway.app/health

# Scrape BMW cars
curl -X POST "https://your-app.railway.app/scrape/brand/bmw?max_cars=5"

# Get recent results
curl https://your-app.railway.app/results
```

### Python Client
```python
import requests

BASE_URL = "https://your-app.railway.app"

# Scrape Audi cars
response = requests.post(f"{BASE_URL}/scrape/brand/audi", params={"max_cars": 10})
result = response.json()

print(f"Cars scraped: {result['stats']['cars_saved_to_db']}")
print(f"Duration: {result['stats']['duration_seconds']:.1f}s")
```

## 🔒 Security Notes

- API is public but includes rate limiting
- AWS credentials are stored as Railway secrets
- Database credentials are managed by Railway
- No sensitive data in logs or responses

## 📈 Monitoring

- Health endpoint: `/health`
- Logs: Railway dashboard → Your App → Deployments → Logs
- Metrics: Railway dashboard → Your App → Metrics

## 🛠️ Troubleshooting

### Common Issues:

1. **Database Connection Failed**
   - Check POSTGRES_URL is set in Railway variables
   - Verify database tables exist

2. **S3 Upload Errors** 
   - Verify AWS credentials in Railway variables
   - Check bucket name and region

3. **Selenium/Chrome Issues**
   - Railway supports headless Chrome
   - If issues persist, check logs for WebDriver errors

4. **Memory Issues**
   - Limit max_cars to reasonable numbers (≤20)
   - Consider upgrading Railway plan if needed

## 📱 Quick Test After Deployment

```bash
# Replace with your Railway app URL
export RAILWAY_URL="https://your-app.railway.app"

# Test health
curl $RAILWAY_URL/health

# Test scraping (small test)
curl -X POST "$RAILWAY_URL/scrape/brand/toyota?max_cars=1"

# Check results
curl $RAILWAY_URL/results
```

---

🎉 **Your OLX Car Scraper is now running on Railway!**

Access your app at: https://your-app.railway.app