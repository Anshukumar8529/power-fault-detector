# Dockerfile
#
# Packages the app so it runs the same way everywhere - no "works on my
# machine" problems. Any reviewer with just Docker installed can run this.

FROM python:3.12-slim

# Set the working folder inside the container
WORKDIR /app

# Copy dependency list first (Docker caches this layer, so rebuilds are
# faster if only your code changes and not your dependencies)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the project files
COPY . .

# The Flask app listens on port 5000 inside the container
EXPOSE 5000

# IMPORTANT: host="0.0.0.0" is required so the app is reachable from
# OUTSIDE the container, not just from inside it.
CMD ["python", "app.py"]
