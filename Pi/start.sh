#!/bin/bash

# Directory containing the virtual environment
TARGET_DIR="/home/pi/solareye"
VENV_DIR="/home/pi/solareye/venv"

# Change to the target directory
cd "$TARGET_DIR" || { echo "Directory not found: $TARGET_DIR"; exit 1; }

# Activate the virtual environment
if [ -d "$VENV_DIR" ]; then
    echo "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
else
    echo "Virtual environment not found in $VENV_DIR."
    exit 1
fi

# Optional: Notify the user of success
echo "Virtual environment activated. You are now in: $TARGET_DIR"

# Keep the shell open in this environment
exec "$SHELL"
