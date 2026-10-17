# Bottlenecks and proposed fixes (2026-10-17)

Each item states the evidence (file or run), the effect, the proposed fix, an effort guess and what would prove the fix worked. Evidence is in `docs/EVIDENCE_LOG.md` unless another file is named. Effort is my estimate, not measured.

## Ranked list

| # | Bottleneck | Effect | Fix | Effort |
|---|-----------|--------|-----|--------|
| 1 | Free-tier quotas of every cloud provider | Real runs stop after a few dozen calls a day | Separate vision model, smaller prompts, a local text fallback, a token budget in `/llm/status`, a paid tier for the demo | 0.5 to 2 days |
| 2 | No vision-capable model with quota | The Vision step answered in only one logged run (the single image test run after the upload fix) | Dedicated vision chain with a local or HF-hosted VLM, see `docs/VISION_ARCHITECTURE.md`. Code done 2026-10-17 (`VISION_CHAIN`, ollama and hf providers); the model install and a benchmark are open | 1 to 2 days |
| 3 | Latency from waiting on rate limits | Runs of 100 to 1,558 s, model calls themselves take 0.4 to 7 s on Groq | Fewer and shorter calls, a local fallback, wait budget per run | 0.5 day |
| 4 | Untested prompt drafts (incident v2, report v4, knowledge v2, risk v2) | Quality claims impossible, two known failures open | Re-run `scripts/before_after.py` and `scripts/report_ab.py` with fresh quotas | 0.5 day of runs |
| 5 | Evaluation too small and too slow | 10 to 12 runs per batch, 3 matched pairs in the report test | Replay of recorded agent outputs, agent-level tests on fixed contexts, 2 providers per run | 1 day |
| 6 | Fire coverage is optimistic | Knowledge agent says `good` for fire_01 although FI-01 says nothing covers flames reaching a house | `/validate` coverage check or knowledge prompt v3, more fire sources | 0.5 day |
| 7 | Retrieval gaps | Structural query v13 missed ST-05 in the top 5, French queries pulled to French fire entries | More French entries, rerank by language, try `multilingual-e5-large` (already in the local cache) | 1 day |
| 8 | Guardrails are regular expressions | One false positive found (markdown emphasis), repair reasons not logged | Log the first attempt, add cases from real outputs, keep it narrow | 0.5 day |
| 9 | Fragile environment | TLS errors in Python, TF/Keras import crash, port 8000 taken, Docker engine stopped once, cooldown state lost on restart | Start script, pinned requirements, persisted cooldowns | 0.5 day |
| 10 | Open items owned by people | Unreviewed French translations, OCR-only flood pages not re-verified, stand-in test images, `rag/corpus/README.md` deleted | Assign owners (`docs/NEXT_STEPS.md`) | small |

## Details

### 1. Free-tier quotas
- **Evidence:** on 2026-10-16 Gemini 3.5 and 3.6 flash hit the daily quota, gemini-3.8-flash answered 503 on 10 of 11 pings and 3.7-flash on 3 of 3, OpenRouter free models hit about 50 requests a day, Groq `gpt-oss-120b` and `gpt-oss-20b` hit daily limits, `qwen3.8-27b` allowed about one 5,000-token call a minute. Batch B had 6 runs lost in 0.1 to 1.1 s. The before and after pipeline test stopped after 8 of 36 runs.
- **Fixes:**
  1. Take the Vision calls out of the shared chain (item 2). It removes the only calls that need rare vision models.
  2. Cut tokens. A pipeline run is about 7 calls with long inputs. The report prompt is about 5,500 characters, v4 adds a format example and was rate-limited on 7 of 12 calls against 4 of 13 for v3. Send the Report agent only the fields it uses and shorten passages to the cited sentences.
  3. Add a local text model as the last link (Ollama or llama.cpp, a 4B to 8B model) so a run never ends with every model cooling down. Quality would be lower, the report would say which model answered.
  4. Keep a daily token counter per model in `/llm/status` so the team sees the budget before a long test.
  5. For the demo, a paid tier of one provider. A few cents a run at these sizes, to be checked against the provider's prices on the day.
- **Proof:** a full six-incident, two-run batch finishing without a `quota_failure` row in `before_after.py analyse`.

### 2. Vision
See `docs/VISION_ARCHITECTURE.md`. Short version: a separate `VISION_CHAIN` (task `vision` in `/llm`), local VLM first, hosted VLM second, current chain last.

### 3. Latency
- **Evidence:** batch C runs 1.6 to 431 s, the before and after BEFORE/fire_01 run 1,558 s. Per step on Groq 0.4 to 7 s.
- **Fixes:** fewer waits through items 1 and 2, a per-run wait budget (for example 120 s, then fall to the local model), `MAX_WAIT` 90 s stays. Run the two branches (vision and RAG) truly in parallel: they are already parallel in n8n, but both draw on the same quota.
- **Proof:** median run under 60 s on a day with quota.

### 4. Untested drafts
- Incident v2 (location, language), report v4 (all fields, image_status), knowledge v2, risk v2 were written from real failures. Partial evidence only: location generic in 2 of 2 BEFORE runs against 0 of 3 AFTER, report v4 passed `/validate` 5 of 5 against 2 of 9 for v3 (confounded by image_status).
- **Fix:** the re-run list in `docs/NEXT_STEPS.md`. Decide a stopping rule before the run (for example at least 18 pairs, same pinned model).

### 5. Evaluation throughput
- **Fixes:** record every agent output of a good run as a fixture and replay downstream agents from it, so a prompt change costs one agent call, not seven. `scripts/report_ab.py` already works this way for the report agent. Add the same for incident, knowledge and risk. Score manual checks from saved files with `scripts/show_run.py`.

### 6. Fire coverage
- **Evidence:** fire_01 runs 1 and 2 of batch A, `knowledge_coverage: good`.
- **Fixes:** (a) in `/validate`, if FI-01 is among the retrieved entries and the incident mentions flames near buildings, coverage `good` is flagged. (b) knowledge prompt v3: coverage cannot be `good` when FI-01 is retrieved. (c) more sources on flames reaching a house (`docs/RAG_CORPUS_PLAN.md`).

### 7. Retrieval
- **Evidence:** `rag/eval/results_queries_v2_*`, misses v08, v12, v13, v16.
- **Fixes:** try `intfloat/multilingual-e5-large` (in the local cache, 560M parameters, slower on CPU), add French versions of key flood and structural entries as done for fire (FI-21 to FI-26), rerank so that one result per language is kept, write a third blind query set.

### 8. Guardrails
- **Fixes:** return the first attempt's violations (`validation.first_violations`) so the repair reason is visible, add every false positive and miss found in real outputs to `backend/tests/test_validate.py`. Do not add rules without a failing real example.

### 9. Environment
- **Fixes:** a `scripts/start_services.ps1` that sets `HF_HUB_OFFLINE`, `USE_TF=0` and `TRANSFORMERS_NO_TF=1` and starts the RAG service on 8010. Remove TensorFlow from the environment or install `tf-keras`. Keep `truststore` in requirements. Write cooldown state to a small file so a restart does not forget daily quotas.

### 10. Open items
- French translations FI-21 to FI-26 need a French reader. `qa_kb.py` needs a machine with tesseract to re-verify four flood pages. The test images are stand-ins (not the incidents' places). `rag/corpus/README.md` is deleted and uncommitted.
