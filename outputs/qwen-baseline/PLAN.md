# Qwen3-8B baseline implementation plan

Goal: deploy the official Q4_K_M model on this 8GB Windows laptop, verify answer quality and timing, then prepare the platform adapter and ngrok connection.

Architecture: local llama.cpp OpenAI-compatible server; platform launcher calls the endpoint and writes results by id. The initial server binds loopback only. Public access uses the user's existing ngrok setup after local verification.

Constraints: Qwen3-8B only; at most 16 requests in flight; under 60s total per call; preserve official run.py; UTF-8 result.json with id and list-valued 回答. Local context size is an experimental deployment setting, not a confirmed competition rule.

- [ ] Download official weights and GPU runtime, verify published SHA-256 hashes.
- [ ] Start GPU inference, disable thinking, verify actual GPU offload and token usage.
- [ ] Prepare platform adapter with hard request deadline, id alignment, atomic checkpointing and separate error logging; test with a mock endpoint.
- [ ] Build evidence-paired synthetic development cases with rule-derived answers; label these as synthetic, not independently audited official data.
- [ ] Run baseline and guarded prompts; record answers, correctness proxies, latency, errors and truncation. Inspect failures manually.
- [ ] Run long-input and concurrency probes; do not infer 16-GPU-slot capacity from the platform cap.
- [ ] Connect ngrok after checking the existing setup and any domain conflict. Log into platform and submit only using the user's account/session and authorized final artifact.

Review focus: queue time counts toward deadline; API errors must not count as valid abstention; answers may finish out of order; never silently truncate input; prior ngrok service must not be displaced.
