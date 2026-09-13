import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.assistant import AssistantService
from app.security.auth import authenticated_user

router = APIRouter()
logger = logging.getLogger("omnicare.api")


def get_assistant_service() -> AssistantService:
    return AssistantService()


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    assistant: AssistantService = Depends(get_assistant_service),
    authorization: str | None = Header(default=None),
) -> ChatResponse:
    """
    The route's only job: validate the request (via ChatRequest), delegate
    to AssistantService, and shape the result into ChatResponse. No vector
    search, LLM prompts, or claim logic lives here (Section 9).
    """
    authenticated_id = authenticated_user(authorization)
    if authenticated_id != request.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authenticated user does not match user_id")
    result = assistant.handle_message(user_id=authenticated_id, message=request.message)
    return ChatResponse(**result)
