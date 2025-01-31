#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create a directory for the task manager if it doesn't exist
mkdir -p ~/.local/bin

# Copy the task manager script to the bin directory
cp "$SCRIPT_DIR/task_manager.py" ~/.local/bin/tm

# Make it executable
chmod +x ~/.local/bin/tm

# Add ~/.local/bin to PATH if it's not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
fi

echo "Task manager installed! Please restart your terminal or run:"
echo "source ~/.bashrc  # if you're using bash"
echo "source ~/.zshrc   # if you're using zsh"
