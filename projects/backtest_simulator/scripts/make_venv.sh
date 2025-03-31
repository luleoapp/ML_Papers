#!/bin/bash
# Script to create a virtual environment and install dependencies

set -e

ECHO_PREFIX="[venv setup]"

echo "$ECHO_PREFIX Creating virtual environment..."
if [ -d "venv" ]; then
    echo "$ECHO_PREFIX Virtual environment already exists. Deleting and recreating..."
    rm -rf venv
fi

python -m venv venv

echo "$ECHO_PREFIX Activating virtual environment..."
source venv/bin/activate

echo "$ECHO_PREFIX Installing dependencies..."
pip install --upgrade pip
pip install -e .
pip install -e ".[dev]"

echo "$ECHO_PREFIX Virtual environment setup complete."
echo "$ECHO_PREFIX Activate with 'source venv/bin/activate'"
