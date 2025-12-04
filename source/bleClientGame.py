import multiplayerSimpleGE
from game import RedSquare, GAME_ID, ClientGameScene

def main():
    print(f"Scanning for BLE games with ID: '{GAME_ID}'...")
    
    ble_discovery = multiplayerSimpleGE.BLEDiscoveryService()
    hosts = multiplayerSimpleGE.NetManager.find_games(
        discovery_service=ble_discovery, 
        target_game_id=GAME_ID,
        timeout=5.0
    )
    
    game = None

    if hosts:
        # Note: BLEDiscoveryService might return hosts without valid IP/Port 
        # if it can't parse Manufacturer Data.
        host_info = hosts[0]
        ip = host_info.get('ip')
        port = host_info.get('tcp_port')
        
        if ip and port:
            print(f"Found BLE game hosted by {host_info['name']} at {ip}:{port}")
            game = ClientGameScene(host=ip, port=port, sprite_class=RedSquare, game_id=GAME_ID)
        else:
            print(f"Found BLE device '{host_info['name']}' but IP/Port data is missing.")
    else:
        print(f"No BLE games found.")
        
    if not game:
        print("Trying manual entry as fallback.")
        manual_ip = input("Enter Server IP manually (or press Enter to quit): ")
        if manual_ip:
            try:
                game = ClientGameScene(host=manual_ip, port=multiplayerSimpleGE.DEFAULT_TCP_PORT, sprite_class=RedSquare, game_id=GAME_ID)
            except Exception as e:
                print(f"Could not connect to {manual_ip}: {e}")
        else:
            print("No server IP entered. Exiting.")
            return

    if game and game.connection_successful:
        game.start()
    elif game:
        print("Failed to start client game due to connection issues.")
    else:
        print("Client game not started.")

if __name__ == "__main__":
    main()
