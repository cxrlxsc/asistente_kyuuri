import difflib
import re
from typing import Optional

from ..core.config import settings
from ..services.app_catalog import all_aliases
from ..services.folder_catalog import folder_aliases
from ..services.modes import mode_aliases
from ..services.site_catalog import SITES, site_aliases
from .text import normalize

FILLERS = {"oye", "hey", "ey", "a", "ver", "ok", "okay", "oka", "bueno", "este", "mira", "eh", "ah",
           "entonces", "ahora", "listo", "y", "pues", "porfa"}
LEADING_FILLERS = re.compile(r"^\s*[¿¡]?\s*(?:(oye|hey|ey|ok|okay|oka|bueno|este|mira|eh|ah|entonces|ahora|listo|"
                             r"pues|porfa|a ver)\b[\s,.!?]*)+", re.IGNORECASE)
QUESTION_START = re.compile(
    r"^(que|como|cual|cuales|quien|quienes|por que|porque|cuanto|cuanta|cuantos|cuantas|donde|adonde|cuando|"
    r"es malo|es bueno|sabes|sabias|conoces|explicame|cuentame)\b"
)

# Palabras de activación que se quitan del texto para quedarse solo con lo que hay que buscar
SEARCH_PREFIX = re.compile(
    r"^(por favor\s+)?(puedes\s+|quiero\s+|haz una\s+)?"
    r"(buscalo|buscame|busca|buscar|busqueda de|googlea|investiga|encuentra|pon)"
    r"(\s+en\s+(google|internet|la web))?"
    r"(\s+(informacion|info)\s+(sobre|de))?\s+"
)
SEARCH_SUFFIX = re.compile(r"\s+en\s+(google|internet|la web)$")
# "cierra" y "sierra" suenan igual en español latino; Whisper a veces escribe "sierra Spotify"
SIERRA = re.compile(r"\bs(i[eé]rr(a|e|as|ame|alo|ala)\b)", re.IGNORECASE)
APP_VERBS = re.compile(r"^(puedes|podrias|quiero|necesito|me)?\s*"
                       r"(abre|abreme|abrir|abrete|cierra|cierrame|cerrar|inicia|iniciar|ejecuta|ejecutar|lanza|"
                       r"arranca|corre|carga|prende|prendeme|enciende|apaga|termina|finaliza|mata|quita|quitame|"
                       r"entra|abres|cierras|muestrame|ponme|pon|sal|sacame|levanta|detén|deten)\b")


NUMBER_WORDS = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "veinte": 20, "veinticinco": 25, "treinta": 30, "cuarenta": 40, "cuarenta y cinco": 45, "cincuenta": 50, "sesenta": 60,
    # En LATAM se mezcla el inglés
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "sixty": 60,
}
UNIT_SECONDS = {"segundo": 1, "minuto": 60, "hora": 3600, "second": 1, "minute": 60, "hour": 3600}
DURATION = re.compile(r"(\d+|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) +
                      r")\s+(segundos?|minutos?|horas?|seconds?|minutes?|hours?)")
HALF_HOUR = re.compile(r"\b(media hora|half an hour)\b")
QUARTER_HOUR = re.compile(r"\b(un )?cuarto de hora\b|\ba quarter of an hour\b")
AND_A_HALF = re.compile(r"\b(hora|minuto)\s+y\s+media?\b")
# "recuérdame sacar la basura en 20 minutos" -> "sacar la basura"
REMINDER = re.compile(r"recuerdame\s+(?:que\s+)?(.+?)\s+(?:en|dentro de|para dentro de)\s+\d|"
                      r"recuerdame\s+(?:que\s+)?(.+?)\s+(?:en|dentro de)\s+(?:" + "|".join(NUMBER_WORDS) + r")\b")

# Para bloquear hay que nombrar el equipo: "mi jefe bloqueó mi cuenta" no debe bloquear la PC
DEVICE_WORDS = re.compile(r"\b(computadora|computador|compu|pc|laptop|equipo|pantalla|sesion|todo|bloqueala|candado)\b")


def mentions_device(text: str) -> bool:
    return bool(DEVICE_WORDS.search(normalize(text)))


def strip_leading_words(clean: str) -> str:
    """Quita del inicio el nombre del asistente y muletillas ("oye kyuuri busca..." -> "busca...")."""
    words = clean.split()
    while words and (words[0] in FILLERS or words[0] in settings.WAKE_WORDS):
        words.pop(0)
    return " ".join(words)


