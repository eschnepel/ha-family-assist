#!/usr/bin/with-contenv bashio

export PYTHONPATH=/app
export PYTHONUNBUFFERED=1
export FA_DATA=/data

bashio::log.info "Starting Family Assist"
exec /opt/venv/bin/python -m assistd
