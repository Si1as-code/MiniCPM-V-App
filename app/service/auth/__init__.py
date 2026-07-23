"""
用户认证模块
提供 JWT 认证、第三方登录、手机号验证码登录。
"""

from service.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
    decode_token,
    get_current_user_id,
    TokenData,
)
from service.auth.oauth import OAuthProvider, OAuthUserInfo
from service.auth.password import (
    hash_password,
    verify_password,
    send_sms_code,
    verify_sms_code,
    login_with_password,
    register_with_password,
)

__all__ = [
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "decode_token",
    "get_current_user_id",
    "TokenData",
    "OAuthProvider",
    "OAuthUserInfo",
    "hash_password",
    "verify_password",
    "send_sms_code",
    "verify_sms_code",
    "login_with_password",
    "register_with_password",
]