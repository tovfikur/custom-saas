from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
import secrets
from .config import settings


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Encryption for sensitive data
def get_encryption_key() -> bytes:
    """Get encryption key from settings"""
    key = settings.ENCRYPTION_KEY
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable not set")
    
    # Try to validate the key format
    try:
        # Check if it's a valid Fernet key by attempting to create a Fernet instance
        test_key = key.encode() if isinstance(key, str) else key
        Fernet(test_key)  # This will raise an exception if invalid
        return test_key
    except Exception as e:
        raise ValueError(f"Invalid ENCRYPTION_KEY format. Must be a valid Fernet key (44 characters, base64 encoded): {str(e)}")

cipher_suite = Fernet(get_encryption_key())


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def encrypt_data(data: Union[str, bytes]) -> str:
    """Encrypt sensitive data"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    encrypted_data = cipher_suite.encrypt(data)
    return base64.b64encode(encrypted_data).decode('utf-8')


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    try:
        if not encrypted_data:
            return ""
        
        encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
        decrypted_data = cipher_suite.decrypt(encrypted_bytes)
        return decrypted_data.decode('utf-8')
    except Exception as e:
        # More detailed error for debugging
        import logging
        logging.getLogger(__name__).error(f"Failed to decrypt data: {str(e)}. This usually happens when the encryption key changes.")
        raise ValueError("Failed to decrypt data - encryption key may have changed")


def generate_secure_token(length: int = 32) -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(length)


def sanitize_error_message(error: str, task_id: Optional[str] = None) -> dict:
    """Sanitize error messages for safe logging and display"""
    # Remove potential sensitive information
    sanitized = error.replace('\n', ' ').strip()
    
    # Remove file paths that might contain sensitive info
    import re
    sanitized = re.sub(r'/[^\s]*/(config|secret|key|password)[^\s]*', '[REDACTED_PATH]', sanitized)
    
    # Remove potential passwords or keys
    sanitized = re.sub(r'(password|key|secret|token)[\s=:]+[^\s]+', r'\1=[REDACTED]', sanitized, flags=re.IGNORECASE)
    
    return {
        "error": sanitized[:500],  # Limit error message length
        "task_id": task_id or generate_secure_token(8),
        "timestamp": datetime.utcnow().isoformat()
    }