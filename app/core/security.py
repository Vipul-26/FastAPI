"""Password hashing and JWT utilities.

- Passwords: Argon2 via pwdlib (one-way hash, never store plain text)
- JWTs: signed tokens with sub (user id) and exp (expiration)
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

# Argon2 via pwdlib — slow, salted, one-way. Not SHA-256, not reversible encryption.
# Shared hasher so hash and verify use the same algorithm/settings.
_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Turn a plaintext password into a salted hash for PostgreSQL.

    Never store the original password. Calling this twice with the same
    password produces different hashes because a random salt is mixed in.
    """
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check a login attempt against the stored hash without decrypting it.

    Hashes cannot be reversed. This re-hashes `password` with the salt
    embedded in `password_hash` and compares the results.
    """
    return _hasher.verify(password, password_hash)


def create_access_token(
    subject: str | UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Sign a JWT that proves "this user id logged in" until `exp`.

    Payload claims:
      sub — user UUID (who the token is for)
      exp — UTC expiry (PyJWT rejects the token after this)

    The string is signed with JWT_SECRET_KEY so clients cannot forge it.
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    expire = datetime.now(UTC) + expires_delta
    payload = {
        "sub": str(subject),
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> UUID:
    """Opposite of create_access_token: JWT → user UUID.

    Must verify signature and exp. Do not jwt.decode without the secret
    (that would trust a forged payload).
    """
    # verify_signature=True by default — we still pass the secret + algorithm
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    subject = payload.get("sub")
    if subject is None:
        raise jwt.InvalidTokenError("Token missing subject claim")

    try:
        return UUID(subject)
    except (ValueError, TypeError, AttributeError) as exc:
        raise jwt.InvalidTokenError("Token subject is not a valid user id") from exc
