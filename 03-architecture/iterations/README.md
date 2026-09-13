# Model execution and handoff protocol

Revision 2. This file is written for an implementer with no chat history.
Start at [START_HERE.md](START_HERE.md), then the active brief.
[REGISTER.md](REGISTER.md) is the only authoritative task-status index.

## 1. First ten actions

1. Read the current user request. It controls scope and authorization.
2. Confirm project root: /home/yams/operations/project-sycamore.
3. Read START_HERE, the roadmap, specification and register.
4. Open the first READY or ACTIVE brief. Do not skip a prerequisite.
5. Read any applicable AGENTS.md and relevant skills required by your runtime.
6. Inspect only task-relevant current files; documentation can be stale.
7. Check Git status if available. If unavailable, record that and hash scoped
   files. Never initialize/reset Git merely to make a report look complete.
8. Record pre-existing changes. Preserve unrelated work.
9. Write the bounded execution checklist and set the brief ACTIVE.
10. Perform its first unchecked step. Keep the user informed of material findings.

Read only project data needed for the task; do not print secrets or private
account/configuration contents into logs.

## 2. Document authority

User instructions → applicable workspace instructions → this revision's
implementation specification for future behavior → current code/tests for
existing behavior → historical architecture notes.

A conflict is a finding, not permission to silently choose either side.
Record it in the brief, preserve current public behavior and make the smallest
compatible change. A new schema must not redefine a field's old meaning.

The roadmap defines outcomes; the specification defines invariants; the register
defines sequence; the brief defines the current implementation. Do not maintain
competing task-status lists in every document.

## 3. Iteration workflow

Before coding:
- List exact allowed files and prohibited side effects.
- Name fixtures, intended output artifacts and the tests proving the change.
- List dependencies and unresolved decisions.
- If implementing a later card, write its detailed brief from the template and
  specification first. If a required decision is absent, do independent work
  and ask one concise question; do not make up a provider, price or customer result.

During coding:
- Make one coherent slice at a time.
- Use existing helpers when they implement the specified behavior.
- Keep generated validators generated; register new tests in the actual runner.
- Do not bypass a failed assertion by weakening validation, inventing data,
  removing tests, raising limits or catching every exception without reporting it.
- Never run fixture ingestion against g3-astro/public/data or the installed timer.
- A plan to test is not evidence that a test passed.

At verification:
- Run focused tests first; run full affected suites before completing runtime work.
- A baseline failure is not caused by your change; preserve its evidence and
  decide whether it blocks the affected gate.
- Distinguish not run, failed, passed and blocked by environment.
- Report exact command, working directory, exit code, source commit/hash,
  fixture hash, elapsed time and output artifact.
- For UI work, use a real browser and the viewport/focus matrix in spec §7.
- For database work, run migration twice, recovery, restore, identity and constraint
  tests. PostgreSQL SQL requires PostgreSQL integration testing.

At closure:
- Check every acceptance item against evidence.
- Mark COMPLETE only when the gate passes; otherwise name the exact missing item.
- Update register row and next iteration.
- Record release state separately: local / staging / pilot / production.
- Continue within already authorized scope; passing a gate does not require
  another permission question by itself.

## 4. Required detailed brief template

Copy this structure for every new iteration; replace placeholders before coding.

    # Iteration <ID> — <title>
    Status: READY | ACTIVE | VALIDATING | COMPLETE | BLOCKED | FAILED
    Release state: none | local verified | staging verified | pilot | production
    Prerequisites: <IDs and evidence paths>
    Last updated: <actual timestamp>
    Executor: <model/contributor identifier>
    Source state: <commit or scoped hash-manifest path>

    ## Outcome
    <One observable user/platform capability>
    ## Read first
    <Exact existing files and spec sections>
    ## Allowed changes
    <Exact existing/new files, small additions if necessary>
    ## Non-goals and prohibited side effects
    <What must not happen in this iteration>
    ## Ordered steps
    - [ ] 1. <Concrete implementation step>
    - [ ] 2. <Concrete implementation step>
    ## Data examples and expected behavior
    <Normal input/output plus relevant edge cases>
    ## Tests
    <Test name, setup, action, expected outcome; actual commands/cwd>
    ## Migration and rollback
    <Explicit authority, ordering, configuration and recovery>
    ## Acceptance
    - [ ] <Measurable assertion and required evidence>
    ## Results
    <Passed/failed/not run, source state, command/exit, logs and measurements>
    ## Unresolved decisions
    <Known missing facts; who decides; independent work that can continue>
    ## Resume checkpoint
    Last completed step:
    Currently running process/tool session:
    Files changed:
    Next exact command/action:
    Pending gate:
    ## Handoff
    Next iteration:
    Why it is/isn't unblocked:
    Suggested model prompt:

## 5. Examples of acceptable evidence

Good: “fixture replay after crash at publication ACK: 0 duplicate source revisions,
legacy ID 103 unchanged; command exited 0; report path and source hash recorded.”

Bad: “Looks good,” “the previous model passed 21 tests,” “should be backward
compatible,” or “browser not available, but the build passed so layout is done.”

Good: “No user study yet. Discovery kit complete; commercial gate awaiting
participants. Technical work 1.2.1 can proceed.”

Bad: “Users liked it” based on model-generated personas.

## 6. Common failure responses

| Situation | Required next action |
| --- | --- |
| Missing input snapshot | Record absent; use labeled fixtures; don't call it real captured data |
| Test fails on unchanged code | Record baseline failure and relevance; don't silently patch out of scope |
| Network/port blocked | Record exact error; follow runtime approval rules; continue independent checks |
| Unknown schema field fails old client | Keep v1 unchanged; use versioned intelligence artifact |
| New test never ran | Import it in tests/run.ts or correct unittest discovery |
| Database migration fails halfway | Preserve original; inspect transaction/migration ledger; restore/retry in fresh test directory |
| Customer/provider/budget unknown | Leave decision pending; prepare local alternatives; don't launch or purchase |
| Context interruption | Read resume checkpoint, inspect modified files and active sessions; don't restart blindly |
| Old ID collision | Stop publication, preserve artifacts, repair mapping/counter with audit |
| Missing real-browser evidence | Mark visual gate unverified; do not claim overlap resolved |
| Vague later task | Expand its brief and test cases before implementation |

Do not add temporary workarounds to public UI as permanent product behavior.
Tests prove invariants; they must not just repeat the implementation's chosen
formula without an independent expected result.
