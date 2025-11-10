"""
Authentication and Authorization
Basic JWT auth skeleton - expand for production
"""

import os
import logging
import bcrypt
from typing import Optional
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy.orm import Session

from infra.database import get_db
from infra.models import User, UserRole

logger = logging.getLogger(__name__)

# Configuration
# Get environment mode
APP_ENV = os.getenv("APP_ENV", "production").lower()

# SECURITY: Always require JWT secret (no fallbacks)
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError(
        "JWT_SECRET_KEY environment variable is required for all environments.\n"
        "Generate a secure secret (minimum 32 bytes of entropy) with:\n"
        "  openssl rand -hex 32\n"
        "Then set: JWT_SECRET_KEY=<generated-key> in your .env file or environment.\n"
        "For tests, use a fixture to inject an ephemeral random secret."
    )

# Validate secret strength (minimum 32 bytes = 64 hex chars)
if len(SECRET_KEY) < 64:
    logger.warning(
        f"⚠️ JWT_SECRET_KEY appears weak (only {len(SECRET_KEY)} chars). "
        "Recommended: Use 'openssl rand -hex 32' for 32 bytes of entropy."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Bearer token scheme
bearer_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash using bcrypt directly"""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt directly"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Token payload
        expires_delta: Optional expiration time
        
    Returns:
        JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.JWTError as e:
        logger.warning(f"Invalid token: {e}")
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current authenticated user from JWT token
    For now, this is optional (returns None if no auth)
    Enable strict auth by removing Optional and raising exceptions
    
    Args:
        credentials: Bearer token from request
        db: Database session
        
    Returns:
        User object if authenticated, None otherwise
    """
    # For Phase 1, auth is optional
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if not payload:
        # For strict auth, raise HTTPException here
        return None
    
    user_email = payload.get("sub")
    if not user_email:
        return None
    
    user = db.query(User).filter(User.email == user_email).first()
    
    if not user or not user.is_active:
        return None
    
    return user


async def require_auth(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """
    Require authentication (any valid user)
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User if authenticated
        
    Raises:
        HTTPException: If not authenticated
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return current_user


async def require_admin(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """
    Require admin role
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User if admin
        
    Raises:
        HTTPException: If not admin
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user


async def require_case_access(
    case_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> bool:
    """
    Check if user has access to a case
    
    Args:
        case_id: Case ID
        current_user: Current user
        db: Database session
        
    Returns:
        True if has access
        
    Raises:
        HTTPException: If no access
    """
    # For Phase 1, allow all access if no auth
    if not current_user:
        return True
    
    # Admins have access to all cases
    if current_user.role == UserRole.ADMIN:
        return True
    
    # Check case assignment
    from infra.models import CaseAssignment
    
    assignment = db.query(CaseAssignment).filter(
        CaseAssignment.case_id == case_id,
        CaseAssignment.user_id == current_user.id
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this case"
        )
    
    return True


# ============================================================================
# Auth Endpoints (add to main.py)
# ============================================================================

async def login(
    email: str,
    password: str,
    db: Session
) -> dict:
    """
    Authenticate user and return token
    
    Args:
        email: User email
        password: Plain password
        db: Database session
        
    Returns:
        Dict with access token
    """
    user = db.query(User).filter(User.email == email).first()
    
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    # Create token
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role.value}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": user.email,
            "name": user.name,
            "role": user.role.value
        }
    }


# Simple API key auth as alternative (for Phase 1)
# Build API_KEYS from environment, skip if not set
_admin_key = os.getenv("API_KEY_ADMIN")
_user_key = os.getenv("API_KEY_USER")

API_KEYS = {}
if _admin_key:
    API_KEYS[_admin_key] = "admin"
if _user_key:
    API_KEYS[_user_key] = "user"

if not API_KEYS:
    logger.warning(
        "No API keys configured. API key authentication is disabled. "
        "Set API_KEY_ADMIN and/or API_KEY_USER environment variables to enable."
    )


async def get_api_key_user(
    api_key: Optional[str] = None
) -> Optional[dict]:
    """
    Simple API key authentication (temporary for Phase 1)
    
    Args:
        api_key: API key from header or query param
        
    Returns:
        User info dict if valid key
    """
    if not api_key:
        return None
    
    role = API_KEYS.get(api_key)
    if not role:
        return None
    
    return {
        "role": role,
        "api_key": api_key[:8] + "..."  # Partial key for logging
    }
