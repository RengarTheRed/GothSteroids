#!/usr/bin/env python3
"""Asteroids Clone with Goth Girl Asteroids and Heart Bullets

Features:
- Floaty, inertia‑based movement for the player ship.
- Asteroids are represented by "goth girl" sprites that drift and rotate.
- Player fires heart‑shaped bullets.
- Screen‑wrap for all objects.
- Simple scoring and game‑over handling.

Dependencies:
    pip install pygame

Assets (place in an `assets/` folder next to this script):
    - ship.png          – your normal ship sprite (any size ~64x64)
    - goth_girl.png     – asteroid sprite (generated image)
    - heart.png         – bullet sprite (generated image)
"""

import math
import random
import sys
from pathlib import Path

import pygame

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Asset paths (relative to this script)
ASSET_DIR = Path(__file__).parent / "assets"
SHIP_IMG = ASSET_DIR / "ship.png"
ASTEROID_IMG = ASSET_DIR / "goth_girl.png"
HEART_IMG = ASSET_DIR / "heart.png"

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
def wrap_position(pos: pygame.math.Vector2) -> pygame.math.Vector2:
    """Wrap a position around the screen edges (toroidal space)."""
    x, y = pos.x % SCREEN_WIDTH, pos.y % SCREEN_HEIGHT
    return pygame.math.Vector2(x, y)

def angle_to_vector(angle_deg: float) -> pygame.math.Vector2:
    """Convert an angle in degrees to a normalized direction vector."""
    rad = math.radians(angle_deg)
    return pygame.math.Vector2(math.cos(rad), -math.sin(rad))

# ------------------------------------------------------------
# Game objects
# ------------------------------------------------------------
class GameObject(pygame.sprite.Sprite):
    def __init__(self, image_path: Path, pos: pygame.math.Vector2, velocity: pygame.math.Vector2 = None, angle: float = 0, image: pygame.Surface = None):
        super().__init__()
        if image:
            self.original_image = image
        else:
            self.original_image = pygame.image.load(str(image_path)).convert_alpha()
            # Hack: If the image has a solid background (e.g. generated JPG/PNG without alpha), make it transparent.
            # We assume the top-left pixel is the background color.
            if self.original_image.get_at((0, 0))[3] == 255:  # If top-left is fully opaque
                bg_color = self.original_image.get_at((0, 0))
                self.original_image.set_colorkey(bg_color)
        
        # Ensure passed-in images also get this treatment if needed
        if image:
             if image.get_at((0, 0))[3] == 255:
                image.set_colorkey(image.get_at((0, 0)))
             self.original_image = image

        self.image = self.original_image
        self.rect = self.image.get_rect(center=pos)
        self.pos = pygame.math.Vector2(pos)
        self.velocity = velocity if velocity else pygame.math.Vector2(0, 0)
        self.angle = angle  # degrees
        self.rotation_speed = 0  # degrees per frame (optional)

    def update(self):
        # Apply rotation if needed
        if self.rotation_speed:
            self.angle = (self.angle + self.rotation_speed) % 360
            self.image = pygame.transform.rotate(self.original_image, self.angle)
            self.rect = self.image.get_rect(center=self.rect.center)
        # Move
        self.pos += self.velocity
        self.pos = wrap_position(self.pos)
        self.rect.center = self.pos

