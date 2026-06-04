import secrets
import string
import base64
import hashlib

from passlib.context import CryptContext
from cryptography.fernet import Fernet, InvalidToken

from app.common.settings import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify((password), hashed)


def generate_email_code() -> str:
    """
    Generate a secure 6-digit numeric OTP
    Example: 483920
    """
    return "".join(secrets.choice(string.digits) for _ in range(6))


def generate_api_key() -> str:
    """Generate unique API key with wa_ prefix"""
    return f"wa_{secrets.token_urlsafe(32)}"


def _get_fernet_key() -> bytes:
    """Generate Fernet key from encryption key"""
    key = settings.API_KEY_ENCRYPTION_KEY.encode()
    hashed = hashlib.sha256(key).digest()
    return base64.urlsafe_b64encode(hashed)


def encrypt_api_key(api_key: str) -> str:
    """Encrypt API key using Fernet"""
    fernet = Fernet(_get_fernet_key())
    encrypted = fernet.encrypt(api_key.encode())
    return encrypted.decode()


def decrypt_api_key(encrypted_api_key: str) -> str:
    """Decrypt API key using Fernet; support legacy plaintext keys."""
    if encrypted_api_key.startswith("wa_"):
        return encrypted_api_key

    fernet = Fernet(_get_fernet_key())
    try:
        decrypted = fernet.decrypt(encrypted_api_key.encode())
        return decrypted.decode()
    except InvalidToken:
        return encrypted_api_key
