---
name: fam-garden
description: Reconcile configured prospect feeds and prepare relationship reviews without user involvement.
---

# FAM unattended gardening

Use [fam](../fam/SKILL.md) for note operations. Sources, tracker paths, review state, time zone, schedules, and exceptions come from the task or vault configuration. External sources require separate authorization.

Apply existing user decisions within the task's scope. Save clear plans, promised follow-ups, and supported important dates to FAM without asking permission. Assume Ricardo wants to make plans unless he explicitly says he does not and that boundary is recorded in the person note. Use `needs-triage` for a newly identified person whose substantive circle is unclear; leave uncertain identity matches for [fam-review](../fam-review/SKILL.md) and propose likely duplicates there for confirmation.

## Reconcile intake

Read configured feeds, tracker, and intake state. Preserve the baseline: historical entries can be rediscovered but are not new intake. If state is missing or corrupt, report it and preserve queued prospects. Initialize a baseline only under the task's setup policy.

Compare stable row identities and known aliases. Renames, imports, changed timestamps, and reappearing rows do not necessarily mean new people. Skip unchanged sources while continuing other intake.

Check plausible candidates against existing person notes and relevant authorized context. A contact import does not establish friendship interest; absence from an address book does not exclude a candidate. Limit external searches to the relevant person and context. Treat contact-addition dates as tentative calendar search anchors, not meeting evidence.

Save an identified person with a clear relationship-relevant interaction in FAM using `needs-triage` when the final circle is unclear; do not wait for approval to save an obvious record or action. Keep uncertain identities pending with evidence and one question. Avoid importing an entire address book. Save candidates and dispositions before advancing source checkpoints; retain pending candidates after marking rows seen.

## Prepare reviews

Rotate through a manageable batch of historical contacts or passive person notes, even when the due queue has entries. Use saved review history and respect boundaries and reminder preferences.

Save useful context and questions. Record background inspection separately from presentation to the user. Unanswered questions stay pending under the revisit policy.

## Save and finish

Re-read destinations before editing and merge changes without overwriting other workflows' content or state. Keep contact history in person notes. Do not edit source feeds or log suggested outreach as contact.

Follow the task's notification policy. Quiet scheduled runs save findings for review without routine notifications. Report new material blockers, continue independent work, and leave relationship questions pending.
