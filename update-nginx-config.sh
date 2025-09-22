#!/bin/bash

# Script to update Nginx configuration for odoo-bangladesh.com

echo "Updating Nginx configuration for odoo-bangladesh.com..."

# Copy the updated configuration to the sites-available directory
echo "Copying configuration..."
sudo cp /home/kendroo/custom-saas/nginx-odoo-bangladesh-ssl.conf /etc/nginx/sites-available/odoo-bangladesh.com

# Enable the site if not already enabled
echo "Enabling site..."
sudo ln -sf /etc/nginx/sites-available/odoo-bangladesh.com /etc/nginx/sites-enabled/

# Test nginx configuration
echo "Testing Nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "Configuration test passed. Reloading Nginx..."
    sudo systemctl reload nginx
    echo "Nginx reloaded successfully!"

    echo "Testing API endpoint..."
    sleep 2
    curl -X POST https://odoo-bangladesh.com/api/v1/auth/login \
         -H "Content-Type: application/x-www-form-urlencoded" \
         -d "username=admin@domain.com&password=admin"
else
    echo "Configuration test failed. Please check the configuration."
    exit 1
fi

echo "Configuration update complete!"