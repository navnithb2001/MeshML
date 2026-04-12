FROM nginx:alpine

COPY nginx.conf.template /etc/nginx/nginx.conf.template

# Only substitute GATEWAY_IP, leaving nginx variables ($host, $remote_addr, etc.) intact
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080 8000 8001 8002 8003 8004 8005 50051 50052 50053 50054 50055
CMD ["/entrypoint.sh"]