def strip_fillers(text: str) -> str:
    """Quita muletillas del inicio conservando el resto tal cual: "Ok, abre Steam" -> "abre Steam"."""
    return LEADING_FILLERS.sub("", text).strip() or text


def is_question(text: str) -> bool:
    """Las preguntas ("¿cómo se abre un coco?") nunca deben ejecutar acciones, aunque mencionen apps o verbos de comando."""
    return bool(QUESTION_START.match(strip_leading_words(normalize(text))))


def fix_transcription(text: str) -> str:
    """Corrige homófonos solo si se menciona una app, para no romper búsquedas como "la Sierra Nevada"."""
    if SIERRA.search(text) and extract_app(text):
        return SIERRA.sub(r"c\1", text)
    return text


def extract_app(text: str) -> Optional[str]:
    clean = normalize(text)
    padded = f" {clean} "
    aliases = all_aliases()
    for alias, key in aliases:
        if f" {alias} " in padded:
            return key

    # Tolerancia a errores de escritura o de transcripción: "calculadroa" -> "calculadora"
    alias_to_key = dict(aliases)
    for word in clean.split():
        match = difflib.get_close_matches(word, alias_to_key.keys(), n=1, cutoff=0.8)
        if match:
            return alias_to_key[match[0]]
    return None


def extract_duration(text: str) -> Optional[int]:
    """Segundos que pide la frase: "5 minutos", "media hora", "hora y media", "un cuarto de hora"."""
    clean = normalize(text)
    if AND_A_HALF.search(clean):
        unit = AND_A_HALF.search(clean).group(1)
        return 5400 if unit == "hora" else 90
    if HALF_HOUR.search(clean):
        return 1800
    if QUARTER_HOUR.search(clean):
        return 900
    match = DURATION.search(clean)
    if not match:
        return None
    amount, unit = match.groups()
    value = int(amount) if amount.isdigit() else NUMBER_WORDS[amount]
    return value * UNIT_SECONDS[unit.rstrip("s")]


def extract_reminder(text: str) -> Optional[str]:
    """Qué hay que recordar, sin el "recuérdame" ni el tiempo."""
    match = REMINDER.search(normalize(text))
    if not match:
        return None
    label = next(group for group in match.groups() if group)
    return label.strip() or None


def extract_app_name(text: str) -> str:
    """El nombre del programa pedido, sin el verbo ni los artículos: "ciérrame el navegador brave" -> "navegador brave"."""
    clean = strip_leading_words(normalize(text))
    clean = APP_VERBS.sub("", clean)
    clean = re.sub(r"\b(el|la|los|las|mi|mis|un|una|programa|aplicacion|app|ventana|de)\b", " ", clean)
    clean = re.sub(r"\b(por favor|ahora|ya)\b", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()


def extract_site(text: str) -> Optional[str]:
    clean = f" {normalize(text)} "
    for alias, key in site_aliases():
        if f" {alias} " in clean:
            return key
    return None


def extract_site_query(text: str, site_key: str) -> str:
    """Lo que hay que buscar, sin el verbo ni el nombre del sitio: "busca gatos en youtube" -> "gatos"."""
    clean = strip_leading_words(normalize(text))
    clean = SEARCH_PREFIX.sub("", clean)
    for alias in sorted(SITES[site_key].aliases, key=len, reverse=True):
        clean = re.sub(rf"\b(en|por|de|dentro de)\s+{re.escape(alias)}\b", " ", clean)
        clean = re.sub(rf"\b{re.escape(alias)}\b", " ", clean)
    clean = re.sub(r"^(pon|ponme|reproduce|abre|busca|buscame|dame)\b", "", clean)
    return re.sub(r"\s+", " ", clean).strip(" ,.")


def extract_mode(text: str) -> Optional[str]:
    clean = f" {normalize(text)} "
    for alias, name in mode_aliases():
        if f" {alias} " in clean:
            return name
    return None


def extract_folder(text: str) -> Optional[str]:
    clean = f" {normalize(text)} "
    for alias, key in folder_aliases():
        if f" {alias} " in clean:
            return key
    return None


def extract_query(text: str) -> str:
    clean = strip_leading_words(normalize(text))
    query = SEARCH_SUFFIX.sub("", SEARCH_PREFIX.sub("", clean))
    return query or clean
