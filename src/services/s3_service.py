#!/usr/bin/env python3
"""
AWS S3 Service for Car Image Upload and Management
Handles image uploads to S3 and generates presigned URLs
"""

import io
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from PIL import Image

# Import local config
from config_loader import get_config

logger = logging.getLogger(__name__)

class S3Service:
    """Service for handling AWS S3 operations for car images"""
    
    def __init__(self):
        """Initialize S3 client with configured credentials"""
        self.s3_client = None
        self.config = get_config()
        s3_config = self.config.get_s3_config()
        self.bucket_name = s3_config.get('bucket_name')
        self.region = s3_config.get('region')
        self.presigned_url_expiry = s3_config.get('presigned_url_expiry', 3600)
        
        self._initialize_s3_client()
    
    def _initialize_s3_client(self):
        """Initialize the S3 client with error handling"""
        try:
            # Initialize with explicit credentials if provided
            aws_access_key = self.config.get('aws_s3.access_key_id') or os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_key = self.config.get('aws_s3.secret_access_key') or os.getenv('AWS_SECRET_ACCESS_KEY')
            
            if aws_access_key and aws_secret_key:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=self.region
                )
            else:
                # Use default credential chain (IAM roles, ~/.aws/credentials, etc.)
                self.s3_client = boto3.client('s3', region_name=self.region)
            
            # Test the connection
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 client initialized successfully for bucket: {self.bucket_name}")
            
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            self.s3_client = None
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"S3 bucket '{self.bucket_name}' not found. Will attempt to create it.")
                self._create_bucket_if_not_exists()
            else:
                logger.error(f"Error connecting to S3: {e}")
                self.s3_client = None
        except Exception as e:
            logger.error(f"Unexpected error initializing S3 client: {e}")
            self.s3_client = None
    
    def _create_bucket_if_not_exists(self):
        """Create S3 bucket if it doesn't exist"""
        try:
            if self.region == 'us-east-1':
                # us-east-1 doesn't need LocationConstraint
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            
            # Set bucket policy for public read access to images
            self._set_bucket_policy()
            
            logger.info(f"Created S3 bucket: {self.bucket_name}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                logger.info(f"S3 bucket {self.bucket_name} already exists")
            else:
                logger.error(f"Error creating S3 bucket: {e}")
                self.s3_client = None
    
    def _set_bucket_policy(self):
        """Set bucket policy to allow public read access to images"""
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{self.bucket_name}/*"
                }
            ]
        }
        
        try:
            self.s3_client.put_bucket_policy(
                Bucket=self.bucket_name,
                Policy=str(bucket_policy).replace("'", '"')
            )
        except ClientError as e:
            logger.warning(f"Could not set bucket policy: {e}")
    
    def is_available(self) -> bool:
        """Check if S3 service is available and properly configured"""
        return self.s3_client is not None
    
    def generate_s3_key(self, phone_number: str, image_url: str, image_index: int = 0) -> str:
        """
        Generate a structured S3 key for an image using phone-based folders
        
        Args:
            phone_number: Phone number for folder structure
            image_url: Original image URL
            image_index: Index of the image in the listing (0 for main image)
            
        Returns:
            S3 key path like: "car/phone_number/image_0.jpg"
        """
        # Extract file extension from URL
        parsed_url = urlparse(image_url)
        path = parsed_url.path
        ext = Path(path).suffix.lower()
        
        # Default to .jpg if no extension found
        if not ext or ext not in ['.jpg', '.jpeg', '.png', '.webp']:
            ext = '.jpg'
        
        # Clean phone number for folder name (remove spaces, special chars)
        clean_phone = ''.join(c for c in phone_number if c.isdigit())
        
        # Generate key with car/phone/image structure
        key = f"car/{clean_phone}/image_{image_index}{ext}"
        return key
    
    def optimize_image(self, image_data: bytes, max_size: int = None) -> bytes:
        """
        Optimize image for web usage
        
        Args:
            image_data: Raw image bytes
            max_size: Maximum width/height in pixels
            
        Returns:
            Optimized image bytes
        """
        if max_size is None:
            max_size = self.config.get('aws_s3.image_max_size', 1920)
        
        try:
            # Open image with PIL
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize if needed
                if img.width > max_size or img.height > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Save optimized image
                output = io.BytesIO()
                img.save(
                    output,
                    format='JPEG',
                    quality=self.config.get('aws_s3.image_quality', 85),
                    optimize=True
                )
                
                return output.getvalue()
                
        except Exception as e:
            logger.warning(f"Error optimizing image: {e}. Using original.")
            return image_data
    
    def upload_image(
        self, 
        image_data: bytes, 
        s3_key: str, 
        content_type: str = 'image/jpeg',
        optimize: bool = True
    ) -> Dict[str, Union[str, bool]]:
        """
        Upload image to S3
        
        Args:
            image_data: Raw image bytes
            s3_key: S3 key for the image
            content_type: MIME type of the image
            optimize: Whether to optimize the image before upload
            
        Returns:
            Dictionary with upload results
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'S3 service not available',
                's3_key': s3_key,
                's3_url': None
            }
        
        try:
            # Optimize image if requested
            if optimize:
                image_data = self.optimize_image(image_data)
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=image_data,
                ContentType=content_type,
                CacheControl='max-age=31536000',  # Cache for 1 year
                Metadata={
                    'uploaded_at': datetime.now().isoformat(),
                    'source': 'car-marketplace-scraper'
                }
            )
            
            # Generate S3 URL
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            logger.info(f"Successfully uploaded image to S3: {s3_key}")
            
            return {
                'success': True,
                'error': None,
                's3_key': s3_key,
                's3_url': s3_url,
                'size_bytes': len(image_data)
            }
            
        except ClientError as e:
            error_msg = f"AWS S3 error uploading {s3_key}: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                's3_key': s3_key,
                's3_url': None
            }
        except Exception as e:
            error_msg = f"Unexpected error uploading {s3_key}: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                's3_key': s3_key,
                's3_url': None
            }
    
    def generate_presigned_url(
        self, 
        s3_key: str, 
        expiration: int = None
    ) -> Optional[str]:
        """
        Generate a presigned URL for temporary access to an S3 object
        
        Args:
            s3_key: S3 key of the object
            expiration: URL expiration time in seconds
            
        Returns:
            Presigned URL string or None if failed
        """
        if not self.is_available():
            return None
        
        if expiration is None:
            expiration = self.presigned_url_expiry
        
        try:
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            
            logger.debug(f"Generated presigned URL for {s3_key}, expires in {expiration}s")
            return presigned_url
            
        except ClientError as e:
            logger.error(f"Error generating presigned URL for {s3_key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL for {s3_key}: {e}")
            return None
    
    def upload_image_from_url(self, image_url: str, s3_key: str) -> Optional[str]:
        """
        Download image from URL and upload to S3
        
        Args:
            image_url: URL of the image to download
            s3_key: S3 key for the uploaded image
            
        Returns:
            S3 URL if successful, None otherwise
        """
        import requests
        from urllib.parse import urlparse
        
        if not self.is_available():
            logger.warning("S3 service not available, skipping image upload")
            return None
        
        try:
            # Download image from URL
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(image_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Determine content type from URL or response
            content_type = response.headers.get('content-type', 'image/jpeg')
            if not content_type.startswith('image/'):
                content_type = 'image/jpeg'
            
            # Upload to S3
            upload_result = self.upload_image(
                image_data=response.content,
                s3_key=s3_key,
                content_type=content_type,
                optimize=True
            )
            
            if upload_result.get('success'):
                logger.debug(f"Successfully uploaded image from {image_url} to {s3_key}")
                return upload_result.get('s3_url')
            else:
                logger.error(f"Failed to upload image from {image_url}: {upload_result.get('error')}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Failed to download image from {image_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading image from {image_url}: {e}")
            return None
    
    def delete_image(self, s3_key: str) -> bool:
        """
        Delete an image from S3
        
        Args:
            s3_key: S3 key of the image to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            logger.info(f"Deleted image from S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Error deleting image {s3_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting image {s3_key}: {e}")
            return False
    
    def list_images_for_phone(self, phone_number: str) -> List[Dict[str, str]]:
        """
        List all images for a specific phone number
        
        Args:
            phone_number: The phone number
            
        Returns:
            List of dictionaries with image information
        """
        if not self.is_available():
            return []
        
        try:
            # Clean phone number for folder name
            clean_phone = ''.join(c for c in phone_number if c.isdigit())
            
            # Search for images with the phone in the key
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"car/{clean_phone}/",  # Search in car/phone directory
            )
            
            images = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    images.append({
                        's3_key': key,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        's3_url': f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"
                    })
            
            return images
            
        except ClientError as e:
            logger.error(f"Error listing images for phone {phone_number}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing images for phone {phone_number}: {e}")
            return []

# Global S3 service instance
s3_service = S3Service()