#!/usr/bin/env python3
"""
PostgreSQL User Management System for Car Marketplace
Maps phone numbers to users and their cars using PostgreSQL database
"""

import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncpg
import asyncio

logger = logging.getLogger(__name__)

class PostgreSQLUserManager:
    """Manages users and their associated cars using PostgreSQL database"""
    
    def __init__(self, database_url: str = "postgresql://car_user:dev_password@localhost:5432/car_marketplace_dev"):
        """Initialize the PostgreSQL user manager"""
        self.database_url = database_url
        self.pool = None
        logger.info("PostgreSQL UserManager initialized")
    
    async def initialize_pool(self):
        """Initialize the connection pool"""
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=2,
                    max_size=10,
                    command_timeout=60
                )
                logger.info("PostgreSQL connection pool created successfully")
            except Exception as e:
                logger.error(f"Failed to create PostgreSQL connection pool: {e}")
                raise
    
    async def close_pool(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")
    
    def _normalize_phone(self, phone_number: str) -> str:
        """
        Normalize phone number format
        
        Args:
            phone_number: Raw phone number
            
        Returns:
            Normalized phone number
        """
        if not phone_number:
            return ""
        
        # Remove all non-digit and non-+ characters
        clean_phone = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        
        # Add +351 prefix if missing (Portuguese numbers)
        if clean_phone.startswith('9') and len(clean_phone) == 9:
            clean_phone = '+351' + clean_phone
        elif clean_phone.startswith('351') and len(clean_phone) == 12:
            clean_phone = '+' + clean_phone
        
        return clean_phone
    
    async def create_or_get_user(self, phone_number: str, car_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a new user or get existing user by phone number
        
        Args:
            phone_number: User's phone number
            car_data: Optional dictionary containing car information for user details
            
        Returns:
            Dictionary with user creation/retrieval results
        """
        if not phone_number:
            return {
                'success': False,
                'error': 'Phone number required',
                'user_id': None,
                'user': None
            }
        
        await self.initialize_pool()
        
        try:
            # Normalize phone number
            normalized_phone = self._normalize_phone(phone_number)
            if not normalized_phone:
                return {
                    'success': False,
                    'error': 'Invalid phone number format',
                    'user_id': None,
                    'user': None
                }
            
            async with self.pool.acquire() as conn:
                # Try to get existing user
                existing_user = await conn.fetchrow(
                    "SELECT * FROM users WHERE phone_number = $1",
                    normalized_phone
                )
                
                if existing_user:
                    # User exists, update last_seen and return
                    await conn.execute(
                        """
                        UPDATE users 
                        SET last_seen = $1, updated_at = $1
                        WHERE id = $2
                        """,
                        datetime.now(),
                        existing_user['id']
                    )
                    
                    user_dict = dict(existing_user)
                    user_dict['last_seen'] = datetime.now()
                    user_dict['updated_at'] = datetime.now()
                    
                    logger.info(f"Retrieved existing user {existing_user['id']} for phone {normalized_phone}")
                    return {
                        'success': True,
                        'user_id': existing_user['id'],
                        'user': user_dict,
                        'created': False,
                        'error': None
                    }
                
                # Create new user
                user_name = None
                user_city = None
                
                # Extract user info from car data if available
                if car_data:
                    user_name = car_data.get('seller_name')
                    user_city = car_data.get('city') or car_data.get('location')
                
                # Insert new user
                new_user = await conn.fetchrow(
                    """
                    INSERT INTO users (
                        phone_number, name, city, total_cars, active_listings, 
                        created_at, updated_at, last_seen, is_active
                    ) VALUES (
                        $1, $2, $3, 0, 0, $4, $4, $4, true
                    ) RETURNING *
                    """,
                    normalized_phone,
                    user_name,
                    user_city,
                    datetime.now()
                )
                
                logger.info(f"Created new user {new_user['id']} for phone {normalized_phone}")
                return {
                    'success': True,
                    'user_id': new_user['id'],
                    'user': dict(new_user),
                    'created': True,
                    'error': None
                }
                
        except Exception as e:
            logger.error(f"Error creating/getting user for phone {phone_number}: {e}")
            return {
                'success': False,
                'error': str(e),
                'user_id': None,
                'user': None
            }
    
    async def update_user_car_stats(self, user_id: int) -> bool:
        """
        Update user's car statistics (total_cars, active_listings)
        
        Args:
            user_id: User's ID
            
        Returns:
            True if successful, False otherwise
        """
        await self.initialize_pool()
        
        try:
            async with self.pool.acquire() as conn:
                # Count user's cars
                car_stats = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) as total_cars,
                        COUNT(*) as active_listings  -- Assuming all scraped cars are active
                    FROM cars 
                    WHERE user_id = $1
                    """,
                    user_id
                )
                
                # Update user statistics
                await conn.execute(
                    """
                    UPDATE users 
                    SET 
                        total_cars = $1,
                        active_listings = $2,
                        updated_at = $3
                    WHERE id = $4
                    """,
                    car_stats['total_cars'],
                    car_stats['active_listings'],
                    datetime.now(),
                    user_id
                )
                
                logger.info(f"Updated stats for user {user_id}: {car_stats['total_cars']} cars")
                return True
                
        except Exception as e:
            logger.error(f"Error updating user {user_id} stats: {e}")
            return False
    
    async def get_user_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Get user data by phone number
        
        Args:
            phone_number: User's phone number
            
        Returns:
            User data dictionary or None if not found
        """
        await self.initialize_pool()
        
        try:
            normalized_phone = self._normalize_phone(phone_number)
            if not normalized_phone:
                return None
            
            async with self.pool.acquire() as conn:
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE phone_number = $1",
                    normalized_phone
                )
                
                return dict(user) if user else None
                
        except Exception as e:
            logger.error(f"Error getting user by phone {phone_number}: {e}")
            return None
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user data by user ID
        
        Args:
            user_id: User's unique ID
            
        Returns:
            User data dictionary or None if not found
        """
        await self.initialize_pool()
        
        try:
            async with self.pool.acquire() as conn:
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE id = $1",
                    user_id
                )
                
                return dict(user) if user else None
                
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            return None
    
    async def get_user_cars(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all cars associated with a user
        
        Args:
            user_id: User's unique ID
            
        Returns:
            List of car dictionaries
        """
        await self.initialize_pool()
        
        try:
            async with self.pool.acquire() as conn:
                cars = await conn.fetch(
                    """
                    SELECT * FROM cars 
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    """,
                    user_id
                )
                
                return [dict(car) for car in cars]
                
        except Exception as e:
            logger.error(f"Error getting cars for user {user_id}: {e}")
            return []
    
    async def get_all_users(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get all users with pagination
        
        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            
        Returns:
            List of user dictionaries
        """
        await self.initialize_pool()
        
        try:
            async with self.pool.acquire() as conn:
                users = await conn.fetch(
                    """
                    SELECT * FROM users 
                    ORDER BY updated_at DESC
                    LIMIT $1 OFFSET $2
                    """,
                    limit,
                    offset
                )
                
                return [dict(user) for user in users]
                
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    async def get_user_statistics(self) -> Dict[str, Any]:
        """
        Get overall user statistics
        
        Returns:
            Statistics dictionary
        """
        await self.initialize_pool()
        
        try:
            async with self.pool.acquire() as conn:
                # Get basic stats
                stats = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) as total_users,
                        COUNT(CASE WHEN is_active THEN 1 END) as active_users,
                        SUM(total_cars) as total_cars_across_users,
                        SUM(active_listings) as total_active_listings,
                        AVG(total_cars) as avg_cars_per_user
                    FROM users
                    """
                )
                
                # Get top cities
                top_cities = await conn.fetch(
                    """
                    SELECT city, COUNT(*) as user_count
                    FROM users 
                    WHERE city IS NOT NULL 
                    GROUP BY city 
                    ORDER BY user_count DESC 
                    LIMIT 10
                    """
                )
                
                return {
                    'total_users': stats['total_users'],
                    'active_users': stats['active_users'],
                    'total_cars': stats['total_cars_across_users'] or 0,
                    'total_active_listings': stats['total_active_listings'] or 0,
                    'avg_cars_per_user': float(stats['avg_cars_per_user']) if stats['avg_cars_per_user'] else 0,
                    'top_cities': [{'city': row['city'], 'users': row['user_count']} for row in top_cities]
                }
                
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return {'error': str(e)}
    
    async def link_car_to_user(self, car_id: int, phone_number: str, car_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Link a car to a user by phone number (creates user if doesn't exist)
        
        Args:
            car_id: Car's database ID
            phone_number: User's phone number
            car_data: Car data for user creation context
            
        Returns:
            Dictionary with linking results
        """
        try:
            # Get or create user
            user_result = await self.create_or_get_user(phone_number, car_data)
            
            if not user_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to create/get user: {user_result['error']}",
                    'user_id': None,
                    'car_id': car_id
                }
            
            user_id = user_result['user_id']
            
            await self.initialize_pool()
            
            # Link car to user
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE cars SET user_id = $1 WHERE id = $2",
                    user_id,
                    car_id
                )
            
            # Update user statistics
            await self.update_user_car_stats(user_id)
            
            logger.info(f"Successfully linked car {car_id} to user {user_id}")
            return {
                'success': True,
                'user_id': user_id,
                'car_id': car_id,
                'user_created': user_result.get('created', False),
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Error linking car {car_id} to phone {phone_number}: {e}")
            return {
                'success': False,
                'error': str(e),
                'user_id': None,
                'car_id': car_id
            }

# Async context manager for easy usage
class UserManagerContext:
    """Context manager for PostgreSQL User Manager"""
    
    def __init__(self, database_url: str = "postgresql://car_user:dev_password@localhost:5432/car_marketplace_dev"):
        self.manager = PostgreSQLUserManager(database_url)
    
    async def __aenter__(self):
        await self.manager.initialize_pool()
        return self.manager
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.manager.close_pool()

# Example usage
async def main():
    """Example usage of PostgreSQL User Manager"""
    async with UserManagerContext() as user_manager:
        # Create/get user
        result = await user_manager.create_or_get_user(
            "+351929816076",
            {"seller_name": "João Silva", "city": "Lisboa"}
        )
        
        if result['success']:
            print(f"User ID: {result['user_id']}")
            print(f"Created: {result.get('created', False)}")
            
            # Get user stats
            stats = await user_manager.get_user_statistics()
            print(f"Total users: {stats['total_users']}")
        else:
            print(f"Error: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())