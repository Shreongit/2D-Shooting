# ultimate_house_shooter.py
# Full single-file 2D tactical shooter with houses (one entry / exit), cover, day/night, AI, particles.
# Save as ultimate_house_shooter.py
# Requires: pygame (pip install pygame)
# Run: python ultimate_house_shooter.py

import pygame, sys, random, math, time
from pygame.math import Vector2

# -------------------------
# CONFIGURABLE SETTINGS
# -------------------------
SCREEN_W, SCREEN_H = 1200, 720
WORLD_W, WORLD_H = 3000, 2000
FPS = 60

# Player
PLAYER_MAX_HEALTH = 130
PLAYER_LIVES = 5
PLAYER_ACCEL = 3000.0
PLAYER_MAX_SPEED = 320.0
PLAYER_SPRINT_MULT = 1.45
PLAYER_FRICTION = 2600.0
PLAYER_RESPAWN_POS = Vector2(300, WORLD_H - 200)

# Weapons
WEAPONS = {
    'rifle':  { 'name':'Rifle',  'damage':28, 'rpm':520, 'spread':2.2, 'speed':950,  'mag':30, 'reload':1.8 },
    'smg':    { 'name':'SMG',    'damage':14, 'rpm':950, 'spread':6.0, 'speed':1020, 'mag':40, 'reload':1.6 },
    'shotgun':{ 'name':'Shotgun','damage':10, 'rpm':380, 'spread':18,  'speed':780,  'mag':6,  'reload':2.4, 'pellets':8 }
}

# Enemy
ENEMY_BASE_HP = 180
ENEMY_BASE_SPEED = 120.0
ENEMY_DETECT_RADIUS = 520
ENEMY_FIRE_COOLDOWN = 0.9
ENEMY_BULLET_SPEED = 390
ENEMY_DAMAGE = 18

# Visuals
DAY_BG = (110, 170, 255)
NIGHT_BG = (8, 12, 32)
COVER_COLOR = (90, 90, 90)
GRID_COLOR = (24,24,24)

TOTAL_LEVELS = 10
BOSS_LEVELS = [5, 10]

# Misc
PARTICLE_GRAVITY = 200.0

# -------------------------
# Utilities
# -------------------------
def clamp(v, a, b): return max(a, min(v, b))

def rect_line_intersect(rect, a, b):
    try:
        return bool(rect.clipline(a, b))
    except Exception:
        return False

def line_blocked(a, b, obstacles):
    for r in obstacles:
        if rect_line_intersect(r, a, b):
            return True
    return False

# -------------------------
# Particle System
# -------------------------
class Particle:
    def __init__(self, pos, vel, life, size, color, gravity=0.0):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.life = life
        self.max_life = life
        self.size = size
        self.color = color
        self.gravity = gravity
    def update(self, dt):
        self.life -= dt
        if self.gravity:
            self.vel.y += self.gravity * dt
        self.pos += self.vel * dt
    def alive(self): return self.life > 0
    def draw(self, surf, cam):
        alpha = int(255 * (self.life / self.max_life))
        if alpha < 0: alpha = 0
        s = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        s.fill((*self.color, alpha))
        surf.blit(s, (self.pos.x - cam.rect.x - self.size/2, self.pos.y - cam.rect.y - self.size/2))

class ParticleSystem:
    def __init__(self):
        self.particles = []
    def spawn_muzzle(self, pos, dir_angle, n=6):
        for i in range(n):
            ang = math.radians(dir_angle + random.uniform(-6,6))
            spd = random.uniform(160, 420)
            vel = Vector2(math.cos(ang), math.sin(ang)) * spd + Vector2(random.uniform(-40,40), random.uniform(-40,40))
            self.particles.append(Particle(pos, vel, life=0.12 + random.random()*0.07, size=random.randint(3,6), color=(255,220,120)))
    def spawn_impact(self, pos):
        for i in range(8):
            ang = random.uniform(0, 360)
            spd = random.uniform(40, 220)
            vel = Vector2(math.cos(math.radians(ang)), math.sin(math.radians(ang))) * spd
            self.particles.append(Particle(pos, vel, life=0.4 + random.random()*0.6, size=random.randint(3,6), color=(200,200,180), gravity=0.0))
    def spawn_explosion(self, pos, color=(255,120,40), n=28):
        for i in range(n):
            ang = random.uniform(0, 360)
            spd = random.uniform(60, 460)
            vel = Vector2(math.cos(math.radians(ang)), math.sin(math.radians(ang))) * spd
            self.particles.append(Particle(pos, vel, life=0.8 + random.random()*0.8, size=random.randint(4,8), color=color, gravity=PARTICLE_GRAVITY*0.6))
    def update(self, dt):
        for p in self.particles: p.update(dt)
        self.particles = [p for p in self.particles if p.alive()]
    def draw(self, surf, cam):
        for p in self.particles: p.draw(surf, cam)

