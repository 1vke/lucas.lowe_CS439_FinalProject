"""
multiplayerSimpleGE.py (Hybrid TCP/UDP + Struct Packing)

Extends simpleGE with a client-server multiplayer framework.
- TCP: Used for connection setup, ID assignment, and exchanging UDP ports.
- UDP: Used for fast, real-time movement updates using 'struct' for binary packing.
"""

try:
    from simpleGE import simpleGE
except ImportError:
    import simpleGE

import socket
import threading
import pickle
import struct
import uuid
import time

# --- Binary Packing Config ---
# Format: UUID (36 bytes) + X (float) + Y (float) + Angle (float)
# 36s = 36 char string, f = float (4 bytes)
# Total size = 36 + 4 + 4 + 4 = 48 bytes per update
PACKET_FMT = '36sfff'
PACKET_SIZE = struct.calcsize(PACKET_FMT)

# --- Network Helper Functions ---

def send_tcp_msg(sock, data):
    """Pickles data and sends it with a 4-byte length header over TCP."""
    try:
        msg = pickle.dumps(data)
        msg = struct.pack('>I', len(msg)) + msg
        sock.sendall(msg)
    except (ConnectionError, OSError):
        pass

def recv_tcp_msg(sock):
    """Receives a length header and then the pickled payload over TCP."""
    try:
        raw_msglen = recvall(sock, 4)
        if not raw_msglen: return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        data = recvall(sock, msglen)
        if not data: return None
        return pickle.loads(data)
    except (ConnectionError, OSError, pickle.UnpicklingError):
        return None

def recvall(sock, n):
    """Helper to ensure exactly n bytes are read."""
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet: return None
        data += packet
    return data

# --- Classes ---

class NetManager:
    @staticmethod
    def find_games_on_lan(target_game_id="simpleGE_Game", broadcast_port=12346, timeout=3):
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
                    message = pickle.loads(data)
                    if message.get("game_id") == target_game_id:
                        host_info = {
                            "name": message.get("host_name", addr[0]),
                            "ip": addr[0],
                            "tcp_port": message.get("tcp_port"),
                            "game_id": message.get("game_id")
                        }
                        if not any(h['ip'] == host_info['ip'] and h['tcp_port'] == host_info['tcp_port'] for h in discovered_hosts):
                            discovered_hosts.append(host_info)
                            print(f"Found: {host_info['name']} at {host_info['ip']}:{host_info['tcp_port']}")
                except socket.timeout: continue
                except (pickle.UnpicklingError, EOFError, KeyError): continue
        finally:
            sock.close()
        if not discovered_hosts: print("No matching games found.")
        return discovered_hosts

