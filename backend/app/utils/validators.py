"""Request validators shared by API layer."""
import re
from decimal import Decimal, InvalidOperation

CODE_RE = re.compile(r"^[A-Za-z0-9_-]{2,50}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def validate_code(value: str) -> bool:
    return bool(CODE_RE.match(value or ""))


def validate_currency(value: str) -> bool:
    return bool(CURRENCY_RE.match(value or ""))


def to_decimal(value, places: int = 3) -> Decimal:
    try:
        d = Decimal(str(value)).quantize(Decimal(1).scaleb(-places))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal: {value!r}") from exc
    return d
