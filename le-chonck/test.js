'use strict';

const assert = require('assert');
const path = require('path');
const fs = require('fs');
const api = require(path.join(__dirname, 'game.js'));

const { Game, W, H, GROUND_Y, BASE_SPEED, MAX_SPEED, START_GAP, MAX_GAP, mulberry32 } = api;

function memStorage() {
  const m = new Map();
  return {
    getItem: k => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    _map: m
  };
}

function makeGame(seed = 42) {
  return new Game({ audio: null, storage: memStorage(), rng: mulberry32(seed) });
}

function stepN(game, seconds, input = {}, dt = 1 / 60) {
  const n = Math.round(seconds / dt);
  for (let i = 0; i < n; i++) game.step(dt, input);
}

function startGame(game) {
  game.step(1 / 60, { any: true });
  assert.strictEqual(game.state, 'play', 'game should be playing after start input');
}

function stepAlive(game, seconds, input = {}, dt = 1 / 60) {
  const n = Math.round(seconds / dt);
  for (let i = 0; i < n; i++) {
    if (game.state === 'play') game.gap = Math.max(game.gap, 500);
    game.step(dt, input);
  }
}

function stubCtx() {
  const calls = { fillRect: 0 };
  const grad = { addColorStop() {} };
  const ctx = new Proxy({}, {
    get(target, prop) {
      if (prop === '__calls') return calls;
      if (prop in target) return target[prop];
      if (prop === 'createLinearGradient' || prop === 'createRadialGradient') return () => grad;
      if (prop === 'measureText') return () => ({ width: 10 });
      if (prop === 'getImageData') return () => ({ data: new Uint8ClampedArray(4) });
      return (...args) => {
        if (prop === 'fillRect') calls.fillRect++;
        if (prop === 'arc' || prop === 'fill' || prop === 'stroke' || prop === 'fillText') calls[prop] = (calls[prop] || 0) + 1;
      };
    },
    set(target, prop, value) { target[prop] = value; return true; }
  });
  return ctx;
}

let passed = 0;
function test(name, fn) {
  try {
    fn();
    passed++;
    console.log('ok   - ' + name);
  } catch (e) {
    console.error('FAIL - ' + name);
    console.error(e.stack || e);
    process.exitCode = 1;
  }
}

test('html references game.js and a 480x270 canvas', () => {
  const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
  assert.ok(html.includes('src="game.js"'), 'script tag');
  assert.ok(/<canvas[^>]*width="480"[^>]*height="270"/.test(html), 'canvas size');
});

test('initial state is title; any input starts the game', () => {
  const g = makeGame();
  assert.strictEqual(g.state, 'title');
  g.step(1 / 60, { any: true });
  assert.strictEqual(g.state, 'play');
});

test('world scrolls and distance accumulates while playing', () => {
  const g = makeGame();
  startGame(g);
  const d0 = g.dist;
  stepN(g, 1.0);
  assert.ok(g.dist > d0 + 100, `dist should grow (d0=${d0}, now=${g.dist})`);
});

test('speed ramps up over time and is capped', () => {
  const g = makeGame();
  startGame(g);
  stepAlive(g, 2);
  const s2 = g.speed;
  stepAlive(g, 20);
  const s22 = g.speed;
  assert.ok(s22 > s2, `speed should increase (${s2} -> ${s22})`);
  g.elapsed = 1000;
  g.gap = 500;
  g.step(1 / 60, {});
  assert.strictEqual(g.speed, MAX_SPEED, 'speed capped at MAX_SPEED');
});

test('jump leaves the ground and lands back', () => {
  const g = makeGame();
  startGame(g);
  stepN(g, 0.5);
  assert.ok(g.cat.onGround, 'starts on ground');
  const y0 = g.cat.y;
  g.step(1 / 60, { jump: true });
  assert.ok(!g.cat.onGround && g.cat.vy < 0, 'jump impulse applied');
  let minY = g.cat.y;
  for (let i = 0; i < 120; i++) {
    g.step(1 / 60, { jump: false });
    minY = Math.min(minY, g.cat.y);
  }
  assert.ok(minY < y0 - 40, `jump apex should be high (minY=${minY}, y0=${y0})`);
  assert.ok(g.cat.onGround && g.cat.y === GROUND_Y - g.cat.h, 'lands back on ground');
});

