Linux_VM/
├─ playbook/
│  ├─ playbook.yml          # entry point playbook (calls the role)
│  └─ inventory.yml         # inventory file for target hosts
│
└─ roles/
   └─ lin_defender_agent/
      ├─ tasks/
      │  └─ main.yml        # all tasks (Arc connect, verify, etc.)
      │
      ├─ defaults/
      │  └─ main.yml        # safe, overridable vars (tenant, sub, RG, tags…)
      │
      ├─ vars/              # (optional) high-precedence vars — avoid if possible
      │  └─ main.yml
      │
      ├─ files/             # (optional) static files to copy
      ├─ templates/         # (optional) Jinja2 templates
      └─ meta/              # (optional) role metadata
