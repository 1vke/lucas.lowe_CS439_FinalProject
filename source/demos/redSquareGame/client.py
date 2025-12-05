import sys, os
# Add project root to sys.path to allow absolute imports from 'source'
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from source import simpleGENetworking
from .redSquareGame import RedSquare, GAME_ID, ClientGameScene

def main():
    print(f"Looking for games with ID: '{GAME_ID}'...")
    
    # Use LANDiscoveryService to find games
    lan_discovery = simpleGENetworking.LANDiscoveryService()
    hosts = simpleGENetworking.NetManager.find_games(
        discovery_service=lan_discovery, 
        target_game_id=GAME_ID
    )
    
    game = None # Initialize game to None

    if hosts:
        host_info = hosts[0]
        print(f"Found game hosted by {host_info['name']} at {host_info['ip']}:{host_info['tcp_port']}")
        
        game = ClientGameScene(host=host_info['ip'], port=host_info['tcp_port'], sprite_class=RedSquare, game_id=GAME_ID)
    else:
        print(f"No games with ID '{GAME_ID}' found on LAN. Trying manual entry.")
        
        # Fallback to manual entry
        manual_ip = input("Enter Server IP manually (or press Enter to quit): ")
        if manual_ip:
            try:
                game = ClientGameScene(host=manual_ip, port=simpleGENetworking.DEFAULT_TCP_PORT, sprite_class=RedSquare, game_id=GAME_ID)
            except Exception as e:
                print(f"Could not connect to {manual_ip}: {e}")
        else:
            print("No server IP entered. Exiting.")
            return # Exit main if no manual IP is entered

    if game and game.connection_successful:
        game.start()
    elif game: # If game was initialized but connection failed
        print("Failed to start client game due to connection issues.")
    else: # If game was never initialized (e.g. no hosts and no manual IP)
        print("Client game not started.")

if __name__ == "__main__":
    main()
