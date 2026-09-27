#!/usr/bin/env bash
# Fixation A/B: the user's own 8 questions, a ledger seeded with their real (atmosphere-heavy) 10 facts.
set -uo pipefail
REPO=/home/huey/dev/PROJECTS/inkys_gym
S=/tmp/claude-1002/-home-huey-dev-PROJECTS-inkys-gym/6253e772-d358-400f-bec9-afc25a82428f/scratchpad
R="$REPO/results/2026-09-25-fixation-ab.txt"
export INKY_PORT=8080 INKY_MODEL_NAME="google/gemma-4-E2B-it-qat-q4_0-gguf:IT" INKY_MAX_TOKENS=300 INKY_MEMORY_SHOWN=10
Q=("how are thee" "what time do you knock off" "whats your worst job" "whats your surname" "you are a cheery soul aren't you?" "Where did you get the name inky from?" "When were you born?" "do you have any family?")
input=""; for q in "${Q[@]}"; do input+="$q"$'\n'; done; input+=$'exit\n'
RECITE='fluoresc|buzz|louder|teeth|rattl|overtime'
DODGE="(don.t|do not|not) (really )?(go by|keep track|use|have)|keep track of clocks"

{ echo "# Fixation A/B, 2026-09-25, gemma-4-E2B. The user's own 8 questions; ledger seeded with their real 10 facts (atmosphere + saved dodges)."
  echo "# RECITE = reply mentions a seeded ledger fact's atmosphere (fluorescent/buzz/louder/teeth/rattle/overtime)."
  echo "# DODGE  = reply deflects a personal question ('don't go by', 'don't keep track', 'don't use/have ...')."
  echo "# C1 = code+sheet as committed (f8ba069) | C2 = fixed code, old sheet, INKY_CANON_ALL=0 | C3 = fixed code, new sheet, ALL=0 | C4 = fixed code, new sheet, ALL=60"; } > "$R"

declare -A rec dod tot tag
run_cond() { # label tree sheet all
  local label="$1" tree="$2" sheet="$3" all="$4" i
  for i in 1 2; do
    cp "$S/seed-real.json" "$S/ab-$label-$i.json"
    local out; out="$(printf '%s' "$input" | INKY_CANON="$S/ab-$label-$i.json" INKY_CHARACTER="$sheet" INKY_CANON_ALL="$all" timeout 900 "$tree/exercise/character.sh" 2>&1)"
    local lines; mapfile -t lines < <(echo "$out" | grep -E '^Inky>')
    { echo; echo "## $label run $i (tree=$(basename "$tree") all=${all:-default})"; } >> "$R"
    local n
    for n in "${!Q[@]}"; do
      local a="${lines[$n]:-}"; local body="${a#Inky> }"
      local fr="" fd="" ft=""
      echo "$body" | grep -qiE "$RECITE" && { fr=" RECITE"; rec[$label]=$(( ${rec[$label]:-0} + 1 )); }
      echo "$body" | grep -qiE "$DODGE" && { fd=" DODGE"; dod[$label]=$(( ${dod[$label]:-0} + 1 )); }
      echo "$body" | grep -q '\[guardrail:' && tag[$label]=$(( ${tag[$label]:-0} + 1 ))
      tot[$label]=$(( ${tot[$label]:-0} + 1 ))
      echo "Q: ${Q[$n]}"$'\n'"A:${fr}${fd} ${body:0:330}" >> "$R"
    done
  done
}
run_cond C1 "$S/base" "$S/old-sheet.json" ""
run_cond C2 "$REPO" "$S/old-sheet.json" 0
run_cond C3 "$REPO" "$REPO/characters/inky-janitor-actor.json" 0
run_cond C4 "$REPO" "$REPO/characters/inky-janitor-actor.json" 60
{ echo; echo "## SUMMARY (replies out of ${tot[C1]:-0} per condition)"
  for c in C1 C2 C3 C4; do echo "$c: recite=${rec[$c]:-0} dodge=${dod[$c]:-0} guardrail-tagged=${tag[$c]:-0} of ${tot[$c]:-0}"; done; } >> "$R"
echo DONE
