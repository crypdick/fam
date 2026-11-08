---
name: fam-garden
description: Reconcile configured prospect feeds and prepare relationship reviews without user involvement.
---

# FAM unattended gardening

Reconcile intake and prepare useful questions for review. Follow [fam](../fam/SKILL.md) for evidence, identity, note operations, and reminder rules. Use task or vault configuration for sources, trackers, state, time zone, schedules, and exceptions. External sources require separate authorization.

## Reconcile intake

Preserve the intake baseline: rediscovered historical entries are not new intake. Match stable row identities and known aliases rather than treating renames, imports, or changed timestamps as new people. Skip unchanged sources. If state is missing or corrupt, report it and preserve queued prospects; initialize only under the task's setup policy.

Check plausible candidates against person notes and relevant authorized context. Keep external searches scoped to the person; do not bulk-import an address book. Imports do not establish friendship interest, and absence from an address book does not exclude a candidate. Contact-addition dates can guide a calendar search but are not meeting evidence.

Save identified people with clear relationship-relevant interactions without extra approval. Record agreed plans, promised follow-ups, and supported important dates. Use `needs-triage` when circle intent is unclear. Keep uncertain identities pending with evidence and a focused question; propose likely duplicates in [fam-review](../fam-review/SKILL.md) for confirmation.

Save candidates and dispositions before advancing source checkpoints. Marking a row seen must not discard pending candidates. Leave source feeds unchanged.

## Prepare and save reviews

Rotate through a manageable selection of historical contacts or passive notes even when contacts are due. Use review history and respect boundaries, deferrals, and reminder preferences. Save useful context and questions; distinguish background inspection from presentation to the user. Unanswered questions remain pending under the revisit policy.

Re-read destinations before writing and preserve other workflows' content and state. Keep contact history in person notes; suggested outreach is not contact. Apply existing user decisions within task scope; leave unresolved relationship choices for review.

Follow task notification policy. Quiet scheduled runs save findings without routine notifications. Report new material blockers while continuing independent work.
