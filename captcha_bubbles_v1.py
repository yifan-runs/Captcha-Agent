#!/usr/bin/env python3
import pygame
import random
import sys
import math
import json
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict

# fingerprinting module
import fingerprinting_v3

pygame.init()

WIDTH, HEIGHT = 600, 350
FPS = 60

MAX_DURATION = 20.0
RESULT_DISPLAY_TIME = 1.5

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

COLOR_MAP = {
    "BLUE":      (80, 160, 255),
    "RED":       (230, 70, 70),
    "GREEN":     (50, 200, 110),
    "YELLOW":    (255, 235, 80),
    "ORANGE":    (255, 165, 50),
    "PURPLE":    (160, 100, 255),
    "PINK":      (255, 140, 200),
    "CYAN":      (80, 255, 255),
    "MAGENTA":   (255, 80, 180),
    "LIME":      (180, 255, 80),
}

COLOR_NAMES = list(COLOR_MAP.keys())

BG_TOP = (230, 240, 255)
BG_BOTTOM = (245, 250, 255)
HUD_BG = (255, 255, 255)
HUD_BORDER = (205, 215, 235)
TEXT_PRIMARY = (40, 50, 80)
TEXT_SECONDARY = (90, 100, 130)
SUCCESS_COLOR = (0, 150, 80)
FAIL_COLOR = (200, 50, 50)
TIME_BAR_BG = (220, 230, 245)
TIME_BAR_FILL = (80, 140, 255)

HUD_HEIGHT = 56

FONT_TITLE = pygame.font.SysFont("arial", 18, bold=True)
FONT = pygame.font.SysFont("arial", 16)
FONT_SMALL = pygame.font.SysFont("arial", 13)

MIN_SPEED = 15
MAX_SPEED = 35
MIN_DIFF = 6  # Minimum size difference between bubbles

def random_velocity():
    """Generate a random velocity for bubbles that have already entered the scene."""
    vx = 0.0
    vy = 0.0
    while abs(vx) < 5 and abs(vy) < 5:
        vx = random.uniform(-MAX_SPEED, MAX_SPEED)
        vy = random.uniform(-MAX_SPEED, MAX_SPEED)
    return vx, vy


@dataclass
class Bubble:
    id: int
    x: float
    y: float
    radius: int
    color_name: str
    color: Tuple[int, int, int]
    vx: float
    vy: float
    alive: bool = True

    def move(self, dt: float):
        if not self.alive:
            return

        self.x += self.vx * dt
        self.y += self.vy * dt

        # If bubble exits the screen — instantly respawn on a new side (so it re-enters quickly)
        if (self.x < -self.radius or
            self.x > WIDTH + self.radius or
            self.y < -self.radius or
            self.y > HEIGHT + self.radius):

            side = random.choice(["left", "right", "top", "bottom"])

            if side == "left":
                self.x = -self.radius - 20
                self.y = random.randint(HUD_HEIGHT + 30, HEIGHT - 40)
            elif side == "right":
                self.x = WIDTH + self.radius + 20
                self.y = random.randint(HUD_HEIGHT + 30, HEIGHT - 40)
            elif side == "top":
                self.x = random.randint(50, WIDTH - 50)
                self.y = HUD_HEIGHT - self.radius - 20
            else:
                self.x = random.randint(50, WIDTH - 50)
                self.y = HEIGHT + self.radius + 20

            # New velocity aimed roughly inward (less center gravity)
            cx, cy = WIDTH // 2, (HEIGHT + HUD_HEIGHT) // 2
            dx = cx - self.x
            dy = cy - self.y
            dist = math.hypot(dx, dy) or 1.0
            dx /= dist
            dy /= dist

            # Add angular noise (reduces center pull)
            angle = math.atan2(dy, dx)
            noise = random.uniform(-1.0, 1.0)
            angle += noise

            speed = random.uniform(40, 80)
            self.vx = math.cos(angle) * speed
            self.vy = math.sin(angle) * speed


    def draw(self, surface: pygame.Surface):
        if not self.alive:
            return
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
        # soft outline
        pygame.draw.circle(surface, (0, 0, 0), (int(self.x), int(self.y)), self.radius, 1)

    def is_clicked(self, mx: int, my: int) -> bool:
        dx = mx - self.x
        dy = my - self.y
        return dx * dx + dy * dy <= (self.radius * self.radius)


@dataclass
class Instruction:
    text: str
    count: int
    direction: str


@dataclass
class GameState:
    instruction: Instruction
    bubbles: List[Bubble] = field(default_factory=list)
    clicked_sizes: List[int] = field(default_factory=list)
    state: str = "RUNNING"
    start_time: float = 0.0
    end_time: Optional[float] = None
    result_display_until: float = 0.0
    result_logged: bool = False

    events: List[dict] = field(default_factory=list)

    def log_event(self, event_type: str, **kwargs):
        # include timestamp automatically if not provided
        if "time" not in kwargs:
            kwargs["time"] = pygame.time.get_ticks() / 1000.0
        self.events.append({"type": event_type, **kwargs})


