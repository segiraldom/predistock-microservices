FROM php:8.4-cli-alpine

# Instalar extensiones necesarias
RUN docker-php-ext-install bcmath

# Instalar Composer
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /app

# 1. Copiar manifiestos de Composer
COPY composer*.json ./

# 2. Instalar dependencias sin ejecutar scripts de artisan todavía
RUN composer install --no-dev --no-interaction --prefer-dist --optimize-autoloader --no-scripts

# 3. Copiar el resto del código del proyecto (incluye artisan, app, routes, etc.)
COPY . .

# 4. Ejecutar el auto-discovery de Laravel ahora que artisan ya existe en /app
RUN php artisan package:discover --ansi

EXPOSE 8000

CMD ["php", "artisan", "serve", "--host=0.0.0.0", "--port=8000"]