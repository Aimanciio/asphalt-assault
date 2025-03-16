import pygame
import random
import pickle
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

# Inicializar Pygame
pygame.init()

def load_image(name: str, size: Tuple[int, int] = None) -> pygame.Surface:
    try:
        image = pygame.image.load(name)
        return pygame.transform.scale(image, size) if size else image
    except pygame.error as e:
        print(f"No se pudo cargar la imagen {name}: {e}")
        return pygame.Surface((0, 0))  # Retorna una superficie vacía en caso de error

# Configuraciones del juego
CONFIG = {
    'SCREEN': {'WIDTH': 800, 'HEIGHT': 600},
    'COLORS': {'BLACK': (0, 0, 0), 'WHITE': (255, 255, 255), 'GREEN': (0, 255, 0), 'BLUE': (0, 0, 255)},
    'AUTOPISTA': {'LEFT': 200, 'RIGHT': 600},
    'FPS': 60,
    'IMAGES': {
        'highway': load_image('highway.png'),
        'cars': {key: load_image(f'{key}_car.png', (50, 50)) for key in ['red', 'blue', 'black']},
        'game_over': load_image('game_over.png', (800, 600)),
        'powerups': {key: load_image(f'{key}_powerup.png', (50, 50)) for key in ['speed', 'immortality']}
    },
    'POWERUP_SPAWN_TIMES': {'speed': 100, 'immortality': 300},
    'POWERUP_DECAY_RATE': 0.005  # Reduce la frecuencia de aparición de power-ups con el tiempo
}

# Configuración del juego
screen = pygame.display.set_mode((CONFIG['SCREEN']['WIDTH'], CONFIG['SCREEN']['HEIGHT']))
pygame.display.set_caption("Asphalt Assault - Menú de Inicio")
clock = pygame.time.Clock()
font = pygame.font.Font(pygame.font.match_font('retro'), 32)

@dataclass
class Entity:
    rect: pygame.Rect
    image: pygame.Surface

@dataclass
class Car(Entity):
    speed: int
    is_immortal: bool = False
    powerups: Dict[str, bool] = field(default_factory=lambda: {'speed': False, 'immortality': False})

    def move(self, dx: int):
        self.rect.x = max(min(self.rect.x + dx, CONFIG['AUTOPISTA']['RIGHT'] - 50), CONFIG['AUTOPISTA']['LEFT'])

    def move_forward(self):
        self.rect.y = max(self.rect.y - self.speed, 0)

    def move_backward(self):
        self.rect.y = min(self.rect.y + self.speed, CONFIG['SCREEN']['HEIGHT'] - 50)

    def draw(self):
        screen.blit(self.image, self.rect)

    def check_collision(self, obstacles: List[Entity]) -> bool:
        return any(self.rect.colliderect(obstacle.rect) for obstacle in obstacles) if not self.is_immortal else False

    def check_power_ups(self, power_ups: List[Entity]):
        for power_up in power_ups[:]:
            if self.rect.colliderect(power_up.rect):
                if power_up.type == 'speed' and not self.powerups['speed']:
                    self.speed = int(self.speed * 2.5)
                    self.powerups['speed'] = True
                elif power_up.type == 'immortality' and not self.powerups['immortality']:
                    self.is_immortal = True
                    self.powerups['immortality'] = True
                    pygame.time.set_timer(pygame.USEREVENT + 1, 5000)
                power_ups.remove(power_up)

@dataclass
class PowerUp(Entity):
    type: str

