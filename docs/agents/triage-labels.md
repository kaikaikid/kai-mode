# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Lane labels

The airport playbook also uses four lane queue labels. Their strings are fixed; the ground crew applies them, the tower reads them and never edits them. Create any missing one once:

```bash
gh label create main-queue   --description "机长道排队"
gh label create deputy-queue --description "副机长道排队"
gh label create second-queue --description "二副道排队"
gh label create ace-queue    --description "王牌飞行员加急队列"
```

| Label in our tracker | Lane | Meaning |
| -------------------- | ---- | ------- |
| `main-queue`         | main | Pin this ticket to the captain (主机长) lane |
| `deputy-queue`       | deputy | Pin this ticket to the copilot (副机长) lane |
| `second-queue`       | second | Pin this ticket to the second officer (二副) lane |
| `ace-queue`          | ace | Ace expedited queue; excluded from the tower's backlog pool |

- No lane label ⇒ the tower schedules the ticket normally (affinity first, then balance).
- `main-queue` / `deputy-queue` / `second-queue` are explicit pins: the tower must place the ticket in that lane, even if affinity or balance would prefer another. If it already sits in a different day table, the tower moves the row.
- `ace-queue` keeps its original meaning: the ace consumes it in `-ace.md`; the tower excludes it from the normal pool.