class Player(GameObject):
    def __init__(self, pos: pygame.math.Vector2):
        # Load and scale ship
        original = pygame.image.load(str(SHIP_IMG)).convert_alpha()
        target_size = 60
        aspect = original.get_width() / original.get_height()
        new_w = target_size
        new_h = int(target_size / aspect)
        image = pygame.transform.smoothscale(original, (new_w, new_h))
        
        super().__init__(SHIP_IMG, pos, image=image)
        self.thrust = 0.15  # acceleration per frame when thrusting
        self.max_speed = 6
        self.rotation_speed = 0  # player does not rotate automatically
        self.angle = 0  # facing upward initially (0 deg points up)
        self.image = pygame.transform.rotate(self.original_image, self.angle)
        self.rect = self.image.get_rect(center=pos)
        self.last_shot_time = 0
        self.shot_cooldown = 250  # milliseconds

    def handle_input(self, keys, dt):
        # Rotation (left/right arrows)
        if keys[pygame.K_LEFT]:
            self.angle = (self.angle + 180 * dt) % 360  # rotate left
        if keys[pygame.K_RIGHT]:
            self.angle = (self.angle - 180 * dt) % 360  # rotate right
        # Apply thrust (up arrow)
        if keys[pygame.K_UP]:
            direction = angle_to_vector(self.angle)
            self.velocity += direction * self.thrust
            # Clamp speed
            if self.velocity.length() > self.max_speed:
                self.velocity.scale_to_length(self.max_speed)
        # Friction – subtle floaty drift
        self.velocity *= 0.99
        # Update image orientation
        self.image = pygame.transform.rotate(self.original_image, self.angle)
        self.rect = self.image.get_rect(center=self.rect.center)

    def can_shoot(self, current_time):
        return current_time - self.last_shot_time >= self.shot_cooldown

    def shoot(self, current_time):
        self.last_shot_time = current_time
        direction = angle_to_vector(self.angle)
        bullet_vel = direction * 10 + self.velocity  # inherit ship momentum
        bullet_pos = self.pos + direction * (self.rect.width // 2)
        return Bullet(bullet_pos, bullet_vel)

class Asteroid(GameObject):
    def __init__(self, pos: pygame.math.Vector2, size: int = 3):
        # Size 3 = large, 2 = medium, 1 = small
        base_size = 100  # pixels
        scale_mult = {3: 1.0, 2: 0.6, 1: 0.35}[size]
        target_size = int(base_size * scale_mult)
        
        # Load and scale image
        original = pygame.image.load(str(ASTEROID_IMG)).convert_alpha()
        # Scale preserving aspect ratio
        aspect = original.get_width() / original.get_height()
        new_w = target_size
        new_h = int(target_size / aspect)
        image = pygame.transform.smoothscale(original, (new_w, new_h))
        
        # Random velocity
        angle = random.uniform(0, 360)
        speed = random.uniform(0.5, 2.0) / size  # smaller asteroids move faster
        velocity = angle_to_vector(angle) * speed
        super().__init__(Path(''), pos, velocity, angle=0, image=image)
        self.rect = self.image.get_rect(center=pos)
        self.size = size
        self.rotation_speed = random.uniform(-1, 1)  # slow spin

    def break_apart(self):
        """Return a list of smaller asteroids (if any)."""
        if self.size <= 1:
            return []
        new_size = self.size - 1
        fragments = []
        for _ in range(2):
            fragment = Asteroid(self.pos, new_size)
            fragments.append(fragment)
        return fragments

class Bullet(GameObject):
    def __init__(self, pos: pygame.math.Vector2, velocity: pygame.math.Vector2):
        # Scale bullet
        original = pygame.image.load(str(HEART_IMG)).convert_alpha()
        target_size = 25
        image = pygame.transform.smoothscale(original, (target_size, target_size))
        super().__init__(HEART_IMG, pos, velocity, image=image)
        self.lifetime = 2000  # ms
        self.spawn_time = pygame.time.get_ticks()

    def update(self):
        super().update()
        # Remove after lifetime expires
        if pygame.time.get_ticks() - self.spawn_time > self.lifetime:
            self.kill()

# ------------------------------------------------------------
# Game States
# ------------------------------------------------------------
class GameState:
    START = "start"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"

# ------------------------------------------------------------
# Helper functions for screens
# ------------------------------------------------------------
def draw_text_centered(screen, text, font, color, y_offset=0):
    """Draw text centered on screen."""
    surf = font.render(text, True, color)
    rect = surf.get_rect(center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + y_offset))
    screen.blit(surf, rect)
    return rect

