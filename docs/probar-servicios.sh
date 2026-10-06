#!/usr/bin/env bash
# Prueba los servicios del servidor del asistente (:5204) con curl y muestra ✓ / ✗ por cada uno.
# No crea solicitudes reales: las pruebas de /api/solicitudes están armadas para que el servidor las rechace.
#
# Uso:
#   ./docs/probar-servicios.sh              # en el Mac, contra http://localhost:5204
#   ./docs/probar-servicios.sh --publico    # desde cualquier equipo, por el túnel publicado en backend.js
# Variables opcionales:  ORIGEN=https://otro-sitio-autorizado.com  BASE=https://…trycloudflare.com
set -uo pipefail

ORIGEN=${ORIGEN:-https://faenabot.stream}
WIDGET=https://asistente-ia.faenabot.stream
if [ "${1:-}" = "--publico" ]; then
  BASE=$(curl -s -m 10 "$WIDGET/backend.js?t=$(date +%s)" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)
  [ -n "$BASE" ] || { echo "El asistente no está publicado (backend.js sin dirección): ¿está corriendo el servicio?"; exit 1; }
fi
BASE=${BASE:-http://localhost:5204}
echo "Servidor: $BASE   Origen: $ORIGEN"
echo

OK=0; FALLAS=0
# prueba "nombre" código_esperado [argumentos de curl…]  → compara el código HTTP y muestra un extracto de la respuesta
prueba() {
  local nombre=$1 esperado=$2; shift 2
  local cuerpo codigo
  cuerpo=$(curl -s -m 120 -w '\n%{http_code}' "$@")
  codigo=${cuerpo##*$'\n'}; cuerpo=${cuerpo%$'\n'*}
  if [ "$codigo" = "$esperado" ]; then OK=$((OK + 1)); printf '✓ %-44s %s\n' "$nombre" "$codigo"
  else FALLAS=$((FALLAS + 1)); printf '✗ %-44s %s (se esperaba %s)\n' "$nombre" "$codigo" "$esperado"; fi
  printf '    %s\n' "$(printf '%s' "$cuerpo" | tr '\n' ' ' | cut -c1-150)"
}
JSON=(-H "Origin: $ORIGEN" -H 'Content-Type: application/json')

echo "Estado del modelo"
prueba "GET /health" 200 "$BASE/health"
prueba "GET /v1/models/status" 200 "$BASE/v1/models/status"

echo; echo "Configuración del sitio"
prueba "GET /api/config (sitio autorizado)" 200 -H "Origin: $ORIGEN" "$BASE/api/config"
prueba "GET /api/config (sitio no autorizado)" 403 -H "Origin: https://ejemplo.com" "$BASE/api/config"
prueba "OPTIONS (permiso CORS)" 204 -X OPTIONS -H "Origin: $ORIGEN" -H 'Access-Control-Request-Method: POST' "$BASE/v1/chat/completions"

echo; echo "Conversación"
MODELO=$(curl -s -m 15 "$BASE/v1/models/status" | python3 -c 'import json,sys; m=[x["id"] for x in json.load(sys.stdin)["models"] if x.get("loaded")]; print(m[0] if m else "")' 2>/dev/null)
[ -n "$MODELO" ] || MODELO=$(curl -s -m 15 "$BASE/health" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("default_model",""))' 2>/dev/null)
echo "  modelo en uso: ${MODELO:-(ninguno)}"
prueba "POST /v1/chat/completions" 200 "${JSON[@]}" "$BASE/v1/chat/completions" \
  -d "{\"model\":\"$MODELO\",\"stream\":false,\"max_tokens\":60,\"messages\":[{\"role\":\"user\",\"content\":\"Hola, ¿qué haces?\"}]}"
prueba "POST /v1/chat/completions (otro modelo)" 404 "${JSON[@]}" "$BASE/v1/chat/completions" \
  -d '{"model":"modelo-inexistente","messages":[{"role":"user","content":"Hola"}]}'

echo; echo "Solicitudes (solo validaciones: ninguna se guarda)"
prueba "POST /api/solicitudes (faltan datos)" 400 "${JSON[@]}" "$BASE/api/solicitudes" -d '{"correo":"no-es-correo"}'
prueba "POST /api/solicitudes (correo inválido)" 400 "${JSON[@]}" "$BASE/api/solicitudes" \
  -d '{"titulo":"Prueba","descripcion":"Prueba","nombre":"Prueba","necesidad":"Prueba","empresa":"Prueba","correo":"no-es-correo"}'
prueba "POST /api/solicitudes (archivo no admitido)" 400 "${JSON[@]}" "$BASE/api/solicitudes" \
  -d '{"necesidad":"Prueba","correo":"prueba@ejemplo.com","archivos":[{"nombre":"programa.exe","contenido_base64":"TVqQAAMAAAAEAAAA"}]}'

echo; echo "Rutas y métodos no admitidos"
prueba "GET /no-existe" 404 "$BASE/no-existe"
prueba "DELETE /api/config" 405 -X DELETE "$BASE/api/config"

echo
echo "Resultado: $OK correctas, $FALLAS con diferencias."
[ "$FALLAS" -eq 0 ]
