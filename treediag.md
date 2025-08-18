AzureARC-pipelines.yml              # ADO pipeline definition (Arc onboarding only)

Linux_VM/
├─ playbook/
│  ├─ playbook.yml                  # Entry playbook (calls Arc role)
│  └─ inventory.yml                 # Hosts inventory
│
└─ roles/
   └─ arc_onboard/
      ├─ tasks/
      │  └─ main.yml                # Arc connect + verify tasks
      │
      └─ defaults/
         └─ main.yml                # Non-secret Arc vars (tenant, sub, RG, etc.)
