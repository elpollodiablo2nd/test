#!/usr/bin/env bash
# Apply the elspot launcher icon (pixel bolt on #150C24, centered) + launcher name "elspot"
# to the generated (gitignored) android/ project. Run after `npx cap add android` / `cap sync`.
set -euo pipefail
cd "$(dirname "$0")/.."
RES=android/app/src/main/res
mkdir -p "$RES/drawable" "$RES/mipmap-anydpi-v26" "$RES/values"
cp tools/launcher/ic_launcher_foreground.xml "$RES/drawable/"
cp tools/launcher/ic_launcher.xml "$RES/mipmap-anydpi-v26/ic_launcher.xml"
cp tools/launcher/ic_launcher_round.xml "$RES/mipmap-anydpi-v26/ic_launcher_round.xml"
# background color: edit Capacitor's own ic_launcher_background.xml (avoids duplicate resource)
sed -i 's|<color name="ic_launcher_background">[^<]*</color>|<color name="ic_launcher_background">#150C24</color>|' "$RES/values/ic_launcher_background.xml"
sed -i 's|<string name="app_name">[^<]*</string>|<string name="app_name">elspot</string>|' "$RES/values/strings.xml"
echo "launcher icon + app_name=elspot applied"
