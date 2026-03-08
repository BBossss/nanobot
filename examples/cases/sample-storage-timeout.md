---
id: INC-20260308-001
title: storage timeout on node-1
source: example
created_at: 2026-03-08T12:00:00
trigger: manual
host: node-1
service: storage
severity: high
status: open
root_cause: pending
tags:
  - storage
  - timeout
---

# Problem
node-1 reported repeated storage timeout events and user IO latency increased.

# Evidence
- `/var/log/storage.log` contained multiple `timeout` and `retry` messages
- `iostat` showed sustained await increase on the affected disk group

# Conclusion
The issue is likely within the storage stack on node-1, but the exact root cause still needs hardware and service verification.

# Suggestion
1. Continue with readonly diagnostics to confirm whether the problem is disk, service, or backend replication.
2. If impact expands, consider controlled failover or workload isolation after manual approval.
