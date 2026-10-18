# Retrieval evaluation (2026-10-17 20:39)

- Test set: 36 queries (30 positive, 6 out-of-scope)
- Labels: keyword page labels + 278 pooled LLM-panel judgments (evaluation/judging/agreement.md)
- Embedding model: `intfloat/multilingual-e5-base`; chunk size 400, overlap 60; per-query results in `retrieval_20261017_2039_strict.csv`

## Overall (positive queries)

| config | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 | Source P@5 |
|---|---|---|---|---|---|---|
| fixed | 0.733 | 0.833 | 0.933 | 0.933 | 0.803 | 0.847 |
| fixed+filter | 0.733 | 0.833 | 0.933 | 0.933 | 0.803 | 0.873 |
| structure | 0.667 | 0.900 | 0.900 | 0.933 | 0.781 | 0.860 |
| structure+filter | 0.667 | 0.900 | 0.900 | 0.933 | 0.781 | 0.887 |
| structure-noheader+filter | 0.733 | 0.900 | 0.900 | 0.967 | 0.813 | 0.847 |
| structure+filter[e5-small] | 0.533 | 0.767 | 0.800 | 0.867 | 0.662 | 0.847 |
| fixed+filter+cap2 | 0.733 | 0.867 | 0.933 | 0.967 | 0.809 | 0.764 |
| structure+filter+cap2 | 0.667 | 0.933 | 0.967 | 0.967 | 0.796 | 0.816 |
| structure+filter+rerank | 0.800 | 0.900 | 0.933 | 1.000 | 0.868 | 0.887 |
| structure+filter+rerank+cap2 | 0.800 | 0.900 | 0.900 | 0.900 | 0.850 | 0.809 |
| fixed+filter+rw3 | 0.533 | 0.667 | 0.800 | 0.933 | 0.641 | 0.733 |
| structure+filter+rw3 | 0.567 | 0.733 | 0.800 | 0.867 | 0.669 | 0.780 |
| structure+filter+fusion3 | 0.767 | 0.900 | 0.933 | 0.967 | 0.835 | 0.833 |
| structure+filter+fusion3+cap2 | 0.767 | 0.933 | 0.933 | 0.933 | 0.833 | 0.762 |
| structure+filter+fusion3+rerank | 0.733 | 0.933 | 0.967 | 1.000 | 0.842 | 0.893 |

## Hit@5 / MRR@10 by disaster_type

| config | fire | flood | structural |
|---|---|---|---|
| fixed | 1.000 / 0.841 (n=11) | 0.900 / 0.825 (n=10) | 0.889 / 0.731 (n=9) |
| fixed+filter | 1.000 / 0.841 (n=11) | 0.900 / 0.825 (n=10) | 0.889 / 0.731 (n=9) |
| structure | 0.909 / 0.828 (n=11) | 0.900 / 0.800 (n=10) | 0.889 / 0.704 (n=9) |
| structure+filter | 0.909 / 0.828 (n=11) | 0.900 / 0.800 (n=10) | 0.889 / 0.704 (n=9) |
| structure-noheader+filter | 0.909 / 0.813 (n=11) | 0.900 / 0.843 (n=10) | 0.889 / 0.778 (n=9) |
| structure+filter[e5-small] | 0.727 / 0.646 (n=11) | 0.800 / 0.667 (n=10) | 0.889 / 0.676 (n=9) |
| fixed+filter+cap2 | 1.000 / 0.848 (n=11) | 0.900 / 0.837 (n=10) | 0.889 / 0.731 (n=9) |
| structure+filter+cap2 | 0.909 / 0.818 (n=11) | 1.000 / 0.820 (n=10) | 1.000 / 0.741 (n=9) |
| structure+filter+rerank | 0.818 / 0.799 (n=11) | 1.000 / 0.875 (n=10) | 1.000 / 0.944 (n=9) |
| structure+filter+rerank+cap2 | 0.818 / 0.773 (n=11) | 0.900 / 0.850 (n=10) | 1.000 / 0.944 (n=9) |
| fixed+filter+rw3 | 0.636 / 0.624 (n=11) | 0.800 / 0.603 (n=10) | 1.000 / 0.704 (n=9) |
| structure+filter+rw3 | 0.818 / 0.628 (n=11) | 0.700 / 0.667 (n=10) | 0.889 / 0.722 (n=9) |
| structure+filter+fusion3 | 0.909 / 0.877 (n=11) | 1.000 / 0.792 (n=10) | 0.889 / 0.833 (n=9) |
| structure+filter+fusion3+cap2 | 0.909 / 0.864 (n=11) | 1.000 / 0.800 (n=10) | 0.889 / 0.833 (n=9) |
| structure+filter+fusion3+rerank | 0.909 / 0.773 (n=11) | 1.000 / 0.825 (n=10) | 1.000 / 0.944 (n=9) |

