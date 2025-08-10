FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system dependencies and clean up
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variable for unbuffered Python output (optional but good practice)
ENV PYTHONUNBUFFERED=1

# Pre-download specific tokenizers
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base');"


# Ensure only local models are used (if applicable to your use case)
ENV HF_HUB_OFFLINE=1

# Set bash alias (will only work in interactive bash sessions started manually)
RUN echo "alias ll='ls -la'" >> ~/.bashrc

COPY . /app

EXPOSE 8888

CMD ["bash", "scripts/run.sh"]
