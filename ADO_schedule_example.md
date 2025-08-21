# ADO_schedule_example.md

schedules:
- cron: "0 3 * * *"   # Every day at 03:00 UTC
  displayName: Daily 3AM build
  branches:
    include:
      - main
  always: true   # run even if no code changes


  azure-pipelines.yml