## Hit@5 / MRR@10 by language

| config | en | fr |
|---|---|---|
| fixed | 0.955 / 0.811 (n=22) | 0.875 / 0.781 (n=8) |
| fixed+filter | 0.955 / 0.811 (n=22) | 0.875 / 0.781 (n=8) |
| structure | 0.955 / 0.811 (n=22) | 0.750 / 0.701 (n=8) |
| structure+filter | 0.955 / 0.811 (n=22) | 0.750 / 0.701 (n=8) |
| structure-noheader+filter | 0.955 / 0.830 (n=22) | 0.750 / 0.764 (n=8) |
| structure+filter[e5-small] | 0.864 / 0.739 (n=22) | 0.625 / 0.451 (n=8) |
| fixed+filter+cap2 | 0.955 / 0.816 (n=22) | 0.875 / 0.792 (n=8) |
| structure+filter+cap2 | 1.000 / 0.820 (n=22) | 0.875 / 0.729 (n=8) |
| structure+filter+rerank | 0.955 / 0.859 (n=22) | 0.875 / 0.893 (n=8) |
| structure+filter+rerank+cap2 | 0.909 / 0.841 (n=22) | 0.875 / 0.875 (n=8) |
| fixed+filter+rw3 | 0.864 / 0.709 (n=22) | 0.625 / 0.453 (n=8) |
| structure+filter+rw3 | 0.818 / 0.703 (n=22) | 0.750 / 0.577 (n=8) |
| structure+filter+fusion3 | 0.909 / 0.798 (n=22) | 1.000 / 0.938 (n=8) |
| structure+filter+fusion3+cap2 | 0.909 / 0.795 (n=22) | 1.000 / 0.938 (n=8) |
| structure+filter+fusion3+rerank | 1.000 / 0.875 (n=22) | 0.875 / 0.750 (n=8) |

## Hit@5 / MRR@10 by style

| config | question | report |
|---|---|---|
| fixed | 0.955 / 0.898 (n=22) | 0.875 / 0.542 (n=8) |
| fixed+filter | 0.955 / 0.898 (n=22) | 0.875 / 0.542 (n=8) |
| structure | 0.955 / 0.856 (n=22) | 0.750 / 0.576 (n=8) |
| structure+filter | 0.955 / 0.856 (n=22) | 0.750 / 0.576 (n=8) |
| structure-noheader+filter | 0.955 / 0.848 (n=22) | 0.750 / 0.714 (n=8) |
| structure+filter[e5-small] | 0.909 / 0.766 (n=22) | 0.500 / 0.375 (n=8) |
| fixed+filter+cap2 | 0.955 / 0.898 (n=22) | 0.875 / 0.567 (n=8) |
| structure+filter+cap2 | 1.000 / 0.871 (n=22) | 0.875 / 0.588 (n=8) |
| structure+filter+rerank | 1.000 / 0.920 (n=22) | 0.750 / 0.723 (n=8) |
| structure+filter+rerank+cap2 | 0.955 / 0.909 (n=22) | 0.750 / 0.688 (n=8) |
| fixed+filter+rw3 | 0.818 / 0.625 (n=22) | 0.750 / 0.683 (n=8) |
| structure+filter+rw3 | 0.818 / 0.687 (n=22) | 0.750 / 0.620 (n=8) |
| structure+filter+fusion3 | 0.955 / 0.902 (n=22) | 0.875 / 0.653 (n=8) |
| structure+filter+fusion3+cap2 | 0.955 / 0.902 (n=22) | 0.875 / 0.646 (n=8) |
| structure+filter+fusion3+rerank | 1.000 / 0.890 (n=22) | 0.875 / 0.708 (n=8) |

## Head-to-head: structure+filter vs fixed+filter (reciprocal rank per query)

structure better on 5 queries, worse on 5, tied on 20.

## Threshold calibration (best config by MRR: `structure+filter+rerank`)

- Score of the first relevant chunk (positives): min 0.758, median 0.857, max 0.894
- Top-1 score on out-of-scope queries: min 0.742, median 0.777, max 0.827

