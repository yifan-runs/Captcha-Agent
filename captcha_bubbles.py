# need to limit number of retries to 3, also keep track of failed attempts DONE
# need the bubbles to be burst in a specific order (largest to smallest) DONE
# --- maybe we can add different such orders for more complexity

import pygame
import random
import sys

pygame.init()

# Window settings
WIDTH, HEIGHT = 500, 300
FPS = 60
NUM_BUBBLES = 4
SPEED = 1.2

MAX_RETRIES = 3
failed_attempts = 0

# Colors
WHITE = (255, 255, 255)

# Distinct bubble colors (RGBA)
BUBBLE_COLORS = [
    (0, 102, 255),     # Blue
    (255, 0, 0),       # Red
    (0, 200, 0),       # Green
    (255, 165, 0)      # Orange
]


class Bubble:
    def __init__(self, x, y, radius, color):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color

        self.vx = random.uniform(-SPEED, SPEED)
        self.vy = random.uniform(-SPEED, SPEED)

        self.alive = True
        self.fading = False
        self.alpha = 255

    def move(self):
        if not self.alive or self.fading:
            return

        self.x += self.vx
        self.y += self.vy

        if (self.x < -self.radius or self.x > WIDTH + self.radius or
            self.y < -self.radius or self.y > HEIGHT + self.radius):
            self.respawn()

    def start_fade(self):
        self.fading = True

    def respawn(self):
        edge = random.choice(["left", "right", "top", "bottom"])

        if edge == "left":
            self.x = -self.radius
            self.y = random.randint(0, HEIGHT)
            self.vx = random.uniform(0.2, SPEED)
            self.vy = random.uniform(-SPEED, SPEED)

        elif edge == "right":
            self.x = WIDTH + self.radius
            self.y = random.randint(0, HEIGHT)
            self.vx = random.uniform(-SPEED, -0.2)
            self.vy = random.uniform(-SPEED, SPEED)

        elif edge == "top":
            self.x = random.randint(0, WIDTH)
            self.y = -self.radius
            self.vx = random.uniform(-SPEED, SPEED)
            self.vy = random.uniform(0.2, SPEED)

        elif edge == "bottom":
            self.x = random.randint(0, WIDTH)
            self.y = HEIGHT + self.radius
            self.vx = random.uniform(-SPEED, -0.2)

    def draw(self, surface):
        if not self.alive:
            return

        if self.fading:
            self.alpha -= 10
            if self.alpha <= 0:
                self.alive = False
                return

        bubble_surf = pygame.Surface((self.radius*2+4, self.radius*2+4), pygame.SRCALPHA)
        pygame.draw.circle(
            bubble_surf,
            (*self.color, self.alpha),
            (self.radius+2, self.radius+2),
            self.radius,
            width=3
        )

        surface.blit(bubble_surf, (self.x - self.radius - 2, self.y - self.radius - 2))

    def is_clicked(self, pos):
        if not self.alive or self.fading:
            return False
        px, py = pos
        return ((self.x - px)**2 + (self.y - py)**2)**0.5 <= self.radius


def create_instruction_image():
    """Creates a rendered text surface so the instruction cannot be copied."""
    font = pygame.font.SysFont("arial", 22, bold=True)
    text = "Burst bubbles in DESCENDING SIZE order"
    surface = font.render(text, True, (0, 0, 0))
    return surface


def main():
    global failed_attempts

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Bubble CAPTCHA")

    clock = pygame.time.Clock()

    # Sizes largest → smallest
    base_size = 60
    step = 15
    sizes = [base_size - i * step for i in range(NUM_BUBBLES)]

    # Required pop order
    expected_order = sizes[:]
    expected_index = 0

    instruction_img = create_instruction_image()
    instruction_rect = instruction_img.get_rect(center=(WIDTH//2, 20))

    def reset_bubbles():
        return [
            Bubble(
                random.randint(50, WIDTH - 50),
                random.randint(50, HEIGHT - 50),
                sizes[i],
                BUBBLE_COLORS[i]
            )
            for i in range(NUM_BUBBLES)
        ]

    bubbles = reset_bubbles()

    running = True
    while running:
        screen.fill(WHITE)
        screen.blit(instruction_img, instruction_rect)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                for bubble in bubbles:
                    if bubble.is_clicked(event.pos):

                        # Check order requirement
                        if bubble.radius == expected_order[expected_index]:
                            bubble.start_fade()
                            expected_index += 1

                            if expected_index == NUM_BUBBLES:
                                print("CAPTCHA PASSED")
                                pygame.display.flip()
                                pygame.time.delay(800)
                                running = False

                        else:
                            failed_attempts += 1
                            print(f"WRONG BUBBLE — Attempt {failed_attempts}/{MAX_RETRIES}")

                            if failed_attempts >= MAX_RETRIES:
                                print("CAPTCHA FAILED — Too many attempts")
                                pygame.time.delay(800)
                                running = False
                            else:
                                expected_index = 0
                                bubbles = reset_bubbles()

                        break

        for bubble in bubbles:
            bubble.move()
            bubble.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
