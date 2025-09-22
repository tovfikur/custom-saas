$TTL    300
@       IN      SOA     ns1.odoo-bangladesh.com. admin.odoo-bangladesh.com. (
                        2025092201  ; Serial
                        3600               ; Refresh
                        1800               ; Retry
                        604800             ; Expire
                        300 )              ; Negative Cache TTL

; Name servers
@       IN      NS      ns1.odoo-bangladesh.com.
ns1     IN      A       192.168.50.2

; Main domain
@       IN      A       192.168.50.2

; Wildcard - matches all subdomains
*       IN      A       192.168.50.2

; Common subdomains (explicit for better performance)
www     IN      A       192.168.50.2
api     IN      A       192.168.50.2
app     IN      A       192.168.50.2
dev     IN      A       192.168.50.2
test    IN      A       192.168.50.2
admin   IN      A       192.168.50.2
mail    IN      A       192.168.50.2
ftp     IN      A       192.168.50.2