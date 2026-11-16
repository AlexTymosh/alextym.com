# Operational workflows

Use Workforce Management with a Member grant. Expand a section to see its latest
records and choose an action. Source identifiers are short fictional codes.
The establishment-line picker shows the service area, location and role behind
each code. Audit History shows the recorded changes and request correlation.

- Add a synthetic employee with an initial contract and assignment. Click their
  name or look up the employee ID to see effective-dated history. The profile
  accepts a fictional first name and surname initial such as `Aria P.`.
  Existing aliases beginning with `Demo` are also accepted. A contract can
  be substantive or temporary, with a fixed end date if needed.
- A changed contract or assignment takes effect on the chosen day. Existing
  intervals are half-open: their end date is the first day they no longer apply.
  A second change at the same boundary corrects that interval and records an
  audit diff. Leave closes both histories on the first inactive day. The employee
  and prior periods remain available. Progression also writes a dated event linked
  to the old and new assignments.
- Request a vacancy, approve it against an active establishment line, then publish
  it. An approval beyond remaining capacity requires a reason. The reason flags
  any resulting overfill explicitly. Cancellation or administrative closure
  stops open recruitment and retains prior hires; it never creates an employee
  or changes budgeted WTE.
- Record an application against a published vacancy, screen and shortlist it,
  and record a successful or unsuccessful interview. Only a successful
  interview permits a conditional offer. Accepted offers proceed to checks,
  confirmed dates and actual starts. An actual start creates linked substantive
  employment and is counted once. Probation can be extended before a final
  outcome. Learning and PDR are dated records with stable event IDs.
- Reference codes may be retired for new writes. Historical assignments keep the
  original code. Use a new role code if its pay band changes. The operations
  preserve the employee, vacancy and application IDs as stable source keys.

The established interview fixture is migrated in place: existing interview and
successful-check stages linked to offers are carried over into source records.
People Voice and the read-only Gold reports keep their existing cutoffs.

## Synthetic baselines

The app opens on the interview fixture to keep the walkthrough predictable.
Choose **Load full dataset** for 4,400 synthetic employees and the observed
period from November 2023 through October 2026. **Controlled baseline** always
uses seed 424400. **Exploratory** generates a new seed; enter a previously
displayed seed to reproduce that source population. Generation metadata is
exposed through `/demo/status`. **Reset demo** returns to the original fixture.
Both actions replace the shared Workforce dataset and require explicit
confirmation. See the [reference inventory](sources.md) for the modelling
assumptions and verified public context.
