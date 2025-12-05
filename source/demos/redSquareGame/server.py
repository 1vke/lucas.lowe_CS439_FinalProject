import sys, os
# Add project root to sys.path to allow absolute imports from 'source'
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
if project_root not in sys.path:
	sys.path.insert(0, project_root)

from source import simpleGENetworking
from .redSquareGame import RedSquare, GAME_ID, HostGameScene

def main():
	# Create the Host Scene with a specific Game ID
	game = HostGameScene(sprite_class=RedSquare, game_id=GAME_ID, discovery_service=simpleGENetworking.LANDiscoveryService())
	print(f"Hosting '{GAME_ID}'...")

	if game.connection_successful:
		game.start()
	else:
		print("Failed to start host game due to connection issues.")

if __name__ == "__main__":
	main()
