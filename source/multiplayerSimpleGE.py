"""
multiplayerSimpleGE.py (Pickle + Length-Prefix Framing + Game ID Validation)

Extends simpleGE with a simple client-server multiplayer framework.
Uses 'pickle' for serialization and 4-byte length headers for robust TCP streaming.
Includes Game ID validation to prevent mismatching connections.
"""

from simpleGE import simpleGE
import socket
import threading
import pickle
import struct
import uuid
import time

# --- Network Helper Functions ---

def send_msg(sock, data):
    """Pickles data and sends it with a 4-byte length header."""
    try:
        msg = pickle.dumps(data)
        # >I = big-endian unsigned int (4 bytes)
        msg = struct.pack('>I', len(msg)) + msg
        sock.sendall(msg)
    except (ConnectionError, OSError):
        pass

def recv_msg(sock):
    """Receives a length header and then the pickled payload."""
    try:
        # Read 4-byte length
        raw_msglen = recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the data
        data = recvall(sock, msglen)
        if not data:
            return None
        return pickle.loads(data)
    except (ConnectionError, OSError, pickle.UnpicklingError):
        return None

def recvall(sock, n):
    """Helper to ensure exactly n bytes are read from the socket."""
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

# --- Classes ---

class NetManager:
    """A utility class for network-related operations, like discovering games."""
    @staticmethod
    def find_games_on_lan(target_game_id="simpleGE_Game", broadcast_port=12346, timeout=3):
        """
        Listens for game broadcasts (UDP) on the local network.
        Returns a list of discovered hosts matching the target_game_id.
        """
        discovered_hosts = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(1.0)
        
        try:
            sock.bind(('', broadcast_port))
            print(f"Searching for games ('{target_game_id}') on LAN for {timeout}s...")
            
            end_time = time.time() + timeout
            while time.time() < end_time:
                try:
                    data, addr = sock.recvfrom(4096)
                    # UDP packets are discrete, so simple pickle.loads works
                    message = pickle.loads(data)
                    
                    # Filter by Game ID
                    if message.get("game_id") == target_game_id:
                        host_info = {
                            "name": message.get("host_name", addr[0]),
                            "ip": addr[0],
                            "tcp_port": message.get("tcp_port"),
                            "game_id": message.get("game_id")
                        }
                        # Avoid duplicates
                        if not any(h['ip'] == host_info['ip'] and h['tcp_port'] == host_info['tcp_port'] for h in discovered_hosts):
                            discovered_hosts.append(host_info)
                            print(f"Found: {host_info['name']} at {host_info['ip']}:{host_info['tcp_port']}")
                except socket.timeout:
                    continue
                except (pickle.UnpicklingError, EOFError, KeyError):
                    continue
        finally:
            sock.close()

        if not discovered_hosts:
            print("No matching games found.")
        return discovered_hosts

