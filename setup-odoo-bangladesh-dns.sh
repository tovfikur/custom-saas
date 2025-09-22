#!/bin/bash

echo "Setting up bind9 configuration for odoo-bangladesh.com -> 192.168.50.2"

# Copy the zone file
echo "Copying zone file..."
cp /home/kendroo/custom-saas/db.odoo-bangladesh.com /etc/bind/zones/
chown bind:bind /etc/bind/zones/db.odoo-bangladesh.com
chmod 644 /etc/bind/zones/db.odoo-bangladesh.com

# Add zone configuration to named.conf.local
echo "Adding zone configuration..."
cat >> /etc/bind/named.conf.local << 'EOF'

// odoo-bangladesh.com zone
zone "odoo-bangladesh.com" {
    type master;
    file "/etc/bind/zones/db.odoo-bangladesh.com";
};
EOF

# Test configuration
echo "Testing bind9 configuration..."
named-checkconf
if [ $? -eq 0 ]; then
    echo "✓ named.conf syntax is valid"
else
    echo "✗ named.conf syntax error"
    exit 1
fi

named-checkzone odoo-bangladesh.com /etc/bind/zones/db.odoo-bangladesh.com
if [ $? -eq 0 ]; then
    echo "✓ Zone file is valid"
else
    echo "✗ Zone file error"
    exit 1
fi

# Restart bind9
echo "Restarting bind9 service..."
systemctl restart bind9
if [ $? -eq 0 ]; then
    echo "✓ bind9 restarted successfully"
else
    echo "✗ Failed to restart bind9"
    exit 1
fi

# Test DNS resolution
echo "Testing DNS resolution..."
dig @localhost odoo-bangladesh.com A +short
echo ""
echo "Setup complete! odoo-bangladesh.com now points to 192.168.50.2"