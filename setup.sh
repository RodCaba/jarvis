#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  JARVIS Setup Script for macOS
#  Instala todas las dependencias necesarias
# ═══════════════════════════════════════════════════════════════

set -e

CYAN='\033[96m'
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

echo ""
echo -e "${CYAN}${BOLD}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║        JARVIS - Setup para macOS          ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${RESET}"

# ── 1. Verificar macOS ──
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}❌ Este script es solo para macOS.${RESET}"
    exit 1
fi

# ── 2. Verificar Homebrew ──
echo -e "${CYAN}[1/6]${RESET} Verificando Homebrew..."
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}  → Instalando Homebrew...${RESET}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo -e "${GREEN}  ✅ Homebrew instalado${RESET}"
fi

# ── 3. Instalar dependencias del sistema ──
echo -e "${CYAN}[2/6]${RESET} Instalando dependencias del sistema..."

# PortAudio (necesario para PyAudio)
if ! brew list portaudio &> /dev/null 2>&1; then
    echo -e "${YELLOW}  → Instalando portaudio...${RESET}"
    brew install portaudio
else
    echo -e "${GREEN}  ✅ portaudio instalado${RESET}"
fi

# FFmpeg (útil para procesamiento de audio)
if ! brew list ffmpeg &> /dev/null 2>&1; then
    echo -e "${YELLOW}  → Instalando ffmpeg...${RESET}"
    brew install ffmpeg
else
    echo -e "${GREEN}  ✅ ffmpeg instalado${RESET}"
fi

# ── 4. Verificar Python ──
echo -e "${CYAN}[3/6]${RESET} Verificando Python..."
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
        PYTHON_CMD="python3"
        echo -e "${GREEN}  ✅ Python ${PYTHON_VERSION}${RESET}"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${YELLOW}  → Instalando Python 3.12...${RESET}"
    brew install python@3.12
    PYTHON_CMD="python3.12"
fi

# ── 5. Crear entorno virtual e instalar paquetes ──
echo -e "${CYAN}[4/6]${RESET} Creando entorno virtual e instalando paquetes Python..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo -e "${GREEN}  ✅ Entorno virtual creado en .venv/${RESET}"
else
    echo -e "${GREEN}  ✅ Entorno virtual ya existe${RESET}"
fi

# Activar venv
source "${VENV_DIR}/bin/activate"

echo -e "${DIM}  → Instalando paquetes Python...${RESET}"
pip install --upgrade pip -q

# Dependencias core
pip install -q \
    numpy \
    pyaudio \
    faster-whisper \
    piper-tts \
    sounddevice

echo -e "${GREEN}  ✅ Paquetes Python instalados${RESET}"

# ── 6. Descargar modelos Piper TTS ──
echo -e "${CYAN}[5/7]${RESET} Descargando modelos de voz Piper..."

MODELS_DIR="${SCRIPT_DIR}/models"
mkdir -p "$MODELS_DIR"

PIPER_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0"

declare -A PIPER_MODELS
PIPER_MODELS=(
    ["es_ES-davefx-medium"]="es/es_ES/davefx/medium"
    ["en_US-lessac-medium"]="en/en_US/lessac/medium"
)

for model_name in "${!PIPER_MODELS[@]}"; do
    model_subpath="${PIPER_MODELS[$model_name]}"
    onnx_file="$MODELS_DIR/${model_name}.onnx"
    json_file="$MODELS_DIR/${model_name}.onnx.json"

    if [ -f "$onnx_file" ] && [ -f "$json_file" ]; then
        echo -e "${GREEN}  ✅ ${model_name}${RESET}"
    else
        echo -e "${YELLOW}  → Descargando ${model_name} (~60MB)...${RESET}"
        curl -L -# -o "$onnx_file" "${PIPER_BASE_URL}/${model_subpath}/${model_name}.onnx"
        curl -sL -o "$json_file" "${PIPER_BASE_URL}/${model_subpath}/${model_name}.onnx.json"

        if [ -f "$onnx_file" ] && [ -s "$onnx_file" ]; then
            echo -e "${GREEN}  ✅ ${model_name}${RESET}"
        else
            echo -e "${RED}  ❌ Error descargando ${model_name}${RESET}"
            rm -f "$onnx_file" "$json_file"
        fi
    fi
done

# ── 7. Verificar Claude Code ──
echo -e "${CYAN}[6/7]${RESET} Verificando Claude Code CLI..."
if command -v claude &> /dev/null; then
    echo -e "${GREEN}  ✅ Claude Code CLI instalado${RESET}"
else
    echo -e "${YELLOW}  ⚠️  Claude Code CLI no encontrado${RESET}"
    echo -e "${DIM}  → Instálalo con: npm install -g @anthropic-ai/claude-code${RESET}"
    echo -e "${DIM}  → Luego autentícate con: claude auth${RESET}"
fi

# ── 8. Configurar ElevenLabs API Key ──
echo -e "${CYAN}[7/7]${RESET} Configurando ElevenLabs..."

if [ -n "$ELEVEN_API_KEY" ]; then
    echo -e "${GREEN}  ✅ ELEVEN_API_KEY configurada${RESET}"
else
    echo ""
    echo -e "${YELLOW}  ⚠️  ELEVEN_API_KEY no configurada${RESET}"
    echo -e "${DIM}"
    echo "  Para usar ElevenLabs (voces ultra-realistas):"
    echo ""
    echo "  1. Crea una cuenta en: https://elevenlabs.io"
    echo "     (el plan gratuito incluye ~10,000 caracteres/mes)"
    echo ""
    echo "  2. Ve a: Profile Settings → API Keys"
    echo ""
    echo "  3. Agrega a tu ~/.zshrc o ~/.bashrc:"
    echo "     export ELEVEN_API_KEY='tu-api-key-aquí'"
    echo ""
    echo "  Sin la API key, JARVIS usará la voz nativa de macOS."
    echo -e "${RESET}"
fi

# ── Resumen ──
echo ""
echo -e "${GREEN}${BOLD}  ══════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  ✅ Setup completado!${RESET}"
echo -e "${GREEN}${BOLD}  ══════════════════════════════════════════${RESET}"
echo ""
echo -e "${CYAN}  Para iniciar JARVIS:${RESET}"
echo ""
echo -e "  ${BOLD}cd ${SCRIPT_DIR}${RESET}"
echo -e "  ${BOLD}source .venv/bin/activate${RESET}"
echo -e "  ${BOLD}python3 jarvis.py${RESET}"
echo ""
echo -e "${DIM}  Opciones útiles:${RESET}"
echo -e "${DIM}    python3 jarvis.py --voice Daniel     # Voz británica estilo Jarvis${RESET}"
echo -e "${DIM}    python3 jarvis.py --lang en           # Cambiar a inglés${RESET}"
echo -e "${DIM}    python3 jarvis.py --tts macos         # Voz nativa (sin API key)${RESET}"
echo -e "${DIM}    python3 jarvis.py --whisper-model small # Mejor precisión STT${RESET}"
echo -e "${DIM}    python3 jarvis.py --help              # Ver todas las opciones${RESET}"
echo ""
