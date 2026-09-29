#!/bin/bash
cd "$(dirname "$0")"; set -a; [ -f .env ] && . ./.env; set +a
python3 -c "from engine import data; print(data.refresh_all())"
