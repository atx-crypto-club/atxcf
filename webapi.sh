#!/bin/bash

until /usr/bin/python -m atxcf; do
    echo ":// atxcf webapi crashed with exit code $?.  Respawning.." >&2
    sleep 1
done
