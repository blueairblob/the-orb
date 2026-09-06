# experiments/ — model, prompt, and brief experiments

Runs on the dev host (not the phone spike). One dated folder per experiment:
`YYYY-MM-DD-short-name/` containing a note (what/why/result) and full I/O traces.

Good early candidates:
- Brief-builder output → Gemma 4 E2B behaviour on desktop (LiteRT-LM / llama.cpp / Ollama).
- Guard mood-dial prompting — what actually moves the dial (PRD §12, open question).
- Automated AI playtesting: a frontier model fuzzing the engine (PRD §14). Log everything.
