# Phase 3 — Enterprise Hardening

**Epics E3.1 – E3.6** · 6 stories · Gate: **formal V&V accreditation**

> ## ⚠️ Deliberately coarse. Do not refine yet.
> Same reasoning as Phase 2 — refine an epic only when Phase 2 is in use.

---

## E3.1 — Full legality

### ⏳ [TODO] S3-01 — Replace the surrogate with a rules engine, and quantify the bias
**Size:** `L`

Depends on S2-01. Spec §5.4, §3.

The surrogate implements L0–L8 with a documented **conservative** bias: surrogate-legal ⇒ almost always
truly legal. Phase 3 replaces it and **measures** that claim per rule.

*Sketch:* a rule-by-rule comparison table; **fails if** the surrogate turns out *optimistic* anywhere —
that would mean the model has been producing assignments that are not actually legal, and every prior
result needs revisiting.

---

## E3.2 — Network propagation

---

### ⏳ [TODO] S3-02 — Delay propagation through aircraft rotations
**Size:** `L`

Depends on S3-01. Spec §1.4, §5.2.

**The largest remaining realism gap.** CVaR₀.₉₅ is in the objective and tail days are exactly when
reserve capacity binds — but the mechanism that manufactures bad days (a delay cascading through
aircraft rotations, stranding crew out of base, breaking several pairings at once) is absent. The
severity regime absorbs it in reduced form; the MVP therefore **understates** tail severity.

*Sketch:* tail cost rises and the CVaR-optimal R rises with it; **fails if** the tail does not move —
propagation is not actually binding and the reduced form was adequate, which is itself worth knowing.

---

## E3.3 — Drift monitoring

---

### ⏳ [TODO] S3-03 — Monthly refit with input-drift alerting
**Size:** `M`

Depends on S2-01. Spec §6.2, §3.

Matters more for a leisure carrier than for a scheduled network carrier: route structure changes
seasonally, so a model fitted on last winter's sun programme may not describe this winter's.

*Sketch:* alert when sick-call intensity or the regime transition matrix shifts beyond tolerance;
**fails if** drift is only visible by manual inspection.

---

## E3.4 — Workflow integration

---

### ⏳ [TODO] S3-04 — Dashboard with scenario drill-down
**Size:** `L`

Depends on S1e-03. Spec §3.

Power BI or a web app, integrated into the monthly bid-period planning workflow.

*Sketch:* a planner can answer "why this number?" unaided; **fails if** the drill-down built in S1e-03
is lost in the move from HTML to dashboard. That drill-down is the reason planners trust the output —
losing it to make the charts prettier would be a net loss.

---

## E3.5 — Accreditation

---

### ⏳ [TODO] S3-05 — Formal V&V accreditation package
**Size:** `L`

Depends on S3-01. Spec §9.

Trace validation, Turing-style controller test, historical backtesting bands and the surrogate-vs-rules
comparison, assembled into one signed package.

*Sketch:* **fails if** any gate is advisory without that being stated on the front page. A package that
reads as fully validated when two gates are advisory is worse than no package.

---

## E3.6 — Voluntary recovery layer  ·  ⛔ **BLOCKED**

---

### ⏳ [TODO] S3-06 — Model the voluntary layer, if one exists
**Size:** `M`

Depends on S1e-07. Spec §1.4.

**Blocked by:** `QUESTIONS_TO_ASK.md` §1.2 — *is what we call drafting already that step?*

At Air Transat drafting is premium-paid and allocated senior-first, so it may already occupy the space
a separate "voluntary open-time pickup at premium" layer would occupy elsewhere. The two mechanisms may
be the same thing under different names.

**Do not design this before the answer.** An earlier draft of the specification invented a
`voluntary_absorption_rate` dial to bound the effect; it was removed, because a knob invented to cover
an unmodelled mechanism reads as a claim that the mechanism has been characterised.

*Sketch:* **fails if** a placeholder parameter is invented instead of modelling the real mechanism.

---

## Out of scope, permanently unless re-scoped

| | Why |
|---|---|
| Real-time / day-of decision support | Different product. A "what-if" mode seeded from live crew state is a possible future track, not this one |
| Aircraft and passenger recovery optimisation | They appear as cost terms only. Adding them as *decisions* makes this a crew-recovery optimiser — a much larger system |

