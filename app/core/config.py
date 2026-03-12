# ─────────────────────────────────────────
# SONOPRO — Configuration
# ─────────────────────────────────────────

from pathlib import Path

UPLOAD_DIR = Path("/tmp/sonopro/uploads")
OUTPUT_DIR = Path("/tmp/sonopro/outputs")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".m4a", ".wav", ".mp3", ".aac", ".ogg", ".flac"}
MAX_FILE_SIZE_MB   = 50

PRESETS = {
    "podcast": {
        "highpass_hz":               100,
        "lowpass_hz":                12000,
        "compression_threshold_db":  -18,
        "compression_ratio":         4.0,
        "compression_attack_ms":     5.0,
        "compression_release_ms":    100.0,
        "gain_db":                   2.0,
        "target_lufs":               -16.0,
    },
    "voiceover": {
        "highpass_hz":               120,
        "lowpass_hz":                14000,
        "compression_threshold_db":  -20,
        "compression_ratio":         5.0,
        "compression_attack_ms":     3.0,
        "compression_release_ms":    80.0,
        "gain_db":                   1.0,
        "target_lufs":               -14.0,
    },
    "interview": {
        "highpass_hz":               80,
        "lowpass_hz":                15000,
        "compression_threshold_db":  -15,
        "compression_ratio":         3.0,
        "compression_attack_ms":     8.0,
        "compression_release_ms":    120.0,
        "gain_db":                   0.0,
        "target_lufs":               -16.0,
    },
    "asmr": {
        "highpass_hz":               40,
        "lowpass_hz":                18000,
        "compression_threshold_db":  -25,
        "compression_ratio":         2.0,
        "compression_attack_ms":     15.0,
        "compression_release_ms":    200.0,
        "gain_db":                   -1.0,
        "target_lufs":               -20.0,
    },
}