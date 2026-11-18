FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
COPY web/src/ ./src/
RUN npm run build

FROM python:3.12-alpine
WORKDIR /app
COPY api/server.py ./
COPY --from=web /web/dist/ ./static/
USER 1000
EXPOSE {{APP_PORT}}
ENV PORT={{APP_PORT}} STATIC_DIR=/app/static
HEALTHCHECK --interval=30s --timeout=5s CMD ["wget", "-qO-", "http://localhost:{{APP_PORT}}/healthz"]
CMD ["python", "server.py"]
