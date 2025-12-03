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
    # Create the Host Scene with a specific Game ID
    game_id = "RedBallGame"
    game = multiplayerSimpleGE.HostScene(sprite_class=RedBall, game_id=game_id)
    print(f"Hosting '{game_id}'...")
    game.start()

if __name__ == "__main__":
    main()
