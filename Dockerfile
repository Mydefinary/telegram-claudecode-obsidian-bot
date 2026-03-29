FROM python:3.13-slim

WORKDIR /app

# Install Node.js for Claude Code CLI (optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Vault directory mount point
VOLUME ["/vault"]

CMD ["python", "bot.py"]
