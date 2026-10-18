# Retrieval evaluation (2026-10-17 20:28)

- Test set: 36 queries (30 positive, 6 out-of-scope)
- Labels: keyword page labels + 278 pooled LLM-panel judgments (evaluation/judging/agreement.md)
- Embedding model: `intfloat/multilingual-e5-base`; chunk size 400, overlap 60; per-query results in `retrieval_20261017_2028_lenient.csv`

## Overall (positive queries)

| config | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 | Source P@5 |
|---|---|---|---|---|---|---|
| fixed | 0.900 | 0.933 | 0.933 | 0.967 | 0.921 | 0.893 |
| fixed+filter | 0.933 | 0.967 | 0.967 | 0.967 | 0.950 | 0.920 |
| structure | 0.867 | 0.933 | 0.933 | 0.933 | 0.900 | 0.907 |
| structure+filter | 0.867 | 0.933 | 0.933 | 0.967 | 0.906 | 0.933 |
| structure-noheader+filter | 0.867 | 0.933 | 0.933 | 0.967 | 0.906 | 0.867 |
| structure+filter[e5-small] | 0.667 | 0.900 | 0.900 | 0.967 | 0.781 | 0.873 |
| fixed+filter+cap2 | 0.933 | 0.967 | 0.967 | 0.967 | 0.950 | 0.838 |
| structure+filter+cap2 | 0.867 | 0.967 | 1.000 | 1.000 | 0.918 | 0.883 |
| structure+filter+rerank | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.947 |
| structure+filter+rerank+cap2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.877 |
| fixed+filter+rw3 | 0.733 | 0.767 | 0.900 | 0.967 | 0.786 | 0.813 |
| structure+filter+rw3 | 0.800 | 0.900 | 0.967 | 0.967 | 0.859 | 0.847 |
| structure+filter+fusion3 | 0.967 | 1.000 | 1.000 | 1.000 | 0.978 | 0.907 |
| structure+filter+fusion3+cap2 | 0.967 | 1.000 | 1.000 | 1.000 | 0.978 | 0.830 |
| structure+filter+fusion3+rerank | 0.900 | 0.967 | 1.000 | 1.000 | 0.934 | 0.960 |

## Hit@5 / MRR@10 by disaster_type

| config | fire | flood | structural |
|---|---|---|---|
| fixed | 1.000 / 1.000 (n=11) | 0.900 / 0.914 (n=10) | 0.889 / 0.833 (n=9) |
| fixed+filter | 1.000 / 1.000 (n=11) | 1.000 / 1.000 (n=10) | 0.889 / 0.833 (n=9) |
| structure | 1.000 / 0.955 (n=11) | 0.900 / 0.900 (n=10) | 0.889 / 0.833 (n=9) |
| structure+filter | 1.000 / 0.955 (n=11) | 0.900 / 0.917 (n=10) | 0.889 / 0.833 (n=9) |
| structure-noheader+filter | 1.000 / 0.955 (n=11) | 0.900 / 0.917 (n=10) | 0.889 / 0.833 (n=9) |
| structure+filter[e5-small] | 0.909 / 0.813 (n=11) | 0.900 / 0.767 (n=10) | 0.889 / 0.759 (n=9) |
| fixed+filter+cap2 | 1.000 / 1.000 (n=11) | 1.000 / 1.000 (n=10) | 0.889 / 0.833 (n=9) |
| structure+filter+cap2 | 1.000 / 0.955 (n=11) | 1.000 / 0.920 (n=10) | 1.000 / 0.870 (n=9) |
| structure+filter+rerank | 1.000 / 1.000 (n=11) | 1.000 / 1.000 (n=10) | 1.000 / 1.000 (n=9) |
| structure+filter+rerank+cap2 | 1.000 / 1.000 (n=11) | 1.000 / 1.000 (n=10) | 1.000 / 1.000 (n=9) |
| fixed+filter+rw3 | 0.818 / 0.720 (n=11) | 0.900 / 0.740 (n=10) | 1.000 / 0.917 (n=9) |
| structure+filter+rw3 | 1.000 / 0.798 (n=11) | 0.900 / 0.850 (n=10) | 1.000 / 0.944 (n=9) |
| structure+filter+fusion3 | 1.000 / 1.000 (n=11) | 1.000 / 0.933 (n=10) | 1.000 / 1.000 (n=9) |
| structure+filter+fusion3+cap2 | 1.000 / 1.000 (n=11) | 1.000 / 0.933 (n=10) | 1.000 / 1.000 (n=9) |
| structure+filter+fusion3+rerank | 1.000 / 0.867 (n=11) | 1.000 / 0.950 (n=10) | 1.000 / 1.000 (n=9) |

## Hit@5 / MRR@10 by language

