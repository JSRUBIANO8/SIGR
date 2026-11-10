"""Hash de contraseñas, sesión y utilidades de autenticación."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

def hash_password(password):
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"

def verify_password(password, encoded):
    try:
        algorithm, salt_hex, digest_hex = encoded.split('$')
        if algorithm != 'scrypt':
            return False
        actual = hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt_hex),n=2**14,r=8,p=1)
        return hmac.compare_digest(actual,bytes.fromhex(digest_hex))
    except (ValueError,TypeError):
        return False

def make_token():
    return secrets.token_urlsafe(32)

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def expires_in(days=1):
    return (datetime.now(timezone.utc)+timedelta(days=days)).isoformat()

def utc_now():
    return datetime.now(timezone.utc).isoformat()
