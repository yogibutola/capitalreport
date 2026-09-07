import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import prashn_kijiye
from app.api.v1.routers import generate_report
from app.api.v1.routers import upload_documents
from app.api.v1.routers import list_files
from app.api.v1.routers.pickleball import pb_league
from app.api.v1.routers.pickleball import pb_tournament
from app.api.v1.routers.pickleball import pb_player
from app.api.v1.routers.pickleball import pb_authorization
from app.api.v1.routers.pickleball import pb_quote
from app.api.v1.routers.pickleball import pb_group

app = FastAPI(title="Query Param Example")

_default_origins = "http://localhost:4200,http://127.0.0.1:4200,http://0.0.0.0:4200"
origins = [origin.strip() for origin in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Allows cookies, authorization headers, etc.
    allow_methods=["*"],  # Allows all HTTP methods (POST, GET, PUT, etc.)
    allow_headers=["*"],  # Allows all headers from the request
)

app.include_router(prashn_kijiye.router, prefix="/api/v1")
app.include_router(upload_documents.router, prefix="/api/v1")
app.include_router(list_files.router, prefix="/api/v1")
app.include_router(pb_league.router, prefix="/api/v1")
app.include_router(pb_tournament.router, prefix="/api/v1")
app.include_router(pb_player.router, prefix="/api/v1")
app.include_router(pb_authorization.router, prefix="/api/v1")
app.include_router(pb_quote.router, prefix="/api/v1")
app.include_router(pb_group.router, prefix="/api/v1")
app.include_router(generate_report.router, prefix="/api/v1")
