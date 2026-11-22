# Math Aid — Android APK (WebView-wrapper)

Dette er et minimalt Android Studio-projekt, der pakker `../index.html` (sammen med manifest, service worker og ikoner) ind i en WebView, så Math Aid kører offline som en rigtig app. `localStorage` (dagens % og historik-graf) virker, fordi `domStorageEnabled` er slået til.

> Bemærk: Jeg kan ikke bygge/signere APK'en i et sandbox-miljø uden Android SDK — det gør du her med ét klik.

## Sådan bygger du APK'en

1. Installer **Android Studio** (nyeste stabile) og **JDK 17**.
2. Åbn denne mappe (`math-aid/android`) i Android Studio: **File → Open → vælg `android`-mappen**. Lad Gradle synkronisere (første gang downloader den Gradle wrapper + Android SDK-komponenter).
3. Tilslut en telefon med USB-debugging, eller vælg en emulator.
4. Klik **▶ Run** — så installeres appen direkte.
5. Eller byg en APK-fil: **Build → Build Bundle(s) / APK(s) → Build APK(s)**.
   - Debug-APK (ingen signering nødvendig, kan installeres direkte): `app/build/outputs/apk/debug/app-debug.apk`
   - Release-APK til Play Store: lav først en signing key (Build → Generate Signed Bundle / APK → vælg eller opret keystore), så får du `app/build/outputs/apk/release/app-release.apk`.

## Filer

- `app/src/main/assets/` — hele web-appen (index.html, manifest.webmanifest, sw.js, ikoner). Opdater ved at kopiere nye filer fra `../`.
- `app/src/main/java/ai/mistral/mathaid/MainActivity.kt` — WebView der loader `file:///android_asset/index.html`.
- `app/src/main/res/drawable/icon.png` — app-ikon (512px pixel M).

## Alternativ uden APK: installer som PWA
Når repoet kører på GitHub Pages (`https://elpollodiablo2nd.github.io/test/math-aid/`), kan appen installeres direkte fra Chrome på Android via **⋮ → "Tilføj til startskærm"** — så får du også app-ikon, fuldskærm og offline via service worker (`sw.js`).
