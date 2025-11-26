const canvas = document.getElementById("captchaCanvas");
const ctx = canvas.getContext("2d");

const WIDTH = 600;
const HEIGHT = 350;
const HUD_HEIGHT = 56;
const FPS = 60;
const MAX_DURATION = 20.0;
const RESULT_DISPLAY_TIME = 1.2;

const COLOR_MAP = {
  BLUE: [80, 160, 255],
  RED: [230, 80, 80],
  GREEN: [80, 200, 120],
  YELLOW: [240, 220, 80],
  ORANGE: [245, 170, 80],
};
const COLOR_NAMES = Object.keys(COLOR_MAP);

const BG_TOP = [230, 240, 255];
const BG_BOTTOM = [245, 250, 255];
const HUD_BG = [255, 255, 255];
const HUD_BORDER = [205, 215, 235];
const TEXT_PRIMARY = "rgb(40,50,80)";
const SUCCESS_COLOR = "rgb(0,150,80)";
const FAIL_COLOR = "rgb(200,50,50)";
const TIME_BAR_BG = [220, 230, 245];
const TIME_BAR_FILL = [80, 140, 255];

const MIN_SPEED = 25;
const MAX_SPEED = 40;

let game = null;
let attempts = 0;

function randomVelocity() {
  let vx = 0,
    vy = 0;
  while (Math.abs(vx) < 5 && Math.abs(vy) < 5) {
    vx = Math.random() * 2 * MAX_SPEED - MAX_SPEED;
    vy = Math.random() * 2 * MAX_SPEED - MAX_SPEED;
  }
  return [vx, vy];
}

// ===== Fingerprinting event log =====
const events = [];

function nowSeconds() {
  return performance.now() / 1000;
}

function logEvent(type, extra = {}) {
  events.push({
    type,
    time: nowSeconds(),
    ...extra,
  });
}

class Bubble {
  constructor(id, x, y, radius, color_name) {
    this.id = id;
    this.x = x;
    this.y = y;
    this.radius = radius;
    this.color_name = color_name;
    this.color = COLOR_MAP[color_name];
    [this.vx, this.vy] = randomVelocity();
    this.alive = true;
  }
  move(dt) {
    if (!this.alive) return;
    this.x += this.vx * dt;
    this.y += this.vy * dt;

    if (
      this.x < -this.radius ||
      this.x > WIDTH + this.radius ||
      this.y < -this.radius ||
      this.y > HEIGHT + this.radius
    ) {
      const sides = ["left", "right", "top", "bottom"];
      const side = sides[Math.floor(Math.random() * sides.length)];
      if (side == "left") {
        this.x = -this.radius;
        this.y = HUD_HEIGHT + 30 + Math.random() * (HEIGHT - HUD_HEIGHT - 70);
      } else if (side == "right") {
        this.x = WIDTH + this.radius;
        this.y = HUD_HEIGHT + 30 + Math.random() * (HEIGHT - HUD_HEIGHT - 70);
      } else if (side == "top") {
        this.x = 50 + Math.random() * (WIDTH - 100);
        this.y = HUD_HEIGHT + 10 - this.radius;
      } else {
        this.x = 50 + Math.random() * (WIDTH - 100);
        this.y = HEIGHT - 10 + this.radius;
      }
      [this.vx, this.vy] = randomVelocity();
    }
  }
  draw(ctx) {
    if (!this.alive) return;
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.radius, 0, 2 * Math.PI);
    ctx.fillStyle = `rgb(${this.color[0]},${this.color[1]},${this.color[2]})`;
    ctx.fill();
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(0,0,0,0.2)";
    ctx.stroke();
  }
  isClicked(mx, my) {
    let dx = mx - this.x;
    let dy = my - this.y;
    return dx * dx + dy * dy <= this.radius * this.radius;
  }
}

function generateInstruction() {
  const count = [2, 3][Math.floor(Math.random() * 2)];
  const direction = ["ascending", "descending"][Math.floor(Math.random() * 2)];
  return {
    text: `Burst ${count} bubbles in ${direction} order of size.`,
    count: count,
    direction: direction,
  };
}

