# Kyuuri — asistente 100 % local

Todo corre en tu equipo: sin Gemini, sin OpenAI, sin enviar tu voz a internet.

| Pieza | Tecnología | Qué hace |
|---|---|---|
| Intenciones | BETO ajustado con `training/intents.json` | Decide qué comando quieres ejecutar |
| Oído | Whisper large-v3-turbo | Convierte tu voz en texto |
| Voz | Piper (`es_MX-claude-high`) | Lee las respuestas en voz alta |
| Conversación | Qwen3 4B Instruct 2507 con Ollama | Responde lo que no es un comando |

Todo junto ocupa ~6.6 GB de memoria de video (probado en una RTX 4060 de 8 GB).
El LLM se eligió frente a `qwen3.5:4b` y `qwen3:1.7b` por acertar más en datos, cálculos y memoria.
En equipos con menos GPU: `WHISPER_MODEL=openai/whisper-small` y `OLLAMA_MODEL=qwen3:1.7b` en `.env`.

## Instalación

```powershell
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
ollama pull qwen3:4b-instruct-2507-q4_K_M
```

## Entrenar el modelo de intenciones

```powershell
.\venv\Scripts\python.exe -m training.train
```

El entrenamiento tiene dos pasos (~2.5 min en GPU):
1. **Evaluación honesta:** entrena sin algunas plantillas y mide cómo le va con frases que nunca vio.
2. **Modelo final:** entrena con todas las plantillas y lo guarda en `models/intent`.

Para enseñarle frases o comandos nuevos, agrégalos a `training/intents.json` y vuelve a entrenar.
Si agregas una intención nueva, también hay que manejarla en `app/assistant.py`.
Las frases que **mencionan** apps o verbos sin ser comandos ("ayer abrí Excel") van en `chat`: evitan acciones por error.

## Español de LATAM y palabras en inglés

Entiende los comandos en español, en inglés y mezclados, como se habla en Latinoamérica:
"open steam", "close the browser", "volume up", "next song", "work mode", "abre el task manager".

- Las muletillas del inicio se ignoran: "Ok, abre Steam" funciona igual que "abre Steam".
- Whisper recibe como pista los nombres de tus apps y sitios, así deja de escribir "vreip" por "Brave".
- "cierra"/"sierra" suenan igual en LATAM: se corrige cuando la frase menciona una app.
- "abre el navegador" abre **tu navegador predeterminado** (se lee del registro de Windows), y
  "cierra el navegador" cierra el que esté abierto, no uno fijo.

## Abrir y cerrar cualquier programa

- **Abrir:** primero busca en su lista rápida (`app_catalog.py`). Si no está, busca entre los programas
  instalados (menú inicio + registro de Windows, `installed_apps.py`): si el parecido es alto lo abre, y si
  hay duda pregunta ("¿Abro FileZilla?"). Si no encuentra nada parecido, lo dice.
- **Cerrar:** le pide a la ventana que se cierre, igual que al hacer clic en la X, así la app avisa si tienes
  algo sin guardar. Si a los 4 segundos sigue abierta, ofrece cerrarla a la fuerza y espera tu "sí".
  Funciona con cualquier programa abierto, no solo con los del catálogo, y nunca toca procesos de Windows
  (lista en `processes.py`).

## Seguridad

Equivocarse conversando no hace daño; ejecutar algo que no pediste, sí. Por eso, antes de actuar:

- Solo abre y cierra apps de la lista blanca (`app/services/app_catalog.py`); nunca ejecuta texto del usuario.
- Las acciones exigen más confianza (`ACTION_CONFIDENCE_THRESHOLD`, 0.8) que la conversación.
- Las preguntas nunca ejecutan acciones: "¿quién inventó la calculadora?" no cierra nada.
- Bloquear el equipo exige nombrarlo ("bloquea la computadora"), así "mi jefe bloqueó mi cuenta" no bloquea nada.
- Cerrar una app no la fuerza: si tiene cambios sin guardar, la app te pregunta.

## Usarlo

