import re
from dataclasses import dataclass

from .normalize import CURRENCY_CODES, CURRENCY_SYMBOLS, is_null_value, normalize_value


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?$")
NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class NumberParse:
    number: float
    has_decimal_point: bool


def parse_number(value):
    text = normalize_value(value)
    negative = False

    if text.startswith("(") and text.endswith(")") and len(text) >= 2:
        negative = True
        text = text[1:-1].strip()

    if text.endswith("-") and text:
        negative = True
        text = text[:-1].strip()

    lowered = text.lower()
    for code in CURRENCY_CODES:
        lowered = lowered.replace(code, "")

    for symbol in CURRENCY_SYMBOLS:
        lowered = lowered.replace(symbol, "")

    cleaned = lowered.replace(",", "").strip()
    if not NUMBER_RE.fullmatch(cleaned):
        return None

    number = float(cleaned)
    if negative:
        number = -number
    return NumberParse(number, "." in cleaned)


def is_date_value(value):
    return DATE_RE.fullmatch(normalize_value(value)) is not None


def infer_type(values, primary_key=False):
    if primary_key:
        return "text"

    non_null = [normalize_value(value) for value in values if not is_null_value(value)]
    if not non_null:
        return "null"

    if all(is_date_value(value) for value in non_null):
        return "date"

    numbers = [parse_number(value) for value in non_null]
    if all(number is not None for number in numbers):
        if any(number.has_decimal_point for number in numbers):
            return "float"
        return "integer"

    return "string"
