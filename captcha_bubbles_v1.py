import pygame
import random
import sys
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict

pygame.init()

WIDTH, HEIGHT = 600, 350
FPS = 60

MAX_DURATION = 20.0 

TOTAL_SPAWNS = 18
MIN_SPAWN_INTERVAL = 0.8
MAX_SPAWN_INTERVAL = 1.3
MAX_SIMULTANEOUS_BUBBLES = 5

MIN_SPEED = 20
MAX_SPEED = 35
MAX_RETRIES = 2
RESULT_DISPLAY_TIME = 1.2

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

COLOR_MAP = {
    "BLUE":   (80, 160, 255),
    "RED":    (230, 80, 80),
    "GREEN":  (80, 200, 120),
    "YELLOW": (240, 220, 80),
    "ORANGE": (245, 170, 80),
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
    spawn_side: str = "left"
    spawn_time: float = 0.0
    age: float = 0.0
    wiggle_amp: float = 0.0
    wiggle_freq: float = 0.0
    wiggle_axis: str = "y"

    def move(self, dt: float):
        if not self.alive:
            return

        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt

        # Wiggle removed: bubbles move along straight paths using vx/vy only.

        if (self.x < -self.radius or
            self.x > WIDTH + self.radius or
            self.y < -self.radius or
            self.y > HEIGHT + self.radius):
            self.alive = False

    def draw(self, surface: pygame.Surface):
        if not self.alive:
            return
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, (0, 0, 0, 40), (int(self.x), int(self.y)), self.radius, 1)

    def is_clicked(self, mx: int, my: int) -> bool:
        if not self.alive:
            return False
        dx = mx - self.x
        dy = my - self.y
        return dx * dx + dy * dy <= self.radius * self.radius


@dataclass
class Instruction:
    text: str
    # ordering task: how many to burst and direction ('ascending' or 'descending')
    count: int
    direction: str


@dataclass
class GameState:
    instruction: Instruction
    bubbles: List[Bubble] = field(default_factory=list)
    # sizes clicked so far (in order)
    clicked_sizes: List[int] = field(default_factory=list)
    state: str = "RUNNING"
    start_time: float = 0.0
    end_time: Optional[float] = None

    next_spawn_at: float = 0.0
    last_bubble_id: int = 0
    spawn_plan: List[Dict[str, int]] = field(default_factory=list)
    spawn_index: int = 0

    events: List[dict] = field(default_factory=list)
    # timestamp until which the result banner should remain visible
    result_display_until: float = 0.0
    # whether we've already logged the final result for this attempt
    result_logged: bool = False

    def log_event(self, event_type: str, **kwargs):
        self.events.append({"type": event_type, **kwargs})


def generate_instruction() -> Instruction:
    # Create an ordering task: burst N bubbles in ascending/descending order of size
    count = random.choice([2, 3])
    direction = random.choice(["ascending", "descending"])
    text = f"Burst {count} bubbles in {direction} order of size."
    return Instruction(text=text, count=count, direction=direction)


