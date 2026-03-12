# ─────────────────────────────────────────
# SONOPRO — Routes FastAPI
# ─────────────────────────────────────────

import uuid
import asyncio
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import aiofiles

from app.core.config import UPLOAD_DIR, OUTPUT_DIR, ALLOWED_EXTENSIONS, PRESETS
from app.models.schemas import EnhanceResponse, HealthResponse, JobStatus
from app.services.audio_processor import process_audio

router = APIRouter()

# Jobs en mémoire { file_id: { step, progress, done, error } }
JOBS: dict[str, dict] = {}


@router.get("/health", response_model=HealthResponse)
def health():
    return {"status": "healthy", "version": "1.0.0"}


@router.post("/enhance", response_model=EnhanceResponse)
async def enhance_audio(
    audio:      UploadFile = File(...),
    preset:     str        = Form("podcast"),
    noiseGate:  str        = Form("true"),
    compressor: str        = Form("true"),
    deEsser:    str        = Form("true"),
    gainDb:     str        = Form("0"),
):
    suffix = Path(audio.filename or "audio.m4a").suffix.lower() or ".m4a"
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Format non supporté : {suffix}")

    if preset not in PRESETS:
        preset = "podcast"

    file_id     = str(uuid.uuid4())
    input_path  = UPLOAD_DIR / f"{file_id}{suffix}"
    output_path = OUTPUT_DIR / f"{file_id}.wav"

    # Init job
    JOBS[file_id] = {"step": 0, "progress": 5, "done": False, "error": None, "duration": 0}

    async with aiofiles.open(input_path, "wb") as f:
        await f.write(await audio.read())

    JOBS[file_id]["step"]     = 1
    JOBS[file_id]["progress"] = 15

    # Traitement dans un thread
    loop = asyncio.get_event_loop()

    def run_with_progress():
        # On simule les étapes intermédiaires via callbacks
        steps = [
            (2, 30),   # denoise
            (3, 55),   # EQ + compressor
            (4, 80),   # LUFS
            (5, 95),   # export
        ]

        import time
        duration = 0.0
        try:
            # Étape 2 : denoise
            JOBS[file_id]["step"] = 2; JOBS[file_id]["progress"] = 30
            # Étape 3-5 via process_audio complet
            duration = process_audio(
                input_path, output_path, preset,
                noiseGate.lower()  == "true",
                compressor.lower() == "true",
                deEsser.lower()    == "true",
                progress_callback=lambda s, p: JOBS[file_id].update({"step": s, "progress": p}),
            )
            JOBS[file_id].update({"step": 5, "progress": 100, "done": True, "duration": duration})
        except Exception as e:
            JOBS[file_id].update({"error": str(e), "done": True})
        finally:
            input_path.unlink(missing_ok=True)

    asyncio.ensure_future(loop.run_in_executor(None, run_with_progress))

    return EnhanceResponse(
        fileId   = file_id,
        duration = 0,
        preset   = preset,
        format   = "wav",
        bitDepth = 24,
    )


@router.get("/status/{file_id}", response_model=JobStatus)
def job_status(file_id: str):
    if file_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job introuvable")
    job = JOBS[file_id]
    return JobStatus(
        fileId   = file_id,
        step     = job["step"],
        progress = job["progress"],
        done     = job["done"],
        error    = job["error"],
        duration = job["duration"],
    )


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


@router.delete("/cleanup/{file_id}")
async def cleanup(file_id: str):
    if "/" in file_id or ".." in file_id:
        raise HTTPException(status_code=400, detail="file_id invalide")
    (OUTPUT_DIR / f"{file_id}.wav").unlink(missing_ok=True)
    JOBS.pop(file_id, None)
    return {"deleted": True}