FROM python:3.12-alpine
WORKDIR /app
COPY app.py ./
USER 1000
EXPOSE 8080
ENV PORT=8080
HEALTHCHECK --interval=30s --timeout=5s CMD ["wget", "-qO-", "http://localhost:8080/healthz"]
CMD ["python", "app.py"]
