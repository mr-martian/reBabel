FROM debian:bullseye-slim
ENV LANG C.UTF-8

RUN useradd -ms /bin/bash dangswan

RUN apt-get update && apt-get -qy --no-install-recommends install python3 pip

RUN pip3 install flask gunicorn

EXPOSE 9000

USER dangswan

WORKDIR /home/dangswan

CMD gunicorn -w 2 core:app -b :9000
