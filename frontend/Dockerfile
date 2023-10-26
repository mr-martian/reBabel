FROM debian:bullseye-slim
ENV LANG C.UTF-8

RUN useradd -ms /bin/bash dangswan

RUN apt-get update && apt-get -qy --no-install-recommends install python3 pip

RUN pip3 install Django==4.2 requests==2.31 gunicorn

WORKDIR /home/dangswan

EXPOSE 9001

USER dangswan

CMD gunicorn -w 2 wsgi:application -b :9001 --capture-output --error-logfile /home/dangswan/errors.txt
