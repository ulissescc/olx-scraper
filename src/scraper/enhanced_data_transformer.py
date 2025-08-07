"""
Enhanced Data transformation utilities for converting scraped data to database format
Supports both original scraper and enhanced scraper output
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class EnhancedCarDataTransformer:
    """Enhanced class for transforming scraped car data with support for enhanced scraper"""
    
    def __init__(self):
        pass
    
    def transform_scraped_data(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform scraped data to database format"""
        return transform_enhanced_scraped_data(scraped_data)

def transform_enhanced_scraped_data(scraped_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform enhanced scraped car data to database-compatible format
    Handles both original scraper output and enhanced scraper with metadata
    
    Args:
        scraped_data: Raw scraped data from OLX scraper (original or enhanced)
        
    Returns:
        Dictionary with data ready for database insertion
    """
    try:
        # Check if this is enhanced scraper output
        enhancement_metadata = scraped_data.get('enhancement_metadata', {})
        is_enhanced = bool(enhancement_metadata)
        
        # Parse scraped_at timestamp
        scraped_at = None
        if scraped_data.get('scraped_at'):
            try:
                scraped_at = datetime.fromisoformat(scraped_data['scraped_at'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                scraped_at = datetime.now(timezone.utc)
        else:
            scraped_at = datetime.now(timezone.utc)
        
        # Parse publication date
        publication_date = None
        if scraped_data.get('publication_date'):
            try:
                publication_date = datetime.fromisoformat(scraped_data['publication_date'])
            except (ValueError, AttributeError):
                pass
        
        # Parse seller dates
        seller_join_date = None
        if scraped_data.get('seller_join_date'):
            try:
                seller_join_date = datetime.fromisoformat(scraped_data['seller_join_date'])
            except (ValueError, AttributeError):
                pass
        
        seller_last_online = None
        if scraped_data.get('seller_last_online'):
            try:
                seller_last_online = datetime.fromisoformat(scraped_data['seller_last_online'])
            except (ValueError, AttributeError):
                pass
        
        # Enhanced: Parse phone extraction time from enhanced scraper
        phone_extraction_time = None
        phone_extraction_method = None
        
        if scraped_data.get('phone_extraction_time'):
            try:
                phone_extraction_time = datetime.fromisoformat(
                    scraped_data['phone_extraction_time'].replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                pass
        
        # Enhanced: Get phone extraction method
        phone_extraction_method = scraped_data.get('phone_extraction_method')
        
        # Transform data to database schema
        db_data = {
            # Required fields
            'url': scraped_data.get('url', ''),
            'scraped_at': scraped_at,
            'website': scraped_data.get('website', 'olx.pt'),
            
            # Basic car information
            'listing_id': scraped_data.get('listing_id'),
            'title': get_title_from_enhanced_data(scraped_data),
            'brand': clean_string(get_brand_from_enhanced_data(scraped_data)),
            'model': clean_string(get_model_from_enhanced_data(scraped_data)),
            'year': get_year_from_enhanced_data(scraped_data),
            
            # Pricing
            'price': safe_int(scraped_data.get('price')),
            'price_raw': get_price_from_enhanced_data(scraped_data),
            'price_negotiable': safe_bool(scraped_data.get('price_negotiable')),
            
            # Technical specifications
            'mileage': safe_int(scraped_data.get('mileage')),
            'mileage_raw': scraped_data.get('mileage_raw'),
            'fuel_type': clean_string(scraped_data.get('fuel_type')),
            'transmission': clean_string(scraped_data.get('transmission')),
            'power': safe_int(scraped_data.get('power')),
            'power_raw': scraped_data.get('power_raw'),
            'engine_size': safe_float(scraped_data.get('engine_size')),
            'doors': safe_int(scraped_data.get('doors')),
            'seats': safe_int(scraped_data.get('seats')),
            'color': clean_string(scraped_data.get('color')),
            'body_type': clean_string(scraped_data.get('body_type')),
            'condition': clean_string(scraped_data.get('condition')),
            'segment': clean_string(scraped_data.get('segment')),
            
            # Location
            'location': clean_string(scraped_data.get('location')),
            'location_raw': scraped_data.get('location_raw'),
            'city': clean_string(scraped_data.get('city')),
            'district': clean_string(scraped_data.get('district')),
            
            # Description and features
            'description': scraped_data.get('description'),
            'description_length': safe_int(scraped_data.get('description_length')),
            'features': safe_json_list(scraped_data.get('features')),
            'features_count': safe_int(scraped_data.get('features_count')),
            'equipment_list': safe_json_list(scraped_data.get('equipment_list')),
            
            # Enhanced: Images with both original and processed URLs
            'images': get_images_from_enhanced_data(scraped_data),
            'main_image': scraped_data.get('main_image'),
            'image_count': safe_int(scraped_data.get('image_count')),
            
            # Publication information
            'publication_date': publication_date,
            'publication_date_raw': scraped_data.get('publication_date_raw'),
            'view_count': safe_int(scraped_data.get('view_count')),
            
            # Seller information
            'seller_name': clean_string(scraped_data.get('seller_name')),
            'seller_type': clean_string(scraped_data.get('seller_type')),
            'seller_join_date': seller_join_date,
            'seller_join_date_raw': scraped_data.get('seller_join_date_raw'),
            'seller_last_online': seller_last_online,
            'seller_last_online_raw': scraped_data.get('seller_last_online_raw'),
            
            # Enhanced: Contact information with enhanced extraction data
            'phone_available': safe_bool(scraped_data.get('phone_available')),
            'phone_extracted': safe_bool(scraped_data.get('phone_extracted')),
            'phone_number': clean_string(scraped_data.get('phone_number')),
            'phone_extraction_time': phone_extraction_time,
            'phone_extraction_error': scraped_data.get('phone_extraction_error'),
            'messaging_available': safe_bool(scraped_data.get('messaging_available')),
            
            # Additional metadata
            'first_registration': scraped_data.get('first_registration'),
            'registration_month': scraped_data.get('registration_month'),
            'inspection': scraped_data.get('inspection'),
            'co2_emissions': scraped_data.get('co2_emissions'),
            'fuel_consumption': scraped_data.get('fuel_consumption'),
            'drivetrain': scraped_data.get('drivetrain'),
            'origin': scraped_data.get('origin'),
            'category': scraped_data.get('category'),
        }
        
        # Enhanced: Add enhancement metadata as JSON if available
        if is_enhanced:
            # Store enhancement metadata for tracking
            enhanced_metadata = {
                'extraction_method': enhancement_metadata.get('extraction_method'),
                'mobile_mode': enhancement_metadata.get('mobile_mode'),
                'preview_data': enhancement_metadata.get('preview_data'),
                'page_number': enhancement_metadata.get('page_number'),
                'fixed_enhanced': enhancement_metadata.get('fixed_enhanced'),
                'phone_extraction_method': phone_extraction_method,
                'enhanced_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Add as notes or custom field (since we don't have enhancement_metadata in DB)
            if not db_data.get('description'):
                db_data['description'] = f"Enhanced extraction: {json.dumps(enhanced_metadata, ensure_ascii=False)}"
            else:
                # Append to description
                db_data['description'] += f"\n\n[Enhanced extraction metadata: {json.dumps(enhanced_metadata, ensure_ascii=False)}]"
        
        # Remove None values to avoid database issues
        db_data = {k: v for k, v in db_data.items() if v is not None}
        
        return db_data
        
    except Exception as e:
        logger.error(f"Error transforming enhanced scraped data: {e}")
        raise ValueError(f"Failed to transform enhanced scraped data: {e}")

def get_title_from_enhanced_data(scraped_data: Dict[str, Any]) -> Optional[str]:
    """Get title from enhanced data with fallbacks"""
    # Try main title first
    if scraped_data.get('title'):
        return clean_string(scraped_data['title'])
    
    # Try preview title from enhanced scraper
    enhancement_metadata = scraped_data.get('enhancement_metadata', {})
    preview_data = enhancement_metadata.get('preview_data', {})
    
    if preview_data.get('title'):
        return clean_string(preview_data['title'])
    
    # Fallback: generate title from available data
    return generate_title_from_data(scraped_data)

def get_brand_from_enhanced_data(scraped_data: Dict[str, Any]) -> Optional[str]:
    """Get brand from enhanced data with fallbacks"""
    # Try main brand first
    if scraped_data.get('brand'):
        return clean_string(scraped_data['brand'])
    
    # Try preview brand from enhanced scraper
    enhancement_metadata = scraped_data.get('enhancement_metadata', {})
    preview_data = enhancement_metadata.get('preview_data', {})
    
    if preview_data.get('brand'):
        return clean_string(preview_data['brand'])
    
    # Extract from title if available
    title = scraped_data.get('title') or preview_data.get('title', '')
    if title:
        return extract_brand_from_title(title)
    
    return None

def get_model_from_enhanced_data(scraped_data: Dict[str, Any]) -> Optional[str]:
    """Get model from enhanced data with fallbacks"""
    # Try main model first
    if scraped_data.get('model'):
        return clean_string(scraped_data['model'])
    
    # Try preview model from enhanced scraper
    enhancement_metadata = scraped_data.get('enhancement_metadata', {})
    preview_data = enhancement_metadata.get('preview_data', {})
    
    if preview_data.get('model'):
        return clean_string(preview_data['model'])
    
    return None

def get_year_from_enhanced_data(scraped_data: Dict[str, Any]) -> Optional[int]:
    """Get year from enhanced data with fallbacks"""
    # Try main year first
    if scraped_data.get('year'):
        return safe_int(scraped_data['year'])
    
    # Try preview year from enhanced scraper
    enhancement_metadata = scraped_data.get('enhancement_metadata', {})
    preview_data = enhancement_metadata.get('preview_data', {})
    
    if preview_data.get('year'):
        return safe_int(preview_data['year'])
    
    # Try extracted_year field
    if scraped_data.get('extracted_year'):
        return safe_int(scraped_data['extracted_year'])
    
    return None

def get_price_from_enhanced_data(scraped_data: Dict[str, Any]) -> Optional[str]:
    """Get price_raw from enhanced data with fallbacks"""
    # Try main price_raw first
    if scraped_data.get('price_raw'):
        return clean_string(scraped_data['price_raw'])
    
    # Try preview price from enhanced scraper
    enhancement_metadata = scraped_data.get('enhancement_metadata', {})
    preview_data = enhancement_metadata.get('preview_data', {})
    
    if preview_data.get('price_text'):
        return clean_string(preview_data['price_text'])
    
    return None

def get_images_from_enhanced_data(scraped_data: Dict[str, Any]) -> Optional[List]:
    """Get images with enhanced handling of S3 URLs and original URLs"""
    images_data = {
        'original_urls': [],
        's3_urls': [],
        'processed_at': None
    }
    
    # Get original images
    original_images = scraped_data.get('images', [])
    if original_images:
        images_data['original_urls'] = original_images
    
    # Check for enhanced scraper preview images
    enhancement_metadata = scraped_data.get('enhancement_metadata', {})
    preview_data = enhancement_metadata.get('preview_data', {})
    
    if preview_data.get('image') and not original_images:
        images_data['original_urls'] = [preview_data['image']]
    
    # Check for S3 processed images (will be added by image processor)
    if scraped_data.get('s3_images'):
        images_data['s3_urls'] = scraped_data['s3_images']
        images_data['processed_at'] = datetime.now(timezone.utc).isoformat()
    
    # Return as JSON for database storage
    return images_data if (images_data['original_urls'] or images_data['s3_urls']) else None

def safe_json_list(value: Any) -> Optional[List]:
    """Safely convert value to JSON-serializable list"""
    if value is None:
        return None
    
    if isinstance(value, list):
        return value
    
    if isinstance(value, str):
        # Try to parse as JSON list
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Fallback to comma-separated
        if ',' in value:
            return [item.strip() for item in value.split(',') if item.strip()]
        return [value] if value.strip() else None
    
    return None

def extract_brand_from_title(title: str) -> Optional[str]:
    """Extract brand name from title"""
    common_brands = [
        'BMW', 'Mercedes', 'Audi', 'Volkswagen', 'VW', 'Ford', 'Opel', 
        'Renault', 'Peugeot', 'Citroën', 'Honda', 'Toyota', 'Nissan',
        'Mazda', 'Hyundai', 'Kia', 'Volvo', 'Skoda', 'SEAT', 'Fiat'
    ]
    
    title_upper = title.upper()
    for brand in common_brands:
        if brand.upper() in title_upper:
            return brand
    
    # Fallback: return first word if it looks like a brand
    first_word = title.split()[0] if title.split() else None
    if first_word and len(first_word) > 2 and first_word.isalpha():
        return first_word.title()
    
    return None

def generate_title_from_data(scraped_data: Dict[str, Any]) -> str:
    """Generate a title from available car data"""
    parts = []
    
    brand = get_brand_from_enhanced_data(scraped_data)
    if brand:
        parts.append(brand)
    
    model = get_model_from_enhanced_data(scraped_data)
    if model:
        parts.append(model)
    
    year = get_year_from_enhanced_data(scraped_data)
    if year:
        parts.append(str(year))
    
    fuel_type = scraped_data.get('fuel_type')
    if fuel_type:
        parts.append(fuel_type)
    
    if parts:
        return ' '.join(parts)
    
    # Ultimate fallback
    return 'Carro Usado'

# Utility functions (reused from original)
def clean_string(value: Any) -> Optional[str]:
    """Clean string values, handle None and empty strings"""
    if value is None:
        return None
    
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    
    return str(value).strip() if str(value).strip() else None

def safe_int(value: Any) -> Optional[int]:
    """Safely convert value to integer"""
    if value is None:
        return None
    
    try:
        if isinstance(value, (int, float)):
            return int(value)
        
        if isinstance(value, str):
            # Remove common non-numeric characters
            cleaned = value.replace(',', '').replace('.', '').replace(' ', '')
            if cleaned.isdigit():
                return int(cleaned)
    
    except (ValueError, TypeError):
        pass
    
    return None

def safe_float(value: Any) -> Optional[float]:
    """Safely convert value to float"""
    if value is None:
        return None
    
    try:
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            cleaned = value.replace(',', '.').replace(' ', '')
            return float(cleaned)
    
    except (ValueError, TypeError):
        pass
    
    return None

def safe_bool(value: Any) -> bool:
    """Safely convert value to boolean"""
    if value is None:
        return False
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'sim', 'verdadeiro')
    
    if isinstance(value, (int, float)):
        return bool(value)
    
    return False

# Compatibility function for backward compatibility
def transform_scraped_data(scraped_data: Dict[str, Any]) -> Dict[str, Any]:
    """Backward compatibility function"""
    return transform_enhanced_scraped_data(scraped_data)