def generate_instruction() -> Instruction:
    count = random.choice([2, 3])
    direction = random.choice(["ascending", "descending"])
    return Instruction(
        text=f"Burst any {count} bubbles in {direction} order of size.",
        count=count,
        direction=direction
    )


def init_game() -> GameState:
    instruction = generate_instruction()
    start_time = pygame.time.get_ticks() / 1000.0

    game = GameState(
        instruction=instruction,
        start_time=start_time,
    )

    # Fingerprinting: mark session start and instruction time
    game.log_event("session_start", time=start_time)
    game.log_event("instruction_shown", time=start_time, text=instruction.text)

    CENTER_X = WIDTH // 2
    CENTER_Y = (HEIGHT + HUD_HEIGHT) // 2

    # Spawn 5 bubbles immediately OUTSIDE the frame but aimed inward, with unique radii and colors
    for i in range(5):
        # Ensure radii are not too close to each other
        while True:
            radius = random.randint(20, 70)
            too_close = False
            for b in game.bubbles:
                if abs(radius - b.radius) < MIN_DIFF:
                    too_close = True
                    break
            if not too_close:
                break

        color_name = COLOR_NAMES[i % len(COLOR_NAMES)]
        color = COLOR_MAP[color_name]

        side = random.choice(["left", "right", "top", "bottom"])

        if side == "left":
            x = -radius - 30
            y = random.randint(HUD_HEIGHT + 10, HEIGHT - 10)

        elif side == "right":
            x = WIDTH + radius + 30
            y = random.randint(HUD_HEIGHT + 10, HEIGHT - 10)

        elif side == "top":
            x = random.randint(20, WIDTH - 20)
            y = random.randint(-radius - 40, HUD_HEIGHT - radius - 5)

        else:  # bottom
            x = random.randint(20, WIDTH - 20)
            y = random.randint(HEIGHT + radius + 10, HEIGHT + radius + 40)


        # Velocity aimed directly toward the center so they enter quickly
        dx = CENTER_X - x
        dy = CENTER_Y - y
        dist = math.hypot(dx, dy) or 1.0
        dx /= dist
        dy /= dist

        speed = random.uniform(80, 140)  # fast entry speed
        vx = dx * speed
        vy = dy * speed

        bubble = Bubble(i + 1, x, y, radius, color_name, color, vx, vy)
        game.bubbles.append(bubble)

    return game


def handle_click(game: GameState, mx: int, my: int, now: float):
    if game.state != "RUNNING":
        return

    clicked_bubble = None
    for b in game.bubbles:
        if b.is_clicked(mx, my) and b.alive:
            clicked_bubble = b
            break

    if not clicked_bubble:
        # empty click logged
        game.log_event("empty_click", mx=mx, my=my)
        return

    size = clicked_bubble.radius
    prev = game.clicked_sizes[-1] if game.clicked_sizes else None

    # Determine correctness according to ordering rule
    is_correct_click = True
    if prev is not None:
        if game.instruction.direction == "ascending":
            if size <= prev:
                is_correct_click = False
        else:  # descending
            if size >= prev:
                is_correct_click = False

    # Log click with extra info for fingerprinting
    game.log_event(
        "bubble_click",
        mx=mx,
        my=my,
        bubble_id=clicked_bubble.id,
        bubble_color=clicked_bubble.color_name,
        bubble_size=size,
        clicked_so_far=list(game.clicked_sizes),
        bubble_center=(clicked_bubble.x, clicked_bubble.y),
        is_correct=is_correct_click,
    )

    if not is_correct_click:
        game.state = "FAILED"
        game.end_time = now
        clicked_bubble.alive = False
        return

    # correct click
    clicked_bubble.alive = False
    game.clicked_sizes.append(size)

    if len(game.clicked_sizes) >= game.instruction.count:
        game.state = "PASSED"
        game.end_time = now


def draw_background(surface):
    for i in range(HEIGHT):
        t = i / HEIGHT
        r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
        pygame.draw.line(surface, (r, g, b), (0, i), (WIDTH, i))


def draw_hud(surface, game, now):
    hud_rect = pygame.Rect(10, 6, WIDTH - 20, HUD_HEIGHT)
    pygame.draw.rect(surface, HUD_BG, hud_rect, border_radius=10)
    pygame.draw.rect(surface, HUD_BORDER, hud_rect, width=1, border_radius=10)

    txt = "Bubble Human Check"
    img = FONT_TITLE.render(txt, True, TEXT_PRIMARY)
    surface.blit(img, (hud_rect.x + 10, hud_rect.y + 4))

    img2 = FONT_SMALL.render(game.instruction.text, True, TEXT_PRIMARY)
    surface.blit(img2, (hud_rect.x + 10, hud_rect.y + 26))

    time_left = max(0.0, MAX_DURATION - (now - game.start_time))
    bar_rect = pygame.Rect(10, HEIGHT - 18, WIDTH - 20, 8)
    pygame.draw.rect(surface, TIME_BAR_BG, bar_rect, border_radius=4)
    fill_width = int(bar_rect.width * (time_left / MAX_DURATION))
    pygame.draw.rect(surface, TIME_BAR_FILL, (bar_rect.x, bar_rect.y, fill_width, 8), border_radius=4)


