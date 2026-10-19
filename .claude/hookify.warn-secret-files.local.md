---
name: warn-secret-files
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: (^|[\\/])(\.env[^\\/]*|alerts\.json|tv\.json|tv_device\.json|autostart\.json|live_state\.json|memory\.db)$
---

🔐 **This file holds secrets or machine-local state.**

It is gitignored on purpose. Never commit it, never paste its keys into chat, code or logs.
