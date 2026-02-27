#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  JARVIS — Instalador a nivel sistema para macOS
#
#  Instala JARVIS como comando global para que puedas usarlo
#  desde cualquier directorio de proyecto.
#
#  Uso:
#    chmod +x install.sh
#    ./install.sh
#
#  Después simplemente:
#    cd ~/mi-proyecto
#    jarvis                  # ← listo, opera sobre mi-proyecto
# ═══════════════════════════════════════════════════════════════

set -e

CYAN='\033[96m'
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ── Configuración de rutas ──
INSTALL_DIR="$HOME/.jarvis"
VENV_DIR="$INSTALL_DIR/.venv"
BIN_LINK="/usr/local/bin/jarvis"

echo ""
echo -e "${CYAN}${BOLD}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║     JARVIS — Instalación a nivel sistema  ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${RESET}"

# ── 1. Verificar macOS ──
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}❌ Este script es solo para macOS.${RESET}"
    exit 1
fi

# ── 2. Verificar/Instalar Homebrew ──
echo -e "${CYAN}[1/7]${RESET} Verificando Homebrew..."
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}  → Instalando Homebrew...${RESET}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo -e "${GREEN}  ✅ Homebrew${RESET}"
fi

# ── 3. Dependencias del sistema ──
echo -e "${CYAN}[2/7]${RESET} Instalando dependencias del sistema..."

for pkg in portaudio ffmpeg; do
    if ! brew list "$pkg" &> /dev/null 2>&1; then
        echo -e "${YELLOW}  → Instalando ${pkg}...${RESET}"
        brew install "$pkg"
    else
        echo -e "${GREEN}  ✅ ${pkg}${RESET}"
    fi
done

# ── 4. Verificar Python ──
echo -e "${CYAN}[3/7]${RESET} Verificando Python..."
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &> /dev/null; then
        PY_VER=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            echo -e "${GREEN}  ✅ Python ${PY_VER} (${cmd})${RESET}"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${YELLOW}  → Instalando Python 3.12...${RESET}"
    brew install python@3.12
    PYTHON_CMD="python3.12"
fi

# ── 5. Crear directorio de instalación ──
echo -e "${CYAN}[4/7]${RESET} Instalando en ${INSTALL_DIR}..."

mkdir -p "$INSTALL_DIR"

# Copiar jarvis.py al directorio de instalación
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/jarvis.py" "$INSTALL_DIR/jarvis.py"
echo -e "${GREEN}  ✅ jarvis.py copiado${RESET}"

# ── 6. Crear entorno virtual e instalar paquetes ──
echo -e "${CYAN}[5/7]${RESET} Configurando entorno virtual..."

if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_CMD -m venv "$VENV_DIR"
fi

source "${VENV_DIR}/bin/activate"

echo -e "${DIM}  → Instalando paquetes Python (esto puede tardar un poco)...${RESET}"
pip install --upgrade pip -q 2>/dev/null

pip install -q \
    numpy \
    pyaudio \
    faster-whisper \
    elevenlabs 2>/dev/null

echo -e "${GREEN}  ✅ Paquetes Python instalados${RESET}"
deactivate

# ── 7. Crear comando global ──
echo -e "${CYAN}[6/7]${RESET} Creando comando global 'jarvis'..."

# Crear el launcher script
LAUNCHER="$INSTALL_DIR/jarvis-launcher.sh"
cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/bin/bash
# ═══════════════════════════════════════════════
#  JARVIS Launcher
#  Activa el venv y ejecuta jarvis.py
#  desde el directorio de trabajo actual (cwd)
# ═══════════════════════════════════════════════

JARVIS_HOME="$HOME/.jarvis"
VENV_DIR="$JARVIS_HOME/.venv"

# Activar entorno virtual silenciosamente
source "${VENV_DIR}/bin/activate" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "❌ Error: Entorno virtual no encontrado en ${VENV_DIR}"
    echo "   Reinstala con: cd ~/.jarvis && ./install.sh"
    exit 1
fi

# Ejecutar JARVIS en el directorio actual del usuario
# Esto es clave: Claude Code operará sobre ESTE directorio
exec python3 "${JARVIS_HOME}/jarvis.py" "$@"
LAUNCHER_EOF

chmod +x "$LAUNCHER"

