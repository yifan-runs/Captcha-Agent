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

MIN_SPEED = 40
MAX_SPEED = 70

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

        wiggle = math.sin(self.age * self.wiggle_freq) * self.wiggle_amp * dt
        if self.wiggle_axis == "x":
            self.x += wiggle
        else:
            self.y += wiggle

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
    targets: Dict[str, int]


@dataclass
class GameState:
    instruction: Instruction
    bubbles: List[Bubble] = field(default_factory=list)
    correct_hits: Dict[str, int] = field(default_factory=dict)
    state: str = "RUNNING"
    start_time: float = 0.0
    end_time: Optional[float] = None

    next_spawn_at: float = 0.0
    last_bubble_id: int = 0
    spawn_plan: List[str] = field(default_factory=list)
    spawn_index: int = 0

    events: List[dict] = field(default_factory=list)

    def log_event(self, event_type: str, **kwargs):
        self.events.append({"type": event_type, **kwargs})


def generate_instruction() -> Instruction:
    mode = random.choice(["single", "double"])

    if mode == "single":
        color = random.choice(COLOR_NAMES)
        count = random.choice([2, 3])
        targets = {color: count}
        text = f"Burst exactly {count} {color} bubble"
        if count > 1:
            text += "s"
        text += ". Do NOT burst any other color."
        return Instruction(text=text, targets=targets)

    c1, c2 = random.sample(COLOR_NAMES, 2)
    targets = {c1: 1, c2: 1}
    text = f"Burst exactly 1 {c1} and 1 {c2} bubble. Do NOT burst any other color."
    return Instruction(text=text, targets=targets)


def make_spawn_plan(instr: Instruction) -> List[str]:
    PRE_DECOYS = 3

    remaining_slots = TOTAL_SPAWNS
    target_colors = list(instr.targets.keys())
    target_pool: List[str] = []
    decoy_pool: List[str] = []

    for color, required in instr.targets.items():
        base = required + 2
        base = min(base, remaining_slots)
        target_pool.extend([color] * base)
        remaining_slots -= base
        if remaining_slots <= 0:
            break

    non_target_colors = [c for c in COLOR_NAMES if c not in instr.targets]
    for _ in range(remaining_slots):
        if non_target_colors:
            decoy_pool.append(random.choice(non_target_colors))
        else:
            decoy_pool.append(random.choice(target_colors))

    plan: List[str] = []
    last_was_target = False

    while target_pool or decoy_pool:
        idx = len(plan)

        if idx < PRE_DECOYS and decoy_pool:
            c = decoy_pool.pop(random.randrange(len(decoy_pool)))
            plan.append(c)
            last_was_target = False
            continue

        if last_was_target and decoy_pool:
            c = decoy_pool.pop(random.randrange(len(decoy_pool)))
            plan.append(c)
            last_was_target = False
            continue

        if target_pool:
            c = target_pool.pop(random.randrange(len(target_pool)))
            plan.append(c)
            last_was_target = True
        elif decoy_pool:
            c = decoy_pool.pop(random.randrange(len(decoy_pool)))
            plan.append(c)
            last_was_target = False
        else:
            break

    return plan


def spawn_bubble(game: GameState, now: float) -> None:
    if game.spawn_index >= len(game.spawn_plan):
        return

    color_name = game.spawn_plan[game.spawn_index]
    color = COLOR_MAP[color_name]
    radius = random.randint(20, 26)

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
    correct_hits = {c: 0 for c in instruction.targets.keys()}
    return GameState(
        instruction=instruction,
        correct_hits=correct_hits,
        start_time=start_time,
        next_spawn_at=start_time,
        spawn_plan=spawn_plan,
    )


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

    color = clicked_bubble.color_name

    game.log_event(
        "bubble_click",
        time=now,
        mx=mx,
        my=my,
        bubble_id=clicked_bubble.id,
        bubble_color=color,
        targets=game.instruction.targets,
    )

    if color not in game.instruction.targets:
        game.state = "FAILED"
        game.end_time = now
        clicked_bubble.alive = False
        return

    if game.correct_hits[color] >= game.instruction.targets[color]:
        game.state = "FAILED"
        game.end_time = now
        clicked_bubble.alive = False
        return

    game.correct_hits[color] += 1
    clicked_bubble.alive = False

    if all(game.correct_hits[c] == req for c, req in game.instruction.targets.items()):
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

    chip_x = hud_rect.right - 8
    chip_y = hud_rect.y + 10
    for color_name, required in game.instruction.targets.items():
        label = f"{required}x {color_name}"
        color = COLOR_MAP[color_name]
        chip_x -= 80
        pygame.draw.circle(surface, color, (chip_x + 10, chip_y + 10), 8)
        pygame.draw.circle(surface, (0, 0, 0, 40), (chip_x + 10, chip_y + 10), 8, 1)
        draw_text_left(
            surface,
            label,
            FONT_SMALL,
            TEXT_SECONDARY,
            chip_x + 24,
            chip_y + 2,
        )

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
                running = False
                game.state = "FAILED"
                game.end_time = now
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                handle_click(game, mx, my, now)

        if game.state == "RUNNING":
            elapsed = now - game.start_time
            if elapsed > MAX_DURATION and not all(
                game.correct_hits[c] == req for c, req in game.instruction.targets.items()
            ):
                game.state = "FAILED"
                game.end_time = now

            maybe_spawn_bubbles(game, now)
            for b in game.bubbles:
                b.move(dt)

        draw_background(screen)
        draw_hud(screen, game, now)

        pygame.draw.rect(screen, WHITE, play_rect, border_radius=12)
        pygame.draw.rect(screen, HUD_BORDER, play_rect, width=1, border_radius=12)

        for b in game.bubbles:
            b.draw(screen)

        if game.state in ("PASSED", "FAILED"):
            draw_result_banner(screen, game.state)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()

