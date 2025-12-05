"""
Game logic for the DVD Logo Networking Demo.

Defines the DraggableWindowMixin, DVDLogo sprite, and the
Host (server) and Client (viewer) scenes.
"""
import pygame
import pygame._sdl2 as sdl2
import random
from source import simpleGENetworking

GAME_ID = "DVD Logo Demo"

class DraggableWindowMixin:
	"""
	Mixin to add draggable functionality to a simpleGE scene window.
	Allows users to move the borderless window by clicking and dragging.
	"""
	def init_draggable(self):
		"""Initializes dragging state variables."""
		self.dragging = False
		self.drag_start_mouse = (0, 0)

	def handle_drag_event(self, event):
		"""
		Processes mouse events to update window position during a drag operation.

		Args:
			event (pygame.event.Event): The Pygame event to process.
		"""
		if event.type == pygame.MOUSEBUTTONDOWN:
			if event.button == 1: # Left click
				self.dragging = True
				self.drag_start_mouse = pygame.mouse.get_pos()
		
		elif event.type == pygame.MOUSEBUTTONUP:
			if event.button == 1:
				self.dragging = False

		elif event.type == pygame.MOUSEMOTION:
			if self.dragging:
				mx, my = pygame.mouse.get_pos()
				dx = mx - self.drag_start_mouse[0]
				dy = my - self.drag_start_mouse[1]
				
				cur_win_x, cur_win_y = self.window.position
				self.window.position = (int(cur_win_x + dx), int(cur_win_y + dy))

class DVDLogo(simpleGENetworking.NetSprite):
	"""
	The bouncing DVD Logo sprite.
	Manages its world coordinates and color.
	"""
	def __init__(self, scene, is_local=False):
		super().__init__(scene, is_local)
		
		self.setImage("source/demos/dvdLogo/dvdLogo.png")
		
		# Resize keeping aspect ratio (target width: 100px)
		target_width = 100
		orig_w, orig_h = self.image.get_size()
		ratio = target_width / orig_w
		target_height = int(orig_h * ratio)
		self.image = pygame.transform.smoothscale(self.image, (target_width, target_height))
		self.rect = self.image.get_rect()
		
		# Create a white template for tinting
		# We store this separately so imageMaster can hold the *colored* version
		self.white_template = self.image.copy()
		self.white_template.fill((255, 255, 255, 0), special_flags=pygame.BLEND_ADD)
		
		self.boundAction = self.CONTINUE
		
		self.current_color = pygame.Color("blue")
		self.set_color(self.current_color)

		# World Coordinates and Physics attributes
		self.world_x = 0
		self.world_y = 0
		self.world_dx = 0
		self.world_dy = 0
		
		# Disable simpleGE's built-in sprite physics, as world physics is handled in the scene
		self.dx = 0
		self.dy = 0
			
	def process(self):
		"""Overrides simpleGE.Sprite.process; no local processing needed."""
		pass 

	def set_color(self, color):
		"""Applies a color tint to the sprite."""
		self.current_color = color
		
		# Create a new tinted master from the white template
		tinted_surf = self.white_template.copy()
		tinted_surf.fill(color, special_flags=pygame.BLEND_MULT)
		
		# Update imageMaster so future rotations use this color
		self.imageMaster = tinted_surf
		
		# Force update of self.image to reflect new color immediately
		# (Re-applying current rotation triggers simpleGE to rebuild self.image from self.imageMaster)
		current_angle = self.imageAngle
		self.imageAngle = current_angle

class DvdHostScene(DraggableWindowMixin, simpleGENetworking.HostScene):
	"""
	The Host scene (Server).
	- Simulates the physics of the DVD logo in the global virtual world.
	- Broadcasts the logo's world position and color to all clients.
	- Acts as a draggable viewport into the virtual world.
	"""
	def __init__(self, world_size=(1200, 600), window_size=(400, 300), window_position=(0,0), host='0.0.0.0', tcp_port=12345, broadcast_port=12346, game_id=GAME_ID):
		super().__init__(host, tcp_port, broadcast_port, game_id)
		
		self._set_window_size(window_size, window_position)
		self.init_draggable()
		
		self.world_width, self.world_height = world_size
		
		self.logo = DVDLogo(self, is_local=True)
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
		"""
		Sets up the borderless Pygame window and explicitly positions it on screen.
		"""
		self.screen = pygame.display.set_mode(size, pygame.NOFRAME)
		self.background = pygame.Surface(self.screen.get_size())
		self.background.fill((50, 0, 100))
		# Draw a white, transparent grid
		grid_color = (255, 255, 255, 50)  # White with 20% opacity (50/255)
		grid_spacing = 50  # Pixels between grid lines
		
		# Create a transparent surface for the grid
		grid_surface = pygame.Surface(size, pygame.SRCALPHA)
		
		# Draw vertical lines
		for x in range(0, size[0], grid_spacing):
			pygame.draw.line(grid_surface, grid_color, (x, 0), (x, size[1]))
		# Draw horizontal lines
		for y in range(0, size[1], grid_spacing):
			pygame.draw.line(grid_surface, grid_color, (0, y), (size[0], y))
		
		self.background.blit(grid_surface, (0, 0))
		self.window = sdl2.Window.from_display_module()
		self.window.position = position

	def processEvent(self, event):
		"""Handles Pygame events, including window dragging."""
		self.handle_drag_event(event)
		super().processEvent(event)

	def process(self):
		"""
		Updates the DVD logo's world physics and projects its position
		to the local screen coordinates based on the window's current position.
		"""
		logo = self.logo
		logo.world_x += logo.world_dx
		logo.world_y += logo.world_dy
		
		# Check world bounds and bounce
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
			logo.set_color(logo.current_color)
		
		# Project world position to local screen position
		win_x, win_y = self.window.position
		logo.x = logo.world_x - win_x
		logo.y = logo.world_y - win_y
			
		super().process()

	def _random_color(self):
		"""Generates a random Pygame color."""
		return pygame.Color(random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))

	def get_local_state(self):
		"""
		Returns the current world state of the logo for network broadcasting.
		Payload includes (net_id, sprite_id, world_x, world_y, angle, color_tuple).
		"""
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
	- Acts as a draggable viewport into the virtual world.
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
		"""Sets up the borderless Pygame window and explicitly positions it on screen."""
		self.screen = pygame.display.set_mode(size, pygame.NOFRAME)
		self.background = pygame.Surface(self.screen.get_size())
		self.background.fill((50, 0, 100))
		self.window = sdl2.Window.from_display_module()
		self.window.position = position

	def processEvent(self, event):
		"""Handles Pygame events, including window dragging."""
		self.handle_drag_event(event)
		super().processEvent(event)

	def get_local_state(self):
		"""Clients do not send local state in this demo."""
		return None

	def handle_network_state(self, server_state):
		"""
		Updates the local DVD logo sprite's position and color based on received
		world state from the server, projecting it to the client's screen space.
		"""
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
					self.logo_sprite.set_color(new_color)
					
					# Project World Position to Local Screen Position
					win_x, win_y = self.window.position
					self.logo_sprite.x = world_x - win_x
					self.logo_sprite.y = world_y - win_y
					self.logo_sprite.imageAngle = angle
