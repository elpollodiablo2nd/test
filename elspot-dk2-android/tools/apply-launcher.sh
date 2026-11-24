#!/usr/bin/env bash
# Apply the elspot launcher icon (pixel bolt on #150C24, centered) + launcher name "elspot"
# to the generated (gitignored) android/ project. Run after `npx cap add android` / `cap sync`.
set -euo pipefail
cd "$(dirname "$0")/.."
RES=android/app/src/main/res
# IMPORTANT: Capacitor ships its default robot vector in drawable-v24/, which shadows
# drawable/ on API 24+ — write the bolt to BOTH so the adaptive icon shows the bolt.
mkdir -p "$RES/drawable" "$RES/drawable-v24" "$RES/mipmap-anydpi-v26"
cp tools/launcher/ic_launcher_foreground.xml "$RES/drawable/ic_launcher_foreground.xml"
cp tools/launcher/ic_launcher_foreground.xml "$RES/drawable-v24/ic_launcher_foreground.xml"
cp tools/launcher/ic_launcher.xml "$RES/mipmap-anydpi-v26/ic_launcher.xml"
cp tools/launcher/ic_launcher_round.xml "$RES/mipmap-anydpi-v26/ic_launcher_round.xml"
# legacy (API < 26) launchers use the PNG mipmaps — replace the default robot with the bolt
for d in mdpi hdpi xhdpi xxhdpi xxxhdpi; do
  mkdir -p "$RES/mipmap-$d"
  cp "tools/launcher/mipmap-$d/ic_launcher.png" "$RES/mipmap-$d/ic_launcher.png"
  cp "tools/launcher/mipmap-$d/ic_launcher_round.png" "$RES/mipmap-$d/ic_launcher_round.png"
done
# background color: edit Capacitor's own file (avoids duplicate resource)
sed -i 's|<color name="ic_launcher_background">[^<]*</color>|<color name="ic_launcher_background">#150C24</color>|' "$RES/values/ic_launcher_background.xml"
sed -i 's|<string name="app_name">[^<]*</string>|<string name="app_name">elspot</string>|' "$RES/values/strings.xml"
echo "launcher icon (adaptive + legacy PNGs) + app_name=elspot applied"
