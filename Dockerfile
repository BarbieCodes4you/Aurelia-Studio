# Aurelia Studio: Python standard library only, no pip install needed.
# The persistent disk is mounted at /data (Railway: add a Volume with mount path /data).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    AURELIA_DATA_DIR=/data \
    HOST=0.0.0.0 \
    PORT=8040 \
    APP_ENV=production
WORKDIR /app
COPY . /app
RUN useradd --create-home aurelia && mkdir -p /data && chown -R aurelia /data /app/static/css
EXPOSE 8040
# Starts as root only to fix /data ownership, then runs the app as the "aurelia" user.
CMD ["python3", "deploy/entrypoint.py"]
