#!/bin/bash
# Envia foto + timestamp de login pro grupo WhatsApp do Jarvis via Evolution API.
set -euo pipefail

IMG="$1"
TS="$2"
# Grupo vem do .env (carregado abaixo) — nada de ID pessoal no fonte.
GROUP=""

cd "$(dirname "$0")/.."
set -a
source docker/.env
set +a

GROUP="${WHATSAPP_GROUP_ID:-}"

if [ -z "${EVO_URL:-}" ] || [ -z "${EVO_KEY:-}" ] || [ -z "${EVO_INSTANCE:-}" ] || [ -z "$GROUP" ]; then
  echo "$(date): Evolution API ou WHATSAPP_GROUP_ID nao configurado" >> /tmp/notify_login.log
  exit 1
fi

if [ ! -f "$IMG" ]; then
  echo "$(date): imagem nao encontrada: $IMG" >> /tmp/notify_login.log
  exit 1
fi

B64_FILE=$(mktemp)
base64 -w0 "$IMG" > "$B64_FILE"
CAPTION="Login no Mac - $TS"

PAYLOAD_FILE=$(mktemp)
jq -n --arg number "$GROUP" --arg caption "$CAPTION" --rawfile media "$B64_FILE" \
  '{number: $number, mediatype: "image", mimetype: "image/jpeg", caption: $caption, media: $media, fileName: "login.jpg"}' > "$PAYLOAD_FILE"

HTTP_CODE=$(curl -s -o /tmp/notify_login_response.json -w "%{http_code}" -X POST "$EVO_URL/message/sendMedia/$EVO_INSTANCE" \
  -H "apikey: $EVO_KEY" \
  -H "Content-Type: application/json" \
  --data-binary "@$PAYLOAD_FILE")

echo "$(date): HTTP $HTTP_CODE - $(cat /tmp/notify_login_response.json)" >> /tmp/notify_login.log

rm -f "$IMG" "$B64_FILE" "$PAYLOAD_FILE"

if [ "$HTTP_CODE" -ge 300 ]; then
  exit 1
fi