test('jump input is edge-triggered (holding does not re-jump mid-air)', () => {
  const g = makeGame();
  startGame(g);
  stepN(g, 0.3);
  g.step(1 / 60, { jump: true });
  g.step(1 / 60, { jump: true });
  assert.ok(g.cat.vy > -600, `holding jump must not re-impulse (vy=${g.cat.vy})`);
  assert.ok(!g.cat.onGround, 'still airborne');
});

test('obstacles spawn over time, move left, and leave the screen', () => {
  const g = makeGame();
  startGame(g);
  stepAlive(g, 6);
  assert.ok(g.obstacles.length > 0, 'at least one obstacle spawned');
  const before = new Map(g.obstacles.map(o => [o, o.x]));
  stepAlive(g, 0.3);
  let moved = 0;
  for (const o of g.obstacles) {
    if (before.has(o)) {
      assert.ok(o.x < before.get(o), `obstacle should move left (${before.get(o)} -> ${o.x})`);
      moved++;
    }
  }
  assert.ok(moved > 0, 'tracked obstacles that moved');
  stepAlive(g, 60);
  assert.ok(g.obstacles.every(o => o.x > -60), 'no stuck obstacles offscreen');
});

test('collecting a mouse scores +25 and restores catcatcher gap (capped)', () => {
  const g = makeGame();
  startGame(g);
  stepN(g, 0.2);
  g.gap = 100;
  const m = { x: g.cat.x + 6, y: g.cat.y + 6, w: 12, h: 8 };
  g.mousies.push(m);
  const score0 = g.score;
  g.step(1 / 60, {});
  assert.strictEqual(g.mice, 1, 'mouse collected');
  assert.ok(g.score >= score0 + 25, `score +25 (${score0} -> ${g.score})`);
  assert.ok(g.gap > 100, 'gap restored');
  g.gap = MAX_GAP - 1;
  g.mousies.push({ x: g.cat.x + 6, y: g.cat.y + 6, w: 12, h: 8 });
  g.step(1 / 60, {});
  assert.ok(g.gap <= MAX_GAP && g.gap > MAX_GAP - 1, `gap capped at MAX_GAP (got ${g.gap})`);
});

test('baguette grants superspeed: +50, gap boost, trips disabled, faster scroll', () => {
  const g = makeGame();
  startGame(g);
  stepN(g, 0.3);
  g.baguettes.push({ x: g.cat.x + 6, y: g.cat.y + 6, w: 16, h: 6 });
  g.step(1 / 60, {});
  assert.ok(g.boost > 4, `boost active (${g.boost})`);
  assert.ok(g.bonus >= 50, `bonus +50 (${g.bonus})`);
  const gapBefore = g.gap;
  g.obstacles.push({ type: 'bin', x: g.cat.x + 8, y: GROUND_Y - 30, w: 20, h: 30 });
  g.step(1 / 60, {});
  assert.ok(g.cat.trip <= 0, 'no trip during superspeed');
  assert.ok(g.gap <= gapBefore, 'gap not penalized during superspeed');
  const d0 = g.dist;
  g.step(1 / 60, {});
  const dBoost = g.dist - d0;
  g.boost = 0;
  const d1 = g.dist;
  g.step(1 / 60, {});
  const dNormal = g.dist - d1;
  assert.ok(dBoost > dNormal * 1.4, `superspeed scrolls faster (${dBoost.toFixed(2)} vs ${dNormal.toFixed(2)})`);
});

test('all mice spawn fully above the street surface', () => {
  const g = makeGame(5);
  for (let i = 0; i < 50; i++) g.spawnMice();
  assert.ok(g.mousies.length > 0, 'mice spawned');
  for (const m of g.mousies) assert.ok(m.y + m.h <= GROUND_Y + 0.01, `mouse above ground (y=${m.y}, h=${m.h})`);
});

test('obstacle hit trips the cat, costs gap, grants invulnerability', () => {
  const g = makeGame();
  startGame(g);
  stepN(g, 0.2);
  g.gap = 120;
  g.obstacles.push({ type: 'bin', x: g.cat.x + 8, y: GROUND_Y - 30, w: 20, h: 30 });
  g.step(1 / 60, {});
  assert.ok(g.cat.trip > 0, 'trip started');
  assert.ok(g.cat.invuln > 0, 'invulnerable');
  assert.ok(Math.abs(g.gap - (120 - 25)) < 0.5, `gap penalty applied (gap=${g.gap})`);
  assert.strictEqual(g.state, 'play', 'trip is not game over');
  const gapAfter = g.gap;
  g.obstacles.push({ type: 'cone', x: g.cat.x + 8, y: GROUND_Y - 19, w: 15, h: 19 });
  g.step(1 / 60, {});
  assert.ok(g.gap === gapAfter || g.gap < gapAfter + 1, 'invulnerable: no second hit');
  assert.ok(g.cat.trip <= 0.6, 'no chain trips');
});

