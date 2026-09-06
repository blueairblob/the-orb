# Product Requirements Document — v0.8 (Draft)
## Working title: **The Orb** — an audio-first AI Dungeon Master

**Status:** Draft — v0.8, housekeeping pass; design-complete pending the spike
**Date:** 6 September 2026
**Owner:** [you]

**Changes since v0.7:** Housekeeping pass — no new design. Disambiguated "RAG" (SRD rules index vs. memory); reframed Gotchas #6/#7 as engine-side retrieval (#6a); recorded the memory experiment as referenced-but-not-adopted; set the spike's benchmark model (**Gemma 4 E2B**); left the vector store explicitly open.

**Changes since v0.6:** The rhythm problems get answered. Six gotchas that were open — most of
the make-or-break voice tier — now have resolutions, and a single principle unifies them.
- **#8 Interruption, #9 Mishearing** — both solved by the same graceful **"shall I repeat that?"** recovery. The DM stops, listens, re-offers. Never acts on nonsense; never ploughs on.
- **#10 Empty input** — a **context-aware nudge ladder**: diegetic hints → *"you there?"* → a warm timeout that ends the session in character.
- **#15 Repetition** — the world *wears down*. Retry the locked chest and the DM varies the line, then the key starts to bend. Consequence, not a canned response.
- **#35 Addressing / wake words** — each voice (DM, helmet, pack, staff) has a **wake word, user-reassignable**. Explicit, unambiguous, no clever NLP.
- **#36 Mix priority** — **speech always wins**; layers duck under it with a ~200 ms crossfade so it breathes. Music level is a **user option**.

**The through-line:** *the DM behaves like a real one — it recovers, it re-offers, it reads the
room, and the world answers back.* Rhythm is the product.

**Changes since v0.4–v0.6:** (carried) §0 the Spike; the harness framing; object model as prompt
factory; Evennia; the moat as *wedge*; walking reward parked; §11b Audio design; §12b Inventory
as character (the Rogue Trooper pattern).

---

## 0. The Spike — *the only question that can kill this*

> **Before a single line of engine code: does a small LLM run acceptably on a mid-range
> Android phone, in a pocket, warm?**

Everything in this document assumes it does. If it does not, the on-device premise collapses
and the product becomes something else entirely. So this is not a task on the roadmap — it is
**the gate in front of the roadmap.**

### What the research says (July 2026, indicative only)

| Finding | Implication |
|---|---|
| A 2B model on a mid-range CPU runs roughly **2–5 tokens/sec** | The pessimistic floor. Sluggish, but not fatal — *if* responses stay short (the Yoda principle earns its keep again) |
| **GPU is not automatically faster on mobile.** A documented case has a 2B model at ~1 tok/s on GPU vs ~6.5 tok/s on CPU on the *same* chip | **Do not assume GPU acceleration is the answer.** Measure both backends. This overturns the earlier "GPU essential" assumption in §11 |
| **Thermal drift is real.** One tester: just under 6 tok/s warm, ~7 tok/s cooled — *and that was plugged in* | A phone in a coat pocket on a dog walk is the worst case, not the best. **Benchmark hot.** |

*These are second-hand figures. They set expectations; they do not replace measurement.*

### The spike, concretely

1. Get the **chosen quantised model** (**Gemma 4 E2B**, `.litertlm`) onto a **real mid-range Android** — not a flagship, not an emulator.
2. Run it on **CPU and GPU**. Measure both. Do not pick a backend on faith.
3. Measure **time-to-first-token**, not just tokens/sec. In a conversation, the first syllable is what kills or saves the illusion.
4. **Run it hot.** Twenty minutes, unplugged, in a pocket. The cold thirty-second benchmark is a lie.
5. Feed it a **realistic brief** — the kind §4 will actually generate — and a realistically short response.

### The pass mark

> **A short, in-character guard reply, spoken, beginning within roughly a second, and still doing
> so after twenty minutes of use, on a warm mid-range phone.**

Pass → build the engine. Fail → the architecture survives, but the deployment story changes
(cloud tier, or a bigger floor device). **Find out first. Everything else is engineering; this
is the one piece of genuine uncertainty.**

---

## 1. Vision

An audio-first, AI-narrated roleplay engine, showcased through a family-friendly
fantasy escape adventure built on the D&D 5e SRD.

**The one-liner:** an interactive podcast — you listen, you speak, the story answers.
Hands-free, eyes-free. Playable on a commute, a dog walk, or whilst chopping onions.

**The real product is the engine.** The game is the flagship demo.

### What the engine actually is — *a harness*

Stated more plainly than in previous drafts:

> **The engine is a harness that constrains a general-purpose model down into a specific,
> reliable, bounded role.**

It hands the AI a world, a filter, and a tight brief — and in return gets something
**predictable** out of a thing that is, by nature, sprawling and unreliable. The guard is not
the point. **The guard is the first instance of a pattern.**

That pattern — *take an unbounded model and make it behave as a consistent character inside
hard rules* — is valuable anywhere you need an AI to stay firmly in its lane. It is, in
current parlance, an **agent skill**: an elaborate one, because it carries a whole world model
and its constraints along with it.

The dungeon is simply the most charming possible way to prove it.

---

## 2. The killer feature

The player should believe the DM is a **real human being**.

Three things carry that illusion, in priority order:

1. **Continuity** — the DM remembers the state, the story, and *you*.
2. **Pace** — no dead air. Rhythm matters more than voice quality.
3. **Personality** — recognisable, consistent, quirky. A character, not a narrator.

Everything else is in service of these three.

---

## 3. Core architectural principle

> **The engine is the director. The AI is the actor.**

Nobody lets the actor rewrite the plot mid-scene.

| Owned by deterministic code | Owned by the LLM |
|---|---|
| Dice rolls, combat maths, HP | Narration and flavour |
| Inventory, gold, economy | Tone and mood |
| Puzzle state, locks, unlocks | Character voice and quirks |
| Rules adjudication (5e SRD) | Improvised description |
| Progression, stats, save state | Player-facing rules Q&A (via the SRD rules index) |
| **NPC mood, drives, memory** | **NPC dialogue and delivery** |
| **Persistent effects and durations** | **Describing the current truth** |

**The boundary, stated plainly:** conventional game tech owns the character's **brain** —
what he feels, wants, remembers. The AI owns his **mouth** — how he expresses it in the
moment. Games have built believable NPCs for decades with no AI at all; what they were
always rubbish at was the *words*, falling back on a finite script of pre-written lines.
That is the one gap the AI fills. Lean on games for the mechanics, on the AI purely for
the language.

The engine hands the AI a **tight brief** each turn — here is the room, here is what
the player holds, here is what just happened, here is the mood — and the AI performs it.
It cannot go off-script because it is never given the pen.

**Second mantra, from the Yoda principle:**

> **The less you say, the more confident you appear.**

Sparse, deliberate, characterful lines. This is not a compromise — it is the character.
It also happens to solve latency, battery drain, and TTS quality in one stroke.

**Third mantra — reality is permanent:**

> **The road stays where it is. The trees do not disappear.**

Walk down a street and nothing flickers. That rock-solid permanence is what makes a world
feel like a *place* rather than a hallucination — and it comes from a deterministic engine,
not from an AI improvising afresh each turn. The existing apps feel like dreams precisely
because nothing is anchored: things shift, contradict, dissolve.

It is *lazy*, and it is seductive, to hand it all to the AI. Resist it. Pin everything solid
in the engine; let the AI paint only on top.

---

## 4. The Object Model — **the architectural backbone**

> **Everything in the world is an object. The AI narrates their state.**

This is the spine the entire engine hangs off. Not a feature — *the* structure.

It is **textbook object-oriented design**, and that is the point. This is not an exotic AI
architecture; it is solid, decades-proven software engineering that any developer understands.
The AI sits on top as the voice. The bones underneath are clean OO code — **testable,
debuggable, predictable**. You can inspect any object's state at any moment and know exactly
what is true. The precise opposite of the flaky "hand it all to the AI" approach.

### The base class: *thing in the world*

Every object — the guard, your familiar, a torch, a locked chest, a puddle, a wall — inherits
the same core. Specialised children switch on extra layers only if they need them.
**A rock does not need a mood. A guard does.**

