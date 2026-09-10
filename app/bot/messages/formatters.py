"""Small text helpers for player-facing output (Persian digits)."""

_DIGIT_MAP = str.maketrans("0123456789,", "۰۱۲۳۴۵۶۷۸۹٬")


def fa_int(value: int) -> str:
    """Format an integer with thousands separators and Persian digits."""
    return f"{value:,}".translate(_DIGIT_MAP)


def money(value: int) -> str:
    """Format a money amount, e.g. «۱٬۵۰۰٬۰۰۰ تومان»."""
    return f"{fa_int(value)} تومان"
