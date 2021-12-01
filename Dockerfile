FROM python:3.9.4-buster
USER root

COPY . /app
WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg libopus-dev

RUN python -m pip install \
--upgrade pip \
--upgrade setuptools \
-r requirements.txt

CMD [ "python3", "smilebot.py" ]