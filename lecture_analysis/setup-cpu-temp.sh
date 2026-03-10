#!/bin/bash

# Enable passwordless sudo for powermetrics command
# This allows the bridge server to read CPU temperature without password prompts

echo "Setting up passwordless sudo for powermetrics..."
echo ""
echo "This will add a rule to /etc/sudoers.d/ that allows running 'powermetrics' without password."
echo "You will be asked for your password once."
echo ""

# Create sudoers rule
SUDOERS_FILE="/etc/sudoers.d/powermetrics"
USERNAME=$(whoami)

# Create the rule
echo "$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/powermetrics" | sudo tee "$SUDOERS_FILE" > /dev/null

# Set correct permissions
sudo chmod 0440 "$SUDOERS_FILE"

echo "✅ Done! You can now run 'sudo powermetrics' without entering a password."
echo ""
echo "Test it: sudo powermetrics -n 1 --samplers cpu_power | grep -i 'CPU die temperature'"
