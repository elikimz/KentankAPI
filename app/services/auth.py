import base64
import hashlib
import hmac
import json
import secrets
import time
from app.core.config import settings


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_text, digest_text = encoded.split('$')
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac(algorithm.replace('pbkdf2_', ''), password.encode(), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_token(subject: str, role: str, expires_in: int = 60 * 60 * 24 * 7) -> str:
    payload = {'sub': subject, 'role': role, 'exp': int(time.time()) + expires_in}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip('=')
    signature = hmac.new(settings.SECRET_KEY.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f'{encoded}.{signature}'


def decode_token(token: str, expected_role: str | None = None) -> dict | None:
    try:
        encoded, signature = token.split('.', 1)
        expected_signature = hmac.new(settings.SECRET_KEY.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        if int(payload.get('exp', 0)) < int(time.time()):
            return None
        if expected_role and payload.get('role') != expected_role:
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
