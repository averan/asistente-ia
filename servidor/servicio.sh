#!/usr/bin/env bash
# Deja el asistente como servicio del Mac (launchd): arranca solo al iniciar sesión, sigue funcionando
# aunque se cierre la terminal o la app, y se reinicia si falla o si el túnel de Cloudflare expira.
# Uso:  ./servidor/servicio.sh instalar | desinstalar | reiniciar | estado | log
set -uo pipefail
cd "$(dirname "$0")"
DIR=$(pwd)
LABEL=com.averan.asistente-ia
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/asistente-ia.log"
DOMINIO="gui/$(id -u)"

instalado() { launchctl print "$DOMINIO/$LABEL" >/dev/null 2>&1; }

instalar() {
  if lsof -iTCP:5204 -sTCP:LISTEN >/dev/null 2>&1 && ! instalado; then
    echo "El asistente ya está corriendo en una terminal: ciérralo (Ctrl+C) y vuelve a ejecutar esto."; exit 1
  fi
  mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$DIR/publicar.sh</string></array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF
  instalado && launchctl bootout "$DOMINIO/$LABEL" 2>/dev/null
  launchctl bootstrap "$DOMINIO" "$PLIST" && echo "Servicio instalado: el asistente arranca solo al iniciar sesión. Registro: $LOG"
}

desinstalar() {
  instalado && launchctl bootout "$DOMINIO/$LABEL"   # detiene el asistente: los sitios muestran «no disponible»
  rm -f "$PLIST"
  echo "Servicio desinstalado."
}

case "${1:-estado}" in
  instalar)    instalar ;;
  desinstalar) desinstalar ;;
  reiniciar)   instalado && launchctl kill SIGTERM "$DOMINIO/$LABEL" && echo "Reiniciando (abre un túnel nuevo en ~1 min)…" ;;
  log)         tail -n 40 -f "$LOG" ;;
  estado)
    if instalado; then
      launchctl print "$DOMINIO/$LABEL" | awk -F' = ' '/^\t(state|pid|runs|last exit code) = /{sub(/^\t/,"",$1); print "  " $1 ": " $2}'
      grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | tail -1 | sed 's/^/  túnel: /'
      true
    else
      echo "  El servicio no está instalado (./servidor/servicio.sh instalar)."
    fi ;;
  *) echo "Uso: $0 instalar | desinstalar | reiniciar | estado | log"; exit 1 ;;
esac
