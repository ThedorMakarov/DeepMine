import pygame
import sys
import random
import os
import math
import json

# Параметры экрана и блоков
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
BLOCK_SIZE = 32

MAP_WIDTH = 50
INITIAL_MAP_HEIGHT = 60

# Цвета (RGB)
BLACK    = (0, 0, 0)
WHITE    = (255, 255, 255)
GRAY     = (100, 100, 100)
DARKGRAY = (50, 50, 50)
BROWN    = (139, 69, 19)
BLUE     = (0, 0, 255)

# Энергия и взрывы
ENERGY_MOVE = 1
INITIAL_EXPLOSION_COST = 5

# Гравитация
GRAVITY = 0.8

# Файл сохранения
SAVE_FILE = "game.txt"


def get_ore_type(y):
    if y < 15:
        return {"type": "coal",     "value": 1}
    elif y < 30:
        return {"type": "iron",     "value": 3}
    elif y < 50:
        return {"type": "amethyst", "value": 5}
    else:
        return {"type": "gold",     "value": 7}


def generate_row(y, game_map):
    row = {}
    for x in range(MAP_WIDTH):
        if y < 5:
            row[(x, y)] = 'air'
        else:
            # Шахты
            if game_map.get((x, y - 1)) == "shaft" and random.random() < 0.8:
                row[(x, y)] = "shaft"
                continue
            elif random.random() < 0.02:
                row[(x, y)] = "shaft"
                continue

            # Руда
            ore_adj = any(isinstance(game_map.get((x+dx, y+dy)), dict)
                          for dx, dy in [(-1,0),(0,-1)])
            chance = 0.005 + y/300.0 + (0.0001 if ore_adj else 0)
            if random.random() < chance:
                row[(x, y)] = get_ore_type(y)
            else:
                row[(x, y)] = 'stone' if random.random() < 0.2 else 'dirt'
    return row


def generate_map():
    m = {}
    for y in range(INITIAL_MAP_HEIGHT):
        m.update(generate_row(y, m))
    return m


