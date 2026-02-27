# 🤖 J.A.R.V.I.S. — Voice-Powered Claude Code

> **Just A Rather Very Intelligent System**
> 
> Controla Claude Code con tu voz, como Tony Stark con JARVIS.

```
🎤 Tu voz → [Whisper STT] → texto → [Claude Code CLI] → texto → [ElevenLabs TTS] → 🔊 Voz
```

## Cómo funciona

JARVIS conecta tres piezas:

1. **Whisper** (faster-whisper) — escucha tu micrófono y transcribe tu voz a texto, todo local en tu Mac
2. **Claude Code CLI** — recibe el texto, ejecuta acciones, y devuelve la respuesta
3. **ElevenLabs** — convierte la respuesta en voz ultra-realista con streaming de baja latencia (~75ms)

El resultado es una experiencia conversacional fluida donde le hablas a tu Mac y Claude te responde con voz natural.

---

## Instalación rápida (macOS)

```bash
# 1. Clona o descarga este directorio
cd jarvis

# 2. Ejecuta el setup (instala todo automáticamente)
chmod +x setup.sh
./setup.sh

# 3. Configura tu API key de ElevenLabs (opcional pero recomendado)
#    Crea cuenta gratis en https://elevenlabs.io
#    Ve a Profile Settings → API Keys
echo 'export ELEVEN_API_KEY="tu-key-aquí"' >> ~/.zshrc
source ~/.zshrc

# 4. Asegúrate de tener Claude Code instalado y autenticado
npm install -g @anthropic-ai/claude-code
claude auth

# 5. ¡Listo! Inicia JARVIS
source .venv/bin/activate
python3 jarvis.py
```

---

## Uso

### Modo básico
```bash
python3 jarvis.py
```

### Con voz británica tipo Jarvis
```bash
python3 jarvis.py --voice Daniel
```

### En inglés
```bash
python3 jarvis.py --lang en --voice James
```

### Sin ElevenLabs (voz nativa de macOS)
```bash
python3 jarvis.py --tts macos
```

### Con mejor precisión de reconocimiento
```bash
python3 jarvis.py --whisper-model small
```

### Con wake word (solo escucha cuando dices "jarvis")
```bash
python3 jarvis.py --wake-word jarvis
```

### Todas las opciones
```bash
python3 jarvis.py --help
```

---

## Voces recomendadas (ElevenLabs)

Para la experiencia más cercana a JARVIS de Iron Man:

| Voz | Estilo | Ideal para |
|-----|--------|------------|
| **Antoni** | Calmada, profesional | Default, buen balance |
| **Daniel** | Británica, elegante | La más "Jarvis" 🎯 |
| **Josh** | Profunda, cálida | Voz de locutor |
| **James** | Formal, narrador | Presentaciones |
| **Callum** | Suave, asistente | Uso cotidiano |

Prueba con: `python3 jarvis.py --voice Daniel`

---

## Modelos Whisper

| Modelo | Velocidad | Precisión | RAM |
|--------|-----------|-----------|-----|
| `tiny` | Muy rápido | Básica | ~1GB |
| `base` | Rápido | Buena | ~1GB |
| `small` | Medio | Muy buena | ~2GB |
| `medium` | Lento | Excelente | ~5GB |
| `large-v3` | Muy lento | Máxima | ~10GB |

Para uso diario, `base` es el mejor balance. Si necesitas mejor precisión en español, usa `small`.

---

## Comandos de voz

- **Para apagar:** Di "apagar", "apágate", "adiós Jarvis", o "cerrar sistema"
- **Para salir:** Presiona `Ctrl+C`
- **Puedes pedir cualquier cosa:** Lo que le pedirías a Claude Code, pero con tu voz

### Ejemplos de lo que puedes decir:

- *"Crea un script en Python que descargue los últimos 10 tweets de una cuenta"*
- *"Revisa el código del archivo main.py y dime si hay bugs"*
- *"Explícame cómo funciona Docker en términos simples"*
- *"Crea una API REST con FastAPI para un to-do list"*
- *"¿Cuál es el estado del repositorio git?"*

---

## Arquitectura

```
┌──────────────────────────────────────────────────┐
│                    JARVIS                         │
│                                                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
│  │   STT    │   │  Claude   │   │     TTS      │ │
│  │ Whisper  │──▶│   Code   │──▶│  ElevenLabs  │ │
│  │ (local)  │   │  (CLI)   │   │  (streaming) │ │
│  └──────────┘   └──────────┘   └──────────────┘ │
│       ▲                               │          │
│       │         ┌──────────┐          │          │
│       └─────────│   User   │◀─────────┘          │
│                 │  🎤  🔊  │                     │
│                 └──────────┘                     │
└──────────────────────────────────────────────────┘
```

---

## Troubleshooting

### "PyAudio no se instala"
```bash
brew install portaudio
pip install pyaudio
```

### "No escucha mi voz"
- Verifica permisos de micrófono: System Settings → Privacy & Security → Microphone → Terminal
- Ajusta el umbral de silencio: `python3 jarvis.py --silence-threshold 300`

### "Las transcripciones son malas"
- Usa un modelo más grande: `--whisper-model small`
- Habla más claro y cerca del micrófono
- Reduce ruido de fondo

### "ElevenLabs no funciona"
- Verifica tu API key: `echo $ELEVEN_API_KEY`
- Verifica tu cuota en https://elevenlabs.io/subscription
- Usa fallback: `--tts macos`

### "Claude Code no responde"
- Verifica autenticación: `claude auth`
- Verifica que funcione: `claude -p "di hola"`

---

## Requisitos

- macOS 13+ (Ventura o superior)
- Python 3.10+
- Claude Code CLI (con suscripción Pro/Max o API key)
- ElevenLabs API key (plan gratuito funciona, opcional)
- Micrófono funcional

---

## Costos estimados

- **Whisper:** Gratis (corre 100% local)
- **Claude Code:** Incluido en suscripción Pro ($20/mes) o Max ($100/mes)
- **ElevenLabs:** Plan gratuito ~10,000 chars/mes, Starter $5/mes ~30,000 chars/mes
- **macOS TTS:** Gratis (como alternativa a ElevenLabs)

Para uso casual (10-20 interacciones por día), el plan gratuito de ElevenLabs es suficiente.
