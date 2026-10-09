#!/usr/bin/env bash
# Conecta el asistente IA (todos los sitios que lo integran) con el modelo de este Mac.
#   1. Arranca server.py y el túnel de Cloudflare:
#      - fijo (TUNEL_CONFIG en .env): túnel con nombre, dirección que no cambia (TUNEL_URL, p. ej. api.faenabot.stream);
#      - si no, uno gratuito (trycloudflare), con una dirección nueva en cada arranque.
#   2. Sube a GitHub publico/backend.js con la dirección y la configuración visible de cada sitio (solo si cambió)
#      → Cloudflare se actualiza solo.
#   3. Vigila el servidor y el túnel cada minuto; si algo cae (o el túnel gratuito expira) termina con
#      error, para que el servicio del Mac (servicio.sh) lo vuelva a arrancar.
#   4. Al salir (Ctrl+C o al detener el servicio) los sitios muestran «no disponible»: con túnel gratuito se publica
#      la dirección vacía; con túnel fijo no hace falta (el widget no logra conectarse y muestra el aviso).
# El Mac debe estar encendido y oMLX en marcha (con el modelo cargado).
# Uso:  ./servidor/publicar.sh   (o como servicio del Mac:  ./servidor/servicio.sh instalar)
set -uo pipefail
cd "$(dirname "$0")"
REPO=$(git rev-parse --show-toplevel) || exit 1
BACKEND_JS=publico/backend.js

bold=$'\033[1m'; green=$'\033[32m'; yellow=$'\033[33m'; red=$'\033[31m'; reset=$'\033[0m'
fail() { echo "${red}✗ $*${reset}"; exit 1; }
warn() { echo "${yellow}! $*${reset}"; }

