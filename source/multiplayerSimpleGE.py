"""
multiplayerSimpleGE.py

Extends simpleGE with a client-server multiplayer framework.

Key Features:
- Hybrid TCP/UDP Architecture:
    - TCP: Used for reliable connection setup, ID assignment, and handshake via `NetUtils`.
    - UDP: Used for fast, real-time game state updates.
- Object Serialization: 
	- Uses `pickle` for both TCP messages and UDP game state payloads, allowing generic Python
    objects (tuples, dicts, etc.) to be transmitted.
- Connection Management: 
    - Includes heartbeat logic to detect server disconnects (`DISCONNECT_TIMEOUT`).
    - Handles connection timeouts for clients connecting to invalid IPs (`CONNECTION_TIMEOUT`).
- Abstract NetworkScene: 
    - Provides a base `NetworkScene` that handles the networking loop.
    - Intended to be subclassed (or used with a mixin) to implement specific game state 
    synchronization logic (`handle_network_state`, `get_local_state`).
"""

from simpleGE import simpleGE
import socket, threading, pickle, struct, uuid, time

VERBOSE = False

# --- Global Constants ---
DEFAULT_GAME_ID = "simpleGE Game"
DEFAULT_TCP_PORT = 12345
BROADCAST_PORT = 12346
DISCONNECT_TIMEOUT = 5.0
CONNECTION_TIMEOUT = 7.0
DISCOVERY_TIMEOUT = 3
ID_WAIT_TIMEOUT = 2.0
ID_WAIT_INTERVAL = 0.05
UDP_SOCKET_TIMEOUT = 1.0
BROADCAST_INTERVAL = 2
UDP_BUFFER_SIZE = 4096

class NetUtils:
    """Utility class for common network operations (logging, TCP sending/receiving)."""
    
    @staticmethod
    def debug_log(message, tag="NETWORK"):
        """Prints a timestamped log message if VERBOSE is True."""
        if VERBOSE:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}][{tag}] {message}")

    @staticmethod
    def send_object_over_tcp(socket_obj, object_data):
        """
        Pickles an object and sends it over TCP with a length header.
        
        TCP is a stream protocol, so we need to tell the receiver exactly how many bytes
        to read for this specific message. We prepend a 4-byte integer (length of the pickled data)
        to the message itself.
        """
        try:
            msg = pickle.dumps(object_data)
            # Pack the length of the message into 4 bytes (big-endian unsigned int)
            msg = struct.pack('>I', len(msg)) + msg
            socket_obj.sendall(msg)
        except (ConnectionError, OSError):
            pass

    @staticmethod
    def receive_object_over_tcp(socket_obj):
        """
        Receives a length-prefixed pickled object over TCP.
        
        First reads 4 bytes to determine the size of the incoming message,
        then reads exactly that many bytes to retrieve the full pickle payload.
        """
        try:
            # 1. Read the 4-byte header to get message length
            raw_msglen = NetUtils.receive_all_bytes(socket_obj, 4)
            if not raw_msglen: 
                NetUtils.debug_log("Failed to read length header", "RECV_TCP")
                return None
            msglen = struct.unpack('>I', raw_msglen)[0]
            
            # 2. Read the actual message data based on the length
            data = NetUtils.receive_all_bytes(socket_obj, msglen)
            if not data: 
                NetUtils.debug_log("Failed to read data payload", "RECV_TCP")
                return None
            return pickle.loads(data)
        except (ConnectionError, OSError, pickle.UnpicklingError) as e:
            NetUtils.debug_log(f"error: {e}", "RECV_TCP")
            return None

    @staticmethod
    def receive_all_bytes(socket_obj, num_bytes):
        """
        Helper to ensure exactly `num_bytes` are read from the socket.
        TCP `recv` can return fewer bytes than requested, so this loops until finished.
        """
        data = b''
        while len(data) < num_bytes:
            packet = socket_obj.recv(num_bytes - len(data))
            if not packet: return None
            data += packet
        return data

