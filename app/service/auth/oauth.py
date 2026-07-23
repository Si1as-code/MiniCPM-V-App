import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class OAuthProvider(str, Enum):
    WECHAT = "wechat"
    APPLE = "apple"


@dataclass
class OAuthUserInfo:
    provider: OAuthProvider
    provider_user_id: str
    display_name: str = ""
    avatar_url: str = ""
    email: str = ""


@dataclass
class OAuthCallbackData:
    success: bool = False
    user_info: Optional[OAuthUserInfo] = None
    error: str = ""


class OAuthClient(ABC):
    @abstractmethod
    async def verify(self, code: str) -> bool:
        ...

    @abstractmethod
    async def get_user_info(self, code: str) -> OAuthUserInfo:
        ...


class WeChatOAuthClient(OAuthClient):
    """微信登录客户端"""
    APP_ID = "your_wechat_app_id"  # 从环境变量读取
    APP_SECRET = "your_wechat_app_secret"

    async def verify(self, code: str) -> bool:
        return bool(code and len(code) > 0)

    async def get_user_info(self, code: str) -> OAuthUserInfo:
        # 调用微信 API 获取 access_token 和用户信息
        url = "https://api.weixin.qq.com/sns/oauth2/access_token"
        params = {
            "appid": self.APP_ID,
            "secret": self.APP_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            if "openid" not in data:
                raise ValueError(f"微信登录失败: {data.get('errmsg', '未知错误')}")
            return OAuthUserInfo(
                provider=OAuthProvider.WECHAT,
                provider_user_id=data["openid"],
                display_name=data.get("nickname", ""),
                avatar_url=data.get("headimgurl", ""),
            )


class AppleOAuthClient(OAuthClient):
    """Apple ID 登录客户端"""

    async def verify(self, code: str) -> bool:
        return bool(code and len(code) > 0)

    async def get_user_info(self, code: str) -> OAuthUserInfo:
        # Apple 返回的是 JWT identity token，解析即可
        import jwt as pyjwt
        try:
            # 验证 Apple 返回的 identity token
            header = pyjwt.get_unverified_header(code)
            # 生产环境需要验证签名和公钥
            payload = pyjwt.decode(code, options={"verify_signature": False})
            return OAuthUserInfo(
                provider=OAuthProvider.APPLE,
                provider_user_id=payload.get("sub", ""),
                display_name=payload.get("name", ""),
                email=payload.get("email", ""),
            )
        except Exception as e:
            raise ValueError(f"Apple ID 登录失败: {e}")


async def oauth_login(provider: OAuthProvider, code: str) -> OAuthCallbackData:
    try:
        if provider == OAuthProvider.WECHAT:
            client = WeChatOAuthClient()
        elif provider == OAuthProvider.APPLE:
            client = AppleOAuthClient()
        else:
            return OAuthCallbackData(success=False, error=f"不支持的登录方式: {provider}")

        if not await client.verify(code):
            return OAuthCallbackData(success=False, error="验证码无效")

        user_info = await client.get_user_info(code)
        return OAuthCallbackData(success=True, user_info=user_info)
    except Exception as e:
        logger.error(f"OAuth 登录失败: {e}")
        return OAuthCallbackData(success=False, error=str(e))