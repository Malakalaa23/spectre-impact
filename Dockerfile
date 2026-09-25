FROM python:3.11-slim

# Install system dependencies
# ffmpeg is REQUIRED for Whisper STT
# build-essential is required for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Make the startup script executable
RUN chmod +x start.sh

# Render injects a $PORT variable. Default to 10000.
ENV PORT=10000
EXPOSE $PORT

# Run the startup script
CMD ["./start.sh"]