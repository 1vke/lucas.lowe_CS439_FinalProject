import multiplayerSimpleGE
from game import RedSquare, GAME_ID, HostGameScene

def main():
    # Create the Host Scene with a specific Game ID
    game = HostGameScene(sprite_class=RedSquare, game_id=GAME_ID)
    print(f"Hosting '{GAME_ID}'...")

    if game.connection_successful:
        game.start()
    else:
        print("Failed to start host game due to connection issues.")

if __name__ == "__main__":
    main()
