# RAG corpus plan (draft v1, 2026-10-15)

Goal: a small, traceable corpus of about 8 to 12 documents in English and French, covering forest fires, floods and structural emergencies, plus general evacuation and safety. Quality and traceability matter more than volume. Every chunk keeps its source file name and page so the report can cite it.

Status column meaning:
- opened: the content was opened and checked during planning
- lead: found by search only, content not yet opened. Do not use until a team member opens it and confirms it fits.

## Candidate documents

| # | Topic | Language | Source and document | Status | Notes |
|---|-------|----------|---------------------|--------|-------|
| 1 | Forest fire | FR | ONPC (Tunisian civil protection) fire prevention recommendations, reported by La Presse on 9 July 2026 | opened (news article) | Tunisian context, emergency number 198. It is a news report, so look for the official ONPC page and prefer that. |
| 2 | Forest fire | EN | FEMA P-2143, Be Prepared for a Wildfire (Aug 2023) | opened | One-page flyer, thin but clean. No license text stated in the copy opened. |
| 3 | Forest fire | EN | Ready.gov wildfire page or full FEMA wildfire guide | lead | Download from ready.gov directly, not from a county mirror. |
| 4 | Forest fire | FR | French government "feux de forêt" guidance (georisques.gouv.fr or interieur.gouv.fr) | lead | Must confirm an official, citable document exists. |
| 5 | Flood | EN | FEMA or Ready.gov flood hazard information sheet | lead | Several mirrors found. Use the original from fema.gov or ready.gov. |
| 6 | Flood | EN | Red Cross flood safety checklist | lead | Use the Red Cross original, not a mirror. |
| 7 | Flood | FR | French government "inondation, que faire" guidance | lead | Same check as item 4. |
| 8 | Structural | EN | FEMA P-2055-2, Recommendations for Cordoning Earthquake-Damaged Buildings | opened | About 50 pages of engineering content. Date check needed: the copy opened says September 2023, the file name says 042025. Confirm on fema.gov. Possibly use selected sections only. |
| 9 | Structural | EN | ATC-20 style post-earthquake building safety evaluation (inspected, restricted, unsafe placards) | lead | Check which document is freely available and short enough. |
| 10 | Structural or general | FR | French guidance for earthquakes or building damage | lead | Needed so the structural category is not English only. |
| 11 | Evacuation and general | EN or FR | One evacuation and emergency kit guide | lead | Keep to one document. |

Gaps to resolve honestly: Arabic is out of scope for v1. Tunisian official flood guidance was not found in this round, so floods are covered by international sources unless the team finds an ONPC flood document.

## Selection rules

1. Official or recognised organisations only (civil protection, FEMA, Red Cross, government ministries).
2. Each document opened and skimmed by a team member before it enters rag/corpus/.
3. Record title, publisher, date, URL, language and licence note in rag/corpus/SOURCES.md.
4. No news articles as the main corpus. Use them only for Tunisian context when no official page exists.
5. Check reuse terms per document. For a course prototype we cite sources and do not redistribute the corpus.

## Chunking experiment design (for section 4 of the presentation)

Compare two strategies on the same corpus and the same test queries:
- Strategy A: fixed size, 300 words (roughly 400 to 500 tokens) with 40 words overlap.
- Strategy B: section or heading based, with a 300 word cap, very short sections merged, and the section title kept in each chunk.
- Chunks never cross page boundaries, so every chunk has an exact page number for citation.
- Sizes are counted in words, not model tokens. State this in the report.

Embedding: multilingual-e5. This model expects the prefix "query: " on queries and "passage: " on chunks. Forgetting the prefixes is a known cause of weak retrieval, so keep it in the code.

Test set:
- 15 to 20 queries, about half English and half French, spread across the three disaster types.
- For each query, a team member writes the expected source document and the passage that answers it, before running anything.
- Include 2 or 3 queries that mix languages (French query, English document) to test cross-language retrieval.

Metrics, reported at k = 1, 3 and 5:
- Hit rate: the expected passage appears in the top k chunks.
- Mean reciprocal rank, if time allows.

Log every run in docs/EVIDENCE_LOG.md with the date, strategy, k and the counts. Report only what was run.
