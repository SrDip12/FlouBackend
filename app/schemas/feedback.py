from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

class FeedbackTargetType(str, Enum):
    CHAT_SESSION = 'chat_session'
    EXERCISE = 'exercise'
    GENERAL = 'general'
    FEATURE = 'feature'

class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = Field(None, description="Optional text comment")
    target_type: FeedbackTargetType = Field(..., description="Type of item being rated")
    target_id: Optional[str] = Field(None, description="Optional ID of the chat session or exercise")

class FeedbackResponse(FeedbackCreate):
    id: int
    user_id: UUID
    created_at: datetime
