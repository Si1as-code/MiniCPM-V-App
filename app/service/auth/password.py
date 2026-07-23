import hashlib
import logging
import os
import random
import time
from typing import Optional

logger = logging.getLogger(__name__)

# 使用 hashlib.pbkdf2_hmac 替代 passlib，避免 bcrypt 5.x 版本兼容问题
# 生产环境建议使用 argon2 或 bcrypt（需固定版本）
HASH_ITERATIONS = 600000
HASH_SALT_LENGTH = 32

# 验证码存储（模拟，生产环境使用 Redis）
# key: phone, value: {"code": "123456", "expire_at": timestamp}
SMS_CODE_STORE: dict = {}


def hash_password(password: str) -> str:
    """
    使用 PBKDF2-SHA256 哈希密码
    格式: pbkdf2$iterations$salt$hash
    """
    salt = os.urandom(HASH_SALT_LENGTH)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        HASH_ITERATIONS,
    )
    return f"pbkdf2${HASH_ITERATIONS}${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    hashed_password 格式: pbkdf2$iterations$salt$hash
    """
    try:
        parts = hashed_password.split("$")
        if parts[0] != "pbkdf2" or len(parts) != 4:
            logger.warning("不支持的密码哈希格式")
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        stored_hash = parts[3]
        key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iterations,
        )
        return key.hex() == stored_hash
    except Exception as e:
        logger.error(f"密码验证失败: {e}")
        return False


def generate_sms_code() -> str:
    return str(random.randint(100000, 999999))


async def send_sms_code(phone: str) -> bool:
    """
    发送短信验证码
    生产环境应调用阿里云/腾讯云 SMS API
    """
    code = generate_sms_code()
    SMS_CODE_STORE[phone] = {
        "code": code,
        "expire_at": time.time() + 300,  # 5 分钟有效期
    }
    logger.info(f"[模拟] 发送验证码 {code} 到手机 {phone}")
    # TODO: 接入真实 SMS 服务
    # from service.config import service_config
    # aliyun_sms.send_sms(
    #     phone=phone,
    #     sign_name=service_config.sms_sign_name,
    #     template_code=service_config.sms_template_code,
    #     template_param={"code": code},
    # )
    return True


def verify_sms_code(phone: str, code: str) -> bool:
    stored = SMS_CODE_STORE.get(phone)
    if not stored:
        logger.warning(f"验证码不存在: {phone}")
        return False
    if time.time() > stored["expire_at"]:
        logger.warning(f"验证码已过期: {phone}")
        del SMS_CODE_STORE[phone]
        return False
    if stored["code"] != code:
        logger.warning(f"验证码错误: {phone}")
        return False
    del SMS_CODE_STORE[phone]
    return True


async def login_with_password(
    phone: str, password: str, db_pool=None
) -> Optional[str]:
    """
    密码登录
    Args:
        phone: 手机号
        password: 明文密码
        db_pool: 数据库连接池（可选，用于查询用户）
    Returns:
        user_id 或 None
    """
    # TODO: 接入 PostgreSQL 查询用户
    # async with db_pool.acquire() as conn:
    #     row = await conn.fetchrow(
    #         "SELECT user_id, password_hash FROM users WHERE phone = $1", phone
    #     )
    #     if row and verify_password(password, row["password_hash"]):
    #         return row["user_id"]
    logger.warning("密码登录: 数据库查询未实现，返回模拟 user_id")
    return "mock_user_id" if phone and password else None


async def register_with_password(
    phone: str, password: str, sms_code: str, db_pool=None
) -> Optional[str]:
    """
    注册新用户
    Args:
        phone: 手机号
        password: 明文密码
        sms_code: 短信验证码
        db_pool: 数据库连接池
    Returns:
        user_id 或 None
    """
    if not verify_sms_code(phone, sms_code):
        logger.warning(f"注册失败: 验证码错误 {phone}")
        return None

    # TODO: 接入 PostgreSQL 插入用户
    # password_hash = hash_password(password)
    # async with db_pool.acquire() as conn:
    #     row = await conn.fetchrow(
    #         "INSERT INTO users (phone, password_hash) VALUES ($1, $2) RETURNING user_id",
    #         phone, password_hash,
    #     )
    #     return row["user_id"]
    logger.warning("注册: 数据库插入未实现，返回模拟 user_id")
    return "mock_user_id"