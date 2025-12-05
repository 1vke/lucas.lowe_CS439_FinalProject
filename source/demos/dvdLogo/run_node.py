"""
Node runner script for the DVD Logo Networking Demo.

This script launches a single game instance, either as a host (server + local view)
or as a client (remote view), configured by command-line arguments.
It handles Pygame initialization, window sizing and positioning, and network connection.
"""

import sys
import os
import time
import argparse
import pygame

# Setup path to allow absolute imports from 'source'
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
if project_root not in sys.path:
	sys.path.insert(0, project_root)

from source import simpleGENetworking
from source.demos.dvdLogo.dvdLogoGame import DvdHostScene, DvdClientScene, GAME_ID

def main():
	"""
	Main entry point for running a single game node.
	Parses command-line arguments and initializes either a Host or Client scene.
	"""
	parser = argparse.ArgumentParser(description="Run a single DVD Logo demo node.")
	parser.add_argument("--mode", choices=["host", "client"], required=True,
						help="Mode to run the node in: 'host' (server) or 'client'.")
	parser.add_argument("--target-ip", type=str, default="127.0.0.1",
						help="IP address of the host server (client mode only).")
	parser.add_argument("--width", type=int, default=400,
						help="Width of the game window.")
	parser.add_argument("--height", type=int, default=300,
						help="Height of the game window.")
	parser.add_argument("--world-width", type=int, default=1200,
						help="Total width of the virtual game world.")
	parser.add_argument("--world-height", type=int, default=600,
						help="Total height of the virtual game world.")
	parser.add_argument("--screen-x", type=int, default=0,
						help="Initial X position of the window on the physical screen.")
	parser.add_argument("--screen-y", type=int, default=0,
						help="Initial Y position of the window on the physical screen.")
	args = parser.parse_args()

	pygame.init()
	
	if args.mode == "host":
		print(f"Starting HOST window at Screen({args.screen_x},{args.screen_y}) with size {args.width}x{args.height}")
		scene = DvdHostScene(
			world_size=(args.world_width, args.world_height),
			window_size=(args.width, args.height),
			window_position=(args.screen_x, args.screen_y),
			game_id=GAME_ID
		)
		scene.start()

	elif args.mode == "client":
		print(f"Starting CLIENT window at Screen({args.screen_x},{args.screen_y}) with size {args.width}x{args.height}")
		
		connected = False
		attempts = 0
		max_attempts = 20
		
		while not connected and attempts < max_attempts:
			try:
				print(f"Connecting to {args.target_ip}... (Attempt {attempts+1}/{max_attempts})")
				scene = DvdClientScene(
					window_size=(args.width, args.height),
					window_position=(args.screen_x, args.screen_y),
					host=args.target_ip,
					port=simpleGENetworking.DEFAULT_TCP_PORT,
					game_id=GAME_ID
				)
				
				if scene.connection_successful:
					connected = True
					scene.start()
				else:
					print("Connection failed, retrying...")
					time.sleep(0.5)
					attempts += 1
			except Exception as e:
				print(f"Error during connection attempt: {e}, retrying...")
				time.sleep(0.5)
				attempts += 1
				
		if not connected:
			print("Could not connect to host after multiple attempts. Exiting client.")

if __name__ == "__main__":
	main()
