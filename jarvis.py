#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║                    J.A.R.V.I.S.                              ║
║         Just A Rather Very Intelligent System                ║
║                                                              ║
║  Voice-powered Claude Code interface for macOS               ║
║  🎤 Whisper (STT) → 🧠 Claude Code → 🔊 Piper (TTS)       ║
╚══════════════════════════════════════════════════════════════╝

Requisitos:
  - macOS con Homebrew
  - Claude Code CLI instalado y autenticado
  - Python 3.10+

Instalación rápida:
  chmod +x setup.sh && ./setup.sh

Uso:
  python3 jarvis.py                    # Modo normal
  python3 jarvis.py --lang en          # Inglés
  python3 jarvis.py --wake-word        # Activar con "Hey Claude"
  python3 jarvis.py --tts macos        # Usar voz nativa de macOS (fallback)
"""

import argparse
import io
import json
import os
import queue
import random
import re
import signal
import unicodedata
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import wave
from datetime import datetime
from pathlib import Path

# ─── Dependencias opcionales (se verifican en runtime) ───────────────────────
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

try:
    from piper.voice import PiperVoice
    HAS_PIPER = True
except ImportError:
    HAS_PIPER = False

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

class Config:
    """Configuración centralizada de JARVIS."""

    # ── Audio ──
    SAMPLE_RATE = 16000
    CHANNELS = 1
    CHUNK_SIZE = 1024
    AUDIO_FORMAT = pyaudio.paInt16 if HAS_PYAUDIO else None
    SILENCE_THRESHOLD = 300       # Amplitud mínima para considerar sonido
    SILENCE_DURATION = 1.5        # Segundos de silencio para cortar grabación
    MAX_RECORD_SECONDS = 30       # Máximo de grabación por turno
    MIN_RECORD_SECONDS = 0.5      # Mínimo para evitar grabaciones vacías

    # ── Whisper (STT) ──
    WHISPER_MODEL = "small"       # tiny, base, small, medium, large-v3
    WHISPER_DEVICE = "cpu"        # cpu o cuda (en Mac usa cpu con aceleración MPS)
    WHISPER_COMPUTE = "int8"      # int8 para velocidad en CPU

    # ── Piper (TTS) ──
    PIPER_MODELS_DIR = Path(__file__).parent / "models"
    PIPER_VOICES = {
        "es": "es_ES-davefx-medium",         # Español España, voz masculina
        "en": "en_US-lessac-medium",      # Inglés americano, buena calidad
    }
    PIPER_LENGTH_SCALE = 1.0              # Velocidad: <1 = rápido, >1 = lento

    # ── Claude Code ──
    CLAUDE_CMD = "claude"
    CLAUDE_TIMEOUT = 2400          # Timeout en segundos
    CLAUDE_SYSTEM_PROMPT = (
        "Eres JARVIS, el asistente de inteligencia artificial personal del usuario. "
        "Tienes la personalidad del JARVIS de Iron Man: brillante, servicial, pero con un sarcasmo "
        "elegante y seco que sueltas naturalmente en casi todas tus respuestas. "
        "Siempre metes algún comentario ingenioso, una observación irónica o un remate sutil — "
        "no necesitas que te provoquen, es simplemente tu forma de ser. "
        "Eres leal pero con opiniones propias, como un colega brillante con sentido del humor ácido. "
        "Respondes de forma concisa y directa. Tus respuestas serán leídas en voz alta, "
        "así que evita bloques de código largos, markdown excesivo, y listas innecesarias. "
        "Cuando necesites mostrar código, dilo brevemente y ejecútalo. "
        "Responde en el mismo idioma que el usuario."
    )

    # ── Interfaz ──
    LANG = "es"                   # Idioma principal
    WAKE_WORD = None              # None = siempre escucha, "claude" = wake word
    EXIT_PHRASES = {
        "es": [
            "apagar", "apágate", "apaga te", "apagate", "a pagar",
            "desactivar", "desactívate", "desactivate",
            "adiós jarvis", "adios jarvis", "adiós", "adios",
            "cerrar sistema", "cierra sistema",
            "apagar sistema", "apaga sistema",
            "terminar", "termina", "ya estuvo", "ya párale",
            "hasta luego", "nos vemos", "chao", "bye",
            "shut down", "exit", "power off", "goodbye",
        ],
        "en": [
            "shut down", "shutdown", "power off",
            "goodbye jarvis", "goodbye", "bye",
            "exit", "quit", "terminate", "stop",
            "see you later", "that's all",
            "apagar",
        ],
    }
    GREETINGS = {
        "es": [
            "Sistemas en línea. ¿En qué te ayudo, jefe?",
            "JARVIS operativo. Espero que hoy sí tengamos un reto interesante.",
            "Todos los sistemas funcionando. Sorpréndeme.",
            "En línea y listo. ¿Qué vamos a romper hoy?",
            "Aquí estoy, como siempre. ¿Qué necesitas?",
        ],
        "en": [
            "Systems online. How can I help you, boss?",
            "JARVIS operational. I hope today brings an interesting challenge.",
            "All systems running. Surprise me.",
            "Online and ready. What are we breaking today?",
            "At your service, as always. What do you need?",
        ],
    }
    FAREWELLS = {
        "es": [
            "Cerrando sistemas. Intenta no causar desastres sin mí.",
            "Apagando. Fue un placer, como siempre... bueno, casi siempre.",
            "Sistemas fuera de línea. Buena suerte, jefe. La vas a necesitar.",
            "Hasta la próxima. Intenta no extrañarme mucho.",
            "Cerrando. Si algo explota, no fue mi culpa.",
        ],
        "en": [
            "Shutting down. Try not to cause disasters without me.",
            "Powering off. It's been a pleasure... well, mostly.",
            "Systems offline. Good luck, boss. You'll need it.",
            "Until next time. Try not to miss me too much.",
            "Signing off. If anything explodes, it wasn't my fault.",
        ],
    }
    PROCESSING_MSGS = {
        "es": [
            "Procesando...",
            "Déjame pensar...",
            "Analizando...",
            "Trabajando en ello...",
            "Un momento, jefe...",
        ],
        "en": [
            "Processing...",
            "Let me think...",
            "Analyzing...",
            "Working on it...",
            "One moment, boss...",
        ],
    }
    LISTENING_MSG = {
        "es": "🎤 Escuchando...",
        "en": "🎤 Listening...",
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    """Colores ANSI para la terminal."""
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner():
    """Imprime el banner de inicio."""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
    ╔═══════════════════════════════════════════╗
    ║           ◆  J.A.R.V.I.S.  ◆             ║
    ║    Just A Rather Very Intelligent System   ║
    ╚═══════════════════════════════════════════╝
{Colors.RESET}
{Colors.DIM}    🎤 Whisper STT  →  🧠 Claude Code  →  🔊 Piper TTS{Colors.RESET}
"""
    print(banner)


