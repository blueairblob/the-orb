# PRD Cleanup — Action Plan

**Goal:** unmuddle the PRD, close the fake gaps, and get to the spike. This is ~1 hour of
work: two decisions, four edits, one rule. **No new section is needed.** The document is
closer to done than it feels.

**Target:** `PRD-v0_7-voice-dm-engine.md` in project knowledge → save out as **v0.8**.

**How to use this file:** work top to bottom. Each edit gives you the exact text to find and
what to replace it with. Line numbers are from the current v0.7 and are a hint, not a promise —
match on the text, not the number. Tick as you go.

---

## Part A — Two decisions (make these first; the edits depend on them)

### ☐ A1. Scope the memory experiment — *is it for The Orb, or the standalone app?*

The rolling-compaction memory brain (extraction, hot/warm/cold tiers, decay/reactivation)
came out of the 13 July experiment. It answers a question **this design deliberately avoids
asking**: §3 and §4 put continuity in the *engine's* object model and regenerate the brief
fresh each turn, so the model is "never asked to think, only to speak what it is handed."
A model that holds no memory between turns is the intended design, not a flaw.

**Decision to make:** default to **keep them separate** unless you can say confidently the
memory brain is for The Orb. If you can't answer, that *is* the answer — keep apart, revisit
after the spike.

- My decision: ____________________
- If separate: the memory work stays in `small-model-big-memory-dev-plan.md`, referenced but
  not imported (see B1).

### ☐ A2. Which model does the spike benchmark? — *this is the only item blocking real work*

§0 currently says a quantised **2B**. The 13 July experiment pointed (unsettled) at **Gemma 4
E2B**: ~2.3B effective params, <1.5 GB, 128K context, quad-modal, Apache 2.0. You are **not**
deciding what ships — only what goes on the phone this week. Pick one; record the other as an
open question.

- Model to benchmark first: ____________________
- Runner-up (→ becomes an open question, not a decision): ____________________

---

## Part B — Four edits (one pass, then bump the header to v0.8)

### ☐ B1. Add ONE cross-reference line for the memory experiment

Stops a future session either rediscovering it from scratch or (as happened) mistaking
provisional notes for settled architecture.

**Find** (Gotcha #6, the Save-state bloat row — its resolution cell currently ends):

> `Tiered memory: hot facts verbatim, cold facts compressed. *Unsolved — needs design.*`

**Replace that trailing sentence with:**

> `Tiered memory: hot facts verbatim, cold facts compressed. *Unsolved — needs design.* Note: exploratory memory-architecture work exists in \`small-model-big-memory-dev-plan.md\` (13 July), but its conclusions are **not settled and not assumed by this design** — and see #6a on why this is engine-side, not a model memory layer.`

---

### ☐ B2. Disambiguate "RAG" — it currently means two different systems

"RAG" is used for the **SRD rules lookup** (correct, keep the concept) *and* has been informally
attached to the **memory brain** in discussion. Rename the SRD one so the two never blur.

**Edit 1 — §3 ownership table** (line ~119):

- Find: `Player-facing rules Q&A (via RAG)`
- Replace: `Player-facing rules Q&A (via the SRD rules index)`

**Edit 2 — §8 Later/Elaboration** (line ~311):

- Find: `RAG index over the SRD for player rules questions ("can I dual-wield this?").`
- Replace: `SRD rules index (embedded lookup) for player rules questions ("can I dual-wield this?").`

**Edit 3 — §11 stack table** (line ~430):

- Find: `| RAG (later) | Lightweight embedding model + SQLite vector extension | SRD chunked and embedded once |`
- Replace: `| SRD rules index (later) | Lightweight embedding model + on-device vector store | SRD chunked and embedded once. *Store not yet chosen — see open questions.* |`

> Note: this also quietly drops the premature "SQLite vector extension" commitment. The vector
> store is genuinely undecided — leave it open rather than half-decided.

---

### ☐ B3. Reframe Gotchas #6 and #7 as engine-side retrieval, not model memory

Same problem, correctly framed — and it stops attracting the wrong (model-memory) solution.
Add a short row **#6a** directly beneath #7:

> `| 6a | **Framing note for #6/#7.** | 🟠 | These are **engine-side retrieval over structured state**, not an LLM memory layer. The engine owns canon; the question is how it *stores and selects* what to feed each turn's brief (§4), not how the model remembers. Keep any memory-brain experiments (A1) firmly separate unless a decision says otherwise. |`

(Leave the #6 and #7 wording otherwise intact — they're correctly marked unsolved.)

---

### ☐ B4. Put the model decision from A2 into §0 and align §11

**§0 spike step 1** (line ~46):

- Find: `Get a **quantised 2B model** (Gemma 2B or similar) onto a **real mid-range Android**`
- Replace with your A2 choice, e.g.: `Get the **chosen quantised model** ([your A2 pick]) onto a **real mid-range Android**`

**§8 PoC bullet** (line ~302) and **§11 stack table** (line ~429): update the model name to match
A2 so all three agree. Don't leave §0 saying one thing and §11 another.

**Open questions** — replace the stale line:

- Find: `- [ ] Gemma 2B vs 3B — is the extra footprint worth the coherence gain?`
- Replace: `- [ ] [A2 runner-up] vs [A2 pick] — is the extra footprint worth the coherence/context gain? *(model choice is provisional until the spike; §0)*`

---

### ☐ B5. Bump the header to v0.8

Update the version, date, and add a short changelog:

> `**Changes since v0.7:** Housekeeping pass — no new design. Disambiguated "RAG" (SRD rules index vs. memory); reframed Gotchas #6/#7 as engine-side retrieval (#6a); recorded the memory experiment as referenced-but-not-adopted; set the spike's benchmark model; left the vector store explicitly open.`

---

## Part C — One permanent rule (adopt, don't just read)

### ☐ C1. Single-source hygiene

- **One PRD file.** The filename carries the version (`PRD-v0.8-...`).
- **Commit at the end** of the session that changed it — never at the start of the next.
- **Delete superseded copies immediately** from project knowledge (the stale `PRD-v0_1` /
  v0.4 file is what caused a wasted reconstruction — bin it if you haven't).
- **Start each session** by having current project-knowledge contents stated back before any
  work begins. Thirty seconds; catches exactly the file-drift that bit us.

---

## Part D — Then stop, and run the spike

§22 already wrote your exit condition:

> *"When the gotchas stop needing new solutions, that's the signal the engine is conceptually
> complete — and it's time to stop philosophising and start building."*

Thirty-six entries in, they fold into each other rather than multiplying. The document passed
its own test days ago. Everything above is ~1 hour; past that, more PRD work is a way of not
finding out whether the premise holds.

**The next real action after this file is roadmap step 0 — the spike.** §0 is explicit that it
is the one piece of genuine uncertainty. Everything else is engineering.

---

### Quick tick-list

- [ ] A1 — memory scope decided (default: separate)
- [ ] A2 — spike benchmark model chosen
- [ ] B1 — memory cross-reference line added (#6)
- [ ] B2 — "RAG" → "SRD rules index" in three places
- [ ] B3 — Gotcha #6a framing row added
- [ ] B4 — model name aligned across §0 / §8 / §11 + open question updated
- [ ] B5 — header bumped to v0.8 with changelog
- [ ] C1 — hygiene rule adopted; stale files deleted
- [ ] D — spike scheduled
