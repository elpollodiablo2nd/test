(function (root, factory) {
  var api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    window.LeChonck = api;
    var start = function () { api.boot(); };
    if (document.readyState === 'loading') window.addEventListener('DOMContentLoaded', start);
    else start();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var W = 480;
  var H = 270;
  var GROUND_Y = 230;
  var GRAV = 2400;
  var JUMP_V = -640;
  var BASE_SPEED = 170;
  var SPEED_RAMP = 4;
  var MAX_SPEED = 420;
  var START_GAP = 115;
  var MAX_GAP = 180;
  var CAT_X = 130;
  var CAT_W = 36;
  var CAT_H = 30;

  function mulberry32(seed) {
    var a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function overlap(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  function Game(opts) {
    opts = opts || {};
    this.rng = opts.rng || Math.random;
    this.storage = opts.storage || null;
    this.audio = opts.audio || null;
    this.best = this.loadBest();
    this.stars = [];
    for (var i = 0; i < 70; i++) {
      this.stars.push({ x: this.rng() * W, y: this.rng() * 130, s: this.rng() < 0.8 ? 1 : 2, p: this.rng() * 6.28 });
    }
    this.reset();
  }

  Game.prototype.loadBest = function () {
    if (!this.storage) return 0;
    try { return parseInt(this.storage.getItem('lechonck_best') || '0', 10) || 0; } catch (e) { return 0; }
  };

  Game.prototype.saveBest = function () {
    if (!this.storage) return;
    try { this.storage.setItem('lechonck_best', String(this.best)); } catch (e) {}
  };

  Game.prototype.reset = function () {
    this.state = 'title';
    this.elapsed = 0;
    this.overTime = 0;
    this.dist = 0;
    this.speed = BASE_SPEED;
    this.mice = 0;
    this.score = 0;
    this.gap = START_GAP;
    this.shake = 0;
    this.nextObstacle = 420;
    this.nextMouse = 260;
    this.obstacles = [];
    this.mousies = [];
    this.popups = [];
    this.cat = { x: CAT_X, y: GROUND_Y - CAT_H, w: CAT_W, h: CAT_H, vy: 0, onGround: true, trip: 0, invuln: 0, phase: 0 };
    this.prevJump = false;
    this.prevAny = false;
  };

  Game.prototype.start = function () {
    var best = this.best;
    this.reset();
    this.best = best;
    this.state = 'play';
    if (this.audio && this.audio.start) this.audio.start();
  };

  Game.prototype.catBox = function () {
    var c = this.cat;
    return { x: c.x + 4, y: c.y + 2, w: c.w - 8, h: c.h - 3 };
  };

  Game.prototype.spawnObstacle = function () {
    var r = this.rng();
    var type = r < 0.45 ? 'bin' : (r < 0.75 ? 'cone' : 'barrier');
    var defs = {
      bin: { w: 20, h: 30 },
      cone: { w: 15, h: 19 },
      barrier: { w: 28, h: 22 }
    };
    var d = defs[type];
    this.obstacles.push({ type: type, x: W + 24, y: GROUND_Y - d.h, w: d.w, h: d.h });
  };

  Game.prototype.spawnMice = function () {
    var arc = this.rng() < 0.45;
    var n = arc ? 3 : 1 + Math.floor(this.rng() * 3);
    for (var i = 0; i < n; i++) {
      var off = arc ? i * 18 : i * 16;
      var dy = arc ? (i === 1 ? -44 : -8) : 0;
      this.mousies.push({ x: W + 24 + off, y: GROUND_Y - 8 - dy, w: 12, h: 8 });
    }
  };

  Game.prototype.addPopup = function (x, y, text, color) {
    this.popups.push({ x: x, y: y, text: text, color: color || '#ffe9a8', life: 1 });
  };

  Game.prototype.step = function (dt, input) {
    dt = Math.min(dt, 0.05);
    input = input || {};
    var jump = !!input.jump;
    var any = !!input.any || jump;

    if (this.state === 'title') {
      if (any) this.start();
      this.prevJump = jump; this.prevAny = any;
      return;
    }

    if (this.state === 'over') {
      this.overTime += dt;
      this.updatePopups(dt);
      if (any && this.overTime > 0.5) this.start();
      this.prevJump = jump; this.prevAny = any;
      return;
    }

    this.elapsed += dt;
    this.speed = Math.min(MAX_SPEED, BASE_SPEED + this.elapsed * SPEED_RAMP);

    var c = this.cat;
    var tripped = c.trip > 0;
    var effSpeed = tripped ? this.speed * 0.3 : this.speed;

    this.dist += effSpeed * dt;

    if (jump && !this.prevJump && c.onGround && c.trip <= 0) {
      c.vy = JUMP_V;
      c.onGround = false;
    }
    c.vy += GRAV * dt;
    c.y += c.vy * dt;
    if (c.y >= GROUND_Y - c.h) {
      c.y = GROUND_Y - c.h;
      c.vy = 0;
      c.onGround = true;
    }
    c.phase += effSpeed * dt * 0.055;
    if (c.trip > 0) c.trip -= dt;
    if (c.invuln > 0) c.invuln -= dt;
    if (this.shake > 0) this.shake -= dt;

    if (this.dist >= this.nextObstacle) {
      this.spawnObstacle();
      this.nextObstacle = this.dist + effSpeed * (0.75 + this.rng() * 0.9);
    }
    if (this.dist >= this.nextMouse) {
      this.spawnMice();
      this.nextMouse = this.dist + 150 + this.rng() * 300;
    }

    var i, e;
    for (i = this.obstacles.length - 1; i >= 0; i--) {
      e = this.obstacles[i];
      e.x -= effSpeed * dt;
      if (e.x < -60) { this.obstacles.splice(i, 1); continue; }
      if (c.trip <= 0 && c.invuln <= 0 && overlap(this.catBox(), { x: e.x + 2, y: e.y + 2, w: e.w - 4, h: e.h - 2 })) {
        c.trip = 0.6;
        c.invuln = 1.5;
        this.gap = Math.max(0, this.gap - 25);
        this.shake = 0.35;
        this.addPopup(c.x + 6, c.y - 10, 'ouch!', '#ff8a7a');
        this.obstacles.splice(i, 1);
        if (this.audio && this.audio.thud) this.audio.thud();
      }
    }

    var box = this.catBox();
    for (i = this.mousies.length - 1; i >= 0; i--) {
      e = this.mousies[i];
      e.x -= effSpeed * dt;
      if (e.x < -40) { this.mousies.splice(i, 1); continue; }
      if (overlap(box, e)) {
        this.mousies.splice(i, 1);
        this.mice++;
        this.gap = Math.min(MAX_GAP, this.gap + 5);
        this.addPopup(e.x, e.y - 8, '+25 miam!', '#a8ffb0');
        if (this.audio && this.audio.blip) this.audio.blip();
      }
    }

    this.score = this.mice * 25 + Math.floor(this.dist / 40);
    this.gap -= (2.5 + this.speed * 0.01) * dt;
    if (this.gap <= 0) {
      this.gap = 0;
      this.state = 'over';
      this.overTime = 0;
      this.overReason = 'caught';
      if (this.score > this.best) { this.best = this.score; this.saveBest(); }
      if (this.audio && this.audio.gameOver) this.audio.gameOver();
    }

    this.updatePopups(dt);
    this.prevJump = jump;
    this.prevAny = any;
  };

  Game.prototype.updatePopups = function (dt) {
    for (var i = this.popups.length - 1; i >= 0; i--) {
      var p = this.popups[i];
      p.y -= 22 * dt;
      p.life -= dt * 1.2;
      if (p.life <= 0) this.popups.splice(i, 1);
    }
  };

  function px(ctx, x, y, w, h, color) {
    ctx.fillStyle = color;
    ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
  }

  function text(ctx, str, x, y, size, color, align) {
    ctx.font = 'bold ' + size + 'px monospace';
    ctx.textAlign = align || 'left';
    ctx.textBaseline = 'top';
    ctx.fillStyle = 'rgba(0,0,0,0.55)';
    ctx.fillText(str, x + 1, y + 1);
    ctx.fillStyle = color;
    ctx.fillText(str, x, y);
  }

  Game.prototype.drawSky = function (ctx, t) {
    var g = ctx.createLinearGradient(0, 0, 0, GROUND_Y);
    g.addColorStop(0, '#1c1038');
    g.addColorStop(0.55, '#4a2360');
    g.addColorStop(0.85, '#a04a63');
    g.addColorStop(1, '#e8845c');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, GROUND_Y);
    for (var i = 0; i < this.stars.length; i++) {
      var s = this.stars[i];
      var a = 0.4 + 0.6 * Math.abs(Math.sin(t * 0.7 + s.p));
      ctx.globalAlpha = a * (1 - s.y / 160);
      px(ctx, s.x, s.y, s.s, s.s, '#ffe9c9');
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = '#f5e6c8';
    ctx.beginPath(); ctx.arc(408, 42, 16, 0, 6.29); ctx.fill();
    px(ctx, 402, 38, 5, 5, '#e0cba6');
    px(ctx, 411, 47, 4, 4, '#e0cba6');
    px(ctx, 405, 49, 3, 3, '#e0cba6');
  };

  function drawEiffel(ctx, x, baseY, h, color) {
    var w = h * 0.42;
    px(ctx, x + w / 2 - 1, baseY - h, 3, h, color);
    px(ctx, x + w / 2 - 4, baseY - h * 0.72, 8, 3, color);
    px(ctx, x + w / 2 - 7, baseY - h * 0.45, 14, 3, color);
    px(ctx, x + w * 0.12, baseY - h * 0.45, 3, h * 0.45, color);
    px(ctx, x + w * 0.85, baseY - h * 0.45, 3, h * 0.45, color);
    px(ctx, x + w * 0.05, baseY - 4, 5, 4, color);
    px(ctx, x + w * 0.9, baseY - 4, 5, 4, color);
    px(ctx, x + w * 0.22, baseY - h * 0.72, w * 0.56, 2, color);
    px(ctx, x + w * 0.3, baseY - h * 0.45, w * 0.4, 2, color);
  }

  Game.prototype.drawFar = function (ctx, t) {
    var off = -(this.dist * 0.15) % 620;
    for (var k = -1; k < 2; k++) {
      var base = off + k * 620;
      px(ctx, base + 20, GROUND_Y - 60, 46, 60, '#241543');
      px(ctx, base + 80, GROUND_Y - 84, 38, 84, '#241543');
      px(ctx, base + 130, GROUND_Y - 52, 52, 52, '#241543');
      drawEiffel(ctx, base + 210, GROUND_Y, 150, '#241543');
      if (Math.floor(t * 1.5) % 2 === 0) px(ctx, base + 210 + 31, GROUND_Y - 154, 3, 3, '#ff6a6a');
      px(ctx, base + 350, GROUND_Y - 70, 44, 70, '#241543');
      px(ctx, base + 410, GROUND_Y - 96, 34, 96, '#241543');
      px(ctx, base + 460, GROUND_Y - 58, 60, 58, '#241543');
      px(ctx, base + 540, GROUND_Y - 78, 40, 78, '#241543');
    }
  };

  Game.prototype.drawMid = function (ctx, t) {
    var off = -(this.dist * 0.4) % 520;
    for (var k = -1; k < 2; k++) {
      var base = off + k * 520;
      px(ctx, base + 10, GROUND_Y - 96, 70, 96, '#33204f');
      px(ctx, base + 95, GROUND_Y - 120, 60, 120, '#3a2657');
      px(ctx, base + 170, GROUND_Y - 84, 80, 84, '#33204f');
      px(ctx, base + 265, GROUND_Y - 108, 55, 108, '#3a2657');
      px(ctx, base + 335, GROUND_Y - 90, 70, 90, '#33204f');
      px(ctx, base + 420, GROUND_Y - 116, 62, 116, '#3a2657');
      for (var b = 0; b < 6; b++) {
        var bx = base + 14 + b * 78;
        for (var wy = GROUND_Y - 88; wy < GROUND_Y - 16; wy += 14) {
          for (var wx = bx; wx < bx + 56; wx += 12) {
            var lit = ((wx * 7 + wy * 13 + b * 31) % 17) < 5;
            if (lit) px(ctx, wx + 2, wy, 6, 8, (t % 2 + ((wx + wy) % 3)) % 4 === 0 ? '#ffd98a' : '#e8b96a');
          }
        }
      }
      var lampX = base + 240;
      px(ctx, lampX, GROUND_Y - 78, 3, 78, '#1a0f2e');
      px(ctx, lampX - 6, GROUND_Y - 82, 15, 5, '#1a0f2e');
      px(ctx, lampX - 3, GROUND_Y - 79, 9, 4, '#ffdf9e');
      ctx.globalAlpha = 0.16;
      ctx.fillStyle = '#ffdf9e';
      ctx.beginPath(); ctx.arc(lampX + 1, GROUND_Y - 76, 14, 0, 6.29); ctx.fill();
      ctx.globalAlpha = 1;
      px(ctx, base + 96, GROUND_Y - 34, 58, 10, '#7a2d3f');
      for (var a = 0; a < 6; a++) px(ctx, base + 96 + a * 10, GROUND_Y - 34, 5, 10, a % 2 ? '#e8ded0' : '#7a2d3f');
      px(ctx, base + 100, GROUND_Y - 24, 50, 24, '#241533');
    }
  };

  Game.prototype.drawStreet = function (ctx) {
    px(ctx, 0, GROUND_Y, W, H - GROUND_Y, '#4b3a5e');
    px(ctx, 0, GROUND_Y, W, 4, '#6e5878');
    var off = -(this.dist % 36);
    for (var row = 0; row < 2; row++) {
      var y = GROUND_Y + 8 + row * 16;
      for (var x = off - 36; x < W + 36; x += 36) {
        px(ctx, x + (row ? 18 : 0), y, 30, 12, row ? '#443452' : '#52406a');
      }
    }
    var man = -(this.dist * 1 % 700);
    px(ctx, man + 300, GROUND_Y + 22, 16, 6, '#33264a');
    px(ctx, man + 900, GROUND_Y + 22, 16, 6, '#33264a');
  };

  Game.prototype.drawMouse = function (ctx, m, t) {
    var bob = Math.sin(t * 6 + m.x * 0.1) * 1;
    var y = m.y + bob;
    px(ctx, m.x + 1, y + 3, 9, 5, '#9a9aa6');
    px(ctx, m.x + 8, y + 2, 4, 4, '#9a9aa6');
    px(ctx, m.x + 9, y + 1, 2, 2, '#e8a0b4');
    px(ctx, m.x + 10, y + 3, 1, 1, '#1a1a22');
    px(ctx, m.x - 3, y + 4, 4, 2, '#e8a0b4');
    px(ctx, m.x + 2, y + 8, 2, 1, '#e8a0b4');
    px(ctx, m.x + 7, y + 8, 2, 1, '#e8a0b4');
  };

  Game.prototype.drawObstacle = function (ctx, o) {
    if (o.type === 'bin') {
      px(ctx, o.x, o.y + 4, o.w, o.h - 4, '#5f7a6a');
      px(ctx, o.x - 1, o.y, o.w + 2, 5, '#7d9a88');
      px(ctx, o.x + o.w / 2 - 2, o.y - 2, 4, 2, '#7d9a88');
      px(ctx, o.x + 3, o.y + 8, 2, o.h - 10, '#4c6355');
      px(ctx, o.x + o.w - 5, o.y + 8, 2, o.h - 10, '#4c6355');
    } else if (o.type === 'cone') {
      px(ctx, o.x + 4, o.y + 12, 7, 7, '#e86a2d');
      px(ctx, o.x + 5, o.y + 8, 5, 4, '#e86a2d');
      px(ctx, o.x + 6, o.y + 4, 3, 4, '#e86a2d');
      px(ctx, o.x + 6, o.y + 9, 3, 2, '#f5e6c8');
      px(ctx, o.x + 1, o.y + o.h - 2, o.w - 2, 2, '#c94f1d');
    } else {
      px(ctx, o.x, o.y, o.w, 7, '#d8b13c');
      px(ctx, o.x + 4, o.y + 1, 4, 5, '#c23b3b');
      px(ctx, o.x + 14, o.y + 1, 4, 5, '#c23b3b');
      px(ctx, o.x + 2, o.y + 7, 3, o.h - 7, '#8a6a2d');
      px(ctx, o.x + o.w - 5, o.y + 7, 3, o.h - 7, '#8a6a2d');
    }
  };

  Game.prototype.drawCat = function (ctx, t) {
    var c = this.cat;
    var x = c.x, y = c.y;
    ctx.save();
    ctx.translate(Math.round(x + c.w / 2), Math.round(y + c.h));
    if (c.trip > 0) ctx.rotate(-0.5 + Math.sin(t * 30) * 0.08);
    else if (!c.onGround) ctx.rotate(-0.12);
    ctx.translate(-Math.round(c.w / 2), -c.h);
    var run = c.onGround && c.trip <= 0;
    var lp = run ? Math.sin(c.phase * 6) : 0;
    px(ctx, 2, 22 + (run ? Math.max(0, lp) * 2 : 2), 5, 6 - (run ? Math.max(0, lp) * 2 : 2), '#d17a24');
    px(ctx, 12, 23 + (run ? Math.max(0, -lp) * 2 : 1), 5, 5 - (run ? Math.max(0, -lp) * 2 : 1), '#d17a24');
    px(ctx, 22, 23 + (run ? Math.max(0, lp) * 2 : 1), 5, 5 - (run ? Math.max(0, lp) * 2 : 1), '#d17a24');
    px(ctx, 30, 22 + (run ? Math.max(0, -lp) * 2 : 2), 5, 6 - (run ? Math.max(0, -lp) * 2 : 2), '#d17a24');
    px(ctx, 0, 4, 4, 12 + (c.onGround ? 0 : -3), '#e8912d');
    px(ctx, -2, 0, 5, 6, '#e8912d');
    px(ctx, -3, -3, 4, 4, '#e8912d');
    px(ctx, -3, -3, 4, 2, '#f5b26a');
    px(ctx, 3, 8, 30, 20, '#e8912d');
    px(ctx, 24, 20, 9, 8, '#f5e6c8');
    px(ctx, 3, 12, 4, 14, '#c96f1a');
    px(ctx, 12, 10, 4, 16, '#c96f1a');
    px(ctx, 21, 8, 4, 18, '#c96f1a');
    px(ctx, 24, 2, 13, 14, '#e8912d');
    px(ctx, 24, 0, 4, 4, '#e8912d');
    px(ctx, 33, 0, 4, 4, '#e8912d');
    px(ctx, 25, 1, 3, 3, '#f5b26a');
    px(ctx, 33, 1, 3, 3, '#f5b26a');
    px(ctx, 27, 7, 3, 3, '#2d5a2d');
    px(ctx, 33, 7, 3, 3, '#2d5a2d');
    px(ctx, 28, 8, 1, 1, '#0a0a12');
    px(ctx, 34, 8, 1, 1, '#0a0a12');
    px(ctx, 30, 12, 4, 2, '#e88a8a');
    ctx.fillStyle = '#f5e6c8';
    ctx.fillRect(37, 9, 5, 1);
    ctx.fillRect(37, 11, 5, 1);
    ctx.fillRect(36, 10, 5, 1);
    ctx.restore();
    if (c.invuln > 0 && c.trip <= 0 && Math.floor(t * 12) % 2 === 0) {
      ctx.globalAlpha = 0.35;
      px(ctx, c.x - 2, c.y - 2, c.w + 4, c.h + 4, '#ffffff');
      ctx.globalAlpha = 1;
    }
  };

  Game.prototype.drawCatcher = function (ctx, t) {
    var c = this.cat;
    var x = Math.round(c.x - this.gap);
    if (x < -70) return;
    var y = GROUND_Y;
    var lunge = this.gap < 45 ? 1 : 0;
    var lp = Math.sin(c.phase * 6) * 2;
    px(ctx, x + 4, y - 10 + Math.max(0, lp), 5, 10 - Math.max(0, lp), '#23304f');
    px(ctx, x + 13, y - 10 + Math.max(0, -lp), 5, 10 - Math.max(0, -lp), '#23304f');
    px(ctx, x + 2, y - 30, 18, 22, '#2c3e70');
    px(ctx, x + 2, y - 30, 18, 4, '#1f2c52');
    px(ctx, x + 6, y - 44, 11, 11, '#e8b98a');
    px(ctx, x + 5, y - 48, 13, 5, '#c23b3b');
    px(ctx, x + 5, y - 44, 13, 2, '#a02e2e');
    px(ctx, x + 8, y - 41, 2, 2, '#1a1a22');
    px(ctx, x + 12, y - 41, 2, 2, '#1a1a22');
    px(ctx, x + 8, y - 37, 5, 1, '#7a4a2d');
    var armX = x + 18 + lunge * 8;
    px(ctx, armX - 2, y - 28, 10 + lunge * 6, 3, '#e8b98a');
    var netX = armX + 8 + lunge * 6;
    var netY = y - 40;
    px(ctx, netX - 1, y - 46, 2, 16, '#8a6a4d');
    ctx.strokeStyle = '#d8d2c4';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(netX + 7, netY + 4, 8, -1.2, 1.2);
    ctx.stroke();
    px(ctx, netX + 2, netY + 2, 11, 1, 'rgba(216,210,196,0.7)');
    px(ctx, netX + 5, netY - 2, 1, 11, 'rgba(216,210,196,0.7)');
  };

  Game.prototype.drawHUD = function (ctx) {
    text(ctx, 'SCORE ' + String(this.score).padStart(6, '0'), 8, 8, 10, '#ffe9c9');
    px(ctx, 8, 22, 10, 6, '#9a9aa6');
    px(ctx, 17, 21, 3, 3, '#9a9aa6');
    px(ctx, 5, 23, 3, 2, '#e8a0b4');
    text(ctx, 'x' + this.mice, 22, 21, 9, '#a8ffb0');
    var mult = (this.speed / BASE_SPEED).toFixed(1);
    text(ctx, 'VITESSE x' + mult, 8, 34, 8, '#c9a8e8');
    var bw = 90;
    var frac = Math.max(0, this.gap / MAX_GAP);
    text(ctx, 'LE CATCHER', W - 8 - bw, 8, 8, frac < 0.3 ? '#ff8a7a' : '#e8c9a8', 'left');
    px(ctx, W - 8 - bw, 18, bw, 7, 'rgba(0,0,0,0.5)');
    px(ctx, W - 8 - bw + 1, 19, (bw - 2) * frac, 5, frac < 0.3 ? '#e84a3c' : (frac < 0.6 ? '#e8a13c' : '#7ac96a'));
  };

  Game.prototype.drawPopups = function (ctx) {
    for (var i = 0; i < this.popups.length; i++) {
      var p = this.popups[i];
      ctx.globalAlpha = Math.max(0, Math.min(1, p.life));
      text(ctx, p.text, p.x, p.y, 8, p.color);
    }
    ctx.globalAlpha = 1;
  };

  Game.prototype.drawOverlays = function (ctx, t) {
    if (this.state === 'title') {
      ctx.fillStyle = 'rgba(12,6,26,0.55)';
      ctx.fillRect(0, 0, W, H);
      text(ctx, 'LE CHONCK', W / 2, 62, 34, '#ffb35c', 'center');
      text(ctx, 'une aventure parisienne', W / 2, 104, 10, '#e8c9a8', 'center');
      text(ctx, 'mange les souris, esquive les poubelles,', W / 2, 132, 9, '#c9b8e8', 'center');
      text(ctx, 'et fuis le catcatcher qui approche...', W / 2, 144, 9, '#c9b8e8', 'center');
      if (Math.floor(t * 2) % 2 === 0) text(ctx, 'ESPACE / CLIC pour jouer', W / 2, 176, 11, '#ffe9c9', 'center');
      text(ctx, 'RECORD ' + this.best, W / 2, 200, 9, '#a8ffb0', 'center');
    } else if (this.state === 'over') {
      ctx.fillStyle = 'rgba(40,8,16,0.6)';
      ctx.fillRect(0, 0, W, H);
      text(ctx, 'ATTRAPÉ !', W / 2, 80, 30, '#ff8a7a', 'center');
      text(ctx, 'le catcatcher a eu le chonck...', W / 2, 120, 9, '#e8c9a8', 'center');
      text(ctx, 'SCORE ' + this.score, W / 2, 146, 12, '#ffe9c9', 'center');
      text(ctx, 'RECORD ' + this.best, W / 2, 164, 10, '#a8ffb0', 'center');
      if (this.overTime > 0.5 && Math.floor(t * 2) % 2 === 0) text(ctx, 'ESPACE pour rejouer', W / 2, 192, 10, '#ffe9c9', 'center');
    }
  };

  Game.prototype.render = function (ctx, t) {
    t = t || 0;
    ctx.save();
    if (this.shake > 0) {
      ctx.translate((this.rng() - 0.5) * 6 * this.shake * 3, (this.rng() - 0.5) * 6 * this.shake * 3);
    }
    this.drawSky(ctx, t);
    this.drawFar(ctx, t);
    this.drawMid(ctx, t);
    this.drawStreet(ctx);
    for (var i = 0; i < this.mousies.length; i++) this.drawMouse(ctx, this.mousies[i], t);
    for (i = 0; i < this.obstacles.length; i++) this.drawObstacle(ctx, this.obstacles[i]);
    this.drawCatcher(ctx, t);
    this.drawCat(ctx, t);
    this.drawPopups(ctx);
    if (this.state === 'play') this.drawHUD(ctx);
    ctx.restore();
    this.drawOverlays(ctx, t);
    for (i = 0; i < 110; i++) {
      ctx.globalAlpha = 0.05;
      px(ctx, this.rng() * W, this.rng() * H, 1, 1, this.rng() < 0.5 ? '#ffffff' : '#000000');
    }
    ctx.globalAlpha = 1;
    var v = ctx.createRadialGradient(W / 2, H / 2, H * 0.45, W / 2, H / 2, H * 0.95);
    v.addColorStop(0, 'rgba(0,0,0,0)');
    v.addColorStop(1, 'rgba(10,4,20,0.5)');
    ctx.fillStyle = v;
    ctx.fillRect(0, 0, W, H);
  };

  function LofiMusic() {
    this.ctx = null;
    this.playing = false;
    this.muted = false;
    this.timer = null;
    this.step = 0;
    this.nextTime = 0;
    this.bpm = 72;
    this.chords = [
      [57, 60, 64, 71],
      [53, 57, 60, 64],
      [60, 64, 67, 71],
      [55, 59, 62, 64]
    ];
    this.roots = [45, 41, 48, 43];
  }

  LofiMusic.prototype.ensure = function () {
    if (this.ctx || typeof window === 'undefined') return;
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    this.ctx = new AC();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.55;
    var comp = this.ctx.createDynamicsCompressor();
    comp.threshold.value = -18;
    comp.ratio.value = 4;
    this.master.connect(comp);
    comp.connect(this.ctx.destination);
    this.noiseBuf = this.ctx.createBuffer(1, this.ctx.sampleRate * 2, this.ctx.sampleRate);
    var data = this.noiseBuf.getChannelData(0);
    for (var i = 0; i < data.length; i++) {
      data[i] = (Math.random() * 2 - 1) * 0.5;
      if (Math.random() < 0.0006) data[i] += (Math.random() * 2 - 1) * 0.9;
    }
    var crackle = this.ctx.createBufferSource();
    crackle.buffer = this.noiseBuf;
    crackle.loop = true;
    var cFilter = this.ctx.createBiquadFilter();
    cFilter.type = 'lowpass';
    cFilter.frequency.value = 4200;
    var cGain = this.ctx.createGain();
    cGain.gain.value = 0.018;
    crackle.connect(cFilter); cFilter.connect(cGain); cGain.connect(this.master);
    crackle.start();
  };

  LofiMusic.prototype.mtof = function (m) { return 440 * Math.pow(2, (m - 69) / 12); };

  LofiMusic.prototype.start = function () {
    this.ensure();
    if (!this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    if (this.playing) return;
    this.playing = true;
    this.step = 0;
    this.nextTime = this.ctx.currentTime + 0.08;
    if (!this.timer) {
      var self = this;
      this.timer = setInterval(function () { self.schedule(); }, 25);
    }
  };

  LofiMusic.prototype.stop = function () {
    this.playing = false;
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
  };

  LofiMusic.prototype.toggleMute = function () {
    this.muted = !this.muted;
    if (this.master) this.master.gain.value = this.muted ? 0 : 0.55;
    return this.muted;
  };

  LofiMusic.prototype.schedule = function () {
    if (!this.playing || !this.ctx) return;
    var spb = 60 / this.bpm;
    while (this.nextTime < this.ctx.currentTime + 0.15) {
      var s16 = this.step % 16;
      var swing = s16 % 2 === 1 ? spb * 0.12 : 0;
      this.playStep(this.step, this.nextTime + swing, spb);
      this.nextTime += spb / 2;
      this.step = (this.step + 1) % 64;
    }
  };

  LofiMusic.prototype.env = function (t, a, d, peak) {
    var g = this.ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(peak, t + a);
    g.gain.exponentialRampToValueAtTime(0.0001, t + a + d);
    g.connect(this.master);
    return g;
  };

  LofiMusic.prototype.tone = function (freq, t, dur, type, peak, filterFreq) {
    var o = this.ctx.createOscillator();
    o.type = type;
    o.frequency.value = freq;
    var f = this.ctx.createBiquadFilter();
    f.type = 'lowpass';
    f.frequency.value = filterFreq || 2000;
    var g = this.env(t, 0.012, dur, peak);
    o.connect(f); f.connect(g);
    o.start(t); o.stop(t + dur + 0.05);
  };

  LofiMusic.prototype.noise = function (t, dur, peak, filterType, filterFreq) {
    var src = this.ctx.createBufferSource();
    src.buffer = this.noiseBuf;
    src.loop = true;
    var f = this.ctx.createBiquadFilter();
    f.type = filterType;
    f.frequency.value = filterFreq;
    var g = this.env(t, 0.004, dur, peak);
    src.connect(f); f.connect(g);
    src.start(t); src.stop(t + dur + 0.05);
  };

  LofiMusic.prototype.playStep = function (step, t, spb) {
    var bar = Math.floor(step / 16) % 4;
    var s16 = step % 16;
    var chord = this.chords[bar];
    if (s16 === 0 || s16 === 8) {
      var vol = s16 === 0 ? 0.11 : 0.07;
      for (var i = 0; i < chord.length; i++) {
        this.tone(this.mtof(chord[i]), t + i * 0.012, spb * 1.6, 'triangle', vol, 1400);
      }
    }
    if (s16 === 0 || s16 === 8) this.tone(this.mtof(this.roots[bar]), t, spb * 1.8, 'sine', 0.3, 500);
    if (s16 === 0 || s16 === 8 || s16 === 11) {
      var o = this.ctx.createOscillator();
      o.type = 'sine';
      o.frequency.setValueAtTime(150, t);
      o.frequency.exponentialRampToValueAtTime(44, t + 0.11);
      var g = this.env(t, 0.004, 0.16, 0.5);
      o.connect(g);
      o.start(t); o.stop(t + 0.25);
    }
    if (s16 === 4 || s16 === 12) {
      this.noise(t, 0.13, 0.16, 'bandpass', 1900);
      this.tone(190, t, 0.09, 'triangle', 0.12, 900);
    }
    if (s16 % 2 === 0) this.noise(t, 0.03, s16 % 4 === 2 ? 0.07 : 0.045, 'highpass', 7200);
  };

  LofiMusic.prototype.blip = function () {
    if (!this.ctx || !this.playing) return;
    var t = this.ctx.currentTime;
    this.tone(880, t, 0.07, 'square', 0.06, 3200);
    this.tone(1318, t + 0.06, 0.09, 'square', 0.05, 3600);
  };

  LofiMusic.prototype.thud = function () {
    if (!this.ctx || !this.playing) return;
    var t = this.ctx.currentTime;
    this.noise(t, 0.16, 0.25, 'lowpass', 320);
    var o = this.ctx.createOscillator();
    o.type = 'sine';
    o.frequency.setValueAtTime(120, t);
    o.frequency.exponentialRampToValueAtTime(40, t + 0.14);
    var g = this.env(t, 0.004, 0.16, 0.4);
    o.connect(g);
    o.start(t); o.stop(t + 0.25);
  };

  LofiMusic.prototype.gameOver = function () {
    if (!this.ctx || !this.playing) return;
    var t = this.ctx.currentTime;
    var notes = [64, 62, 60, 57];
    for (var i = 0; i < notes.length; i++) {
      this.tone(this.mtof(notes[i]), t + i * 0.22, 0.3, 'triangle', 0.14, 1200);
    }
  };

  function boot() {
    var canvas = document.getElementById('game');
    var ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    var music = new LofiMusic();
    var storage = null;
    try { storage = window.localStorage; } catch (e) { storage = null; }
    var game = new Game({ audio: music, storage: storage });
    window.__game = game;
    window.__music = music;

    function resize() {
      var scale = Math.min(window.innerWidth / W, window.innerHeight / H);
      canvas.style.width = Math.floor(W * scale) + 'px';
      canvas.style.height = Math.floor(H * scale) + 'px';
    }
    window.addEventListener('resize', resize);
    resize();

    var jumpKeys = { Space: 1, ArrowUp: 1, KeyW: 1 };
    var anyPressed = false;
    var jumpDown = false;
    var jumpQueued = false;
    function press(code) {
      anyPressed = true;
      if (jumpKeys[code]) { jumpDown = true; jumpQueued = true; return false; }
      if (code === 'KeyM') { music.toggleMute(); return false; }
      return true;
    }
    window.addEventListener('keydown', function (e) {
      if (press(e.code) === false) e.preventDefault();
    });
    window.addEventListener('keyup', function (e) {
      if (jumpKeys[e.code]) jumpDown = false;
    });
    function pointerDown(e) {
      e.preventDefault();
      anyPressed = true;
      jumpDown = true;
      jumpQueued = true;
    }
    canvas.addEventListener('mousedown', pointerDown);
    canvas.addEventListener('touchstart', pointerDown, { passive: false });
    window.addEventListener('mouseup', function () { jumpDown = false; });
    window.addEventListener('touchend', function () { jumpDown = false; });

    var last = performance.now();
    var t = 0;
    function frame(now) {
      var dt = (now - last) / 1000;
      last = now;
      t += dt;
      game.step(dt, { jump: jumpDown || jumpQueued, any: anyPressed });
      anyPressed = false;
      jumpQueued = false;
      game.render(ctx, t);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  return {
    W: W, H: H, GROUND_Y: GROUND_Y, BASE_SPEED: BASE_SPEED, MAX_SPEED: MAX_SPEED,
    START_GAP: START_GAP, MAX_GAP: MAX_GAP, CAT_X: CAT_X,
    Game: Game, LofiMusic: LofiMusic, boot: boot, mulberry32: mulberry32
  };
});
