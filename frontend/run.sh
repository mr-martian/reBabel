#!/bin/bash

docker run --mount type=bind,source=$(pwd),target=/home/dangswan -p 9001:9001 rebabel:frontend