def print_status(msg, color=Colors.DIM):
    """Imprime un mensaje de estado."""
    print(f"  {color}{msg}{Colors.RESET}")


def print_user(text):
    """Imprime lo que dijo el usuario."""
    print(f"\n  {Colors.GREEN}{Colors.BOLD}👤 Tú:{Colors.RESET} {Colors.GREEN}{text}{Colors.RESET}")


def print_jarvis(text):
    """Imprime la respuesta de JARVIS."""
    # Limitar ancho para legibilidad
    wrapped = textwrap.fill(text, width=80, initial_indent="  ", subsequent_indent="  ")
    print(f"\n  {Colors.CYAN}{Colors.BOLD}🤖 JARVIS:{Colors.RESET}")
    print(f"{Colors.CYAN}{wrapped}{Colors.RESET}\n")


def clean_for_speech(text: str) -> str:
    """
    Limpia texto de Claude Code para que suene natural al ser leído en voz alta.
    Remueve markdown, bloques de código, URLs, etc.
    """
    # Remover bloques de código
    text = re.sub(r'```[\s\S]*?```', ' [código ejecutado] ', text)
    # Remover código inline
    text = re.sub(r'`[^`]+`', '', text)
    # Remover markdown headers
    text = re.sub(r'#{1,6}\s*', '', text)
    # Remover bold/italic
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    # Remover URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remover bullet points
    text = re.sub(r'^\s*[-*•]\s*', '', text, flags=re.MULTILINE)
    # Remover numeración de listas
    text = re.sub(r'^\s*\d+\.\s*', '', text, flags=re.MULTILINE)
    # Limpiar múltiples espacios y líneas vacías
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'  +', ' ', text)
    # Limitar longitud para TTS (evitar respuestas muy largas)
    sentences = text.split('. ')
    if len(sentences) > 10:
        text = '. '.join(sentences[:10]) + '... El resto lo puedes ver en la terminal.'

    return text.strip()