@dataclass
class Game:
    player_cars: List[Car]
    entities: Dict[str, List[Entity]] = field(default_factory=lambda: {'black_cars': [], 'power_ups': []})
    scores: List[int] = field(default_factory=lambda: [0, 0])
    high_score: int = 0
    en_menu: bool = True
    two_player_mode: bool = False
    game_over: List[bool] = field(default_factory=lambda: [False, False])
    timers: Dict[str, int] = field(default_factory=lambda: {'black_car': 0, **{key: 0 for key in CONFIG['POWERUP_SPAWN_TIMES']}})

    def __post_init__(self):
        self.load_high_score()

    def run(self):
        while True:
            self.handle_events()
            if self.en_menu:
                self.show_menu()
            elif not any(self.game_over):
                self.update()
                self.draw()
            else:
                self.show_game_over()
            clock.tick(CONFIG['FPS'])

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.save_high_score()
                pygame.quit()
                exit()
            elif event.type == pygame.USEREVENT:
                self.reset_powerups()
            elif event.type == pygame.USEREVENT + 1:
                self.reset_immortality()
            elif event.type == pygame.MOUSEBUTTONDOWN and self.en_menu:
                self.handle_menu_click(event)

    def handle_menu_click(self, event):
        if self.start_button_rect.collidepoint(event.pos):
            self.start_single_player_mode()
        elif self.two_players_button_rect.collidepoint(event.pos):
            self.start_two_player_mode()

    def start_single_player_mode(self):
        self.en_menu = False
        self.two_player_mode = False
        pygame.display.set_caption("Asphalt Assault - Modo 1 Jugador")
        self.reset_timers()

    def start_two_player_mode(self):
        self.en_menu = False
        self.two_player_mode = True
        pygame.display.set_caption("Asphalt Assault - Modo 2 Jugadores")
        self.reset_timers()

    def show_menu(self):
        screen.fill(CONFIG['COLORS']['BLACK'])
        self.draw_button(self.start_button_rect, "START", CONFIG['COLORS']['GREEN'])
        self.draw_button(self.two_players_button_rect, "2 PLAYERS", CONFIG['COLORS']['BLUE'])
        self.show_high_score()
        pygame.display.flip()

    def update(self):
        keys = pygame.key.get_pressed()
        self.player_cars[0].move((keys[pygame.K_d] - keys[pygame.K_a]) * self.player_cars[0].speed)
        if self.two_player_mode:
            self.player_cars[1].move((keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]) * self.player_cars[1].speed)
        if keys[pygame.K_w]:
            self.player_cars[0].move_forward()
        if keys[pygame.K_s]:
            self.player_cars[0].move_backward()
        if self.two_player_mode:
            if keys[pygame.K_UP]:
                self.player_cars[1].move_forward()
            if keys[pygame.K_DOWN]:
                self.player_cars[1].move_backward()

        self.update_timers()
        self.spawn_elements()
        self.move_elements()
        self.check_collisions()
        self.scores = [p + 1 for p in self.scores]

    def draw(self):
        screen.blit(CONFIG['IMAGES']['highway'], (0, 0))
        for car in self.player_cars[:2 if self.two_player_mode else 1]:
            car.draw()
        self.draw_elements(self.entities['black_cars'])
        self.draw_elements(self.entities['power_ups'])
        self.draw_scores()
        pygame.display.flip()

    def show_game_over(self):
        self.high_score = max(self.high_score, self.scores[0] // 20)
        self.save_high_score()
        screen.blit(CONFIG['IMAGES']['game_over'], (0, 0))
        pygame.display.flip()
        pygame.time.wait(2000)
        self.reset_game()

    def reset_game(self):
        self.en_menu = True
        pygame.display.set_caption("Asphalt Assault - Menú de Inicio")
        self.game_over = [False, False]
        self.reset_player_cars()
        self.entities['black_cars'].clear()
        self.entities['power_ups'].clear()
        self.scores = [0, 0]
        self.reset_timers()

    def reset_player_cars(self):
        for idx, car in enumerate(self.player_cars):
            car.rect.x = CONFIG['SCREEN']['WIDTH'] // 4 if idx == 0 else 3 * CONFIG['SCREEN']['WIDTH'] // 4
            car.speed = 5
            car.is_immortal = False
            car.powerups = {'speed': False, 'immortality': False}

    def reset_timers(self):
        self.timers = {'black_car': 0, **{key: 0 for key in CONFIG['POWERUP_SPAWN_TIMES']}}

    def update_timers(self):
        self.timers['black_car'] += 1
        for key in CONFIG['POWERUP_SPAWN_TIMES']:
            self.timers[key] += 1

    def spawn_elements(self):
        # Ajustar la frecuencia de aparición de coches negros
        black_car_spawn_time = max(60 - pygame.time.get_ticks() // 10000, 10)
        if self.timers['black_car'] >= black_car_spawn_time:
            self.entities['black_cars'].append(self.create_element('black_car'))
            self.timers['black_car'] = 0

        for key in CONFIG['POWERUP_SPAWN_TIMES']:
            decayed_spawn_time = int(CONFIG['POWERUP_SPAWN_TIMES'][key] * (1 + CONFIG['POWERUP_DECAY_RATE'] * pygame.time.get_ticks() // 1000))
            if self.timers[key] >= decayed_spawn_time:
                self.entities['power_ups'].append(self.create_element(key))
                self.timers[key] = 0

    def move_elements(self):
        black_car_speed = 5 + pygame.time.get_ticks() // 30000  # Aumenta la velocidad gradualmente
        self.move_entity_group(self.entities['black_cars'], black_car_speed)
        self.move_entity_group(self.entities['power_ups'], 5)

    def check_collisions(self):
        for idx, car in enumerate(self.player_cars[:2 if self.two_player_mode else 1]):
            if car.check_collision(self.entities['black_cars']):
                self.game_over[idx] = True
            car.check_power_ups(self.entities['power_ups'])

    def create_element(self, element_type: str) -> Entity:
        x = random.randint(CONFIG['AUTOPISTA']['LEFT'], CONFIG['AUTOPISTA']['RIGHT'] - 50)
        y = -50
        image = CONFIG['IMAGES']['cars']['black'] if element_type == 'black_car' else CONFIG['IMAGES']['powerups'][element_type]
        return PowerUp(rect=pygame.Rect(x, y, 50, 50), image=image, type=element_type) if element_type in ['speed', 'immortality'] else Entity(rect=pygame.Rect(x, y, 50, 50), image=image)

    def move_entity_group(self, entities: List[Entity], speed: int):
        for entity in entities:
            entity.rect.y += speed

    def draw_elements(self, elements: List[Entity]):
        for element in elements:
            screen.blit(element.image, element.rect)

    def draw_button(self, rect: pygame.Rect, text: str, color: Tuple[int, int, int]):
        pygame.draw.rect(screen, color, rect, border_radius=10)
        self.center_text(rect, text, CONFIG['COLORS']['BLACK'])

    def center_text(self, rect: pygame.Rect, text: str, color: Tuple[int, int, int]):
        text_surf = font.render(text, True, color)
        screen.blit(text_surf, text_surf.get_rect(center=rect.center))

    def show_high_score(self):
        text = font.render(f"Record: {self.high_score}", True, CONFIG['COLORS']['WHITE'])
        screen.blit(text, (CONFIG['SCREEN']['WIDTH'] // 2 - text.get_width() // 2, CONFIG['SCREEN']['HEIGHT'] // 2 + 100))

    def draw_scores(self):
        text = font.render(f"Score: {self.scores[0] // 20}", True, CONFIG['COLORS']['WHITE'])
        screen.blit(text, (CONFIG['SCREEN']['WIDTH'] // 2 - text.get_width() // 2, 10))
        if self.two_player_mode:
            text = font.render(f"Score P2: {self.scores[1] // 20}", True, CONFIG['COLORS']['WHITE'])
            screen.blit(text, (10, 10))

    def reset_powerups(self):
        for car in self.player_cars:
            car.speed = 5
            car.powerups['speed'] = False

    def reset_immortality(self):
        for car in self.player_cars:
            car.is_immortal = False
            car.powerups['immortality'] = False

    @property
    def start_button_rect(self) -> pygame.Rect:
        return pygame.Rect(CONFIG['SCREEN']['WIDTH'] // 2 - 80, CONFIG['SCREEN']['HEIGHT'] // 2 - 60, 160, 70)

    @property
    def two_players_button_rect(self) -> pygame.Rect:
        return pygame.Rect(CONFIG['SCREEN']['WIDTH'] // 2 - 80, CONFIG['SCREEN']['HEIGHT'] // 2 + 10, 160, 70)

    def save_high_score(self):
        with open('high_score.sav', 'wb') as file:
            pickle.dump(self.high_score, file)

    def load_high_score(self):
        try:
            with open('high_score.sav', 'rb') as file:
                self.high_score = pickle.load(file)
        except FileNotFoundError:
            self.high_score = 0

# Inicializar el juego
player_cars = [
    Car(rect=pygame.Rect(CONFIG['SCREEN']['WIDTH'] // 4, CONFIG['SCREEN']['HEIGHT'] - 100, 50, 50), image=CONFIG['IMAGES']['cars']['red'], speed=5),
    Car(rect=pygame.Rect(3 * CONFIG['SCREEN']['WIDTH'] // 4, CONFIG['SCREEN']['HEIGHT'] - 100, 50, 50), image=CONFIG['IMAGES']['cars']['blue'], speed=5)
]

game = Game(player_cars=player_cars)
game.run()
