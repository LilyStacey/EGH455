#!/bin/bash

# Optional: Create and activate a virtual environment
python3 -m venv EGH455env
source EGH455env/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install dependencies from requirements.txt
pip install -r requirements.txt

echo "Dependencies installed successfully."