"""
Supabase client initialization and connection management with authentication support
"""

import os
import logging
from typing import Optional
from supabase import create_client, Client
from config import Config

logger = logging.getLogger(__name__)

class SupabaseClient:
    """Supabase client wrapper with connection management and error handling"""

    def __init__(self):
        self._client: Optional[Client] = None
        self._connected = False
        self._connection_error = None

    def connect(self) -> bool:
        """
        Initialize connection to Supabase

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if not Config.SUPABASE_URL or not Config.SUPABASE_SERVICE_KEY:
                self._connection_error = "Supabase URL or Service Key not configured"
                logger.error(self._connection_error)
                return False

            # Create client with service key for full access
            self._client = create_client(
                Config.SUPABASE_URL,
                Config.SUPABASE_SERVICE_KEY
            )

            # Test connection by making a simple query
            if self.test_connection():
                self._connected = True
                self._connection_error = None
                logger.info("Successfully connected to Supabase")
                return True
            else:
                self._connected = False
                return False

        except Exception as e:
            self._connection_error = f"Failed to connect to Supabase: {str(e)}"
            logger.error(self._connection_error)
            self._connected = False
            return False

    def test_connection(self) -> bool:
        """
        Test the database connection by running a simple query

        Returns:
            bool: True if connection is working, False otherwise
        """
        try:
            if not self._client:
                return False

            # Test with a simple query - try to select from clients table
            result = self._client.table('clients').select('id').limit(1).execute()
            return True

        except Exception as e:
            self._connection_error = f"Connection test failed: {str(e)}"
            logger.error(self._connection_error)
            return False

    def get_client(self) -> Optional[Client]:
        """
        Get the Supabase client instance

        Returns:
            Optional[Client]: The client instance if connected, None otherwise
        """
        if not self._connected and not self.connect():
            return None
        return self._client

    def is_connected(self) -> bool:
        """
        Check if client is connected to Supabase

        Returns:
            bool: True if connected, False otherwise
        """
        return self._connected and self._client is not None

    def get_connection_error(self) -> Optional[str]:
        """
        Get the last connection error message

        Returns:
            Optional[str]: Error message if any, None otherwise
        """
        return self._connection_error

    def disconnect(self):
        """Close the connection to Supabase"""
        if self._client:
            # Note: python-supabase doesn't have explicit close method
            # The connection will be cleaned up automatically
            self._client = None
            self._connected = False
            logger.info("Disconnected from Supabase")

# Global client instance
_supabase_client = SupabaseClient()

def get_supabase_client() -> SupabaseClient:
    """
    Get the global Supabase client instance

    Returns:
        SupabaseClient: The global client instance
    """
    return _supabase_client

def get_supabase() -> Optional[Client]:
    """
    Get the Supabase client, connecting if necessary

    Returns:
        Optional[Client]: Supabase client if available, None if connection failed
    """
    client = get_supabase_client()
    return client.get_client()

def test_database_connection() -> dict:
    """
    Test database connection and return status

    Returns:
        dict: Connection status with details
    """
    client = get_supabase_client()

    if client.is_connected():
        return {
            'connected': True,
            'status': 'healthy',
            'message': 'Database connection is active'
        }

    # Try to connect
    if client.connect():
        return {
            'connected': True,
            'status': 'healthy',
            'message': 'Database connection established'
        }

    return {
        'connected': False,
        'status': 'error',
        'message': client.get_connection_error() or 'Unknown connection error'
    }

def init_database():
    """
    Initialize database connection on application startup

    Returns:
        bool: True if initialization successful, False otherwise
    """
    client = get_supabase_client()
    success = client.connect()

    if success:
        logger.info("Database initialized successfully")
    else:
        logger.warning(f"Database initialization failed: {client.get_connection_error()}")
        logger.warning("Application will continue without database functionality")

    return success

def get_authenticated_supabase(access_token: str = None) -> Optional[Client]:
    """
    Get Supabase client with authentication context for RLS

    Args:
        access_token: User's access token for authentication

    Returns:
        Optional[Client]: Authenticated Supabase client or None
    """
    try:
        # Create a new client instance for the authenticated user
        client = create_client(
            Config.SUPABASE_URL,
            Config.SUPABASE_ANON_KEY
        )

        # Set the auth context if token is provided
        if access_token:
            # Set the auth header for RLS to work
            # Note: In practice, you would store and use both access and refresh tokens
            client.postgrest.auth(access_token)

        return client

    except Exception as e:
        logger.error(f"Error creating authenticated Supabase client: {e}")
        return None

def set_user_context(client: Client, user_id: str) -> Client:
    """
    Set user context for RLS policies

    Args:
        client: Supabase client
        user_id: User UUID for RLS context

    Returns:
        Client: Client with user context set
    """
    try:
        # For RLS to work properly, we need to set the auth context
        # This ensures that auth.uid() returns the correct user ID in policies
        if hasattr(client, 'set_auth_context'):
            client.set_auth_context(user_id)

        return client

    except Exception as e:
        logger.warning(f"Could not set user context: {e}")
        return client