class NetManager:
    """Helper class for finding games on the local network."""
    
    @staticmethod
    def find_games_on_lan(target_game_id=DEFAULT_GAME_ID, broadcast_port=BROADCAST_PORT, timeout=DISCOVERY_TIMEOUT):
        """
        Searches for active games on the LAN by broadcasting a discovery packet.
        Returns a list of found host dictionaries.
        """
        discovered_hosts = []
        sock = NetManager._create_discovery_socket(broadcast_port)
        
        try:
            print(f"Searching for games ('{target_game_id}') on LAN for {timeout}s...")
            NetManager._listen_for_discovery_responses(sock, discovered_hosts, target_game_id, timeout)
        finally:
            sock.close()
            
        if not discovered_hosts: 
            print("No matching games found.")
        return discovered_hosts

    @staticmethod
    def _create_discovery_socket(broadcast_port):
        """Creates and binds a UDP socket for discovery listening."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(1.0)
        
        try:
            # Bind to all interfaces on the broadcast port to hear announcements
            sock.bind(('', broadcast_port))
        except OSError:
            pass 
        return sock

    @staticmethod
    def _listen_for_discovery_responses(sock, discovered_hosts, target_game_id, timeout):
        """Loops and listens for broadcast packets until timeout."""
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                data, addr = sock.recvfrom(UDP_BUFFER_SIZE)
                NetManager._process_discovery_packet(data, addr, discovered_hosts, target_game_id)
            except socket.timeout: 
                continue
            except (pickle.UnpicklingError, EOFError, KeyError): 
                continue

    @staticmethod
    def _process_discovery_packet(data, addr, discovered_hosts, target_game_id):
        """Parses a discovery packet and adds it to the list if valid."""
        try:
            message = pickle.loads(data)
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
        except Exception:
            pass

class Server:
    def __init__(self, host, tcp_port, broadcast_port, game_id=DEFAULT_GAME_ID):
        self.host = host
        self.tcp_port = tcp_port
        self.broadcast_port = broadcast_port
        self.game_id = game_id
        
        self.game_state = {} # Generic game state: client_id -> data payload
        self.client_map = {} # Maps client_id -> (IP, UDP_Port)
        self.clients_tcp = []
        
        self.lock = threading.Lock()
        self.running = True

        # Initialize UDP Socket for game updates
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind((self.host, 0)) # Bind to ephemeral port
        self.udp_port = self.udp_sock.getsockname()[1]

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}][SERVER] {msg}")

    def start(self):
        """Starts all server threads (TCP, UDP listener, UDP broadcast)."""
        threading.Thread(target=self._run_tcp_server, daemon=True).start()
        threading.Thread(target=self._run_udp_listener, daemon=True).start()
        threading.Thread(target=self._run_udp_broadcast, daemon=True).start()
        self.log(f"UDP listening on port {self.udp_port}")

    def _run_tcp_server(self):
        """Handles new client connections via TCP."""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.tcp_port))
        server_sock.listen()
        self.log(f"Game server ('{self.game_id}') listening on {self.host}:{self.tcp_port}")
        
        while self.running:
            try:
                client_sock, _ = server_sock.accept()
                threading.Thread(target=self._handle_client_tcp, args=(client_sock,), daemon=True).start()
            except OSError: break

    def _run_udp_listener(self):
        """Continuously receives UDP packets from clients."""
        while self.running:
            try:
                data, addr = self.udp_sock.recvfrom(UDP_BUFFER_SIZE)
                self._process_client_packet(data, addr)
            except OSError as e:
                if VERBOSE: self.log(f"UDP: OSError in listener: {e}")
                break

    def _process_client_packet(self, data, addr):
        """Unpacks client data, updates internal state, and broadcasts to all."""
        try:
            client_id, payload = pickle.loads(data)
            if VERBOSE: self.log(f"UDP: Received from {client_id} at {addr}: {payload}")
            
            with self.lock:
                # Register client's UDP address if new
                if client_id not in self.client_map:
                    self.client_map[client_id] = addr
                    if VERBOSE: self.log(f"UDP: Added {client_id} to client_map: {addr}")
                    
                # Update the authoritative game state with client's payload
                self.game_state[client_id] = payload
                if VERBOSE: self.log(f"UDP: Updated game_state for {client_id}. Current state keys: {list(self.game_state.keys())}")
                
            # Immediately echo the full game state back to all clients
            self._broadcast_udp_state()
        except (pickle.UnpicklingError, ValueError) as e:
            if VERBOSE: self.log(f"UDP: Error unpickling/unpacking data from {addr}: {e}, Data: {data}")

    def _broadcast_udp_state(self):
        """Packs entire game state and blasts it to all known UDP clients."""
        try:
            with self.lock:
                if not self.client_map: 
                    return
                payload = pickle.dumps(self.game_state)
                
                for cid, addr in self.client_map.items():
                    self.udp_sock.sendto(payload, addr)
        except Exception as e:
            if VERBOSE: self.log(f"UDP: Error broadcasting state: {e}")

    def _handle_client_tcp(self, client_sock):
        """Handles initial client handshake, ID assignment, and disconnects."""
        try:
            # 1. Receive Handshake (Check Game ID)
            handshake = NetUtils.receive_object_over_tcp(client_sock)
            if not handshake or handshake.get("game_id") != self.game_id:
                client_sock.close()
                return

            # 2. Assign Unique ID
            client_id = str(uuid.uuid4())
            with self.lock: self.clients_tcp.append(client_sock)

            # 3. Send ID + Server UDP Port to Client
            NetUtils.send_object_over_tcp(client_sock, {
                "type": "id_assignment",
                "id": client_id,
                "udp_port": self.udp_port
            })
            
            self.log(f"Client {client_id} connected via TCP.")

            # 4. Keep TCP connection open to detect disconnects
            while True:
                msg = NetUtils.receive_object_over_tcp(client_sock)
                if msg is None: break 
                # Potential for chat messages or reliable events here
                
        except Exception as e:
            self.log(f"TCP Error {client_id}: {e}")
        finally:
            # Cleanup on disconnect
            with self.lock:
                if client_sock in self.clients_tcp: self.clients_tcp.remove(client_sock)
                if client_id in self.game_state: del self.game_state[client_id]
                if client_id in self.client_map: del self.client_map[client_id]
            client_sock.close()
            self.log(f"Client {client_id} disconnected.")

    def _run_udp_broadcast(self):
        """Periodically broadcasts server existence on LAN."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self.running:
            msg = {"game_id": self.game_id, "host_name": socket.gethostname(), "tcp_port": self.tcp_port}
            try: sock.sendto(pickle.dumps(msg), ('<broadcast>', self.broadcast_port))
            except: pass
            time.sleep(BROADCAST_INTERVAL)

