# ADO_schedule_example.md

schedules:
- cron: "0 3 * * *"   # Every day at 03:00 UTC
  displayName: Daily 3AM build
  branches:
    include:
      - main
  always: true   # run even if no code changes


  azure-pipelines.yml


Additional notes

✅ Requirements / Config in ADO

*Pipelines must be YAML-based (if you’re using Classic, the UI schedule handles it).

* In YAML, the schedules: block goes at the root level.

* If you mis-indent, ADO ignores it silently.

* Schedules only run on the default branch unless you explicitly specify branches.include.

* Default branch is set in Project Settings → Repositories → [repo] → Options → Default branch for manual and scheduled builds.

* Pipeline Triggers tab in the UI:

* Even for YAML, you’ll see a “Triggers” tab. That’s where you can confirm that the schedule parsed correctly.

* If schedules: isn’t valid, the tab will show no schedules.

* Project Settings → Pipelines → Settings:

* There’s a global toggle “Allow pipeline triggers to run”. If that’s disabled, schedules won’t fire.

* Also, if the repo is GitHub, the ADO service connection needs rights to read branches.

Timezone:

  * The cron in YAML is always UTC. There’s no knob in ADO to change this—you have to offset the cron expression manually if you want local time.
