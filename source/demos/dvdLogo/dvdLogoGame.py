"""
Game logic for the DVD Logo Networking Demo.

Defines the Host and Client scenes, the DVD Logo sprite, and the
draggable window behavior.
"""

if __name__ == "__main__":
	print("Please run launch_demo.py!")
	exit(1)

import pygame
import pygame._sdl2 as sdl2
import random
from source import simpleGENetworking

GAME_ID = "DVD Logo Demo"

class DraggableWindowMixin:
	"""
	Mixin to make a simpleGE scene window draggable by clicking and holding.
	Uses SDL2 window positioning.
	"""
	def init_draggable(self):
		self.dragging = False
		self.drag_start_mouse = (0, 0)

	def handle_drag_event(self, event):
		"""Processes mouse events to handle window dragging."""
		if event.type == pygame.MOUSEBUTTONDOWN:
			if event.button == 1: # Left click
				self.dragging = True
				self.drag_start_mouse = pygame.mouse.get_pos()
		
		elif event.type == pygame.MOUSEBUTTONUP:
			if event.button == 1:
				self.dragging = False

		elif event.type == pygame.MOUSEMOTION:
			if self.dragging:
				# Calculate mouse displacement relative to the window
				mx, my = pygame.mouse.get_pos()
				dx = mx - self.drag_start_mouse[0]
				dy = my - self.drag_start_mouse[1]
				
				# Apply displacement to current window position
				cur_win_x, cur_win_y = self.window.position
				self.window.position = (int(cur_win_x + dx), int(cur_win_y + dy))

class DVDLogo(simpleGENetworking.NetSprite):
	"""
	The bouncing DVD Logo sprite.
	"""
	def __init__(self, scene, is_local=False):
		super().__init__(scene, is_local)
		
		self.boundAction = self.CONTINUE
		
		self.current_color = pygame.Color("blue")
		self.colorRect(self.current_color, (50, 50))

		# World Coordinates and Physics (handled by Host)
		self.world_x = 0
		self.world_y = 0
		self.world_dx = 0
		self.world_dy = 0
		
		# Disable local simpleGE physics (we manually update x/y from world coords)
		self.dx = 0
		self.dy = 0
			
	def process(self):
		pass 

class DvdHostScene(DraggableWindowMixin, simpleGENetworking.HostScene):
	"""
	The Host scene (Server).
	- Simulates the physics of the DVD logo in the virtual world.
	- Broadcasts the logo's world position to all clients.
	- Acts as a draggable viewport into the virtual world.
	"""
	def __init__(self, world_size=(1200, 600), window_size=(400, 300), window_position=(0,0), host='0.0.0.0', tcp_port=12345, broadcast_port=12346, game_id=GAME_ID):
		super().__init__(host, tcp_port, broadcast_port, game_id)
		
		self._set_window_size(window_size, window_position)
		self.init_draggable()
		
		self.world_width, self.world_height = world_size
		
		# Create the DVD Logo
		self.logo = DVDLogo(self, is_local=True)
		# Initialize world position to center
		self.logo.world_x = self.world_width // 2
		self.logo.world_y = self.world_height // 2
		self.logo.world_dx = 5
		self.logo.world_dy = 5
		
		self.logo.net_id = self.local_client_id 
		self.logo.sprite_id = "dvd_logo"
		
		self.sprites = [self.logo]
		self.net_sprite_group = self.makeSpriteGroup([self.logo])
		self.addGroup(self.net_sprite_group)

	def _set_window_size(self, size, position):
		"""Sets up a borderless window and positions it explicitly."""
		self.screen = pygame.display.set_mode(size, pygame.NOFRAME)
		self.background = pygame.Surface(self.screen.get_size())
		self.background.fill((0, 0, 0))
		self.window = sdl2.Window.from_display_module()
		self.window.position = position

	def processEvent(self, event):
		self.handle_drag_event(event)
		super().processEvent(event)

	def process(self):
		# 1. Update Physics (World Space)
		logo = self.logo
		logo.world_x += logo.world_dx
		logo.world_y += logo.world_dy
		
		# 2. Check World Bounds and Bounce
		half_w = logo.rect.width / 2
		half_h = logo.rect.height / 2
		
		left = logo.world_x - half_w
		right = logo.world_x + half_w
		top = logo.world_y - half_h
		bottom = logo.world_y + half_h
		
		bounce = False
		if right > self.world_width:
			logo.world_x = self.world_width - half_w
			logo.world_dx *= -1
			bounce = True
		if left < 0:
			logo.world_x = half_w
			logo.world_dx *= -1
			bounce = True
		if bottom > self.world_height:
			logo.world_y = self.world_height - half_h
			logo.world_dy *= -1
			bounce = True
		if top < 0:
			logo.world_y = half_h
			logo.world_dy *= -1
			bounce = True
			
		if bounce:
			logo.current_color = self._random_color()
			logo.colorRect(logo.current_color, (50, 50))
		
		# 3. Project World Position to Local Screen Position
		# The window acts as a viewport: screen_pos = world_pos - window_world_pos
		# Note: We treat the window's physical screen position as its "world" position 
		# relative to the virtual coordinate system origin (0,0) at top-left of screen.
		win_x, win_y = self.window.position
		logo.x = logo.world_x - win_x
		logo.y = logo.world_y - win_y
			
		super().process()

	def _random_color(self):
		return pygame.Color(random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))

	def get_local_state(self):
		"""Returns the current state of the logo to broadcast to clients."""
		# Protocol: (net_id, sprite_id, world_x, world_y, angle, color)
		color_tuple = (self.logo.current_color.r, self.logo.current_color.g, self.logo.current_color.b)
		
		state = (
			self.logo.net_id,
			self.logo.sprite_id,
			self.logo.world_x,
			self.logo.world_y,
			self.logo.imageAngle,
			color_tuple
		)
		return [state]

