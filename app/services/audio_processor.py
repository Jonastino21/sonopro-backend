from pathlib import Path
import subprocess
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
    cfg = PRESETS.get(preset, PRESETS["podcast"])

    # ── 1. Conversion en WAV mono 44100 via ffmpeg ──
    wav_input = input_path.with_suffix('_input.wav')
    subprocess.run([
        'ffmpeg', '-y', '-i', str(input_path),
        '-ar', '44100', '-ac', '1',
        str(wav_input)
    ], check=True, capture_output=True)

    # ── 2. Lecture ──────────────────────────
    with AudioFile(str(wav_input)) as f:
        audio = f.read(f.frames)
        sr    = f.samplerate
    wav_input.unlink(missing_ok=True)

    # ── 3. Chaîne pedalboard ────────────────
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
    processed = board(audio, sr)

    # ── 4. Normalisation LUFS ───────────────
    meter      = pyln.Meter(sr)
    audio_lufs = processed.T.astype(np.float64)
    loudness   = meter.integrated_loudness(audio_lufs)
    if np.isfinite(loudness):
        normalized = pyln.normalize.loudness(audio_lufs, loudness, cfg["target_lufs"])
    else:
        normalized = audio_lufs

    # ── 5. Export WAV 24bit ─────────────────
    sf.write(str(output_path), normalized, sr, subtype="PCM_24")

    return normalized.shape[0] / sr