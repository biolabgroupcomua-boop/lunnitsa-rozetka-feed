FROM python:3.12-slim
# tzdata: build_feed.py ставить у фід київський час збору (zoneinfo), у slim-образі зон немає
RUN pip install --no-cache-dir requests pillow tzdata
WORKDIR /app
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python", "server.py"]
