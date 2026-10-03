import bcrypt

_MIN_LEN = 8
_MAX_BYTES = 72  # bcrypt silently truncates beyond 72 bytes


class PasswordTooShort(ValueError):
    pass


class PasswordTooLong(ValueError):
    pass


def validate_password(password: str) -> None:
    """Reject passwords shorter than 8 chars or longer than 72 UTF-8 bytes."""
    if len(password) < _MIN_LEN:
        raise PasswordTooShort(f"Password must be at least {_MIN_LEN} characters")
    if len(password.encode("utf-8")) > _MAX_BYTES:
        raise PasswordTooLong(f"Password must not exceed {_MAX_BYTES} bytes (UTF-8)")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    # If the password exceeds bcrypt's 72-byte limit, reject immediately
    # to avoid silent truncation matching a different password.
    if len(password.encode("utf-8")) > _MAX_BYTES:
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())
