#!/bin/bash
# Wazuh Indexer Initialization Script
# This script runs on first boot via cloud-init

set -e

WAZUH_VERSION="${wazuh_version}"
MANAGER_IP="${manager_ip}"

echo "=== Wazuh Indexer Installation Started ===" | tee -a /var/log/wazuh-indexer-install.log

# Update system
apt-get update
apt-get upgrade -y

# Install prerequisites
apt-get install -y curl apt-transport-https lsb-release gnupg2

# Add Wazuh repository
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import && chmod 644 /usr/share/keyrings/wazuh.gpg
echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | tee -a /etc/apt/sources.list.d/wazuh.list

# Update package list
apt-get update

# Install Wazuh Indexer (OpenSearch/Elasticsearch-based)
apt-get install -y wazuh-indexer

# Get node IP
NODE_IP=$(hostname -I | awk '{print $1}')

# Configure Wazuh Indexer
cat > /etc/wazuh-indexer/opensearch.yml <<EOF
network.host: "$NODE_IP"
node.name: "indexer-node"
cluster.name: "wazuh-cluster"
node.master: true
node.data: true
path.data: /var/lib/wazuh-indexer
path.logs: /var/log/wazuh-indexer

# Bootstrap cluster
cluster.initial_master_nodes:
- "indexer-node"

# Network settings
http.port: 9200
transport.tcp.port: 9300

# Security settings
plugins.security.ssl.transport.pemcert_filepath: /etc/wazuh-indexer/certs/indexer.pem
plugins.security.ssl.transport.pemkey_filepath: /etc/wazuh-indexer/certs/indexer-key.pem
plugins.security.ssl.transport.pemtrustedcas_filepath: /etc/wazuh-indexer/certs/root-ca.pem
plugins.security.ssl.transport.enforce_hostname_verification: false
plugins.security.ssl.http.enabled: true
plugins.security.ssl.http.pemcert_filepath: /etc/wazuh-indexer/certs/indexer.pem
plugins.security.ssl.http.pemkey_filepath: /etc/wazuh-indexer/certs/indexer-key.pem
plugins.security.ssl.http.pemtrustedcas_filepath: /etc/wazuh-indexer/certs/root-ca.pem
plugins.security.allow_unsafe_democertificates: true
plugins.security.allow_default_init_securityindex: true
plugins.security.authcz.admin_dn:
- "CN=admin,OU=Wazuh,O=Wazuh,L=California,C=US"

plugins.security.audit.type: internal_opensearch
plugins.security.enable_snapshot_restore_privilege: true
plugins.security.check_snapshot_restore_write_privileges: true
plugins.security.restapi.roles_enabled: ["all_access", "security_rest_api_access"]

# Performance tuning
indices.query.bool.max_clause_count: 100000
indices.memory.index_buffer_size: 30%

# JVM heap settings (set to 50% of available RAM, max 32GB)
# This will be configured via jvm.options
EOF

# Configure JVM options for Indexer
cat > /etc/wazuh-indexer/jvm.options <<EOF
## JVM Configuration for Wazuh Indexer

## GC Settings
-XX:+UseG1GC
-XX:G1ReservePercent=25
-XX:InitiatingHeapOccupancyPercent=30

## Heap Size (set to 50% of system RAM)
-Xms8g
-Xmx8g

## DNS cache policy
-Des.networkaddress.cache.ttl=60
-Des.networkaddress.cache.negative.ttl=10

## Optimize string deduplication
-XX:+UseStringDeduplication

## GC Logging
-Xlog:gc*,gc+age=trace,safepoint:file=/var/log/wazuh-indexer/gc.log:utctime,pid,tags:filecount=32,filesize=64m
EOF

# Format and mount data disk
if [ -b /dev/sdc ]; then
    echo "Formatting and mounting data disk..."
    mkfs.ext4 /dev/sdc
    mkdir -p /mnt/wazuh-data
    mount /dev/sdc /mnt/wazuh-data
    echo '/dev/sdc /mnt/wazuh-data ext4 defaults,nofail 0 2' >> /etc/fstab

    # Move data directory to mounted disk
    mkdir -p /mnt/wazuh-data/lib
    mkdir -p /mnt/wazuh-data/log
    chown -R wazuh-indexer:wazuh-indexer /mnt/wazuh-data

    # Update paths
    sed -i 's|path.data: /var/lib/wazuh-indexer|path.data: /mnt/wazuh-data/lib|g' /etc/wazuh-indexer/opensearch.yml
    sed -i 's|path.logs: /var/log/wazuh-indexer|path.logs: /mnt/wazuh-data/log|g' /etc/wazuh-indexer/opensearch.yml
