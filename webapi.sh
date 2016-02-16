#!/bin/bash

until python webapi.py; do
    echo "Server 'webapi.py' crashed with exit code $?.  Respawning.." >&2
    sleep 1
done
