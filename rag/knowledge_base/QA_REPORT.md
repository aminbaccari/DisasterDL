# Quality and consistency report

Run on 2026-10-16 with qa_kb.py. Results below are the output of that run.

## Results

| Test | What it checks | Result |
|------|----------------|--------|
| T1 provenance | 388 verbatim anchor phrases are found on the cited PDF page (OCR for the 4 image-only pages) | pass |
| T2 numbers | 33 numbers in entry texts each appear within 500 characters of an anchor on the cited page | pass |
| T3 consistency | 14 topics checked across sources, see the table below | pass |
| T4 scope | no phone numbers, URLs or foreign-only institutions in the texts | pass |
| T5 self-contained | 20 to 160 words (mean 78.2), no references to other places | pass |
| T6 duplicates | no near-duplicate entries (TF-IDF cosine below 0.60 except declared overlaps) | pass |
| T7 coverage | every need on the checklist has at least one entry | pass |
| T9 structure | ids, fields, language, audience, declared team notes | pass |

## What T1 and T2 do not prove

They prove that quoted phrases and numbers exist on the cited page. They do not prove that a paraphrase means the same as the source. Meaning was checked by reading each entry against its page. Sentences written by the team are listed as team notes in the md files.

## T3 consistency across sources

Detection is automatic: a keyword group that appears in entries drawn from two or more sources must be reconciled by a dedicated entry or declared as an agreement.

| Topic | Entries | Sources | Status | Detail |
|-------|---------|---------|--------|--------|
| flood/vehicle | FL-04, FL-05, FL-14 | FALC, RC | reconciled | C1: Depth that sweeps a vehicle away: Red Cross 12 in (30 cm), French poster 'a few centimetres'. |
| flood/light | FL-10, FL-22 | FALC, P2055, RC | reconciled | C2: Candle: listed in the French 72 h kit, discouraged by the Red Cross (fire risk). |
| flood/utilities | FL-12, FL-17, FL-21, FL-22, FL-24 | FALC, P2055, RC | reconciled | C3: Cut gas and power (French poster) versus do not touch wet electrical equipment (Red Cross) versus leave on gas smell (FEMA P-2055). |
| flood/stay_go | FL-01, FL-02, FL-03, FL-07, FL-13, FL-17 | FALC, RC | reconciled | C4: Shelter upstairs and do not travel (French) versus move to higher ground and evacuate on advice (Red Cross). |
| flood/mold | FL-19, FL-20, FL-25, FL-26 | P2055, RC | agreement | Dry within 24 to 48 hours, mold likely after that (Red Cross and P-2055). |
| flood/co | FL-21 | P2055, RC | agreement | Carbon monoxide: Red Cross rules for appliances indoors, P-2055 adds a 20 ft generator distance. Complementary, no contradiction. |
| flood/contamination | FL-15, FL-16, FL-25 | P2055, RC | agreement | Floodwater is contaminated: Red Cross and P-2055 agree. |
| structural/cordon_distance | ST-07, ST-10, ST-22 | P2055, P2055-2 | reconciled | C5: Cordon distance: 1.5 x building height (P-2055, fire-service practice) versus height above hinge point (P-2055-2). |
| fire/smoke_shelter | FI-05 | P2055 | single source |  |
| fire/stay_go_fire | FI-05, FI-09, FI-10, FI-13, FI-14, FI-17, FI-24 | MTE, P2055, V1013 | reconciled | C11: Leave immediately when told (FEMA V-1013) versus shelter in a cleared house and not in a car until rescue (French ministry page) versus stay indoors in smoke (P-2055). |
| fire/smoke_protection | FI-09, FI-10, FI-16, FI-18, FI-21, FI-22, FI-25 | MTE, V1013 | reconciled | C12: Smoke protection: N95 mask (FEMA V-1013) versus damp cloth over nose and mouth (French ministry page). The sources do not compare them. |
| fire/defensible_space | FI-11, FI-14, FI-17, FI-24 | MTE, V1013 | agreement | Clear flammable material around the house: FEMA gives at least 30 feet, the French page requires clearing in risk zones and gives no distance. Complementary, no contradiction. |
| fire/return_after | FI-19, FI-20 | MTE, V1013 | agreement | After a fire, wait for the authorities before returning: FEMA, the French prefecture notice and the P-2055 evaluators agree. |
| fire/report_fire | FI-09, FI-12, FI-14 | MTE, ONPC, V1013 | agreement | Alert the emergency services: FEMA, the French page and the ONPC report agree. Numbers differ by country, only Tunisia's 198 (from the ONPC report) is kept. |

