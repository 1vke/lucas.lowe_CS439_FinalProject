import multiplayerSimpleGE
from game import RedBall, GAME_ID, HostGameScene

def main():
    # Create the Host Scene with a specific Game ID
    game = HostGameScene(sprite_class=RedBall, game_id=GAME_ID)
    print(f"Hosting '{GAME_ID}'...")
    game.start()

if __name__ == "__main__":
    main()