def draw_result_banner(surface, state):
    if state == "PASSED":
        text = "CAPTCHA PASSED - close window."
        color = SUCCESS_COLOR
    else:
        text = "CAPTCHA FAILED - close window."
        color = FAIL_COLOR

    banner_rect = pygame.Rect(0, HEIGHT - 42, WIDTH, 24)
    pygame.draw.rect(surface, WHITE, banner_rect)
    pygame.draw.line(surface, (200, 200, 200), (0, banner_rect.top), (WIDTH, banner_rect.top))
    img = FONT.render(text, True, color)
    surface.blit(img, (WIDTH // 2 - img.get_width() // 2, banner_rect.centery - img.get_height() // 2))


def save_fingerprint_json(game: GameState, features: Optional[dict], classification: Optional[dict], filename="fingerprint.json"):
    out = {
        "events": game.events,
        "features": features,
        "classification": classification,
    }
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"[FINGERPRINT] saved to {filename}")
    except Exception as e:
        print("[FINGERPRINT] failed to save fingerprint.json:", e)


def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Anti-AI Bubble CAPTCHA")
    clock = pygame.time.Clock()

    game = init_game()
    attempts = 0

    play_rect = pygame.Rect(10, HUD_HEIGHT + 12, WIDTH - 20, HEIGHT - (HUD_HEIGHT + 12) - 40)

    running = True
    last_time = pygame.time.get_ticks() / 1000.0

    while running:
        now = pygame.time.get_ticks() / 1000.0
        dt = now - last_time
        last_time = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # mark session end, save fingerprint, then quit
                game.log_event("session_end", time=now)
                try:
                    features = fingerprinting_v2.compute_features_from_events(game.events)
                    classification = fingerprinting_v2.classify_fingerprint(features, captcha_passed=(game.state == "PASSED"))
                except Exception as e:
                    print("[FINGERPRINT] compute/classify failed on quit:", e)
                    features = None
                    classification = None
                save_fingerprint_json(game, features, classification)
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEMOTION and game.state == "RUNNING":
                mx, my = event.pos
                # log movement events (timestamped automatically inside log_event)
                game.log_event("move", mx=mx, my=my)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                handle_click(game, mx, my, now)

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and game.state != "RUNNING":
                    # manual retry
                    game = init_game()
                    last_time = pygame.time.get_ticks() / 1000.0
                    continue

        if game.state == "RUNNING":
            if (now - game.start_time) > MAX_DURATION and len(game.clicked_sizes) < game.instruction.count:
                game.state = "FAILED"
                game.end_time = now

            for b in game.bubbles:
                b.move(dt)

        draw_background(screen)
        draw_hud(screen, game, now)

        pygame.draw.rect(screen, WHITE, play_rect, border_radius=12)
        pygame.draw.rect(screen, HUD_BORDER, play_rect, width=1, border_radius=12)

        for b in game.bubbles:
            b.draw(screen)

        # terminal-state handling: set up banner display and logging once
        if game.state in ("PASSED", "FAILED") and not game.result_logged:
            game.end_time = now
            game.result_display_until = now + RESULT_DISPLAY_TIME
            game.result_logged = True

            # log captcha_result and session_end for fingerprinting
            game.log_event("captcha_result", result=game.state, attempts=attempts, clicked_sizes=list(game.clicked_sizes))
            game.log_event("session_end", time=now)

        if game.state in ("PASSED", "FAILED"):
            draw_result_banner(screen, game.state)

        pygame.display.flip()
        clock.tick(FPS)

        # After showing the banner for a short time, compute fingerprint features/classify and either retry or exit
        if game.state in ("PASSED", "FAILED") and now >= game.result_display_until:
            # compute features + classification (wrapped)
            features = None
            classification = None
            try:
                features = fingerprinting_v2.compute_features_from_events(game.events)
                classification = fingerprinting_v2.classify_fingerprint(
                    features,
                    captcha_passed=(game.state == "PASSED"),
                )
            except Exception as e:
                print("[FINGERPRINT] compute/classify failed:", e)

            # print features & classification
            print("\n=== FINGERPRINT FEATURES ===")
            if features:
                for k, v in features.items():
                    print(f"{k:30s}: {v}")
            else:
                print("(no features)")

            print("=== CLASSIFICATION ===")
            if classification is not None:
                print(classification)
            else:
                print("(no classification)")

            # save fingerprint.json (events + features + classification if present)
            save_fingerprint_json(game, features, classification)

            if game.state == "PASSED":
                pygame.quit()
                sys.exit()
            else:
                attempts += 1
                if attempts <= 2:
                    game = init_game()
                    last_time = pygame.time.get_ticks() / 1000.0
                    continue
                pygame.quit()
                sys.exit()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
