#!/bin/zsh

# This script will launch 10 Terminal windows on macOS.
# One window will run the game as the Host, and the other nine will run as Clients.
# This script is designed to be placed within the 'source/demos/squareShooter/' directory.

# Determine the project root directory relative to this script
# $0 is the path to this script. We go up 3 levels:
# squareShooter/ -> demos/ -> source/ -> project_root/
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)

# Define paths
PYTHON_EXEC="$PROJECT_ROOT/.venv/bin/python3"
GAME_SCRIPT="source/demos/squareShooter/squareShooter.py"

# Verify python exists
if [ ! -f "$PYTHON_EXEC" ]; then
    echo "Error: Python executable not found at $PYTHON_EXEC"
    exit 1
fi

echo "Project Root: $PROJECT_ROOT"
echo "Python: $PYTHON_EXEC"

osascript <<EOF
    set project_path to "$PROJECT_ROOT"
    set python_executable to "$PYTHON_EXEC"
    set game_script_relative_path to "$GAME_SCRIPT"

    # The command that will be run in each Terminal instance
    # We use quoted form to handle spaces in paths safely
    set full_game_command to quoted form of python_executable & " " & game_script_relative_path

    # Launch Host (Player Name: HostPlayer, Mode: h)
    tell application "Terminal"
        activate
        # First cd to the project_path, then run the game command
        # We execute 'cd' then the python command
        do script "cd " & quoted form of project_path & " && " & full_game_command & " <<< $'HostPlayer\nh\n'"
    end tell

    delay 3 # Give the host a moment to initialize the server

    # Launch 9 Clients
    repeat with i from 1 to 20
        tell application "Terminal"
            activate
            # Client inputs: Player Name (ClientX), Mode (j), Host IP (127.0.0.1)
            do script "cd " & quoted form of project_path & " && " & full_game_command & " <<< $'Client" & i & "\nj\n127.0.0.1\n'"
        end tell
        delay 0.75 # Small delay between launching clients
    end repeat
EOF