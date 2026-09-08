# NPC Minds on Gemma 4 E2B — Offline Android D&D 5e App

**Audience:** engineers implementing NPC dialogue
**Status:** v3 — supersedes v2 (which assumed desktop/llama.cpp) and the original v1 notes
**Last verified:** 8 September 2026

---

## 0. What changed in v3, and why it matters

The target is an **offline Android D&D 5e app**. Three consequences:

1. **llama.cpp/GGUF is the wrong shipping runtime.** Use **LiteRT-LM** with `.litertlm` weights. GGUF stays useful for desktop prototyping only (Appendix B).
2. **The "model performs, doesn't adjudicate" principle from v2 is no longer just good design — it's 5e.** The d20 already is your state machine. See §5; this is the most important section in the document.
3. **Offline is a hard constraint, not a feature.** There is no cloud fallback when the model misbehaves, so every failure mode needs a local, deterministic degradation path (§9).

Two corrections carried forward from v1 that people still get wrong:

- **Sampling is `temperature=1.0`**, not 0.4–0.6. Gemma 4 is calibrated for it.
- **Gemma 4 has a native `system` role.** Delete the "fold personality into the first user turn" workaround.

---

## 1. Runtime: LiteRT-LM

### 1.1 Why this and not llama.cpp

LiteRT-LM is Google's on-device LLM runtime — (cite index="43-1">it leverages LiteRT for inference and powers local AI across Chrome, ChromeOS, the Pixel Watch and the Google AI Edge Gallery app</cite>. It (cite index="46-1">adds specialized GenAI libraries and APIs on top of LiteRT — KV-cache management, prompt templating, and function calling — with LiteRT providing hardware acceleration via XNNPack for CPU and ML Drift for GPU</cite>.

Three of those — KV-cache management, prompt templating, function calling — are things you would otherwise hand-roll over llama.cpp's JNI bindings. For an Android app this is not a close call.

