#!/bin/bash
# Wazuh Manager Initialization Script
# This script runs on first boot via cloud-init

set -e

WAZUH_VERSION="${wazuh_version}"
INDEXER_IP="${indexer_ip}"
STORAGE_ACCOUNT="${storage_account}"

echo "=== Wazuh Manager Installation Started ===" | tee -a /var/log/wazuh-install.log

# Update system
apt-get update
apt-get upgrade -y

# Install prerequisites
apt-get install -y curl apt-transport-https lsb-release gnupg2 software-properties-common

# Add Wazuh repository
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import && chmod 644 /usr/share/keyrings/wazuh.gpg
echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | tee -a /etc/apt/sources.list.d/wazuh.list

# Update package list
apt-get update

# Install Wazuh Manager
apt-get install -y wazuh-manager

# Configure Wazuh Manager
cat > /var/ossec/etc/ossec.conf <<EOF
<ossec_config>
  <global>
    <jsonout_output>yes</jsonout_output>
    <alerts_log>yes</alerts_log>
    <logall>no</logall>
    <logall_json>no</logall_json>
    <email_notification>no</email_notification>
  </global>

  <alerts>
    <log_alert_level>3</log_alert_level>
    <email_alert_level>12</email_alert_level>
  </alerts>

  <remote>
    <connection>secure</connection>
    <port>1514</port>
    <protocol>tcp</protocol>
    <queue_size>131072</queue_size>
  </remote>

  <logging>
    <log_format>plain</log_format>
  </logging>

  <ruleset>
    <decoder_dir>ruleset/decoders</decoder_dir>
    <rule_dir>ruleset/rules</rule_dir>
    <rule_exclude>0215-policy_rules.xml</rule_exclude>
    <list>etc/lists/audit-keys</list>
    <list>etc/lists/amazon/aws-eventnames</list>
    <list>etc/lists/security-eventchannel</list>
  </ruleset>

  <auth>
    <disabled>no</disabled>
    <port>1515</port>
    <use_source_ip>no</use_source_ip>
    <purge>yes</purge>
    <use_password>no</use_password>
    <ssl_agent_ca></ssl_agent_ca>
    <ssl_verify_host>no</ssl_verify_host>
    <ssl_manager_cert>/var/ossec/etc/sslmanager.cert</ssl_manager_cert>
    <ssl_manager_key>/var/ossec/etc/sslmanager.key</ssl_manager_key>
    <ssl_auto_negotiate>no</ssl_auto_negotiate>
  </auth>

  <cluster>
    <name>wazuh</name>
    <node_name>manager</node_name>
    <node_type>master</node_type>
    <key>c98b62a9b6169ac5f67dae55ae4a9088</key>
    <port>1516</port>
    <bind_addr>0.0.0.0</bind_addr>
    <nodes>
      <node>$(hostname -I | awk '{print $1}')</node>
    </nodes>
    <hidden>no</hidden>
    <disabled>no</disabled>
  </cluster>

  <vulnerability-detector>
    <enabled>yes</enabled>
    <interval>5m</interval>
    <ignore_time>6h</ignore_time>
    <run_on_start>yes</run_on_start>
    <feed name="ubuntu-20">
      <disabled>no</disabled>
      <update_interval>1h</update_interval>
    </feed>
    <feed name="redhat">
      <disabled>no</disabled>
      <update_from_year>2010</update_from_year>
      <update_interval>1h</update_interval>
    </feed>
    <feed name="windows">
      <disabled>no</disabled>
      <update_interval>1h</update_interval>
    </feed>
  </vulnerability-detector>

  <indexer>
    <enabled>yes</enabled>
    <hosts>
      <host>https://$INDEXER_IP:9200</host>
    </hosts>
    <ssl>
      <certificate_authorities>
        <ca>/etc/ssl/root-ca.pem</ca>
      </certificate_authorities>
      <certificate>/etc/ssl/filebeat.pem</certificate>
      <key>/etc/ssl/filebeat.key</key>
    </ssl>
  </indexer>
