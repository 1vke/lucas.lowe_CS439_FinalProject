"""
Launcher script for the DVD Logo Networking Demo.

This script calculates the screen layout based on the current monitor resolution,
accounts for OS menu bars, and spawns multiple subprocesses (one Host, multiple Clients)
arranged in a grid to create a unified virtual display.
"""

import subprocess
import sys
import os
import time
import pygame

# This is a safe amount of games for a Macbook Air M2, 16 GB of ram. I have tested up to 7 x 7. 
# It works, sometimes. The third time I tried this I broke the interpreter and got a bad memory 
# access error, so beware XD
GRID_COLS = 3
GRID_ROWS = 2

current_dir = os.path.dirname(os.path.abspath(__file__))
runner_script = os.path.join(current_dir, "run_node.py")

processes = []

def launch_process(mode, col, row, screen_x, screen_y, width, height, world_width, world_height):
	"""
	Launches a single game node (Host or Client) as a subprocess.

	Args:
		mode (str): 'host' or 'client'.
		col (int): Grid column index (for logging).
		row (int): Grid row index (for logging).
		screen_x (int): Absolute X position on the physical screen.
		screen_y (int): Absolute Y position on the physical screen.
		width (int): Window width.
		height (int): Window height.
		world_width (int): Total width of the virtual world.
		world_height (int): Total height of the virtual world.
	"""
	env = os.environ.copy()
	env["SDL_VIDEO_WINDOW_POS"] = f"{screen_x},{screen_y}"
	
	cmd = [
		sys.executable, runner_script, 
		"--mode", mode, 
		"--width", str(width),
		"--height", str(height),
		"--world-width", str(world_width),
		"--world-height", str(world_height),
		"--screen-x", str(screen_x),
		"--screen-y", str(screen_y)
	]
	if mode == "client":
		cmd.extend(["--target-ip", "127.0.0.1"])
	
	print(f"Launching {mode.upper()} at Grid({col},{row}) Screen({screen_x},{screen_y}) Size({width}x{height})")
	
	p = subprocess.Popen(cmd, env=env)
	processes.append(p)

def main():
	"""
	Main entry point. Detects screen size, calculates layout, and manages subprocesses.
	"""
	print("Starting DVD Logo Networking Demo...")
	print("Press Ctrl+C to stop all windows.")
	
	pygame.init()
	info = pygame.display.Info()
	screen_w = info.current_w
	screen_h = info.current_h
	
	# Account for macOS menu bar or similar top bars
	Y_OFFSET = 30 
	
	usable_height = screen_h - Y_OFFSET
	window_width = screen_w // GRID_COLS
	window_height = usable_height // GRID_ROWS
	
	world_width = window_width * GRID_COLS
	world_height = window_height * GRID_ROWS
	
	print(f"Detected Screen Size: {screen_w}x{screen_h}")
	print(f"Usable Height (minus offset): {usable_height}")
	print(f"Calculated Window Size: {window_width}x{window_height}")
	print(f"Total World Size: {world_width}x{world_height}")
	
	screen_start_x = 0
	screen_start_y = Y_OFFSET
	
	try:
		# Launch Host First (Top-Left)
		launch_process(
			"host", 0, 0, 
			screen_start_x, screen_start_y, 
			window_width, window_height, 
			world_width, world_height
		)
		
		for row in range(GRID_ROWS):
			for col in range(GRID_COLS):
				# Skip the host we just launched
				if col == 0 and row == 0:
					continue
				
				screen_x = screen_start_x + (col * window_width)
				screen_y = screen_start_y + (row * window_height)
				
				launch_process(
					"client", col, row, 
					screen_x, screen_y, 
					window_width, window_height, 
					world_width, world_height
				)
				
		# Keep main script alive to monitor
		while True:
			time.sleep(1)
			all_dead = True
			for p in processes:
				if p.poll() is None:
					all_dead = False
					break
			if all_dead:
				print("All processes exited.")
				break

	except KeyboardInterrupt:
		print("\nStopping all processes...")
	finally:
		for p in processes:
			if p.poll() is None:
				p.terminate()
		pygame.quit()

if __name__ == "__main__":
	main()