| config | en | fr |
|---|---|---|
| fixed | 0.955 / 0.938 (n=22) | 0.875 / 0.875 (n=8) |
| fixed+filter | 1.000 / 0.977 (n=22) | 0.875 / 0.875 (n=8) |
| structure | 0.955 / 0.932 (n=22) | 0.875 / 0.812 (n=8) |
| structure+filter | 0.955 / 0.939 (n=22) | 0.875 / 0.812 (n=8) |
| structure-noheader+filter | 0.955 / 0.939 (n=22) | 0.875 / 0.812 (n=8) |
| structure+filter[e5-small] | 0.955 / 0.886 (n=22) | 0.750 / 0.493 (n=8) |
| fixed+filter+cap2 | 1.000 / 0.977 (n=22) | 0.875 / 0.875 (n=8) |
| structure+filter+cap2 | 1.000 / 0.941 (n=22) | 1.000 / 0.854 (n=8) |
| structure+filter+rerank | 1.000 / 1.000 (n=22) | 1.000 / 1.000 (n=8) |
| structure+filter+rerank+cap2 | 1.000 / 1.000 (n=22) | 1.000 / 1.000 (n=8) |
| fixed+filter+rw3 | 0.955 / 0.898 (n=22) | 0.750 / 0.478 (n=8) |
| structure+filter+rw3 | 0.955 / 0.879 (n=22) | 1.000 / 0.806 (n=8) |
| structure+filter+fusion3 | 1.000 / 0.970 (n=22) | 1.000 / 1.000 (n=8) |
| structure+filter+fusion3+cap2 | 1.000 / 0.970 (n=22) | 1.000 / 1.000 (n=8) |
| structure+filter+fusion3+rerank | 1.000 / 1.000 (n=22) | 1.000 / 0.754 (n=8) |

## Hit@5 / MRR@10 by style

| config | question | report |
|---|---|---|
| fixed | 0.955 / 0.955 (n=22) | 0.875 / 0.830 (n=8) |
| fixed+filter | 0.955 / 0.955 (n=22) | 1.000 / 0.938 (n=8) |
| structure | 0.955 / 0.932 (n=22) | 0.875 / 0.812 (n=8) |
| structure+filter | 0.955 / 0.932 (n=22) | 0.875 / 0.833 (n=8) |
| structure-noheader+filter | 0.955 / 0.955 (n=22) | 0.875 / 0.771 (n=8) |
| structure+filter[e5-small] | 0.909 / 0.823 (n=22) | 0.875 / 0.667 (n=8) |
| fixed+filter+cap2 | 0.955 / 0.955 (n=22) | 1.000 / 0.938 (n=8) |
| structure+filter+cap2 | 1.000 / 0.947 (n=22) | 1.000 / 0.838 (n=8) |
| structure+filter+rerank | 1.000 / 1.000 (n=22) | 1.000 / 1.000 (n=8) |
| structure+filter+rerank+cap2 | 1.000 / 1.000 (n=22) | 1.000 / 1.000 (n=8) |
| fixed+filter+rw3 | 0.864 / 0.744 (n=22) | 1.000 / 0.900 (n=8) |
| structure+filter+rw3 | 0.955 / 0.861 (n=22) | 1.000 / 0.854 (n=8) |
| structure+filter+fusion3 | 1.000 / 1.000 (n=22) | 1.000 / 0.917 (n=8) |
| structure+filter+fusion3+cap2 | 1.000 / 1.000 (n=22) | 1.000 / 0.917 (n=8) |
| structure+filter+fusion3+rerank | 1.000 / 0.970 (n=22) | 1.000 / 0.838 (n=8) |

## Head-to-head: structure+filter vs fixed+filter (reciprocal rank per query)

structure better on 0 queries, worse on 2, tied on 28.

## Threshold calibration (best config by MRR: `structure+filter+rerank`)

- Score of the first relevant chunk (positives): min 0.758, median 0.861, max 0.894
- Top-1 score on out-of-scope queries: min 0.742, median 0.777, max 0.827

| threshold | positives kept (hit@5) | negatives rejected | balanced |
|---|---|---|---|
| 0.780 | 0.933 | 0.667 | 0.800 |
| 0.785 | 0.833 | 0.833 | 0.833 |
| 0.790 | 0.833 | 0.833 | 0.833 |
| 0.795 | 0.833 | 0.833 | 0.833 |
| 0.800 | 0.833 | 0.833 | 0.833 |
| 0.805 | 0.833 | 0.833 | 0.833 |
| 0.810 | 0.767 | 0.833 | 0.800 |
| 0.815 | 0.767 | 0.833 | 0.800 |
| 0.820 | 0.700 | 0.833 | 0.767 |
| 0.825 | 0.700 | 0.833 | 0.767 |
| 0.830 | 0.667 | 1.000 | 0.833 |
| 0.835 | 0.667 | 1.000 | 0.833 |
| 0.840 | 0.633 | 1.000 | 0.817 |
| 0.845 | 0.600 | 1.000 | 0.800 |
| 0.850 | 0.600 | 1.000 | 0.800 |
| 0.855 | 0.600 | 1.000 | 0.800 |
| 0.860 | 0.533 | 1.000 | 0.767 |
| 0.865 | 0.367 | 1.000 | 0.683 |
| 0.870 | 0.267 | 1.000 | 0.633 |
| 0.875 | 0.167 | 1.000 | 0.583 |
| 0.880 | 0.167 | 1.000 | 0.583 |
| 0.885 | 0.100 | 1.000 | 0.550 |
| 0.890 | 0.033 | 1.000 | 0.517 |
| 0.895 | 0.000 | 1.000 | 0.500 |
| 0.900 | 0.000 | 1.000 | 0.500 |

Best balanced threshold: **0.785** (keeps 83% of positive hits, rejects 83% of out-of-scope queries).

## Failed queries (no relevant chunk in top 5, `structure+filter+rerank`)


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
