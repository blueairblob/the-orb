# Custom `.litertlm` export — closing the prefill-bucket-floor lever

The spike's remaining open question (`spike/results/2026-09-10-poco-m4-pro-litert-lm.md`) is
whether a custom re-export of Gemma 4 E2B with a smaller prefill bucket can shrink the ~1-2s
fixed-bucket floor that keeps both CPU and GPU over the ~1s TTFT pass mark. The litert-community
pre-converted model only has 128- and 1024-token prefill buckets; real incremental guard turns run
~17-20 tokens, so they pay the full 128-token bucket's compute regardless.

## Why this doesn't run on this host

`litert-torch` (the HF → `.litertlm` conversion tool) depends on `litert-converter`, which
publishes **no linux-aarch64 wheels at all**, stable or pre-release — confirmed via `uv pip
install --prerelease=allow litert-torch` here, which fails at the resolver stage. This OCI dev
host is aarch64. Same class of problem as the Android NDK cross-build
(`.github/workflows/litert-lm-android-build.yml`), same fix: run it on a free x86_64 GitHub
Actions runner instead.

## Where the actual export runs

`.github/workflows/gemma4-litertlm-export.yml` — `workflow_dispatch`, needs a repo secret
`HF_TOKEN` (a Hugging Face read-scope token from an account that's accepted the Gemma license at
https://huggingface.co/google/gemma-4-E2B-it):

```
gh secret set HF_TOKEN --repo blueairblob/the-orb
gh workflow run gemma4-litertlm-export.yml --repo blueairblob/the-orb
```

Default `--prefill_lengths=32,128,1024` — adds a 32-token bucket alongside the existing two.
Pull the resulting `.litertlm` from the workflow's artifact, sanity-check it actually generates
coherent text (a sibling Gemma export has a documented bug producing only pad tokens — see the
workflow file's comments), then push to the phone and re-run the same benchmark protocol used for
the pre-converted model for a direct comparison.

The `.venv/` in this directory is a dead end kept only as the record of the above — nothing in it
is usable on this host.
