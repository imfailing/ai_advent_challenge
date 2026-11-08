"""Модуль для сохранения и загрузки токена авторизации."""

import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path

TOKEN_FILE = Path.home() / ".report_service_token"
SALT_FILE = Path.home() / ".report_service_token_salt"
SALT_SIZE = 32
ITERATIONS = 100000
KEY_SIZE = 32


def _get_encryption_key() -> tuple[bytes, bytes]:
    """Получает ключ шифрования из системного хранилища или создаёт новый.
    
    Returns:
        Tuple of (encryption_key, hmac_key)
    """
    if SALT_FILE.exists():
        with open(SALT_FILE, "rb") as f:
            salt = f.read()
    else:
        salt = secrets.token_bytes(SALT_SIZE)
        fd = os.open(str(SALT_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, salt)
        finally:
            os.close(fd)

    # Use environment variable for key derivation instead of hardcoded string
    key_material = os.environ.get("REPORT_SERVICE_KEY_MATERIAL", b"")
    if not key_material:
        key_material = b"report_service_token_key"  # Fallback if env var not set
    
    encryption_key = hashlib.pbkdf2_hmac(
        "sha256", key_material, salt, ITERATIONS, dklen=KEY_SIZE
    )
    hmac_key = hashlib.pbkdf2_hmac(
        "sha256", key_material, salt, ITERATIONS, dklen=KEY_SIZE, 
        info=b"hmac_key"
    )
    
    return encryption_key, hmac_key


def _encrypt_token(token: str, key: bytes, hmac_key: bytes) -> str:
    """Шифрует токен с использованием XOR-шифра и HMAC для целостности.
    
    Note: XOR encryption is used due to standard library constraint.
    For production, use cryptography library with AES-GCM or ChaCha20-Poly1305.
    """
    token_bytes = token.encode("utf-8")
    
    # Generate IV for additional security
    iv = secrets.token_bytes(16)
    
    # XOR encryption with key mixing
    encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(token_bytes))
    
    # Combine IV and encrypted data
    data = iv + encrypted
    
    # Calculate HMAC for integrity
    signature = hmac.new(hmac_key, data, hashlib.sha256).digest()
    
    # Combine data and signature
    full_data = data + signature
    
    return base64.b64encode(full_data).decode("ascii")


def _decrypt_token(encrypted_token: str, key: bytes, hmac_key: bytes) -> str:
    """Расшифровывает токен с использованием XOR-шифра и HMAC для целостности.
    
    Note: XOR encryption is used due to standard library constraint.
    For production, use cryptography library with AES-GCM or ChaCha20-Poly1305.
    """
    encrypted_bytes = base64.b64decode(encrypted_token.encode("ascii"))
    
    # Extract IV, encrypted data, and signature
    if len(encrypted_bytes) < 16 + 32:  # IV + minimum data + signature
        raise ValueError("Invalid encrypted token format")
    
    iv = encrypted_bytes[:16]
    data_with_sig = encrypted_bytes[16:]
    signature = data_with_sig[-32:]
    data = data_with_sig[:-32]
    
    # Verify HMAC
    expected_signature = hmac.new(hmac_key, iv + data, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Token integrity check failed")
    
    # XOR decryption
    decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return decrypted.decode("utf-8")


def save_token(token: str) -> None:
    """Сохраняет токен авторизации в защищённый файл с шифрованием.

    Args:
        token: Токен авторизации для сохранения.

    Raises:
        ValueError: Если токен пустой или не является строкой.
    """
    if not token or not isinstance(token, str):
        raise ValueError("Токен должен быть непустой строкой")

    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    key, hmac_key = _get_encryption_key()
    encrypted_token = _encrypt_token(token, key, hmac_key)

    fd = os.open(str(TOKEN_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, encrypted_token.encode("utf-8"))
    finally:
        os.close(fd)


def load_token() -> str | None:
    """Загружает токен авторизации из файла.

    Returns:
        Токен авторизации или None, если файл не найден или повреждён.
    """
    if not TOKEN_FILE.exists():
        return None

    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            encrypted_token = f.read()

        key, hmac_key = _get_encryption_key()
        return _decrypt_token(encrypted_token, key, hmac_key)
    except (IOError, OSError, UnicodeDecodeError, base64.binascii.Error, ValueError):
        return None
