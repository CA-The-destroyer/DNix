#!/usr/bin/env bash
set -euo pipefail

LOG="/var/log/arc_mde_selfheal_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

say() { echo -e "[+] $*"; }
fail() { echo -e "[x] $*"; exit 1; }

# --- Sanity
command -v azcmagent >/dev/null || fail "azcmagent not found in PATH."
say "Arc agent: $(azcmagent version || true)"

# --- Check for guestconfig + himds units in both canonical paths
has_unit() {
  local unit="$1"
  systemctl list-unit-files | awk '{print $1}' | grep -qx "$unit"
}

check_units() {
  local missing=0
  for u in guestconfig.service himds.service; do
    if has_unit "$u"; then
      say "$u found"
    else
      say "$u MISSING"
      missing=1
    fi
  done
  return $missing
}

check_units || NEED_REPAIR=1 || true

# --- Try lightweight repair first: (re)lay down units without disconnecting
if [[ "${NEED_REPAIR:-0}" -eq 1 ]]; then
  say "Attempting in-place repair to lay down guestconfig/himds…"
  curl -fsSL -o /tmp/install_linux_azcmagent.sh https://aka.ms/azcmagent
  chmod +x /tmp/install_linux_azcmagent.sh
  # --force to re-lay components even if version matches
  sudo /bin/bash -x /tmp/install_linux_azcmagent.sh --enable-guest-configuration --force || true
  systemctl daemon-reload || true
fi

# Re-check
if ! check_units; then
  say "Units still missing. Proceeding with clean uninstall/reinstall (resource will disconnect)."
  # Capture resource ID for reconnect guidance (if needed)
  azcmagent show || true

  # Attempt graceful disconnect; do not fail script if this errors
  azcmagent disconnect --force || true

  # Uninstall and remove any stale bits
  azcmagent uninstall || true
  rm -rf /opt/azcmagent /var/opt/azcmagent || true

  # Fresh install with guest configuration
  curl -fsSL -o /tmp/install_linux_azcmagent.sh https://aka.ms/azcmagent
  chmod +x /tmp/install_linux_azcmagent.sh
  /bin/bash -x /tmp/install_linux_azcmagent.sh --enable-guest-configuration

  systemctl daemon-reload
fi

# Enable and start services
for svc in himds guestconfig; do
  say "Enabling and starting $svc…"
  systemctl enable --now "$svc"
  systemctl status "$svc" --no-pager || fail "$svc failed to start"
done

# Quick plumbing sanity
say "Arc extension plumbing check:"
azcmagent check || true
azcmagent extensions list || true

# --- Deploy MDE extension if not present
if ! azcmagent extensions list 2>/dev/null | grep -q "MDE.Linux"; then
  say "Installing Defender (MDE.Linux) extension…"
  azcmagent extensions install --name MDE.Linux || fail "Failed to install MDE extension"
else
  say "MDE extension already registered."
fi

# --- Validate Microsoft repo and install mdatp if needed (proves connectivity)
if ! rpm -qa | grep -qi '^mdatp'; then
  say "Ensuring Microsoft packages repo is reachable…"
  if ! ls /etc/yum.repos.d/microsoft-*.repo >/dev/null 2>&1; then
    say "Adding Microsoft repo…"
    # RHEL 9 path; RHEL 8/7 script still works and selects proper prod repo
    curl -fsSL -o /etc/yum.repos.d/microsoft-prod.repo https://packages.microsoft.com/config/rhel/9/prod.repo || true
  fi
  say "Installing mdatp package (validates repo + prereqs)…"
  # Fall back to yum if dnf missing
  if command -v dnf >/dev/null; then sudo dnf install -y mdatp || true; else sudo yum install -y mdatp || true; fi
fi

# --- Final health
if command -v mdatp >/dev/null; then
  say "mdatp present. Health:"
  mdatp health --details || true
else
  say "mdatp not installed yet—extension should complete the install shortly if repo connectivity is good."
fi

say "Done. Log: $LOG"
