FROM node:22-alpine AS build
ARG NPM_REGISTRY=https://registry.npmjs.org
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci --registry "$NPM_REGISTRY"
COPY frontend/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
