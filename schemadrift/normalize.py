import re


NULL_TOKENS = frozenset({"", "null", "none", "na", "n/a", "-"})
CURRENCY_CODES = ("usd", "eur", "gbp", "cny", "rmb")
CURRENCY_SYMBOLS = ("$", "€", "£", "¥", "￥")


def normalize_name(name):
    normalized = str(name).strip().lower().replace("-", "_")
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized


def normalize_value(value):
    return "" if value is None else str(value).strip()


def is_null_value(value):
    return normalize_value(value).lower() in NULL_TOKENS
