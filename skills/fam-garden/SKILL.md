---
name: fam-garden
description: Prepare FAM relationship reviews without user involvement by reconciling configured prospect feeds, preserving unresolved candidates, and rotating through older connections. Use for scheduled CRM intake and background review preparation; leave relationship choices for an interactive review.
---

# FAM unattended gardening

Use [FAM's note and command contract](../fam/SKILL.md). Work from configured
sources, tracker, review state, timezone, and existing user decisions. Feed
paths, baseline snapshots, schedules, and person-specific exceptions belong in
the user's task or vault configuration. This skill does not configure a watcher
or grant access to external accounts.

Complete useful preparation without requiring answers. Save unresolved questions
for [fam-review](../fam-review/SKILL.md); do not choose friendship interest,
circles, or cadence on the user's behalf. Existing explicit decisions may be
applied within the task's authorized scope.

## Reconcile intake

Read the configured feed, tracker, and saved intake state. Preserve an established
baseline; historical entries are eligible for rediscovery but are not new intake.
If expected baseline or state is missing or corrupt, report the problem and
preserve queued prospects rather than silently adopting the current feed as a
replacement baseline. Initialize a baseline only under the task's setup policy.

Compare stable row identities and known aliases with previously seen entries.
Renames, changed timestamps, imports, and reappearing rows do not automatically
mean new people. An unchanged export can skip that source's intake while other
configured sources and user-reported prospects remain eligible.

Cross-reference plausible candidates with existing person notes and relevant
authorized context. Keep candidates from different sources eligible on the same
terms; absence from an address book does not rule someone out. Equally, being a
contact, coworker, recruiter, or social connection does not establish friendship
interest.

Use external message or calendar context only when separately authorized and
available, with searches bounded to the relevant person and context. Contact
addition dates may reflect imports, so they are tentative calendar search anchors.
Keep possible meeting associations tentative. Do not read unrelated private
conversations or claim inaccessible history was checked.

Save clearly supported prospects in the configured tracker. Keep unresolved
plausible candidates in pending state with evidence and the question that would
resolve the uncertainty. Avoid filling the tracker with an entire contact import.
Save candidates and dispositions before advancing seen-row or export checkpoints,
and retain pending candidates after their source rows are marked seen.

## Prepare future reviews

Rotate through a manageable batch of historical contacts or passive person notes
using saved review history. Favor useful relationship context and possible
follow-through, while respecting boundaries and reminder preferences. Do this
independently of whether the due queue is empty.

Save useful cues and unresolved questions for the interactive review. Record
background inspection separately from a person being surfaced to the user or a
question being answered. An unanswered prompt stays pending under the configured
revisit policy; it does not become rejection or a completed review.

## Persist and finish

Re-read destinations before edits, merge intended changes, and preserve other
workflows' content and state fields. Keep person notes canonical for contact
history. Do not modify generated source feeds or record suggested outreach as
contact. Record only work actually performed.

Follow the task's notification policy. For quiet scheduled gardening, save useful
findings for review without a routine notification. Report a new material blocker
without claiming success, and continue work that does not depend on it. Leave
questions requiring user judgment pending rather than interrupting the run.
