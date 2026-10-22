---
name: fam-review
description: Review relationships with the user and save their choices as next steps, cadence changes, or reminders.
---

# FAM relationship review

Use [fam](../fam/SKILL.md) for note operations. For unattended preparation, use [fam-garden](../fam-garden/SKILL.md).

## Prepare the review

Read current person notes and any configured tracker and review state. Get the due queue, excluding snoozed people and scores below the threshold unless requested. Read notes using their exact paths.

Include unresolved prospects and older connections in the selection, even when the queue has due entries. `fam today` includes a separate `triage` list for `needs-triage` people and `actions` for one-off dates outside triage.

Use saved review history to vary the selection. Respect boundaries, deferrals, muted reminders, and the user's bandwidth. Leave unanswered questions pending until the configured revisit time unless there is an urgent reason to raise them.

## Work through choices

Use relevant notes and separately authorized sources to ground suggestions. Flag uncertain identities or meeting context. Help the user decide whom to prioritize, keep casual, defer, or stop pursuing, without pressure to maintain everyone.

Assume Ricardo wants to make plans unless he explicitly says he does not and that boundary is recorded in the person note. Add clear agreed plans, promised follow-ups, and supported important dates directly to FAM without asking permission. Set a useful action date and preserve concrete context. Never send messages or invitations. Use `needs-triage` when circle intent remains unclear; change to a substantive circle only when user choice or evidence supports it. Preserve person-specific overrides and distinguish one-time action dates from recurring cadence.

## Save decisions

Use the shared fam contact-logging and field-update operations from [fam](../fam/SKILL.md) for mechanical writes. Use file edits for free-form relationship context.

Save explicit answers and unresolved questions in the configured tracker or relationship notes. Keep contact history and reminder fields in person notes and link to them from the tracker.

In configured review state, record whom you surfaced and what the user answered or deferred. Suggested outreach remains uncompleted; log only reported or evidenced interactions. Summarize the updates saved.
