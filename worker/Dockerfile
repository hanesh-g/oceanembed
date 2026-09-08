FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install inference dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy core package and install it
# In a real environment, the context would be the repo root,
# but for now we assume core is mounted or copied in appropriately.
# We will use pip install -e /app/core assuming it's mounted in docker-compose.
# Wait, let's just make it simple if we expect to run it from repo root:
# COPY core /app/core
# RUN pip install -e /app/core
# But we don't have the context here in a single dockerfile without knowing docker-compose setup.
# I'll just put standard requirements and the pip install.

# For now, let's just create the entrypoint
COPY worker /app/worker
WORKDIR /app/worker

CMD ["python", "run_weekly_inference.py"]
