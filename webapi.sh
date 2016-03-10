#!/bin/bash

until /usr/bin/python -m atxcf; do
    echo "Server atxcf crashed with exit code $?.  Respawning.." >&2
    sleep 1
done
