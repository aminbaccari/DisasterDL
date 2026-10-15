# DisasterAI: project brief

## Course context
Advanced Deep Learning final project "AI Automation" (Esprit 5DS1, 2026-27). Team of 5-6. Graded on engineering choices and justification, not complexity. Teacher asks technical questions on: Transformers, LLMs, fine-tuning, RAG, multimodal models, agentic AI.

## Mandatory requirements
1. Automation platform (n8n): everything triggerable end-to-end, no manual cell-by-cell runs.
2. Prompt engineering (20%): versioned prompt library; per prompt: role, technique (few-shot, CoT, structured output, role, guardrails), observed failure cases, fixes, at least one before/after.
3. RAG (25%): own knowledge base; justify corpus, chunking (size, overlap), embedding model, vector store, retrieval (top-k, filters, reranking); small retrieval evaluation on test queries; comparing two chunking strategies is valued.
4. Multi-agent (25%): several agents; justify architecture, each agent's role/tools, information flow, and why alternatives would be worse.
5. Multimodality (15%): at least one non-text modality (we use images; PDFs with layout in RAG).
Demo/report/Q&A: 15%. Deliverables: workflow JSON + repo with run instructions, 8-page report, prompt library file, retrieval evaluation. Failures must be documented (they earn credit).

## Presentation outline (from the teacher)
1 Use case; 2 Architecture + n8n workflow end-to-end; 3 Prompt engineering (library, techniques, before/after, failures); 4 RAG (corpus, chunking, embeddings, vector store, retrieval eval, two-chunker comparison); 5 Multi-agent (design, tools, flow, justification); 6 Multimodality; 7 Live demo + evaluation + limitations + error handling; 8 Conclusion/future work. 15-20 min + 10 min Q&A, everyone speaks.

## Our system
Input: incident text (FR/AR/EN) + optional image -> n8n webhook ->
[Incident agent] extracts type, location, observations, missing info ->
parallel: [Vision agent] (if image) and [Knowledge/RAG agent] (query rewrite, filter by disaster type, retrieve with sources) ->
[Risk agent] potential risks, each with supporting evidence + source ->
[Verifier agent] checks every claim is supported by evidence ->
[Report agent] Markdown + JSON report, with a human-review notice.
Output is a preliminary AI-generated assessment, never an authoritative life-critical decision.

## Constraints
- Disaster types: fire, flood, structural. Languages: French, Arabic, English.
- Data: see docs/DATA.md (to be written) and data/sources.csv.