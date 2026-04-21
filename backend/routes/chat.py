from fastapi import APIRouter

from backend.models.schemas import ChatRequest, ChatResponse
from backend.services.chat_service import build_chat_response

router = APIRouter(prefix='/api/chat', tags=['chat'])


@router.post('', response_model=ChatResponse)
def chat(payload: ChatRequest):
    response = build_chat_response(
        message=payload.message,
        language=payload.language,
        sensor_data=payload.sensor_data,
        robot_state=payload.robot_state,
    )
    return {'response': response}
