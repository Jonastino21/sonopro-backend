from pathlib import Path
import subprocess
import numpy as np
import soundfile as sf
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
    cfg = PRESETS.get(preset, PRESETS["podcast"])

    # ── 1. Conversion m4a/aac → WAV via ffmpeg ──
    wav_input = output_path.parent / f"{input_path.stem}_tmp.wav"
    subprocess.run(
        ['ffmpeg', '-y', '-i', str(input_path), '-ar', '44100', '-ac', '1', str(wav_input)],
        check=True, capture_output=True
    )

    # ── 2. Lecture soundfile → numpy (samples,) ──
    data, sr = sf.read(str(wav_input), dtype='float32')
    wav_input.unlink(missing_ok=True)

    # Mono → (1, samples) pour pedalboard
    if data.ndim == 1:
        data = data[np.newaxis, :]
    else:
        data = data.T  # (channels, samples)

    # ── 3. Chaîne pedalboard ────────────────────
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

    processed = Pedalboard(chain)(data, sr)  # (channels, samples)

    # ── 4. Normalisation LUFS ───────────────────
    audio_lufs = processed.T.astype(np.float64)  # (samples, channels)
    meter      = pyln.Meter(sr)
    loudness   = meter.integrated_loudness(audio_lufs)

    normalized = pyln.normalize.loudness(
        audio_lufs, loudness, cfg["target_lufs"]
    ) if np.isfinite(loudness) else audio_lufs

    # ── 5. Export WAV 24bit ─────────────────────
    sf.write(str(output_path), normalized, sr, subtype="PCM_24")

    return normalized.shape[0] / sr