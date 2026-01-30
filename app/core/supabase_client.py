from supabase import create_client, Client
from app.core.config import get_settings

class SupabaseManager:
    _instance = None
    _client: Client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseManager, cls).__new__(cls)
            settings = get_settings()
            try:
                cls._client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            except Exception as e:
                print(f"Error initializing Supabase client: {e}")
                # En producción, esto debería loguearse adecuadamente o lanzar una excepción crítica.
                raise e
        return cls._instance

    @property
    def client(self) -> Client:
        return self._client

# Helper function to get the client instance easily
def get_supabase() -> Client:
    return SupabaseManager().client
