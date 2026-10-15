"""Small TOTP implementation for session and API-token second factors."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password


def _cipher():
    key = settings.MFA_ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode("ascii")
    return Fernet(key)


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def encrypt_secret(secret):
    return _cipher().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_secret(encrypted):
    return _cipher().decrypt(encrypted.encode("ascii")).decode("ascii")


def provisioning_uri(secret, user_label):
    label = quote(f"Kumon EMS:{user_label}", safe="")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer=Kumon%20EMS"
        "&algorithm=SHA1&digits=6&period=30"
    )


def matching_counter(secret, code, last_counter=-1, at=None):
    """Return matching unused TOTP counter, or None."""
    token = str(code or "").strip()
    if len(token) != 6 or not token.isascii() or not token.isdigit():
        return None
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8))
    counter = int((time.time() if at is None else at) // 30)
    for candidate in (counter - 1, counter, counter + 1):
        if candidate <= last_counter or candidate < 0:
            continue
        digest = hmac.new(key, struct.pack(">Q", candidate), hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
        if hmac.compare_digest(f"{value % 1_000_000:06d}", token):
            return candidate
    return None


def new_recovery_codes(count=10):
    codes = [secrets.token_hex(8).upper() for _ in range(count)]
    return codes, [make_password(code) for code in codes]


def consume_recovery_code(hashes, code):
    token = str(code or "").replace("-", "").strip().upper()
    if len(token) != 16 or not token.isascii() or not token.isalnum():
        return None
    for index, hashed in enumerate(hashes or []):
        if check_password(token, hashed):
            return list(hashes[:index]) + list(hashes[index + 1 :])
    return None