# -------------------------
# Bullet fired from  the direction of the other than it all then
# -------------------------
class Bullet(pygame.sprite.Sprite):
    def __init__(self, pos, angle_deg, speed, damage, owner_tag):
        super().__init__()
        self.pos = Vector2(pos)
        a = math.radians(angle_deg)
        self.vel = Vector2(math.cos(a), math.sin(a)) * speed
        self.damage = damage
        self.owner = owner_tag
        self.image = pygame.Surface((8,4), pygame.SRCALPHA)
        color = (255,220,100) if owner_tag=='player' else (255,90,90)
        pygame.draw.rect(self.image, color, (0,0,8,4))
        self.orig_image = self.image
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        self.angle = angle_deg
        self.life = 6.0
    def update(self, dt, obstacles):
        self.pos += self.vel * dt
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        self.life -= dt
        if self.life <= 0:
            self.kill(); return
        for r in obstacles:
            if self.rect.colliderect(r):
                self.kill()
                return
        if self.pos.x < -200 or self.pos.x > WORLD_W+200 or self.pos.y < -200 or self.pos.y > WORLD_H+200:
            self.kill()
    def draw(self, surf, cam):
        rot = pygame.transform.rotate(self.orig_image, -self.angle)
        surf.blit(rot, (self.pos.x - cam.rect.x - rot.get_width()/2, self.pos.y - cam.rect.y - rot.get_height()/2))

# -------------------------
# House (walls + entry + exit)
# -------------------------
class House:
    def __init__(self, x, y, w, h, entry_rect, exit_rect):
        self.rect = pygame.Rect(x, y, w, h)
        self.entry_rect = pygame.Rect(entry_rect)
        self.exit_rect = pygame.Rect(exit_rect)
        # interior obstacles - optional (furniture)
        self.interior = []
        # build interior small tables, etc.
        for i in range(4):
            rx = random.randint(x+40, x+w-80)
            ry = random.randint(y+40, y+h-80)
            self.interior.append(pygame.Rect(rx, ry, random.choice([30,40,48]), random.choice([20,28])))
    def draw(self, surf, cam):
        outer = pygame.Rect(self.rect.x - cam.rect.x, self.rect.y - cam.rect.y, self.rect.w, self.rect.h)
        pygame.draw.rect(surf, (120,120,120), outer)
        pygame.draw.rect(surf, (80,80,80), outer, 3)
        # doors
        de = pygame.Rect(self.entry_rect.x - cam.rect.x, self.entry_rect.y - cam.rect.y, self.entry_rect.w, self.entry_rect.h)
        dx = pygame.Rect(self.exit_rect.x - cam.rect.x, self.exit_rect.y - cam.rect.y, self.exit_rect.w, self.exit_rect.h)
        pygame.draw.rect(surf, (220,200,80), de)
        pygame.draw.rect(surf, (220,100,80), dx)
        # interior
        for r in self.interior:
            rr = pygame.Rect(r.x - cam.rect.x, r.y - cam.rect.y, r.w, r.h)
            pygame.draw.rect(surf, (80,60,60), rr)
            pygame.draw.rect(surf, (60,40,40), rr, 2)
    def block_movement(self, entity):
        # if entity inside house rect but not overlapping doors, push back to nearest edge
        if not self.rect.colliderect(entity.rect):
            return
        inside_entry = self.entry_rect.colliderect(entity.rect)
        inside_exit = self.exit_rect.colliderect(entity.rect)
        if inside_entry or inside_exit:
            # allowed to pass
            return
        # push entity outside: compute which side it's intersecting more with
        dx_left = abs(entity.pos.x - self.rect.left)
        dx_right = abs(self.rect.right - entity.pos.x)
        dy_top = abs(entity.pos.y - self.rect.top)
        dy_bot = abs(self.rect.bottom - entity.pos.y)
        m = min(dx_left, dx_right, dy_top, dy_bot)
        if m == dx_left:
            entity.pos.x = self.rect.left - entity.rect.width/2 - 2
        elif m == dx_right:
            entity.pos.x = self.rect.right + entity.rect.width/2 + 2
        elif m == dy_top:
            entity.pos.y = self.rect.top - entity.rect.height/2 - 2
        else:
            entity.pos.y = self.rect.bottom + entity.rect.height/2 + 2
        entity.rect.center = (int(entity.pos.x), int(entity.pos.y))

    def blocks_los(self, a, b):
        # if line a->b intersects the house border (not doors), block LOS
        # check against the 4 walls as rects minus doors
        left_wall = pygame.Rect(self.rect.left, self.rect.top, 4, self.rect.h)
        right_wall = pygame.Rect(self.rect.right-4, self.rect.top, 4, self.rect.h)
        top_wall = pygame.Rect(self.rect.left, self.rect.top, self.rect.w, 4)
        bottom_wall = pygame.Rect(self.rect.left, self.rect.bottom-4, self.rect.w, 4)
        walls = [left_wall, right_wall, top_wall, bottom_wall]
        for w in walls:
            # if line intersects the door region we should not block
            if rect_line_intersect(w, a, b):
                # if intersects door area, do not block
                # we'll treat doors as gaps: if line passes through door rect, do not block
                if rect_line_intersect(self.entry_rect, a, b) or rect_line_intersect(self.exit_rect, a, b):
                    return False
                return True
        return False

