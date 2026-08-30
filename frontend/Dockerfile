FROM node:22-alpine AS build
WORKDIR /app
ARG VITE_API_BASE=/api/v2
ENV VITE_API_BASE=$VITE_API_BASE
COPY frontend/package.json frontend/package-lock.json ./
# Fail loudly on lockfile drift instead of silently falling back to `npm install`.
RUN npm ci
COPY frontend .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
# Pick up patched Alpine packages (openssl, expat, libpng, libxml2, musl, etc.)
# ahead of the next nginx:1.27-alpine image refresh, to keep the Trivy CVE gate green.
USER root
RUN apk update && apk upgrade --no-cache
COPY nginx/frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 101
EXPOSE 8080
