import pygame, random, time, sys, os

# Setup path to allow absolute imports from 'source'
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
if project_root not in sys.path:
	sys.path.insert(0, project_root)

from source import simpleGENetworking
from source.simpleGE import simpleGE

# --- Constants ---
GAME_ID = "Square Shooter"
WINDOW_SIZE = (1600, 900)
PLAYER_SIZE = 30
BULLET_SIZE = 5
PLAYER_SPEED = 5
BULLET_SPEED = 10
BULLET_LIFETIME = 2.0 # seconds

class Bullet(simpleGENetworking.NetSprite):
    def __init__(self, scene, parent, target_pos):
        super().__init__(scene, is_local=True)
        self.type = "bullet"
        self.parent = parent # The Player object who shot this
        self.owner_id = parent.net_id
        self.colorRect((255, 255, 255), (BULLET_SIZE, BULLET_SIZE))
        self.x = parent.x
        self.y = parent.y
        self.boundAction = self.STOP
        
        # Calculate velocity
        angle = self.dirTo(target_pos)
        self.setAngle(angle)
        self.speed = 0 # Reset speed before adding force
        self.addForce(BULLET_SPEED, angle)
        
        self.birth_time = time.time()

    def process(self):
        if self.is_local:
            # Check lifetime
            if time.time() - self.birth_time > BULLET_LIFETIME:
                self.kill()
                return
            
			# TODO: See if this is needed
            # # Bounds check (simpleGE handles basic bounds, but let's kill if off screen)
            # if not self.rect.colliderect(self.scene.background.get_rect()):
            #     self.kill()

    def get_net_state(self):
        # (net_id, sprite_id, x, y, angle, color(dummy), name(dummy), type, owner_id)
        return (self.net_id, self.sprite_id, self.x, self.y, self.imageAngle, None, "", "bullet", self.owner_id)

class Player(simpleGENetworking.NetSprite):
    def __init__(self, scene, name, is_local=False):
        super().__init__(scene, is_local)
        self.type = "player"
        self.name = name
        self.kills = 0
        self.deaths = 0
        self.color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        self.colorRect(self.color, (PLAYER_SIZE, PLAYER_SIZE))
        self.moveSpeed = PLAYER_SPEED
        
        # Random spawn
        self.x = random.randint(50, WINDOW_SIZE[0]-50)
        self.y = random.randint(50, WINDOW_SIZE[1]-50)
        
        self.cooldown = 0.2
        self.last_shot = 0

    def process(self):
        if self.is_local:
            # Movement
            if self.isKeyPressed(pygame.K_a) or self.isKeyPressed(pygame.K_LEFT):
                self.x -= self.moveSpeed
            if self.isKeyPressed(pygame.K_d) or self.isKeyPressed(pygame.K_RIGHT):
                self.x += self.moveSpeed
            if self.isKeyPressed(pygame.K_w) or self.isKeyPressed(pygame.K_UP):
                self.y -= self.moveSpeed
            if self.isKeyPressed(pygame.K_s) or self.isKeyPressed(pygame.K_DOWN):
                self.y += self.moveSpeed
            
            # Manual Bounds Checking
            if self.x < 0: self.x = 0
            if self.x > self.screenWidth: self.x = self.screenWidth
            if self.y < 0: self.y = 0
            if self.y > self.screenHeight: self.y = self.screenHeight
                
            # Shooting
            if pygame.mouse.get_pressed()[0]:
                now = time.time()
                if now - self.last_shot > self.cooldown:
                    self.shoot()
                    self.last_shot = now
                    
    def shoot(self):
        target = pygame.mouse.get_pos()
        bullet = Bullet(self.scene, self, target)
        
        # Add to scene's managed sprites so it gets synced
        self.scene.add_local_sprite(bullet)

    def get_net_state(self):
        # (net_id, sprite_id, x, y, angle, color, name, type, owner_id)
        return (self.net_id, self.sprite_id, self.x, self.y, self.imageAngle, self.color, self.name, "player", self.net_id)