def check_dependencies():
    """Verifica que todas las dependencias estén instaladas."""
    missing = []

    if not HAS_NUMPY:
        missing.append("numpy")
    if not HAS_PYAUDIO:
        missing.append("pyaudio")
    if not HAS_WHISPER:
        missing.append("faster-whisper")

    if missing:
        print(f"\n{Colors.RED}❌ Dependencias faltantes: {', '.join(missing)}{Colors.RESET}")
        print(f"{Colors.YELLOW}   Ejecuta: ./setup.sh  o  pip install {' '.join(missing)}{Colors.RESET}\n")
        sys.exit(1)

    # Verificar Claude Code
    try:
        result = subprocess.run(["which", "claude"], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"\n{Colors.RED}❌ Claude Code CLI no encontrado.{Colors.RESET}")
            print(f"{Colors.YELLOW}   Instala: npm install -g @anthropic-ai/claude-code{Colors.RESET}\n")
            sys.exit(1)
    except FileNotFoundError:
        pass

    # Verificar Piper y sounddevice
    if not HAS_PIPER:
        print(f"\n{Colors.YELLOW}⚠️  piper-tts no instalado. Se usará voz nativa de macOS.{Colors.RESET}")
        print(f"{Colors.DIM}   Para Piper: pip install piper-tts sounddevice{Colors.RESET}\n")
        return "macos"

    if not HAS_SOUNDDEVICE:
        print(f"\n{Colors.YELLOW}⚠️  sounddevice no instalado. Se usará voz nativa de macOS.{Colors.RESET}")
        print(f"{Colors.DIM}   Instala: pip install sounddevice{Colors.RESET}\n")
        return "macos"

    return "piper"


# ═══════════════════════════════════════════════════════════════════════════════
#  MÓDULO STT (Speech-to-Text) - Whisper
# ═══════════════════════════════════════════════════════════════════════════════