Differences found between sources, and how they are handled:

- C1: Depth that sweeps a vehicle away: Red Cross 12 in (30 cm), French poster 'a few centimetres'. Handled in FL-14.
- C2: Candle: listed in the French 72 h kit, discouraged by the Red Cross (fire risk). Handled in FL-22.
- C3: Cut gas and power (French poster) versus do not touch wet electrical equipment (Red Cross) versus leave on gas smell (FEMA P-2055). Handled in FL-12.
- C4: Shelter upstairs and do not travel (French) versus move to higher ground and evacuate on advice (Red Cross). Handled in FL-13.
- C5: Cordon distance: 1.5 x building height (P-2055, fire-service practice) versus height above hinge point (P-2055-2). Handled in ST-07.
- C10: Stay indoors during smoke (P-2055) must not be read as advice when flames approach. Handled in FI-05.
- C11: Leave immediately when told (FEMA V-1013) versus shelter in a cleared house and not in a car until rescue (French ministry page) versus stay indoors in smoke (P-2055). Handled in FI-13.
- C12: Smoke protection: N95 mask (FEMA V-1013) versus damp cloth over nose and mouth (French ministry page). The sources do not compare them. Handled in FI-18.

Agreements confirmed:

- mold: Dry within 24 to 48 hours, mold likely after that (Red Cross and P-2055).
- co: Carbon monoxide: Red Cross rules for appliances indoors, P-2055 adds a 20 ft generator distance. Complementary, no contradiction.
- contamination: Floodwater is contaminated: Red Cross and P-2055 agree.
- defensible_space: Clear flammable material around the house: FEMA gives at least 30 feet, the French page requires clearing in risk zones and gives no distance. Complementary, no contradiction.
- return_after: After a fire, wait for the authorities before returning: FEMA, the French prefecture notice and the P-2055 evaluators agree.
- report_fire: Alert the emergency services: FEMA, the French page and the ONPC report agree. Numbers differ by country, only Tunisia's 198 (from the ONPC report) is kept.

Rule used when sources differ: the entry keeps both positions with their source, states the stricter safety action, and says when the sources give no answer. Nothing is added that no source says.

## T8 retrieval proxy (lexical, not the embedding model)

56 natural queries (English and French, written after the entries), TF-IDF search inside the topic. hit@1 0.89, hit@3 0.98, hit@5 0.98, MRR 0.93.

This checks that each entry can be found by the words a person would use. It does not replace the embedding evaluation in rag/evaluate.py, and it cannot test cross-language retrieval. The queries were written by the same person who wrote the entries, so the score is optimistic.

