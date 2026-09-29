#!/bin/bash
set -e

# ====== À REMPLIR UNE FOIS ======
API_BASE="http://app.localhost:8080"        # adapte le port de ton API
LOGIN_PATH="/api/auth/login"
EMAIL="dylan@example.com"
PASSWORD="12345678"
SLUG="teststack12"
# =================================



echo "=== 1. Login ==="
LOGIN_RESPONSE=$(curl -s -c "cookies.txt" -X POST "$API_BASE$LOGIN_PATH" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")


echo "$LOGIN_RESPONSE"
ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')

if [ -z "$ACCESS_TOKEN" ]; then
  echo "Pas de access_token dans la réponse JSON — on part du principe que tout passe par le cookie httpOnly."
  AUTH_HEADER=""
else
  AUTH_HEADER="-H \"Authorization: Bearer $ACCESS_TOKEN\""
fi

echo ""
echo "=== 2. Test négatif : port manquant sur le back (doit renvoyer 422) ==="
curl -s -b "cookies.txt" -X POST "$API_BASE/api/deploy/stack" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "'"$SLUG"'-neg",
    "components": [
      {
        "name": "back",
        "kind": "back",
        "repo_url": "https://github.com/Dylan-Best/repo-test-back",
        "branch": "main",
        "expose_publicly": true
      }
    ]
  }'
echo ""

echo ""
echo "=== 3. Déploiement complet avec les bons ports ==="
curl -s -b "cookies.txt" -X POST "$API_BASE/api/deploy/stack" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "'"$SLUG"'",
    "components": [
      {
        "name": "database",
        "kind": "database",
        "db_image": "postgres:15-alpine",
        "volume_name": "'"$SLUG"'-pgdata"
      },
      {
        "name": "back",
        "kind": "back",
        "repo_url": "https://github.com/Dylan-Best/repo-test-back",
        "branch": "main",
        "port": 3000,
        "expose_publicly": true
      },
      {
        "name": "front",
        "kind": "front",
        "repo_url": "https://github.com/Dylan-Best/repo-test-front",
        "branch": "main",
        "port": 8080,
        "expose_publicly": true
      }
    ]
  }'
echo ""
echo ""

echo "=== 4. Attente que le pipeline tourne (ajuste si besoin) ==="
sleep 30

echo ""
echo "=== 5. Vérif labels Traefik du back ==="
docker inspect "${SLUG}-back-1" --format '{{json .Config.Labels}}' | jq .

echo ""
echo "=== 6. Vérif labels Traefik du front ==="
docker inspect "${SLUG}-front-1" --format '{{json .Config.Labels}}' | jq .

echo ""
echo "=== 7. Test HTTP réel du back ==="
curl -sv "http://${SLUG}-back-1.localhost:8080/api/ping-db"

echo ""
echo ""
echo "=== 8. Test HTTP réel du front ==="
curl -sv "http://${SLUG}-front-1.localhost:8080/"