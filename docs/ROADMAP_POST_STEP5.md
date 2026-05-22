# Roadmap After Step 5

This roadmap describes where OLRE should go after the confidence-gated traversal review milestone.

## Completed Milestones

- Step 1: runtime validation
- Step 2: traversal safety validation
- Step 3: real-world corpus classification
- Step 4: manual traversal evidence validation
- Step 5: confidence-gated review system

These steps established that OLRE can classify, queue, and govern traversal candidates conservatively before introducing any fetch behavior.

## Strategic Position After Step 5

OLRE now has:

- reference extraction
- destination metadata
- confidence/risk/recommended-action state
- exception-based operator review
- append-only review history

It does not yet have:

- controlled fetch execution
- recursive traversal governance
- child-document lifecycle handling

That is appropriate for current maturity.

## Recommended Next Phases

### Step 6: Controlled Single-Depth Fetch Sandbox

Goal:

- introduce fetch behavior only for controlled single-depth targets

Requirements:

- isolated fetch sandbox
- strict allow/deny policy
- no recursion
- no child document creation by default
- durable provenance logging
- explicit fetch timeout and content-size limits

Why this should be next:

- Step 5 already separates likely safe cases from risky ones
- a single-depth sandbox can validate real operator value without turning OLRE into a crawler

### Step 7: Human Exception Queue Refinement

Goal:

- improve the operator workflow once real review traffic is observed

Focus areas:

- better queue filters
- bulk operator actions where safe
- sharper review reasons
- confidence distribution analytics
- better handling of recurring review patterns

Why this matters:

- commercialization depends on time saved, not just correctness
- queue usability determines whether operators trust and adopt the system

### Step 8: Policy-Driven Traversal Automation

Goal:

- automate only the clearest approved patterns under strict policy

Potential features:

- policy-bound fetch eligibility
- approved domain classes
- controlled destination-type rules
- post-fetch review checkpoints

Important:

- automation should remain policy-driven and auditable
- not every `AUTO_ELIGIBLE` reference should become instant background execution

## Risks And Operational Concerns

- broken QR and weak scan quality remain common
- redirect-chain behavior complicates safe fetch decisions
- invalid PDF artifacts can contaminate naive automation assumptions
- multiple QR candidates in one packet can create provenance ambiguity
- child-document lifecycle becomes materially more complex once fetch begins

These are reasons to keep the rollout staged.

## Commercialization Considerations

OLRE becomes commercially useful by:

- reducing repetitive human review
- preserving trust in risky document environments
- keeping explanations and audit trails strong
- making safe cases fast without hiding uncertain cases

It does not become commercially useful by behaving like a generic crawler too early.

## Why OLRE Is Not A Generic Crawler Platform

OLRE is designed for official-document workflows with governance needs.

It should remain:

- document-centric
- policy-aware
- operator-auditable
- conservative about traversal depth

It should not drift into:

- arbitrary web crawling
- recursive discovery for its own sake
- opaque automation without provenance

## Recommended Direction Summary

```text
Step 5
  governance and review
    ↓
Step 6
  controlled single-depth fetch sandbox
    ↓
Step 7
  operator queue refinement
    ↓
Step 8
  policy-driven traversal automation
```

The key principle after Step 5 is simple:

- automate obvious cases gradually
- keep risky cases explainable
- do not outrun governance
