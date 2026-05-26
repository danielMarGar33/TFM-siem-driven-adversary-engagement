# ETAPA 1: Construcción (Build)
FROM node:20-alpine as build-stage
WORKDIR /app
# Copiamos solo los package para aprovechar la caché de Docker
COPY package*.json ./
RUN npm install
# Copiamos el resto del código y compilamos
COPY . .
RUN npm run build

# ETAPA 2: Producción (Servidor Nginx)
FROM nginx:alpine as production-stage
# Copiamos los archivos compilados de la etapa anterior
COPY --from=build-stage /app/dist /usr/share/nginx/html
# Copiamos una configuración básica de Nginx (opcional, pero recomendada para Vue Router)
# COPY nginx.conf /etc/nginx/nginx.conf 

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
