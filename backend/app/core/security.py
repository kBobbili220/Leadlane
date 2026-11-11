import hashlib
import secrets

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

password_hasher = PasswordHash.recommended()
# Unknown-email login attempts still perform a real Argon2 verification.
dummy_password_hash = password_hasher.hash(secrets.token_urlsafe(32))


def token_digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def verify_password(password: str, hashed: str) -> tuple[bool, str | None]:
    try:
        return password_hasher.verify_and_update(password, hashed)
    except (UnknownHashError, ValueError):
        return False, None
