# syntax=docker/dockerfile:1

FROM python:3.13-slim-bookworm

WORKDIR /app

RUN apt-get update
RUN apt-get install -y git

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

RUN mkdir -p /usr/share/fonts/truetype/
RUN install -m644 fonts/TitilliumWeb-Regular.ttf /usr/share/fonts/truetype/
RUN install -m644 fonts/TitilliumWeb-Bold.ttf /usr/share/fonts/truetype/
RUN install -m644 fonts/TitilliumWeb-Italic.ttf /usr/share/fonts/truetype/
RUN install -m644 fonts/TitilliumWeb-BoldItalic.ttf /usr/share/fonts/truetype/

CMD [ "python3", "UpdatingBot.py"]