| Layer | What it holds | Example |
|---|---|---|
| **State** | What it is like *now* | Torch: `lit`. Guard: `suspicious`. Door: `locked` |
| **Relationships** | How it connects to other objects | The key *belongs to* the chest. The sword is *owned by* the guard. The rat is *inside* the cell |
| **Capabilities** | What may be *done* to it | `takeable` · `movable` · `ownable` · `destructible` · `lockable` · `openable` |
| **Existence** | Whether it is still here | The torch burns to nothing, crosses its threshold, and is simply **gone** |
| **Position** | Where it is (see §5) | Cell, north wall, 3 paces from the door |

### Capabilities *are* the rules

This quietly solves the grounding problem (Gotcha #2). The engine knows a wall is not
`takeable` — so when the player says *"I pick up the wall,"* the DM refuses gracefully, in
character. **The AI never has to judge. It just reads the flags.**

### Why this is the whole game

Adding a lantern, a dog, a door, a merchant needs **no new code** — they are profiles with
different properties filled in. This is how you get from one dungeon to a universe of skins
cheaply. Keep the common core **lean**; layer optionally.

### The object model *is* the prompt factory

The turn's brief (§7, step 4) is **not hand-written**. It is **auto-generated by walking the
object graph**: here is the room, here is what is in it, here is what you carry, here is the
guard's mood, here is the hour. The engine already knows all of it — composing the brief is
close to mechanical.

> **Every ounce of rigour in the object model pays off twice: once as game truth, once as a
> cleaner prompt that keeps a small, dim model firmly on the rails.**

This is the shortcut hiding in plain sight. A well-shaped object model does not merely *support*
the AI — it **writes the AI's instructions for it**, fresh, correct, and complete, every single
turn. It is also why a 2B model is a defensible choice: it is never asked to think, only to
speak what it is handed.

*Everything below in §5, §6 and §12 is just properties hanging off this model.*

---

## 5. World Coordinates — time, distance, direction

The three axes of a believable world: **when, how far, which way.** All owned by the engine.
None of them known to the AI, which is simply told the current truth and narrates it.

### The world clock

Time is not flavour — it is **numbers the engine ticks**. Every action costs time: a quick
retort to the guard costs seconds, walking the passage costs minutes, resting costs hours.
The clock advances, and the time of day feeds into every brief.

- Deep night → the guard is drowsy, the torchlight low.
- Dawn → the shift changes.

**The clock quietly powers half the engine.** Effect durations (Gotcha #5) — a sleep spell
lasting three turns *is* the clock. The guard's shift ending, torches guttering, the player
tiring: all the same clock, ticking.

### Distance

Places are a known number of **paces** apart. Movement spends time (and later, energy).
The world has real geography the engine understands — **not vibes**.

### Direction

If distance is *how far*, direction is *which way*. North, south, up, down. The guard is
north through the door; the passage runs east. The engine holds the **map and the bearings**,
so when the player says *"go west,"* it knows exactly what that means — it is holding a real
compass, not guessing.

### The player's state vector

Together these give the player a complete **state vector**: where they are, which way they
face, what time it is, how they feel, what they carry. Their full position in the world at
any instant. Every brief is a snapshot of that vector.

---

## 6. Randomness — *random, but never absurd*

Randomness is the spice that stops the world feeling mechanical. The 5e dice are exactly how
the game injects surprise without the DM having to invent it.

**But randomness must be context-aware.** A random event is *not* drawn from all possible
events — it is drawn from the ones that make sense **right here, right now**.

The engine holds a table of plausible events **per situation**. In the cell, at night, the
roll might give you: the guard coughing, a distant scream, a rat scurrying past.

> **It never gives you a bear. A bear is not on the cell's table.**

The bear cannot appear in the cell for precisely the same reason the guard cannot pick things
up with a severed arm: **the engine simply does not hand the AI that option.**

---

## 7. Core loop

1. Player speaks (STT).
2. Engine parses intent against current state.
3. Deterministic layer resolves outcome (rules, dice, puzzle logic).
4. Engine composes a brief (markdown) for the LLM.
5. LLM narrates within those bounds.
6. Guardrail filter checks output.
7. TTS speaks. Orb pulses/shifts colour to match mood.
8. State written to save file.

---

## 8. Scope

### Must-have — Proof of Concept (v0.1): **The Cell and the Guard**

**The scenario, sharpened.** One cell. One door. One guard on the other side of it.
No items, no puzzle chain, no map to explore. The *only* way out is to **talk your way past
the guard**.

The scene is set with nothing but a cell and a sound outside the door. The player has to
work out for themselves that conversation *is* the mechanic. The guard is persuadable — but
he takes some winning over.

**Why this is the right proof of concept.** By making the whole game a conversation, it puts
the single hardest, most human thing — natural back-and-forth dialogue — at the *centre* as
the core mechanic, not off to one side as a garnish. There are no puzzles to hide behind and
nowhere for the system to fall back to. The question is stark: **can the AI hold a
persuadable conversation that feels human?** If talking past that guard feels real, the
heartbeat and the fun are proven in one stroke.

- **The guard has a mood dial** — see §12, the Character Engine. Persuasion is not vibes; it is a number the engine moves.
- **Google on-device STT and TTS.** Free, mature, already on the phone. Plain voice, no character yet.
- **Small on-device LLM** (Gemma 4 E2B, quantised) for dialogue only.
- **Deterministic state machine** — guard state, conversation flags, what he has let slip.
- **Simple save state** — one structured JSON file. Human-readable, debuggable.
- **The orb.** Pulsing. Colour tracks the guard's mood.
- **No dice, no inventory, no combat.** Not yet.

### Later — Elaboration

- Coqui TTS for a distinctive character voice (Northern English, sparse, Yoda-adjacent).
- SRD rules index (embedded lookup) for player rules questions ("can I dual-wield this?").
- Full 5e combat with severity tiers (grazed / wounded / dying) driving narration cues.
- Persistent economy — gold, merchants, saving up for items.
- Evolving personality: callback memory ("Ahh, reaching for the sword again, are we?").
- Progression: skills, reputation, titles.
- Retention: return ritual, cliffhangers, daily refresh.
- Additional skins: sci-fi derelict starship, chaotic restaurant kitchen, etc.
- Public engine API.

### Explicitly NOT in scope for v0.1

Multiple maps. Character sheets. Combat system. Economy. Multiplayer. iOS.
Personality flourishes. Anything with a menu.

---

## 9. The Maze — the second test bed

If the cell-and-guard proves **conversation**, the maze proves the **world model**.

A deliberately basic maze is the right instrument because it is *pure spatial navigation* —
it isolates direction, distance and time with nothing else muddying the water.

> **If a player can build a mental map of a maze purely from the DM's voice, the world model
> genuinely works.**

It also stress-tests time (you won't clear it in five minutes) and description quality.

### The disorientation risk

In a maze you cannot see, going round in circles is not a challenge — **it is maddening**, and
they will quit. So the breadcrumb mechanism is not a nice-to-have. It is essential.

### Breadcrumbs — the DM as the player's memory

The engine tracks every cell visited. A sighted player in a maze glances back; **your player
cannot, so the engine remembers *for* them and the DM voices it.**

> *"The passage ahead you've not trodden. The one to your left, you have."*

The player navigates by the DM's recall. That is the world model earning its keep — and the
player feels **known**.

**Landmarks, not bearings.** Give each junction a distinct, memorable feature — *the mossy
arch, the dripping alcove*. "Turn left" is hard to hold in your head; "the dripping alcove"
sticks. **Human memory hangs on features, not compass bearings.**

### Sensory beacons and the intensity gradient

Distant light and the sound of rushing water are not just atmosphere — they are **navigational
anchors**, fixed points to orient against when everything else is a tangle of turns.

The magic is the **gradient**: *"the water is getting louder," "the light is growing."* This
tells the player they're heading the right way **without the DM ever saying so**. They deduce
it themselves — which feels like *their* skill, *their* discovery. Far more satisfying than a
hint.

Mechanically it's the same trick again: the engine knows the distance from player to water
source, and translates that number into intensity — *faint → growing → loud → roaring*. The AI
voices the current level.

**Double duty:** rushing water is orientation *and* dread at once. Efficient design.

### The costed exit — a shortcut with a price

Respect the player's real-world context. Someone walking the dog may not have the headspace to
solve the maze right now. **So give them an out — but not for free.**

| Choice | Cost | Reward |
|---|---|---|
| **Navigate it yourself** | Time, attention, effort | Pick a safe route. Avoid the lair entirely |
| **Take the quick exit** | Higher odds of an encounter — you'll walk through the lair and end up in a scrap | Speed. Zero effort |

A real decision with real trade-offs, and **both paths are valid**. It flexes to the player's
attention: fully engaged on the sofa? Navigate, master it, feel clever. Half-distracted on a
walk? Take the exit, roll the dice, still get a satisfying beat.

**And it is not a new system.** It is the map, the lair's position, and context-aware
randomness (§6) *combining*. Exactly the folding-in predicted in §22.

---

## 10. Constraints

- **On-device.** No network round-trip for the core loop — latency is the enemy.
- **Android-first.** iOS deferred until validated (dev cost).
- **Mid-range Android phone** is the target device, not a flagship. Test on real hardware early.
- **Family-friendly.** Content rating is a design constraint, not an afterthought.
- **SRD-compliant.** See §16.

---

## 11. Tech stack (provisional — to be validated)

### The build order — *two phases, kept apart*

**Phase 1 — desktop prototype: Python.** Not React Native. Not yet. Python is the fastest
route to proving the heartbeat — you speak, the engine decides, it speaks back — and it is
where the object model, the state machine and the brief-builder actually get designed.
**The engine is the hard part, and Python is the right language to think in.**

**Phase 2 — the phone.** Only once the loop is proven does the app shell matter. Keep the two
phases cleanly separated; do not let React Native's bridging pain contaminate the period when
you are still working out what the engine *is*.

> **The engine is portable. The shell is disposable. Build them in that order.**

*(Note: §0's spike is deliberately independent of both — it is a bare benchmark on real
hardware, not an app.)*

### The stack

| Layer | Choice | Notes |
|---|---|---|
| Prototype language | **Python** | Fast to think in. Where the engine gets designed |
| World model | **Evennia** (candidate — see below) | Python-native. Could save months of plumbing |
| App shell (later) | React Native | Familiar; native modules needed for the heavy lifting. **Deferred** |
| LLM runtime | MediaPipe LLM Inference API / LiteRT, or llama.cpp for ARM | **GPU is *not* automatically the answer — see §0.** Measure CPU and GPU |
| Model | Gemma 4 E2B (quantised `.litertlm`) | Doesn't need to be clever. Needs to be *obedient and consistent* |
| SRD rules index (later) | Lightweight embedding model + on-device vector store | SRD chunked and embedded once. *Store not yet chosen — see open questions.* |
| STT | Google on-device | Solid, fast, free |
| TTS (v0.1) | Google on-device | Placeholder. Clear but neutral |
| TTS (later) | Coqui TTS | Character voice, voice cloning. Footprint/speed on phone unproven |
| Save state | JSON file | Keep it dumb and reliable |

**Prototype on desktop, but port to a real phone early.** Desktop will flatter the
latency and lull you into false confidence.

### 🌟 Evennia — the shortcut for the non-AI half

The deterministic engine described in §4 — objects with **state, containment, relationships,
capabilities** (`takeable`, `openable`, `lockable`) — is not a new problem. **Interactive
fiction has been solving it since the 1980s.** There is no medal for rebuilding it.

**Evennia** is the closest fit found:

- **Python-native**, open source, actively maintained (v5.x, current).
- **Typeclasses** — persistent Python objects with database-backed attributes. This *is* the object model of §4, already built, already tested.
- Rooms, exits, characters, containment, state persistence — **out of the box**.
- A **turn-based, D&D-style combat contrib** waiting for later (§8, Elaboration).
- **It already has an LLM NPC contrib** — a character class that queries a language model for its replies, complete with a "pondering" filler message if generation runs long. *That is the guard, half-built.*

**The caveat, honestly stated:** Evennia is built for **MUDs** — multiplayer online text games.
It ships with a server and a networking layer a single-player phone app does not need. The move
is to **borrow the world model and ignore the scaffolding** — and to be alert to the risk of
inheriting a heavier framework than the job requires.

*(And note the irony: that unwanted multiplayer scaffolding is exactly what "five people in a
car" (§23) would one day need. Worth remembering before ripping it out.)*

### The peer group — what else was considered

| Tool | Verdict |
|---|---|
| **Inform 7 / TADS** | Decades of world-modelling rigour, and the gold standard for it. But **walled gardens with their own languages**, and their dialogue systems are famously primitive — precisely the part you are replacing with the LLM. **Reference, not foundation.** |
| **Emerging "AI RPG engines"** | A real and growing category. At least one describes itself almost word-for-word like this document — persistent memory, independent NPC minds, a reactive world. **Mostly cloud-model-based, screen-first.** Study them for architecture ideas *and* as a competitive check (§19) |

> **Borrow the bones from Evennia. Learn world-modelling patterns from interactive fiction.
> Watch the AI RPG engines. Build only what is genuinely yours: the harness, the voice, the
> constraint.**

---

## 11b. Audio design — *the second language*

A screen game hands you a heads-up display for free: health bar, minimap, inventory, all glanceable
at once. **An audio game has none of that.** Rather than mourn it, build a HUD out of *sound* — a
second channel running underneath the dialogue, telling the player how they are and where they are
without a single word being spoken.

This is not decoration. **It is a parallel information stream**, and it is owned by the engine
exactly like everything else (§4). Audio state is just another property of world state.

### The precedent — BBC radio drama

Radio 4 plays did this for decades with a **keyboard of effects**: a small, curated, preloaded
palette, triggered live at the right moment and volume. That is the model — **not** on-the-fly
synthesis or generation, but a **finite bank of intentional effects**, selected and layered by the
engine against the current state. A small palette used brilliantly beats an infinite one used
poorly.

### The three layers

| Layer | What it encodes | How it behaves |
|---|---|---|
| **1. Mood music** | Which world you're in, the baseline tone | Persistent, low, adaptive per location. Dungeon vs forest vs a tense standoff |
| **2. Health — the heartbeat** | The player's HP, felt not stated | Silent when healthy. A faint pulse when scratched. Louder and faster as damage mounts. *Bleeding out is a pounding boom-boom-boom* |
| **3. Ambient bed** | Where you physically are | Above ground: a few birds, air, calm. Below ground: silence and the slow drip of water in stone |

### The Skyrim principle — *the silence that screams*

Skyrim keeps music playing almost constantly. You stop consciously hearing it — it simply *is* the
atmosphere. **The trick this unlocks is the cut.**

> **When the music suddenly drops and it's just heartbeat, breath and a single dripping sound —
> the silence is deafening. The player's lizard brain knows something is wrong before their
> conscious mind catches up.**

The persistent bed exists *so that its absence can carry meaning*. Danger doesn't need announcing;
you pull the music, throw the health and ambient layers into sharp relief, and dread arrives on its
own. This is the §9 intensity-gradient trick again — *let the player deduce it* — applied to the
whole soundscape.

### The heartbeat solves the hit-point problem

Hit points are the hardest number to convey by voice — you can't glance at a bar. Two devices carry
it, and neither is a spoken statistic:

1. **Narrated feeling.** The engine owns the true number; the DM voices the *state*. Not "you are at 7 hit points" but *"you're bloodied, breathing ragged, that one really landed."*
2. **The heartbeat layer.** Your own pulse is the health bar. It is visceral, pre-verbal, and never breaks the fiction.

When the player *asks* outright — *"how bad is it?"* — the answer comes from their **gear** (see
§12b), in character, in relative terms: *"Half-gone, and I wouldn't take another hit like that."*
The point is a real, retreat-or-fight decision made **without ever reading a spreadsheet.**

### Implementation

- **Engine-owned and deterministic.** The engine already knows HP, location, time of day, and mood — it simply selects and layers the matching assets. Audio selection is the same discipline as the brief-builder (§4): *know the truth, express it with the right asset.*
- **Preloaded bank.** Heartbeats at graded tempos/volumes; ambient beds per environment; mood tracks per world and tension level. No synthesis in the core loop.
- **Layering and ducking.** Music ducks or cuts on danger; heartbeat rises with damage; ambient sits under both. Simple cross-fades, not clever DSP.
- **Not a v0.1 concern** — the cell-and-guard PoC can ship dry. But this is a *cheap, high-impact* early elaboration, and it is pure engine work with **no AI and no LLM cost.**

---

## 12. The Character Engine

An NPC is just **the DM wearing a different hat**. Same director/actor machinery, pointed at
a single person instead of the whole scene. The DM *narrates* the world; the NPC *lives in* it,
with his own wants and moods.

This is not new technology and should not be treated as such. **No frontier AI required.**

### The Tamagotchi model

The guard is a pet you are tending. Underneath the conversation sits a **mood dial** the
engine owns. Say something kind or clever, it ticks up. Threaten him, lie clumsily, slip up —
it ticks down. The AI simply voices wherever the dial currently sits: gruff and guarded when
low, softening as it climbs. Cross a threshold, and he opens the door.

**You are not solving a puzzle. You are tending a mood.**

### Per-NPC state model

| Component | Example (the guard) |
|---|---|
| **Mood dial(s)** | Suspicion, warmth |
| **Drives** | Bored. Cold. Wants his shift to end. Secretly soft on prisoners |
| **Memory** | What you've said, what he's let slip, how you've treated him |
| **Thresholds** | Below X he calls for backup; above Y he unlocks the door |

The **illusion of autonomy** comes from drives that tick along regardless of the player.
The guard exists when you're not talking to him. That is not real intelligence — it is
**consistent wants plus memory**, which is indistinguishable from the outside.

### It solves the jeopardy problem

Family-friendly means nobody dies — so where are the stakes? *Here.* Anger the guard enough
and he storms off, the mood locks, and you have lost your only way out. Consequences that
sting without being grim.

**Open design question:** what actually moves the dial? Needs sketching.

---

## 12b. Inventory as character — *the Rogue Trooper pattern*

### The problem

D&D is **paperwork**. The tabletop player is forever reaching for a pencil — tracking equipment,
spell slots, what's equipped, ammunition, damage. On a screen you offload all of it to a character
sheet you glance at. **In pure audio, there is no sheet to glance at.** Ask the player to hold their
entire inventory in their head and the cognitive load sinks the game — especially for the youngest
players, and especially on a distracted dog-walk.

### The solution — *your kit talks back*

From the 2000 AD comic **Rogue Trooper**: a lone soldier carries three dead comrades' personalities
as biochips — **Gunnar** in the rifle, **Helm** in the helmet, **Bagman** in the backpack. He
doesn't consult a menu; he *talks to his gear*, and it answers, in character.

> **Do not make the player read a list. Make them *ask their kit* — and let the kit answer with a
> personality.**

You need a rope? You ask the pack, and it grumbles one back. Loading a spell? The staff tells you
what's in which slot, maybe fussy about it. Every inventory check becomes a **micro-conversation**,
not a menu — and the flavour comes free with the fact.

### Why this is three wins, not one

- **It kills the paperwork** — the whole reason the pattern exists. The player learns what they're carrying by *talking*, the most natural audio act there is.
- **It's companionship.** Multiple voices in your head means you're never alone, without the full cost of a companion NPC (§23). Someone to talk *to*, not just narrate *at*.
- **The kit can push back** — *"Gunnar wants to shoot,"* *"Helm says it's a trap."* Collaborative, opinionated, alive. Gear with a stake in the outcome.

### The vessel owns the list — *not the spell*

An important refinement, so this doesn't multiply out of control:

> **The personality lives in the *wielding object*, not in each item it holds.**

The **staff** is one character. It knows its own loadout and tells you: *"Slot one, a fireball.
Slot two, a shield. Slot three's empty — save it, in case this all goes wrong."* You do **not**
give every individual spell its own mind. One voice per vessel, and that voice is the interface to
everything inside it. The wand, the pack, the weapon — each a single persona that reports on its
own contents.

### It reskins per world — same pattern, new flavour

The pattern is generic; only the dressing changes with the skin (§8, §23):

| World | The voices might be |
|---|---|
| **Fantasy dungeon** | Helmet, backpack, weapon/staff — classic Rogue Trooper |
| **Sci-fi derelict** | Suit AI, toolkit, scanner |
| **Restaurant kitchen** | Head chef in your ear, the sous, the pass |

Same machinery underneath; wildly different feel on top. Exactly the object-model promise of §4.

### Architecturally, it's nothing new

Each talking vessel is **just another NPC running the Character Engine (§12)** — its own small
personality and voice — tethered to a thing the player carries. It reads its contents straight off
the object model (§4); the item list *is* state, the persona merely voices it. No new system, no
frontier AI. **The same director/actor split, pointed at a rucksack.**

**Scope note.** Not v0.1 — the cell-and-guard has no items by design (§8). This lands in **v0.2+**,
once one room is proven alive. But it reshapes how the Character Engine is built, so it's recorded
now: keep the persona-per-vessel wiring generic from the start.

---

## 13. Authoring Mode

A **design mode** distinct from play mode, in which *you* walk your own dungeon and narrate
the world into existence. Everything you commit becomes **canon the DM must honour**.

You stroll the passage and say: *"Beyond this wall — rolling farmland, a distant church
spire, smoke from cottages."* **Commit.** Now it is locked.

- This is **not** machine-learning training. It is **authoring the world bible by playing through it.**
- It pre-answers the questions players are likely to ask — in *your* voice, with *your* taste.
- Runtime improvisation shrinks to only the genuinely unexpected, because the obvious is already fleshed out.

**The strategic bonus:** this same mechanism is the **content pipeline for every future skin.**
Walk the starship, commit its facts. Walk the restaurant, commit its facts. One tool, endless
worlds — and very likely the mechanism by which *other creators* build on the engine later.
It ties straight back to the engine-as-a-product plan (§25).

**Cost to watch:** the richer you author, the more canon there is, and the heavier every turn's
context gets. See Gotcha #7.

---

## 14. Automated AI Playtesting

Authoring Mode's sibling. **One AI helps you *build* the world; another tries to *break* it.**

Point a **frontier model** (not the on-device one) at the dungeon and let it hammer the engine
with hundreds of permutations you would never think of. You will walk your own dungeon the same
way every time; it won't.

It will try to seduce the guard, bribe him, confuse him, claim to be the king, ask what's over
the wall, name things that don't exist. **Every ungraceful response is a gap to patch. Every
improvised detail it forces becomes seeded canon.**

Essentially a **fuzzing tool** for the deterministic engine — throw chaos at it and see where
it cracks or contradicts. Vastly more coverage than one human tester.

**Two caveats:**
1. It tests the **logic**, not the **feel**. It will tell you if the state holds up; it will *not* tell you whether the voice sounds human.
2. **Log everything.** Full input/output traces, or you won't know which input broke what.

---

## 15. Personality design

Personality is **authored, not learned.**

- Voice, catchphrases, humour, speech patterns — defined in the system prompt, pinned to a consistent TTS voice.
- The "evolving" feel comes from **curated recall**, not training: the engine logs notable moments, tags a few as *callback-worthy*, and surfaces them at the right time.
- Signature tics — always grumbles before a trap, always sighs when you pick the sword.

**Hard rule:** personality is flavour on top of the state machine. **Charm cannot break continuity.**

---

## 16. Legal — SRD licensing

**Verified July 2026.** The D&D System Reference Document is available under
**Creative Commons Attribution 4.0 (CC-BY-4.0)** — irrevocable, royalty-free,
commercial use explicitly permitted. Wizards attempted to walk this back in 2023,
faced a community backlash, and retreated. It is now permanently locked in.

- **SRD 5.1** (2014 rules) and **SRD 5.2** (2024 rules, updated May 2025) — both usable commercially.
- **Obligation:** attribution line crediting the SRD. That's it. No sharealike — your own code and content stay yours.
- **Off-limits:** branded IP. Beholders, mind flayers, Forgotten Realms, named settings and lore.
  Use the open skeleton; **invent your own creatures, places and names.**
- **Marketing:** describe it as a *fantasy roleplay engine*, not "D&D". Sidesteps the whole issue.

You want to attribute generously — it's a selling point, and the licence makes it free to do so.

---

## 17. Content safety

**Family-friendly** is the decision. This narrows content and *widens* the market —
parents, kids, classrooms.

- Heroic, bloodless combat. "Knocked out" and "defeated", not gore.
- Peril and tension, yes. Description of violence, no. **Suggestion beats description.**
- **Guardrail layer:** filter LLM output before it's spoken. On a trip, fall back to a safe pre-written line.
- The bounded architecture already boxes the model in — trips should be rare.

---

## 18. Retention design (post-PoC)

- **Return ritual.** DM greets you, recaps where you left off, teases what's next. Reopening should feel *warm*.
- **Cliffhangers.** End sessions on a hook, never a resolution. Serialised, like a good podcast.
- **Economy.** Gold and inventory that persist. You've *earned* that sword. (Pure engine work — no AI needed.)
- **Progression you can feel.** Skills, reputation, a title.
- **The relationship.** The real moat. People return for people. A DM that remembers you beats any points system.

---

## 19. Competitive position

| | Coherence | Voice-first | Game engine | Evolving character |
|---|---|---|---|---|
| AI Dungeon & similar | ✗ (too open, loses the plot) | ✗ (text, screen-heavy) | ✗ | ✗ |
| AI voice companions | — | ✓ | ✗ (no rules, no stakes) | partial |
| **This** | ✓ | ✓ | ✓ | ✓ |

The existing tools are clunky *because* they let the AI do everything. The gap is a
**bounded, rules-driven engine with voice-first delivery and a DM with a memory.**
Nobody is properly combining all four.

*Action: run a fresh competitive search before committing — this space moves fast.*

### The moat — an honest examination

Others *are* building in this space (see §11, the peer group). That discovery prompts the
natural scramble: **where exactly is the moat?** The answer needs to be honest, because a moat
you cannot defend is not a moat.

**The instinct: on-device, and audio-first.**

That instinct is right about *why* those two are hard. Everyone else is building cloud-model,
screen-based AI RPGs **because it is the easy version** — big model, big server, text on a
glass rectangle. Doing it as a *tiny* model, on a phone, offline, by **voice alone** forces a
discipline nobody else is bothering with. The constraint is the design.

**But here is the uncomfortable truth:**

> **On-device is a moat with a shelf life.** In two or three years, mid-range phones will run
> far bigger models comfortably — and the constraint that currently forces your rigour will
> ease for *everyone*, not just you.

So the engineering edge is a **wedge, not a moat**. It is how you get in, and it buys a head
start. What you build *with* that head start is the actual defence:

| | Erodes with hardware? |
|---|---|
| On-device tiny-model performance | **Yes.** Hardware catches up |
| Voice-first design discipline | Partly — but taste is not commoditised |
| **The relationship** — a DM that remembers *you* | **No** |
| **The character sheet** you feel is genuinely yours (§23) | **No** |
| **The harness pattern** (§1) — the accumulated pain of bounding a model into a role | **No.** This is the "selling shovels" asset (§25) |
| Feel, pace, humour, taste | **No** |

**Conclusion.** Hold on-device and audio-first as the **wedge** — the reason to exist now, the
thing that makes the product distinctive today. But understand that the thing actually being
defended is **the relationship and the harness**. As §18 already said, without quite realising
its full weight: **people come back for people.** That does not erode when the chips get faster.

---

## 20. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Latency** — LLM generation + TTS round trip feels dead | **High** | Stream: speak sentence one whilst the rest generates. Keep responses short (the Yoda principle does this for free) |
| **TTS sounds robotic** | Medium | *Reframed:* pacing and cadence carry humanity, not timbre. A foreign accent sounds robotic and we forgive it instantly. Avoid drawn-out words and unnatural pauses. Lean into a characterful accent — the quirk becomes the feature |
| **2B model too dim / hallucinates** | Low | Engine does the thinking. The AI only voices tight briefs. Less rope, less trouble |
| **Battery and heat** | Medium | Short generations, small model, fire the LLM only when needed. Manageable, not solved. Test on the walk |
| **Retention** — interactive fiction is notorious for one-and-done | Medium | See §18. The DM relationship is the answer |
| **Discovery** — novel category, hard to pitch in one app-store line | Medium | "Interactive podcast" is the hook |
| **Engine-as-a-product ≠ consumer app** | Medium | Different beast: docs, stable interface, support. A later problem, but a real one |

---

## 21. Success criteria

**v0.1 (Proof of Concept):**
> Does one room feel *alive*? Does the loop breathe — you speak, it understands,
> the engine decides, the DM answers coherently and in character?

**v0.2 (Family beta):**
> **Does someone in my family start a second session, unprompted?**

That's the whole test. If they come back without being asked, the magic is real.
Kids will not be polite about dead air or a boring DM — unfiltered signal.

---

## 22. Gotchas — things to consider

*A running register. Expect it to grow. **Severity:** 🔴 blocks the PoC · 🟠 bites once people
are playing · 🟢 a champagne problem (only exists if they love it).*

### A. World consistency — the "it's all just state" family

| # | Gotcha | Sev | Resolution |
|---|---|---|---|
| 1 | **Compound commands.** *"Go down the passage, stand at the end, hide in the dark, wait."* Four intents in one breath. | 🟠 | The AI does the one job it's genuinely good at — **translating** messy natural language into a structured list of intents. It does *not* resolve them. The engine takes the clean list and executes each against the world state, one at a time. **A translator at the front door, not the decision-maker.** |
| 2 | **Grounding.** The player names something that isn't there — *"the dark passage"* when you only have a north corridor. | 🟠 | The engine holds the finite truth of what exists. The AI must **map onto that list, never conjure**. If nothing matches, the DM redirects in character: *"You peer about, but there's no dark passage here — only the north corridor and a rusted gate."* The constraint becomes flavour. |
| 3 | **Improvised detail becomes canon.** *"What's over the wall?"* → "rolling green hills." Twenty minutes later → "a dark forest." Contradiction. Illusion dead. | 🔴 | **The instant the AI invents something, it stops being improvisation and becomes fact.** The engine writes it straight to state (`over_the_wall = rolling green hills`) and feeds it back in every future brief. The AI may be spontaneous **once per detail** — thereafter it is bound by its own word. Exactly what a good human DM does behind the screen: improvise, then *jot it down*. |
| 4 | **Context for plausible improvisation.** When it *must* invent, how does it invent *well*? | 🟠 | The save state carries a **world bible** alongside the hard facts: setting, tone, what lies beyond. Damp medieval dungeon, tense but hopeful, pastoral farmland beyond the walls. Green hills, yes. A neon spaceport, no. **Hard facts constrain what's true; soft context steers what's plausible.** The AI never improvises from a blank page. |
| 5 | **Persistent effects.** A spell turns hair green. An NPC loses an arm. A door is scorched. It all has to *stick*. | 🟠 | Not a special case — **the same machinery as a key unlocking a door**, just with more colourful properties. An effect is *a change to a tracked property, plus a duration.* Green hair = permanent; sleep = 3 turns; burning door = lit → ash over time. The engine ticks them along and hands the AI the **current truth** each turn. The AI never *remembers* the spell — it doesn't need to. It's simply told the guard has one arm, and so cannot narrate him picking things up with two. **Define upfront which properties an effect may touch.** |
| 6 | **Save-state bloat.** Every improvised detail becomes canon (#3) — so canon grows forever, and eventually won't fit the context window. | 🟠 | Decide what stays sharp and what gets quietly summarised. Tiered memory: hot facts verbatim, cold facts compressed. *Unsolved — needs design.* Note: exploratory memory-architecture work exists in `small-model-big-memory-dev-plan.md` (13 July), but its conclusions are **not settled and not assumed by this design** — and see #6a on why this is engine-side, not a model memory layer. |
| 7 | **Cost of the seeding run.** Authoring a rich world (§13) means a *lot* of committed canon — which feeds straight back into #6. | 🟠 | The richer you author, the heavier every turn. Tension between world depth and context budget. *Unsolved.* |
| 6a | **Framing note for #6/#7.** | 🟠 | These are **engine-side retrieval over structured state**, not an LLM memory layer. The engine owns canon; the question is how it *stores and selects* what to feed each turn's brief (§4), not how the model remembers. Keep any memory-brain experiments firmly separate unless a decision says otherwise. |

### B. Voice and conversation — the make-or-break tier

| # | Gotcha | Sev | Notes |
|---|---|---|---|
| 8 | **Interruption / barge-in.** It's a real conversation, so the player *will* talk over the DM. | 🔴 | **Solved (design; needs Android validation).** The DM behaves like a good human one: the instant the player speaks, it **stops mid-sentence and listens.** When they're done it offers *"...shall I go on?"* / *"want me to repeat that?"* and resumes from where it was cut. The player self-regulates — interrupting just to hear the same line again gets old, so they let it finish. **No dead air, no ploughing on.** *(Open sub-question: can Android STT/TTS actually stop TTS mid-utterance and switch to listening fast enough? — see §20.)* |
| 9 | **Mishearing.** STT garbles invented fantasy names — and they're on a dog walk, in the wind. | 🔴 | **Solved by the same move as #8.** When confidence is low or the parse maps to nothing (§4, Gotcha #2), the DM **never acts on nonsense** — it asks, in character: *"Say that again?"* / *"The wind stole your words, traveller."* The recovery *is* the character. Repeated for the youngest players until it lands, gently, never with irritation. **One graceful "repeat" primitive covers both #8 and #9.** |
| 10 | **Empty input.** The player goes quiet — thinking, or distracted by the actual dog. | 🔴 | **Solved: a nudge ladder, escalating gently.** (1) **Diegetic nudges first** — the world does the prompting: *"A sound echoes from down the passage..."* — context-aware (§6), never breaking fiction, often enough to restart them. (2) Then a soft check: *"...you still there?"* (3) Finally a **warm timeout** that closes the session in character: *"We'll carry on the adventure another day."* Reads the room *for* the player, and even the giving-up is part of the story. Ties into the return ritual (§18). |
| 11 | **The accidental command.** *"Sit down, good boy"* gets caught by the mic and becomes a game action. | 🟠 | Need a way to distinguish in-game speech from real-world chatter. Push-to-talk? A wake pattern? |
| 12 | **Accent and voice range.** A soft-voiced child; a strong regional accent. Google's STT is good, not flawless. | 🟠 | Directly threatens the family beta — the very people you most need to delight. |
| 13 | **The backseat player.** One person holds the phone; three shout suggestions. | 🟢 | Whose voice counts? A genuine mess for STT *and* for the fiction. |
| 14 | **The long monologue trap.** Sometimes the story genuinely needs a longer beat — a big reveal, a richly described room. | 🟠 | But the whole voice design is sparse and snappy. **Knowing when to break your own rule is the art.** |
| 15 | **Repetition.** The player retries the same locked chest. An identical line each time *screams machine*. | 🟠 | **Solved: the world *wears down*.** Two parts. (1) Response *variety* — the DM varies the line and gets wry about it. (2) Better still, **the state actually changes with repetition**: the engine counts attempts, and eventually the world answers — *"Keep forcing it and the key will snap..."* The chest resists, the lock bends, the tool strains. Not a canned reply but a **real consequence fed back into state** (§4). Repetition stops being a seam and becomes a mechanic. |

### C. Player psychology

| # | Gotcha | Sev | Notes |
|---|---|---|---|
| 16 | **The trust wobble.** The *first* time the DM forgets your sword or contradicts itself, faith cracks — and once they're watching for the seams, the magic is gone for good. | 🔴 | **Early sessions matter disproportionately.** The DM must be near-flawless while the player is still deciding whether to believe. |
| 17 | **The show-off moment.** Players — *especially kids* — will deliberately try to break it. *"Can you rap? Who's the Prime Minister?"* | 🟠 | The DM must **deflect in character** — *"Such matters lie beyond these walls, traveller"* — never break the fiction by answering like a chatbot. |
| 18 | **The emotional stakes gap.** Family-friendly means nobody dies. So where's the jeopardy? | 🟠 | **Solved by the Character Engine (§12):** anger the guard, he storms off, the mood locks, you've lost your only way out. Stings without being grim. |
| 19 | **Onboarding — the first thirty seconds.** A new player opens the app to an orb and silence. | 🔴 | Do they know they can speak? What to say? That blank first moment could lose them *before the magic even starts.* |
| 20 | **Emotional tone mismatch.** The engine says *danger*, so the brief says *tense* — but the player's been treating the whole thing as a comedy. A suddenly grave DM jars. | 🟢 | Matching the player's register over time is subtle work. |
| 21 | **Pace of progress.** One player cracks it in ten minutes; another wanders for an hour. | 🟠 | Nudge the stuck without hand-holding the quick. A hint system that's subtle, in character, and well-timed is genuinely fiddly. |
| 22 | **Resume after days.** The return ritual assumes they remember. After a fortnight away, they've forgotten the plot, the puzzle, what they were carrying. | 🟢 | The recap must genuinely **re-orient**, not just say "welcome back" — or they'll feel lost and quit. |
| 23 | **"I forgot how to play."** They forget they can just *talk*, or what the rules were. | 🟢 | Re-teaching purely through the DM's voice, with no tutorial screen. Neat challenge. |

### D. Design and architecture

| # | Gotcha | Sev | Notes |
|---|---|---|---|
| 24 | **Unwinnable states.** A rigid puzzle chain means the player can strand themselves — drop the only key down a hole, burn the rope they needed. | 🟠 | Either the engine permits soft-locks (bad) or you **design so nothing essential can ever be truly lost**. Real risk with a strict chain. *(Largely dodged in v0.1 — the guard scenario has no items.)* |
| 25 | **Multiple profiles.** A family shares one phone — *and yours will, that's the beta.* Dad's halfway through; the kids want their own run. | 🟠 | Touches the save architecture **early**. Worth deciding now, not later. |
| 26 | **The bear in the cell.** Random events must never be absurd for the situation. | 🟠 | **Solved by §6:** per-situation event tables. Randomness picks only from what the engine already knows fits. *"Random, but never absurd."* |
| 27 | **Maze disorientation.** Going round in circles you cannot see is not a challenge — it is maddening. | 🔴 | **Solved by §9:** breadcrumbs, named landmarks, sensory beacons with an intensity gradient. **The DM is the player's memory.** |
| 28 | **Procedural generation loses the authored soul.** Randomly assembled dungeons feel samey and hollow. | 🟢 | Blend: **procedural skeleton, authored highlights.** Confine generation to the benign connective tissue (§23). |
| 29 | **Companion bookkeeping.** Each companion is another position, mood, memory, voice. | 🟢 | Powerful, but it *multiplies* state. Keep the count low. (§23) |
| 30 | **The walking reward drags in permissions.** Step-tracking, pedometers, possibly GPS. | 🟢 | A whole new dimension of complexity, privacy and platform permissions — *especially* with a family-friendly, child-facing product. **Park it entirely for the PoC.** (§23) |
| 31 | **Multi-agent NPCs contradict each other and the world.** Independent minds will drift out of alignment. | 🟢 | **The engine remains the single source of truth. Agents *propose*; the engine *disposes*.** No agent may write to world state directly. (§23) |
| 32 | **Multi-agent compute cost.** Every NPC as its own AI instance multiplies latency and spend — fighting *directly* against the on-device goal. | 🟢 | Cloud-only, premium tier. **Never the phone default.** (§23) |
| 33 | **NFT baggage.** Blockchain association could repel a family audience and trip app-store crypto rules. | 🟢 | **Keep the unique key and portable export. Park the blockchain wrapper.** The uniqueness lives in the sentiment, not the crypto. (§23) |
| 34 | **Audio-only cognitive load.** Inventory, spell slots, equipment, HP — all trivially glanceable on a screen, all a memory burden by voice. | 🟠 | **Solved by §12b:** the player never holds the list — they *ask their kit*, and it answers in character. Paperwork becomes conversation. HP is narrated as *feeling* + heartbeat (§11b), never a number. |
| 35 | **Talking to your gear muddies intent-parsing.** The player now addresses the pack, the staff, the guard, *and* the DM — the parser must know *who* is being spoken to. | 🟠 | **Solved: wake words per voice.** Each personality (DM, helmet, pack, staff) has an **address marker** — *"Helmet, how bad is it?"* vs. an unmarked line to the DM. Explicit, unambiguous, no clever NLP; doubles as a voice-UI pattern the player internalises fast (hear the name, know who answers). **Wake words are user-reassignable** — say *"hey pack"* or whatever rolls off *your* tongue. The words themselves are part of per-world voice design: make them natural to say. |
| 36 | **Soundscape masks the voice.** Heartbeat, dripping, mood music and dialogue all share one tiny mono speaker on a windy walk. | 🟠 | **Solved: speech always wins.** The engine owns mix priority — when any voice speaks, all layers **duck under it**, rising again after. A **~200 ms crossfade** on the way back stops it feeling dead; it *breathes*. Music level is also a **user option** — dial it low or off for clarity on a noisy walk. Deterministic mixing rule, no DSP cleverness. |

---

### 🔴 The four that must be solved before anything else

**Latency and turn-taking (§20), interruption (#8), mishearing (#9), and the trust wobble (#16).**
These four hit within the **first thirty seconds of the first session**. Get them wrong and
nobody ever reaches the good bit. Everything else can be designed around as it shows up.

**Status (v0.7):** #8 and #9 now have a **shared design solution** — the graceful *"shall I
repeat?"* recovery — but both still carry a **hardware question**: can Android actually halt TTS
mid-utterance and switch to listening fast enough to feel natural? That is a **spike-adjacent
validation** (§0), not a design gap. #16, the trust wobble, remains a discipline to *earn* session
by session, not a thing you "solve" once. Latency stays the top technical risk until measured on
real hardware.

### A note on the shape of this list

As the register grows, **new gotchas will increasingly fold into old ones** — *"yep, that's just
state again."* This is **a good sign, not a disappointing one.** One principle absorbing every new
problem is exactly what a sound architecture looks like. You are not running out of answers; you
are discovering you only ever needed the one.

**When the gotchas stop needing new solutions, that's the signal the engine is conceptually
complete — and it's time to stop philosophising and start building.**

---

## 23. Future directions

*Explicitly **not** proof-of-concept work. Recorded so they aren't lost — and because one of
them may be the real product.*

### Companions

In D&D terms: **familiars**, animal companions, sidekicks, followers.

A companion is just **another NPC running the Character Engine (§12)** — own mood, own drives,
own memory. The difference: they're on *your* side, so the engine tracks their position
alongside yours in the state vector.

**Why they matter for an audio game:** a companion gives the player someone to talk *to*, not
just at. A DM narrates the world; a familiar *reacts to it with you*.

> *"The rat bristles — it senses something you don't."*

Atmosphere, hint system, and companionship in one line. And they carry real stakes — you'd
protect a companion you'd grown fond of.

**Watch:** every companion is more state, another mood to keep consistent, another voice.
Powerful, but it multiplies the bookkeeping.

### Game modes — dials on the world

Game mode is not a new system. The engine already owns time, randomness, encounter rates, the
guard's mood thresholds — **all numbers**. A game mode is simply a set of dials that tunes them
all at once.

| | Harsh | Easy |
|---|---|---|
| Encounter rolls | Frequent | Rare |
| Mood dials | Stingy | Forgiving |
| Experience | Slow | Quick |

Same engine, same objects. **Parameters turned up or down.**

### Procedural generation — as *connective tissue*

Because everything is an object (§4), the engine can **assemble** dungeons rather than have you
hand-author every one. Endless content from the same parts.

**But the division matters:** procedural generation earns its keep in the ***benign* stretches** —
the connective tissue *between* authored set-pieces. You do not proceduralise the clever escape
room. You proceduralise **the walk through the forest to get there** — the bits where nothing
critical happens, but the world should still feel alive.

> **Hand-author the moments that matter. Procedurally generate the journeys between them.**

This makes procedural gen a **pacing tool**, sized to how long the player is actually walking.
Long commute? The forest is longer, a couple more encounters. Quick hop? Straight through.

**The risk:** procedural generation is where you lose the authored soul. A hand-crafted dungeon
has intent, pace, a clever puzzle. Randomly assembled ones feel samey and hollow. Keep the soul
in the set-pieces.

### 🌟 The walking reward — the north-star feature

> **"The adventure that rewards you for walking."**

The in-game journey and the player's *real* journey run in parallel — and are **linked**.

| | Effort | Outcome |
|---|---|---|
| **Walk the forest** (really walking) | Slow. Real steps | Richer encounters, faster experience, the chance of stumbling on something *good* |
| **Take the cart** | Instant. Time passes massively | You arrive fast. You gain little |

**This flips the usual thing on its head.** In most games you'd take fast travel every time.
Here the slow road is the rewarding one — precisely because you move your actual body to earn it.

You have quietly built **a walking app wearing a dungeon costume.** It is a real hook, and a
wholesome one — parents would love it for kids.

**The caution — and it was flagged at the time:** this edges toward step-tracking, pedometers,
possibly GPS. A whole new dimension of complexity and permissions. **Park it. Do not let it near
the cell-and-guard PoC.**

But it may be the moment this stopped being a novelty and became something with a purpose.

**Decision (v0.5): formally into the long grass.** The open question below — *is the walking
reward a feature, or is it actually the product?* — is a **real strategic fork**, and it is
therefore deliberately **not answered yet**. Answering it now would change what is being built
before the cheaper, faster question (*does one room feel alive?*) has been answered at all.

> **It is scope, and scope is the enemy of the proof of concept.** Prove the room. Then decide
> what the room is for.

### Multi-agent NPCs — *the joy of meeting another mind*

**The advanced mode for characters.** Rather than one central AI voicing everyone, each
significant NPC becomes **its own independent AI agent**, handed a **markdown brief** — who you
are, what you want, what you know, the rules you must obey — and left to *act* as that character.

The guard's agent doesn't know the whole game. It knows it is a bored, cold guard who wants his
shift to end. **That is all it needs.**

**Why this is more than a technical nicety.** Humans are wired for the thrill of meeting another
mind. A genuinely responsive, unpredictable *other* is endlessly more compelling than a scripted
puppet. It is why a good conversation with a stranger lights you up.

> **It is catnip. The joy of meeting another mind.**

When each NPC is its own mind with its own agenda and secrets, **meeting one becomes an event.**
The player leans in, because there is genuinely someone there to *discover* — not a decision tree
to exhaust. And it directly answers the retention problem (§18): **people come back for people.**
A world populated by distinct, surprising minds is a world you want to return to.

It also unlocks real depth: the guard's agent can **withhold** things, because *his* mind knows
what the conversation doesn't share.

**Two hard cautions:**

1. **Compute.** Every character as its own AI instance multiplies cost and latency — fighting *directly* against the on-device, low-latency goal. This is **cloud-only, premium-tier** territory. Not the phone default.
2. **Coordination.** Independent agents will contradict each other and the world unless refereed strictly. **The engine remains the single source of truth. Agents only ever *propose*. The engine *disposes*.**

### Character identity — the unique key

The **markdown brief is a character's native language** — readable by the game engine *and* by an
external agent. And each character carries a **unique key**, guaranteeing there is only ever *one*
of them. No duplicates. Genuinely singular.

**This core is sound and worth building on its own merits**, with no blockchain anywhere near it:
unique key per character, no duplicates, portable state.

**On the NFT idea — an honest flag.** The collectible-character notion is charming: a beloved
companion, provably yours, like a one-of-a-kind playing card. But the blockchain wrapper is parked
as a **distant maybe**, for three reasons:

1. **Reputation.** NFTs carry heavy public baggage. For a wholesome, family-friendly product, that association could actively *repel* the audience rather than delight it.
2. **App-store friction.** Apple and Google have thorny rules around NFTs and crypto — complicating the very distribution you need.
3. **Focus.** It is a very long way from *"prove one room feels alive."*

**Keep the beautiful bit — unique keys, portable ownership. Park the wrapper.**

### 🌟 The character sheet — the emotional anchor

*You still have your original D&D character sheet from decades ago. That is not nostalgia — it is
evidence.*

Everything happened **to that character**. The sheet becomes a keepsake, a physical artefact of
all those adventures — strength, dexterity, and all the scrawled notes in the margins. **Most
digital games completely miss this.**

So make the character sheet a **first-class, ownable thing**: properly saved, and crucially
**exportable and importable**. The character is not trapped inside the app. It is *theirs*. Back it
up, carry it between devices, print it and stick it on the wall.

**And note:** this is the sensible, grounded version of the NFT idea. You get nearly all the
emotional payoff of *"this character is uniquely mine"* through something as simple and robust as an
export file. **The uniqueness lives in the sentiment, not the crypto.** No blockchain, no app-store
friction, no baggage.

It is also nearly free to build — the character is just another object (§4) with state that
serialises cleanly.

### The cloud tier — *"buy me a coffee"*

**Local-first, always.** Everything genuinely functional and complete for free, on the device. The
cloud is a **want**, never a **need**. The free tier must be genuinely good on its own — **not a
crippled demo nagging you to pay.**

The exportable character sheet becomes the **passport** into the cloud tier. Optional
enhancements, all hanging off that portable character:

- **Enhanced AI** — richer, cleverer responses (and the natural home for multi-agent NPCs, above).
- **Cloud auto-save.**
- **Sync across devices** — desktop, phone, tablet.

> **The "buy me a coffee" model.** Build something you're proud of, give it away freely, and the
> people who love it chip in because they *want* to support you — not because a feature was held
> hostage.

People smell a cynical paywall a mile off, *especially* in a family product. Generous developers
build loyal communities, and loyalty is worth more than squeezed pennies. It also keeps you honest:
the free tier has to be genuinely excellent — which is exactly the discipline that makes the whole
thing better anyway.

### Shared multiplayer — five people in a car

**Five people. One family. One car. One adventure. Each on their own phone, each with their own
character sheet.**

This is the natural home for the cloud, because now you genuinely *need* a server to coordinate
everyone's state in one consistent world. **The tier justifies itself rather than being justified
artificially.**

**Honest flag:** this is a **big architectural step up** — real-time coordination, everyone's actions
affecting one shared world, turn-taking between real people *and* the AI. It leans hard on the
"engine as single source of truth" principle. Powerful, but firmly a **later horizon**, well past
the cell and the guard.

Still — that family-in-a-car picture is a brilliant north star for where this could go.

---

## 24. Roadmap

**0. 🚦 THE SPIKE — go / no-go.** *(§0)* Quantised **Gemma 4 E2B** on a **real mid-range Android**.
CPU *and* GPU. Time-to-first-token. **Benchmark it hot.** Nothing else starts until this
returns an answer. It is cheap, it is quick, and it is the only thing that can kill the premise.

1. **Set up the desktop environment — in Python.** *(§11)* Get the pieces talking.
2. **Evaluate Evennia.** *(§11)* Half a day. Does borrowing its typeclass world model and LLM-NPC contrib save months — or drag in a MUD server you'll spend months removing? **Decide early; this choice is structural.**
3. **Build the object model.** *(§4)* The spine. Base class, state, relationships, capabilities, existence, position. Everything hangs off this — including the brief-builder.
4. **Build the smallest possible voice loop.** One cell, one guard. Google STT/TTS. Plain voice. **Prove the heartbeat** — you speak, it hears, the engine decides, it speaks back. A weekend, not a year.
5. **Port to a real mid-range phone.** Feel the true latency *in the real loop*, not the bare benchmark. The second reality check.
6. **Harden the state machine.** Continuity is non-negotiable. This is where the real work is.
7. **Build the maze.** Second test bed — proves the world model (direction, distance, time, breadcrumbs). See §9.
8. **Family beta.**
9. **Elaborate:** character voice, personality, economy, retention.
10. **Public beta.**
11. **Open the engine.**

> **Steps 0–4 are the whole gamble.** Everything from 5 onwards is craft. Get to a spoken guard
> line, on a real phone, as fast as humanly possible.

---

## 25. Monetisation

- **The game is free.** It is the flagship demo — and an *improving* demo, the living showroom where every engine upgrade lands first.
- **Local-first, genuinely complete.** The free tier is not a crippled demo. The cloud is a *want*, never a *need*. (§23)
- **"Buy me a coffee" tier.** Optional cloud extras — enhanced AI, auto-save, cross-device sync, and one day shared multiplayer. People chip in because they *want* to, not because a feature was held hostage.
- **The engine is the business.** License it via API to other developers building voice-driven, AI-narrated experiences.
- Selling shovels, not gold. The moat is the years of pain already suffered on the deterministic-engine-plus-AI-actor architecture.
- **Income is a bonus, not the driver.** This is built because it's worth building.

---

## Open questions

### Answered in v0.5

- [x] ~~React Native vs native Android for the prototype?~~ → **Neither. Prototype in Python on the desktop.** The shell is a Phase 2 problem. *(§11)*
- [x] ~~Is GPU acceleration essential?~~ → **No — and possibly harmful.** GPU is not reliably faster than CPU for small models on mobile. **Measure both.** *(§0)*
- [x] ~~Do we build the deterministic world model from scratch?~~ → **Probably not.** Evennia is a strong candidate; interactive fiction solved this decades ago. *(§11)*
- [x] ~~Is the walking reward in or out?~~ → **Out. Long grass, formally.** *(§23)*
- [x] ~~How does the parser know who's being addressed?~~ → **Wake words per voice, user-reassignable.** Explicit, no NLP. *(§12b, Gotcha #35)*
- [x] ~~How aggressively do sound layers duck under speech?~~ → **Speech always wins; ~200 ms crossfade back; music level user-optional.** *(§11b, Gotcha #36)*
- [x] ~~Interruption & mishearing recovery?~~ → **One shared "shall I repeat?" primitive.** Design done; Android mid-utterance stop still needs validating. *(#8, #9)*
- [x] ~~Empty input handling?~~ → **Nudge ladder: diegetic hint → "you there?" → warm timeout.** *(#10)*
- [x] ~~Repetition without sounding canned?~~ → **The world wears down — vary the line, then change state (the key bends).** *(#15)*

### Still open

- [ ] **Does the spike pass?** Short in-character reply, spoken, sub-second-ish first token, on a *warm* mid-range phone. **Everything hinges on this.** *(§0)*
- [ ] **Evennia: shortcut or trap?** Does borrowing the typeclass world model save months, or is the MUD server scaffolding a millstone? *(§11)*
- [ ] **Can Android halt TTS mid-utterance and switch to listening fast enough** for barge-in to feel natural? Spike-adjacent. *(#8, §20)*
- [ ] Time-to-first-token vs tokens/sec — which actually governs the felt latency in a spoken conversation? *(§0, §20)*
- [ ] Does Coqui TTS survive quantisation to phone-viable size with acceptable quality?
- [ ] Real measured latency of the *full loop* (STT → engine → LLM → TTS) on a mid-range Android device?
- [ ] Gemma 4 E4B vs E2B — is the extra footprint worth the coherence/context gain? *(model choice is provisional until the spike; §0)*
- [ ] **Is the harness itself the real product?** §1 now claims the pattern generalises beyond dungeons. If so, is the engine-as-agent-skill a bigger business than the game? *(§1, §25)*
- [ ] Where does the preloaded audio bank come from — commissioned, licensed, or synthesised once offline? *(§11b)*
- [ ] What exactly is the daily reason to return, beyond the cliffhanger?
- [ ] **What moves the guard's mood dial?** What actually wins him over — kindness, cleverness, a shared grievance, discovering his weakness? Needs sketching. *(§12)*
- [ ] How is barge-in handled technically on Android — can the DM stop mid-sentence and listen? *(Gotcha #8)*
- [ ] Tiered memory: what stays verbatim, what gets summarised, and who decides? *(Gotcha #6)*
- [ ] Profiles from day one, or retrofit later? Touches save architecture. *(Gotcha #25)*
- [ ] How is Authoring Mode actually driven — voice, text, or a desktop tool? *(§13)*
- [ ] **How granular does the world clock need to be?** Seconds, minutes, abstract "turns"? *(§5)*
- [ ] Does the player navigate by compass bearing, by landmark, or both? Audio-only argues for landmarks — but "go west" must still work. *(§5, §9)*
- [ ] Who authors the per-situation random event tables — you, or the frontier model during playtesting? *(§6, §14)*
- [ ] Where exactly is the line between authored set-piece and procedurally generated journey? *(§23)*
- [ ] Is the walking reward a *feature* of this app, or is it actually **the product**, with the dungeon as its costume? *(§23)*
- [ ] Can a multi-agent NPC ever run on-device, or is "another mind" *inherently* a cloud feature? *(§23)*
- [ ] What exactly is on the character sheet — and what format does it export to? *(§23)*
- [ ] Does shared multiplayer break the sparse-Yoda voice design? Five people talking at once is not a quiet campfire. *(§23, Gotcha #13)*
