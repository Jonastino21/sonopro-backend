# ─────────────────────────────────────────
# SONOPRO — Service de traitement audio
# Pipeline : denoise → EQ → compress → LUFS
# ─────────────────────────────────────────

from pathlib import Path
import numpy as np
import soundfile as sf
import librosa
import noisereduce as nr
import pyloudnorm as pyln
from pedalboard import Pedalboard, Compressor, HighpassFilter, LowpassFilter, Gain

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
    Pipeline complet de traitement audio.

    Étapes :
      1. Chargement du fichier source
      2. Noise reduction (noisereduce)
      3. Highpass + Lowpass filter (pedalboard)
      4. De-esser — atténuation des sibilantes
      5. Compression dynamique (pedalboard)
      6. Gain makeup
      7. Normalisation LUFS (pyloudnorm)
      8. Export WAV 24bit

    Retourne la durée en secondes du fichier traité.
    """
    cfg = PRESETS.get(preset, PRESETS["podcast"])

    # ── 1. Chargement ──────────────────────
    audio, sr = librosa.load(str(input_path), sr=None, mono=False)
    if audio.ndim == 1:
        audio = audio[np.newaxis, :]  # mono → (1, N)

    # ── 2. Noise reduction ─────────────────
    if noise_gate:
        audio = np.stack([
            nr.reduce_noise(
                y=ch,
                sr=sr,
                stationary=False,
                prop_decrease=0.8,
            )
            for ch in audio
        ])

    # ── 3. EQ + 4. De-esser + 5. Compresseur ──
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

    # ── 6. Gain makeup ─────────────────────
    chain.append(Gain(gain_db=cfg["gain_db"]))

    board    = Pedalboard(chain)
    processed = board(audio.astype(np.float32), sr)

    # ── 7. Normalisation LUFS ──────────────
    meter        = pyln.Meter(sr)
    audio_lufs   = processed.T.astype(np.float64)   # (samples, channels)
    loudness     = meter.integrated_loudness(audio_lufs)

    if np.isfinite(loudness):
        normalized = pyln.normalize.loudness(
            audio_lufs,
            loudness,
            cfg["target_lufs"],
        )
    else:
        normalized = audio_lufs

    # ── 8. Export WAV 24bit ────────────────
    sf.write(str(output_path), normalized, sr, subtype="PCM_24")

    return normalized.shape[0] / sr