| Query | Topic | Language | Expected | Top 3 | Rank |
|-------|-------|----------|----------|-------|------|
| can I drive through water on a flooded road | flood | en | FL-04, FL-14, FL-05 | FL-14, FL-04, FL-01 | 1 |
| how long can a house stay wet before mold starts | flood | en | FL-19 | FL-19, FL-20, FL-15 | 1 |
| is it safe to run a generator in the garage after the flood | flood | en | FL-21 | FL-21, FL-14, FL-23 | 1 |
| should I switch off the electricity when water gets into the house | flood | en | FL-12 | FL-12, FL-14, FL-25 | 1 |
| storm surge warning, when do we leave | flood | en | FL-03 | FL-03, FL-01, FL-02 | 1 |
| can we eat food that got wet or warm | flood | en | FL-16 | FL-16, FL-23, FL-19 | 1 |
| what protective gear for cleaning up flood damage | flood | en | FL-18 | FL-18, FL-01, FL-02 | 1 |
| water is rising fast and the roads are blocked, where should people go | flood | en | FL-13, FL-02, FL-03, FL-07 | FL-14, FL-13, FL-01 | 2 |
| floodwater moved chemicals and a propane tank into the yard | flood | en | FL-24 | FL-24, FL-15, FL-14 | 1 |
| when can I go back home after being evacuated | flood | en | FL-17 | FL-17, FL-01, FL-16 | 1 |
| feeling anxious after the flood | flood | en | FL-23 | FL-21, FL-16, FL-23 | 3 |
| candles or flashlight during the power cut | flood | en | FL-22 | FL-22, FL-12, FL-17 | 1 |
| is the tap water safe to drink after flooding | flood | en | FL-16 | FL-16, FL-14, FL-12 | 1 |
| que mettre dans le sac d'urgence pour trois jours | flood | fr | FL-10 | FL-10, FL-11, FL-05 | 1 |
| est-ce que je peux prendre ma voiture pendant l'inondation | flood | fr | FL-05 | FL-05, FL-06, FL-08 | 1 |
| faut-il descendre a la cave ou monter a l'etage | flood | fr | FL-07 | FL-07, FL-06, FL-26 | 1 |
| comment aider les voisins isoles ou ages | flood | fr | FL-09 | FL-09, FL-08, FL-05 | 1 |
| ou trouver l'information et qui ecouter pendant la crue | flood | fr | FL-08 | FL-08, FL-10, FL-05 | 1 |
| rester loin des berges et des ponts | flood | fr | FL-06 | FL-06, FL-08, FL-11 | 1 |
| quand verifier le contenu du kit et les piles | flood | fr | FL-11 | FL-11, FL-10, FL-08 | 1 |
| building partly collapsed and people may still be inside, should I go in | structural | en | ST-05, ST-17 | ST-17, ST-13, ST-09 | 1 |
| how far should the cordon be around a leaning building | structural | en | ST-07, ST-08, ST-10 | ST-01, ST-24, ST-07 | 3 |
| there is a smell of gas near the collapsed building | structural | en | ST-17 | ST-17, ST-18, ST-04 | 1 |
| what do the red, yellow and green signs on a damaged building mean | structural | en | ST-03 | ST-03, ST-20, ST-09 | 1 |
| do damaged buildings need to be checked again after an aftershock | structural | en | ST-14, ST-13, ST-15 | ST-14, ST-13, ST-15 | 1 |
| a chimney or parapet could fall onto the street | structural | en | ST-26, ST-04, ST-12 | ST-26, ST-12, ST-04 | 1 |
| damage to a building after a blast, broken windows | structural | en | ST-20 | ST-20, ST-04, ST-14 | 1 |
| who decides how big the safety zone should be | structural | en | ST-01 | ST-01, ST-24, ST-14 | 1 |
| spilled chemicals next to a damaged building | structural | en | ST-18 | ST-18, ST-03, ST-16 | 1 |
| how long does the safety perimeter stay in place | structural | en | ST-13, ST-22, ST-12 | ST-01, ST-13, ST-06 | 2 |
| the cause of the collapse is unknown, does the cordon guidance still apply | structural | en | ST-25 | ST-25, ST-06, ST-07 | 1 |
| an undamaged building beside a leaning one | structural | en | ST-16 | ST-16, ST-15, ST-07 | 1 |
| flames are near the first houses and the wind blows toward the village | fire | en | FI-01, FI-05, FI-13, FI-09 | FI-13, FI-04, FI-08 | 1 |
| wildfire smoke, should we stay indoors | fire | en | FI-05 | FI-05, FI-18, FI-13 | 1 |
| who suffers most from smoke and soot | fire | en | FI-04 | FI-04, FI-18, FI-05 | 1 |
| is it safe to go back into a house after the fire | fire | en | FI-03, FI-02 | FI-03, FI-13, FI-19 | 1 |
| mudslide danger in burned hills | fire | en | FI-08 | FI-08, FI-04, FI-06 | 1 |
| a fire started after the explosion | fire | en | FI-07 | FI-07, FI-03, FI-19 | 1 |
| a wildfire warning has been issued, what should we do right now | fire | en | FI-09, FI-13 | FI-09, FI-06, FI-01 | 1 |
| how far from the house should dry leaves and brush be cleared | fire | en | FI-11 | FI-13, FI-09, FI-18 | 6 |
| what to prepare before a wildfire evacuation | fire | en | FI-10 | FI-10, FI-22, FI-19 | 1 |
| is it safe to walk back onto burned land after the fire is out | fire | en | FI-19, FI-20 | FI-19, FI-06, FI-03 | 1 |
| should I shelter in my car if the fire reaches us | fire | en | FI-13, FI-14 | FI-13, FI-06, FI-01 | 1 |
| which mask or cloth for wildfire smoke | fire | en | FI-18, FI-09 | FI-18, FI-05, FI-10 | 1 |
| flames near the first houses of the village and the wind blows toward us | fire | en | FI-13, FI-09, FI-01 | FI-13, FI-04, FI-08 | 1 |
| que faire si je vois un début d'incendie | fire | fr | FI-14 | FI-14, FI-15, FI-12 | 1 |
| comment protéger ma maison avant l'arrivée du feu | fire | fr | FI-16, FI-17 | FI-16, FI-23, FI-17 | 1 |
| quels gestes pour éviter un départ de feu en forêt | fire | fr | FI-15, FI-12 | FI-15, FI-26, FI-17 | 1 |
| peut-on retourner sur les lieux après l'incendie | fire | fr | FI-20 | FI-20, FI-26, FI-14 | 1 |
| quel numéro appeler en Tunisie pour signaler un incendie | fire | fr | FI-12 | FI-21, FI-12, FI-14 | 2 |
| bouteilles en verre et mégots dans la forêt | fire | fr | FI-12, FI-15 | FI-12, FI-17, FI-15 | 1 |
| débroussailler autour de la maison est-ce obligatoire | fire | fr | FI-17 | FI-17, FI-23, FI-24 | 1 |
| la voiture est-elle un abri sûr pendant un feu | fire | fr | FI-14, FI-13, FI-24 | FI-14, FI-24, FI-20 | 1 |
| que faire en cas d'alerte feu de forêt | fire | fr | FI-21, FI-24, FI-14 | FI-21, FI-15, FI-24 | 1 |
| quel masque ou linge contre la fumée | fire | fr | FI-25, FI-16 | FI-25, FI-16, FI-23 | 1 |
| après l'incendie, quoi éviter sur le sol brûlé | fire | fr | FI-26, FI-20 | FI-26, FI-14, FI-20 | 1 |

