from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=2000)


class ToolCall(BaseModel):
    name: str
    arguments: dict


class Source(BaseModel):
    section: str
    document: str = "sample_policy.md"


class ChatResponse(BaseModel):
    response: str
    sources: list[Source] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
