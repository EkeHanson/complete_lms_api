#!/bin/bash
set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running migrations..."
python manage.py migrate

echo "Creating log directory..."
mkdir -p /tmp/logs

echo "Adding cron jobs..."
python manage.py crontab add

echo "Deployment setup complete."