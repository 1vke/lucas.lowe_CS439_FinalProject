import multiplayerSimpleGE
from game import RedBall, GAME_ID, ClientGameScene

def main():
    print(f"Looking for games with ID: '{GAME_ID}'...")
    hosts = multiplayerSimpleGE.NetManager.find_games_on_lan(target_game_id=GAME_ID)
    
    if hosts:
        host_info = hosts[0]
        print(f"Found game hosted by {host_info['name']} at {host_info['ip']}:{host_info['tcp_port']}")
        
        game = ClientGameScene(host=host_info['ip'], port=host_info['tcp_port'], sprite_class=RedBall, game_id=GAME_ID)
        game.start()
    else:
        print(f"No games with ID '{GAME_ID}' found on LAN. Make sure the correct server is running.")
        
        # Fallback to manual entry
        manual_ip = input("Enter Server IP manually (or press Enter to quit): ")
        if manual_ip:
            try:
                game = ClientGameScene(host=manual_ip, port=12345, sprite_class=RedBall, game_id=GAME_ID)
                game.start()
            except Exception as e:
                print(f"Could not connect to {manual_ip}: {e}")

if __name__ == "__main__":
    main()