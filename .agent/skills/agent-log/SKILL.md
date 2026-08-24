---
name: agent-log
description: Append session activity logs to AGENT_LOG.md at the end of work sessions. Use when updating or recording changes in AGENT_LOG.md.
---

# Agent Session Logging

At the end of every work session where code files were modified, append an entry to `AGENT_LOG.md` at the repository root.

## Format
```markdown
## YYYY-MM-DD — <short session goal>
- `path/to/file.py` — what changed (one line per file)
```
