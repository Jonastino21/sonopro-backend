# ─────────────────────────────────────────
# SONOPRO — Routes FastAPI
# ─────────────────────────────────────────

import uuid
import asyncio
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
import aiofiles

from app.core.config import UPLOAD_DIR, OUTPUT_DIR, ALLOWED_EXTENSIONS, PRESETS
from app.models.schemas import EnhanceResponse, HealthResponse
from app.services.audio_processor import process_audio

router = APIRouter()


# ── Health ────────────────────────────────
@router.get("/health", response_model=HealthResponse)
def health():
    return {"status": "healthy", "version": "1.0.0"}


# ── Enhance ───────────────────────────────
@router.post("/enhance", response_model=EnhanceResponse)
async def enhance_audio(
    audio:      UploadFile = File(...),
    preset:     str        = Form("podcast"),
    noiseGate:  str        = Form("true"),
    compressor: str        = Form("true"),
    deEsser:    str        = Form("true"),
    gainDb:     str        = Form("0"),
):
    # Validation extension
    suffix = Path(audio.filename or "audio.m4a").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Format non supporté : {suffix}")

    # Validation preset
    if preset not in PRESETS:
        preset = "podcast"

    # Sauvegarde du fichier uploadé
    file_id     = str(uuid.uuid4())
    input_path  = UPLOAD_DIR / f"{file_id}{suffix}"
    output_path = OUTPUT_DIR / f"{file_id}.wav"

    async with aiofiles.open(input_path, "wb") as f:
        await f.write(await audio.read())

    # Traitement (CPU-bound → thread séparé)
    try:
        duration = await asyncio.get_event_loop().run_in_executor(
            None,
            process_audio,
            input_path,
            output_path,
            preset,
            noiseGate.lower()  == "true",
            compressor.lower() == "true",
            deEsser.lower()    == "true",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur traitement : {str(e)}")
    finally:
        input_path.unlink(missing_ok=True)

    return EnhanceResponse(
        fileId   = file_id,
        duration = round(duration, 2),
        preset   = preset,
        format   = "wav",
        bitDepth = 24,
    )


# ── Download ──────────────────────────────
@router.get("/download/{file_id}")
async def download_audio(file_id: str):
    if "/" in file_id or ".." in file_id:
        raise HTTPException(status_code=400, detail="file_id invalide")

    path = OUTPUT_DIR / f"{file_id}.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    return FileResponse(
        path       = str(path),
        media_type = "audio/wav",
        filename   = f"sonopro_{file_id}.wav",
    )


# ── Cleanup ───────────────────────────────
@router.delete("/cleanup/{file_id}")
async def cleanup(file_id: str):
    """Appelé par le mobile après téléchargement"""
    if "/" in file_id or ".." in file_id:
        raise HTTPException(status_code=400, detail="file_id invalide")

    (OUTPUT_DIR / f"{file_id}.wav").unlink(missing_ok=True)
    return {"deleted": True}