class DvdClientScene(DraggableWindowMixin, simpleGENetworking.ClientScene):
	"""
	The Client scene (Viewer).
	- Receives the logo's world position from the server.
	- Renders the logo relative to its own window position.
	"""
	def __init__(self, window_size=(400, 300), window_position=(0,0), host='127.0.0.1', port=12345, game_id=GAME_ID):
		super().__init__(host, port, game_id)
		
		self._set_window_size(window_size, window_position)
		self.init_draggable()
		
		self.sprites = [] 
		self.logo_sprite = None
		self.managed_sprites = {} 
		self.net_sprite_group = self.makeSpriteGroup([])
		self.addGroup(self.net_sprite_group)

	def _set_window_size(self, size, position):
		"""Sets up a borderless window and positions it explicitly."""
		self.screen = pygame.display.set_mode(size, pygame.NOFRAME)
		self.background = pygame.Surface(self.screen.get_size())
		self.background.fill((0, 0, 0))
		self.window = sdl2.Window.from_display_module()
		self.window.position = position

	def processEvent(self, event):
		self.handle_drag_event(event)
		super().processEvent(event)

	def get_local_state(self):
		return []

	def handle_network_state(self, server_state):
		"""Updates local sprites based on server state."""
		for _, sprite_list in server_state.items():
			if not isinstance(sprite_list, list): continue
			
			for sprite_data in sprite_list:
				if len(sprite_data) < 6: continue
				owner_id, sprite_id, world_x, world_y, angle, color_tuple = sprite_data[:6]
				
				if sprite_id == "dvd_logo":
					if self.logo_sprite is None:
						self.logo_sprite = DVDLogo(self, is_local=False)
						self.logo_sprite.net_id = owner_id
						self.logo_sprite.sprite_id = sprite_id
						self.managed_sprites[sprite_id] = self.logo_sprite
						self.net_sprite_group.add(self.logo_sprite)
					
					# Update Color if changed
					new_color = pygame.Color(*color_tuple)
					if self.logo_sprite.current_color != new_color:
						self.logo_sprite.current_color = new_color
						self.logo_sprite.colorRect(new_color, (50, 50))
					
					# Project World Position to Local Screen Position
					# screen_pos = world_pos - window_pos
					win_x, win_y = self.window.position
					self.logo_sprite.x = world_x - win_x
					self.logo_sprite.y = world_y - win_y
					self.logo_sprite.imageAngle = angle