## T7 coverage matrix (needs and the entries that serve them)

### flood

| Need | Entries |
|------|---------|
| before | FL-02, FL-10, FL-11 |
| during | FL-04, FL-05, FL-06, FL-07, FL-08, FL-09, FL-12, FL-13, FL-14, FL-26 |
| after | FL-15, FL-16, FL-17, FL-18, FL-19, FL-20, FL-21, FL-22, FL-23, FL-24, FL-25, FL-26 |
| evacuate | FL-02, FL-03, FL-13 |
| vehicle | FL-04, FL-05, FL-14 |
| power | FL-12, FL-21, FL-22 |
| gas | FL-12 |
| health | FL-15, FL-16, FL-18, FL-19, FL-20, FL-21 |
| mold | FL-19, FL-20 |
| kit | FL-10, FL-11 |
| shelter | FL-07, FL-13 |
| roads_blocked | FL-04, FL-05, FL-14 |
| rising_water | FL-13, FL-26 |
| vulnerable_people | FL-09 |
| electrocution | FL-12, FL-17 |
| cleanup | FL-15, FL-18, FL-19, FL-24 |
| basement | FL-05, FL-07 |
| children | FL-07 |

### structural

| Need | Entries |
|------|---------|
| cordon | ST-06, ST-07, ST-08, ST-09, ST-10, ST-11, ST-12, ST-13, ST-16, ST-22, ST-23, ST-24, ST-25 |
| distance | ST-07, ST-08, ST-09, ST-10, ST-11, ST-12 |
| collapse | ST-04, ST-07, ST-09, ST-10, ST-11, ST-15, ST-25 |
| trapped_people | ST-05, ST-17 |
| entry | ST-05, ST-17 |
| gas | ST-17 |
| placard | ST-03, ST-04, ST-16, ST-26 |
| aftershock | ST-06, ST-13, ST-14, ST-15, ST-21 |
| building_safety | ST-01, ST-02, ST-03, ST-04, ST-05, ST-14, ST-19, ST-20 |
| falling_hazard | ST-04, ST-12, ST-20, ST-26 |
| limits | ST-01, ST-22, ST-25 |
| explosion | ST-20, ST-21 |
| hazmat | ST-18, ST-19 |
| authority | ST-01 |
| adjacent_buildings | ST-16 |

