# Static ValaDeploy UI: pages/, scripts/, styles/, and components/
FROM nginx:stable-alpine
COPY . /usr/share/nginx/html/
# index.html lives in pages/, but Nginx expects it at the document root.
RUN test -f /usr/share/nginx/html/pages/index.html \
    && cp /usr/share/nginx/html/pages/index.html /usr/share/nginx/html/index.html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
