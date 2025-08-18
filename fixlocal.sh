# 1) Home dir must be owned by the user and not group/world-writable
sudo chown -R localuser:localuser /home/localuser
sudo chmod 700 /home/localuser          # 755 is ok for password login, but 700 is safest for keys

# 2) SSH key path must be locked down
sudo mkdir -p /home/localuser/.ssh
sudo chmod 700 /home/localuser/.ssh
sudo touch /home/localuser/.ssh/authorized_keys
sudo chmod 600 /home/localuser/.ssh/authorized_keys

# 3) SELinux contexts (if Enforcing)
sudo restorecon -Rv /home/localuser/.ssh