[ -f .env ] || fail "Falta servidor/.env. Créalo con:  cp servidor/.env.example servidor/.env  y pon tu OMLX_API_KEY."
envget() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
PORT=$(envget PORT); PORT=${PORT:-5204}
ADMIN_PORT=$(envget ADMIN_PORT); ADMIN_PORT=${ADMIN_PORT:-5205}
OMLX_URL=$(envget OMLX_URL); OMLX_URL=${OMLX_URL:-http://127.0.0.1:8000}
SITIO_URL=$(envget SITIO_URL); SITIO_URL=${SITIO_URL:-https://asistente-ia.faenabot.stream}
TUNEL_CONFIG=$(envget TUNEL_CONFIG); TUNEL_CONFIG=${TUNEL_CONFIG/#\~/$HOME}
TUNEL_URL=$(envget TUNEL_URL); TUNEL_URL=${TUNEL_URL:-https://api.faenabot.stream}
GESTION_REMOTA=""
[ -n "$(envget ACCESS_TEAM)" ] && [ -n "$(envget ACCESS_AUD)" ] && GESTION_REMOTA="https://$(envget GESTION_HOST | grep . || echo gestion.faenabot.stream)"
[ -z "$TUNEL_CONFIG" ] || [ -f "$TUNEL_CONFIG" ] || fail "No existe $TUNEL_CONFIG (TUNEL_CONFIG en .env)."

command -v cloudflared >/dev/null || fail "Falta cloudflared. Instálalo con:  brew install cloudflared"
curl -sf -m 5 "$OMLX_URL/health" >/dev/null || fail "oMLX no responde en $OMLX_URL. Arráncalo primero."
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  fail "El puerto $PORT ya está en uso (¿otro publicar.sh abierto?). Ciérralo y vuelve a intentarlo."
fi

# Escribe backend.js (dirección del túnel, '' = sin asistente, + configuración visible de los sitios) y lo sube.
publish_backend() {
  python3 server.py backend-js "$1" > "$REPO/$BACKEND_JS" || return 1
  git -C "$REPO" diff --quiet -- "$BACKEND_JS" && return 0
  git -C "$REPO" commit -q -m "$2" -- "$BACKEND_JS" || return 1
  git -C "$REPO" pull -q --rebase --autostash >/dev/null 2>&1 || true
  git -C "$REPO" push -q
}

LOG=$(mktemp -t cloudflared)
cleanup() {
  trap - EXIT INT TERM
  echo; echo "Deteniendo…"
  kill "${SERVER_PID:-}" "${TUNNEL_PID:-}" "${AWAKE_PID:-}" 2>/dev/null
  rm -f "$LOG"
  if [ -n "${PUBLISHED:-}" ] && [ -z "$TUNEL_CONFIG" ]; then
    publish_backend "" "Asistente: fuera de línea" \
      && echo "Los sitios ahora muestran «asistente no disponible» (Cloudflare tarda ~1 min en actualizarse)." \
      || warn "No se pudo actualizar GitHub: los sitios seguirán apuntando al túnel cerrado hasta el próximo publicar.sh."
  fi
  echo "El asistente ya no está conectado."
}
trap cleanup EXIT INT TERM

python3 server.py & SERVER_PID=$!
sleep 1
kill -0 "$SERVER_PID" 2>/dev/null || fail "No se pudo arrancar server.py."

caffeinate -i -w $$ & AWAKE_PID=$!   # evita que el Mac se duerma mientras está conectado

URL=""
if [ -n "$TUNEL_CONFIG" ]; then
  echo "Conectando el túnel fijo ($TUNEL_URL)…"
  cloudflared tunnel --config "$TUNEL_CONFIG" run >"$LOG" 2>&1 & TUNNEL_PID=$!
  for _ in $(seq 1 60); do
    curl -sf -m 5 -o /dev/null "$TUNEL_URL/health" && { URL=$TUNEL_URL; break; }
    kill -0 "$TUNNEL_PID" 2>/dev/null || break
    sleep 2
  done
  [ -n "$URL" ] || { tail -20 "$LOG"; fail "El túnel fijo no responde en $TUNEL_URL (ver mensajes de arriba)."; }
else
  echo "Abriendo túnel con Cloudflare…"
  cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$LOG" 2>&1 & TUNNEL_PID=$!
  for _ in $(seq 1 45); do
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1)
    [ -n "$URL" ] && break
    kill -0 "$TUNNEL_PID" 2>/dev/null || break
    sleep 1
  done
  [ -n "$URL" ] || { cat "$LOG"; fail "No se pudo abrir el túnel (ver mensajes de arriba)."; }
fi

echo "Túnel: $URL"
echo "Actualizando backend.js en GitHub (si cambió)…"
publish_backend "$URL" "Asistente: dirección del túnel" || fail "No se pudo subir backend.js a GitHub (revisa tu conexión o ejecuta git push a mano)."
PUBLISHED=1

echo "Esperando a que Cloudflare publique el cambio…"
LIVE=""
for _ in $(seq 1 60); do
  curl -sf -m 5 "$SITIO_URL/backend.js?t=$(date +%s)" | grep -qF "$URL" && { LIVE=1; break; }
  sleep 3
done

echo
if [ -n "$LIVE" ]; then
  echo "${bold}${green}✓ Asistente activo en todos los sitios${reset}  (widget en ${bold}$SITIO_URL${reset})"
else
  warn "Cloudflare aún no muestra la nueva dirección. Revisa el despliegue en dash.cloudflare.com; el asistente se activará cuando termine."
fi
echo "  Servidor local:  http://localhost:$PORT"
[ "$ADMIN_PORT" != "0" ] && echo "  Gestión:         http://localhost:$ADMIN_PORT${GESTION_REMOTA:+  y $GESTION_REMOTA (Cloudflare Access)}"
echo "  Mantén este Mac encendido y oMLX en marcha. Ctrl+C para desconectar el asistente."
echo
echo "Consultas recibidas:"

# Vigilancia: si el servidor o el túnel se caen, o el túnel deja de responder 3 veces seguidas
# (los túneles gratuitos expiran, p. ej. tras dormir el Mac o cambiar de red), sale con error y el servicio lo reinicia.
FALLAS=0
while true; do
  sleep 60 & wait $!
  kill -0 "$SERVER_PID" 2>/dev/null || { warn "$(date +%H:%M:%S)  El servidor se detuvo."; exit 1; }
  kill -0 "$TUNNEL_PID" 2>/dev/null || { warn "$(date +%H:%M:%S)  El túnel se cerró."; exit 1; }
  if curl -sf -m 15 -o /dev/null "$URL/health"; then
    FALLAS=0
  else
    FALLAS=$((FALLAS + 1))
    warn "$(date +%H:%M:%S)  El túnel no responde ($FALLAS/3)."
    [ "$FALLAS" -ge 3 ] && { warn "Se cerrará para volver a conectar el túnel."; exit 1; }
  fi
done
