import os
import sys
import base64
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet

def _get_key_file_path():
    """动态获取密钥文件路径，避免循环依赖"""
    if getattr(sys, 'frozen', False):
        base_dir = Path.home() / '.fundval-live'
    else:
        base_dir = Path(__file__).resolve().parent.parent

    return base_dir / "data" / ".encryption_key"

def _get_or_create_key():
    """获取或创建主加密密钥"""
    key_file = _get_key_file_path()

    if key_file.exists():
        with open(key_file, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        with open(key_file, "wb") as f:
            f.write(key)
        os.chmod(key_file, 0o600)
        return key

def _derive_user_key(user_id: int) -> bytes:
    """从主密钥派生用户级别的加密密钥（HKDF-like derivation）。
    每个用户拥有独立的派生密钥，主密钥泄露后仍需知道 user_id 才能解密。"""
    master_key = _get_or_create_key()
    # 使用 PBKDF2 从 master_key + user_id 派生 32 字节密钥
    salt = f"fundval-user-{user_id}".encode()
    derived = hashlib.pbkdf2_hmac("sha256", master_key, salt, 100000)
    # Fernet 需要 url-safe base64 编码的 32 字节密钥
    return base64.urlsafe_b64encode(derived)

def encrypt_value(plaintext: str, user_id: int = None) -> str:
    """加密字符串。如果提供 user_id，使用用户派生密钥；否则使用全局主密钥。"""
    if not plaintext:
        return ""
    try:
        key = _derive_user_key(user_id) if user_id is not None else _get_or_create_key()
        f = Fernet(key)
        encrypted = f.encrypt(plaintext.encode())
        return encrypted.decode()
    except Exception as e:
        print(f"Encryption error: {e}")
        return ""

def decrypt_value(ciphertext: str, user_id: int = None) -> str:
    """解密字符串。如果提供 user_id，使用用户派生密钥；否则使用全局主密钥。"""
    if not ciphertext:
        return ""
    try:
        key = _derive_user_key(user_id) if user_id is not None else _get_or_create_key()
        f = Fernet(key)
        decrypted = f.decrypt(ciphertext.encode())
        return decrypted.decode()
    except Exception as e:
        print(f"Decryption error: {e}")
        return ""
