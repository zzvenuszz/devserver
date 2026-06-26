FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y wget curl && \
    mkdir -p /usr/share/man/man1 && \
    apt-get install -y openjdk-25-jre-headless && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN chmod +x /app/playit

RUN pip install -r requirements.txt

CMD ["python", "app.py"]