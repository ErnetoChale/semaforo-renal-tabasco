"""Password hashing and account validation; no default credentials."""
import hashlib
import hmac
import re
import secrets

ITERATIONS = 600_000

def normalize_username(username):
    username = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,49}", username):
        raise ValueError("El usuario debe tener de 3 a 50 caracteres: letras sin acentos, números, punto, guion o guion bajo.")
    return username

def hash_password(password):
    if len(password) < 12 or len(password) > 256:
        raise ValueError("La contraseña debe tener entre 12 y 256 caracteres.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"

def verify_password(password, encoded):
    try:
        kind, iterations, salt, expected = encoded.split("$")
        if kind != "pbkdf2_sha256" or len(password) > 256:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError, AttributeError):
        return False
