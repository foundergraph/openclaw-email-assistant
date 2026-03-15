FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create config and log directories
RUN mkdir -p /root/.openclaw/email-assistant \
    /root/.openclaw/logs

# Run the skill
CMD ["python", "skill.py", "config/local.yaml"]
