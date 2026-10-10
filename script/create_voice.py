"""Create a cloned voice on Sarvam AI from Recording.wav.

Endpoint: POST https://api.sarvam.ai/voices/create
Documentation: https://docs.sarvam.ai/api-reference/voice-cloning/create-voice
"""
from __future__ import annotations

import argparse
import json
import os
import re
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
AUDIO_PATH = PROJECT_ROOT / "English.wav"
API_URL = "https://api.sarvam.ai/voices/create"


def load_sarvam_api_key(env_path: Path) -> str:
    """Read SARVAM_API_KEY from .env (or environment) without exposing secrets."""
    if not env_path.is_file():
        raise FileNotFoundError(
            f"The .env file was not found at:\n  {env_path}\n"
            "Please create a .env file in the project root."
        )

    config = dotenv_values(env_path)
    # Check SARVAM_API_KEY explicitly in .env, falling back to os.environ if needed
    key = config.get("SARVAM_API_KEY")
    if key is None:
        key = os.getenv("SARVAM_API_KEY")

    if not key or not str(key).strip():
        raise RuntimeError(
            f"SARVAM_API_KEY was not found or is empty.\n"
            f"Checked file: {env_path}\n"
            "Please ensure 'SARVAM_API_KEY=<your_key>' is set in your .env file."
        )

    return str(key).strip().strip("'\"")


def update_env_sarvam_voice_id(env_path: Path, voice_id: str) -> bool:
    """Save or update SARVAM_VOICE_ID in .env while preserving all other settings."""
    try:
        content = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
        if re.search(r"^SARVAM_VOICE_ID=.*$", content, flags=re.MULTILINE):
            new_content = re.sub(
                r"^SARVAM_VOICE_ID=.*$",
                f"SARVAM_VOICE_ID={voice_id}",
                content,
                flags=re.MULTILINE,
            )
        else:
            sep = "\n" if content and not content.endswith("\n") else ""
            new_content = f"{content}{sep}SARVAM_VOICE_ID={voice_id}\n"

        env_path.write_text(new_content, encoding="utf-8")
        return True
    except Exception as exc:
        print(f"Warning: Could not automatically update .env ({exc})")
        return False


def validate_local_setup(audio_file: Optional[Path] = None) -> tuple[str, Path]:
    """Validate environment and local recording before calling the API."""
    print("=" * 60)
    print("Aarogya Saathi - Voice Creation Pre-flight Validation")
    print("=" * 60)

    target_audio = audio_file or AUDIO_PATH

    # 1. Validate .env
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Checking .env at: {ENV_PATH}")
    if not ENV_PATH.is_file():
        raise FileNotFoundError(f".env file missing at {ENV_PATH}")
    print(" [OK] .env file exists.")

    # 2. Validate SARVAM_API_KEY
    api_key = load_sarvam_api_key(ENV_PATH)
    key_prefix = api_key[:3] if len(api_key) >= 3 else "***"
    print(f" [OK] SARVAM_API_KEY loaded successfully (starts with '{key_prefix}', length {len(api_key)}).")

    # 3. Validate reference recording
    print(f"Checking reference recording at: {target_audio}")
    if not target_audio.is_file():
        raise FileNotFoundError(
            f"Reference audio was not found at: {target_audio}\n"
            f"Please ensure {target_audio.name} exists directly inside your project folder."
        )

    file_size_bytes = target_audio.stat().st_size
    if file_size_bytes == 0:
        raise ValueError(f"Reference audio file is empty (0 bytes): {target_audio}")
    file_size_mb = file_size_bytes / (1024 * 1024)
    print(f" [OK] {target_audio.name} found ({file_size_mb:.2f} MB, {file_size_bytes} bytes).")

    # Audio duration check if wave module can parse it
    try:
        import wave

        with wave.open(str(target_audio), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / float(rate) if rate else 0.0
            print(f" [OK] Audio duration: {duration:.2f} seconds ({rate} Hz, {wf.getnchannels()} channels).")
    except Exception:
        pass

    return api_key, target_audio


def create_voice(api_key: str, audio_path: Path, voice_name: str = "Aarogya Saathi Voice") -> str:
    """Send recording to Sarvam's /voices/create endpoint and return the voice_id."""
    headers = {
        "api-subscription-key": api_key,
    }

    form_data = {
        "name": voice_name,
        "language": "en-IN",
    }

    print(f"\nTarget endpoint: {API_URL}")
    print(f"Voice display name: '{voice_name}'")
    print("Reference audio language: 'en-IN'")
    print("Uploading recording to Sarvam AI (this may take 15-45 seconds)...")

    try:
        with audio_path.open("rb") as audio_file:
            files = {
                "file": (audio_path.name, audio_file, "audio/wav"),
            }
            response = requests.post(
                API_URL,
                headers=headers,
                data=form_data,
                files=files,
                timeout=120,
            )

    except requests.Timeout:
        print("\n[ERROR] Request timed out after 120 seconds connecting to Sarvam.")
        sys.exit(1)
    except requests.RequestException as err:
        print(f"\n[ERROR] Network error connecting to Sarvam: {err}")
        sys.exit(1)

    # Check response status
    if not response.ok:
        print(f"\n[FAILED] Voice creation failed with HTTP status: {response.status_code}")
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
            # Fallback if response is not JSON
            sanitized = response.text[:400]
            print(f"Response: {sanitized}")
        sys.exit(1)

    # Parse success response
    try:
        resp_json = response.json()
    except Exception as exc:
        print(f"\n[ERROR] Could not decode JSON response: {exc}")
        print(f"Response body: {response.text[:300]}")
        sys.exit(1)

    voice_id: Optional[str] = None
    if isinstance(resp_json, dict):
        data = resp_json.get("data")
        if isinstance(data, dict):
            voice_id = data.get("voice_id")
            ref_text = data.get("reference_text")
            if ref_text:
                print(f"Auto-generated transcript: \"{ref_text}\"")
        if not voice_id:
            voice_id = resp_json.get("voice_id")

    if not voice_id:
        print("\n[ERROR] Voice creation returned success status, but no voice_id found in response:")
        print(json.dumps(resp_json, indent=2))
        sys.exit(1)

    print("\n" + "=" * 60)
    print("SUCCESS! Cloned voice created successfully.")
    print("=" * 60)
    print(f"Voice ID: {voice_id}")

    if update_env_sarvam_voice_id(ENV_PATH, voice_id):
        print(f"Automatically saved SARVAM_VOICE_ID={voice_id} to .env")
    else:
        print(f"Please add this line to your .env:\n  SARVAM_VOICE_ID={voice_id}")

    return voice_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a cloned voice on Sarvam AI from English.wav")
    parser.add_argument(
        "--file",
        dest="audio_file",
        default=str(AUDIO_PATH),
        help=f"Reference audio file (default: {AUDIO_PATH.name})",
    )
    parser.add_argument(
        "--check",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Run local pre-flight checks (validate .env, SARVAM_API_KEY, audio file) without making the API call.",
    )
    parser.add_argument(
        "--name",
        dest="name",
        default="Aarogya Saathi Voice",
        help="Display name for the voice (default: 'Aarogya Saathi Voice')",
    )
    args = parser.parse_args()

    audio_file_path = Path(args.audio_file)
    api_key, audio_path = validate_local_setup(audio_file_path)

    if args.dry_run:
        print("\n[DRY RUN] All local validations passed! Ready for voice creation.")
        print("To create the voice, run:")
        print("  python script/create_voice.py")
        return

    create_voice(api_key, audio_path, voice_name=args.name)


if __name__ == "__main__":
    main()
