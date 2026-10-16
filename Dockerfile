# Liquidity Engine dashboard + PAPER bot, always on (your PC can be off).
# Cloud mode is paper only: live eval orders go TradingView -> bridge, never through this container.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 TZ=America/New_York \
    HOST=0.0.0.0 PORT=8766 LE_CLOUD=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# LE_DASH_PASSWORD must be set in the host's environment settings (never in this file); the server refuses to start without it.
EXPOSE 8766
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8766\")}/api/health/ping',timeout=4)"
CMD ["python", "-u", "server.py"]
