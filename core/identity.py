import re


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_name(value: str) -> str:
    name = value.strip()
    if not 1 <= len(name) <= 80:
        raise ValueError("Name must contain between 1 and 80 characters")
    return name


def normalize_token(value: str) -> str:
    return value.strip().lower()


def is_email(value: str) -> bool:
    token = normalize_token(value)
    return len(token) <= 254 and bool(_EMAIL_RE.fullmatch(token))


def validate_token(value: str) -> str:
    token = normalize_token(value)
    if not is_email(token):
        raise ValueError("Token must be a valid email address of at most 254 characters")
    return token