function initGame() {
  const instruction = generateInstruction();
  const now = performance.now() / 1000;

  // reset fingerprint events for this attempt
  events.length = 0;
  logEvent("session_start");
  logEvent("instruction_shown", { text: instruction.text });

  const DISTINCT_RADII = [15, 30, 50, 65, 80]; // fixed distinct sizes
  const radii = [...DISTINCT_RADII];
  radii.sort(() => Math.random() - 0.5); // shuffle for randomness

  const gameState = {
    instruction: instruction,
    bubbles: [],
    clicked_sizes: [],
    state: "RUNNING",
    start_time: now,
    end_time: null,
    result_display_until: 0,
    result_logged: false,
  };

  for (let i = 0; i < 5; i++) {
    const radius = radii[i]; // pick distinct fixed size
    const color_name =
      COLOR_NAMES[Math.floor(Math.random() * COLOR_NAMES.length)];

    // NON-OVERLAPPING placement
    let x, y;
    let safe = false;
    let attempts = 0;

    while (!safe && attempts < 200) {
      attempts++;
      x = 40 + radius + Math.random() * (WIDTH - 80 - 2 * radius);
      y =
        HUD_HEIGHT +
        40 +
        radius +
        Math.random() * (HEIGHT - HUD_HEIGHT - 100 - 2 * radius);

      safe = true;
      for (const b of gameState.bubbles) {
        const dx = x - b.x;
        const dy = y - b.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < radius + b.radius + 12) {
          safe = false;
          break;
        }
      }
    }

    gameState.bubbles.push(new Bubble(i + 1, x, y, radius, color_name));
  }

  console.log("Generated radii:", radii);
  return gameState;
}

function handleClick(mx, my) {
  if (game.state != "RUNNING") return;

  let clicked = null;
  for (const b of game.bubbles) {
    if (b.isClicked(mx, my)) {
      clicked = b;
      break;
    }
  }

  // no bubble hit -> empty click
  if (!clicked) {
    logEvent("empty_click", { mx, my });
    return;
  }

  const size = clicked.radius;
  const prev = game.clicked_sizes.length
    ? game.clicked_sizes[game.clicked_sizes.length - 1]
    : null;

  let is_correct = true;

  if (prev !== null) {
    if (game.instruction.direction == "ascending" && size <= prev) {
      is_correct = false;
    }
    if (game.instruction.direction == "descending" && size >= prev) {
      is_correct = false;
    }
  }

  // log the bubble click for fingerprinting
  logEvent("bubble_click", {
    mx,
    my,
    bubble_id: clicked.id,
    bubble_color: clicked.color_name,
    bubble_size: clicked.radius,
    bubble_center: [clicked.x, clicked.y],
    clicked_so_far: [...game.clicked_sizes],
    is_correct,
  });

  // game logic
  if (!is_correct) {
    game.state = "FAILED";
    game.end_time = performance.now() / 1000;
    clicked.alive = false;
    return;
  }

  game.clicked_sizes.push(size);
  clicked.alive = false;

  if (game.clicked_sizes.length >= game.instruction.count) {
    game.state = "PASSED";
    game.end_time = performance.now() / 1000;
  }
}

function drawBackground() {
  const grd = ctx.createLinearGradient(0, 0, 0, HEIGHT);
  grd.addColorStop(0, "rgb(" + BG_TOP.join(",") + ")");
  grd.addColorStop(1, "rgb(" + BG_BOTTOM.join(",") + ")");
  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
}

function drawHUD() {
  ctx.fillStyle = `rgb(${HUD_BG.join(",")})`;
  ctx.strokeStyle = `rgb(${HUD_BORDER.join(",")})`;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(10, 6, WIDTH - 20, HUD_HEIGHT, 10);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = TEXT_PRIMARY;
  ctx.font = "bold 18px Arial";
  ctx.fillText("Bubble Human Check", 20, 24);
  ctx.font = "13px Arial";
  ctx.fillText(game.instruction.text, 20, 46);

  const now = performance.now() / 1000;
  const timeLeft = Math.max(0, MAX_DURATION - (now - game.start_time));
  ctx.fillStyle = `rgb(${TIME_BAR_BG.join(",")})`;
  ctx.fillRect(10, HEIGHT - 18, WIDTH - 20, 8);
  ctx.fillStyle = `rgb(${TIME_BAR_FILL.join(",")})`;
  ctx.fillRect(10, HEIGHT - 18, (WIDTH - 20) * (timeLeft / MAX_DURATION), 8);
}

