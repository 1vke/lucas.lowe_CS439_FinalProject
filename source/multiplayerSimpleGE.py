"""
multiplayerSimpleGE.py (Hybrid TCP/UDP + Struct Packing)

Extends simpleGE with a client-server multiplayer framework.
- TCP: Used for connection setup, ID assignment, and exchanging UDP ports.
- UDP: Used for fast, real-time movement updates using 'struct' for binary packing.
"""

from simpleGE import simpleGE
import socket, threading, pickle, struct, uuid, time

VERBOSE = False

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
        if not raw_msglen: 
            if VERBOSE: print("recv_tcp_msg: Failed to read length header")
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        data = recvall(sock, msglen)
        if not data: 
            if VERBOSE: print("recv_tcp_msg: Failed to read data payload")
            return None
        return pickle.loads(data)
    except (ConnectionError, OSError, pickle.UnpicklingError) as e:
        if VERBOSE: print(f"recv_tcp_msg error: {e}")
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
        
        self.game_state = {} # Generic game state: client_id -> data payload
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
        """Receives pickled updates from clients."""
        while self.running:
            try:
                data, addr = self.udp_sock.recvfrom(4096)
                try:
                    client_id, payload = pickle.loads(data)
                    if VERBOSE: print(f"Server UDP: Received from {client_id} at {addr}: {payload}")
                    
                    with self.lock:
                        if client_id not in self.client_map:
                            self.client_map[client_id] = addr
                            if VERBOSE: print(f"Server UDP: Added {client_id} to client_map: {addr}")
                            
                        self.game_state[client_id] = payload
                        if VERBOSE: print(f"Server UDP: Updated game_state for {client_id}. Current state keys: {list(self.game_state.keys())}")
                        
                    self._broadcast_udp_state()
                except (pickle.UnpicklingError, ValueError) as e:
                    if VERBOSE: print(f"Server UDP: Error unpickling/unpacking data from {addr}: {e}, Data: {data}")
                    continue
            except OSError as e:
                if VERBOSE: print(f"Server UDP: OSError in listener: {e}")
                break

    def _broadcast_udp_state(self):
        """Packs entire game state and blasts it to all known UDP clients."""
        try:
            with self.lock:
                if not self.client_map: 
                    # print("Server UDP: No clients to broadcast to.") # Not printing every time for brevity
                    return
                payload = pickle.dumps(self.game_state)
                if VERBOSE: print(f"Server UDP: Broadcasting state (size {len(payload)} bytes) to {len(self.client_map)} clients. State keys: {list(self.game_state.keys())}")
                
                for cid, addr in self.client_map.items():
                    # print(f"Server UDP: Sending to {cid} at {addr}") # Not printing every time for brevity
                    self.udp_sock.sendto(payload, addr)
        except Exception as e:
            if VERBOSE: print(f"Server UDP: Error broadcasting state: {e}")

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
                
                # Remove client state
                if client_id in self.game_state:
                    del self.game_state[client_id]

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

# Kept as a utility, but not used by NetworkScene directly anymore
class NetSprite(simpleGE.Sprite):
    def __init__(self, scene, is_local=False):
        super().__init__(scene)
        self.net_id = None # Owner's client ID
        self.sprite_id = str(uuid.uuid4()) # Unique ID for this sprite
        self.is_local = is_local
        if not self.is_local: self.hide()

    def get_net_state(self):
        # Return owner_id, sprite_id, x, y, angle
        return (self.net_id, self.sprite_id, self.x, self.y, self.imageAngle)

    def set_net_state(self, state):
        if not self.visible: self.show()
        # Expecting tuple (x, y, angle)
        if isinstance(state, (tuple, list)) and len(state) >= 3:
            self.x, self.y, self.imageAngle = state

