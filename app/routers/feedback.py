from fastapi import APIRouter, Depends
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.feedback_service import FeedbackService
from app.routers.profiles import get_current_user_id
from typing import List

router = APIRouter()

@router.post("/", response_model=FeedbackResponse)
async def create_app_feedback(
    feedback: FeedbackCreate,
    user_id: str = Depends(get_current_user_id)
):
    """
    Submit feedback or satisfaction rating for a chat, exercise, or general app usage.
    """
    service = FeedbackService()
    return await service.create_feedback(user_id, feedback)

@router.get("/history", response_model=List[FeedbackResponse])
async def get_feedback_history(
    user_id: str = Depends(get_current_user_id)
):
    """
    Get the history of feedback submitted by the current user.
    """
    service = FeedbackService()
    return await service.get_my_feedback(user_id)
