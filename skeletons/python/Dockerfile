FROM python:3.12-alpine
WORKDIR /app
COPY app.py ./
USER 1000
EXPOSE {{APP_PORT}}
ENV PORT={{APP_PORT}}
HEALTHCHECK --interval=30s --timeout=5s CMD ["wget", "-qO-", "http://localhost:{{APP_PORT}}/healthz"]
CMD ["python", "app.py"]
