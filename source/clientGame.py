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
    print("Looking for games...")
    hosts = multiplayerSimpleGE.NetManager.find_games_on_lan()
    
    if hosts:
        host_info = hosts[0]
        print(f"Found game hosted by {host_info['name']} at {host_info['ip']}:{host_info['tcp_port']}")
        
        game = multiplayerSimpleGE.ClientScene(host=host_info['ip'], port=host_info['tcp_port'], sprite_class=RedBall)
        game.start()
    else:
        print("No games found on LAN. Make sure the server is running.")

if __name__ == "__main__":
    main()