import pygame, multiplayerSimpleGE

class RedBall(multiplayerSimpleGE.NetSprite):
    def __init__(self, scene, is_local=False):
        super().__init__(scene, is_local)
        self.image = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (255, 0, 0), (15, 15), 15)
        self.imageMaster = self.image
        self.rect = self.image.get_rect()
        self.moveSpeed = 5

    def process(self):
        if self.is_local:
            if self.isKeyPressed(pygame.K_LEFT):
                self.x -= self.moveSpeed
            if self.isKeyPressed(pygame.K_RIGHT):
                self.x += self.moveSpeed
            if self.isKeyPressed(pygame.K_UP):
                self.y -= self.moveSpeed
            if self.isKeyPressed(pygame.K_DOWN):
                self.y += self.moveSpeed

def main():
    game_id = "RedBallGame"
    print(f"Looking for games with ID: '{game_id}'...")
    hosts = multiplayerSimpleGE.NetManager.find_games_on_lan(target_game_id=game_id)
    
    if hosts:
        host_info = hosts[0]
        print(f"Found game hosted by {host_info['name']} at {host_info['ip']}:{host_info['tcp_port']}")
        
        game = multiplayerSimpleGE.ClientScene(host=host_info['ip'], port=host_info['tcp_port'], sprite_class=RedBall, game_id=game_id)
        game.start()
    else:
        print(f"No games with ID '{game_id}' found on LAN. Make sure the correct server is running.")

if __name__ == "__main__":
    main()
