from typing import Literal

from pydantic import BaseModel


class UpdateProgressRequest(BaseModel):
    status: Literal["not_started", "in_progress", "solved"] | None = None
    attempt_text: str | None = None
