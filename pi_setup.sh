#!/bin/bash

set -e

ZIP_URL="https://github.com/gbradham/glider/archive/refs/heads/PiConfig.zip"
FOLDER_NAME="glider-PiConfig"

echo "Starting setup"

# 1. Install Python 3.12 and Global PyQt6
echo "Installing System Dependencies..."
sudo apt update
# python3-pyqt6 is the global apt package
sudo apt install -y python3 python3 python3-pyqt6 wget unzip

# 2. Download and Unzip
echo "Downloading PiConfig branch..."
wget -O glider_piconfig.zip $ZIP_URL
unzip -o glider_piconfig.zip
rm glider_piconfig.zip

cd $FOLDER_NAME

# 3. Create Virtual Environment with System Site Packages
# The --system-site-packages flag allows the venv to access PyQt6 from apt
echo "Creating venv with access to global packages..."
python3 -m venv --system-site-packages venv
source venv/bin/activate

# 4. Install Project
echo "Installing project in editable mode..."
pip install --upgrade pip
# We avoid 'pip install pyqt6' here because we are using the system version
pip install -e .

echo "------------------------------------------------"
echo "Setup complete!"
echo "Your venv is configured to use the GLOBAL PyQt6 installation."
echo "To activate: cd $FOLDER_NAME && source venv/bin/activate"
echo "------------------------------------------------"