# Static web page server for WEB_HOST=cloudrun. Build context: a folder holding this file, nginx.conf
# and web/ (the Flutter web build); infra/deploy.ps1 puts it together. No key or secret goes in here.
FROM nginx:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY web /usr/share/nginx/html
EXPOSE 8080
