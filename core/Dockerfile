FROM debian:bullseye-slim
ENV LANG C.UTF-8

RUN sudo apt-get -qy --no-install-recommends install python3 pip

RUN sudo pip3 install flask gunicorn

EXPOSE 9000

WORKDIR /home/dangswan

CMD gunicorn -w 2 core:core -b :9000