class DeepMineGame:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("deep mine")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 24)

        # Состояния
        self.state = "menu"
        self.menu_options = ["Начать игру", "Магазин", "Настройки", "Выйти из игры"]
        self.selected_menu = 0

        # Магазин
        self.shop_items = [
            {"name":"Батарея",    "key":"battery",   "base_cost":50,  "desc":"Энергия +20"},
            {"name":"Взрыв",      "key":"explosion", "base_cost":100, "desc":"Взрыв –1"},
            {"name":"Амортизация","key":"springs",   "base_cost":50,  "desc":"Падение +1"},
            {"name":"Скорость",   "key":"speed",     "base_cost":75,  "desc":"Скорость +2"}
        ]
        self.selected_shop = 0
        self.upgrades = {"battery":0,"explosion":0,"springs":0,"speed":0}

        # Настройки
        self.settings = {"sfx":50,"music":50,"god":False}
        self.selected_setting = 0
        self.setting_keys = ["sfx","music","god"]

        # Загрузка текстур
        self.textures = {}
        for name in ('dirt','stone','shaft','coal','iron','amethyst','gold','player'):
            path = f"assets/{name}.png"
            if os.path.exists(path):
                self.textures[name] = pygame.image.load(path).convert_alpha()

        # Фон меню
        self.menu_bg = pygame.image.load("assets/menu_bg.png").convert()

        # Звук копания
        self.sfx_dig = pygame.mixer.Sound("assets/dig.wav")
        self.sfx_dig.set_volume(self.settings["sfx"]/100.0)

        # Фоновая музыка
        pygame.mixer.music.load("assets/song.mp3")
        pygame.mixer.music.set_volume(self.settings["music"]/100.0)
        pygame.mixer.music.play(-1)

        # Игра
        self.reset_game()
        self.load_progress()

    def reset_game(self):
        self.game_map = generate_map()
        self.current_map_height = INITIAL_MAP_HEIGHT
        self.player_pos = [(MAP_WIDTH//2)*BLOCK_SIZE, 4*BLOCK_SIZE]
        self.velocity_y = 0
        self.falling = False
        self.fall_distance = 0
        self.target_x = self.player_pos[0]
        self.animating_horiz = False

        self.coins = 0
        self.energy = 100 + self.upgrades["battery"]*20
        self.max_depth = int(self.player_pos[1]/BLOCK_SIZE)
        self.move_speed = 8 + self.upgrades["speed"]*2
        self.explosion_cost = max(1, INITIAL_EXPLOSION_COST - self.upgrades["explosion"])

    def save_progress(self):
        data = {
            "coins": self.coins,
            "max_depth": self.max_depth,
            "energy": self.energy,
            "upgrades": self.upgrades,
            "settings": self.settings
        }
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def load_progress(self):
        default = {
            "coins": 0,
            "max_depth": 0,
            "energy": 10,
            "upgrades": {
                "battery": 1,
                "explosion": 1,
                "springs": 2,
                "speed": 0
            },
            "settings": {
                "sfx": 70,
                "music": 70,
                "god": False
            }
        }

        if not os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f)
            self._apply_progress(default)
            return
        try:
            with open(SAVE_FILE, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            # при ошибке чтения — перезаписываем дефолтом
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f)
            self._apply_progress(default)
            return
        self._apply_progress(data)

    def _apply_progress(self, data):
        """Вынесено, чтобы не дублировать код."""
        self.coins     = data.get("coins",     0)
        self.max_depth = data.get("max_depth", 0)
        self.energy    = data.get("energy",    10)
        self.upgrades  = data.get("upgrades",  {
            "battery":1, "explosion":1, "springs":2, "speed":0
        })
        self.settings  = data.get("settings",  {
            "sfx":70, "music":70, "god":False
        })

        # Пересчитываем зависящие от апгрейдов параметры
        self.explosion_cost = max(1, INITIAL_EXPLOSION_COST - self.upgrades["explosion"])
        self.move_speed     = 8 + self.upgrades["speed"]*2

        # Обновляем громкости
        self.sfx_dig.set_volume(self.settings["sfx"] / 100.0)
        pygame.mixer.music.set_volume(self.settings["music"] / 100.0)

    def update_map(self):
        ty = int(self.player_pos[1]/BLOCK_SIZE)
        if ty + 10 > self.current_map_height:
            for y in range(self.current_map_height, self.current_map_height + 10):
                self.game_map.update(generate_row(y, self.game_map))
            self.current_map_height += 10

    def update_physics(self):
        tx = int(self.player_pos[0]/BLOCK_SIZE)
        ty = int((self.player_pos[1]+BLOCK_SIZE)/BLOCK_SIZE)
        below = self.game_map.get((tx, ty), 'air')
        if below in ('air','shaft'):
            self.falling = True
        elif self.falling:
            safe = (1 + self.upgrades["springs"]) * BLOCK_SIZE
            if self.fall_distance > safe and not self.settings["god"]:
                self.reset_game()
                return
            self.falling = False
            self.velocity_y = 0
            self.fall_distance = 0

        if self.falling:
            self.velocity_y += GRAVITY
            newy = self.player_pos[1] + self.velocity_y
            ty2 = int((newy + BLOCK_SIZE)/BLOCK_SIZE)
            if ty2 != ty and self.game_map.get((tx, ty2), 'air') not in ('air','shaft'):
                self.player_pos[1] = ty2*BLOCK_SIZE - BLOCK_SIZE
                self.fall_distance += (newy - self.player_pos[1])
                safe = (1 + self.upgrades["springs"]) * BLOCK_SIZE
                if self.fall_distance > safe and not self.settings["god"]:
                    self.reset_game()
                    return
                self.falling = False
                self.velocity_y = 0
                self.fall_distance = 0
            else:
                self.player_pos[1] = newy
                self.fall_distance += self.velocity_y

    def update_horizontal_animation(self):
        if not self.animating_horiz:
            return
        dx = self.target_x - self.player_pos[0]
        step = self.move_speed if dx > 0 else -self.move_speed
        if abs(dx) < abs(step):
            self.player_pos[0] = self.target_x
            self.animating_horiz = False
        else:
            self.player_pos[0] += step

    def move_player(self, dx, dy):
        if self.falling or self.animating_horiz or self.energy < ENERGY_MOVE:
            return
        cx = int(self.player_pos[0]/BLOCK_SIZE)
        cy = int(self.player_pos[1]/BLOCK_SIZE)
        nx, ny = cx+dx, cy+dy
        if nx < 0 or nx >= MAP_WIDTH:
            return
        target = self.game_map.get((nx, ny), 'air')
        if target == 'stone':
            return
        if isinstance(target, dict):
            self.coins += target["value"]
        if target != 'shaft':
            self.game_map[(nx, ny)] = 'air'

        self.target_x = nx * BLOCK_SIZE
        self.animating_horiz = True
        self.energy -= ENERGY_MOVE
        if ny > self.max_depth:
            self.max_depth = ny
        self.update_map()
        # Звук копания
        self.sfx_dig.play()

    def explosion(self):
        if self.energy < self.explosion_cost:
            return
        tx = int(self.player_pos[0]/BLOCK_SIZE)
        ty = int(self.player_pos[1]/BLOCK_SIZE)
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                x, y = tx+dx, ty+dy
                if 0 <= x < MAP_WIDTH and y < self.current_map_height:
                    b = self.game_map.get((x, y), 'air')
                    if b != 'air':
                        if isinstance(b, dict):
                            self.coins += b["value"]
                        self.game_map[(x, y)] = 'air'
        self.energy -= self.explosion_cost

    def draw_game(self):
        self.screen.fill(BLACK)
        ox = self.player_pos[0] - SCREEN_WIDTH//2 + BLOCK_SIZE//2
        oy = self.player_pos[1] - SCREEN_HEIGHT//2 + BLOCK_SIZE//2

        sx = max(0, int(ox//BLOCK_SIZE))
        sy = max(0, int(oy//BLOCK_SIZE))
        ex = min(MAP_WIDTH, sx + SCREEN_WIDTH//BLOCK_SIZE + 2)
        ey = min(self.current_map_height, sy + SCREEN_HEIGHT//BLOCK_SIZE + 2)

        for y in range(sy, ey):
            for x in range(sx, ex):
                b = self.game_map.get((x,y), 'air')
                if b == 'air':
                    continue
                dx, dy = x*BLOCK_SIZE - ox, y*BLOCK_SIZE - oy
                key = b["type"] if isinstance(b, dict) else b
                tex = self.textures.get(key)
                if tex:
                    self.screen.blit(tex, (dx, dy))
                else:
                    color = BROWN if key=='dirt' else GRAY if key=='stone' else DARKGRAY
                    pygame.draw.rect(self.screen, color, (dx, dy, BLOCK_SIZE, BLOCK_SIZE))

        # Игрок
        pr = pygame.Rect(int(self.player_pos[0]-ox), int(self.player_pos[1]-oy), BLOCK_SIZE, BLOCK_SIZE)
        ptex = self.textures.get("player")
        if ptex:
            self.screen.blit(ptex, pr)
        else:
            pygame.draw.rect(self.screen, BLUE, pr)

        info = self.font.render(
            f"Монеты:{self.coins}  Энергия:{self.energy}  Глубина:{int(self.player_pos[1]/BLOCK_SIZE)}",
            True, WHITE)
        self.screen.blit(info, (10,10))
        pygame.display.flip()

    def draw_menu(self):
        self.screen.blit(self.menu_bg, (0, 0))
        for i, opt in enumerate(self.menu_options):
            col = WHITE if i==self.selected_menu else GRAY
            txt = self.font.render(opt, True, col)
            self.screen.blit(txt, (50, 200 + i*40))
        pygame.display.flip()

    def draw_shop(self):
        self.screen.fill(DARKGRAY)
        hdr = self.font.render("Магазин (Beta)", True, WHITE)
        self.screen.blit(hdr, (50,50))
        for i,item in enumerate(self.shop_items):
            lvl  = self.upgrades[item["key"]]
            cost = item["base_cost"]*(lvl+1)
            sel  = "-> " if i==self.selected_shop else "   "
            line = f"{sel}{item['name']} L{lvl} C{cost} {item['desc']}"
            self.screen.blit(self.font.render(line,True,WHITE),(50,100+i*30))
        self.screen.blit(self.font.render(f"Монеты:{self.coins}",True,WHITE),(50,550))
        pygame.display.flip()

    def draw_settings(self):
        self.screen.fill(DARKGRAY)
        hdr = self.font.render("Настройки (ESC)", True, WHITE)
        self.screen.blit(hdr,(50,50))
        lines = [
            f"SFX Volume: {self.settings['sfx']}%",
            f"Music Volume: {self.settings['music']}%",
            f"God Mode: {'ON' if self.settings['god'] else 'OFF'}"
        ]
        for i,line in enumerate(lines):
            sel = "-> " if i==self.selected_setting else "   "
            self.screen.blit(self.font.render(sel+line,True,WHITE),(50,100+i*30))
        pygame.mixer.music.set_volume(self.settings["music"]/100.0)
        self.sfx_dig.set_volume(self.settings["sfx"]/100.0)
        pygame.display.flip()

    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.save_progress()
                pygame.quit()
                sys.exit()
            elif e.type == pygame.KEYDOWN:
                if self.state=="menu":
                    if e.key==pygame.K_UP:
                        self.selected_menu=(self.selected_menu-1)%len(self.menu_options)
                    elif e.key==pygame.K_DOWN:
                        self.selected_menu=(self.selected_menu+1)%len(self.menu_options)
                    elif e.key==pygame.K_RETURN:
                        opt=self.menu_options[self.selected_menu]
                        if opt=="Начать игру":
                            self.reset_game(); self.state="game"
                        elif opt=="Магазин":
                            self.state="shop"
                        elif opt=="Настройки":
                            self.state="settings"
                        elif opt=="Выйти из игры":
                            self.save_progress(); pygame.quit(); sys.exit()

                elif self.state=="game":
                    if e.key==pygame.K_ESCAPE:
                        self.state="menu"
                    elif e.key==pygame.K_SPACE:
                        self.explosion()
                    elif e.key in (pygame.K_LEFT,pygame.K_a):
                        self.move_player(-1,0)
                    elif e.key in (pygame.K_RIGHT,pygame.K_d):
                        self.move_player(1,0)
                    elif e.key in (pygame.K_UP,pygame.K_w):
                        self.move_player(0,-1)
                    elif e.key in (pygame.K_DOWN,pygame.K_s):
                        self.move_player(0,1)

                elif self.state=="shop":
                    if e.key==pygame.K_ESCAPE:
                        self.state="menu"
                    elif e.key==pygame.K_UP:
                        self.selected_shop=(self.selected_shop-1)%len(self.shop_items)
                    elif e.key==pygame.K_DOWN:
                        self.selected_shop=(self.selected_shop+1)%len(self.shop_items)
                    elif e.key==pygame.K_RETURN:
                        itm=self.shop_items[self.selected_shop]
                        lvl=self.upgrades[itm["key"]]
                        cost=itm["base_cost"]*(lvl+1)
                        if self.coins>=cost:
                            self.coins-=cost
                            if itm["key"]=="battery":
                                self.upgrades["battery"]+=1; self.energy+=20
                            elif itm["key"]=="explosion":
                                self.upgrades["explosion"]+=1; self.explosion_cost=max(1,self.explosion_cost-1)
                            elif itm["key"]=="springs":
                                self.upgrades["springs"]+=1
                            elif itm["key"]=="speed":
                                self.upgrades["speed"]+=1; self.move_speed+=2

                elif self.state=="settings":
                    if e.key==pygame.K_ESCAPE:
                        self.state="menu"
                    elif e.key==pygame.K_UP:
                        self.selected_setting=(self.selected_setting-1)%len(self.setting_keys)
                    elif e.key==pygame.K_DOWN:
                        self.selected_setting=(self.selected_setting+1)%len(self.setting_keys)
                    elif e.key==pygame.K_LEFT:
                        k=self.setting_keys[self.selected_setting]
                        if k in ("sfx","music"):
                            self.settings[k]=max(0,self.settings[k]-5)
                        else:
                            self.settings[k]=not self.settings[k]
                    elif e.key==pygame.K_RIGHT:
                        k=self.setting_keys[self.selected_setting]
                        if k in ("sfx","music"):
                            self.settings[k]=min(100,self.settings[k]+5)
                        else:
                            self.settings[k]=not self.settings[k]

    def run(self):
        while True:
            self.handle_events()
            if   self.state=="menu":     self.draw_menu()
            elif self.state=="game":
                self.update_physics()
                self.update_horizontal_animation()
                self.draw_game()
            elif self.state=="shop":     self.draw_shop()
            elif self.state=="settings": self.draw_settings()
            self.clock.tick(60)


if __name__ == "__main__":
    DeepMineGame().run()
