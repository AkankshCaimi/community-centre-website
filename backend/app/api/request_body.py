"""Reading the request body: rule B3 of docs/specs/F01.md."""

import json

MAX_DEPTH = 10
# Python refuses to convert longer integer text; see sys.get_int_max_str_digits().
MAX_INTEGER_DIGITS = 4300
# Stands in for an integer too long to convert. Far outside every accepted range.
HUGE = 10**30


class UnreadableBody(Exception):
    """The body is not one readable JSON object (B3)."""


def _refuse_constant(name: str):
    raise UnreadableBody(f"{name} is not allowed")


def _parse_decimal(text: str) -> float:
    if "e" in text or "E" in text:
        raise UnreadableBody("numbers with an exponent are not allowed")
    return float(text)


def _parse_integer(text: str) -> int:
    """Convert integer text of any length, so a huge number is a field error (V4)."""
    if len(text) > MAX_INTEGER_DIGITS:
        return -HUGE if text.startswith("-") else HUGE
    return int(text)


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise UnreadableBody(f"duplicate key {key!r}")
        result[key] = value
    return result


def _too_deep(value, levels_left: int) -> bool:
    """Whether a parsed JSON value has more levels of objects and lists than `levels_left`."""
    if isinstance(value, dict):
        children = value.values()
    elif isinstance(value, list):
        children = value
    else:
        return False
    if levels_left == 0:
        return True
    return any(_too_deep(child, levels_left - 1) for child in children)


def read_json_object(data: bytes) -> dict:
    """Parse a request body as one JSON object. Raises UnreadableBody if it is not one."""
    try:
        body = json.loads(
            data.decode("utf-8"),
            parse_constant=_refuse_constant,
            parse_float=_parse_decimal,
            parse_int=_parse_integer,
            object_pairs_hook=_object_without_duplicate_keys,
        )
    except (ValueError, RecursionError) as error:
        raise UnreadableBody(str(error)) from error

    if not isinstance(body, dict):
        raise UnreadableBody("the body is not a JSON object")
    if _too_deep(body, MAX_DEPTH):
        raise UnreadableBody("the body is nested too deeply")
    return body