# -------------------------
# Obstacle (crate/tree/wall)
# -------------------------
class Obstacle:
    def __init__(self, rect, clip_shoot=True):
        self.rect = pygame.Rect(rect)
        self.clip_shoot = clip_shoot
    def draw(self, surf, cam):
        r = pygame.Rect(self.rect.x - cam.rect.x, self.rect.y - cam.rect.y, self.rect.w, self.rect.h)
        pygame.draw.rect(surf, COVER_COLOR, r)
        pygame.draw.rect(surf, (110,110,110), r, 2)

# -------------------------
# Player that can beat the user and work on the are and other than map and house
# -------------------------
class Player(pygame.sprite.Sprite):
    def __init__(self, pos):
        super().__init__()
        self.pos = Vector2(pos)
        self.vel = Vector2(0,0)
        self.health = PLAYER_MAX_HEALTH
        self.lives = PLAYER_LIVES
        self.weapon_key_order = ['rifle','smg','shotgun']
        self.weapon_idx = 0
        self.weapon = WEAPONS[self.weapon_key_order[self.weapon_idx]]
        self.mag = self.weapon['mag']
        self.last_shot_time = 0.0
        self.reload_end = 0.0
        self.angle = -90.0
        self.image = self._make_sprite()
        self.rect = self.image.get_rect(center=self.pos)
        self.invuln = 0.0
        self.alive_flag = True
        self.recoil = 0.0
    def _make_sprite(self):
        surf = pygame.Surface((56,56), pygame.SRCALPHA)
        pygame.draw.rect(surf, (36,46,56), (18, 12, 20, 28))  # torso
        pygame.draw.rect(surf, (70,80,92), (14, 6, 28, 10))   # helmet
        pygame.draw.rect(surf, (30,30,34), (10, 40, 10, 12))
        pygame.draw.rect(surf, (30,30,34), (36, 40, 10, 12))
        return surf
    def switch_weapon(self, dir):
        self.weapon_idx = (self.weapon_idx + dir) % len(self.weapon_key_order)
        self.weapon = WEAPONS[self.weapon_key_order[self.weapon_idx]]
        self.mag = self.weapon['mag']
    def update(self, dt, keys, obstacles, houses):
        if not self.alive_flag: return
        # movement with accel/decel and sprint
        move = Vector2(0,0)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: move.x += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]: move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: move.y += 1
        sprint = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        max_speed = PLAYER_MAX_SPEED * (PLAYER_SPRINT_MULT if sprint else 1.0)
        if move.length_squared() > 0:
            move = move.normalize()
            desired = move * max_speed
            dv = desired - self.vel
            max_acc = PLAYER_ACCEL * dt
            if dv.length() > max_acc:
                dv.scale_to_length(max_acc)
            self.vel += dv
        else:
            vlen = self.vel.length()
            decel = PLAYER_FRICTION * dt
            if vlen <= decel:
                self.vel = Vector2(0,0)
            else:
                self.vel.scale_to_length(vlen - decel)
        self.pos += self.vel * dt
        # bounds
        self.pos.x = clamp(self.pos.x, 10, WORLD_W - 10)
        self.pos.y = clamp(self.pos.y, 10, WORLD_H - 10)
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        # collisions with obstacles
        for ob in obstacles:
            if self.rect.colliderect(ob.rect):
                # push back simple resolution: move out along shortest axis
                overlap = self.rect.clip(ob.rect)
                if overlap.width < overlap.height:
                    if self.rect.centerx > ob.rect.centerx:
                        self.pos.x += overlap.width + 1
                    else:
                        self.pos.x -= overlap.width + 1
                else:
                    if self.rect.centery > ob.rect.centery:
                        self.pos.y += overlap.height + 1
                    else:
                        self.pos.y -= overlap.height + 1
                self.rect.center = (int(self.pos.x), int(self.pos.y))
        # house blocking
        for h in houses:
            h.block_movement(self)
        # invuln
        if self.invuln > 0:
            self.invuln -= dt
            if self.invuln < 0: self.invuln = 0
        # reload completion
        if self.reload_end and time.time() >= self.reload_end:
            self.mag = self.weapon['mag']
            self.reload_end = 0.0
        # recoil decay
        if self.recoil > 0:
            self.recoil = max(0.0, self.recoil - 85.0 * dt)
    def can_shoot(self):
        if not self.alive_flag: return False
        if self.reload_end: return False
        now = time.time()
        secs_per_shot = 60.0 / self.weapon['rpm']
        return (now - self.last_shot_time) >= secs_per_shot and self.mag > 0
    def shoot(self, target_world_pos, bullets_group, all_sprites_group, particle_sys):
        if not self.can_shoot(): return False
        dx = target_world_pos[0] - self.pos.x
        dy = target_world_pos[1] - self.pos.y
        base_ang = math.degrees(math.atan2(dy, dx))
        wkey = self.weapon_key_order[self.weapon_idx]
        w = self.weapon
        self.last_shot_time = time.time()
        self.mag -= 1
        particle_sys.spawn_muzzle(self.pos + Vector2(math.cos(math.radians(base_ang))*28, math.sin(math.radians(base_ang))*28), base_ang, n=6)
        self.recoil += 6.0
        if wkey == 'shotgun':
            pellets = w.get('pellets', 8)
            for i in range(pellets):
                spread = random.uniform(-w['spread'], w['spread'])
                ang = base_ang + spread
                b = Bullet(self.pos + Vector2(math.cos(math.radians(ang))*22, math.sin(math.radians(ang))*22), ang, w['speed'], w['damage'], 'player')
                bullets_group.add(b); all_sprites_group.add(b)
        else:
            ang = base_ang + random.uniform(-w['spread'], w['spread'])
            b = Bullet(self.pos + Vector2(math.cos(math.radians(ang))*22, math.sin(math.radians(ang))*22), ang, w['speed'], w['damage'], 'player')
            bullets_group.add(b); all_sprites_group.add(b)
        if self.mag <= 0:
            self.reload()
        return True
    def reload(self):
        if self.reload_end: return
        self.reload_end = time.time() + self.weapon['reload']

