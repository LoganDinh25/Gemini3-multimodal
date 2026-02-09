#!/bin/bash

# Graph-Aware Logistics Planner - Setup Script
# Automates installation and first run

echo "🚚 Graph-Aware Logistics Planner - Setup"
echo "========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Create virtual environment (optional but recommended)
read -p "Create virtual environment? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✓ Virtual environment activated"
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Create data directory structure
echo ""
echo "Setting up data directories..."
mkdir -p data/mekong_delta
mkdir -p data/toy_region
echo "✓ Data directories created"

# Optional: Download sample datasets
echo ""
echo "Sample data will be generated automatically when you run the app."
echo "To use your own data, place CSV files in data/[region_name]/"

# Run the app
echo ""
echo "========================================="
echo "Setup complete! 🎉"
echo ""
echo "To run the application:"
echo "  streamlit run app.py"
echo ""
echo "Or run this script with --start to launch immediately:"
echo "  ./setup.sh --start"
echo "========================================="

# Auto-start if flag provided
if [[ "$1" == "--start" ]]
then
    echo ""
    echo "Starting application..."
    streamlit run app.py
fi
