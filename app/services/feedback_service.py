from supabase import Client, create_client
from app.core.config import get_settings
from app.schemas.feedback import FeedbackCreate
from typing import List

class FeedbackService:
    def __init__(self):
        settings = get_settings()
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    async def create_feedback(self, user_id: str, feedback: FeedbackCreate):
        data = feedback.model_dump()
        data["user_id"] = user_id
        # Convert Enum to string explicitly if pydantic doesn't do it in model_dump for json compatible dicts usually it sends the value but let's be safe
        data["target_type"] = data["target_type"].value
        
        response = self.supabase.table("feedback").insert(data).execute()
        return response.data[0]

    async def get_my_feedback(self, user_id: str) -> List[dict]:
        response = self.supabase.table("feedback").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return response.data
