# ─────────────────────────────────────────
# SONOPRO — Service de traitement audio
# Pipeline : DeepFilterNet → EQ → compress → LUFS
# ─────────────────────────────────────────

from pathlib import Path
from typing import Callable, Optional
import numpy as np
import soundfile as sf
import librosa
import pyloudnorm as pyln
from pedalboard import Pedalboard, Compressor, HighpassFilter, LowpassFilter, Gain

from app.core.config import PRESETS

# ── DeepFilterNet — init une seule fois ──
import torch
from df.enhance import enhance, init_df, load_audio, save_audio
from df.utils import log as df_log
import logging
df_log.setLevel(logging.WARNING)  # silence les logs verbose

_df_model  = None
_df_state  = None

def get_df():
    global _df_model, _df_state
    if _df_model is None:
        _df_model, _df_state, _ = init_df()
    return _df_model, _df_state


def process_audio(
    input_path:        Path,
    output_path:       Path,
    preset:            str  = "podcast",
    noise_gate:        bool = True,
    use_compressor:    bool = True,
    de_esser:          bool = True,
    progress_callback: Optional[Callable[[int, float], None]] = None,
) -> float:

    def report(step: int, progress: float):
        if progress_callback:
            progress_callback(step, progress)

    cfg = PRESETS.get(preset, PRESETS["podcast"])

    # ── 1. Chargement ──────────────────────
    report(1, 15)
    audio, sr = librosa.load(str(input_path), sr=None, mono=False)
    if audio.ndim == 1:
        audio = audio[np.newaxis, :]  # → (1, N)

    # ── 2. DeepFilterNet — suppression bruit ─
    report(2, 30)
    if noise_gate:
        try:
            model, df_state = get_df()

            # DeepFilterNet attend du 48kHz
            audio_dfn, sr_dfn = load_audio(str(input_path), sr=df_state.sr())

            # Traitement
            enhanced = enhance(model, df_state, audio_dfn)

            # Resample vers sr original si différent
            if sr_dfn != sr:
                enhanced_np = enhanced.numpy()
                enhanced_np = librosa.resample(enhanced_np, orig_sr=sr_dfn, target_sr=sr)
                audio = enhanced_np
            else:
                audio = enhanced.numpy()

            if audio.ndim == 1:
                audio = audio[np.newaxis, :]

        except Exception as e:
            # Fallback silencieux si DeepFilterNet échoue
            import warnings
            warnings.warn(f"DeepFilterNet failed, skipping denoising: {e}")

    # ── 3. EQ ──────────────────────────────
    report(3, 55)
    chain = [
        HighpassFilter(cutoff_frequency_hz=float(cfg["highpass_hz"])),
        LowpassFilter(cutoff_frequency_hz=float(cfg["lowpass_hz"])),
    ]

    # ── 4. De-esser + Compresseur ──────────
    report(4, 75)
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
    processed = board(audio.astype(np.float32), sr)

    # ── 5. Normalisation LUFS + export ─────
    report(5, 90)
    meter      = pyln.Meter(sr)
    audio_lufs = processed.T.astype(np.float64)
    loudness   = meter.integrated_loudness(audio_lufs)

    if np.isfinite(loudness):
        normalized = pyln.normalize.loudness(
            audio_lufs, loudness, cfg["target_lufs"]
        )
    else:
        normalized = audio_lufs

    sf.write(str(output_path), normalized, sr, subtype="PCM_24")
    report(5, 100)

    return normalized.shape[0] / sr