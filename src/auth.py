from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set in production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer for token authentication
security = HTTPBearer()

class TokenData:
    """Token data model"""
    username: Optional[str] = None

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """JWT token verification - unified authentication method"""
    token = credentials.credentials

    # Check for fallback simple token mode for backward compatibility
    expected_token = os.getenv("API_TOKEN")
    if expected_token and os.getenv("ENVIRONMENT") == "development":
        logger.warning("Using simple token verification in development mode. Consider switching to JWT.")
        if token != expected_token:
            logger.warning(f"Invalid token attempt: {token[:10]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return "development_user"

    # Use JWT verification (primary method)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except jwt.ExpiredSignatureError:
        logger.warning(f"Token expired: {token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        logger.warning(f"Invalid JWT token: {token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)

def authenticate_user(username: str, password: str) -> bool:
    """
    Authenticate user (placeholder implementation)
    In a real implementation, you would check against a database
    WARNING: This is only for development - use proper authentication in production!
    """
    # For development only - remove or replace with proper authentication in production
    if os.getenv("ENVIRONMENT") == "production":
        logger.error("Production environment detected - placeholder authentication not allowed")
        return False

    # This is a simple placeholder - in production, use a proper user database
    users = {
        "admin": get_password_hash("admin123"),
        "user": get_password_hash("user123")
    }

    if username not in users:
        return False

    return verify_password(password, users[username])

def get_current_user(token: str = Depends(verify_token)) -> dict:
    """Get current authenticated user"""
    # In a real implementation, you would fetch user details from database
    return {"username": token, "authenticated": True}

def optional_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))) -> Optional[dict]:
    """Optional authentication - doesn't raise error if no token provided"""
    if credentials is None:
        return None
    try:
        username = verify_token(credentials)
        return {"username": username, "authenticated": True}
    except HTTPException:
        return {"username": None, "authenticated": False}

def generate_api_token(username: str = "api_user") -> str:
    """Generate a JWT token for API usage"""
    data = {"sub": username}
    return create_access_token(data)

def validate_token_for_usage(token: str) -> dict:
    """Validate token and return user information"""
    try:
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        username = verify_token(credentials)
        return {"username": username, "valid": True}
    except HTTPException:
        return {"username": None, "valid": False}