# Kept as a utility base class for easy sprite networking
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
    """
    A simpleGE Scene that handles client-server networking.
    
    This class manages the network loop (receiving updates, sending state).
    It is designed to be subclassed. Subclasses must override:
    - handle_network_state(self, state): To apply server updates to the local game.
    - get_local_state(self): To provide the local data to send to the server.
    - on_server_disconnect(self): To handle connection loss.
    """
    def __init__(self, host, port, game_id=DEFAULT_GAME_ID):
        super().__init__()
        self.host = host
        self.port = port
        self.game_id = game_id
        self.client = None
        self.local_client_id = None # Will be set by the Client after ID assignment
    
    def process(self):
        # Check for disconnect every frame
        if self.client and not self.client.get_connected_status():
            self.on_server_disconnect()
            return # Stop processing if disconnected

        self._update_from_network()
        self._send_local_state()

    def _update_from_network(self):
        """Override this to handle state updates from server."""
        if not self.client: return
        state = self.client.get_latest_state()
        if not state: 
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

    def on_server_disconnect(self):
        """Override to handle server disconnection."""
        print("Server disconnected. Stopping scene.")
        self.stop()

    def stop(self):
        if self.client: self.client.stop()
        super().stop()

class HostScene(NetworkScene):
    def __init__(self, host='0.0.0.0', tcp_port=DEFAULT_TCP_PORT, broadcast_port=BROADCAST_PORT, game_id=DEFAULT_GAME_ID):
        self.server = Server(host, tcp_port, broadcast_port, game_id)
        self.server.start()
        super().__init__('127.0.0.1', tcp_port, game_id)
        self.setCaption(f"{game_id} (HOST)")
        
        self.connection_successful = False # Track if initial connection was successful
        self.client = Client('127.0.0.1', tcp_port, game_id)
        self._wait_for_id()
        if self.client.get_connected_status():
            self.connection_successful = True
        else:
            print("[HOST SCENE] Initial client connection to server failed.")

    def _wait_for_id(self):
        """Waits briefly for the internal client to connect to the internal server."""
        start = time.time()
        while not self.client.id and time.time() - start < ID_WAIT_TIMEOUT and self.client.connected:
            time.sleep(ID_WAIT_INTERVAL)
        if self.client.id:
            self.local_client_id = self.client.id

class ClientScene(NetworkScene):
    def __init__(self, host, port=DEFAULT_TCP_PORT, game_id=DEFAULT_GAME_ID):
        super().__init__(host, port, game_id)
        self.setCaption(f"{game_id} (Client at {host})")
        
        self.connection_successful = False # Track if initial connection was successful
        self.client = Client(self.host, port, game_id)
        self._wait_for_id()
        if self.client.get_connected_status():
            self.connection_successful = True
        else:
            print("[CLIENT SCENE] Initial client connection to server failed.")

    def _wait_for_id(self):
        """Waits briefly for ID assignment from the server."""
        start = time.time()
        while not self.client.id and time.time() - start < ID_WAIT_TIMEOUT and self.client.connected:
            time.sleep(ID_WAIT_INTERVAL)
        if self.client.id:
            self.local_client_id = self.client.id

