"""
Authentication and Authorization
Basic JWT auth skeleton - expand for production
"""

import os
import logging
from typing import Optional
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import get_db
from .models import User

logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token scheme
bearer_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


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
    
    if current_user.role != "admin":
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
    if current_user.role == "admin":
        return True
    
    # Check case assignment
    from .models import CaseAssignment
    
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
API_KEYS = {
    os.getenv("API_KEY_ADMIN", "admin-key-change-me"): "admin",
    os.getenv("API_KEY_USER", "user-key-change-me"): "user",
}


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
