# ─────────────────────────────────────────
# SONOPRO — Audio Processor (rapide)
# Pipeline : EQ → compress → LUFS → WAV
# ─────────────────────────────────────────

from pathlib import Path
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from pedalboard import Pedalboard, Compressor, HighpassFilter, LowpassFilter, Gain
from pedalboard.io import AudioFile

from app.core.config import PRESETS


def process_audio(
    input_path:     Path,
    output_path:    Path,
    preset:         str  = "podcast",
    noise_gate:     bool = True,
    use_compressor: bool = True,
    de_esser:       bool = True,
) -> float:
    """
    Pipeline rapide via pedalboard uniquement :
      1. Lecture audio (pedalboard.io — supporte m4a/mp3/wav)
      2. Highpass + Lowpass EQ
      3. De-esser
      4. Compression dynamique
      5. Gain makeup
      6. Normalisation LUFS (pyloudnorm)
      7. Export WAV 24bit
    """
    cfg = PRESETS.get(preset, PRESETS["podcast"])

    # ── 1. Lecture avec pedalboard.io ──────
    # Supporte m4a, mp3, wav, aac sans librosa
    with AudioFile(str(input_path)) as f:
        audio = f.read(f.frames)  # (channels, samples) float32
        sr    = f.samplerate

    # ── 2-5. Chaîne pedalboard ─────────────
    chain = [
        HighpassFilter(cutoff_frequency_hz=float(cfg["highpass_hz"])),
        LowpassFilter(cutoff_frequency_hz=float(cfg["lowpass_hz"])),
    ]

    if de_esser:
        chain.append(LowpassFilter(cutoff_frequency_hz=7000.0))

    if use_compressor:
        chain.append(Compressor(
            threshold_db=cfg["compression_threshold_db"],
            ratio=cfg["compression_ratio"],
            attack_ms=cfg["compression_attack_ms"],
            release_ms=cfg["compression_release_ms"],
        ))

    chain.append(Gain(gain_db=cfg["gain_db"]))

    board     = Pedalboard(chain)
    processed = board(audio, sr)  # (channels, samples) float32

    # ── 6. Normalisation LUFS ──────────────
    meter      = pyln.Meter(sr)
    audio_lufs = processed.T.astype(np.float64)  # (samples, channels)
    loudness   = meter.integrated_loudness(audio_lufs)

    if np.isfinite(loudness):
        normalized = pyln.normalize.loudness(audio_lufs, loudness, cfg["target_lufs"])
    else:
        normalized = audio_lufs

    # ── 7. Export WAV 24bit ────────────────
    sf.write(str(output_path), normalized, sr, subtype="PCM_24")

    return normalized.shape[0] / sr