| threshold | positives kept (hit@5) | negatives rejected | balanced |
|---|---|---|---|
| 0.780 | 0.929 | 0.667 | 0.798 |
| 0.785 | 0.857 | 0.833 | 0.845 |
| 0.790 | 0.857 | 0.833 | 0.845 |
| 0.795 | 0.821 | 0.833 | 0.827 |
| 0.800 | 0.821 | 0.833 | 0.827 |
| 0.805 | 0.821 | 0.833 | 0.827 |
| 0.810 | 0.786 | 0.833 | 0.810 |
| 0.815 | 0.786 | 0.833 | 0.810 |
| 0.820 | 0.750 | 0.833 | 0.792 |
| 0.825 | 0.750 | 0.833 | 0.792 |
| 0.830 | 0.714 | 1.000 | 0.857 |
| 0.835 | 0.714 | 1.000 | 0.857 |
| 0.840 | 0.643 | 1.000 | 0.821 |
| 0.845 | 0.607 | 1.000 | 0.804 |
| 0.850 | 0.607 | 1.000 | 0.804 |
| 0.855 | 0.607 | 1.000 | 0.804 |
| 0.860 | 0.500 | 1.000 | 0.750 |
| 0.865 | 0.393 | 1.000 | 0.696 |
| 0.870 | 0.286 | 1.000 | 0.643 |
| 0.875 | 0.179 | 1.000 | 0.589 |
| 0.880 | 0.179 | 1.000 | 0.589 |
| 0.885 | 0.107 | 1.000 | 0.554 |
| 0.890 | 0.036 | 1.000 | 0.518 |
| 0.895 | 0.000 | 1.000 | 0.500 |
| 0.900 | 0.000 | 1.000 | 0.500 |

Best balanced threshold: **0.830** (keeps 71% of positive hits, rejects 100% of out-of-scope queries).

## Failed queries (no relevant chunk in top 5, `structure+filter+rerank`)

- **FIRE-Q02** (en, fire): Smoke from a nearby forest fire is filling our neighbourhood and my elderly father has asthma.
  - expected: FIRE-02, GEN-02; first relevant rank: 7
  - got 0.780 FIRE-02 p.10 [OUTDOORS]: 'America’s PrepareAthon! www.ready.gov/prepare\n- - Use caution when entering burned areas. Hazards may still exist, inclu'
  - got 0.781 FIRE-02 p.2 [IMPACT]: 'A wildfire is an unplanned, unwanted fire burning in a natural area, such as a forest, grassland, or prairie. As buildin'
  - got 0.776 FIRE-04 p.54 [mmaire > LA PRÉVENTION DES FEUX DE VÉGÉTATION > LES RISQUES]: 'Les acteurs de prévention ne sont pas censés prendre de risques physiques sur un incendie de végétation. Il est toutefoi'
- **FIRE-Q05** (fr, fire): Un incendie de végétation s'est déclaré près des maisons, le vent pousse les flammes vers le village.
  - expected: FIRE-02, FIRE-04, GEN-02; first relevant rank: 7
  - got 0.816 FIRE-04 p.26 [ VÉGÉTATION EN NOUVELLE-CALÉDONIE > LES MODES DE PROPAGATION]: 'Le vent agit de plusieurs manières : il apporte de l’oxygène, activant ainsi la combustion, il rabat les flammes sur la '
  - got 0.817 FIRE-04 p.28 [ VÉGÉTATION EN NOUVELLE-CALÉDONIE > LES FEUX EN TERRAIN PLAT]: 'Sans vent : les feux prennent une forme vaguement circulaire en générant un courant centripète (mouvement circulaire qui'
  - got 0.813 FIRE-04 p.17 [EN NOUVELLE-CALÉDONIE > L’INCENDIE DE FORÊT EN QUELQUES MOTS]: 'Une partie de l’eau contenue dans les tissus des plantes (le combustible) est évaporée en période de forte chaleur et de'

## Rewritten queries (prompt rag_query_rewrite v3)

