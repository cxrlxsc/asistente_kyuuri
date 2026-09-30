# Kyuuri — asistente de voz 100 % local

Asistente de voz en español que corre **entero en tu computadora**. Sin Gemini, sin OpenAI, sin enviar
tu voz a internet y sin pagar APIs. El modelo que entiende los comandos está entrenado desde cero
para este proyecto.

```
Tú:     Kyuuri, ponte en modo trabajo
Kyuuri: Modo trabajo activado.          (abre tu editor y tu música)

Tú:     busca fastapi en github
Kyuuri: Buscando fastapi en GitHub.

Tú:     recuérdame sacar la basura en 20 minutos
Kyuuri: Listo, te recuerdo sacar la basura en 20 minutos.
```

## Cómo funciona

| Pieza | Tecnología | Qué hace |
|---|---|---|
| Cerebro | BETO ajustado con nuestros datos | Decide qué quieres, en ~10 ms |
| Oído | Whisper (local) | Convierte tu voz en texto |
| Voz | Piper (local) | Contesta hablando |
| Conversación | Qwen3 con Ollama | Responde lo que no es un comando |

El clasificador de intenciones se entrena en unos minutos con `training/intents.json`, y **aprende de ti**:
guarda lo que le dices, tú corriges lo que entendió mal y lo reentrenas con tus propias frases.

## Instalación

Doble clic en **`instalar.bat`**. Instala todo lo que falte y configura el asistente para tu equipo.
Detalles, requisitos y solución de problemas: **[INSTALAR.md](INSTALAR.md)**.

Funciona con o sin tarjeta gráfica NVIDIA; sin GPU los comandos van bien y la conversación libre es
más lenta.

## Qué entiende

29 intenciones, en español y en inglés (como se habla en Latinoamérica):

- **Programas:** abrir y cerrar cualquiera de los instalados, incluido "cierra el navegador"
- **Carpetas:** descargas, documentos, escritorio, imágenes, música, vídeos
- **Búsquedas:** Google, YouTube, YouTube Music, Wikipedia, GitHub, Maps, Netflix, Amazon, X
- **Modos:** varias acciones de golpe, configurables en `modes.json`
- **Música:** poner, pausar, siguiente, anterior, volumen
- **Tiempo:** hora, fecha, temporizadores y recordatorios por voz
- **Equipo:** mostrar el escritorio, bloquear, apagar o reiniciar (preguntando antes)
- **Conversación:** cualquier otra cosa se la lleva el LLM local

## Seguridad

Equivocarse conversando no hace daño; ejecutar algo que no pediste, sí. Por eso:

- Solo abre programas que ya están instalados: **nunca ejecuta texto dictado**.
- Las acciones exigen más confianza que la charla, y **una pregunta nunca ejecuta una acción**
  ("¿quién inventó la calculadora?" no cierra nada).
- Cerrar una app no la fuerza: si tienes cambios sin guardar, la app te pregunta.
- Apagar y reiniciar piden confirmación hablada.

## Documentación

- **[INSTALAR.md](INSTALAR.md)** — instalación, uso y problemas comunes
- **[backend/README.md](backend/README.md)** — cómo entrenarlo, agregar comandos, modos y la API

## Licencia

[MIT](LICENSE): úsalo, modifícalo y compártelo libremente, citando la autoría.

## Hecho con software libre

Whisper (MIT) · [BETO](https://github.com/dccuchile/beto) (CC BY 4.0) · Piper (MIT) ·
Qwen3 (Apache 2.0) · PyTorch (BSD) · FastAPI (MIT)
