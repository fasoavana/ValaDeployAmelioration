FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du reste des sources du projet
COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Commande d'exécution générique
CMD ["python", "main.py"]

# L'option -m permet de lancer un module Python comme un script. 

# Pour un template 100 % générique, python -m http.server 8000 sert de
# serveur de démonstration par défaut