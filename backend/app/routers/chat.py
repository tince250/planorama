from fastapi import APIRouter, HTTPException

from app.chat.service import run_chat
from app.config import settings
from app.models.event import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set (check your .env file).")

    reply, events = run_chat(
        [m.model_dump() for m in request.messages],
        username=request.username,
        user_lat=request.user_lat,
        user_lon=request.user_lon,
    )
    return ChatResponse(reply=reply, events=events)
