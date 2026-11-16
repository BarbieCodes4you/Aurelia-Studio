# Aurelia: Python standard library only, no pip install needed.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    AURELIA_DATA_DIR=/data \
    HOST=0.0.0.0 \
    PORT=8040 \
    APP_ENV=production
WORKDIR /app
COPY . /app
RUN useradd --create-home aurelia && mkdir -p /data && chown -R aurelia /data /app/static/css
USER aurelia
VOLUME ["/data"]
EXPOSE 8040
CMD ["python3", "run.py"]