# -------------------------
# Enemy
# -------------------------
class Enemy(pygame.sprite.Sprite):
    def __init__(self, pos, patrol_points=None, hp=ENEMY_BASE_HP, speed=ENEMY_BASE_SPEED, is_boss=False):
        super().__init__()
        self.pos = Vector2(pos)
        self.vel = Vector2(0,0)
        self.image = pygame.Surface((48,48), pygame.SRCALPHA)
        self._draw_sprite(is_boss)
        self.rect = self.image.get_rect(center=self.pos)
        self.hp = hp
        self.max_hp = hp
        self.speed = speed
        self.state = 'patrol'
        self.patrol_points = patrol_points or []
        self.patrol_index = 0
        self.last_seen = 0.0
        self.fire_cool = ENEMY_FIRE_COOLDOWN * (0.8 if is_boss else 1.0)
        self.last_shot = 0.0
        self.is_boss = is_boss
    def _draw_sprite(self, boss):
        s = self.image
        clr = (200,30,80) if not boss else (120,20,180)
        pygame.draw.rect(s, clr, (6,8,36,32))
        if boss:
            pygame.draw.rect(s, (255,215,0), (8,10,32,6))
    def update(self, dt, player, obstacles, enemy_bullets, all_sprites, particle_sys, houses):
        if self.hp <= 0: return
        to_player = player.pos - self.pos
        dist = to_player.length()
        has_los = True
        # check houses block LOS
        for h in houses:
            if h.blocks_los((int(self.pos.x), int(self.pos.y)), (int(player.pos.x), int(player.pos.y))):
                has_los = False
                break
        # check obstacles block LOS
        if has_los and line_blocked((int(self.pos.x), int(self.pos.y)), (int(player.pos.x), int(player.pos.y)), [ob.rect for ob in obstacles if ob.clip_shoot]):
            has_los = False
        if dist <= ENEMY_DETECT_RADIUS and has_los:
            self.state = 'engage'
            self.last_seen = time.time()
        elif time.time() - self.last_seen < 4.0:
            self.state = 'alert'
        else:
            self.state = 'patrol'
        if self.state == 'patrol':
            if self.patrol_points:
                target = self.patrol_points[self.patrol_index]
                if (target - self.pos).length() < 12:
                    self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)
                desired = (target - self.pos)
                if desired.length() > 0: desired = desired.normalize() * self.speed
                self.vel += (desired - self.vel) * min(1.0, dt*4.5)
            else:
                self.vel += (Vector2(random.uniform(-1,1), random.uniform(-1,1)) * self.speed - self.vel) * min(1.0, dt*2.0)
            self.pos += self.vel * dt
        elif self.state == 'alert':
            if (player.pos - self.pos).length() > 12:
                desired = (player.pos - self.pos).normalize() * (self.speed * 0.9)
                self.vel += (desired - self.vel) * min(1.0, dt*3.5)
                self.pos += self.vel * dt
        elif self.state == 'engage':
            dir_to_player = (player.pos - self.pos)
            if dir_to_player.length() > 6:
                move_dir = dir_to_player.normalize()
                desired_dist = 220 if not self.is_boss else 300
                if dir_to_player.length() > desired_dist + 40:
                    desired = move_dir * self.speed
                elif dir_to_player.length() < desired_dist - 40:
                    desired = -move_dir * (self.speed * 0.6)
                else:
                    perp = Vector2(-move_dir.y, move_dir.x)
                    desired = perp * self.speed * (1.0 if random.random() > 0.5 else -1.0)
                self.vel += (desired - self.vel) * min(1.0, dt*6.0)
                self.pos += self.vel * dt
            # shooting
            if has_los and time.time() - self.last_shot >= self.fire_cool:
                self.last_shot = time.time()
                ang = math.degrees(math.atan2(player.pos.y - self.pos.y, player.pos.x - self.pos.x))
                b = Bullet(self.pos + Vector2(math.cos(math.radians(ang))*22, math.sin(math.radians(ang))*22), ang, ENEMY_BULLET_SPEED, ENEMY_DAMAGE * (2 if self.is_boss else 1), 'enemy')
                enemy_bullets.add(b); all_sprites.add(b)
        # collisions with obstacles (avoid walking through)
        for ob in obstacles:
            if self.rect.colliderect(ob.rect):
                overlap = self.rect.clip(ob.rect)
                if overlap.width < overlap.height:
                    if self.rect.centerx > ob.rect.centerx:
                        self.pos.x += overlap.width + 1
                    else:
                        self.pos.x -= overlap.width + 1
                else:
                    if self.rect.centery > ob.rect.centery:
                        self.pos.y += overlap.height + 1
                    else:
                        self.pos.y -= overlap.height + 1
                self.rect.center = (int(self.pos.x), int(self.pos.y))
        # house blocking
        for h in houses:
            h.block_movement(self)
        self.pos.x = clamp(self.pos.x, 12, WORLD_W - 12)
        self.pos.y = clamp(self.pos.y, 12, WORLD_H - 12)
        self.rect.center = (int(self.pos.x), int(self.pos.y))
    def hit(self, dmg, particle_sys):
        self.hp -= dmg
        particle_sys.spawn_impact(self.pos)
        if self.hp <= 0:
            particle_sys.spawn_explosion(self.pos, color=(255,150,60), n=28)
            self.kill()

