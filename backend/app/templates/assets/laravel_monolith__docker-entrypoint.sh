#!/bin/sh
set -e

# SecurityProfile / read-only root filesystem :
# recrée les zones d'écriture montées en tmpfs.
echo " Préparation des zones d'écriture temporaires..."

mkdir -p \
    /run/nginx \
    /var/lib/nginx/tmp/client_body \
    /var/lib/nginx/tmp/proxy \
    /var/lib/nginx/tmp/fastcgi \
    /var/lib/nginx/tmp/uwsgi \
    /var/lib/nginx/tmp/scgi \
    /var/log/nginx \
    /var/www/html/storage/framework/cache/data \
    /var/www/html/storage/framework/sessions \
    /var/www/html/storage/framework/views \
    /var/www/html/storage/logs \
    /var/www/html/bootstrap/cache

chown -R nginx:nginx \
    /run/nginx \
    /var/lib/nginx \
    /var/log/nginx

ln -sf /dev/stdout /var/log/nginx/access.log
ln -sf /dev/stderr /var/log/nginx/error.log

chmod -R 775 \
    /var/www/html/storage/framework \
    /var/www/html/storage/logs \
    /var/www/html/bootstrap/cache

chown -R www-data:www-data \
    /var/www/html/storage/framework \
    /var/www/html/storage/logs \
    /var/www/html/bootstrap/cache

chmod 1777 /tmp

echo " Démarrage de l'application Laravel..."

echo "Mise en cache de la configuration..."
php artisan config:clear
php artisan config:cache
php artisan route:cache
php artisan view:cache

# 1. Lancer les migrations (le --force est obligatoire car l'environnement est considéré comme 'production')
echo " Exécution des migrations de la base de données..."
php artisan migrate --force

# 2. Démarrer Nginx en arrière-plan
echo " Démarrage de Nginx..."
nginx

# 3. Démarrer PHP-FPM au premier plan (pour garder le conteneur actif)
echo " Démarrage de PHP-FPM..."
php-fpm