```powershell
.\venv\Scripts\python.exe -m app.voice               # por voz: "Kyuuri, abre Spotify"
.\venv\Scripts\python.exe -m app.voice --texto       # por teclado
.\venv\Scripts\python.exe -m app.voice --microfonos  # lista micrófonos; elige uno con MIC_DEVICE en .env
.\venv\Scripts\python.exe -m uvicorn app.main:app    # API en http://127.0.0.1:8000/docs
```

Por voz: di "Kyuuri" y el comando en la misma frase. Durante 25 segundos después de cada respuesta
puedes seguir hablando sin repetir el nombre; pasado ese rato avisa en consola que no era su turno.
Con `--sin-palabra` responde a todo lo que oiga.

"Pon música" reanuda lo que ya esté sonando (reproductor o pestaña del navegador) y, si no hay nada,
abre Apple Music y le manda el play.

### Cambiar el nombre

1. En `.env` cambia `ASSISTANT_NAME` y `WAKE_WORDS`. En `WAKE_WORDS` pon el nombre y las formas en que
   Whisper lo escribe (míralas en la línea "Tú: ..." al hablarle).
2. Reentrena: `.\venv\Scripts\python.exe -m training.train`.

Endpoints: `POST /command` (texto), `POST /voice` (archivo de audio), `POST /speak` (devuelve un WAV).
Si defines `API_KEY` en `.env`, envíala en el header `X-API-Key`.

## Qué entiende

29 intenciones: abrir y cerrar apps (las de `app/services/app_catalog.py` más cualquiera instalada), abrir carpetas
(`folder_catalog.py`), buscar en Google o en sitios concretos (YouTube, GitHub, Maps...), modos
("ponte en modo trabajo"), poner música, hora y fecha, temporizadores y recordatorios ("recuérdame sacar la
basura en 20 minutos"), volumen, música, mostrar el escritorio, bloquear, apagar o reiniciar el equipo
(con confirmación hablada), contar qué sabe hacer, saludar, despedirse y conversar.

Al preguntarle "¿qué sabes hacer?", "¿qué modos tienes?" o "¿qué programas puedes abrir?" responde con datos
reales sacados de sus catálogos (`services/capabilities.py`), no con una lista escrita a mano. Esa misma lista
se le pasa al LLM, así que cuando conversa tampoco se inventa lo que puede hacer.

## Buscar en sitios

"Busca gatos en YouTube", "busca fastapi en GitHub", "búscame la plaza de armas en maps".
Sitios en `app/services/site_catalog.py`: YouTube, YouTube Music, Wikipedia, GitHub, Maps, Netflix, Amazon, X.
Para agregar uno, copia una línea con su URL de búsqueda y reentrena.

## Modos

Un modo hace varias cosas de golpe: "ponte en modo trabajo", "sal del modo trabajo".
Se configuran en `modes.json`, sin tocar código:

```json
"trabajo": {
  "alias": ["trabajo", "programar", "desarrollo"],
  "pasos": [{"app": "vscode"}, {"app": "antigravity"}, {"music": true}],
  "cierra": ["vscode", "antigravity"]
}
```

Pasos disponibles: `{"app": "clave"}`, `{"folder": "clave"}`, `{"url": "https://..."}`,
`{"site": "youtube_music", "query": "lofi"}`, `{"music": true}`, `{"volume": "up|down|mute"}`, `{"wait": 2}`.
Tras crear un modo nuevo, reentrena para que aprenda su nombre: `python -m training.train`.

## Que aprenda de ti

Kyuuri guarda lo que le dices en `data/interactions.jsonl` (solo en tu equipo; se apaga con
`LOG_INTERACTIONS=false`). Para enseñarle con tus frases reales:

```powershell
.\venv\Scripts\python.exe -m training.review              # revisa y corrige lo que entendió
.\venv\Scripts\python.exe -m training.review --solo-dudosas
.\venv\Scripts\python.exe -m training.train               # las aprende
```

En la revisión: Enter si acertó, o el número de la intención correcta si se equivocó. Tus frases quedan en
`training/corrections.json` y pesan el triple que las de ejemplo, porque son cómo hablas de verdad.
