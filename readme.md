# Final Project: simpleGENetworking

## Overview

**simpleGENetworking** is a networking extension for the **simpleGE** game engine, designed to make multiplayer game development accessible for students and beginners. It abstracts away the complexities of socket programming, providing a high-level API for synchronizing game state across a local network.

Key features include:
*   **Hybrid TCP/UDP Architecture**: Uses TCP for reliable connection setup and UDP for fast, real-time game state updates.
*   **Easy Serialization**: Automatically handles object serialization using `pickle`, allowing you to send standard Python objects.
*   **Automatic Discovery**: Includes a LAN discovery service so players can find hosted games without typing IP addresses.
*   **Client/Host Model**: Simplifies the logic into `HostScene` (server + player) and `ClientScene` (remote player) classes.

## Usage

To get started with this project:

1.  **Clone the Repository**:
    ```bash
    git clone <repository_url>
    cd lucas.lowe_CS439_FinalProject
    ```

2.  **Install Dependencies**:
    This project requires `pygame`. You can install it using the provided requirements file:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run a Demo**:
    Navigate to a demo folder (e.g., `source/demos/redSquareGame`) and run the server script in one terminal and the client script in another.
    ```bash
    # Terminal 1 (Host)
    python3 source/demos/redSquareGame/server.py

    # Terminal 2 (Client)
    python3 source/demos/redSquareGame/client.py
    ```

## Demo Documentation

This project includes three fully functional demos that showcase different capabilities of the networking framework.

### Red Square Game (`source/demos/redSquareGame`)

A basic multiplayer example where players control a red square avatar.
*   **Networking Feature**: Demonstrates basic movement synchronization and multiple client connections.
*   **Entry Points**:
    *   `server.py`: Starts the host scene.
    *   `client.py`: Starts a client scene that automatically searches for a local server.
*   **Controls**: Use arrow keys to move your square.

### DVD Logo (`source/demos/dvdLogo`)

A networked simulation of the bouncing DVD logo.
*   **Networking Feature**: Demonstrates server-authoritative physics. The server calculates the logo's position and bounces, broadcasting the world state to all clients. Clients purely render the state.
*   **Entry Point**: `launch_demo.py`
    *   This script launches a grid of windows (1 Host, multiple Clients) to simulate a large video wall.

### Square Shooter (`source/demos/squareShooter`)

A simple top-down shooter game.
*   **Networking Feature**: Shows a more complex game state with projectiles and score synchronization.
*   **Entry Points**:
    *   `launch_game.sh`: A helper script to launch a host and client for testing.
    *   `squareShooter.py`: Can be run with arguments to start as host or client manually.
*   **Controls**: Use WASD keys to move your square.

## `simpleGENetworking` Documentation

The `simpleGENetworking.py` module extends `simpleGE` with several key classes.

### Configuration
*   **VERBOSE**: Set `simpleGENetworking.VERBOSE = True` to enable detailed console logging of network packets, heartbeats, and connection events. Useful for debugging.

### NetSprite
A `simpleGE.Sprite` subclass optimized for networking.
*   **Properties**:
    *   `net_id`: The UUID of the client who owns this sprite.
    *   `sprite_id`: A unique UUID for the sprite instance.
    *   `is_local`: Boolean indicating if this sprite is controlled by the local machine.
*   **Methods**:
    *   `get_net_state()`
        *   Returns a tuple `(net_id, sprite_id, x, y, angle)` for serialization.
    *   `set_net_state(state)`
        *   Updates the sprite's position and rotation from a received state tuple.

### NetworkScene
The base class for networked scenes. It handles the update loop and state synchronization.
*   `process()`
    *   Automatically calls `_update_from_network()` and `_send_local_state()` every frame.
*   `handle_network_state(state)`
    *   Override this method to define how your game reacts to data received from the server.
*   `get_local_state()`
    *   Override this method to return the data you want to send to the server (or clients).
*   `on_server_disconnect()`
    *   Called when the connection to the server is lost. Override this to implement custom disconnection logic.

### HostScene
Inherits from `NetworkScene`. Represents the game server.
*   **Functionality**:
    *   Initializes a `Server` instance that listens for TCP connections and UDP packets.
    *   Broadcasts the authoritative game state to all connected clients at a fixed tick rate (default 30 TPS).

### ClientScene
Inherits from `NetworkScene`. Represents a player connecting to a host.
*   **Functionality**:
    *   Connects to a host via TCP to receive a unique Client ID.
    *   Listens for UDP state broadcasts from the server.
    *   Sends local player input/state to the server via UDP.

### NetManager
A static utility class for managing game discovery.
*   `find_games(discovery_service=None, target_game_id=DEFAULT_GAME_ID, timeout=3)`
    *   Uses the provided discovery service (default is `None`) to search for available games. Returns a list of dictionaries containing host info.

### Discovery Services
*   **DiscoveryService**: An abstract base class. Subclass this to implement custom discovery protocols (e.g., Bluetooth).
*   **LANDiscoveryService**: The default implementation using UDP broadcasting.
    *   `find_games(game_id, timeout)`
        *   Searches for hosts on the local network.
