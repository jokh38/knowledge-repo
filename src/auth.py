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
    """Simple token verification"""
    token = credentials.credentials
    expected_token = os.getenv("API_TOKEN")
    
    # If API_TOKEN is set, use simple token verification
    if expected_token:
        if token != expected_token:
            logger.warning(f"Invalid token attempt: {token[:10]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return token
    
    # Otherwise, use JWT verification
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
    except jwt.PyJWTError:
        logger.warning(f"JWT decode failed for token: {token[:10]}...")
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

def get_current_user(token: str = Depends(verify_token)):
    """Get current authenticated user"""
    # In a real implementation, you would fetch user details from database
    return {"username": token}

def optional_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))):
    """Optional authentication - doesn't raise error if no token provided"""
    if credentials is None:
        return None
    return verify_token(credentials)