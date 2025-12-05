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

MIN_SPEED = 25
MAX_SPEED = 40


def random_velocity():
    """Generate a random velocity for respawned bubbles."""
    vx = 0
    vy = 0
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

        # If bubble exits the screen — instantly respawn on a new side
        if (self.x < -self.radius or
            self.x > WIDTH + self.radius or
            self.y < -self.radius or
            self.y > HEIGHT + self.radius):

            side = random.choice(["left", "right", "top", "bottom"])

            if side == "left":
                self.x = -self.radius
                self.y = random.randint(HUD_HEIGHT + 30, HEIGHT - 40)
            elif side == "right":
                self.x = WIDTH + self.radius
                self.y = random.randint(HUD_HEIGHT + 30, HEIGHT - 40)
            elif side == "top":
                self.x = random.randint(50, WIDTH - 50)
                self.y = HUD_HEIGHT + 10 - self.radius
            else:
                self.x = random.randint(50, WIDTH - 50)
                self.y = HEIGHT - 10 + self.radius

            # New velocity
            self.vx, self.vy = random_velocity()

    def draw(self, surface: pygame.Surface):
        if not self.alive:
            return
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, (0, 0, 0, 40), (int(self.x), int(self.y)), self.radius, 1)

    def is_clicked(self, mx: int, my: int) -> bool:
        dx = mx - self.x
        dy = my - self.y
        return dx * dx + dy * dy <= self.radius * self.radius


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
        self.events.append({"type": event_type, **kwargs})


def generate_instruction() -> Instruction:
    count = random.choice([2, 3])
    direction = random.choice(["ascending", "descending"])
    return Instruction(
        text=f"Burst {count} bubbles in {direction} order of size.",
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

    # Spawn 5 bubbles immediately
    for i in range(5):
        radius = random.randint(20, 55)
        color_name = random.choice(COLOR_NAMES)
        color = COLOR_MAP[color_name]

        # Spawn fully inside play_rect region
        x = random.randint(40 + radius, WIDTH - 40 - radius)
        y = random.randint(HUD_HEIGHT + 40 + radius, HEIGHT - 60 - radius)

        vx, vy = random_velocity()

        bubble = Bubble(i + 1, x, y, radius, color_name, color, vx, vy)
        game.bubbles.append(bubble)


    return game


def handle_click(game: GameState, mx: int, my: int, now: float):
    if game.state != "RUNNING":
        return

    clicked_bubble = None
    for b in game.bubbles:
        if b.is_clicked(mx, my):
            clicked_bubble = b
            break

    if not clicked_bubble:
        return

    size = clicked_bubble.radius

    prev = game.clicked_sizes[-1] if game.clicked_sizes else None

    if prev is not None:
        if game.instruction.direction == "ascending" and size <= prev:
            game.state = "FAILED"
            game.end_time = now
            clicked_bubble.alive = False
            return
        if game.instruction.direction == "descending" and size >= prev:
            game.state = "FAILED"
            game.end_time = now
            clicked_bubble.alive = False
            return

    game.clicked_sizes.append(size)
    clicked_bubble.alive = False

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
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                handle_click(game, mx, my, now)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                if game.state != "RUNNING":
                    game = init_game()

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

        if game.state in ("PASSED", "FAILED") and not game.result_logged:
            game.result_logged = True
            game.result_display_until = now + RESULT_DISPLAY_TIME

        if game.state in ("PASSED", "FAILED"):
            draw_result_banner(screen, game.state)

        pygame.display.flip()
        clock.tick(FPS)

        if game.state in ("PASSED", "FAILED") and now >= game.result_display_until:
            if game.state == "PASSED":
                pygame.quit()
                sys.exit(0)
            else:
                attempts += 1
                if attempts <= 2:
                    game = init_game()
                    last_time = pygame.time.get_ticks() / 1000.0
                    continue
                pygame.quit()
                sys.exit(1)


if __name__ == "__main__":
    main()
