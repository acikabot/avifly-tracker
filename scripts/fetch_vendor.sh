#!/usr/bin/env bash
# Downloads the pinned front-end libraries into static/vendor/.
# The app serves these itself (no CDN at runtime). Re-run after changing a version.
set -euo pipefail

cd "$(dirname "$0")/.."
CDN="https://cdn.jsdelivr.net/npm"
DEST="static/vendor"

BOOTSTRAP=5.3.8
BOOTSTRAP_ICONS=1.13.1
HTMX=2.0.7
TOM_SELECT=2.4.3
ECHARTS=5.6.0
LEAFLET=1.9.4

fetch() {  # fetch <url> <destination>
  mkdir -p "$(dirname "$2")"
  curl -fsSL "$1" -o "$2"
  echo "  $2"
}

echo "Fetching vendor libraries into $DEST"
rm -rf "$DEST"

fetch "$CDN/bootstrap@$BOOTSTRAP/dist/css/bootstrap.min.css" "$DEST/bootstrap/bootstrap.min.css"
fetch "$CDN/bootstrap@$BOOTSTRAP/dist/js/bootstrap.bundle.min.js" "$DEST/bootstrap/bootstrap.bundle.min.js"

fetch "$CDN/bootstrap-icons@$BOOTSTRAP_ICONS/font/bootstrap-icons.min.css" "$DEST/bootstrap-icons/bootstrap-icons.min.css"
fetch "$CDN/bootstrap-icons@$BOOTSTRAP_ICONS/font/fonts/bootstrap-icons.woff2" "$DEST/bootstrap-icons/fonts/bootstrap-icons.woff2"
fetch "$CDN/bootstrap-icons@$BOOTSTRAP_ICONS/font/fonts/bootstrap-icons.woff" "$DEST/bootstrap-icons/fonts/bootstrap-icons.woff"

fetch "$CDN/htmx.org@$HTMX/dist/htmx.min.js" "$DEST/htmx/htmx.min.js"

fetch "$CDN/tom-select@$TOM_SELECT/dist/js/tom-select.complete.min.js" "$DEST/tom-select/tom-select.complete.min.js"
fetch "$CDN/tom-select@$TOM_SELECT/dist/css/tom-select.bootstrap5.min.css" "$DEST/tom-select/tom-select.bootstrap5.min.css"

fetch "$CDN/echarts@$ECHARTS/dist/echarts.min.js" "$DEST/echarts/echarts.min.js"

fetch "$CDN/leaflet@$LEAFLET/dist/leaflet.js" "$DEST/leaflet/leaflet.js"
fetch "$CDN/leaflet@$LEAFLET/dist/leaflet.css" "$DEST/leaflet/leaflet.css"
for img in layers.png layers-2x.png marker-icon.png marker-icon-2x.png marker-shadow.png; do
  fetch "$CDN/leaflet@$LEAFLET/dist/images/$img" "$DEST/leaflet/images/$img"
done

# Source maps aren't shipped, so drop the references to them (they only help debugging).
grep -rl "sourceMappingURL" "$DEST" | xargs -r sed -i -E '/sourceMappingURL=/d'

cat > "$DEST/VERSIONS.txt" <<EOF
bootstrap        $BOOTSTRAP
bootstrap-icons  $BOOTSTRAP_ICONS
htmx             $HTMX
tom-select       $TOM_SELECT
echarts          $ECHARTS
leaflet          $LEAFLET
EOF
echo "Done."
