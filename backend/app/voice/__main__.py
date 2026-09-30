"""
El asistente por voz (o por teclado).

Uso (desde la carpeta backend):
    python -m app.voice              escucha el micrófono y se activa al decir su nombre (WAKE_WORDS en .env)
    python -m app.voice --sin-palabra responde a todo lo que escuche, sin palabra de activación
    python -m app.voice --texto      escribe los comandos en la terminal (sin micrófono)
    python -m app.voice --mudo       no habla, solo imprime las respuestas
    python -m app.voice --microfonos lista los micrófonos (elige uno con MIC_DEVICE en .env)
"""
import argparse
import difflib
import sys
import time

from ..assistant import Assistant
from ..core.config import settings
from ..nlu.text import normalize

FOLLOW_UP_SECONDS = 25  # tras responder, no hace falta repetir la palabra de activación


def strip_wake_word(text: str) -> tuple[bool, str]:
    """Detecta la palabra de activación entre las 3 primeras palabras, tolerando cómo la transcriba Whisper ("kiury")."""
    words = text.split()
    for i, word in enumerate(words[:3]):
        clean = normalize(word)
        if any(difflib.SequenceMatcher(None, clean, wake).ratio() >= 0.75 for wake in settings.WAKE_WORDS):
            return True, " ".join(words[i + 1:]).strip(" ,.!?¿¡")
    return False, text


def main():
    parser = argparse.ArgumentParser(description=f"{settings.ASSISTANT_NAME} por voz")
    parser.add_argument("--texto", action="store_true", help="usar el teclado en vez del micrófono")
    parser.add_argument("--sin-palabra", action="store_true", help="no exigir la palabra de activación")
    parser.add_argument("--mudo", action="store_true", help="no reproducir la voz")
    parser.add_argument("--microfonos", action="store_true", help="listar los micrófonos disponibles")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

    if args.microfonos:
        from .microphone import input_devices
        for index, name in input_devices():
            print(f"{index:3}  {name}")
        return

    print("Cargando modelos...")
    assistant = Assistant()
    tts = None
    if not args.mudo:
        from .tts import TextToSpeech
        tts = TextToSpeech()

    def say(message: str):
        print(f"{settings.ASSISTANT_NAME}: {message}")
        if tts:
            tts.say(message)

    # Los temporizadores y recordatorios avisan en voz alta cuando se cumplen
    assistant.timers.notify = say

    def respond(command: str, source: str) -> bool:
        started = time.perf_counter()
        reply = assistant.handle(command, source)
        print(f"  [{reply.intent} {reply.confidence:.0%} · {time.perf_counter() - started:.2f}s]")
        say(reply.text)
        return reply.intent != "goodbye"

    if args.texto:
        print("Escribe tus comandos (Ctrl+C para salir).")
        while True:
            try:
                command = input("Tú: ")
            except (EOFError, KeyboardInterrupt):
                return
            if command.strip() and not respond(command, "texto"):
                return

    from .microphone import Microphone
    from .stt import SpeechToText
    stt = SpeechToText()
    mic = Microphone(settings.MIC_DEVICE)
    print(f"Micrófono: {mic.name}")
    print("Calibrando el ruido del ambiente, guarda silencio un segundo...")
    try:
        mic.calibrate()
    except RuntimeError as e:
        sys.exit(str(e))

    wake = settings.ASSISTANT_NAME
    print(f"Listo. Di '{wake}, ...' (Ctrl+C para salir)." if not args.sin_palabra else "Listo, te escucho.")
    awake_until = 0.0
    try:
        while True:
            text = stt.transcribe(mic.listen())
            if not text:
                continue
            print(f"Tú: {text}")

            woke, command = strip_wake_word(text)
            if not (woke or args.sin_palabra or time.time() < awake_until):
                # Sin esto parece que el asistente se cuelga, cuando en realidad no fue su turno
                print(f'  (no hice nada: empieza con "{settings.ASSISTANT_NAME}" para hablarme)')
                continue
            if not command:
                say("¿Sí?")
                awake_until = time.time() + FOLLOW_UP_SECONDS
                continue

            if not respond(command, "voz"):
                return
            awake_until = time.time() + FOLLOW_UP_SECONDS
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
