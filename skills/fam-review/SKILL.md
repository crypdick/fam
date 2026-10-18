---
name: fam-review
description: Review relationships with the user, decide who they want to follow up with, and turn their answers into next steps and FAM cadence or reminder updates. Use for interactive friend CRM reviews and relationship prioritization.
---

# FAM relationship review

Use [FAM's note and command contract](../fam/SKILL.md) for reading and updating
people. This workflow involves the user in relationship decisions. Scheduled
preparation without their involvement belongs in [fam-garden](../fam-garden/SKILL.md).

## Prepare a useful review

Read the configured tracker and review state, if any, alongside current person
notes. Get the due queue with snoozed and below-threshold rows excluded unless
the user requests otherwise. Read relevant person notes using their exact paths.

Consider unresolved prospects and older connections as well as due relationships.
The queue excludes passive people and other circles without cadence, even when
they have `next_action_at`. Use person discovery or saved candidates to find
these relationships; rediscovery need not wait for an empty queue. Respect
explicit boundaries, deferrals, and muted reminders when choosing whom to raise.

Use saved review history to vary the selection and avoid repeatedly raising
unanswered questions. Follow the configured revisit timing; absent an urgent
reason, leave an unanswered question pending for a later review.

Ground suggestions in relevant notes and any separately authorized source
context. Surface uncertainty where identity, meeting context, or follow-through
is unclear. Adapt the selection and conversation to the user's bandwidth.

## Work through relationship choices

Help the user clarify interest, shared activities, reciprocity, closeness, and
available time where those affect the decision. The useful outcome might be
prioritizing someone, keeping things casual, deferring, or choosing not to pursue
the relationship. Support those choices without pressure to maintain everyone.

Translate the user's decisions into a realistic next step and suitable timing.
Change circles or cadence when the user selects them; do not infer a desired
cadence from a contact import or the mere existence of a person note. Preserve
an existing person-specific override unless the user changes it. Keep an exact
next-action date distinct from a recurring cadence.

## Save the outcome

Record explicit answers and decisions in the configured tracker or existing
relationship notes, with dates where useful. Keep unresolved hypotheses separate.
Use person notes for contact history and FAM reminder fields; link to them from
a tracker. `fam-tend` creates notes and never logs contacts or updates existing
relationship state.

Record what was surfaced, answered, or deferred in configured review state so
later reviews can continue without repeating the interview. Log only reported
or evidenced interactions, and leave suggested outreach uncompleted. Summarize
the decisions and updates actually saved.
