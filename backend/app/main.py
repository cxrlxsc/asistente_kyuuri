from functools import lru_cache
from typing import Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from .assistant import Assistant, Reply
from .core.config import settings

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)
assistant = Assistant()


# Los modelos de voz ocupan VRAM, así que solo se cargan si alguien usa esos endpoints
@lru_cache(maxsize=1)
def get_stt():
    from .voice.stt import SpeechToText
    return SpeechToText()


@lru_cache(maxsize=1)
def get_tts():
    from .voice.tts import TextToSpeech
    return TextToSpeech()


class CommandRequest(BaseModel):
    text: str = Field(max_length=500)


class CommandResponse(BaseModel):
    intent: str
    confidence: float
    result: str
    parameters: dict = {}
    transcript: Optional[str] = None


def verify_api_key(x_api_key: Optional[str] = Header(default=None)):
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida.")


def to_response(reply: Reply, transcript: Optional[str] = None) -> CommandResponse:
    return CommandResponse(intent=reply.intent, confidence=reply.confidence, result=reply.text,
                           parameters=reply.parameters, transcript=transcript)


@app.get("/")
def read_root():
    return {"message": f"Bienvenido a {settings.PROJECT_NAME} API"}


@app.post("/command", response_model=CommandResponse, dependencies=[Depends(verify_api_key)])
def process_command(request: CommandRequest):
    return to_response(assistant.handle(request.text, source="api"))


@app.post("/voice", response_model=CommandResponse, dependencies=[Depends(verify_api_key)])
async def process_voice(audio: UploadFile = File(..., description="Audio WAV, FLAC u OGG")):
    from .voice.audio import decode_file
    try:
        samples = decode_file(await audio.read())
    except Exception:
        raise HTTPException(status_code=400, detail="No pude leer el audio. Envía WAV, FLAC u OGG.")
    transcript = get_stt().transcribe(samples)
    if not transcript:
        raise HTTPException(status_code=422, detail="No se entendió ninguna frase en el audio.")
    return to_response(assistant.handle(transcript, source="api-voz"), transcript)


@app.post("/speak", dependencies=[Depends(verify_api_key)])
def speak(request: CommandRequest):
    from .voice.audio import encode_wav
    tts = get_tts()
    return Response(content=encode_wav(tts.synthesize(request.text), tts.sample_rate), media_type="audio/wav")
