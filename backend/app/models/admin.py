from dataclasses import dataclass


@dataclass(frozen=True)
class AdminUser:
    id: int
    email: str
    password_hash: str
