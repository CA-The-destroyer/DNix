┌──────────────────────────────────────────────────────────────────────┐
│                      Azure DevOps (ADO) Project                      │
└──────────────────────────────────────────────────────────────────────┘
               │
               │ uses
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Library → Variable Group:  Azure-Linux-VDI                           │
│  ├─ user                 (username; non-secret or secret)            │
│  ├─ XAdmin_login       (password; secret 🔒)                       │
│  └─ defender_sp_secret   (Arc SP client secret; secret 🔒)           │
└──────────────────────────────────────────────────────────────────────┘
               │
               │ linked by
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Pipeline YAML:  AzureARC-pipelines.yml                               │
│  variables:                                                          │
│    - group: Azure-Linux-VDI   (injects all vars from the group)      │
│                                                                      │
│  steps:                                                              │
│    - checkout: self                                                  │
│    - bash:                                                           │
│        env mappings (aliases):                                       │
│          defender_sp_secret  ← $(defender_sp_secret)                 │
│          ANSIBLE_USER        ← $(user)                               │
│          ANSIBLE_PASSWORD    ← $(XAdmin_login)                     │
│          ANSIBLE_ROLES_PATH  ← ./Linux_VM/roles                      │
│        run: ansible-playbook -i Linux_VM/playbook/inventory.yml ...  │
└──────────────────────────────────────────────────────────────────────┘
               │
               │ provides env to
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Repo: Linux_VM/playbook/inventory.yml                                │
│  group: azure_vms                                                    │
│  vars read from ENV (no secrets in repo):                            │
│    ansible_user            = {{ lookup('env','ANSIBLE_USER') }}      │
│    ansible_password        = {{ lookup('env','ANSIBLE_PASSWORD') }}  │
└──────────────────────────────────────────────────────────────────────┘
               │
               │ targets hosts & calls
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Playbook: Linux_VM/playbook/playbook.yml                             │
│  hosts: azure_vms                                                    │
│  vars:                                                               │
│    defender_sp_secret = {{ lookup('env','defender_sp_secret') }}     │
│  roles:                                                              │
│    - arc_onboard                                                     │
└──────────────────────────────────────────────────────────────────────┘
               │
               │ loads role from
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Role: Linux_VM/roles/arc_onboard                                     │
│  defaults/main.yml    (non-secrets: tenant/sub/RG/location/tags…)    │
│  tasks/main.yml:                                                     │
│    1) sanity: azcmagent present?                                     │
│    2) status: azcmagent show (connected?)                            │
│    3) derive arc_name (hostname-first; IP fallback if needed)        │
│    4) connect:                                                       │
│       azcmagent connect                                              │
│         --service-principal-id      {{ arc_sp_app_id }}              │
│         --service-principal-secret  {{ defender_sp_secret }} 🔒       │
│         --tenant-id                 {{ arc_tenant_id }}              │
│         --subscription-id           {{ arc_subscription_id }}        │
│         --resource-group            {{ arc_resource_group }}         │
│         --location                  {{ arc_location }}               │
│         --resource-name             {{ arc_name }}                   │
│       (no_log: true to protect secrets)                              │
│    5) verify: azcmagent show / --json until Connected=true           │
│    6) diagnostics on failure (no secrets)                            │
└──────────────────────────────────────────────────────────────────────┘
               │
               │ configures
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Target VM (RHEL VDI)                                                 │
│  /opt/azcmagent/bin/azcmagent connect → Azure Arc                    │
│  Services: himds, azcmagent; logs under /var/opt/azcmagent/log/      │
└──────────────────────────────────────────────────────────────────────┘
