# Build Gitleaks from its official source at a pinned version.
# The upstream v8.30.1 release contains Go dependencies reported by Trivy.
FROM golang:1.27.2-bookworm AS gitleaks-builder
ENV GOTOOLCHAIN=local
WORKDIR /src
RUN git clone --quiet --depth 1 --branch v8.30.1 https://github.com/gitleaks/gitleaks.git . \
    && go get golang.org/x/crypto@v0.55.0 golang.org/x/text@v0.41.0 \
    && go mod tidy \
    && test "$(go list -m -f '{{.Version}}' golang.org/x/crypto)" = 'v0.55.0' \
    && test "$(go list -m -f '{{.Version}}' golang.org/x/text)" = 'v0.41.0' \
    && CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /out/gitleaks . \
    && /out/gitleaks version

FROM python:3.13-slim

ARG DOCKER_GID=999


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Build-time pip is not needed by the running FastAPI service.
# Remove its vendored dependencies and their CycloneDX SBOM from the final filesystem.
RUN python -m pip uninstall -y pip && \
    python -c "import importlib.util; assert importlib.util.find_spec('pip') is None"

RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Gitleaks is kept mandatory: use a patched Go build, not the upstream
# release binary compiled with Go 1.24.11 / x/crypto 0.35 / x/text 0.22.
COPY --from=gitleaks-builder /out/gitleaks /usr/local/bin/gitleaks
RUN gitleaks version
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