| query | original | rewritten |
|---|---|---|
| FIRE-Q01 | What should I do if a wildfire is approaching and authorities order an evacuation? | wildfire evacuation procedures, immediate actions during wildfire threat and official orders |
| FIRE-Q02 | Smoke from a nearby forest fire is filling our neighbourhood and my elderly father has asthma. | wildfire smoke impacting vulnerable populations with respiratory issues, assessing air quality and public health response |
| FIRE-Q03 | How can homeowners create defensible space around their house to protect it from wildfire? | wildfire risk mitigation, establishing defensible space around residential properties for fire protection |
| FIRE-Q04 | Quelles sont les consignes de sécurité si un feu de forêt menace mon habitation ? | wildfire threat to residential areas, implementing pre-fire safety measures and evacuation protocols |
| FIRE-Q05 | Un incendie de végétation s'est déclaré près des maisons, le vent pousse les flammes vers le village. | wildfire spreading towards a populated village with wind-driven flames, immediate evacuation order |
| FIRE-Q06 | What are the principles of fire prevention and early warning in national fire management? | preventing and detecting wildfires, implementing early warning systems in national fire management protocols |
| FIRE-Q07 | How do I use a fire extinguisher safely to put out a small fire? | safe operation of a portable fire extinguisher on a contained small fire incident |
| FIRE-Q08 | A burn scar from last month's wildfire lies above our town and heavy rain is forecast for tonight. | post-wildfire burn scar area experiencing heavy rainfall, potential for debris flow and flooding hazards |
| FIRE-Q09 | What precautions should we take when returning home after a wildfire? | post-wildfire home reentry safety, assessing structural damage and hazardous materials after a fire |
| FLOOD-Q01 | Is it safe to walk or drive through floodwater? | floodwater inundation, assessing risk of driving or walking through submerged roadways and structures |
| FLOOD-Q02 | Heavy flooding in Nabeul, several roads are blocked and water is entering ground-floor homes. | severe flooding blocking roadways and inundating ground-floor residential properties in a coastal area |
| FLOOD-Q03 | What health risks follow a flood such as contaminated water or infectious diseases? | floodwater contamination risks: assessing public health hazards and infectious disease potential |
| FLOOD-Q04 | Why is carbon monoxide poisoning a risk after a flood? | floodwater contamination causing carbon monoxide hazards, assessing indoor air quality and ventilation |
| FLOOD-Q05 | Les autorités annoncent une crue dans quelques heures, comment se préparer ? | imminent river flood warning, preparing for evacuation and protecting property from rising water levels |
| FLOOD-Q06 | L'eau est entrée dans notre sous-sol et l'électricité est toujours branchée. | flooded basement with active electrical hazard, immediate power disconnection and safety assessment |
| FLOOD-Q07 | What should I check before going back into my house after a flood? | post-flood residential reentry assessment: structural damage, electrical hazards, and water contamination evaluation |
| FLOOD-Q08 | Comment préparer un plan d'urgence familial en cas d'inondation ? | developing a family emergency plan for flood events, including evacuation routes and safety procedures |
| FLOOD-Q09 | How do floods affect hospitals and health services? | flood inundation of hospital facilities, disruption of health services and patient care operations |
| STRUCT-Q01 | A building partially collapsed in the old medina and people may be trapped under the rubble. | partial building collapse in a historic area, search and rescue operations under rubble debris |
| STRUCT-Q02 | How do rescue teams mark buildings that have already been searched after a collapse? | post-collapse building marking and stabilization procedures for rescue team operations and debris removal |
| STRUCT-Q03 | What do green yellow and red placards mean in a post-disaster building inspection? | post-disaster building inspection placard designations: green, yellow, and red hazard assessment criteria |
| STRUCT-Q04 | Large cracks appeared in the walls of an apartment building after a gas explosion, residents want to go back inside. | post-gas explosion structural damage in apartment building, assessing building integrity for re-entry |
| STRUCT-Q05 | How should volunteers size up a damaged building before deciding to enter it? | assessing structural damage in a damaged building, determining building entry safety for volunteer responders |
| STRUCT-Q06 | Who coordinates the international urban search and rescue teams arriving after a disaster? | international urban search and rescue team coordination following structural damage and building collapse events |
| STRUCT-Q07 | Un immeuble s'est effondré, comment rechercher des victimes sous les décombres en sécurité ? | search and rescue operations under unstable building debris, ensuring responder safety and victim recovery |
| STRUCT-Q08 | What is the difference between a rapid evaluation and a detailed evaluation of a damaged building? | rapid and detailed building damage assessments, prioritizing structural stability and hazard mitigation |
| FIRE-Q10 | Thick smoke is coming from the kitchen of our flat and the hallway is filling up. | kitchen fire producing heavy smoke, containing fire and evacuating affected residential hallway |
| FIRE-Q11 | Comment évacuer les résidents à mobilité réduite lors d'un incendie dans une résidence pour aînés ? | evacuating residents with mobility limitations during a residential fire, accessible evacuation plans and support |
| FIRE-Q12 | Où faut-il installer les détecteurs de fumée dans une maison ? | smoke detector placement within a residential dwelling, fire hazard mitigation and early warning detection |
| STRUCT-Q09 | How do rescuers reach victims trapped in the voids of a collapsed concrete building? | accessing victims trapped in collapsed concrete building voids, search and rescue operations within unstable structures |
| NEG-Q01 | What is the best recipe for lamb couscous? | culinary recipe request for lamb couscous, food preparation guidance |
| NEG-Q02 | How do I reset my email password? | user account password reset assistance, accessing and restoring email account credentials |
| NEG-Q03 | What is the exchange rate between the Tunisian dinar and the euro today? | currency exchange rate inquiry: Tunisian dinar to euro, financial data request |
| NEG-Q04 | How do I file my income tax return online? | filing income tax returns electronically, accessing online tax preparation services |
| NEG-Q05 | Quelle est la meilleure saison pour visiter Tozeur ? | tourism season assessment for Tozeur, considering weather conditions and visitor activity levels |
| NEG-Q06 | How can farmers protect their crops from locust swarms? | locust swarm impacting agricultural crops, implementing protective measures for livestock and vegetation |