class Server:
    """Encapsulates all server-side logic, state, and networking."""
    def __init__(self, host, tcp_port, broadcast_port, game_id="simpleGE_Game"):
        self.host = host
        self.tcp_port = tcp_port
        self.broadcast_port = broadcast_port
        self.game_id = game_id
        self.game_state = {"clients": {}}
        self.clients = []
        self.lock = threading.Lock()

    def start(self):
        threading.Thread(target=self._run_tcp_server, daemon=True).start()
        threading.Thread(target=self._run_udp_broadcast, daemon=True).start()

    def _run_tcp_server(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.tcp_port))
        server_socket.listen()
        print(f"Game server ('{self.game_id}') listening on {self.host}:{self.tcp_port}")
        while True:
            client_sock, _ = server_socket.accept()
            handler = threading.Thread(target=self._handle_client_connection, args=(client_sock,))
            handler.daemon = True
            handler.start()

    def _run_udp_broadcast(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        print(f"Broadcasting presence on UDP port {self.broadcast_port}")
        while True:
            message = {
                "game_id": self.game_id,
                "host_name": socket.gethostname(),
                "tcp_port": self.tcp_port
            }
            try:
                sock.sendto(pickle.dumps(message), ('<broadcast>', self.broadcast_port))
            except Exception as e:
                print(f"Broadcast error: {e}")
            time.sleep(2)

    def _handle_client_connection(self, client_sock):
        # 1. Receive Client Handshake (Game ID check)
        try:
            handshake = recv_msg(client_sock)
            if not handshake or handshake.get("game_id") != self.game_id:
                print(f"Connection rejected: Game ID mismatch. Expected {self.game_id}, got {handshake.get('game_id')}")
                client_sock.close()
                return
        except Exception as e:
            print(f"Handshake error: {e}")
            client_sock.close()
            return

        # 2. Assign ID and Accept
        client_id = str(uuid.uuid4())
        with self.lock:
            self.clients.append(client_sock)
        
        # Send ID assignment
        send_msg(client_sock, {"type": "id_assignment", "id": client_id})

        print(f"Client {client_id} connected.")
        try:
            while True:
                client_data = recv_msg(client_sock)
                if client_data is None: 
                    break
                
                with self.lock:
                    self.game_state.setdefault("clients", {})[client_id] = client_data
                
                self._broadcast_game_state()
        except Exception as e:
            print(f"Error handling client {client_id}: {e}")
        finally:
            with self.lock:
                if client_sock in self.clients: 
                    self.clients.remove(client_sock)
                if client_id in self.game_state.get("clients", {}): 
                    del self.game_state["clients"][client_id]
            
            client_sock.close()
            print(f"Client {client_id} disconnected.")
            self._broadcast_game_state()

    def _broadcast_game_state(self):
        with self.lock:
            if not self.clients: return
            # Prepare data once
            try:
                msg = pickle.dumps(self.game_state)
                header = struct.pack('>I', len(msg))
                full_msg = header + msg
                
                for client_sock in self.clients[:]:
                    try:
                        client_sock.sendall(full_msg)
                    except Exception:
                        # Connection dead, will be cleaned up by the handler thread
                        pass
            except Exception as e:
                print(f"Broadcast error: {e}")

class NetSprite(simpleGE.Sprite):
    def __init__(self, scene, is_local=False):
        super().__init__(scene)
        self.net_id = None
        self.is_local = is_local
        if not self.is_local: self.hide()

    def get_net_state(self):
        return {"x": self.x, "y": self.y, "image_angle": self.imageAngle}

    def set_net_state(self, state):
        if not self.visible: self.show()
        self.x = state.get("x", self.x)
        self.y = state.get("y", self.y)
        self.imageAngle = state.get("image_angle", self.imageAngle)

class NetworkScene(simpleGE.Scene):
    def __init__(self, host, port, sprite_class=NetSprite, game_id="simpleGE_Game"):
        super().__init__()
        self.host = host
        self.port = port
        self.sprite_class = sprite_class
        self.game_id = game_id
        self.client = None
        self.remote_sprites = {}
        self.remote_player_group = self.makeSpriteGroup([])
        self.addGroup(self.remote_player_group)
        self.local_player = self.sprite_class(self, is_local=True)
        self.sprites = [self.local_player]
    
    def process(self):
        self._update_from_network()
        self._send_local_state()

    def _update_from_network(self):
        if not self.client: return
        
        state = self.client.get_latest_state()
        if not state: return

        client_data_dict = state.get("clients", {})
        server_client_ids = set(client_data_dict.keys())
        local_known_ids = set(self.remote_sprites.keys())

        # Add new remote sprites
        for client_id in server_client_ids - local_known_ids:
            if client_id != self.local_player.net_id:
                new_sprite = self.sprite_class(self, is_local=False)
                self.remote_sprites[client_id] = new_sprite
                self.remote_player_group.add(new_sprite)

        # Update existing remote sprites
        for client_id, sprite in self.remote_sprites.items():
            if client_id in client_data_dict:
                sprite.set_net_state(client_data_dict[client_id])
        
        # Remove disconnected remote sprites
        for client_id in local_known_ids - server_client_ids:
            self.remote_sprites[client_id].kill()
            del self.remote_sprites[client_id]

    def _send_local_state(self):
        if self.client and self.local_player.net_id:
            self.client.send_data(self.local_player.get_net_state())

    def stop(self):
        if self.client: self.client.stop()
        super().stop()

class HostScene(NetworkScene):
    def __init__(self, host='0.0.0.0', tcp_port=12345, broadcast_port=12346, sprite_class=NetSprite, game_id="simpleGE_Game"):
        self.server = Server(host, tcp_port, broadcast_port, game_id)
        self.server.start()
        # Connect as a client to our own server
        super().__init__('127.0.0.1', tcp_port, sprite_class, game_id)
        self.setCaption(f"{game_id} (HOST)")
        self.client = Client('127.0.0.1', tcp_port, game_id)
        
        # Wait briefly for ID assignment
        start = time.time()
        while not self.client.id and time.time() - start < 1.0:
            time.sleep(0.05)
            
        if self.client.id:
             self.local_player.net_id = self.client.id

class ClientScene(NetworkScene):
    def __init__(self, host, port=12345, sprite_class=NetSprite, game_id="simpleGE_Game"):
        super().__init__(host, port, sprite_class, game_id)
        self.setCaption(f"{game_id} (Client at {host})")
        self.client = Client(self.host, port, game_id)
        
        # Wait briefly for ID assignment
        start = time.time()
        while not self.client.id and time.time() - start < 1.0:
            time.sleep(0.05)

        if self.client.id:
            self.local_player.net_id = self.client.id

class Client:
    def __init__(self, host, port, game_id="simpleGE_Game"):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.id = None
        self.game_id = game_id
        self.latest_state = {}
        self.lock = threading.Lock()
        try:
            self.socket.connect((host, port))
            
            # Send handshake
            send_msg(self.socket, {"game_id": self.game_id})
            
            threading.Thread(target=self._receive_data, daemon=True).start()
        except ConnectionRefusedError:
            print(f"Connection refused at {host}:{port}. Is a host running?")
            self.socket = None
            
    def _receive_data(self):
        print("Connected to server. Receiving data...")
        while self.socket:
            state = recv_msg(self.socket)
            if state is None:
                break
            
            if state.get("type") == "id_assignment":
                with self.lock:
                    self.id = state.get("id")
                    print(f"Assigned Player ID: {self.id}")
            else:
                with self.lock: 
                    self.latest_state = state
        print("Disconnected from server.")

    def send_data(self, data):
        if self.socket:
            send_msg(self.socket, data)

    def get_latest_state(self):
        with self.lock: return self.latest_state.copy()

    def stop(self):
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
            self.socket = None