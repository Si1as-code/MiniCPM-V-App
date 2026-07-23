import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from service.config import service_config

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


@dataclass
class TokenData:
    user_id: str
    token_type: str = "access"
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        seconds=service_config.jwt_access_expire
    )
    payload = {
        "user_id": user_id,
        "token_type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, service_config.jwt_secret, algorithm=service_config.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        seconds=service_config.jwt_refresh_expire
    )
    payload = {
        "user_id": user_id,
        "token_type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, service_config.jwt_secret, algorithm=service_config.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            service_config.jwt_secret,
            algorithms=[service_config.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Token",
        )


def verify_token(token: str) -> bool:
    try:
        decode_token(token)
        return True
    except HTTPException:
        return False


async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证信息",
        )
    payload = decode_token(credentials.credentials)
    return payload.get("user_id", "")