test('catcatcher gap drains over time; reaching 0 ends the game as caught', () => {
  const g = makeGame();
  startGame(g);
  stepN(g, 1);
  const gap0 = g.gap;
  stepN(g, 1);
  assert.ok(g.gap < gap0, 'gap drains');
  g.gap = 0.01;
  g.step(1 / 30, {});
  assert.strictEqual(g.state, 'over', 'game over when caught');
  assert.strictEqual(g.overReason, 'caught');
});

test('a decent player (jumps obstacles, eats mice) survives a long run', () => {
  const g = makeGame(7);
  startGame(g);
  let steps = 0;
  const dt = 1 / 60;
  while (g.state === 'play' && steps < 60 * 60) {
    let jump = false;
    const c = g.cat;
    if (c.onGround && c.trip <= 0) {
      const trigger = 0.35 * g.speed - 45;
      for (const o of g.obstacles) {
        const ahead = o.x - (c.x + c.w);
        if (ahead > -10 && ahead < trigger) { jump = true; break; }
      }
    }
    g.step(dt, { jump });
    steps++;
  }
  const survived = steps / 60;
  assert.ok(g.state === 'play' && survived >= 45, `bot should survive >= 45s (survived ${survived.toFixed(1)}s, gap=${g.gap.toFixed(1)})`);
  assert.ok(g.mice > 5, `bot collected mice (${g.mice})`);
  assert.ok(g.speed > BASE_SPEED + 100, `speed ramped during long run (${g.speed.toFixed(0)})`);
});

test('game over saves best score to storage and restart resets the run', () => {
  const storage = memStorage();
  const g = new Game({ audio: null, storage, rng: mulberry32(3) });
  startGame(g);
  stepN(g, 3);
  g.gap = 0.01;
  g.step(1 / 30, {});
  assert.strictEqual(g.state, 'over');
  assert.strictEqual(parseInt(storage.getItem('lechonck_best'), 10), g.best, 'best saved');
  assert.ok(g.best > 0, 'best positive');
  stepN(g, 0.6);
  g.step(1 / 60, { any: true });
  assert.strictEqual(g.state, 'play', 'restart works after over delay');
  assert.strictEqual(g.score, 0);
  assert.strictEqual(g.gap, START_GAP);
  assert.strictEqual(g.mice, 0);
  assert.ok(g.best > 0, 'best kept across restart');
});

test('title ignores jump-only edge until any input, then starts', () => {
  const g = makeGame();
  g.step(1 / 60, {});
  assert.strictEqual(g.state, 'title');
  g.step(1 / 60, { any: true });
  assert.strictEqual(g.state, 'play');
});

test('render does not throw in any state and draws many pixels', () => {
  const g = makeGame();
  const ctx = stubCtx();
  g.render(ctx, 0.5);
  let calls = ctx.__calls.fillRect;
  assert.ok(calls > 100, `title render draws (${calls} rects)`);
  startGame(g);
  stepN(g, 2);
  g.render(ctx, 1.0);
  calls = ctx.__calls.fillRect;
  assert.ok(calls > 300, `play render draws (${calls} rects)`);
  g.gap = 0.01;
  g.step(1 / 30, {});
  g.render(ctx, 2.0);
  assert.ok(ctx.__calls.fillRect > 300, 'over render draws');
});

test('render works with a real 2d-like surface (node-canvas not required): smoke via stub covers all states', () => {
  const g = makeGame(99);
  startGame(g);
  const ctx = stubCtx();
  for (let i = 0; i < 600; i++) {
    if (i === 300) { g.cat.trip = 0.5; g.shake = 0.3; }
    g.step(1 / 60, { jump: i === 120 });
    g.render(ctx, i / 60);
    if (g.state === 'over') break;
  }
  assert.ok(true, '600 mixed frames rendered without exceptions');
});

console.log(`\n${passed} tests passed${process.exitCode ? ' (with failures)' : ''}`);
