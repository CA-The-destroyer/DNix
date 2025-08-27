# Ensure the Microsoft repo is correct and enabled
sudo tee /etc/yum.repos.d/microsoft-prod.repo >/dev/null <<'EOF'
[microsoft-azure-prod]
name=Microsoft Azure Prod
baseurl=https://packages.microsoft.com/rhel/9/prod/
enabled=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc
EOF

sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
sudo dnf clean all
sudo dnf makecache --refresh

# If epel-cisco-openh264 is flaking, ignore it
sudo dnf -y --disablerepo=epel-cisco-openh264 install azcmagent
