import secrets
import string
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(user_id: int, company_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "company_id": company_id,
        "role": role,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire}
    return jwt.encode(payload, settings.jwt_refresh_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise JWTError("Invalid token type")
        return payload
    except JWTError as exc:
        raise ValueError("Invalid access token") from exc


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_refresh_secret, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise JWTError("Invalid token type")
        return payload
    except JWTError as exc:
        raise ValueError("Invalid refresh token") from exc


def generate_invite_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))