class ShooterLogicMixin:
    def init_game_logic(self, player_name):
        self.player_name = player_name
        self.managed_sprites = {} # sprite_id -> NetSprite
        self.net_sprite_group = self.makeSpriteGroup([])
        self.addGroup(self.net_sprite_group)
        
        self.local_player = None
        self.client_names = {} # {client_id: name}
        self.leaderboard = {} # {name: kills}
        self.destroyed_queue = [] # [sprite_id] to tell others to kill
        
        # UI
        self.lbl_leaderboard = simpleGE.MultiLabel()
        self.lbl_leaderboard.center = (100, 100)
        self.lbl_leaderboard.size = (200, 200)
        self.lbl_leaderboard.textLines = ["Leaderboard"]
        self.lbl_leaderboard.fgColor = (255, 255, 255)
        self.lbl_leaderboard.bgColor = (0, 0, 0, 100) # Transparent-ish
        self.lbl_leaderboard.clearBack = False # Alpha handled by bgColor
        # self.addLabel(self.lbl_leaderboard) # Assuming Scene has addLabel or addGroup
        self.groups.append(pygame.sprite.Group(self.lbl_leaderboard))

    def add_local_sprite(self, sprite):
        self.managed_sprites[sprite.sprite_id] = sprite
        self.net_sprite_group.add(sprite)

    def register_local_player(self):
        if self.local_client_id and not self.local_player:
            self.local_player = Player(self, self.player_name, is_local=True)
            self.local_player.net_id = self.local_client_id
            self.add_local_sprite(self.local_player)
            print(f"Registered local player: {self.player_name} ({self.local_client_id})")

    def process(self):
        super().process()
        self.update_leaderboard_ui()

    def die(self):
        # Respawn
        if self.local_player:
            self.local_player.x = random.randint(50, WINDOW_SIZE[0]-50)
            self.local_player.y = random.randint(50, WINDOW_SIZE[1]-50)

    def update_leaderboard_ui(self):
        lines = ["LEADERBOARD"]
        # Sort by kills
        sorted_scores = sorted(self.leaderboard.items(), key=lambda item: item[1], reverse=True)
        for name, kills in sorted_scores:
            lines.append(f"{name}: {kills}")
        self.lbl_leaderboard.textLines = lines

    def get_local_state(self):
        """Constructs the payload to send to the server."""
        if not self.local_player: return {}
        
        sprite_states = []
        to_remove = []
        for sid, sprite in self.managed_sprites.items():
            # Check if sprite is dead (removed from groups via kill()) or hidden
            # pygame.sprite.Sprite.alive() returns True if the sprite belongs to any groups.
            if not sprite.alive():
                 to_remove.append(sid)
            else:
                sprite_states.append(sprite.get_net_state())
        
        for sid in to_remove:
            del self.managed_sprites[sid]

        payload = {
            "sprites": sprite_states,
            "name": self.player_name # Send name so Host knows who we are for leaderboard
        }
        
        # If I am Host, I also include the full leaderboard and kill events
        if isinstance(self, ShooterHost):
            payload["leaderboard"] = self.leaderboard
            if self.kill_queue:
                payload["kill_events"] = self.kill_queue[:]
                self.kill_queue.clear()
            if self.destroyed_queue:
                payload["destroyed_sprites"] = self.destroyed_queue[:]
                self.destroyed_queue.clear()
            payload["client_names"] = self.client_names
            
        return payload

    def handle_network_state(self, server_state):
        # server_state: {client_id: payload_dict}
        
        current_remote_sprites = set()
        
        for client_id, payload in server_state.items():
            if client_id == self.local_client_id: continue
            if not isinstance(payload, dict): continue

            # 1. Update Sprites
            sprites = payload.get("sprites", [])
            for s_data in sprites:
                # (net_id, sprite_id, x, y, angle, color, name, type, owner_id)
                if len(s_data) < 9: continue
                owner_id, sprite_id, x, y, angle, color, name, s_type, bullet_owner = s_data
                
                current_remote_sprites.add(sprite_id)
                
                if sprite_id in self.managed_sprites:
                    # Update existing
                    s = self.managed_sprites[sprite_id]
                    s.x, s.y, s.imageAngle = x, y, angle
                    # Update visual rect
                    s.rect.center = (s.x, s.y)
                else:
                    # Create new remote sprite
                    new_s = simpleGENetworking.NetSprite(self, is_local=False)
                    new_s.net_id = owner_id
                    new_s.sprite_id = sprite_id
                    new_s.type = s_type
                    new_s.owner_id = bullet_owner
                    
                    # Setup visuals
                    if s_type == "player":
                        new_s.colorRect(color, (PLAYER_SIZE, PLAYER_SIZE))
                        # Could add name label above head?
                    elif s_type == "bullet":
                        new_s.colorRect((255, 255, 255), (BULLET_SIZE, BULLET_SIZE))
                    
                    new_s.x, new_s.y, new_s.imageAngle = x, y, angle
                    self.managed_sprites[sprite_id] = new_s
                    self.net_sprite_group.add(new_s)

            # 2. Handle Leaderboard (from Host)
            if "leaderboard" in payload:
                self.leaderboard = payload["leaderboard"]

            # 3. Handle Kill Events (from Host)
            if "kill_events" in payload:
                # Update client_names from host if available
                if "client_names" in payload:
                    self.client_names.update(payload["client_names"])

                for event in payload["kill_events"]:
                    # If I am the victim, I die
                    if event.get("victim") == self.local_client_id:
                        killer_id = event.get("killer")
                        killer_name = self.client_names.get(killer_id, "Unknown Player")
                        print(f"I was killed by {killer_name}!")
                        self.die()
                    
                    # If I am the killer, I destroy my bullet
                    if event.get("killer") == self.local_client_id:
                        bullet_id = event.get("bullet_id")
                        if bullet_id and bullet_id in self.managed_sprites:
                            # print(f"My bullet {bullet_id} hit someone! destroying it.")
                            self.managed_sprites[bullet_id].kill()
                            del self.managed_sprites[bullet_id]

        # 4. Cleanup missing remote sprites
        to_delete = []
        for sid, sprite in self.managed_sprites.items():
            if not sprite.is_local and sid not in current_remote_sprites:
                to_delete.append(sid)
        
        for sid in to_delete:
            self.managed_sprites[sid].kill()
            del self.managed_sprites[sid]