class Client:
    def __init__(self, host, port, game_id=DEFAULT_GAME_ID):
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set a timeout for UDP socket to detect disconnects (heartbeat)
        self.udp_sock.settimeout(UDP_SOCKET_TIMEOUT) 
        self.host = host
        self.id = None
        self.server_udp_port = None
        self.latest_state = {}
        self.lock = threading.Lock()
        self.running = True
        self.connected = False # Connection status flag
        self.last_packet_time = time.time()

        try:
            self.tcp_sock.settimeout(CONNECTION_TIMEOUT) # Timeout for initial connection
            if VERBOSE: self.log(f"Connecting to {host}:{port}...")
            
            # TCP Handshake
            self.tcp_sock.connect((host, port))
            self.tcp_sock.settimeout(None) # Restore blocking for handshake
            
            if VERBOSE: self.log("Connected. Sending handshake...")
            NetUtils.send_object_over_tcp(self.tcp_sock, {"game_id": game_id})
            
            # Wait for assignment
            if VERBOSE: self.log("Waiting for ID assignment...")
            response = NetUtils.receive_object_over_tcp(self.tcp_sock)
            if response and response.get("type") == "id_assignment":
                self.id = response["id"]
                self.server_udp_port = response["udp_port"]
                self.connected = True # Successfully connected
                self.log(f"Assigned ID: {self.id}. Server UDP at port {self.server_udp_port}")
            else:
                self.log(f"Received unexpected response: {response}")
            
            # Start Listeners
            threading.Thread(target=self._listen_udp, daemon=True).start()
            
        except Exception as e:
            self.log(f"Connection Error: {e}")
            self.running = False

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        if self.id:
            short_id = self.id[-8:]
            tag = f"[CLIENT {short_id}]"
        else:
            tag = "[CLIENT]"
        print(f"[{timestamp}]{tag} {msg}")

    def _listen_udp(self):
        """Receives game state updates via UDP and monitors connection health."""
        
        # Send a dummy packet first so server knows our UDP address
        if self.id and self.server_udp_port:
            if VERBOSE: self.log("Sending initial registration packet.")
            self.send_update("init")
        
        self.last_packet_time = time.time() # Reset timer on start

        while self.running and self.connected:
            try:
                data, _ = self.udp_sock.recvfrom(UDP_BUFFER_SIZE)
                self._handle_udp_packet(data)
            except socket.timeout:
                self._handle_timeout()
            except (ConnectionError, OSError) as e:
                self.log(f"Connection lost: {e}")
                self.connected = False
                break
            except Exception as e:
                self.log(f"Error receiving state: {e}")
                break

    def _handle_udp_packet(self, data):
        """Process received UDP data."""
        self.last_packet_time = time.time() # Update heartbeat timestamp
        try:
            state = pickle.loads(data)
            if VERBOSE: self.log(f"Received state. Keys: {list(state.keys())}")
            with self.lock: self.latest_state = state
        except (pickle.UnpicklingError, ValueError) as e:
            if VERBOSE: self.log(f"Error processing packet: {e}")

    def _handle_timeout(self):
        """Handle socket timeout and check if server is effectively disconnected."""
        if time.time() - self.last_packet_time > DISCONNECT_TIMEOUT:
            self.log(f"Connection timed out (no data for {DISCONNECT_TIMEOUT}s).")
            self.connected = False
        elif VERBOSE: 
            self.log("UDP socket timed out, checking connection status.")

    def send_update(self, data):
        """Packs data using pickle and sends via UDP."""
        if not (self.running and self.id and self.server_udp_port and self.connected): return
        try:
            # Send tuple: (client_id, payload)
            packet = pickle.dumps((self.id, data))
            if VERBOSE: self.log(f"Sending update (size {len(packet)} bytes). Payload: {data}")
            self.udp_sock.sendto(packet, (self.host, self.server_udp_port))
        except Exception as e:
            if VERBOSE: self.log(f"Error sending update: {e}")

    def get_latest_state(self):
        with self.lock: return self.latest_state.copy()

    def get_connected_status(self):
        return self.connected

    def stop(self):
        self.running = False
        self.connected = False
        try: self.tcp_sock.close()
        except: pass
        try: self.udp_sock.close()
        except: pass