# -------------------------
# Camera
# -------------------------
class Camera:
    def __init__(self, w, h):
        self.rect = pygame.Rect(0,0,w,h)
    def update(self, player):
        self.rect.center = (int(player.pos.x), int(player.pos.y))
        self.rect.x = clamp(self.rect.x, 0, WORLD_W - SCREEN_W)
        self.rect.y = clamp(self.rect.y, 0, WORLD_H - SCREEN_H)
    def apply_rect(self, r): return pygame.Rect(r.x - self.rect.x, r.y - self.rect.y, r.w, r.h)
    def world_to_screen(self, pos): return Vector2(pos.x - self.rect.x, pos.y - self.rect.y)

# -------------------------
# Map generation helpers
# -------------------------
def create_urban_obstacles():
    obstacles = []
    buildings = [
        pygame.Rect(300, 220, 900, 360),
        pygame.Rect(1400, 150, 600, 380),
        pygame.Rect(950, 820, 600, 420),
        pygame.Rect(400, 1280, 480, 320),
        pygame.Rect(2100, 980, 720, 440)
    ]
    for b in buildings:
        obstacles.append(Obstacle(b, clip_shoot=True))
    for i in range(48):
        x = random.randint(80, WORLD_W-160)
        y = random.randint(80, WORLD_H-160)
        obstacles.append(Obstacle(pygame.Rect(x,y, random.choice([44,56,72]), random.choice([28,44])), clip_shoot=True))
    return obstacles

