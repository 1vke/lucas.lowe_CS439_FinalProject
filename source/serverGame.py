import pygame, random, multiplayerSimpleGE

def generate_random_rgb_color():
    """Generates a random RGB color as a tuple (R, G, B)."""
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    return (r, g, b)

class RedBall(multiplayerSimpleGE.NetSprite):
    def __init__(self, scene, is_local=False):
        super().__init__(scene, is_local)
        self.colorRect(generate_random_rgb_color(), (30, 30))
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
    # Create the Host Scene
    # We use the RedBall sprite for players
    game = multiplayerSimpleGE.HostScene(sprite_class=RedBall)
    game.start()

if __name__ == "__main__":
    main()