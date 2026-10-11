"""Password hashing (bcrypt) + password policy."""
import re
import bcrypt
import os

MIN_LENGTH = 8


def validate_password(password: str) -> None:
    """سياسة كلمات المرور: ≥8 أحرف + حرف + رقم."""
    if not password or len(password) < MIN_LENGTH:
        raise ValueError(f"Password must be at least {MIN_LENGTH} characters")
    if not re.search(r"[A-Za-z\u0600-\u06FF]", password) or not re.search(r"\d", password):
        raise ValueError("Password must contain letters and digits")


def hash_password(plain: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=rounds)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False
