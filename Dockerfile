FROM eclipse-temurin:8-jre AS java8
FROM eclipse-temurin:11-jre AS java11
FROM eclipse-temurin:17-jre AS java17
FROM eclipse-temurin:21-jre AS java21
FROM eclipse-temurin:25-jre AS java25

FROM rust:1-bookworm AS bore-build
RUN cargo install bore-cli --locked

FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y wget curl libfreetype6 libfontconfig1 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=java8 /opt/java/openjdk /opt/java/jdk8
COPY --from=java11 /opt/java/openjdk /opt/java/jdk11
COPY --from=java17 /opt/java/openjdk /opt/java/jdk17
COPY --from=java21 /opt/java/openjdk /opt/java/jdk21
COPY --from=java25 /opt/java/openjdk /opt/java/jdk25
ENV JAVA_8_HOME=/opt/java/jdk8 \
    JAVA_11_HOME=/opt/java/jdk11 \
    JAVA_17_HOME=/opt/java/jdk17 \
    JAVA_21_HOME=/opt/java/jdk21 \
    JAVA_25_HOME=/opt/java/jdk25

WORKDIR /app

COPY . /app
COPY --from=bore-build /usr/local/cargo/bin/bore /usr/local/bin/bore

RUN pip install -r requirements.txt

CMD ["python", "app.py"]
