from dataclasses import dataclass


@dataclass
class ApiException(Exception):
    status_code: int
    message: str
    code: str

