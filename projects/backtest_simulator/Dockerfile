# Use a slim Python image as the base
FROM python:3.8-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy just the requirements file first to leverage Docker cache
COPY pyproject.toml .

# Install the Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir build setuptools wheel

# Copy the project code
COPY . .

# Build the project
RUN pip install --no-cache-dir -e .

# Build a smaller runtime image
FROM python:3.8-slim

# Copy the installed package from the builder stage
COPY --from=builder /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages
COPY --from=builder /app /app

# Set the working directory
WORKDIR /app

# Environment variables
ENV PYTHONPATH=/app
ENV BACKTEST_DATA_PATH=/data

# Create a directory for data and results
RUN mkdir -p /data /app/results

# Set the command to run the backtest
ENTRYPOINT ["python", "-m", "scripts.run_backtest"]

# Default to showing help
CMD ["--help"]