class Server:
    def __init__(self, host, tcp_port, broadcast_port, game_id="simpleGE_Game"):
        self.host = host
        self.tcp_port = tcp_port
        self.broadcast_port = broadcast_port
        self.game_id = game_id
        
        self.game_state = {"clients": {}}
        self.client_map = {} # Maps client_id -> (IP, UDP_Port)
        self.clients_tcp = []
        
        self.lock = threading.Lock()
        self.running = True

        # Initialize UDP Socket
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind((self.host, 0)) # Bind to ephemeral port
        self.udp_port = self.udp_sock.getsockname()[1]

    def start(self):
        threading.Thread(target=self._run_tcp_server, daemon=True).start()
        threading.Thread(target=self._run_udp_listener, daemon=True).start()
        threading.Thread(target=self._run_udp_broadcast, daemon=True).start()
        print(f"Server UDP listening on port {self.udp_port}")

    def _run_tcp_server(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.tcp_port))
        server_sock.listen()
        print(f"Game server ('{self.game_id}') listening on {self.host}:{self.tcp_port}")
        
        while self.running:
            try:
                client_sock, _ = server_sock.accept()
                threading.Thread(target=self._handle_client_tcp, args=(client_sock,), daemon=True).start()
            except OSError: break

    def _run_udp_listener(self):
        """Receives binary packed movement updates from clients."""
        while self.running:
            try:
                data, addr = self.udp_sock.recvfrom(1024)
                if len(data) == PACKET_SIZE:
                    # Unpack: UUID (36s), x (f), y (f), angle (f)
                    uid_bytes, x, y, angle = struct.unpack(PACKET_FMT, data)
                    client_id = uid_bytes.decode().strip('\x00')
                    
                    with self.lock:
                        # Store UDP address for broadcasting back
                        if client_id not in self.client_map:
                            self.client_map[client_id] = addr
                            
                        # Update State
                        self.game_state["clients"][client_id] = {
                            "x": x, "y": y, "image_angle": angle
                        }
                        
                    # Immediately broadcast update to others (via UDP)
                    self._broadcast_udp_state()
            except OSError: break

    def _broadcast_udp_state(self):
        """Packs entire game state and blasts it to all known UDP clients."""
        # Note: For many clients, this loop should be smarter (don't send everything to everyone)
        # For simplicity, we pickle the WHOLE state for downstream updates 
        # (Client -> Server is Struct, Server -> Client is Pickle for simplicity/flexibility 
        # unless we want to implement a complex binary protocol for the full state list).
        # To keep it strictly struct, we'd need to loop and pack every player.
        
        # Optimization: Let's stick to Pickle for Server->Client Broadcast for now 
        # because the client list is dynamic length.
        
        try:
            with self.lock:
                if not self.client_map: return
                # We use pickle here because the list of players varies size
                payload = pickle.dumps(self.game_state)
                
                for cid, addr in self.client_map.items():
                    self.udp_sock.sendto(payload, addr)
        except Exception: pass

    def _handle_client_tcp(self, client_sock):
        """Handles handshake: Checks ID, exchanges UDP ports."""
        try:
            # 1. Handshake
            handshake = recv_tcp_msg(client_sock)
            if not handshake or handshake.get("game_id") != self.game_id:
                client_sock.close()
                return

            client_id = str(uuid.uuid4())
            with self.lock: self.clients_tcp.append(client_sock)

            # 2. Send Assigned ID + Server UDP Port
            send_tcp_msg(client_sock, {
                "type": "id_assignment",
                "id": client_id,
                "udp_port": self.udp_port
            })
            
            print(f"Client {client_id} connected via TCP.")

            # 3. Keep TCP open for lifecycle events (ping/disconnect)
            while True:
                msg = recv_tcp_msg(client_sock)
                if msg is None: break 
                # Handle other TCP messages (chat, etc) if needed
                
        except Exception as e:
            print(f"TCP Error {client_id}: {e}")
        finally:
            with self.lock:
                if client_sock in self.clients_tcp: self.clients_tcp.remove(client_sock)
                if client_id in self.game_state["clients"]: del self.game_state["clients"][client_id]
                if client_id in self.client_map: del self.client_map[client_id]
            client_sock.close()
            print(f"Client {client_id} disconnected.")

    def _run_udp_broadcast(self):
        """Discovery broadcast."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self.running:
            msg = {"game_id": self.game_id, "host_name": socket.gethostname(), "tcp_port": self.tcp_port}
            try: sock.sendto(pickle.dumps(msg), ('<broadcast>', self.broadcast_port))
            except: pass
            time.sleep(2)

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

        client_data = state.get("clients", {})
        current_ids = set(client_data.keys())
        known_ids = set(self.remote_sprites.keys())

        # New Players
        for cid in current_ids - known_ids:
            if cid != self.local_player.net_id:
                new_sprite = self.sprite_class(self, is_local=False)
                self.remote_sprites[cid] = new_sprite
                self.remote_player_group.add(new_sprite)
        
        # Update Players
        for cid, sprite in self.remote_sprites.items():
            if cid in client_data:
                sprite.set_net_state(client_data[cid])
        
        # Remove Players
        for cid in known_ids - current_ids:
            self.remote_sprites[cid].kill()
            del self.remote_sprites[cid]

    def _send_local_state(self):
        if self.client and self.local_player.net_id:
            self.client.send_movement(
                self.local_player.x, 
                self.local_player.y, 
                self.local_player.imageAngle
            )

    def stop(self):
        if self.client: self.client.stop()
        super().stop()

class HostScene(NetworkScene):
    def __init__(self, host='0.0.0.0', tcp_port=12345, broadcast_port=12346, sprite_class=NetSprite, game_id="simpleGE_Game"):
        self.server = Server(host, tcp_port, broadcast_port, game_id)
        self.server.start()
        super().__init__('127.0.0.1', tcp_port, sprite_class, game_id)
        self.setCaption(f"{game_id} (HOST)")
        self.client = Client('127.0.0.1', tcp_port, game_id)
        self._wait_for_id()

    def _wait_for_id(self):
        start = time.time()
        while not self.client.id and time.time() - start < 2.0:
            time.sleep(0.05)
        if self.client.id: self.local_player.net_id = self.client.id

class ClientScene(NetworkScene):
    def __init__(self, host, port=12345, sprite_class=NetSprite, game_id="simpleGE_Game"):
        super().__init__(host, port, sprite_class, game_id)
        self.setCaption(f"{game_id} (Client at {host})")
        self.client = Client(self.host, port, game_id)
        self._wait_for_id()

    def _wait_for_id(self):
        start = time.time()
        while not self.client.id and time.time() - start < 2.0:
            time.sleep(0.05)
        if self.client.id: self.local_player.net_id = self.client.id

class Client:
    def __init__(self, host, port, game_id="simpleGE_Game"):
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.host = host
        self.id = None
        self.server_udp_port = None
        self.latest_state = {}
        self.lock = threading.Lock()
        self.running = True

        try:
            # TCP Handshake
            self.tcp_sock.connect((host, port))
            send_tcp_msg(self.tcp_sock, {"game_id": game_id})
            
            # Wait for assignment
            response = recv_tcp_msg(self.tcp_sock)
            if response and response.get("type") == "id_assignment":
                self.id = response["id"]
                self.server_udp_port = response["udp_port"]
                print(f"Assigned ID: {self.id}. Server UDP at port {self.server_udp_port}")
            
            # Start Listeners
            threading.Thread(target=self._listen_udp, daemon=True).start()
            
        except Exception as e:
            print(f"Connection Error: {e}")
            self.running = False

    def _listen_udp(self):
        """Receives game state updates via UDP."""
        # Send a dummy packet first so server knows our UDP address
        if self.id and self.server_udp_port:
            self.send_movement(0,0,0)

        while self.running:
            try:
                data, _ = self.udp_sock.recvfrom(4096)
                state = pickle.loads(data)
                with self.lock: self.latest_state = state
            except: break

    def send_movement(self, x, y, angle):
        """Packs data into binary struct and sends via UDP."""
        if not (self.running and self.id and self.server_udp_port): return
        try:
            # Pack: UUID (36s), x (f), y (f), angle (f)
            # Encode ID to bytes, ensure it fits 36 bytes
            id_bytes = self.id.encode('utf-8')
            packet = struct.pack(PACKET_FMT, id_bytes, x, y, angle)
            self.udp_sock.sendto(packet, (self.host, self.server_udp_port))
        except Exception: pass

    def get_latest_state(self):
        with self.lock: return self.latest_state.copy()

    def stop(self):
        self.running = False
        try: self.tcp_sock.close()
        except: pass
        try: self.udp_sock.close()
        except: pass
