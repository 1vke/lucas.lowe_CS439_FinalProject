import multiplayerSimpleGE
from game import RedSquare, GAME_ID, HostGameScene

def main():
    print(f"Starting BLE Host for '{GAME_ID}'...")
    
    # Use BLEDiscoveryService
    # Note: As of now, Bleak primarily supports the Central role (Client scanning).
    # This service will log that advertising is not supported, but the TCP/UDP server 
    # will still start on the specified ports.
    ble_discovery = multiplayerSimpleGE.BLEDiscoveryService()
    
    game = HostGameScene(
        sprite_class=RedSquare, 
        game_id=GAME_ID,
        discovery_service=ble_discovery
    )
    
    print(f"Hosting '{GAME_ID}' (BLE Advertising placeholder)...")

    if game.connection_successful:
        game.start()
    else:
        print("Failed to start host game due to connection issues.")

if __name__ == "__main__":
    main()
