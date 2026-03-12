# ─────────────────────────────────────────
# SONOPRO — Service de traitement audio
# Pipeline : denoise → EQ → compress → LUFS
# ─────────────────────────────────────────

from pathlib import Path
from typing import Callable, Optional
import numpy as np
import soundfile as sf
import librosa
import noisereduce as nr
import pyloudnorm as pyln
from pedalboard import Pedalboard, Compressor, HighpassFilter, LowpassFilter, Gain

from app.core.config import PRESETS


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

    # 1. Chargement
    report(1, 20)
    audio, sr = librosa.load(str(input_path), sr=None, mono=False)
    if audio.ndim == 1:
        audio = audio[np.newaxis, :]

    # 2. Noise reduction
    report(2, 35)
    if noise_gate:
        audio = np.stack([
            nr.reduce_noise(y=ch, sr=sr, stationary=False, prop_decrease=0.8)
            for ch in audio
        ])

    # 3. EQ
    report(3, 55)
    chain = [
        HighpassFilter(cutoff_frequency_hz=float(cfg["highpass_hz"])),
        LowpassFilter(cutoff_frequency_hz=float(cfg["lowpass_hz"])),
    ]

    # 4. De-esser + Compresseur
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

    # 5. LUFS + export
    report(5, 90)
    meter      = pyln.Meter(sr)
    audio_lufs = processed.T.astype(np.float64)
    loudness   = meter.integrated_loudness(audio_lufs)

    if np.isfinite(loudness):
        normalized = pyln.normalize.loudness(audio_lufs, loudness, cfg["target_lufs"])
    else:
        normalized = audio_lufs

    sf.write(str(output_path), normalized, sr, subtype="PCM_24")
    report(5, 100)

    return normalized.shape[0] / sr