# Math Aid — Android APK (WebView-wrapper)

Dette er et minimalt Android Studio-projekt, der pakker `../index.html` (sammen med manifest, service worker og ikoner) ind i en WebView, så Math Aid kører offline som en rigtig app. `localStorage` (dagens % og historik-graf) virker, fordi `domStorageEnabled` er slået til.

> Bemærk: Jeg kan ikke bygge/signere APK'en i et sandbox-miljø uden Android SDK — det gør du her med ét klik.

## Sådan bygger du APK'en

1. Installer **Android Studio** (nyeste stabile) og **JDK 17**.
2. Åbn denne mappe (`math-aid/android`) i Android Studio: **File → Open → vælg `android`-mappen**. Lad Gradle synkronisere (første gang downloader den Gradle wrapper + Android SDK-komponenter).
3. Tilslut en telefon med USB-debugging, eller vælg en emulator.
4. Klik **▶ Run** — så installeres appen direkte.
5. Eller byg en APK-fil: **Build → Build Bundle(s) / APK(s) → Build APK(s)**.
   - Debug-APK (auto-signeret med debug-nøgle, kan installeres direkte på egen telefon): `app/build/outputs/apk/debug/app-debug.apk`
   - **Release-APK** (signeret, klar til deling/Play): `app/build/outputs/apk/release/app-release.apk`. Lokalt: sæt miljøvariablerne `KEYSTORE_PATH`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD` (eller læg en `keystore.jks` i `app/`), så kører `gradle assembleRelease`.

## Debug vs. release
- **Debug**: signeres automatisk med en engangsnøgle — fin til at teste på din egen telefon (`adb install app-debug.apk`), men kan ikke opdateres over en tidligere installeret version.
- **Release**: signeret med din egen nøgle. Til Play Store skal du bruge **samme nøgle ved hver opdatering**, så gem keystore et sikkert sted.

## Automatisk release ved tag (GitHub Releases med APK)

Workflowet `.github/workflows/release.yml` kører ved hvert tag på formen `v*`:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Så bygger CI en signeret `app-release.apk` og opretter automatisk en **GitHub Release** med APK'en vedhæftet (Releases-fanen). Brug dine egne secrets (se nedenfor) for at alle releases signeres med samme nøgle — ellers genereres en ny nøgle pr. tag.

## Automatisk build i CI (ingen lokal toolchain nødvendig)
Workflowet `.github/workflows/build-apk.yml` bygger både `app-debug.apk` og signeret `app-release.apk` ved hvert push til `math-aid/**` (eller via **Run workflow** på fanen Actions). Download dem under **Actions → seneste run → Artifacts**.

For at CI skal bruge din egen nøgle til release, opret disse repo-secrets (Settings → Secrets and variables → Actions):
- `APP_KEYSTORE_BASE64` — din `.jks`/`.keystore` base64-encoded (`base64 -i keystore.jks`)
- `APP_KEYSTORE_PASSWORD`, `APP_KEY_ALIAS`, `APP_KEY_PASSWORD`

Uden secrets genererer CI en midlertidig nøgle — så er release-APK'en stadig signeret og installerbar, men kun én gang pr. build.

## Filer

- `app/src/main/assets/` — hele web-appen (index.html, manifest.webmanifest, sw.js, ikoner). Opdater ved at kopiere nye filer fra `../`.
- `app/src/main/java/ai/mistral/mathaid/MainActivity.kt` — WebView der loader `file:///android_asset/index.html`.
- `app/src/main/res/drawable/icon.png` — app-ikon (512px pixel M).

## Alternativ uden APK: installer som PWA
Når repoet kører på GitHub Pages (`https://elpollodiablo2nd.github.io/test/math-aid/`), kan appen installeres direkte fra Chrome på Android via **⋮ → "Tilføj til startskærm"** — så får du også app-ikon, fuldskærm og offline via service worker (`sw.js`).
