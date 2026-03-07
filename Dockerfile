# Use Python 3.11 slim image
FROM python:3.11.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, and wheel for cache-busting and better dependency resolution
RUN python -m pip install --upgrade pip setuptools wheel

# Copy constraints file for dependency version control
COPY constraints.txt .

# Install Python dependencies
# Use optimized requirements for Cloud Run with constraints
COPY requirements-cloudrun.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

# Copy project files
COPY . .

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Run uvicorn directly for faster startup and better signal handling
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]