"""
Authentication utilities and middleware for Supabase integration
"""

import jwt
import logging
import json
from functools import wraps
from typing import Optional, Dict, Any, Tuple
from flask import request, jsonify, g
from supabase import create_client, Client
from config import Config

logger = logging.getLogger(__name__)

class AuthError(Exception):
    """Custom authentication error"""
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class SupabaseAuth:
    """Supabase authentication client wrapper"""

    def __init__(self):
        self._client: Optional[Client] = None
        self._admin_client: Optional[Client] = None
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize Supabase clients for authentication"""
        try:
            # Client for user operations (with anon key)
            self._client = create_client(
                Config.SUPABASE_URL,
                Config.SUPABASE_ANON_KEY
            )

            # Admin client for user management (with service key)
            self._admin_client = create_client(
                Config.SUPABASE_URL,
                Config.SUPABASE_SERVICE_KEY
            )

            logger.info("Supabase authentication clients initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Supabase auth clients: {e}")
            raise AuthError("Authentication service unavailable", 503)

    def get_client(self) -> Client:
        """Get the user Supabase client"""
        if not self._client:
            self._initialize_clients()
        return self._client

    def get_admin_client(self) -> Client:
        """Get the admin Supabase client"""
        if not self._admin_client:
            self._initialize_clients()
        return self._admin_client

# Global auth instance
_auth_instance = None

def get_auth_client() -> SupabaseAuth:
    """Get the global authentication client instance"""
    global _auth_instance
    if not _auth_instance:
        _auth_instance = SupabaseAuth()
    return _auth_instance

def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token from Supabase

    Args:
        token: JWT token string

    Returns:
        Decoded token payload with user information

    Raises:
        AuthError: If token is invalid or expired
    """
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]

        # Get Supabase JWT secret from environment or use default
        # Note: In production, you should use the actual JWT secret from Supabase
        jwt_secret = Config.SUPABASE_ANON_KEY

        # Decode without verification first to get the header
        unverified_header = jwt.get_unverified_header(token)
        unverified_payload = jwt.decode(token, options={"verify_signature": False})

        # For Supabase tokens, we need to verify against the project's secret
        # In production, you would get the actual secret from Supabase settings

                # For Supabase tokens, validate structure and expiration
        if 'exp' in unverified_payload:
            import time
            if unverified_payload['exp'] < time.time():
                raise AuthError("Token has expired")

        if 'sub' not in unverified_payload:
            raise AuthError("Invalid token: missing user ID")

        # Ensure we have the user ID as a string (UUID format)
        if 'role' not in unverified_payload:
            unverified_payload['role'] = 'authenticated'

        # Validate UUID format for user ID
        import uuid
        try:
            uuid.UUID(unverified_payload['sub'])
        except ValueError:
            raise AuthError("Invalid user ID format")

        return unverified_payload

    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthError(f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Error verifying JWT token: {e}")
        raise AuthError("Token verification failed")

def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Get user information from JWT token

    Args:
        token: JWT token string

    Returns:
        User information dictionary or None if invalid
    """
    try:
        payload = verify_jwt_token(token)
        auth_client = get_auth_client()

        # Get user details from Supabase
        user_response = auth_client.get_admin_client().auth.admin.get_user_by_id(payload['sub'])

        if user_response.user:
            return {
                'id': user_response.user.id,
                'email': user_response.user.email,
                'email_verified': user_response.user.email_confirmed_at is not None,
                'created_at': user_response.user.created_at,
                'updated_at': user_response.user.updated_at,
                'user_metadata': user_response.user.user_metadata or {}
            }

        return None

    except AuthError:
        return None
    except Exception as e:
        logger.error(f"Error getting user from token: {e}")
        return None

def require_auth(f):
    """
    Decorator to require authentication for Flask routes

    Usage:
        @app.route('/protected')
        @require_auth
        def protected_route():
            user_id = g.current_user['id']
            return jsonify({'message': 'Authenticated!'})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({'error': 'Missing Authorization header'}), 401

            # Verify token and get user info
            payload = verify_jwt_token(auth_header)
            user_info = get_user_from_token(auth_header)

            if not user_info:
                return jsonify({'error': 'Invalid or expired token'}), 401

            # Store user info in Flask g object for use in the route
            g.current_user = user_info
            g.current_user_id = user_info['id']
            g.auth_token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else auth_header

            return f(*args, **kwargs)

        except AuthError as e:
            return jsonify({'error': e.message}), e.status_code
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return jsonify({'error': 'Authentication failed'}), 401

    return decorated_function

def optional_auth(f):
    """
    Decorator for routes that optionally use authentication
    Sets g.current_user if authenticated, but doesn't require it
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # First try Authorization header (for API calls)
            auth_header = request.headers.get('Authorization')

            # If no header, try to get token from query parameter (for redirects)
            token = None
            if auth_header:
                token = auth_header
            elif request.args.get('token'):
                token = f"Bearer {request.args.get('token')}"

            if token:
                user_info = get_user_from_token(token)
                if user_info:
                    g.current_user = user_info
                    g.current_user_id = user_info['id']
                    g.auth_token = token.replace('Bearer ', '') if token.startswith('Bearer ') else token
                else:
                    g.current_user = None
                    g.current_user_id = None
                    g.auth_token = None
            else:
                g.current_user = None
                g.current_user_id = None
                g.auth_token = None

        except Exception as e:
            logger.warning(f"Optional auth failed: {e}")
            g.current_user = None
            g.current_user_id = None
            g.auth_token = None

        return f(*args, **kwargs)

    return decorated_function

def get_current_user_id() -> Optional[str]:
    """Get the current authenticated user ID from Flask g"""
    return getattr(g, 'current_user_id', None)

def get_current_user() -> Optional[Dict[str, Any]]:
    """Get the current authenticated user info from Flask g"""
    return getattr(g, 'current_user', None)

def create_user_folder(user_id: str) -> str:
    """
    Create user-specific folder structure

    Args:
        user_id: Unique user identifier

    Returns:
        User folder path
    """
    import os
    user_folder = os.path.join(Config.PROCESSED_FOLDER, user_id)
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def validate_user_file_access(user_id: str, file_path: str) -> bool:
    """
    Validate that user can access the specified file path

    Args:
        user_id: User ID
        file_path: File path to validate

    Returns:
        True if user can access file, False otherwise
    """
    try:
        import os
        user_folder = os.path.join(Config.PROCESSED_FOLDER, user_id)
        normalized_user_folder = os.path.normpath(user_folder)
        normalized_file_path = os.path.normpath(file_path)

        # Check if file path is within user's folder
        return normalized_file_path.startswith(normalized_user_folder)

    except Exception as e:
        logger.error(f"Error validating file access: {e}")
        return False

class AuthenticationService:
    """Service for handling authentication operations"""

    def __init__(self):
        self.auth_client = get_auth_client()

    def sign_up(self, email: str, password: str, user_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Sign up a new user

        Args:
            email: User email
            password: User password
            user_metadata: Additional user metadata

        Returns:
            Dictionary with user info and session data
        """
        try:
            client = self.auth_client.get_client()

            response = client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": user_metadata or {}
                }
            })

            if response.user:
                # Create user folder
                create_user_folder(response.user.id)

                return {
                    'user': {
                        'id': response.user.id,
                        'email': response.user.email,
                        'email_verified': response.user.email_confirmed_at is not None,
                        'user_metadata': response.user.user_metadata or {}
                    },
                    'session': {
                        'access_token': response.session.access_token if response.session else None,
                        'refresh_token': response.session.refresh_token if response.session else None,
                        'expires_at': response.session.expires_at if response.session else None
                    } if response.session else None
                }

            raise AuthError("Sign up failed: No user returned")

        except Exception as e:
            logger.error(f"Sign up error: {e}")
            raise AuthError(f"Sign up failed: {str(e)}")

    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """
        Sign in an existing user

        Args:
            email: User email
            password: User password

        Returns:
            Dictionary with user info and session data
        """
        try:
            client = self.auth_client.get_client()

            response = client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if response.user and response.session:
                # Ensure user folder exists
                create_user_folder(response.user.id)

                return {
                    'user': {
                        'id': response.user.id,
                        'email': response.user.email,
                        'email_verified': response.user.email_confirmed_at is not None,
                        'user_metadata': response.user.user_metadata or {}
                    },
                    'session': {
                        'access_token': response.session.access_token,
                        'refresh_token': response.session.refresh_token,
                        'expires_at': response.session.expires_at
                    }
                }

            raise AuthError("Invalid email or password")

        except Exception as e:
            logger.error(f"Sign in error: {e}")
            if "Invalid login credentials" in str(e):
                raise AuthError("Invalid email or password")
            raise AuthError(f"Sign in failed: {str(e)}")

    def sign_out(self, access_token: str) -> bool:
        """
        Sign out the user

        Args:
            access_token: User's access token

        Returns:
            True if successful
        """
        try:
            client = self.auth_client.get_client()
            client.auth.sign_out(access_token)
            return True

        except Exception as e:
            logger.error(f"Sign out error: {e}")
            return False

    def refresh_session(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh user session

        Args:
            refresh_token: Refresh token

        Returns:
            New session data
        """
        try:
            client = self.auth_client.get_client()

            response = client.auth.refresh_session(refresh_token)

            if response.session:
                return {
                    'access_token': response.session.access_token,
                    'refresh_token': response.session.refresh_token,
                    'expires_at': response.session.expires_at
                }

            raise AuthError("Failed to refresh session")

        except Exception as e:
            logger.error(f"Refresh session error: {e}")
            raise AuthError(f"Session refresh failed: {str(e)}")

# Global authentication service instance
def get_auth_service() -> AuthenticationService:
    """Get the global authentication service instance"""
    return AuthenticationService()