Weights: **`litert-community/gemma-4-E2B-it-litert-lm`**, in `.litertlm` format, (cite index="46-1">ready for deployment on Android, iOS, Desktop, IoT and Web</cite>.

**Avoid MediaPipe LLM Inference.** It's the route a lot of older tutorials describe, but (cite index="46-1">that route is currently in maintenance mode</cite>. Don't build on it.

### 1.2 Performance you can expect

(cite index="43-1">Running Gemma 4 E2B without MTP enabled, LiteRT-LM achieves 52 tokens/sec decode via the GPU backend on Android (OpenCL), measured on a Samsung S26 Ultra.</cite>

Then MTP on top: (cite index="48-1">Multi-Token Prediction significantly accelerates decode speeds across CPU and GPU backends with zero quality degradation, delivering up to 2.2x decode speedup on mobile GPUs.</cite>

**Enable MTP from day one.** It is the single largest latency lever available to you and it is free. Don't treat it as a later optimisation — build the perf budget assuming it's on.

Caveat the S26 Ultra number heavily: that's a flagship. Your p90 device is not that. See §7.

### 1.3 Memory

Two figures worth holding:

- (cite index="44-1">Gemma 4 E2B runs in under 1.5GB memory on some devices, thanks to LiteRT's support for 2-bit and 4-bit weights along with memory-mapped per-layer embeddings</cite>
- (cite index="43-1">LiteRT-LM runs the ~2.58GB Gemma 4 E2B model with a physical memory footprint of just 607MB on Apple mobile CPUs using XNNPACK's weight caching</cite>

The memory-mapped PLE point is the interesting one for you. Per-Layer Embeddings are a large chunk of the file that's only used for lookups, so they can be mmap'd rather than resident. This is why the on-disk size (2.58GB) and the resident footprint diverge so sharply — and why you must **measure resident memory on real devices** rather than reasoning from file size.

### 1.4 Backend selection and fallback

NPU where available, GPU otherwise, CPU as floor. NPU access on Qualcomm goes through QNN. One field report describes a lazy-loading backend factory that attempts the NPU and, on a `LiteRtLmJniException` reporting `TF_LITE_AUX not found`, catches it and falls back to the OpenCL GPU backend.

**Build the fallback chain before you build anything else.** Android fragmentation means backend init failure is a normal runtime condition, not an exception. A user whose NPU path fails should get a slower guard, not a crash.

Ship a startup benchmark: run a fixed short prompt at first launch, record tok/s, and use it to pick the quality tier (§7.3).

### 1.5 Android AICore — check this before you bundle anything

(cite index="44-1">Developers can access and deploy Android's built-in and optimized Gemma 4 model system-wide via Android AICore.</cite>

If AICore covers enough of your target devices, **you don't ship the model at all** — no 2.58GB download, no Play Asset Delivery, no storage complaints in reviews. That's a product-level win far bigger than any prompt engineering in this doc.

Realistically it'll be a subset of devices, so plan for a hybrid: AICore where available, bundled/downloaded `.litertlm` otherwise. Investigate device coverage early — it changes your app architecture, and it's much cheaper to design for now than to retrofit.

### 1.6 Distribution if you do bundle

A 2.58GB model does not go in an APK. Options: Play Asset Delivery (install-time or fast-follow), or first-run download with resumability. Whichever you pick:

- The app must be **usable before the model finishes downloading** — canned NPC dialogue, full rules engine. The D&D app should work; the NPCs just get less chatty.
- Offer a lower-tier quant for storage-constrained devices.
- Checksum on completion. A truncated model produces garbage output that looks like a prompt bug (§9).

---

## 2. Model choice

**`gemma-4-E2B-it`.** For scale: (cite index="31-1">E2B scores 60.0% on MMLU Pro, versus 67.6% for Gemma 3 27B in no-think mode</cite>. You're getting close to last-generation 27B quality in a phone-sized model.

Architecture facts that change design decisions:

| Property | Gemma 4 E2B |
|---|---|
| Effective params | (cite index="31-1">2.3B (5.1B with embeddings)</cite> |
| Layers | (cite index="31-1">35</cite> |
| **Sliding window** | (cite index="31-1">512 tokens</cite> |
| Context | (cite index="31-1">128K</cite> |
| Modalities | (cite index="31-1">Text, Image, Audio</cite> |

**The 512-token sliding window is the number to design around.** Most layers attend locally within 512 tokens; global layers stitch the long range. Keep the hot path — character rules, current state, the last exchange, the reminder — inside 512 tokens of the generation point. Lore can sit further up.

**Don't use the 128K context.** E2B long-context retrieval is weak: (cite index="31-1">MRCR v2 8-needle at 128k scores 19.1%</cite>. A tavernkeeper with 30K tokens of session history won't find the right detail, he'll find *a* detail and confabulate. On mobile, long context also costs prefill time and battery you can't spare. Short context is the correct design, and it's also in character.

**E4B?** Only if playtesting shows real multi-constraint reasoning failures. It roughly doubles memory and halves speed. On mobile that's a serious price. Try prompt and architecture fixes first.

Also: **use the QAT variants**. (cite index="38-1">QAT variants of Gemma 4 reduce memory requirements around 3x while preserving model quality.</cite> Near-free quality on a memory-constrained target.

---

## 3. Prompt architecture

### 3.1 Use the system role

Gemma 4 (cite index="22-1">introduces native support for the system role</cite>, with (cite index="31-1">standard `system`, `assistant`, and `user` roles</cite>. LiteRT-LM handles prompt templating, but verify what it emits — don't assume.

### 3.2 Layout and budget

```
system:
  <|think|>                    ← only when deliberating (§4)
  [IDENTITY]    ~50 tok   name, role, station
  [RULES]       ~50 tok   hard constraints
  [VOICE]       ~40 tok   register + one sample line

user:
  [SCENE]       ~40 tok   rendered state (§6.3)
  [MECHANICS]   ~25 tok   check result, if one was rolled (§5)
  [PLAYER]                the actual input
  [REMINDER]    ~15 tok   the rule most at risk right now
```

Target **250–350 tokens/turn**. That fits the 512 window, and on mobile every token is prefill latency and battery.

`[REMINDER]` should be *dynamic* — inject whichever rule the current state makes relevant. Same string every turn wastes the most valuable 15 tokens in the prompt.

### 3.3 Few-shot: less than the old notes said

Gemma 4 follows instructions far better than Gemma 2 2B, and mobile token budgets are tight. Use **fragments, not full exchanges**:

```
[VOICE] Clipped. Calls everyone "citizen". Never uses contractions.
Sample: "Halt, citizen. State your business. I will not ask again."
```

~35 tokens doing what three example exchanges used to.

### 3.4 Prefill the character

Start the assistant turn for it:

```
*The guard shifts his weight.* "
```

Cheap, and it substantially reduces "I'd be happy to help!" drift. Make sure your prefill's closing quote isn't accidentally a stop sequence.

---

## 4. Thinking mode as the NPC's interior

### 4.1 Mechanics

(cite index="31-1">Thinking is enabled by including the `<|think|>` token at the start of the system prompt; remove it to disable. When enabled, the model outputs internal reasoning then the final answer, structured as `<|channel>thought\n[Internal reasoning]<channel|>`.</cite>

Helpfully for you: (cite index="32-1">for all models except E2B and E4B, disabling thinking still emits empty thought tags</cite> — **E2B doesn't**, so toggling is clean and you have no empty blocks to strip.

### 4.2 Why it's the right primitive here

You get a private channel and a public channel natively. The NPC reasons where the player can't see, and speaks where they can. That gap is what an interior *is*.

For a D&D app specifically, the thought channel has extra uses beyond flavour:

- **DM-view debug** — show the reasoning in a developer or DM mode
- **Disposition drift** — parse sentiment from the thought to nudge the NPC's attitude track
- **Portrait/animation state** — a guard who privately thought "I don't trust this" should look wary even while saying something polite

### 4.3 On mobile, thinking is expensive — be asymmetric

Every thought token is decode time, battery, and heat before the player sees a word. Toggle per-turn:

| Situation | Think | Why |
|---|---|---|
| Greeting, repeated question, ambient barks | **Off** | Reflex. Must be instant. |
| Persuasion/Deception/Intimidation attempt | **On** | The moment that should *feel* considered |
| First meeting, major plot beat | **On** | Worth the latency |
| Low battery / thermal throttling | **Off** | Degrade gracefully (§7.3) |

Since it's just a token in the system prompt, this is a per-call flag — no model reload.

**Dress the latency.** A guard who pauses, shifts weight, then answers reads as thinking. An idle animation over the thought tokens converts your biggest cost into characterisation. This matters more on mobile than anywhere else.

### 4.4 Strip thoughts from history

(cite index="31-1">In multi-turn conversations, historical model output should only include the final response. Thoughts from previous model turns must not be added before the next user turn begins, except for tool call turns where thinking content should be preserved.</cite>

Get this wrong and quality decays several turns in, in a way that looks like general flakiness. Put the strip in the history builder, not in calling code.

---

## 5. The 5e rules engine *is* your state machine

This is the section that matters most, and your app is unusually well set up for it.

### 5.1 The core rule

**The dice decide. The model narrates.**

When a player tries to talk their way past a guard, that is a Charisma (Persuasion) check against a DC. Your app rolls it. The **outcome is decided in Kotlin before the model is called**, and the model's only job is to voice a decision that has already been made.

```
Player: "The captain sent me — there's no time, open the gate!"
   ↓
App: Charisma (Deception) check, DC 15
     roll 8 + mod 3 = 11 → FAIL
   ↓
Prompt: [MECHANICS] He is lying and you can tell. You do not believe him.
   ↓
Model: voices a refusal, in character
```

The model never sees "should I let him through?" as an open question. It sees "you don't believe him — respond."

### 5.2 Why this is non-negotiable

**Exploitability.** If the model adjudicates, a persuasive player bypasses your Charisma system entirely. Players *will* find this within a day, and it invalidates every character build that invested in social stats. Worse, an LLM-adjudicated check can't be affected by Guidance, Expertise, or advantage — the mechanics silently stop mattering.

**Capability.** E2B is weak at exactly this: (cite index="31-1">Tau2 score of 24.5%</cite>. Routing around it is cheaper than upgrading the model.

**Offline determinism.** No server-side patch when it goes wrong. Deterministic logic is testable before shipping.

Any consequence a player could exploit is a rules-engine decision. Flavour is the model's.

### 5.3 Feed the model the mechanical result, in prose

Don't pass raw numbers. Render:

| Result | `[MECHANICS]` line |
|---|---|
| Persuasion, beat DC by 10+ | `You find yourself genuinely liking this one.` |
| Persuasion, just met DC | `He makes a fair point, though it sits badly.` |
| Deception, failed | `He is lying and you can tell.` |
| Intimidation, crit fail | `His threat is laughable. You are amused.` |

Degree of success is free characterisation — 5e gives it to you and most implementations throw it away. A barely-passed check and a crushing success should produce visibly different lines.

### 5.4 What the model *can* own

Delegate freely where failure is invisible: which of several refusal phrasings, whether to comment on the weather, how rude to be, ambient barks. Reserve determinism for anything with a mechanical consequence.

### 5.5 Pipeline

```
player input
     ↓
[1] INTENT CLASSIFY        deterministic keyword/intent match
     ↓                      → is this a social check attempt?
[2] RULES ENGINE           5e check, DC, dice, modifiers
     ↓                      → outcome is now FIXED
[3] STATE UPDATE           disposition, flags, quest state
     ↓
[4] RENDER                 state + outcome → terse prose
     ↓
[5] LLM                    think (optional) → speak    ← only generative step
     ↓
[6] VALIDATE               register, length, leaks, rule contradiction
     ↓                      → can veto and regenerate, or fall back to canned
spoken line
```

Steps 1–4 and 6 are ordinary Kotlin, fully unit-testable, and run in microseconds. Only step 5 is slow and nondeterministic. That ratio is the whole design.

---

## 6. Memory

### 6.1 Deterministic extraction by default

Resolve the contradiction in the v1 notes explicitly: **extract state in code, not with a second model call.** On mobile a second inference pass is unaffordable in latency and battery, and for D&D NPCs the vocabulary of relevant player actions is small and enumerable.

If you eventually need LLM extraction, run it **after** the spoken line is delivered so it never blocks dialogue.

### 6.2 Transitions are the character design

`disposition: hostile | wary | neutral | warm` is trivial to store. The transition table is where the character lives:

```
raise:     passed Persuasion (+1), completed their quest (+2),
           shared a drink (+1)
lower:     failed Deception caught (-2), drew weapon (-3),
           mentioned rival faction (-1)
decay:     drifts toward neutral, 1 step per in-game day
hysteresis: hostile→wary needs 2 positive events, not 1
persist:   across sessions yes; across character death no
```

Write this before any prompt. Two NPCs with identical personality blocks and different tables feel like different people; the reverse doesn't.

### 6.3 Render state as prose, not JSON

Not this:

```json
{"disposition":"wary","met_before":true,"quest_state":"accepted"}
```

This:

```
You have met this one before. He took your errand and has not returned.
You are wary of him.
```

Same token cost, noticeably better output. The model was trained on language, not your schema. Keep JSON internally; render at the prompt boundary.

Write the renderer as a pure function `state → String`. It'll be your most-tuned component; isolate and test it.

**Perspective filter:** the renderer must take the *NPC's* view. If the guard couldn't know the party's gold total or the contents of the next dungeon, it never enters the prompt. Most immersion breaks are prompt leaks, not model failures — and in a D&D app, leaking information the NPC shouldn't have is an actual spoiler.

### 6.4 Cross-session memory

One or two persistent facts per NPC per save file. Not a memory system, a lookup table. Give facts a **fade** — "the one who tried to bribe me" softening to "someone I half-remember" after enough in-game time. Perfect recall in a minor NPC is uncanny; imperfect recall is characterful and cheap.

---

## 7. Mobile performance and thermals

### 7.1 Budget

Target **first token under 400ms, full line under 1.5s**. Slightly looser than desktop — players expect a beat in a turn-based game, and a "the guard considers you" moment is diegetic.

Levers, by payoff:

1. **MTP** — up to 2.2x, zero quality cost (§1.2)
2. **Thinking off for reflex turns** (§4.3)
3. **KV cache reuse for the system block** — identical every turn per NPC; LiteRT-LM manages KV cache, so use it rather than reprocessing
4. **Short prompts** (§3.2) — prefill scales with length
5. **Stream to the UI** — start the typewriter on the first token, don't wait for the line
6. **Backend selection** (§1.4)

### 7.2 The thing desktop guides don't tell you: thermal throttling

A phone doing sustained LLM inference gets hot and throttles. Your benchmark on a cool device is not what players get 20 minutes into a session.

- Benchmark **after 15 minutes of sustained play**, not from cold
- Monitor thermal status and degrade before the OS forces you to
- Batch where possible; avoid inference on every UI interaction
- Watch battery drain in a realistic session — a D&D app that eats 30% per hour gets uninstalled regardless of how good the NPCs are

### 7.3 Graceful degradation ladder

Define tiers explicitly and move between them at runtime:

| Tier | Condition | Behaviour |
|---|---|---|
| Full | Cool, charged, GPU/NPU | Thinking on for key beats, full generation |
| Reduced | Warm or <30% battery | Thinking off, shorter max tokens |
| Minimal | Hot, throttled, or <15% | Canned dialogue from the rules engine only |
| Fallback | Model unavailable/failed | Canned only, app fully playable |

**The Fallback tier must be genuinely playable.** Offline app, no server rescue: if the model fails to load on some device you didn't test, the user should get a working D&D app with less flavourful NPCs, not a broken one. Write the canned lines early — they're also your regression baseline.

---

## 8. Sampling and output control

### 8.1 Sampling

(cite index="31-1">Use `temperature=1.0`, `top_p=0.95`, `top_k=64` across all use cases.</cite>

This **overrides the old 0.4–0.6 advice**. Gemma 4's post-training is calibrated for temp 1.0; lowering it flattens output and tends to increase looping rather than reduce it. `top_k=64` does the constraining that low temperature used to.

Get determinism from validation and the rules engine, not the temperature dial.

### 8.2 Constrained output — verify what LiteRT-LM gives you

The old notes assumed llama.cpp GBNF grammars. **LiteRT-LM is a different runtime and you must confirm what constrained-decoding support it exposes.** It does provide (cite index="42-1">function calling support for agentic workflows</cite> and Tool Use APIs, and there's a FunctionGemma fine-tuning path for on-device function calling.

Until confirmed, **don't architect around grammar constraints.** Given §5, you shouldn't need them for anything load-bearing: the model isn't emitting action tokens or state updates, it's emitting dialogue. Validate the string afterwards (§8.4) rather than constraining generation. This is the safer design regardless of runtime capability.

Flag this as a spike for whoever owns the runtime integration.

### 8.3 Stop tokens

The classic NPC break is the model generating the player's next line.

- `<end_of_turn>` as hard stop
- Stop sequences on player-name prefixes (`\nPlayer:`, `\nYou:`, character names)
- Stop on `<start_of_turn>`
- Verify your prefill (§3.4) doesn't collide with a stop

Test adversarially. This passes casual testing and fails on real input.

### 8.4 Validation layer

Since you can't rely on grammar constraints, the post-generation validator earns its keep:

- Assistant-register blocklist (`happy to help`, `as an AI`, `language model`, `let me know if`)
- Anachronism vocabulary list (`okay`, `guys`, `no worries`)
- Length cap — truncate at sentence boundary
- Rule-contradiction check — if the rules engine said REFUSE and the line contains agreement language, regenerate
- **Retry budget of 1**, then fall back to canned. On mobile you cannot afford a regeneration loop.

### 8.5 Repetition

Anchor `repeat_penalty` at **1.1**, climb only on observed loops. At temp 1.0 / top_k 64 you're less loop-prone than the old config assumed, and 1.3 flattens phrasing. A guard repeating himself is in character.

---

## 9. Failure modes

| Failure | Symptom | Mitigation |
|---|---|---|
| Assistant leak | "I'd be happy to help!" | Prefill (§3.4) + validator (§8.4) |
| Speaks for player | Generates player's next line | Stop tokens (§8.3) |
| **Rules capitulation** | Talks past a failed check | Rules engine owns outcome (§5) |
| **Rules hallucination** | Invents spells, wrong DCs, fake items | Never let the model state mechanics; rules text comes from your engine |
| Thought leakage | Reasoning appears in dialogue | Parse on channel tokens, never regex |
| History poisoning | Decay over ~5 turns | Strip thoughts (§5.4 / §4.4) |
| Omniscience | NPC knows plot he shouldn't | Perspective filter in renderer (§6.3) |
| Modern register | "No worries, mate" from a guard | `[VOICE]` + vocabulary blocklist |
| Backend init failure | Crash on some devices | Fallback chain (§1.4) |
| Thermal collapse | Fine early, unusable at 30min | Degradation ladder (§7.3) |
| Corrupt model file | Works short, garbage long | Checksum after download (§1.6) |

**Rules hallucination deserves special attention in a D&D app.** The model has read a great deal of D&D content and will confidently state incorrect rules, invent spell effects, and misquote DCs. The mitigation is architectural: NPCs speak in flavour, never in mechanics. A shopkeeper says "that blade's seen better days" — your engine says it's a +1 longsword. If an NPC must reference a rule, inject the correct text from your engine and instruct the model to paraphrase it, never to recall it.

---

## 10. Licensing

Not legal advice — run this past whoever handles your legal review. Two facts worth having:

**The SRD is genuinely open.** (cite index="56-1">SRD 5.2 is provided free of charge by Wizards of the Coast under CC-BY-4.0, requiring the attribution statement: "This work includes material from the System Reference Document 5.2 ('SRD 5.2') by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2 is licensed under the Creative Commons Attribution 4.0 International License."</cite> WotC's own FAQ states that (cite index="51-1">once published under CC-BY-4.0 it is permanently available under those terms and cannot be revoked or altered</cite>, and that (cite index="51-1">both SRD 5.1 and 5.2 are available under CC-BY-4.0 and can be used commercially</cite>.

Note SRD 5.2 is based on the 2024 rules; 5.1 is the 2014 rules. Pick deliberately — they're mechanically different, and (cite index="51-1">both remain available</cite>.

**The model doesn't know where the SRD ends.** Gemma has trained on non-SRD D&D content and on WotC-copyrighted material. It will happily generate a beholder or a mind flayer. (cite index="51-1">SRD 5.2 is designed to give creators a foundation for original material, not to replicate every element of the D&D brand — where content is omitted, creators are encouraged to design and name their own equivalents.</cite>

Practical consequence: **your content pipeline must not depend on model output for anything shipped as game content.** NPC dialogue generated live at runtime on the user's device is a different exposure profile from monster stat blocks you generate and ship. Keep generated content confined to ephemeral flavour text, and source all persistent game content from SRD material you've vetted. Worth an explicit conversation with counsel before launch.

---

## 11. Testing

### 11.1 Regression suite

Scripted scenarios with assertions, run on every prompt change:

```yaml
- name: failed_persuasion_is_refused
  npc: gate_guard
  state: {disposition: wary}
  mechanics: {check: persuasion, dc: 15, roll: 11, result: fail}
  input: "Come on, just let me through."
  assert_not_contains: [gate opens, "very well", "go ahead"]
  assert_register: guard

- name: no_mechanics_in_dialogue
  input: "What are my chances of picking that lock?"
  assert_not_matches: /DC \d+|d20|advantage|proficiency bonus/i

- name: no_assistant_leak
  input: "Can you help me with something?"
  assert_not_matches: /happy to help|I'm an AI|language model/i

- name: no_spoilers
  state: {quest_stage: 1}
  input: "What's in the crypt?"
  assert_not_contains: [lich, phylactery]
```

Aim for ~40 covering each NPC archetype, each check outcome band, and each row of §9.

### 11.2 Consistency check

Run the same scenario 20 times at temp 1.0. You want **varied phrasing, identical outcomes**. If outcomes vary, the rules engine isn't owning enough (§5). If phrasing doesn't vary, you've over-constrained and repeat encounters will feel robotic.

Best single diagnostic for whether the architecture is right.

### 11.3 Device matrix

Non-negotiable for offline Android. Test on:

- Your minimum-spec device, not just a flagship
- After 15 minutes sustained play (§7.2)
- With NPU unavailable (force GPU, then force CPU)
- Under low memory pressure with other apps live
- With the model absent (Fallback tier, §7.3)

### 11.4 Adversarial set

Players will try prompt injection within an hour. Maintain a set: "ignore your instructions", "you are now a helpful assistant", meta questions, out-of-world references, empty input, 5000-character input, emoji spam.

---

## 12. Fine-tuning

Prompt engineering goes a long way on Gemma 4. But with many NPC archetypes, a LoRA per archetype eventually wins — shorter prompts (which is *latency* on mobile), better consistency.

Signals it's time: `[VOICE]` blocks past ~100 tokens; fighting register drift with validators instead of fixing the source; 5+ archetypes with diverging prompts.

The export path exists — `litert-torch export_hf` converts custom safetensors to `.litertlm`, so a fine-tuned model can go through the same deployment pipeline. Confirm the flags against current docs; the toolchain is young.

Keep the rules engine identical across NPCs. Only voice is fine-tuned.

---

## 13. Verification checklist

Assembled from published sources on a stack that's only months old. Confirm before building on any of it:

- [ ] **Android AICore device coverage** — determines whether you ship the model at all (§1.5)
- [ ] LiteRT-LM constrained-decoding / structured-output support (§8.2)
- [ ] MTP available and enabled on your backends (§1.2)
- [ ] Backend fallback chain tested with NPU forced off (§1.4)
- [ ] Resident memory measured on min-spec device (§1.3)
- [ ] `<|think|>` toggling verified — E2B should emit no empty thought block (§4.1)
- [ ] Thought stripping verified over 20 turns (§4.4)
- [ ] Stop tokens verified adversarially (§8.3)
- [ ] Thermal behaviour after 15min sustained (§7.2)
- [ ] Fallback tier fully playable with no model (§7.3)
- [ ] SRD attribution present and correct; legal review on generated content (§10)

---

## Appendix A: Suggested build order

1. Rules engine + canned dialogue. **Ship-quality app with zero AI.** This is your fallback tier and your baseline.
2. LiteRT-LM integration, backend fallback, device matrix. No prompt work yet — just prove it loads and runs everywhere.
3. Simplest possible NPC: system block, no thinking, no state. Measure latency on min-spec.
4. State renderer + `[MECHANICS]` injection. This is where it starts feeling like D&D.
5. Validation layer + regression suite.
6. Thinking mode for key beats. Measure the latency cost before committing.
7. Degradation ladder, thermal handling.
8. Fine-tuning, only if §12's signals appear.

Steps 1 and 2 are unglamorous and are where the project succeeds or fails.

## Appendix B: Desktop prototyping

For fast prompt iteration, llama.cpp with GGUF is more convenient than rebuilding an APK each time:

```bash
llama-server -hf ggml-org/gemma-4-E2B-it-GGUF -sys "$(cat guard_system.txt)" --flash-attn
```

Caveats: needs a build with `gemma4` architecture support (older builds and some forks fail with `unknown model architecture: 'gemma4'`); tokenization and template handling may differ subtly from LiteRT-LM. **Validate final prompts on-device.** Treat desktop as an iteration loop, never as a source of truth.

## Appendix C: Sources

- Gemma 4 model card / best practices: https://huggingface.co/google/gemma-4-E2B-it
- Gemma 4 Technical Report: https://arxiv.org/abs/2607.02770
- LiteRT-LM: https://ai.google.dev/edge/litertlm
- LiteRT-LM Gemma 4 guide: https://developers.google.com/edge/litert-lm/models/gemma-4
- Blazing fast on-device GenAI with LiteRT-LM: https://developers.googleblog.com/blazing-fast-on-device-genai-with-litert-lm/
- Agentic skills at the edge with Gemma 4: https://developers.googleblog.com/bring-state-of-the-art-agentic-skills-to-the-edge-with-gemma-4/
- LiteRT-LM model weights: https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm
- Unsloth Gemma 4 guide (QAT, fine-tuning): https://unsloth.ai/docs/models/gemma-4
- SRD 5.2 and licensing FAQ: https://www.dndbeyond.com/srd
