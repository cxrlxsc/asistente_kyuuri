# Instalar Kyuuri

Kyuuri es un asistente de voz que funciona **entero en tu computadora**: no envía tu voz a internet
y no usa servicios de pago.

## Lo que necesitas

| | Mínimo | Recomendado |
|---|---|---|
| Sistema | Windows 10 o 11 | Windows 11 |
| Espacio libre | 8 GB | 12 GB |
| Memoria | 8 GB de RAM | 16 GB |
| Tarjeta gráfica | ninguna (funciona más lento) | NVIDIA con 8 GB |
| Internet | solo para instalar | |

## Instalación

1. Descarga la carpeta del proyecto.
2. Doble clic en **`instalar.bat`**.
3. Espera. Descarga entre 4 y 10 GB según tu equipo, así que puede tardar bastante.
4. Al terminar tendrás un acceso directo **Kyuuri** en el escritorio.

El instalador se encarga de todo: instala Python si falta, elige la versión de PyTorch según tu
tarjeta gráfica, instala Ollama, configura el micrófono y prepara los modelos.

## Cómo se usa

Abre **Kyuuri** y di su nombre seguido de lo que quieres:

- "Kyuuri, abre Spotify" · "cierra el navegador" · "abre la carpeta de descargas"
- "busca gatos en YouTube" · "pon música" · "súbele al volumen"
- "ponme un temporizador de 10 minutos" · "recuérdame sacar la basura en 20 minutos"
- "ponte en modo trabajo" · "qué hora es" · "qué sabes hacer"
- Y cualquier otra cosa: si no es un comando, conversa contigo.

Después de que responde, tienes 25 segundos para seguir hablando sin repetir su nombre.

## Qué tan rápido va

Medido en una laptop con RTX 4060:

| | Con GPU NVIDIA | Solo procesador |
|---|---|---|
| Entender un comando | 10 ms | 20 ms |
| Entender lo que dijiste | 0.3 s | 1.6 s |
| Responder hablando | 0.1 s | 0.1 s |
| Conversar (respuesta del LLM) | 1.5 s | 10 a 30 s |

Sin GPU los comandos van bien; lo que se siente lento es la conversación libre.

## Si algo no funciona

```
python -m app.diagnose
```
Ese comando revisa todo y dice cómo arreglar lo que falte. Ejecútalo dentro de la carpeta `backend`
con el Python del entorno: `backend\venv\Scripts\python.exe -m app.diagnose`.

Problemas comunes:

- **No me escucha:** puede que Windows esté usando otro micrófono. Corre `python -m app.configure`
  y elige uno; el configurador prueba cuáles entregan audio de verdad.
- **No reacciona cuando digo su nombre:** mira en la consola la línea `Tú: ...` para ver cómo se
  transcribió, y agrega esa forma a `WAKE_WORDS` en el archivo `.env`.
- **La conversación va lentísima aunque tengo GPU NVIDIA:** Ollama pudo elegir la gráfica integrada.
  Ejecuta `setx OLLAMA_VULKAN 0` y `setx OLLAMA_IGPU_ENABLE 0`, y reinicia Ollama.

## Privacidad y seguridad

- Todo corre local: tu voz, lo que dices y las respuestas no salen de tu equipo.
- Guarda lo que le dices en `backend/data/` solo para que puedas mejorarlo. Se apaga con
  `LOG_INTERACTIONS=false` en el `.env`.
- **Kyuuri puede cerrar programas, bloquear y apagar tu equipo.** Apagar y reiniciar te preguntan
  antes. Solo abre programas que ya están instalados; nunca ejecuta lo que dictes como texto.

## Hecho con software libre

Whisper (OpenAI, MIT) · BETO (Universidad de Chile, CC BY 4.0) · Piper (MIT) ·
Qwen3 (Alibaba, Apache 2.0) · PyTorch (BSD) · FastAPI (MIT)
