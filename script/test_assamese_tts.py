"""Test speech synthesis in Assamese (as-IN) using a cloned voice on Sarvam AI.

Endpoint: POST https://api.sarvam.ai/voices/clone
Documentation: https://docs.sarvam.ai/api-reference/voice-cloning/clone
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests
from dotenv import dotenv_values

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def safe_print(msg: str) -> None:
    """Print message safely even if terminal encoding does not support characters."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="backslashreplace").decode("ascii"))


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_AUDIO = PROJECT_ROOT / "assamese_test.wav"
CLONE_URL = "https://api.sarvam.ai/voices/clone"

DEFAULT_ASSAMESE_TEXT = "নমস্কাৰ! আৰোগ্য সাৰথিয়ে আপোনাৰ স্বাস্থ্যৰ যত্ন ল'বলৈ সদায় সাজু।"


def load_credentials(env_path: Path) -> tuple[str, str]:
    """Read SARVAM_API_KEY and SARVAM_VOICE_ID from .env without exposing secrets."""
    if not env_path.is_file():
        raise FileNotFoundError(
            f"The .env file was not found at:\n  {env_path}\n"
            "Please create a .env file in the project root."
        )

    config = dotenv_values(env_path)
    api_key = config.get("SARVAM_API_KEY") or os.getenv("SARVAM_API_KEY")
    voice_id = config.get("SARVAM_VOICE_ID") or os.getenv("SARVAM_VOICE_ID")

    if not api_key or not str(api_key).strip():
        raise RuntimeError(
            f"SARVAM_API_KEY was not found or is empty in: {env_path}\n"
            "Please ensure 'SARVAM_API_KEY=<your_key>' is set in your .env file."
        )

    if not voice_id or not str(voice_id).strip():
        raise RuntimeError(
            f"SARVAM_VOICE_ID was not found or is empty in: {env_path}\n"
            "Please create a cloned voice first by running:\n"
            "  python script/create_voice.py\n"
            "and ensure 'SARVAM_VOICE_ID=<voice_id>' is in your .env file."
        )

    return str(api_key).strip().strip("'\""), str(voice_id).strip().strip("'\"")


def validate_setup() -> tuple[Optional[str], Optional[str]]:
    """Inspect environment configuration and report readiness."""
    print("=" * 60)
    print("Aarogya Saathi - Assamese TTS Clone Pre-flight Check")
    print("=" * 60)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Checking .env at: {ENV_PATH}")

    if not ENV_PATH.is_file():
        print(" [MISSING] .env file not found.")
        return None, None
    print(" [OK] .env file exists.")

    config = dotenv_values(ENV_PATH)
    api_key = config.get("SARVAM_API_KEY") or os.getenv("SARVAM_API_KEY")
    voice_id = config.get("SARVAM_VOICE_ID") or os.getenv("SARVAM_VOICE_ID")

    if api_key:
        prefix = str(api_key).strip()[:3]
        print(f" [OK] SARVAM_API_KEY found (starts with '{prefix}', length {len(str(api_key).strip())}).")
    else:
        print(" [MISSING] SARVAM_API_KEY is not set.")

    if voice_id:
        v_str = str(voice_id).strip()
        print(f" [OK] SARVAM_VOICE_ID found: {v_str}")
    else:
        print(" [PENDING] SARVAM_VOICE_ID is not set yet.")
        print("           Run 'python script/create_voice.py' to generate your voice ID.")

    return api_key, voice_id


def generate_assamese_speech(
    api_key: str,
    voice_id: str,
    text: str = DEFAULT_ASSAMESE_TEXT,
    output_path: Path = OUTPUT_AUDIO,
) -> Path:
    """Call Sarvam /voices/clone with the Assamese sentence and save audio to disk."""
    headers = {
        "api-subscription-key": api_key,
    }

    # /voices/clone expects multipart/form-data
    form_data = {
        "voice_id": voice_id,
        "text": text,
        "language_code": "as-IN",
        "output_audio_codec": "wav",
        "pace": "1.0",
    }

    print(f"\nTarget endpoint: {CLONE_URL}")
    print(f"Voice ID: {voice_id}")
    print("Language code: as-IN (Assamese)")
    safe_print(f"Text to synthesize: \"{text}\"")
    print("Sending synthesis request to Sarvam AI...")

    try:
        response = requests.post(
            CLONE_URL,
            headers=headers,
            data=form_data,
            timeout=60,
        )
    except requests.Timeout:
        print("\n[ERROR] Request timed out after 60 seconds.")
        sys.exit(1)
    except requests.RequestException as err:
        print(f"\n[ERROR] Connection error: {err}")
        sys.exit(1)

    if not response.ok:
        print(f"\n[FAILED] Speech generation failed with HTTP status: {response.status_code}")
        try:
            err_json = response.json()
            err_detail = err_json.get("error", {})
            if isinstance(err_detail, dict):
                code = err_detail.get("code", "unknown_error")
                message = err_detail.get("message", "No message provided")
                req_id = err_detail.get("request_id")
                print(f"Error Code: {code}")
                print(f"Message: {message}")
                if req_id:
                    print(f"Request ID: {req_id}")
            else:
                print(f"Details: {err_detail or err_json}")
        except Exception:
            print(f"Response: {response.text[:300]}")
        sys.exit(1)

    try:
        data = response.json()
    except Exception as exc:
        print(f"\n[ERROR] Could not decode JSON response: {exc}")
        sys.exit(1)

    audio_b64 = data.get("audio")
    if not audio_b64:
        print("\n[ERROR] No audio field found in response:")
        print(json.dumps(data, indent=2))
        sys.exit(1)

    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception as exc:
        print(f"\n[ERROR] Failed to base64-decode audio: {exc}")
        sys.exit(1)

    output_path.write_bytes(audio_bytes)

    duration = data.get("audio_duration")
    duration_str = f" ({duration:.2f} seconds)" if duration else ""

    print("\n" + "=" * 60)
    print("SUCCESS! Assamese speech generated.")
    print("=" * 60)
    print(f"Audio saved to: {output_path}{duration_str}")
    print(f"File size: {len(audio_bytes):,} bytes")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Assamese TTS using Sarvam cloned voice")
    parser.add_argument(
        "--check",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Run local configuration checks without making billable API calls.",
    )
    parser.add_argument(
        "--text",
        dest="text",
        default=DEFAULT_ASSAMESE_TEXT,
        help="Custom Assamese text to synthesize (default is a short greeting).",
    )
    parser.add_argument(
        "--out",
        dest="output_file",
        default=str(OUTPUT_AUDIO),
        help=f"Path to save WAV audio (default: {OUTPUT_AUDIO.name}).",
    )
    args = parser.parse_args()

    api_key_chk, voice_id_chk = validate_setup()

    if args.dry_run:
        print("\n[DRY RUN] Check completed.")
        if api_key_chk and voice_id_chk:
            print("Both SARVAM_API_KEY and SARVAM_VOICE_ID are present. Ready to synthesize speech.")
            print("To generate speech, run:")
            print("  python script/test_assamese_tts.py")
        else:
            print("Prerequisites incomplete: A cloned voice ID must first be created via:")
            print("  python script/create_voice.py")
        return

    api_key, voice_id = load_credentials(ENV_PATH)
    generate_assamese_speech(api_key, voice_id, text=args.text, output_path=Path(args.output_file))


if __name__ == "__main__":
    main()