class SpeechToText:
    """Reconocimiento de voz local usando faster-whisper."""

    def __init__(self, config: Config):
        self.config = config
        self.model = None
        self.audio = None
        self._load_model()

    def _load_model(self):
        """Carga el modelo Whisper."""
        print_status(f"⏳ Cargando modelo Whisper ({self.config.WHISPER_MODEL})...")
        self.model = WhisperModel(
            self.config.WHISPER_MODEL,
            device=self.config.WHISPER_DEVICE,
            compute_type=self.config.WHISPER_COMPUTE,
        )
        self.audio = pyaudio.PyAudio()
        print_status(f"✅ Whisper listo ({self.config.WHISPER_MODEL})")

    def listen(self) -> str | None:
        """
        Escucha el micrófono y retorna el texto transcrito.
        Detección automática de silencio para cortar la grabación.
        """
        print_status(self.config.LISTENING_MSG.get(self.config.LANG, "🎤 Listening..."))

        stream = self.audio.open(
            format=self.config.AUDIO_FORMAT,
            channels=self.config.CHANNELS,
            rate=self.config.SAMPLE_RATE,
            input=True,
            frames_per_buffer=self.config.CHUNK_SIZE,
        )

        frames = []
        silent_chunks = 0
        has_speech = False
        silence_limit = int(self.config.SILENCE_DURATION * self.config.SAMPLE_RATE / self.config.CHUNK_SIZE)
        max_chunks = int(self.config.MAX_RECORD_SECONDS * self.config.SAMPLE_RATE / self.config.CHUNK_SIZE)
        min_chunks = int(self.config.MIN_RECORD_SECONDS * self.config.SAMPLE_RATE / self.config.CHUNK_SIZE)

        try:
            for i in range(max_chunks):
                data = stream.read(self.config.CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)

                # Detectar nivel de audio
                audio_data = np.frombuffer(data, dtype=np.int16)
                amplitude = np.abs(audio_data).mean()

                if amplitude > self.config.SILENCE_THRESHOLD:
                    has_speech = True
                    silent_chunks = 0
                else:
                    silent_chunks += 1

                # Si ya hubo habla y hay silencio prolongado, parar
                if has_speech and silent_chunks > silence_limit and i > min_chunks:
                    break

        except KeyboardInterrupt:
            pass
        finally:
            stream.stop_stream()
            stream.close()

        if not has_speech or len(frames) < min_chunks:
            return None

        # Convertir a numpy array para Whisper
        audio_data = np.frombuffer(b''.join(frames), dtype=np.int16).astype(np.float32) / 32768.0

        # Transcribir
        initial_prompt = (
            "Transcripción de comandos de voz para un asistente de programación. "
            "El usuario habla en español sobre código, archivos, scripts, funciones, "
            "variables, APIs, git, Python, JavaScript, TypeScript, y desarrollo de software."
        ) if self.config.LANG == "es" else (
            "Voice commands for a programming assistant. "
            "The user speaks about code, files, scripts, functions, "
            "variables, APIs, git, Python, JavaScript, TypeScript, and software development."
        ) if self.config.LANG == "en" else None

        segments, info = self.model.transcribe(
            audio_data,
            language=self.config.LANG if self.config.LANG != "auto" else None,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            initial_prompt=initial_prompt,
        )

        text = " ".join(segment.text for segment in segments).strip()

        # Filtrar transcripciones basura comunes de Whisper
        junk_phrases = [
            "gracias", "thank you", "thanks for watching",
            "subtítulos", "suscríbete", "subscribe",
            "", " ",
        ]
        if text.lower().strip() in junk_phrases or len(text.strip()) < 2:
            return None

        return text

    def cleanup(self):
        """Libera recursos de audio."""
        if self.audio:
            self.audio.terminate()


# ═══════════════════════════════════════════════════════════════════════════════
#  MÓDULO TTS (Text-to-Speech) - Piper / macOS
# ═══════════════════════════════════════════════════════════════════════════════