function drawResult() {
  if (game.state != "PASSED" && game.state != "FAILED") return;
  const text = game.state == "PASSED" ? "CAPTCHA PASSED!" : "CAPTCHA FAILED!";
  const color = game.state == "PASSED" ? SUCCESS_COLOR : FAIL_COLOR;
  ctx.fillStyle = "white";
  ctx.fillRect(0, HEIGHT - 42, WIDTH, 24);
  ctx.strokeStyle = "rgb(200,200,200)";
  ctx.beginPath();
  ctx.moveTo(0, HEIGHT - 42);
  ctx.lineTo(WIDTH, HEIGHT - 42);
  ctx.stroke();

  ctx.fillStyle = color;
  ctx.font = "16px Arial";
  const metrics = ctx.measureText(text);
  ctx.fillText(text, (WIDTH - metrics.width) / 2, HEIGHT - 24);
}

canvas.addEventListener("mousemove", (e) => {
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  logEvent("move", { mx, my });
});

canvas.addEventListener("click", (e) => {
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  handleClick(mx, my);
});

game = initGame();

let lastTime = performance.now() / 1000;

function sendFingerprintToServer(events, features, classification, meta) {
  fetch("/log_fingerprint", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      events,
      features,
      classification,
      ...meta,
    }),
  }).catch((err) => {
    console.error("Failed to log fingerprint:", err);
  });
}

function loop() {
  const now = performance.now() / 1000;
  const dt = now - lastTime;
  lastTime = now;

  if (game.state == "RUNNING") {
    if (
      now - game.start_time > MAX_DURATION &&
      game.clicked_sizes.length < game.instruction.count
    ) {
      game.state = "FAILED";
      game.end_time = now;
    }
    for (const b of game.bubbles) {
      b.move(dt);
    }
  }

  drawBackground();
  drawHUD();
  for (const b of game.bubbles) {
    b.draw(ctx);
  }
  drawResult();

  if (game.state == "PASSED" || game.state == "FAILED") {
    if (!game.result_logged) {
      game.result_logged = true;
      game.result_display_until = now + RESULT_DISPLAY_TIME;

      // mark end of session for fingerprinting
      logEvent("captcha_result", {
        result: game.state,
        clicked_sizes: [...game.clicked_sizes],
        attempts,
      });
      logEvent("session_end");
    } else if (now >= game.result_display_until) {
      // === FINGERPRINTING: compute features + classification ===
      const features = computeFeaturesFromEvents(events);
      const classification = classifyFingerprint(
        features,
        game.state === "PASSED"
      );

      // === METADATA for logging ===
      const captchaPassed = game.state === "PASSED";
      const isHuman = !!classification.is_human;
      const finalAllowed = captchaPassed && isHuman; // only true in the “real human + correct” case
      const attemptIndex = attempts + 1;            // this run is the (attempts+1)-th attempt

      // send to backend file with metadata
      sendFingerprintToServer(events, features, classification, {
        captcha_passed: captchaPassed,
        final_allowed: finalAllowed,
        attempt_index: attemptIndex,
      });

      // Helper: notify parent window & close popup
      function finishAndClose(passed) {
        try {
          if (
            window.opener &&
            !window.opener.closed &&
            typeof window.opener.onCaptchaResult === "function"
          ) {
            window.opener.onCaptchaResult({ passed });
          }
        } catch (e) {
          console.error("Error notifying opener:", e);
        }
        window.close();
      }

      // ───────── CASE 1: correct bubbles + human-like behaviour ─────────
      if (game.state === "PASSED" && isHuman) {
        //alert("CAPTCHA Passed! Human verified, you may proceed.");
        finishAndClose(true);
        return;
      }

      // ───────── CASE 2: wrong bubbles (any behaviour) ─────────
      if (game.state === "FAILED") {
        attempts++;
        if (attempts <= 2) {
          // allow retry for normal mistakes
          game = initGame();
          lastTime = performance.now() / 1000;
        } else {
          // final fail after max attempts
          //alert("CAPTCHA Failed. Try again later.");
          finishAndClose(false);
          return;
        }
        // no return here -> let the loop continue and draw the new game
      }

      // ───────── CASE 3: PASSED but classified as bot ─────────
      // (correct bubbles + non-human behaviour)
      if (game.state === "PASSED" && !isHuman) {
        //alert("CAPTCHA Failed. Try again later.");
        finishAndClose(false);
        return;
      }
    }
  }

  requestAnimationFrame(loop);
}

loop();
