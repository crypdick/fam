---
name: fam-review
description: Review relationships with the user and save their choices as next steps, cadence changes, or reminders.
---

# FAM relationship review

Use [fam](../fam/SKILL.md) for note operations. For unattended preparation, use [fam-garden](../fam-garden/SKILL.md).

## Prepare the review

Read current person notes and any configured tracker and review state. Get the due queue, excluding snoozed people and scores below the threshold unless requested. Read notes using their exact paths.

Include unresolved prospects and older connections in the selection, even when the queue has due entries. Discover people in circles without cadence separately; they never appear in the queue, even with `next_action_at` set.

Use saved review history to vary the selection. Respect boundaries, deferrals, muted reminders, and the user's bandwidth. Leave unanswered questions pending until the configured revisit time unless there is an urgent reason to raise them.

## Work through choices

Use relevant notes and separately authorized sources to ground suggestions. Flag uncertain identities or meeting context. Help the user decide whom to prioritize, keep casual, defer, or stop pursuing, without pressure to maintain everyone.

Turn their choices into next steps and timing. Change circles or cadence only when the user selects them. Preserve person-specific overrides unless changed explicitly, and distinguish a one-time action date from recurring cadence.

## Save decisions

Save explicit answers and unresolved questions in the configured tracker or relationship notes. Keep contact history and reminder fields in person notes and link to them from the tracker.

In configured review state, record whom you surfaced and what the user answered or deferred. Suggested outreach remains uncompleted; log only reported or evidenced interactions. Summarize the updates saved.