def make_spawn_plan(instr: Instruction) -> List[Dict[str, int]]:
    # Create exactly 5 bubbles, each with a unique color and unique radius
    num_bubbles = 5
    colors = random.sample(COLOR_NAMES, num_bubbles)
    # sample unique radii with at least 10px gap between any two
    min_radius = 16
    max_radius = 56
    min_gap = 10

    radii: List[int] = []
    attempts = 0
    max_attempts = 1000
    while len(radii) < num_bubbles and attempts < max_attempts:
        attempts += 1
        r = random.randint(min_radius, max_radius)
        ok = True
        for ex in radii:
            if abs(r - ex) < min_gap:
                ok = False
                break
        if ok:
            radii.append(r)

    # If unable to find a full set due to randomness, fall back to evenly spaced radii
    if len(radii) < num_bubbles:
        span = max_radius - min_radius
        step = max(min_gap, span // (num_bubbles - 1))
        radii = [min_radius + i * step for i in range(num_bubbles)]

    plan: List[Dict[str, int]] = []
    for c, r in zip(colors, radii):
        plan.append({"color": c, "radius": r})
    return plan


def spawn_bubble(game: GameState, now: float) -> None:
    if game.spawn_index >= len(game.spawn_plan):
        return

    plan_entry = game.spawn_plan[game.spawn_index]
    color_name = plan_entry["color"]
    color = COLOR_MAP[color_name]
    radius = plan_entry["radius"]

    margin_x = 70
    margin_y = HUD_HEIGHT + 20  
    min_gap = 10

    side = random.choice(["left", "right", "top", "bottom"])

    max_attempts = 15
    for _ in range(max_attempts):
        if side == "left":
            x = -radius
            y = random.randint(margin_y, HEIGHT - 40)
            vx = random.uniform(MIN_SPEED, MAX_SPEED)
            vy = random.uniform(-20, 20)
            wiggle_axis = "y"
        elif side == "right":
            x = WIDTH + radius
            y = random.randint(margin_y, HEIGHT - 40)
            vx = -random.uniform(MIN_SPEED, MAX_SPEED)
            vy = random.uniform(-20, 20)
            wiggle_axis = "y"
        elif side == "top":
            x = random.randint(margin_x, WIDTH - margin_x)
            y = HUD_HEIGHT + 20 - radius
            vx = random.uniform(-20, 20)
            vy = random.uniform(MIN_SPEED, MAX_SPEED)
            wiggle_axis = "x"
        else:
            x = random.randint(margin_x, WIDTH - margin_x)
            y = HEIGHT - 40 + radius
            vx = random.uniform(-20, 20)
            vy = -random.uniform(MIN_SPEED, MAX_SPEED)
            wiggle_axis = "x"

        overlaps = False
        for b in game.bubbles:
            if not b.alive:
                continue
            dx = x - b.x
            dy = y - b.y
            dist_sq = dx * dx + dy * dy
            min_dist = radius + b.radius + min_gap
            if dist_sq < min_dist * min_dist:
                overlaps = True
                break
        if not overlaps:
            break

    bubble_id = game.last_bubble_id + 1
    game.last_bubble_id = bubble_id
    game.spawn_index += 1

    wiggle_amp = random.uniform(15, 25)
    wiggle_freq = random.uniform(2.0, 3.5)

    bubble = Bubble(
        id=bubble_id,
        x=x,
        y=y,
        radius=radius,
        color_name=color_name,
        color=color,
        vx=vx,
        vy=vy,
        spawn_side=side,
        spawn_time=now,
        wiggle_amp=wiggle_amp,
        wiggle_freq=wiggle_freq,
        wiggle_axis=wiggle_axis,
    )
    game.bubbles.append(bubble)


def maybe_spawn_bubbles(game: GameState, now: float):
    if game.state != "RUNNING":
        return

    elapsed = now - game.start_time
    if elapsed > MAX_DURATION:
        return

    alive_count = sum(1 for b in game.bubbles if b.alive)
    if alive_count >= MAX_SIMULTANEOUS_BUBBLES:
        return

    if game.spawn_index >= len(game.spawn_plan):
        return

    if now >= game.next_spawn_at:
        spawn_bubble(game, now)
        interval = random.uniform(MIN_SPAWN_INTERVAL, MAX_SPAWN_INTERVAL)
        game.next_spawn_at = now + interval


def init_game() -> GameState:
    instruction = generate_instruction()
    spawn_plan = make_spawn_plan(instruction)
    start_time = pygame.time.get_ticks() / 1000.0
    game = GameState(
        instruction=instruction,
        start_time=start_time,
        next_spawn_at=start_time,
        spawn_plan=spawn_plan,
    )

    # Spawn all planned bubbles immediately so all are visible when the CAPTCHA loads.
    # We call spawn_bubble repeatedly; spawn_bubble will attempt to place bubbles without overlap.
    while game.spawn_index < len(game.spawn_plan):
        spawn_bubble(game, start_time)

    return game


def handle_click(game: GameState, mx: int, my: int, now: float):
    if game.state != "RUNNING":
        return

    clicked_bubble = None
    for b in game.bubbles:
        if b.is_clicked(mx, my):
            clicked_bubble = b
            break

    if clicked_bubble is None:
        game.log_event("empty_click", time=now, mx=mx, my=my)
        return

    size = clicked_bubble.radius

    game.log_event(
        "bubble_click",
        time=now,
        mx=mx,
        my=my,
        bubble_id=clicked_bubble.id,
        bubble_color=clicked_bubble.color_name,
        bubble_size=size,
        clicked_so_far=game.clicked_sizes,
    )
    # Check ordering rule: for ascending, each click must be strictly larger than previous;
    # for descending, strictly smaller.
    prev = game.clicked_sizes[-1] if game.clicked_sizes else None

    if prev is not None:
        if game.instruction.direction == "ascending":
            if size <= prev:
                game.state = "FAILED"
                game.end_time = now
                clicked_bubble.alive = False
                return
        else:  # descending
            if size >= prev:
                game.state = "FAILED"
                game.end_time = now
                clicked_bubble.alive = False
                return

    # correct click: accept and record
    clicked_bubble.alive = False
    game.clicked_sizes.append(size)

    if len(game.clicked_sizes) >= game.instruction.count:
        game.state = "PASSED"
        game.end_time = now


def draw_text_center(surface, text, font, color, x, y):
    img = font.render(text, True, color)
    rect = img.get_rect(center=(x, y))
    surface.blit(img, rect)


def draw_text_left(surface, text, font, color, x, y):
    img = font.render(text, True, color)
    rect = img.get_rect(topleft=(x, y))
    surface.blit(img, rect)


def draw_background(surface: pygame.Surface):
    for i in range(HEIGHT):
        t = i / HEIGHT
        r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
        pygame.draw.line(surface, (r, g, b), (0, i), (WIDTH, i))


def draw_hud(surface: pygame.Surface, game: GameState, now: float):
    hud_rect = pygame.Rect(10, 6, WIDTH - 20, HUD_HEIGHT)
    pygame.draw.rect(surface, HUD_BG, hud_rect, border_radius=10)
    pygame.draw.rect(surface, HUD_BORDER, hud_rect, width=1, border_radius=10)

    draw_text_left(
        surface,
        "Bubble Human Check",
        FONT_TITLE,
        TEXT_PRIMARY,
        hud_rect.x + 10,
        hud_rect.y + 4,
    )

    draw_text_left(
        surface,
        game.instruction.text,
        FONT_SMALL,
        TEXT_PRIMARY,
        hud_rect.x + 10,
        hud_rect.y + 26,
    )
    # Legend removed for accessibility; HUD shows instruction only.

    time_left = max(0.0, MAX_DURATION - (now - game.start_time))
    bar_rect = pygame.Rect(10, HEIGHT - 18, WIDTH - 20, 8)
    pygame.draw.rect(surface, TIME_BAR_BG, bar_rect, border_radius=4)
    ratio = max(0.0, min(1.0, time_left / MAX_DURATION))
    if ratio > 0:
        fill_width = int(bar_rect.width * ratio)
        fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, fill_width, bar_rect.height)
        pygame.draw.rect(surface, TIME_BAR_FILL, fill_rect, border_radius=4)


