from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.ai.agent.supervisor import run_chat
from app.core.deps import get_optional_user
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User | None = Depends(get_optional_user),
):
    """
    Unified AI chat endpoint.
    - No token: public info only (providers, availability)
    - Patient token: own appointments, prescriptions, history
    - Provider token: own patients' data, booking, scheduling
    - Admin token: unrestricted
    """
    reply, conversation_id = await run_chat(
        message=body.message,
        current_user=current_user,
        conversation_id=body.conversation_id,
    )
    return {"reply": reply, "conversation_id": conversation_id}
 