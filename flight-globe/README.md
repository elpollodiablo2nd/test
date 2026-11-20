# FLIGHT GLOBE

A single-file, pixel-art web app that wraps [FlightConnections.com](https://www.flightconnections.com/) on a **rotatable, zoomable globe**. Click any airport to instantly see its **direct** and **indirect (1-stop)** connections — drawn as great-circle arcs on the globe and listed in the side panel — with one-click deep links into the live FlightConnections.com pages.

![style](https://img.shields.io/badge/style-Mistral%20pixel%20UI-FF8205) ![stack](https://img.shields.io/badge/stack-vanilla%20HTML%2FJS%2Fcanvas-FFD800)

## Run it

It is plain HTML — no build step.

### Option A: GitHub Pages (recommended)

1. Go to the repo on GitHub → **Settings → Pages**.
2. Under **Source**, choose **Deploy from a branch**.
3. Select branch **`vibe/flight-globe-2c20e5`** and folder **`/ (root)`** → **Save**.
4. After a minute, open:
   `https://elpollodiablo2nd.github.io/test/flight-globe/`

(If you later move these files into their own repo, e.g. `flight-globe`, the URL becomes `https://elpollodiablo2nd.github.io/flight-globe/` — just enable Pages on `main` / root there.)

### Option B: anywhere static

Upload `index.html` to any static host (Netlify Drop, Cloudflare Pages, S3, …) or just open the file locally in a browser.

## Controls

| Action | How |
|---|---|
| Rotate the globe | drag with mouse / finger, or arrow keys |
| Zoom | mouse wheel, or `+` / `-` |
| Select an airport | click it on the globe, or use the search box (IATA / city / name) |
| Direct connections | amber arcs + yellow dots, listed as chips under **DIRECT CONNECTIONS** |
| Indirect (1 stop) | red diamonds (+ red arcs when zoomed in ≥ 2.5×), listed under **INDIRECT — 1 STOP** |
| Fly the globe to a destination | click its chip |
| Toggle layers | **DIRECT**, **1-STOP**, **ALL ROUTES** buttons |
| Auto-rotate | **SPIN** button |
| Deep link to FlightConnections.com | orange button — opens `flights-from-<city>-<IATA>` for the selected airport (route URLs `flights-from-<A>-to-<B>` are in the direct-chip tooltips) |
| Clear selection | `Esc` or click empty space |

## How it works

- The globe is a hand-rolled **orthographic 3D projection** on a `<canvas>` — drag rotates yaw/pitch, wheel scales the radius. Airports are projected each frame; only the front hemisphere is drawn and clickable.
- Routes are rendered as **slerp great-circle arcs** with an altitude bump proportional to distance, animated with marching dashes.
- Connections are computed at runtime with a **BFS of depth 2** over the route graph (direct = depth 1, indirect = depth 2).
- Data is loaded live in the browser from the public [OpenFlights](https://openflights.org/data.html) dataset (`airports.dat` + `routes.dat`) via jsDelivr, falling back to raw.githubusercontent.com. The top **1,200 airports by route count** (~15k routes) are rendered. If both are unreachable, a built-in offline sample (~80 hubs) keeps the globe usable and a banner says so.
- Styled with the **Mistral pixel UI** (Press Start 2P / VT323, rainbow gradient, chunky borders, CRT scanlines).

## Files

- `index.html` — the whole app (markup + CSS + JS, no dependencies besides Google Fonts)
- `.nojekyll` — disables Jekyll processing on GitHub Pages

## Credits

- Route/airport data: [OpenFlights](https://openflights.org/data.html) (public domain)
- Live schedules, airlines and the reference map: [FlightConnections.com](https://www.flightconnections.com/)
