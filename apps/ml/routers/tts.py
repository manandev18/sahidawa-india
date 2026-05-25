from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import io
import logging

try:
    from google.cloud import texttospeech
except ImportError:
    texttospeech = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["TTS"])

# ---------------------------------------------------------------------------
# Google Cloud TTS voice mapping
# Maps BCP-47 language codes to appropriate Google Cloud TTS voices.
# We prioritize Neural2 voices for better quality, falling back to Standard.
# ---------------------------------------------------------------------------
GOOGLE_TTS_VOICE_MAP: dict[str, dict] = {
    "en-IN": {"languageCode": "en-IN", "name": "en-IN-Neural2-D"},
    "hi-IN": {"languageCode": "hi-IN", "name": "hi-IN-Neural2-D"},
    "ta-IN": {"languageCode": "ta-IN", "name": "ta-IN-Standard-C"},
    "bn-IN": {"languageCode": "bn-IN", "name": "bn-IN-Standard-A"},
    "mr-IN": {"languageCode": "mr-IN", "name": "mr-IN-Standard-A"},
    "te-IN": {"languageCode": "te-IN", "name": "te-IN-Standard-A"},
}

DEFAULT_VOICE_CONFIG = GOOGLE_TTS_VOICE_MAP["en-IN"]

class TTSRequest(BaseModel):
    text: str
    language_code: str = "en-IN"

@router.post("/generate")
async def generate_speech(request: TTSRequest):
    """
    Generate speech audio using Google Cloud TTS and stream it back as MP3.
    """
    if texttospeech is None:
        logger.error("[TTS] google-cloud-texttospeech package is not installed.")
        raise HTTPException(status_code=503, detail="TTS package missing.")

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    # Limit text length (Google Cloud TTS limit is 5000 chars per request)
    text = request.text.strip()[:4000]

    voice_config = GOOGLE_TTS_VOICE_MAP.get(request.language_code, DEFAULT_VOICE_CONFIG)

    logger.info(
        f"[TTS] Generating speech for language={request.language_code}, "
        f"voice={voice_config['name']}, text_length={len(text)}"
    )

    try:
        # The client automatically picks up GOOGLE_APPLICATION_CREDENTIALS from env
        client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code=voice_config["languageCode"],
            name=voice_config["name"]
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        audio_data = response.audio_content
        logger.info(f"[TTS] Successfully generated {len(audio_data)} bytes of audio.")

        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=tts.mp3",
                "Cache-Control": "no-store",
            },
        )

    except Exception as e:
        logger.error(f"[TTS] Google Cloud TTS synthesis failed: {e}")
        raise HTTPException(status_code=503, detail="TTS service is currently unavailable.")
