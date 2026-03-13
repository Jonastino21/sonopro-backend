# ─────────────────────────────────────────
# SONOPRO — Service de traitement audio
# Pipeline : denoise → EQ → compress → LUFS
# ─────────────────────────────────────────

from pathlib import Path
import numpy as np
import soundfile as sf
import librosa
import pyloudnorm as pyln
from scipy.signal import butter, sosfilt
from pedalboard import Pedalboard, Compressor, HighpassFilter, LowpassFilter, Gain

from app.core.config import PRESETS


def _spectral_denoise(audio: np.ndarray, sr: int, prop_decrease: float = 0.75) -> np.ndarray:
    """
    Débruitage spectral simple sans dépendance externe.
    Estime le bruit sur les 0.5 premières secondes puis soustrait.
    """
    results = []
    noise_frames = int(sr * 0.5)

    for ch in audio:
        stft = librosa.stft(ch)
        mag, phase = np.abs(stft), np.angle(stft)

        # Profil de bruit estimé sur les premières frames
        noise_profile = np.mean(mag[:, :noise_frames], axis=1, keepdims=True)

        # Soustraction spectrale
        mag_clean = np.maximum(mag - prop_decrease * noise_profile, 0)
        ch_clean  = librosa.istft(mag_clean * np.exp(1j * phase), length=len(ch))
        results.append(ch_clean)

    return np.stack(results)


def process_audio(
    input_path:     Path,
    output_path:    Path,
    preset:         str  = "podcast",
    noise_gate:     bool = True,
    use_compressor: bool = True,
    de_esser:       bool = True,
) -> float:
    """
    Pipeline complet :
      1. Chargement
      2. Débruitage spectral (scipy + librosa)
      3. Highpass + Lowpass EQ (pedalboard)
      4. De-esser
      5. Compression dynamique
      6. Gain makeup
      7. Normalisation LUFS (pyloudnorm)
      8. Export WAV 24bit
    """
    cfg = PRESETS.get(preset, PRESETS["podcast"])

    # ── 1. Chargement ──────────────────────
    audio, sr = librosa.load(str(input_path), sr=None, mono=False)
    if audio.ndim == 1:
        audio = audio[np.newaxis, :]  # mono → (1, N)

    # ── 2. Débruitage ──────────────────────
    if noise_gate:
        audio = _spectral_denoise(audio, sr, prop_decrease=0.75)

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

    board     = Pedalboard(chain)
    processed = board(audio.astype(np.float32), sr)

    # ── 7. Normalisation LUFS ──────────────
    meter      = pyln.Meter(sr)
    audio_lufs = processed.T.astype(np.float64)
    loudness   = meter.integrated_loudness(audio_lufs)

    if np.isfinite(loudness):
        normalized = pyln.normalize.loudness(audio_lufs, loudness, cfg["target_lufs"])
    else:
        normalized = audio_lufs

    # ── 8. Export WAV 24bit ────────────────
    sf.write(str(output_path), normalized, sr, subtype="PCM_24")

    return normalized.shape[0] / sr