fi

# Generate certificates
mkdir -p /etc/wazuh-indexer/certs
cd /etc/wazuh-indexer/certs

# Generate root CA
openssl genrsa -out root-ca-key.pem 2048
openssl req -new -x509 -sha256 -key root-ca-key.pem -subj "/C=US/ST=California/L=California/O=Wazuh/OU=Wazuh/CN=root-ca" -out root-ca.pem -days 3650

# Generate indexer certificate
openssl genrsa -out indexer-key-temp.pem 2048
openssl pkcs8 -inform PEM -outform PEM -in indexer-key-temp.pem -topk8 -nocrypt -v1 PBE-SHA1-3DES -out indexer-key.pem
openssl req -new -key indexer-key.pem -subj "/C=US/ST=California/L=California/O=Wazuh/OU=Wazuh/CN=indexer" -out indexer.csr
openssl x509 -req -in indexer.csr -CA root-ca.pem -CAkey root-ca-key.pem -CAcreateserial -sha256 -out indexer.pem -days 3650

# Generate admin certificate
openssl genrsa -out admin-key-temp.pem 2048
openssl pkcs8 -inform PEM -outform PEM -in admin-key-temp.pem -topk8 -nocrypt -v1 PBE-SHA1-3DES -out admin-key.pem
openssl req -new -key admin-key.pem -subj "/C=US/ST=California/L=California/O=Wazuh/OU=Wazuh/CN=admin" -out admin.csr
openssl x509 -req -in admin.csr -CA root-ca.pem -CAkey root-ca-key.pem -CAcreateserial -sha256 -out admin.pem -days 3650

# Set permissions
chown -R wazuh-indexer:wazuh-indexer /etc/wazuh-indexer/certs
chmod 500 /etc/wazuh-indexer/certs
chmod 400 /etc/wazuh-indexer/certs/*

# Clean up temp files
rm -f *-temp.pem *.csr *.srl

# Enable and start Wazuh Indexer
systemctl daemon-reload
systemctl enable wazuh-indexer
systemctl start wazuh-indexer

# Wait for indexer to start
sleep 30

# Initialize security index
/usr/share/wazuh-indexer/plugins/opensearch-security/tools/securityadmin.sh \
  -cd /usr/share/wazuh-indexer/plugins/opensearch-security/securityconfig/ \
  -icl -nhnv \
  -cacert /etc/wazuh-indexer/certs/root-ca.pem \
  -cert /etc/wazuh-indexer/certs/admin.pem \
  -key /etc/wazuh-indexer/certs/admin-key.pem

# Configure firewall
ufw allow 22/tcp
ufw allow 9200/tcp
ufw allow 9300/tcp
ufw --force enable

# Create index templates for CDR metrics
cat > /tmp/cdr-template.json <<'EOFTEMPLATE'
{
  "index_patterns": ["cdr-metrics-*"],
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0,
      "refresh_interval": "5s"
    },
    "mappings": {
      "properties": {
        "timestamp": { "type": "date" },
        "test_run_id": { "type": "keyword" },
        "file_name": { "type": "keyword" },
        "file_hash": { "type": "keyword" },
        "phase": { "type": "keyword" },
        "edr_vendor": { "type": "keyword" },
        "edr_alerts": { "type": "integer" },
        "edr_severity": { "type": "keyword" },
        "av_vendor": { "type": "keyword" },
        "av_detections": { "type": "integer" },
        "av_threats_found": { "type": "text" },
        "processing_time_seconds": { "type": "float" },
        "vm_cost_usd": { "type": "float" }
      }
    }
  }
}
EOFTEMPLATE

# Wait a bit more for cluster to be ready
sleep 10

# Apply index template
curl -X PUT "https://localhost:9200/_index_template/cdr-metrics" \
  -H 'Content-Type: application/json' \
  -u admin:admin \
  --cacert /etc/wazuh-indexer/certs/root-ca.pem \
  -d @/tmp/cdr-template.json

echo "=== Wazuh Indexer Installation Completed ===" | tee -a /var/log/wazuh-indexer-install.log

# Save installation summary
cat > /root/wazuh-indexer-info.txt <<EOF
Wazuh Indexer Installation Complete
====================================
Indexer IP: $NODE_IP
Indexer URL: https://$NODE_IP:9200

Default Credentials:
  Username: admin
  Password: admin

IMPORTANT: Change default credentials immediately!

Health Check:
  curl -k -u admin:admin https://$NODE_IP:9200/_cluster/health?pretty

Installation Log: /var/log/wazuh-indexer-install.log
EOF

cat /root/wazuh-indexer-info.txt