def create_compound_obstacles():
    obstacles = []
    walls = [
        pygame.Rect(220, 260, WORLD_W-440, 30),
        pygame.Rect(220, WORLD_H-290, WORLD_W-440, 30),
        pygame.Rect(220, 260, 30, WORLD_H - 520),
        pygame.Rect(WORLD_W-250, 260, 30, WORLD_H - 520)
    ]
    for w in walls: obstacles.append(Obstacle(w, clip_shoot=True))
    obstacles.append(Obstacle(pygame.Rect(900, 560, 720, 420), clip_shoot=True))
    for i in range(58):
        x = random.randint(240, WORLD_W-260)
        y = random.randint(240, WORLD_H-260)
        obstacles.append(Obstacle(pygame.Rect(x,y, random.choice([48,64]), random.choice([24,40])), clip_shoot=True))
    return obstacles

# -------------------------
# Level Manager
# -------------------------
class LevelManager:
    def __init__(self, enemies_group, all_sprites, enemy_bullets, particle_sys):
        self.enemies = enemies_group
        self.all = all_sprites
        self.enemy_bullets = enemy_bullets
        self.particles = particle_sys
        self.current_level = 1
        self.spawned = 0
        self.spawn_interval = 1.1
        self.spawn_timer = 0.0
        self.enemies_to_spawn = 8 + self.current_level * 3
        self.boss = None
    def update(self, dt, obstacles, houses):
        if self.current_level in BOSS_LEVELS and self.boss is None:
            bpos = Vector2(WORLD_W//2, 180 + (self.current_level*10))
            boss = Enemy(bpos, patrol_points=[Vector2(bpos.x-220,bpos.y), Vector2(bpos.x+220,bpos.y)], hp=900 + self.current_level*180, speed=80, is_boss=True)
            self.enemies.add(boss); self.all.add(boss); self.boss = boss
            return
        if self.spawned >= self.enemies_to_spawn: return
        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer = 0.0
            sx = random.randint(220, WORLD_W-220)
            sy = random.randint(80, WORLD_H//2)
            pts = [Vector2(sx + random.randint(-260, 260), sy + random.randint(-160, 160)) for _ in range(3)]
            e = Enemy((sx, sy), patrol_points=pts, hp=ENEMY_BASE_HP + self.current_level*18, speed=ENEMY_BASE_SPEED + self.current_level*3)
            self.enemies.add(e); self.all.add(e)
            self.spawned += 1
    def check_progress(self):
        if self.current_level in BOSS_LEVELS:
            if self.boss and not self.boss.alive():
                self.boss = None
                self._advance()
            return
        if self.spawned >= self.enemies_to_spawn and len(self.enemies) == 0:
            self._advance()
    def _advance(self):
        if self.current_level >= TOTAL_LEVELS:
            print("Victory - all levels complete")
            return
        self.current_level += 1
        self.spawned = 0
        self.enemies_to_spawn = 8 + self.current_level * 3
        self.spawn_interval = max(0.45, 1.1 - self.current_level * 0.05)
        print("Advanced to level", self.current_level)

# -------------------------
# HUD
# -------------------------
def draw_hud(screen, player, lm, cam):
    font = pygame.font.SysFont("consolas", 18)
    texts = [
        f"Level: {lm.current_level}/{TOTAL_LEVELS}",
        f"Lives: {player.lives}",
        f"HP: {int(player.health)}/{PLAYER_MAX_HEALTH}",
        f"Weapon: {player.weapon['name']}  Mag: {player.mag}/{player.weapon['mag']}"
    ]
    x, y = 12, 8
    for t in texts:
        screen.blit(font.render(t, True, (240,240,240)), (x, y)); y += 22
    pygame.draw.circle(screen, (255,255,255), (SCREEN_W//2, SCREEN_H//2), 6, 1)

# -------------------------
# Healthbar helper
# -------------------------
def draw_healthbar(surf, pos, frac, cam, w=44, h=6):
    px = pos.x - cam.rect.x - w//2
    py = pos.y - cam.rect.y - 40
    bg = pygame.Rect(px, py, w, h)
    fg = pygame.Rect(px, py, int(w*frac), h)
    pygame.draw.rect(surf, (40,40,40), bg)
    pygame.draw.rect(surf, (40,200,40), fg)
    pygame.draw.rect(surf, (0,0,0), bg, 1)

# -------------------------
# MAIN
# -------------------------
def main():
    pygame.init()
    try:
        pygame.mixer.init()
    except:
        pass
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Ultimate House Shooter")
    clock = pygame.time.Clock()
    font_big = pygame.font.SysFont("consolas", 44)

    all_sprites = pygame.sprite.Group()
    enemies = pygame.sprite.Group()
    player_bullets = pygame.sprite.Group()
    enemy_bullets = pygame.sprite.Group()

    particles = ParticleSystem()

    player = Player(PLAYER_RESPAWN_POS)
    all_sprites.add(player)

    cam = Camera(SCREEN_W, SCREEN_H)

    maps = [create_urban_obstacles(), create_compound_obstacles()]
    map_index = 0
    obstacles = maps[map_index]

    # create houses with single entry & exit
    houses = []
    # House 1 (urban)
    hx, hy, hw, hh = 1200, 820, 420, 300
    entry = (hx + hw - 46, hy + hh - 80, 46, 80)   # south-east small door (entry)
    exitr = (hx + 20, hy + 20, 46, 80)             # north-west small door (exit)
    houses.append(House(hx, hy, hw, hh, entry, exitr))
    # House 2 (compound)
    hx2, hy2, hw2, hh2 = 2200, 420, 420, 320
    entry2 = (hx2 + 10, hy2 + hh2 - 80, 46, 80)
    exit2 = (hx2 + hw2 - 56, hy2 + 12, 46, 80)
    houses.append(House(hx2, hy2, hw2, hh2, entry2, exit2))

    lm = LevelManager(enemies, all_sprites, enemy_bullets, particles)

    # pre-spawn enemies to create immediate tension to panic the player in the match
    for _ in range(6):
        sx = random.randint(220, WORLD_W-220)
        sy = random.randint(80, WORLD_H//2)
        pts = [Vector2(sx + random.randint(-260,260), sy + random.randint(-160,160)) for _ in range(3)]
        e = Enemy((sx, sy), patrol_points=pts, hp=ENEMY_BASE_HP, speed=ENEMY_BASE_SPEED)
        enemies.add(e); all_sprites.add(e); lm.spawned += 1

    paused = False
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        keys = pygame.key.get_pressed()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                if ev.key == pygame.K_p:
                    paused = not paused
                if ev.key == pygame.K_q:
                    player.switch_weapon(-1)
                if ev.key == pygame.K_e:
                    player.switch_weapon(1)
                if ev.key == pygame.K_r:
                    player.reload()
                if ev.key == pygame.K_m:
                    map_index = (map_index + 1) % len(maps)
                    obstacles = maps[map_index]
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and not paused:
                if player.alive_flag:
                    mx, my = pygame.mouse.get_pos()
                    world_target = (mx + cam.rect.x, my + cam.rect.y)
                    player.shoot(world_target, player_bullets, all_sprites, particles)

        if not paused:
            lm.update(dt, obstacles, houses)
            player.update(dt, keys, obstacles, houses)
            for en in list(enemies):
                en.update(dt, player, obstacles, enemy_bullets, all_sprites, particles, houses)
            for b in list(player_bullets): b.update(dt, obstacles)
            for b in list(enemy_bullets): b.update(dt, obstacles)
            # player bullets -> enemies
            for en in list(enemies):
                hits = [b for b in player_bullets if b.rect.colliderect(en.rect)]
                for b in hits:
                    # ensure bullet is not blocked by house walls between its pos and enemy (already removed if collided)
                    en.hit(b.damage, particles)
                    particles.spawn_impact(b.pos)
                    try: b.kill()
                    except: pass
            # enemy bullets -> player
            if player.alive_flag:
                hits = [b for b in enemy_bullets if b.rect.colliderect(player.rect)]
                for b in hits:
                    player.health -= b.damage
                    particles.spawn_impact(b.pos)
                    try: b.kill()
                    except: pass
                    if player.health <= 0:
                        player.lives -= 1
                        particles.spawn_explosion(player.pos, color=(255,90,50))
                        if player.lives > 0:
                            player.pos = Vector2(PLAYER_RESPAWN_POS)
                            player.health = PLAYER_MAX_HEALTH
                            player.invuln = 1.6
                        else:
                            player.alive_flag = False
            # enemy-player collisions (ram)
            if player.alive_flag:
                col = pygame.sprite.spritecollide(player, enemies, dokill=False)
                for en in col:
                    player.health -= 18 * dt * 8 * 0.02
                    if player.health <= 0:
                        player.lives -= 1
                        particles.spawn_explosion(player.pos, color=(255,90,50))
                        if player.lives > 0:
                            player.pos = Vector2(PLAYER_RESPAWN_POS)
                            player.health = PLAYER_MAX_HEALTH
                            player.invuln = 1.6
                        else:
                            player.alive_flag = False
            for en in list(enemies):
                if not en.alive():
                    try:
                        enemies.remove(en); all_sprites.remove(en)
                    except: pass
            lm.check_progress()
            if lm.current_level == 6 and map_index == 0:
                map_index = 1; obstacles = maps[map_index]
        cam.update(player)
        # draw
        if lm.current_level <= 5:
            screen.fill(DAY_BG)
        else:
            screen.fill(NIGHT_BG)
            for i in range(40):
                sx = (i * 37 + lm.current_level * 13) % SCREEN_W
                sy = (i * 79 + lm.current_level * 7) % (SCREEN_H//2)
                screen.set_at((sx, sy), (200,200,180))
        # ground grid
        gap = 96
        start_x = - (cam.rect.x % gap)
        start_y = - (cam.rect.y % gap)
        for gx in range(start_x, SCREEN_W, gap):
            pygame.draw.line(screen, GRID_COLOR, (gx, 0), (gx, SCREEN_H))
        for gy in range(start_y, SCREEN_H, gap):
            pygame.draw.line(screen, GRID_COLOR, (0, gy), (SCREEN_W, gy))
        # draw obstacles
        for ob in obstacles:
            ob.draw(screen, cam)
        # draw houses
        for h in houses: h.draw(screen, cam)
        # particles behind characters
        particles.draw(screen, cam)
        # bullets
        for b in player_bullets: b.draw(screen, cam)
        for b in enemy_bullets: b.draw(screen, cam)
        # enemies
        for en in enemies:
            pos_scr = cam.world_to_screen(en.pos)
            screen.blit(en.image, (pos_scr.x - en.image.get_width()/2, pos_scr.y - en.image.get_height()/2))
            draw_healthbar(screen, en.pos, max(0.0, en.hp/en.max_hp), cam, w=44, h=6)
        # player
        if player.alive_flag:
            ppos = cam.world_to_screen(player.pos)
            screen.blit(player.image, (ppos.x - player.image.get_width()/2, ppos.y - player.image.get_height()/2))
            if player.recoil > 0:
                ang = player.angle
                mpos = player.pos + Vector2(math.cos(math.radians(ang))*28, math.sin(math.radians(ang))*28)
                mp = cam.world_to_screen(mpos)
                pygame.draw.circle(screen, (255,200,100), (int(mp.x), int(mp.y)), int(6 + player.recoil*0.12))
        else:
            go = font_big.render("GAME OVER - Press ESC to quit", True, (255,80,80))
            screen.blit(go, (SCREEN_W//2 - go.get_width()//2, SCREEN_H//2 - 40))
        # HUD
        draw_hud(screen, player, lm, cam)
        # minimap
        mm_w, mm_h = 240, 160
        mm_rect = pygame.Rect(SCREEN_W - mm_w - 16, SCREEN_H - mm_h - 16, mm_w, mm_h)
        pygame.draw.rect(screen, (8,8,8), mm_rect)
        pygame.draw.rect(screen, (80,80,80), mm_rect, 2)
        sx = mm_rect.x; sy = mm_rect.y; sw = mm_rect.width; sh = mm_rect.height
        sx_scale = sw / WORLD_W; sy_scale = sh / WORLD_H
        for ob in obstacles[:600]:
            rx = sx + int(ob.rect.x * sx_scale); ry = sy + int(ob.rect.y * sy_scale)
            rw = max(1, int(ob.rect.w * sx_scale)); rh = max(1, int(ob.rect.h * sy_scale))
            pygame.draw.rect(screen, (120,120,120), (rx, ry, rw, rh))
        for h in houses:
            hx = sx + int(h.rect.x * sx_scale); hy = sy + int(h.rect.y * sy_scale)
            hw = max(2, int(h.rect.w * sx_scale)); hh = max(2, int(h.rect.h * sy_scale))
            pygame.draw.rect(screen, (140,120,100), (hx, hy, hw, hh))
        for en in enemies:
            ex = sx + int(en.pos.x * sx_scale); ey = sy + int(en.pos.y * sy_scale)
            pygame.draw.circle(screen, (200,40,40), (ex, ey), 2)
        px = sx + int(player.pos.x * sx_scale); py = sy + int(player.pos.y * sy_scale)
        pygame.draw.circle(screen, (40,220,40), (px, py), 3)
        particles.update(dt)
        pygame.display.flip()
    pygame.quit(); sys.exit()

if __name__ == "__main__":
    main()