### fire

| Need | Entries |
|------|---------|
| limits | FI-01 |
| flames_approaching | FI-01, FI-09, FI-13, FI-14, FI-21, FI-24 |
| smoke | FI-04, FI-05, FI-09, FI-16, FI-18, FI-21, FI-25 |
| shelter | FI-05, FI-13, FI-14, FI-24 |
| health | FI-04, FI-05, FI-18, FI-19, FI-25, FI-26 |
| after | FI-02, FI-03, FI-04, FI-08, FI-19, FI-20, FI-26 |
| building_safety | FI-02, FI-03, FI-06 |
| evacuate | FI-01, FI-09, FI-10, FI-13, FI-21, FI-22, FI-24 |
| prevention | FI-11, FI-12, FI-15, FI-17, FI-23 |
| defensible_space | FI-11, FI-17, FI-23 |
| home_protection | FI-11, FI-16, FI-17, FI-23 |
| reporting | FI-09, FI-10, FI-12, FI-14, FI-21, FI-22 |
| tunisia_context | FI-12 |
| return | FI-02, FI-03, FI-19, FI-20, FI-26 |

## Known gaps (not covered by the four sources)

- flood:
  - what to do if water reaches the upper floor or you are trapped (no source gives it)
  - Tunisian warning services and emergency numbers (no Tunisian source supplied)
  - after-flood advice is in English only (the French source has none)
- structural:
  - search and rescue and what bystanders should do for trapped people (sources only say do not enter an obviously unsafe building and call emergency personnel from outside)
  - cordon distance for a tall building whose damage point is unknown
  - no French-language structural source, and cordon material is written for earthquakes
- fire:
  - what to do when flames are approaching and you cannot leave (the sources say leave when told and shelter in a cleared house until rescue, and give no further steps)
  - no distance for the cleared zone in the French source, and Tunisian clearing rules are not covered
  - Tunisian guidance is one news report of an ONPC communique (prevention and reporting only, no evacuation or protection steps), the original ONPC document was not found
  - firefighting by residents is not covered by any source

## Content read but left out

