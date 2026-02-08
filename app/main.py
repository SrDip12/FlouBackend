from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import get_settings
from app.routers import profiles, wellness, info, feedback, chat
from app.core.i18n import get_translation, detect_user_language

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers to support i18n
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc):
    lang = detect_user_language(request)
    return JSONResponse(
        status_code=404,
        content={"detail": get_translation("not_found", lang)},
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    lang = detect_user_language(request)
    return JSONResponse(
        status_code=500,
        content={"detail": get_translation("generic_error", lang)},
    )

# Routers
app.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
app.include_router(wellness.router, prefix="/wellness", tags=["wellness"])
app.include_router(info.router, prefix="/info", tags=["info"])
app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])

@app.get("/")
async def root():
    return {"message": "Welcome to Flou Backend API", "status": "running"}
