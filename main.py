# ─────────────────────────────────────────
# SONOPRO — Point d'entrée FastAPI
# ─────────────────────────────────────────

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(
    title       = "SonoPro Backend",
    description = "Pipeline de traitement audio professionnel",
    version     = "1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

app.include_router(router)

@app.get("/")
def root():
    return {"service": "SonoPro", "status": "ok"}