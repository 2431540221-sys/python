#!/usr/bin/env bash
# Chạy khi deploy lên Render/Railway
set -o errexit
pip install -r requirements-prod.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
