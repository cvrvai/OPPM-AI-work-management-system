FROM nginx:1.27-alpine

# Copy the single nginx configuration
COPY deploy/nginx/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