def draw_result_banner(surface: pygame.Surface, state: str):
    if state == "PASSED":
        text = "CAPTCHA PASSED - close window."
        color = SUCCESS_COLOR
    else:
        text = "CAPTCHA FAILED - close window."
        color = FAIL_COLOR

    banner_rect = pygame.Rect(0, HEIGHT - 42, WIDTH, 24)
    pygame.draw.rect(surface, (255, 255, 255, 230), banner_rect)
    pygame.draw.line(surface, (220, 220, 230), (0, banner_rect.top), (WIDTH, banner_rect.top))
    draw_text_center(surface, text, FONT, color, WIDTH // 2, banner_rect.centery)


def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Anti-AI Bubble CAPTCHA")
    clock = pygame.time.Clock()

    game = init_game()
    attempts = 0
    running = True
    last_time = pygame.time.get_ticks() / 1000.0

    play_rect = pygame.Rect(
        10,
        HUD_HEIGHT + 12,
        WIDTH - 20,
        HEIGHT - (HUD_HEIGHT + 12) - 40,
    )

    while running:
        now = pygame.time.get_ticks() / 1000.0
        dt = now - last_time
        last_time = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # Exit quietly when window is closed by the user
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                handle_click(game, mx, my, now)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and game.state != "RUNNING":
                    # manual retry
                    game = init_game()
                    last_time = pygame.time.get_ticks() / 1000.0
                    continue
            # terminal-state handling (PASS/FAIL) is managed after drawing so a banner can be shown

        if game.state == "RUNNING":
            elapsed = now - game.start_time
            # If time runs out and required clicks haven't been made, retry or exit
            if elapsed > MAX_DURATION and len(game.clicked_sizes) < game.instruction.count:
                # mark as failed; logging and retry will be handled after showing the banner
                game.state = "FAILED"
                game.end_time = now

            maybe_spawn_bubbles(game, now)
            for b in game.bubbles:
                b.move(dt)

            # terminal-state handling (PASS/FAIL) happens after drawing so a banner is shown

        draw_background(screen)
        draw_hud(screen, game, now)

        pygame.draw.rect(screen, WHITE, play_rect, border_radius=12)
        pygame.draw.rect(screen, HUD_BORDER, play_rect, width=1, border_radius=12)

        for b in game.bubbles:
            b.draw(screen)
        # If terminal state reached, ensure we log it and set up a short display window
        if game.state in ("PASSED", "FAILED") and not game.result_logged:
            game.end_time = now
            game.result_display_until = now + RESULT_DISPLAY_TIME
            game.result_logged = True
            game.log_event(
                "captcha_result",
                time=now,
                result=game.state,
                attempts=attempts,
                clicked_sizes=list(game.clicked_sizes),
            )

        if game.state in ("PASSED", "FAILED"):
            draw_result_banner(screen, game.state)

        pygame.display.flip()
        clock.tick(FPS)

        # After showing the banner for a short time, either retry or exit
        if game.state in ("PASSED", "FAILED") and now >= game.result_display_until:
            if game.state == "PASSED":
                pygame.quit()
                sys.exit()
            else:
                attempts += 1
                if attempts <= MAX_RETRIES:
                    game = init_game()
                    last_time = pygame.time.get_ticks() / 1000.0
                    continue
                else:
                    pygame.quit()
                    sys.exit()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
