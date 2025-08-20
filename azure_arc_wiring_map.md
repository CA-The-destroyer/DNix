# Azure Arc Onboarding — Wiring Map

```
AZURE ARC ONBOARDING — WIRING MAP (ASCII)

┌──────────────────────────────────────────────────────────────────────┐
│                      Azure DevOps (ADO) Project                      │
└──────────────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Library → Variable Group:  Azure-Linux-VDI                           │
│  ├─ user                (VM login username)                          │
│  ├─ **XAdmin_login      (VM login password, secret 🔒)               │
│  └─ defender_sp_secret  (Arc SP client secret, secret 🔒)            │
│     + optionally: arc_* non-secrets (tenant/sub/RG/location/appId)   │
└──────────────────────────────────────────────────────────────────────┘
               │ linked into
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Pipeline YAML: AzureARC-pipelines.yml                                │
│  variables:                                                          │
│    - group: Azure-Linux-VDI                                          │
│                                                                      │
│  steps/env aliases:                                                  │
│    defender_sp_secret  ← $(defender_sp_secret)                       │
│    ANSIBLE_USER        ← $(user)                                     │
│    ANSIBLE_PASSWORD    ← $(**XAdmin_login)                           │
│    ANSIBLE_ROLES_PATH  ← ./Linux_VM/roles                            │
│                                                                      │
│  runs: ansible-playbook -i Linux_VM/playbook/inventory.yml \         │
│                      Linux_VM/playbook/playbook.yml                  │
└──────────────────────────────────────────────────────────────────────┘
               │ feeds env into
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Inventory: Linux_VM/playbook/inventory.yml                           │
│  group: azure_vms                                                    │
│  hosts: 10.50.172.[11:50]   (or static IPs/hostnames)                 │
│  vars (from env):                                                    │
│    ansible_user     = {{ lookup('env','ANSIBLE_USER') }}             │
│    ansible_password = {{ lookup('env','ANSIBLE_PASSWORD') }}         │
└──────────────────────────────────────────────────────────────────────┘
               │ targeted by
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Playbook: Linux_VM/playbook/playbook.yml                              │
│  hosts: azure_vms                                                     │
│  gather_facts: true                                                   │
│  vars: defender_sp_secret = {{ lookup('env','defender_sp_secret') }}  │
│  roles:                                                               │
│    - arc_onboard                                                      │
└──────────────────────────────────────────────────────────────────────┘
               │ executes
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Role: Linux_VM/roles/arc_onboard                                     │
│  tasks/main.yml                                                       │
│    • Install azcmagent if missing                                     │
│    • Check pre-status                                                 │
│    • Skip connect if already onboarded                                │
│    • Derive arc_name from ansible_hostname/fqdn (legalize)            │
│    • (Optional) merge arc_tags                                        │
│    • Run azcmagent connect with SP creds, tenant, sub, RG, location   │
│    • Verify connection → Connected=true                               │
│    • On fail, dump status + log tail (safe, no secrets)               │
└──────────────────────────────────────────────────────────────────────┘
               │ results in
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Target VMs: RHEL VDI                                                 │
│  Services: himds, azcmagent                                          │
│  Logs: /var/opt/azcmagent/log/{azcmagent.log,himds.log}              │
│  Arc Resource: shows hostname (not raw IP) if facts are gathered      │
│  Tags: applied only if arc_tags defined; safe to omit                 │
└──────────────────────────────────────────────────────────────────────┘
```