class NetworkScene(simpleGE.Scene):
    def __init__(self, host, port, game_id="simpleGE_Game"):
        super().__init__()
        self.host = host
        self.port = port
        self.game_id = game_id
        self.client = None
        self.local_client_id = None # Will be set by the Client after ID assignment
    
    def process(self):
        self._update_from_network()
        self._send_local_state()

    def _update_from_network(self):
        """Override this to handle state updates from server."""
        if not self.client: return
        state = self.client.get_latest_state()
        if not state: 
            # if VERBOSE: print("NetworkScene: No state from client.")
            return
        if VERBOSE: print(f"NetworkScene: Passing state to handler. Keys: {list(state.keys())}")
        self.handle_network_state(state)

    def handle_network_state(self, state):
        """Override to process the entire game state dict."""
        pass

    def _send_local_state(self):
        """Override to send local state."""
        if self.client and self.client.id:
            data = self.get_local_state()
            if data is not None:
                self.client.send_update(data)

    def get_local_state(self):
        """Override to return data to send to server."""
        return None

    def stop(self):
        if self.client: self.client.stop()
        super().stop()

class HostScene(NetworkScene):
    def __init__(self, host='0.0.0.0', tcp_port=12345, broadcast_port=12346, game_id="simpleGE_Game"):
        self.server = Server(host, tcp_port, broadcast_port, game_id)
        self.server.start()
        super().__init__('127.0.0.1', tcp_port, game_id)
        self.setCaption(f"{game_id} (HOST)")
        self.client = Client('127.0.0.1', tcp_port, game_id)
        self._wait_for_id()

    def _wait_for_id(self):
        start = time.time()
        while not self.client.id and time.time() - start < 2.0:
            time.sleep(0.05)
        if self.client.id:
            self.local_client_id = self.client.id

class ClientScene(NetworkScene):
    def __init__(self, host, port=12345, game_id="simpleGE_Game"):
        super().__init__(host, port, game_id)
        self.setCaption(f"{game_id} (Client at {host})")
        self.client = Client(self.host, port, game_id)
        self._wait_for_id()

    def _wait_for_id(self):
        start = time.time()
        while not self.client.id and time.time() - start < 2.0:
            time.sleep(0.05)
        if self.client.id:
            self.local_client_id = self.client.id

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
            if VERBOSE: print(f"Client connecting to {host}:{port}...")
            # TCP Handshake
            self.tcp_sock.connect((host, port))
            if VERBOSE: print("Client connected. Sending handshake...")
            send_tcp_msg(self.tcp_sock, {"game_id": game_id})
            
            # Wait for assignment
            if VERBOSE: print("Client waiting for ID assignment...")
            response = recv_tcp_msg(self.tcp_sock)
            if response and response.get("type") == "id_assignment":
                self.id = response["id"]
                self.server_udp_port = response["udp_port"]
                print(f"Assigned ID: {self.id}. Server UDP at port {self.server_udp_port}")
            else:
                print(f"Client received unexpected response: {response}")
            
            # Start Listeners
            threading.Thread(target=self._listen_udp, daemon=True).start()
            
        except Exception as e:
            print(f"Connection Error: {e}")
            self.running = False

    def _listen_udp(self):
        """Receives game state updates via UDP."""
        # Send a dummy packet first so server knows our UDP address
        if self.id and self.server_udp_port:
            if VERBOSE: print(f"Client UDP ({self.id}): Sending initial registration packet.")
            self.send_update("init")

        while self.running:
            try:
                data, _ = self.udp_sock.recvfrom(4096)
                state = pickle.loads(data)
                if VERBOSE: print(f"Client UDP ({self.id}): Received state. Keys: {list(state.keys())}")
                with self.lock: self.latest_state = state
            except Exception as e:
                if VERBOSE: print(f"Client UDP ({self.id}): Error receiving state: {e}")
                break

    def send_update(self, data):
        """Packs data using pickle and sends via UDP."""
        if not (self.running and self.id and self.server_udp_port): return
        try:
            # Send tuple: (client_id, payload)
            packet = pickle.dumps((self.id, data))
            if VERBOSE: print(f"Client UDP ({self.id}): Sending update (size {len(packet)} bytes). Payload: {data}")
            self.udp_sock.sendto(packet, (self.host, self.server_udp_port))
        except Exception as e:
            if VERBOSE: print(f"Client UDP ({self.id}): Error sending update: {e}")

    def get_latest_state(self):
        with self.lock: return self.latest_state.copy()

    def stop(self):
        self.running = False
        try: self.tcp_sock.close()
        except: pass
        try: self.udp_sock.close()
        except: pass