</ossec_config>
EOF

# Enable and start Wazuh Manager
systemctl daemon-reload
systemctl enable wazuh-manager
systemctl start wazuh-manager

# Install Filebeat for log forwarding to Wazuh Indexer
curl -L -O https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-7.17.13-amd64.deb
dpkg -i filebeat-7.17.13-amd64.deb

# Configure Filebeat
curl -so /etc/filebeat/filebeat.yml https://packages.wazuh.com/4.7/tpl/wazuh/filebeat/filebeat.yml

# Download Filebeat Wazuh module
curl -s https://packages.wazuh.com/4.x/filebeat/wazuh-filebeat-0.3.tar.gz | tar -xvz -C /usr/share/filebeat/module

# Configure Filebeat to connect to Indexer
sed -i "s/YOUR_INDEXER_IP/$INDEXER_IP/g" /etc/filebeat/filebeat.yml

# Enable and start Filebeat
systemctl daemon-reload
systemctl enable filebeat
systemctl start filebeat

# Install Wazuh API
apt-get install -y nodejs npm
cd /var/ossec/api
npm install

# Generate API credentials
cd /var/ossec/api/configuration/auth
node htpasswd -c user wazuh -b wazuh

# Start Wazuh API
systemctl enable wazuh-api
systemctl start wazuh-api

# Install and configure Dashboard (Kibana-based)
apt-get install -y wazuh-dashboard

# Configure dashboard
cat > /etc/wazuh-dashboard/opensearch_dashboards.yml <<EOF
server.host: 0.0.0.0
server.port: 443
opensearch.hosts: https://$INDEXER_IP:9200
opensearch.ssl.verificationMode: certificate
server.ssl.enabled: true
server.ssl.certificate: /etc/wazuh-dashboard/certs/wazuh-dashboard.pem
server.ssl.key: /etc/wazuh-dashboard/certs/wazuh-dashboard-key.pem
opensearch.username: kibanaserver
opensearch.password: kibanaserver
opensearch.requestHeadersAllowlist: ["securitytenant","Authorization"]
opensearch_security.multitenancy.enabled: true
opensearch_security.multitenancy.tenants.preferred: ["Private", "Global"]
opensearch_security.readonly_mode.roles: ["kibana_read_only"]
EOF

# Enable and start dashboard
systemctl daemon-reload
systemctl enable wazuh-dashboard
systemctl start wazuh-dashboard

# Configure firewall
ufw allow 22/tcp
ufw allow 443/tcp
ufw allow 1514/tcp
ufw allow 1515/tcp
ufw allow 55000/tcp
ufw --force enable

# Create custom integration directories
mkdir -p /var/ossec/integrations/custom
mkdir -p /var/ossec/logs/integrations

# Install Python for custom integrations
apt-get install -y python3 python3-pip
pip3 install requests pyyaml

echo "=== Wazuh Manager Installation Completed ===" | tee -a /var/log/wazuh-install.log

# Save installation summary
cat > /root/wazuh-info.txt <<EOF
Wazuh Manager Installation Complete
====================================
Manager IP: $(hostname -I | awk '{print $1}')
Dashboard URL: https://$(curl -s ifconfig.me)
API Endpoint: https://$(hostname -I | awk '{print $1}'):55000

Default Credentials:
  Username: wazuh
  Password: wazuh

IMPORTANT: Change default credentials immediately!

Agent Registration Command:
  wget -O /tmp/wazuh-agent.deb https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_$WAZUH_VERSION-1_amd64.deb
  WAZUH_MANAGER='$(hostname -I | awk '{print $1}')' dpkg -i /tmp/wazuh-agent.deb
  systemctl daemon-reload
  systemctl enable wazuh-agent
  systemctl start wazuh-agent

Installation Log: /var/log/wazuh-install.log
EOF

cat /root/wazuh-info.txt
