FROM python:3.13-slim

ARG DOCKER_GID=999


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

RUN GITLEAKS_VERSION=$(curl -s "https://api.github.com/repos/gitleaks/gitleaks/releases/latest" | grep -Po '"tag_name": "v\K[0-9.]+') && \
    curl -sfL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" -o gitleaks.tar.gz && \
    tar -xzf gitleaks.tar.gz -C /usr/local/bin gitleaks && \
    rm gitleaks.tar.gz
# Copy the rest of the application source code
COPY . .

# Expose the port your app runs on (change 8000 if needed)
EXPOSE 8000

# Create and switch to a non-privileged user for security
RUN useradd --create-home appuser && chown -R appuser /app

# add the user to the docker group to allow access to the Docker socket
RUN groupadd -g $DOCKER_GID docker && usermod -aG docker appuser

USER appuser

# Define the command to execute your application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
