# Studio — React 19 + MapLibre SPA, inlined to a single index.html by Vite.
# The browser talks only to the gateway via the same-origin /api proxy below.
FROM node:24-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable pnpm && corepack prepare pnpm@10.34.9 --activate && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# Same-origin /api proxy: Studio builds API_BASE = "" so every call is /api/v1/*.
# /health is exposed for smoke tests; hash routing needs no server-side fallback.
RUN printf 'server {\n\
  listen 80;\n\
  root /usr/share/nginx/html;\n\
  index index.html;\n\
  location /api/ {\n\
    proxy_pass http://gateway:8000;\n\
    proxy_set_header Host $host;\n\
    proxy_set_header X-Real-IP $remote_addr;\n\
  }\n\
  location /health {\n\
    proxy_pass http://gateway:8000;\n\
  }\n\
  location / {\n\
    try_files $uri $uri/ /index.html;\n\
  }\n\
}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