class ShooterHost(ShooterLogicMixin, simpleGENetworking.HostScene):
    def __init__(self, name, host='0.0.0.0'):
        # Default ports
        super().__init__(host=host, game_id=GAME_ID, window_size=WINDOW_SIZE)
        self.sprites = []
        self.init_game_logic(name)
        self.client_names = {} # {client_id: name}
        self.kill_queue = []

    def process(self):
        self.register_local_player()
        self.check_collisions()
        # Call Mixin's process (which calls super().process -> NetworkScene.process)
        ShooterLogicMixin.process(self)
        
    def check_collisions(self):
        players = []
        bullets = []
        
        for sprite in self.net_sprite_group:
            s_type = getattr(sprite, 'type', None)
            if s_type == "player":
                players.append(sprite)
            elif s_type == "bullet":
                bullets.append(sprite)
                
        # O(N*M) collision check
        for bullet in bullets:
            for player in players:
                # Don't shoot self
                if bullet.owner_id == player.net_id:
                    continue
                
                if bullet.rect.colliderect(player.rect):
                    # Collision detected by Host
                    self.handle_kill(player.net_id, bullet.owner_id, bullet.sprite_id)
                    bullet.kill() # Destroy bullet locally
                    break 

    def handle_kill(self, victim_id, killer_id, bullet_id=None):
        killer_name = self.client_names.get(killer_id, "Unknown")
        victim_name = self.client_names.get(victim_id, "Unknown")
        
        if killer_name in self.leaderboard:
            self.leaderboard[killer_name] += 1
        else:
            self.leaderboard[killer_name] = 1
            
        print(f"[HOST] {killer_name} killed {victim_name}")
        
        # If Host died, handle locally
        if victim_id == self.local_client_id:
            print(f"I (Host) was killed by {killer_name}!")
            self.die()
        
        self.kill_queue.append({
            "victim": victim_id, 
            "killer": killer_id,
            "bullet_id": bullet_id
        })

    def handle_network_state(self, server_state):
        super().handle_network_state(server_state)
        
        for client_id, payload in server_state.items():
            if isinstance(payload, dict) and "name" in payload:
                self.client_names[client_id] = payload["name"]
                if payload["name"] not in self.leaderboard:
                    self.leaderboard[payload["name"]] = 0

class ShooterClient(ShooterLogicMixin, simpleGENetworking.ClientScene):
    def __init__(self, name, host):
        super().__init__(host=host, game_id=GAME_ID, window_size=WINDOW_SIZE)
        self.sprites = []
        self.init_game_logic(name)

    def process(self):
        self.register_local_player()
        super().process()

def main():
    print(f"--- {GAME_ID} ---")
    name = input("Enter your name: ").strip()
    if not name: name = f"Player{random.randint(100,999)}"
    
    mode = input("Host (h) or Join (j)? ").lower()
    
    if mode.startswith('h'):
        game = ShooterHost(name)
    else:
        host_ip = input("Enter Host IP (default localhost): ").strip()
        if not host_ip: host_ip = '127.0.0.1'
        game = ShooterClient(name, host_ip)
    
    game.start()

if __name__ == "__main__":
    main()