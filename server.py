from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.api.conversation_api import router as conversation_router
from app.api.signature_api import router as signature_router
from app.api.auth_api import router as auth_router
from app.api.connection_api import router as connection_router

app = FastAPI(title="CurveApp API")

frontend_origin_env = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
frontend_origins = [
    origin.strip()
    for origin in frontend_origin_env.split(",")
    if origin.strip()
]
if "http://localhost:3000" not in frontend_origins:
    frontend_origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=r"^https?://([a-zA-Z0-9-]+\.)?vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversation_router)
app.include_router(signature_router)
app.include_router(auth_router)
app.include_router(connection_router)


@app.get("/")
def health():
    return {"ok": True}