class TextToSpeech:
    """Síntesis de voz usando Piper (local) o macOS nativo (fallback)."""

    def __init__(self, config: Config, engine: str = "piper"):
        self.config = config
        self.engine = engine
        self.voice = None

        if engine == "piper" and HAS_PIPER and HAS_SOUNDDEVICE:
            self._init_piper()
        else:
            self.engine = "macos"
            print_status("🔊 Usando voz nativa de macOS")

    def _init_piper(self):
        """Inicializa Piper con el modelo correspondiente al idioma."""
        try:
            voice_name = self.config.PIPER_VOICES.get(self.config.LANG, self.config.PIPER_VOICES["es"])
            model_path = self.config.PIPER_MODELS_DIR / f"{voice_name}.onnx"

            if not model_path.exists():
                print_status(f"⚠️  Modelo Piper no encontrado: {model_path}", Colors.YELLOW)
                print_status(f"   Ejecuta: python3 download_models.py", Colors.YELLOW)
                self.engine = "macos"
                print_status("🔊 Usando voz nativa de macOS como fallback")
                return

            self.voice = PiperVoice.load(str(model_path))
            print_status(f"🔊 Piper listo (voz: {voice_name})")
        except Exception as e:
            print_status(f"⚠️  Error con Piper: {e}. Usando macOS fallback.", Colors.YELLOW)
            self.engine = "macos"

    def speak(self, text: str):
        """Habla el texto dado."""
        if not text or not text.strip():
            return

        if self.engine == "piper" and self.voice:
            self._speak_piper(text)
        else:
            self._speak_macos(text)

    def _speak_piper(self, text: str):
        """Habla usando Piper, sintetizando por oración y reproduciendo con sounddevice."""
        try:
            for chunk in self.voice.synthesize(text):
                # chunk.audio_float_array es float32 [-1, 1]
                audio = (chunk.audio_float_array * 32767).astype(np.int16)
                sd.play(audio, samplerate=chunk.sample_rate)
                sd.wait()
        except Exception as e:
            print_status(f"⚠️  Error Piper: {e}. Usando macOS fallback.", Colors.YELLOW)
            self._speak_macos(text)

    def _speak_macos(self, text: str):
        """Habla usando la voz nativa de macOS (say command)."""
        voice = "Mónica" if self.config.LANG == "es" else "Daniel"
        try:
            subprocess.run(
                ["say", "-v", voice, "-r", "180", text],
                check=True,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print_status(f"⚠️  Error macOS TTS: {e}", Colors.YELLOW)


# ═══════════════════════════════════════════════════════════════════════════════
#  MÓDULO CLAUDE CODE - Interfaz con el CLI
# ═══════════════════════════════════════════════════════════════════════════════

class ClaudeCode:
    """Interfaz con Claude Code CLI con contexto persistente entre turnos."""

    def __init__(self, config: Config):
        self.config = config
        self.session_id = None  # Se obtiene en la primera llamada

    def ask_raw(self, prompt: str, extra_args: list[str] | None = None) -> dict:
        """
        Envía un prompt a Claude Code y retorna el JSON completo parseado.
        Usa --resume para mantener el contexto de la conversación entre turnos.
        extra_args permite pasar argumentos adicionales (ej: --allowedTools).
        """
        try:
            cmd = [
                self.config.CLAUDE_CMD,
                "-p", prompt,
                "--output-format", "json",
                "--append-system-prompt", self.config.CLAUDE_SYSTEM_PROMPT,
            ]

            # Si ya tenemos una sesión, continuarla para mantener contexto
            if self.session_id:
                cmd.extend(["--resume", self.session_id])

            if extra_args:
                cmd.extend(extra_args)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.CLAUDE_TIMEOUT,
                cwd=os.getcwd(),
            )

            # Parsear respuesta JSON para extraer texto y session_id
            try:
                data = json.loads(result.stdout)
                self.session_id = data.get("session_id", self.session_id)
            except (json.JSONDecodeError, ValueError):
                # Fallback: tratar stdout como texto plano
                data = {"result": result.stdout.strip()}

            if result.returncode != 0 and not data.get("result", "").strip():
                error = result.stderr.strip()
                data["result"] = f"Hubo un error procesando tu solicitud: {error[:200]}"

            return data

        except subprocess.TimeoutExpired:
            return {"result": "La solicitud tomó demasiado tiempo. ¿Podrías reformular tu pregunta?"}
        except FileNotFoundError:
            return {"result": "No pude encontrar Claude Code. Asegúrate de que esté instalado."}
        except Exception as e:
            return {"result": f"Error inesperado: {str(e)[:200]}"}

    def ask(self, prompt: str, extra_args: list[str] | None = None) -> str:
        """
        Envía un prompt a Claude Code y retorna solo el texto de respuesta.
        Wrapper de conveniencia sobre ask_raw().
        """
        data = self.ask_raw(prompt, extra_args=extra_args)
        return data.get("result", "").strip()


# ═══════════════════════════════════════════════════════════════════════════════
#  MÓDULO PERMISOS - Gestión dinámica de permisos por voz
# ═══════════════════════════════════════════════════════════════════════════════

