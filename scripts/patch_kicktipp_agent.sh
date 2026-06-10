#!/usr/bin/env bash
# Deutsche Kicktipp-Instanz: kicktipp.de + /tippabgabe statt .com/predict
set -eu
ROOT="${1:-.kicktipp-agent}"
URL_FILE="$ROOT/src/url.ts"
if [ ! -f "$URL_FILE" ]; then
  echo "Nicht gefunden: $URL_FILE" >&2
  exit 1
fi
sed -i.bak 's|https://www.kicktipp.com|https://www.kicktipp.de|g' "$URL_FILE"
sed -i.bak 's|/predict|/tippabgabe|g' "$URL_FILE"
BROWSER_FILE="$ROOT/src/browser.ts"
if [ -f "$BROWSER_FILE" ]; then
  sed -i.bak 's|height: 900|height: 2400|g' "$BROWSER_FILE"
fi
echo "Gepatcht: $URL_FILE (-> kicktipp.de/tippabgabe)"
