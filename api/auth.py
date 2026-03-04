"""
Authentication module for NexCompli.

Provides JWT token-based authentication, password hashing, and user verification.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from config.settings import get_settings
from database.db_setup import get_db
from database.user import User

# Logger setup
logger = logging.getLogger(__name__)

# HTTP status codes
HTTP_BAD_REQUEST = 400

settings = get_settings()
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.jwt_refresh_token_expire_days
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/token')


def verify_password(plain_password: str, hashed_password: str) ->bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) ->str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[
    timedelta]=None) ->str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=
            ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({'exp': expire, 'type': 'access'})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=
        ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) ->str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=
        REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({'exp': expire, 'type': 'refresh'})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=
        ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str=Depends(oauth2_scheme), db: Session=
    Depends(get_db)) ->User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(status_code=status.
        HTTP_401_UNAUTHORIZED, detail='Could not validate credentials',
        headers={'WWW-Authenticate': 'Bearer'})
    try:
        print(
            f"[AUTH DEBUG] JWT Secret: {settings.jwt_secret[:10] if settings.jwt_secret else 'None'}..."
            )
        logger.info('[AUTH DEBUG] Token to decode: %s...' % token[:50])
        logger.info('[AUTH DEBUG] Algorithm: %s' % ALGORITHM)
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM]
            )
        user_id: Optional[str] = payload.get('sub')
        if user_id is None or payload.get('type') != 'access':
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User=Depends(get_current_user)
    ) ->User:
    """Ensure the current user is active."""
    if hasattr(current_user, 'is_active') and getattr(current_user,
        'is_active', True) is False:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=
            'Inactive user')
    return current_user