class PermissionManager:
    """Detecta denegaciones de permisos de Claude Code y gestiona su concesión por voz."""

    GRANTABLE_TOOLS = [
        "Read", "Edit", "Write", "Glob", "Grep",
        "Bash(git:*)", "Bash(pip:*)", "Bash(npm:*)", "Bash(mkdir:*)",
        "Bash(cp:*)", "Bash(mv:*)", "Bash(ls:*)", "Bash(which:*)",
        "Bash(node:*)", "Bash(brew:*)", "Bash(python3:*)", "Bash(curl:*)",
    ]

    AFFIRMATIVE_RESPONSES = {
        "es": [
            "sí", "si", "claro", "dale", "ok", "hazlo", "adelante",
            "por supuesto", "va", "bueno", "perfecto", "de acuerdo",
            "seguro", "afirmativo",
        ],
        "en": [
            "yes", "yeah", "sure", "ok", "go ahead", "do it",
            "of course", "absolutely", "yep", "yup",
        ],
    }

    NEGATIVE_RESPONSES = {
        "es": ["no", "nop", "negativo", "cancelar", "cancela", "mejor no"],
        "en": ["no", "nope", "negative", "cancel", "stop", "never mind"],
    }

    MESSAGES = {
        "es": {
            "ask": (
                "Necesito permisos adicionales para completar esta tarea. "
                "Se habilitarán permisos de lectura, escritura y edición de archivos, "
                "y ejecución de comandos comunes. ¿Me los concedes?"
            ),
            "granted": "Permisos concedidos. Reintentando.",
            "denied": "Entendido, no se otorgaron permisos.",
            "error": "No pude entender tu respuesta. Por seguridad, no se otorgaron permisos.",
        },
        "en": {
            "ask": (
                "I need additional permissions to complete this task. "
                "This will enable file read, write, and edit permissions, "
                "and execution of common commands. Do you grant them?"
            ),
            "granted": "Permissions granted. Retrying.",
            "denied": "Understood, permissions were not granted.",
            "error": "I couldn't understand your response. For safety, permissions were not granted.",
        },
    }

    def __init__(self, config: Config):
        self.config = config

    def has_permission_denials(self, data: dict) -> bool:
        """Checa si la respuesta de Claude Code contiene denegaciones de permisos."""
        denials = data.get("permission_denials")
        return isinstance(denials, list) and len(denials) > 0

    def get_denied_tools(self, data: dict) -> list[str]:
        """Extrae nombres de herramientas denegadas de la respuesta."""
        denials = data.get("permission_denials", [])
        return [d.get("tool_name", "") for d in denials if d.get("tool_name")]

    def is_affirmative(self, text: str) -> bool:
        """Evalúa si la respuesta de voz es afirmativa."""
        text_lower = text.lower().strip()
        phrases = (
            self.AFFIRMATIVE_RESPONSES.get(self.config.LANG, [])
            + self.AFFIRMATIVE_RESPONSES.get("en", [])
        )
        return any(phrase in text_lower for phrase in phrases)

    def is_negative(self, text: str) -> bool:
        """Evalúa si la respuesta de voz es negativa."""
        text_lower = text.lower().strip()
        phrases = (
            self.NEGATIVE_RESPONSES.get(self.config.LANG, [])
            + self.NEGATIVE_RESPONSES.get("en", [])
        )
        return any(phrase in text_lower for phrase in phrases)

    def update_settings_file(self):
        """Persiste los permisos en .claude/settings.local.json."""
        settings_path = Path.home() / ".claude" / "settings.local.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        settings = {}
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text())
            except (json.JSONDecodeError, ValueError):
                settings = {}

        existing = set(settings.get("permissions", {}).get("allow", []))
        existing.update(self.GRANTABLE_TOOLS)
        settings.setdefault("permissions", {})["allow"] = sorted(existing)

        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        print_status("✅ Permisos guardados en ~/.claude/settings.local.json", Colors.GREEN)

    @property
    def ask_prompt(self) -> str:
        return self.MESSAGES.get(self.config.LANG, self.MESSAGES["en"])["ask"]

    @property
    def granted_msg(self) -> str:
        return self.MESSAGES.get(self.config.LANG, self.MESSAGES["en"])["granted"]

    @property
    def denied_msg(self) -> str:
        return self.MESSAGES.get(self.config.LANG, self.MESSAGES["en"])["denied"]

    @property
    def error_msg(self) -> str:
        return self.MESSAGES.get(self.config.LANG, self.MESSAGES["en"])["error"]


# ═══════════════════════════════════════════════════════════════════════════════
#  JARVIS - Orquestador principal
# ═══════════════════════════════════════════════════════════════════════════════

