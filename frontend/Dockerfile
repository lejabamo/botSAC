FROM node:20-alpine AS build

WORKDIR /app

# Instalar dependencias
COPY package.json package-lock.json* ./
RUN npm ci

# Copiar el código fuente y construir
COPY . .
RUN npm run build

# Etapa de producción con Nginx
FROM nginx:alpine

# Copiar configuración custom de nginx para proxy reverso hacia /api/ y SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copiar los assets construidos de Vite al directorio público de Nginx
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
