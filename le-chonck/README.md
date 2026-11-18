# Le Chonck — une aventure parisienne

A lofi pixel-art platform runner that runs entirely in the browser. No build step,
no external assets: art is drawn on a 480x270 canvas (upscaled with
`image-rendering: pixelated`) and the chill soundtrack is synthesized live with
the Web Audio API.

## Run

Open `index.html` directly in a browser, or serve the folder:

```
python3 -m http.server 8000
# then visit http://localhost:8000/
```

## Play

- **Space / ArrowUp / W / click / tap** — jump
- **M** — toggle music
- Eat mice (+25, and it gives you breathing room), jump over bins, cones and
  barriers, and don't let the catcatcher reach you — the gap closes over time
  and every stumble costs you. The game speeds up the longer you survive.
- Best score is saved in `localStorage`.

## Tests

```
node test.js    # 15 logic/render tests (engine runs headless in Node)
```

The engine in `game.js` is environment-agnostic (audio/storage/rng injected),
which is what makes the Node test suite possible.

Screenshots from the headless-browser E2E runs are in `shots/`.