def draw_start_screen(screen, title_font, font):
    """Draw the start screen."""
    screen.fill((10, 10, 30))
    
    # Title
    draw_text_centered(screen, "ASTEROIDS", title_font, (255, 100, 150), -80)
    draw_text_centered(screen, "Goth Girls Edition", font, (200, 150, 200), -30)
    
    # Instructions
    draw_text_centered(screen, "Arrow Keys to Move | Space to Shoot", font, (150, 150, 150), 40)
    draw_text_centered(screen, "ESC to Pause", font, (150, 150, 150), 70)
    
    # Start prompt (blinking effect)
    if (pygame.time.get_ticks() // 500) % 2 == 0:
        draw_text_centered(screen, "Press SPACE to Start", font, (255, 255, 255), 130)

def draw_pause_screen(screen, font):
    """Draw pause overlay."""
    # Semi-transparent overlay
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    screen.blit(overlay, (0, 0))
    
    draw_text_centered(screen, "PAUSED", font, (255, 255, 255), -20)
    draw_text_centered(screen, "Press ESC to Resume", font, (200, 200, 200), 20)

def draw_game_over_screen(screen, title_font, font, score):
    """Draw game over screen."""
    screen.fill((10, 10, 30))
    
    draw_text_centered(screen, "GAME OVER", title_font, (255, 50, 50), -60)
    draw_text_centered(screen, f"Final Score: {score}", font, (255, 255, 255), 0)
    
    draw_text_centered(screen, "Press R to Restart", font, (100, 255, 100), 60)
    draw_text_centered(screen, "Press Q to Quit", font, (255, 100, 100), 100)

def reset_game(all_sprites, asteroids, bullets):
    """Reset game state for a new game."""
    all_sprites.empty()
    asteroids.empty()
    bullets.empty()
    
    # Create player
    player = Player(pygame.math.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2))
    all_sprites.add(player)
    
    # Spawn initial asteroids with safe zone
    for _ in range(5):
        min_dist = 200
        while True:
            pos = pygame.math.Vector2(random.randrange(SCREEN_WIDTH), random.randrange(SCREEN_HEIGHT))
            if pos.distance_to(player.pos) > min_dist:
                break
        asteroid = Asteroid(pos, size=3)
        all_sprites.add(asteroid)
        asteroids.add(asteroid)
    
    return player, 0  # Return player and reset score

# ------------------------------------------------------------
# Main game loop
# ------------------------------------------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Asteroids – Goth Girls Edition")
    clock = pygame.time.Clock()

    # Fonts
    font = pygame.font.SysFont("Arial", 24)
    title_font = pygame.font.SysFont("Arial", 48, bold=True)

    # Sprite groups
    all_sprites = pygame.sprite.Group()
    asteroids = pygame.sprite.Group()
    bullets = pygame.sprite.Group()

    # Initialize game
    player, score = reset_game(all_sprites, asteroids, bullets)
    
    # Game state
    state = GameState.START
    
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                # Handle input based on game state
                if state == GameState.START:
                    if event.key == pygame.K_SPACE:
                        state = GameState.PLAYING
                
                elif state == GameState.PLAYING:
                    if event.key == pygame.K_SPACE:
                        now = pygame.time.get_ticks()
                        if player.can_shoot(now):
                            bullet = player.shoot(now)
                            all_sprites.add(bullet)
                            bullets.add(bullet)
                    elif event.key == pygame.K_ESCAPE:
                        state = GameState.PAUSED
                
                elif state == GameState.PAUSED:
                    if event.key == pygame.K_ESCAPE:
                        state = GameState.PLAYING
                
                elif state == GameState.GAME_OVER:
                    if event.key == pygame.K_r:
                        # Restart game
                        player, score = reset_game(all_sprites, asteroids, bullets)
                        state = GameState.PLAYING
                    elif event.key == pygame.K_q:
                        running = False

        # Update logic (only when playing)
        if state == GameState.PLAYING:
            keys = pygame.key.get_pressed()
            player.handle_input(keys, dt)
            all_sprites.update()

            # Collision: bullet hits asteroid
            hits = pygame.sprite.groupcollide(bullets, asteroids, True, False)
            for bullet, hit_asteroids in hits.items():
                for asteroid in hit_asteroids:
                    fragments = asteroid.break_apart()
                    asteroid.kill()
                    for frag in fragments:
                        all_sprites.add(frag)
                        asteroids.add(frag)
                    score += 10 * asteroid.size

            # Collision: asteroid hits player
            if pygame.sprite.spritecollideany(player, asteroids):
                state = GameState.GAME_OVER

        # Drawing
        if state == GameState.START:
            draw_start_screen(screen, title_font, font)
        
        elif state == GameState.PLAYING:
            screen.fill((10, 10, 30))
            all_sprites.draw(screen)
            score_surf = font.render(f"Score: {score}", True, (255, 255, 255))
            screen.blit(score_surf, (10, 10))
            # Show pause hint
            pause_hint = font.render("ESC to Pause", True, (100, 100, 100))
            screen.blit(pause_hint, (SCREEN_WIDTH - 140, 10))
        
        elif state == GameState.PAUSED:
            # Draw game state underneath
            screen.fill((10, 10, 30))
            all_sprites.draw(screen)
            score_surf = font.render(f"Score: {score}", True, (255, 255, 255))
            screen.blit(score_surf, (10, 10))
            # Draw pause overlay
            draw_pause_screen(screen, font)
        
        elif state == GameState.GAME_OVER:
            draw_game_over_screen(screen, title_font, font, score)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
