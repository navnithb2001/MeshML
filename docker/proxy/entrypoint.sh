#!/bin/sh
# Substitute backend hosts, preserving all nginx variables like $host, $remote_addr, etc.
envsubst '${API_GATEWAY_HOST} ${DATASET_SHARDER_HOST} ${TASK_ORCHESTRATOR_HOST} ${PARAMETER_SERVER_HOST} ${MODEL_REGISTRY_HOST} ${METRICS_SERVICE_HOST}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
exec nginx -g 'daemon off;'
