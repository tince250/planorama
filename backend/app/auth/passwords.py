import hashlib
import hmac
import os

PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Returns (hash_hex, salt_hex). Uses stdlib pbkdf2_hmac (no extra
    dependency) rather than plaintext -- this is a course project with no
    session/token layer, but passwords still shouldn't be stored in the
    clear."""
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return derived.hex(), salt.hex()


def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    candidate_hash, _ = hash_password(password, salt_hex)
    return hmac.compare_digest(candidate_hash, hash_hex)
