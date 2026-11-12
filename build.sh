#!/usr/bin/env bash
# Chạy khi deploy lên Render/Railway
set -o errexit
pip install -r requirements-prod.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
if [ "${LOAD_DEMO:-0}" = "1" ]; then
  python manage.py load_demo_data
fi
