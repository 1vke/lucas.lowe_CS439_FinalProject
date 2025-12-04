import pygame
import multiplayerSimpleGE

GAME_ID = "Red Square Game"
VERBOSE = False

class RedSquare(multiplayerSimpleGE.NetSprite):
    def __init__(self, scene, is_local=False):
        super().__init__(scene, is_local)
        self.colorRect(pygame.Color("red"), (30, 30))
        self.moveSpeed = 5

    def process(self):
        if self.is_local:
            if self.isKeyPressed(pygame.K_LEFT):
                self.x -= self.moveSpeed
            if self.isKeyPressed(pygame.K_RIGHT):
                self.x += self.moveSpeed
            if self.isKeyPressed(pygame.K_UP):
                self.y -= self.moveSpeed
            if self.isKeyPressed(pygame.K_DOWN):
                self.y += self.moveSpeed

class GameLogicMixin:
    """Mixin to add sprite management logic to Host/Client scenes."""
    def init_game_logic(self, sprite_class):
        self.sprite_class = sprite_class
        self.managed_sprites = {} # sprite_id -> NetSprite
        self.net_sprite_group = self.makeSpriteGroup([])
        self.addGroup(self.net_sprite_group)

        # Initialize local player
        self.local_player = self.sprite_class(self, is_local=True)
        # Note: local_player is NOT added to managed_sprites yet, waiting for ID assignment
        self.sprites = [self.local_player]

    def register_local_player(self):
        if self.local_client_id:
            self.local_player.net_id = self.local_client_id
            self.managed_sprites[self.local_player.sprite_id] = self.local_player
            if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): Registered local player {self.local_player.sprite_id}. Managed sprites: {list(self.managed_sprites.keys())}")
        else:
            if VERBOSE: print(f"GameLogicMixin (Pending ID): Cannot register local player, local_client_id not yet set.")

    def get_local_state(self):
        """Returns a list of states for all local sprites."""
        local_updates = []
        for sprite_id, sprite in self.managed_sprites.items():
            if sprite.is_local:
                local_updates.append(sprite.get_net_state())
        if local_updates:
            if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): Sending local state: {local_updates}")
            return local_updates
        if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): No local state to send (managed_sprites might be empty or no local sprites).")
        return None

    def handle_network_state(self, server_state):
        """
        server_state is a dict: { client_id: [ (net_id, sprite_id, x, y, angle), ... ] }
        """
        if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): Handling network state. Full state: {server_state}")
        # 1. Collect all currently reported sprite IDs from the server
        current_server_sprite_ids = set()
        
        for client_id_from_server, sprite_list in server_state.items():
            # If the client_id_from_server is our own local client_id, we ignore it because we already control those sprites.
            if client_id_from_server == self.local_client_id:
                if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): Skipping own client_id {client_id_from_server}")
                continue

            if not isinstance(sprite_list, list): # Check if the payload is actually a list of sprite data
                if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): Warning: Expected list of sprites for client {client_id_from_server}, got {type(sprite_list)}. Payload: {sprite_list}")
                continue

            for sprite_data in sprite_list:
                # Unpack data
                if not (isinstance(sprite_data, (list, tuple)) and len(sprite_data) >= 5):
                    if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): Warning: Malformed sprite_data received from {client_id_from_server}: {sprite_data}")
                    continue
                    
                owner_id, sprite_id, x, y, angle = sprite_data
                current_server_sprite_ids.add(sprite_id)
                if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): Processing sprite {sprite_id} from {owner_id} with data ({x}, {y}, {angle})")

                # Update or Create Sprite
                if sprite_id in self.managed_sprites:
                    sprite = self.managed_sprites[sprite_id]
                    if not sprite.is_local: # Ensure we don't update our local sprites from remote state
                        sprite.set_net_state((x, y, angle))
                        if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): Updated existing remote sprite {sprite_id}")
                else:
                    # Create new remote sprite
                    if owner_id != self.local_client_id:
                        if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): Creating new remote sprite {sprite_id} from {owner_id}")
                        new_sprite = self.sprite_class(self, is_local=False)
                        new_sprite.net_id = owner_id
                        new_sprite.sprite_id = sprite_id
                        new_sprite.set_net_state((x, y, angle))
                        self.managed_sprites[sprite_id] = new_sprite
                        self.net_sprite_group.add(new_sprite)

        # 2. Remove remote sprites that are no longer in the server state
        sprites_to_remove_ids = []
        for sprite_id, sprite in self.managed_sprites.items():
            if not sprite.is_local and sprite_id not in current_server_sprite_ids:
                sprites_to_remove_ids.append(sprite_id)

        if sprites_to_remove_ids:
            if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): Removing sprites: {sprites_to_remove_ids}")
            for sprite_id in sprites_to_remove_ids:
                sprite = self.managed_sprites[sprite_id]
                sprite.kill() # Remove from simpleGE scene
                del self.managed_sprites[sprite_id]
        else:
            if VERBOSE: print(f"GameLogicMixin ({self.local_client_id}): No sprites to remove.")

    def on_server_disconnect(self):
        """Handle server disconnection specifically for this game."""
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!!!!!!!!!!!!!!! SERVER DISCONNECTED !!!!!!!!!!!!!!!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        self.stop()

class HostGameScene(GameLogicMixin, multiplayerSimpleGE.HostScene):
    def __init__(self, host='0.0.0.0', tcp_port=12345, broadcast_port=12346, sprite_class=RedSquare, game_id=GAME_ID, discovery_service=None):
        super().__init__(host, tcp_port, broadcast_port, game_id, discovery_service=discovery_service)
        self.init_game_logic(sprite_class)
        self.register_local_player()

class ClientGameScene(GameLogicMixin, multiplayerSimpleGE.ClientScene):
    def __init__(self, host, port=12345, sprite_class=RedSquare, game_id=GAME_ID):
        super().__init__(host, port, game_id)
        self.init_game_logic(sprite_class)
        self.register_local_player()