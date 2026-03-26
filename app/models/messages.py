from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    receiver_id: int = Field(..., ge=1)
    task_id: int | None = Field(default=None, ge=1)
    text: str = Field(min_length=1)