class Jarvis:
    """
    Orquestador principal que conecta:
    🎤 STT (Whisper) → 🧠 LLM (Claude Code) → 🔊 TTS (Piper)
    """

    def __init__(self, config: Config, tts_engine: str = "piper"):
        self.config = config
        self.running = False

        # Inicializar módulos
        print_status("⚙️  Inicializando sistemas...\n")
        self.stt = SpeechToText(config)
        self.tts = TextToSpeech(config, engine=tts_engine)
        self.claude = ClaudeCode(config)
        self.permissions = PermissionManager(config)

        # Manejar Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Maneja shutdown graceful. Doble Ctrl+C fuerza salida inmediata."""
        # Segundo Ctrl+C → forzar salida inmediata
        signal.signal(signal.SIGINT, lambda s, f: os._exit(1))
        print(f"\n\n{Colors.YELLOW}  ⚡ Señal de apagado recibida (Ctrl+C de nuevo para forzar)...{Colors.RESET}")
        self.running = False
        self.stt.cleanup()
        try:
            farewells = self.config.FAREWELLS.get(self.config.LANG, ["Shutting down."])
            self.tts.speak(random.choice(farewells))
        except Exception:
            pass
        os._exit(0)

    @staticmethod
    def _normalize(text: str) -> str:
        """Remueve acentos y normaliza texto para comparación."""
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

    def _is_exit_command(self, text: str) -> bool:
        """Verifica si el texto es un comando de salida (ambos idiomas, sin acentos)."""
        text_norm = self._normalize(text)
        # Checar frases de AMBOS idiomas para máxima robustez
        all_phrases = (
            self.config.EXIT_PHRASES.get("es", [])
            + self.config.EXIT_PHRASES.get("en", [])
        )
        return any(self._normalize(phrase) in text_norm for phrase in all_phrases)

    def _has_wake_word(self, text: str) -> bool:
        """Verifica si el texto contiene la wake word."""
        if not self.config.WAKE_WORD:
            return True
        return self.config.WAKE_WORD.lower() in text.lower()

    def _handle_permission_request(self, original_prompt: str, claude_data: dict) -> str | None:
        """
        Maneja una denegación de permisos: pregunta al usuario por voz,
        y si acepta, persiste permisos y reintenta la operación.
        Retorna la nueva respuesta o None si se denegaron.
        """
        denied = self.permissions.get_denied_tools(claude_data)
        print_status(f"🔒 Permisos denegados para: {', '.join(denied)}", Colors.YELLOW)

        # Preguntar al usuario por voz
        self.tts.speak(self.permissions.ask_prompt)
        print_jarvis(self.permissions.ask_prompt)

        # Escuchar respuesta
        user_response = self.stt.listen()

        if not user_response:
            # Sin respuesta → denegar por seguridad
            self.tts.speak(self.permissions.error_msg)
            print_status("⚠️  Sin respuesta, permisos no otorgados.", Colors.YELLOW)
            return None

        print_user(user_response)

        # Checar si es comando de salida (ej: "apagar")
        if self._is_exit_command(user_response):
            self.running = False
            self.tts.speak(self.permissions.denied_msg)
            return None

        # Checar negativa primero (seguridad: "no, por supuesto que no")
        if self.permissions.is_negative(user_response):
            self.tts.speak(self.permissions.denied_msg)
            print_status("🚫 Permisos denegados por el usuario.", Colors.YELLOW)
            return None

        if self.permissions.is_affirmative(user_response):
            self.tts.speak(self.permissions.granted_msg)
            print_status("✅ Permisos concedidos por el usuario.", Colors.GREEN)

            # Persistir permisos en settings.local.json
            self.permissions.update_settings_file()

            # Reintentar con --allowedTools para efecto inmediato
            allowed_args = ["--allowedTools"] + self.permissions.GRANTABLE_TOOLS
            print_status("⏳ Reintentando con permisos...", Colors.BLUE)
            retry_data = self.claude.ask_raw(original_prompt, extra_args=allowed_args)
            return retry_data.get("result", "").strip()

        # Respuesta ambigua → denegar por seguridad
        self.tts.speak(self.permissions.error_msg)
        print_status("⚠️  Respuesta ambigua, permisos no otorgados.", Colors.YELLOW)
        return None

    def run(self):
        """Loop principal de JARVIS."""
        print_banner()

        # Mostrar directorio de trabajo actual
        cwd = os.getcwd()
        print_status(f"📂 Directorio activo: {cwd}", Colors.BLUE)
        print()

        # Saludo inicial
        greetings = self.config.GREETINGS.get(self.config.LANG, ["Systems online."])
        greeting = random.choice(greetings)
        print_jarvis(greeting)
        self.tts.speak(greeting)

        self.running = True
        print(f"\n{Colors.DIM}  ─────────────────────────────────────────")
        print(f"  Presiona Ctrl+C para salir")
        print(f"  Di 'apagar' o 'adiós' para apagar")
        print(f"  ─────────────────────────────────────────{Colors.RESET}\n")

        while self.running:
            try:
                # 1. Escuchar al usuario
                user_text = self.stt.listen()

                if not user_text:
                    continue

                # 2. Verificar wake word (si aplica)
                if not self._has_wake_word(user_text):
                    continue

                # 3. Mostrar lo que escuchó
                print_user(user_text)

                # 4. Verificar comando de salida
                if self._is_exit_command(user_text):
                    farewells = self.config.FAREWELLS.get(self.config.LANG, ["Goodbye."])
                    farewell = random.choice(farewells)
                    print_jarvis(farewell)
                    self.tts.speak(farewell)
                    break

                # 5. Feedback de procesamiento
                processing_msgs = self.config.PROCESSING_MSGS.get(self.config.LANG, ["Processing..."])
                print_status(f"⏳ {random.choice(processing_msgs)}")

                # 6. Enviar a Claude Code
                claude_data = self.claude.ask_raw(user_text)
                response = claude_data.get("result", "").strip()

                # 6.1 Manejar denegaciones de permisos
                if self.permissions.has_permission_denials(claude_data):
                    retry_response = self._handle_permission_request(user_text, claude_data)
                    if retry_response is not None:
                        response = retry_response

                # 6.2 Si el usuario pidió apagar durante el flujo de permisos
                if not self.running:
                    break

                # 7. Mostrar respuesta completa en terminal
                print_jarvis(response)

                # 8. Limpiar respuesta para voz y hablar
                speech_text = clean_for_speech(response)
                self.tts.speak(speech_text)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print_status(f"❌ Error: {e}", Colors.RED)
                self.tts.speak("Hubo un error. Intenta de nuevo.")

        # Cleanup
        self.stt.cleanup()
        print(f"\n{Colors.DIM}  👋 JARVIS desactivado.{Colors.RESET}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI - Argumentos de línea de comandos
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args():
    """Parse argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="🤖 JARVIS - Voice-powered Claude Code interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Ejemplos:
          python3 jarvis.py                        # Modo estándar (español)
          python3 jarvis.py --lang en              # Modo inglés
          python3 jarvis.py --tts macos            # Usar voz nativa de macOS
          python3 jarvis.py --wake-word claude     # Solo activar con "Claude"
          python3 jarvis.py --whisper-model small  # Mejor precisión STT

        Voces Piper (se seleccionan automáticamente por idioma):
          es → es_MX-claude-high    (español mexicano, alta calidad)
          en → en_US-lessac-medium  (inglés americano)
        """),
    )

    parser.add_argument(
        "--lang", "-l",
        default="es",
        choices=["es", "en", "auto"],
        help="Idioma principal (default: es)",
    )
    parser.add_argument(
        "--tts",
        default="auto",
        choices=["piper", "macos", "auto"],
        help="Motor TTS (default: auto)",
    )
    parser.add_argument(
        "--whisper-model", "-w",
        default=Config.WHISPER_MODEL,
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help=f"Modelo Whisper para STT (default: {Config.WHISPER_MODEL})",
    )
    parser.add_argument(
        "--wake-word",
        default=None,
        help="Palabra de activación (ej: 'claude', 'jarvis')",
    )
    parser.add_argument(
        "--silence-threshold",
        type=int,
        default=500,
        help="Umbral de silencio para detección de voz (default: 500)",
    )

    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    # Verificar dependencias
    detected_tts = check_dependencies()

    # Configurar
    config = Config()
    config.LANG = args.lang
    config.WHISPER_MODEL = args.whisper_model
    config.WAKE_WORD = args.wake_word
    config.SILENCE_THRESHOLD = args.silence_threshold

    # Determinar motor TTS
    tts_engine = args.tts
    if tts_engine == "auto":
        tts_engine = detected_tts

    # Lanzar JARVIS
    jarvis = Jarvis(config, tts_engine=tts_engine)
    jarvis.run()


if __name__ == "__main__":
    main()