# Crear symlink en /usr/local/bin (disponible en PATH)
if [ -L "$BIN_LINK" ] || [ -f "$BIN_LINK" ]; then
    echo -e "${DIM}  → Actualizando symlink existente...${RESET}"
    sudo rm -f "$BIN_LINK"
fi

# Intentar sin sudo primero, luego con sudo
if ln -sf "$LAUNCHER" "$BIN_LINK" 2>/dev/null; then
    echo -e "${GREEN}  ✅ Comando 'jarvis' disponible globalmente${RESET}"
else
    echo -e "${YELLOW}  → Necesita permisos de administrador...${RESET}"
    sudo ln -sf "$LAUNCHER" "$BIN_LINK"
    echo -e "${GREEN}  ✅ Comando 'jarvis' disponible globalmente${RESET}"
fi

# ── 8. Verificar Claude Code ──
echo -e "${CYAN}[7/7]${RESET} Verificando Claude Code CLI..."
if command -v claude &> /dev/null; then
    echo -e "${GREEN}  ✅ Claude Code CLI listo${RESET}"
else
    echo -e "${YELLOW}  ⚠️  Claude Code CLI no encontrado${RESET}"
    echo -e "${DIM}     Instala: npm install -g @anthropic-ai/claude-code${RESET}"
    echo -e "${DIM}     Luego:   claude auth${RESET}"
fi

# ── Configuración de ElevenLabs ──
if [ -z "$ELEVEN_API_KEY" ]; then
    echo ""
    echo -e "${YELLOW}  ⚠️  ELEVEN_API_KEY no configurada${RESET}"
    echo -e "${DIM}"
    echo "  Para voces ultra-realistas (recomendado):"
    echo "  1. Crea cuenta gratis en: https://elevenlabs.io"
    echo "  2. Ve a Profile Settings → API Keys"
    echo "  3. Agrega a tu shell:"
    echo ""
    echo "     echo 'export ELEVEN_API_KEY=\"tu-key\"' >> ~/.zshrc"
    echo "     source ~/.zshrc"
    echo ""
    echo "  Sin la key, JARVIS usa la voz nativa de macOS."
    echo -e "${RESET}"
fi

# ── Resumen final ──
echo ""
echo -e "${GREEN}${BOLD}  ═══════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  ✅ JARVIS instalado a nivel sistema!${RESET}"
echo -e "${GREEN}${BOLD}  ═══════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  Ahora puedes usar ${BOLD}jarvis${RESET} desde cualquier directorio:"
echo ""
echo -e "  ${CYAN}  cd ~/mi-proyecto${RESET}"
echo -e "  ${CYAN}  jarvis${RESET}                        ${DIM}# Claude opera sobre mi-proyecto${RESET}"
echo ""
echo -e "  ${CYAN}  cd ~/otro-repo${RESET}"
echo -e "  ${CYAN}  jarvis --voice Daniel${RESET}         ${DIM}# Voz británica estilo Jarvis${RESET}"
echo ""
echo -e "  ${CYAN}  cd ~/api-backend${RESET}"
echo -e "  ${CYAN}  jarvis --lang en${RESET}              ${DIM}# En inglés${RESET}"
echo ""
echo -e "${DIM}  Instalado en:  ~/.jarvis/${RESET}"
echo -e "${DIM}  Comando en:    /usr/local/bin/jarvis${RESET}"
echo -e "${DIM}  Desinstalar:   jarvis-uninstall${RESET}"
echo ""

# ── Crear script de desinstalación ──
cat > "$INSTALL_DIR/uninstall.sh" << 'UNINSTALL_EOF'
#!/bin/bash
echo "🗑️  Desinstalando JARVIS..."
sudo rm -f /usr/local/bin/jarvis
sudo rm -f /usr/local/bin/jarvis-uninstall
rm -rf "$HOME/.jarvis"
echo "✅ JARVIS desinstalado."
UNINSTALL_EOF
chmod +x "$INSTALL_DIR/uninstall.sh"

# Symlink para desinstalar
UNINSTALL_LINK="/usr/local/bin/jarvis-uninstall"
if ln -sf "$INSTALL_DIR/uninstall.sh" "$UNINSTALL_LINK" 2>/dev/null; then
    :
else
    sudo ln -sf "$INSTALL_DIR/uninstall.sh" "$UNINSTALL_LINK" 2>/dev/null
fi
