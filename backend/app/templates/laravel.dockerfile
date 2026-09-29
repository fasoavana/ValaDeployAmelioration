#Étape 1 : Installation des dépendances Composer
FROM composer:2.7 AS composer_builder
WORKDIR /app

#Copie des fichiers de dépendances
COPY composer.json composer.lock ./

#Installation optimisée pour la production
RUN composer install --no-dev --optimize-autoloader --no-interaction --no-scripts

#Étape 2 : Production avec PHP 8.2 FPM + Nginx
FROM php:8.2-fpm-alpine

WORKDIR /var/www/html

#Installation des dépendances système et extensions PHP
RUN apk add --no-cache 
    nginx 
    git 
    curl 
    libpng-dev 
    libjpeg-turbo-dev 
    freetype-dev 
    oniguruma-dev 
    zip 
    unzip 
    postgresql-dev 
    && docker-php-ext-configure gd --with-freetype --with-jpeg 
    && docker-php-ext-install pdo pdo_pgsql gd mbstring exif pcntl bcmath opcache

#Copie des dépendances PHP depuis l'étape de build
COPY --from=composer_builder /app/vendor /var/www/html/vendor

#Copie du code source
COPY . .

#Optimisations Laravel et permissions
RUN chown -R www-data:www-data /var/www/html/storage /var/www/html/bootstrap/cache 
    && chmod -R 775 /var/www/html/storage /var/www/html/bootstrap/cache 
    && php artisan config:cache 
    && php artisan route:cache 
    && php artisan view:cache

    #Configuration Nginx pour Laravel
RUN echo 'server { 
    listen 8000; 
    root /var/www/html/public; 
    index index.php; 
    location / { 
        try_files uri $uri/ /index.php?$query_string; \
    } \
    location ~ \.php$ { \
        fastcgi_pass 127.0.0.1:9000; \
        fastcgi_index index.php; \
        include fastcgi_params; \
        fastcgi_param SCRIPT_FILENAME ocument_root$fastcgi_script_name; 
    } 
}' > /etc/nginx/http.d/default.conf

#Script de démarrage pour lancer Nginx et PHP-FPM ensemble
RUN echo '#!/bin/sh\nnginx &\nphp-fpm' > /start.sh && chmod +x /start.sh

EXPOSE 8000

CMD ["/start.sh"]