| Where | What | Why |
|-------|------|-----|
| FALC p4-5 | Meteo-France vigilance and Vigicrues services, sites and app | French-only services, not usable in Tunisia |
| FALC p6 | Candle with matches or lighter in the kit list | Conflicts with the Red Cross advice, handled in FL-22 |
| FALC p3, p14-15 | Climate background and rainfall figures (more than 10 cm in 1 hour) | Background, not an action. Could support severity later |
| FALC p11-13 | Overseas site, risk-box game, witness video | Not guidance |
| RC p1 | FEMA Flood Map Service Center | US-only service |
| RC p2 | Disaster Distress Helpline number and Emergency App | US-only number and app, flagged in FL-23 |
| P-2055 ch. 2.3-2.6, 5, 6 (most), 7, 8 | Legislation, grants, certification, resource typing, mutual aid, data collection, quality assurance | Programme management in the United States, not useful to an incident assistant |
| P-2055 ch. 3.4-3.7, 3.11 | Land instability, volcanoes, hail, snow and ice, historic resources | Outside the three incident types |
| P-2055 ch. 4.4.6-4.4.11 | Asbestos, lead paint, parasites, animals, insects, debris | Possible later extension for flooded buildings |
| P-2055 p87-88 | US Coast Guard hotline number, NFPA diamond, IICRC category names | US-only identifiers |
| P-2055-2 ch. 2.3, 3.2 narratives, appendix A | Case histories and literature review behind the collapse modes | Evidence behind the tables, kept out to avoid repeating the table rules |
| P-2055-2 ch. 4 | Building-code authority, grants, cordon office funding, CERA organisation | US and New Zealand administration |
| V-1013 p1-2 | 9-1-1, Emergency Alert System, NOAA Weather Radio, FEMA app, Ready.gov | US-only numbers and services |
| V-1013 p1 | Cover facts (what a wildfire is, causes, flooding and transport problems afterwards) | Background, not an action |
| French ministry page | French emergency numbers, Météo des forêts, Géorisques, prefecture access rules, campaign video, partner list | French-only services and numbers, not usable in Tunisia |
| French ministry page | Statistics on French forest area | Background, not an action |
| allAfrica article | Heat context and the reproduction-rights notice | Not guidance. The article is paraphrased and quoted only in short phrases |
| FEMA P-2143 (2023) | The newer flyer was not obtained | The ready.gov copy carries the number V-1013 and the date May 2018, so V-1013 is cited |

## Do the tests catch mistakes?

qa_kb.py --selftest injects known faults into a copy of the entries. 14 of 14 were caught (2 could not run because they target OCR-only pages).

| Injected fault | Caught |
|----------------|--------|
| number changed (30 cm to 50 cm) | skipped (no OCR) |
| cordon factor changed (1.5 to 2.5) | yes |
| anchor cited on the wrong page | skipped (no OCR) |
| invented sentence cited as anchor | yes |
| emergency number injected | yes |
| url injected | yes |
| candle added to the kit entry | yes |
| reconciliation entry loses a source | yes |
| stay-indoors advice without the flames caveat | yes |
| duplicate entry added | yes |
| a required need removed (gas, structural) | yes |
| news report entry loses its La Presse attribution | yes |
| foreign emergency number 112 added to the Tunisian entry | yes |
| number changed in a French translation (30 to 50) | yes |
| translation points to a missing entry | yes |
| entry with a missing field | yes |

## Pages not re-verified in the latest run

This run had no OCR tools (tesseract, pdftoppm). Anchors, numbers and agreement numbers on these OCR-only pages were skipped: FALC p10, FALC p8, RC p1, RC p2. Their entries were not changed since the run of 2026-10-15, when all of them passed. Re-run on a machine with OCR to re-confirm.


## Iteration log

- First run: T1 failed on 2 anchors (both were misquoted, the source wording differed from what had been written), T5 flagged 5 entries (1 too short, 4 caused by a reference pattern that matched ordinary words such as 'above' and 'section loss'). The entries and the pattern were corrected.
- First retrieval proxy run: hit@1 0.76, hit@3 0.92, hit@5 0.97, MRR 0.85 on 38 queries. Misses came from a stemmer that did not match 'mudslide' with 'mudslides' (a flaw in the test tool) and from wording such as 'going back into a house'. The stemmer was fixed and one fire entry was reworded in plain language.
- Number check was first run against the whole page and missed a faked 2.5 because 'Section 2.5' is on the same page. It now looks only near the anchors, and the injected fault is caught.
- Fire sources added on 2026-10-16 (FEMA V-1013, French ministry page, La Presse report of an ONPC communique), entries FI-09 to FI-20. The first QA run on them failed T4 (the word Tunisian triggered the Tunisia disclaimer rule, now matched on the word Tunisia only), T5 (FI-12 had 172 words, shortened) and T3 (the report-the-fire group did not match the entries, regex corrected). Q33 was widened to accept FI-13 and FI-09, which now answer an approaching-flames question. Q40 stays a miss: FI-11 does not use the words clear or brush.
