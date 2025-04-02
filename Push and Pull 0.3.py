import pygame
import math
import sys
import random
import colorsys

# === INITIALIZATION ===
pygame.init()
info = pygame.display.Info()
WIDTH, HEIGHT = info.current_w, info.current_h
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
clock = pygame.time.Clock()

# === WORLD SETTINGS ===
WORLD_WIDTH = 5000
WORLD_HEIGHT = 4000
CEILING_Y = 0
FLOOR_Y = WORLD_HEIGHT

# === GAME STATE FLAGS ===
paused = True
game_over = False
victory = False
rainbow_mode = False
rainbow_triggered = False
rainbow_hue = 0

# === PULL MECHANIC ===
PULL_MAX = 4.0
PULL_RECHARGE_TIME = 2.0
pull_remaining = PULL_MAX
pulling = False

# === COLORS ===
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
GOLD = (255, 215, 0)
GRAY = (100, 100, 100)
SILVER = (192, 192, 192)

# === PLAYER STATE ===
def reset_player():
    return [WORLD_WIDTH // 2, 100], [0, 0]

player_pos, player_vel = reset_player()
gravity = 0.5

# === ROPE / SWING MECHANICS ===
anchor_point = None
anchor_global_pos = None
rope_length = 0
swinging = False
min_rope_length = 50
selected_anchor = None
selected_anchor_global_pos = None

# === ANCHORS ===
def generate_anchors():
    return [{'x': random.randint(0, WORLD_WIDTH),
             'y': random.randint(100, WORLD_HEIGHT - 300),
             'time': 5.0, 'cooldown': 0.0, 'used': False} for _ in range(10)]

anchor_points = generate_anchors()

# === CAMERA ===
camera_offset = [0, 0]

# === UTILITIES ===
def hsv_color(hue, s=1.0, v=1.0):
    rgb = colorsys.hsv_to_rgb(hue % 1.0, s, v)
    return tuple(int(c * 255) for c in rgb)

def dynamic_color(base):
    return hsv_color(rainbow_hue) if rainbow_mode else base

# === DRAWING HELPERS ===
def draw_rope(start, end):
    pygame.draw.line(screen, dynamic_color(SILVER), start, end, 2)

def draw_dotted_line(start, end, color, segment_length=10):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.hypot(dx, dy)
    steps = int(dist // segment_length)
    for i in range(0, steps, 2):
        t1 = i / steps
        t2 = (i + 1) / steps
        x1 = start[0] + dx * t1
        y1 = start[1] + dy * t1
        x2 = start[0] + dx * t2
        y2 = start[1] + dy * t2
        pygame.draw.line(screen, color, (x1, y1), (x2, y2), 2)

def count_remaining_anchors():
    return sum(1 for anchor in anchor_points if anchor['time'] > 0)

# === DRAW FUNCTIONS ===
def draw_anchors():
    tile_range = 2
    player_tile = int(player_pos[0] // WORLD_WIDTH)
    font = pygame.font.SysFont(None, 24)

    for tile in range(player_tile - tile_range, player_tile + tile_range + 1):
        offset_x = tile * WORLD_WIDTH
        for anchor in anchor_points:
            world_x = anchor['x'] + offset_x
            y = anchor['y']
            screen_x = world_x - camera_offset[0]
            screen_y = y - camera_offset[1]

            if -100 <= screen_x <= WIDTH + 100:
                if anchor['time'] <= 0:
                    color = GRAY
                elif anchor['cooldown'] > 0:
                    color = RED
                else:
                    color = dynamic_color(GOLD)

                pygame.draw.circle(screen, color, (int(screen_x), int(screen_y)), 10)

                if anchor['time'] > 0 and anchor['cooldown'] == 0:
                    secs = int(anchor['time'])
                    timer_text = font.render(str(secs), True, WHITE)
                    screen.blit(timer_text, (screen_x - timer_text.get_width() // 2, screen_y - 25))

def draw_boundaries():
    pygame.draw.rect(screen, dynamic_color(WHITE), (0, -camera_offset[1], WIDTH, 10))
    pygame.draw.rect(screen, dynamic_color(RED), (0, FLOOR_Y - camera_offset[1], WIDTH, 10))

def draw_minimap():
    minimap_w, minimap_h = 250, 200
    minimap = pygame.Surface((minimap_w, minimap_h), pygame.SRCALPHA)
    minimap.fill((0, 0, 0, 100))
    scale_x = minimap_w / WORLD_WIDTH
    scale_y = minimap_h / WORLD_HEIGHT

    for anchor in anchor_points:
        ax = int(anchor['x'] * scale_x)
        ay = int(anchor['y'] * scale_y)
        if anchor['time'] <= 0:
            color = GRAY
        elif anchor['cooldown'] > 0:
            color = RED
        else:
            color = GOLD
        pygame.draw.circle(minimap, color, (ax, ay), 3)

    px = int((player_pos[0] % WORLD_WIDTH) * scale_x)
    py = int(player_pos[1] * scale_y)
    pygame.draw.circle(minimap, WHITE, (px, py), 4)
    screen.blit(minimap, (WIDTH - minimap_w - 20, 20))

def apply_camera_follow():
    cam_speed = 0.05
    target_x = player_pos[0] - WIDTH // 2
    target_y = player_pos[1] - HEIGHT // 2
    camera_offset[0] += (target_x - camera_offset[0]) * cam_speed
    camera_offset[1] += (target_y - camera_offset[1]) * cam_speed

def count_remaining_anchors():
    return sum(1 for anchor in anchor_points if anchor['time'] > 0)

def update_targeting():
    global selected_anchor, selected_anchor_global_pos
    selected_anchor = None
    selected_anchor_global_pos = None

    mx, my = pygame.mouse.get_pos()
    mouse_world = (mx + camera_offset[0], my + camera_offset[1])

    vx = mouse_world[0] - player_pos[0]
    vy = mouse_world[1] - player_pos[1]
    v_len = math.hypot(vx, vy)
    if v_len == 0:
        return
    vx /= v_len
    vy /= v_len

    best_direct = None
    best_direct_dist = float('inf')
    best_mouse = None
    best_mouse_dist = float('inf')

    for tile in range(-1, 2):
        offset_x = tile * WORLD_WIDTH
        for anchor in anchor_points:
            if anchor['time'] <= 0 or anchor['cooldown'] > 0:
                continue

            ax = anchor['x'] + offset_x
            ay = anchor['y']
            dx = ax - player_pos[0]
            dy = ay - player_pos[1]
            dist_to_player = math.hypot(dx, dy)
            if dist_to_player > 1500:
                continue

            proj_len = dx * vx + dy * vy
            if proj_len >= 0:
                closest_x = player_pos[0] + proj_len * vx
                closest_y = player_pos[1] + proj_len * vy
                perp_dist = math.hypot(ax - closest_x, ay - closest_y)

                if perp_dist <= 30 and dist_to_player < best_direct_dist:
                    best_direct = (anchor, (ax, ay))
                    best_direct_dist = dist_to_player

            dist_to_mouse = math.hypot(mouse_world[0] - ax, mouse_world[1] - ay)
            if dist_to_mouse < best_mouse_dist:
                best_mouse = (anchor, (ax, ay))
                best_mouse_dist = dist_to_mouse

    if best_direct:
        selected_anchor, selected_anchor_global_pos = best_direct
    elif best_mouse:
        selected_anchor, selected_anchor_global_pos = best_mouse

def draw_targeting():
    if selected_anchor and not swinging:
        start = (player_pos[0] - camera_offset[0], player_pos[1] - camera_offset[1])
        end = (selected_anchor_global_pos[0] - camera_offset[0], selected_anchor_global_pos[1] - camera_offset[1])
        draw_dotted_line(start, end, dynamic_color(SILVER))

# === MAIN GAME LOOP ===
while True:
    dt = clock.get_time() / 1000
    screen.fill(BLACK)

    update_targeting()

    # --- INPUT EVENTS ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.MOUSEBUTTONDOWN and not paused and not game_over and not victory:
            if selected_anchor:
                anchor_point = selected_anchor
                anchor_global_pos = selected_anchor_global_pos
                dx = anchor_global_pos[0] - player_pos[0]
                dy = anchor_global_pos[1] - player_pos[1]
                rope_length = math.hypot(dx, dy)
                swinging = True

        if event.type == pygame.MOUSEBUTTONUP and not paused:
            swinging = False
            if anchor_point:
                anchor_point['time'] = float(max(0, math.floor(anchor_point['time'])))
                if anchor_point['time'] > 0:
                    anchor_point['cooldown'] = 3.0
                anchor_point = None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_s:
                if game_over or victory:
                    player_pos, player_vel = reset_player()
                    swinging = False
                    anchor_point = None
                    game_over = False
                    victory = False
                    pull_remaining = PULL_MAX
                    rainbow_mode = False
                    rainbow_triggered = False
                    anchor_points = generate_anchors()
                else:
                    paused = not paused
            elif event.key == pygame.K_d and (game_over or victory):
                pygame.quit()
                sys.exit()

    # --- INPUT STATE ---
    keys = pygame.key.get_pressed()
    pulling = keys[pygame.K_SPACE] and pull_remaining > 0

    # --- GAME LOGIC ---
    if not paused and not game_over and not victory:
        player_vel[1] += gravity
        player_pos[0] += player_vel[0]
        player_pos[1] += player_vel[1]

        if not rainbow_triggered and math.hypot(*player_vel) > 100:
            rainbow_mode = True
            rainbow_triggered = True

        if player_pos[1] > FLOOR_Y:
            game_over = True
            paused = True

        if player_pos[1] < CEILING_Y:
            player_pos[1] = CEILING_Y
            player_vel[1] = 0

        if pulling:
            pull_remaining = max(0.0, pull_remaining - dt)
        else:
            pull_remaining = min(PULL_MAX, pull_remaining + (PULL_MAX / PULL_RECHARGE_TIME) * dt)

        for anchor in anchor_points:
            if anchor['cooldown'] > 0:
                anchor['cooldown'] = max(0.0, anchor['cooldown'] - dt)

        if swinging and anchor_point:
            dx = anchor_global_pos[0] - player_pos[0]
            dy = anchor_global_pos[1] - player_pos[1]
            dist = math.hypot(dx, dy)
            if dist == 0: dist = 0.001
            norm_x = dx / dist
            norm_y = dy / dist

            if pulling and rope_length > min_rope_length:
                rope_length -= 2
                scale = dist / rope_length
                player_vel[0] *= scale
                player_vel[1] *= scale

            player_pos[0] = anchor_global_pos[0] - norm_x * rope_length
            player_pos[1] = anchor_global_pos[1] - norm_y * rope_length

            dot = player_vel[0] * norm_x + player_vel[1] * norm_y
            player_vel[0] -= norm_x * dot
            player_vel[1] -= norm_y * dot

            anchor_point['time'] = max(0.0, anchor_point['time'] - dt)
            if anchor_point['time'] <= 0:
                swinging = False
                anchor_point = None

        if not victory and count_remaining_anchors() == 0:
            victory = True
            paused = True

    # --- CAMERA ---
    apply_camera_follow()

    # --- DRAWING ---
    draw_boundaries()
    draw_anchors()
    draw_targeting()

    if swinging and anchor_global_pos:
        start = (anchor_global_pos[0] - camera_offset[0], anchor_global_pos[1] - camera_offset[1])
        end = (player_pos[0] - camera_offset[0], player_pos[1] - camera_offset[1])
        draw_rope(start, end)

    screen_x = int(player_pos[0] - camera_offset[0])
    screen_y = int(player_pos[1] - camera_offset[1])
    pygame.draw.circle(screen, dynamic_color(WHITE), (screen_x, screen_y), 10)

    draw_minimap()

    # Pull bar
    bar_x, bar_y = 30, 30
    bar_width, bar_height = 200, 20
    fill = int((pull_remaining / PULL_MAX) * bar_width)
    pygame.draw.rect(screen, dynamic_color(WHITE), (bar_x, bar_y, bar_width, bar_height), 2)
    pygame.draw.rect(screen, dynamic_color(SILVER), (bar_x, bar_y, fill, bar_height))
    label = pygame.font.SysFont(None, 24).render("PULL", True, dynamic_color(WHITE))
    screen.blit(label, (bar_x, bar_y - 22))

    remaining = count_remaining_anchors()
    counter_text = pygame.font.SysFont(None, 32).render(f"Anchors Remaining: {remaining}", True, dynamic_color(WHITE))
    screen.blit(counter_text, (30, 60))

    font = pygame.font.SysFont(None, 48)
    if paused and not game_over and not victory:
        text = font.render("Press S to Play/Pause", True, dynamic_color(WHITE))
        screen.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
    elif game_over:
        text = font.render("Game Over! Press S to Restart or D to Quit", True, dynamic_color(WHITE))
        screen.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
    elif victory:
        text = font.render("Victory! Press S to Restart or D to Quit", True, dynamic_color(WHITE))
        screen.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
        if rainbow_mode:
            love_font = pygame.font.SysFont(None, 72)
            love = love_font.render("J <3 E", True, (255, 105, 180))
            screen.blit(love, love.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 60)))

    if rainbow_mode:
        rainbow_hue += dt * 0.2

    pygame.display.flip()
    clock.tick(60)
