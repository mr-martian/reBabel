#!/bin/bash

docker run --mount type=bind,source=$(pwd),target=/home/dangswan -p 9000:9000 rebabel:core
