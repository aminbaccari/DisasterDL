"""Structural and urban emergency entries (sources: FEMA P-2055 and FEMA P-2055-2)."""

STRUCTURAL = [
    dict(
        id="ST-01", lang="en", title="Who decides: building safety evaluators, not responders or software",
        text=("Deciding whether a damaged building is safe, and how large a cordon should be, is a task for trained and certified post-disaster building safety "
              "evaluators. The cordon recommendations assume that the evaluator has the necessary certification and training. Suggested personnel for rapid "
              "evaluations include structural engineers, engineers specialised in structures, architects, building officials, inspectors and experienced contractors."
              ""),
        sources=[("P2055-2", 15, ["post-disaster building safety evaluator determining the cordon area", "would have the necessary certification and training"]),
                 ("P2055", 29, ["structural engineers, professional engineers with a", "specialization in structures, architects, building officials"])],
        needs=["authority", "limits", "building_safety"], audience="public",
    ),
    dict(
        id="ST-02", lang="en", title="Levels of evaluation: rapid, detailed, engineering",
        text=("Post-disaster building evaluation has levels. A rapid evaluation takes an average of 30 minutes per building and gives an initial general evaluation of damage "
              "and safety, to quickly identify and post unsafe and apparently safe structures. A detailed evaluation takes one to four hours per building and is a more thorough "
              "visual examination of the building and its structural system. An engineering evaluation is a detailed investigation by consultants, hired by the owner, "
              "using drawings, damage data and new calculations. A windshield survey before the teams go out only maps the extent of damage and normally does not post placards."),
        sources=[("P2055", 29, ["Rapid Evaluations typically take an average of 30 minutes per building", "Windshield or", "Buildings are normally not"]),
                 ("P2055", 30, ["Detailed Evaluations take one to four hours per building", "Engineering Evaluation"])],
        needs=["building_safety", "process"], audience="professional",
    ),
    dict(
        id="ST-03", lang="en", title="Placards: green INSPECTED, yellow RESTRICTED USE, red UNSAFE",
        text=("Damaged buildings are posted with placards after evaluation: INSPECTED (green placard, lawful permitted use), RESTRICTED USE (yellow placard, use limited) "
              "or UNSAFE (red placard, occupancy prohibited). Even when the structure is not significantly damaged, a building can be posted RESTRICTED USE or UNSAFE because "
              "of mold contamination, blocked exits or toxic chemical spills. A placard cannot be removed or changed until the hazard has been mitigated."),
        sources=[("P2055", 29, ["INSPECTED (green placard), RESTRICTED USE (yellow placard) or UNSAFE (red placard)", "posting of buildings as INSPECTED"]),
                 ("P2055-2", 18, ["green placards for lawful permitted use, yellow for restricted use, and red for prohibited occupancy"]),
                 ("P2055-2", 61, ["The placards cannot be removed or changed until the hazard is mitigated"]),
                 ("P2055", 31, ["posted as", "RESTRICTED USE or UNSAFE when habitability is compromised", "mold contamination, blocked exits, or toxic chemical", "spills"])],
        needs=["placard", "building_safety", "return"], audience="public",
    ),
    dict(
        id="ST-04", lang="en", title="Rapid evaluation criteria and the posting action for each",
        text=("Rapid evaluation criteria after an earthquake, with the action for severe cases: building collapsed, partially collapsed or moved off its foundation, post UNSAFE. "
              "Building or any story significantly out of plumb (leaning), post UNSAFE. Obvious severe damage to primary structural members or severe racking of walls, post UNSAFE. "
              "Obvious parapet, chimney or other falling hazard, post RESTRICTED USE and barricade the unsafe area. Large ground fissures, massive ground movement or slope displacement, post UNSAFE. "
              "Other hazard such as a toxic spill, asbestos contamination, a broken gas line or a fallen power line, post UNSAFE and/or barricade the unsafe area."),
        sources=[("P2055", 49, ["Building has collapsed, partially collapsed, or moved off its foundation", "significantly out of plumb", "Obvious parapet, chimney, or other falling hazard present",
                                "Large fissures in ground", "broken", "gas line, fallen power line"])],
        needs=["building_safety", "collapse", "placard", "falling_hazard"], audience="professional",
    ),
    dict(
        id="ST-05", lang="en", title="Do not enter obviously unsafe buildings; entry rules",
        text=("Entering damaged buildings: do not enter obviously unsafe buildings. A building should not be entered without the permission of the owner or occupant, unless authorized "
              "by the local jurisdiction. Most rapid evaluations are mainly exterior inspections, and evaluators try to enter only when interior damage is suspected or visible from the outside, "
              "when not enough of the structure can be seen from the outside, or to talk with the manager or occupants."),
        sources=[("P2055", 29, ["Do not enter obviously unsafe buildings", "building should not be entered without the permission", "Most Rapid Evaluations are primarily exterior inspections"])],
        needs=["entry", "trapped_people", "building_safety"], audience="public",
    ),
    dict(
        id="ST-06", lang="en", title="Purpose of a cordon and why aftershocks matter",
        text=("A safety cordon evacuates the area around at-risk buildings and restricts access to damaged and partially collapsed buildings. Its purpose is to control public access, "
              "to prevent further casualties in a large aftershock, and to isolate damaged buildings in a restricted perimeter where authorized personnel can repair, demolish or "
              "rebuild without harming people. Large aftershocks have caused much of the death toll in past earthquake sequences, because buildings already damaged by the main shock collapse."),
        sources=[("P2055-2", 17, ["The concept of a safety cordon is to evacuate the area surrounding at-risk buildings", "to control public access, to", "prevent further casualties in a large aftershock",
                                  "Aftershocks following a damaging earthquake may be strong enough to cause additional movement"])],
        needs=["cordon", "aftershock", "evacuate"], audience="public",
    ),
    dict(
        id="ST-07", lang="en", title="Initial cordon distance: 1.5 times height versus height above the damage point",
        text=("Initial cordon distance around a damaged building: the earlier California guidance and fire-service practice set a soft barrier at a horizontal distance of up to 1.5 times "
              "the building height (1.5H:1V), because falling items can bounce and shatter. FEMA P-2055-2 says this is logical and acceptable for common fire emergencies in low-rise buildings of three stories or less, but overly "
              "conservative, particularly for taller buildings, where it could create an exclusion zone up to one-half mile in diameter. For a building with obvious serious damage or a visible lean, "
              "it recommends an initial cordon distance D equal to the height of the building above the significant damage or hinge point, then refining it. "
              "The sources give no distance for a tall building whose damage point is unknown. Any wider default cordon is temporary until evaluators can justify a shorter distance."),
        sources=[("P2055", 179, ["initial placement of soft barriers", "up to 1.5 times", "1.5H:1V setback", "falling", "items can bounce and shatter"]),
                 ("P2055-2", 18, ["establish a cordon offset distance of", "1.5x the building height", "(i.e., three stories or less)", "one-half mile in diameter"]),
                 ("P2055-2", 24, ["an initial emergency cordon distance, D, equal to the", "height of the building above the significant damage or hinge point is prudent", "overly conservative"])],
        needs=["cordon", "distance", "collapse", "evacuate"], audience="professional",
        topic_keys=["structural.cordon_distance"], resolves="C5", numbers_agree=["1.5"],
    ),
    dict(
        id="ST-08", lang="en", title="Wide cordons until evaluators can shorten them",
        text=("Wide safe distances, including block-long cordons, are warranted until inspectors, evaluators, owners, engineers and contractors can evaluate, stabilize or remove "
              "potential falling or collapse risks and erect hard, impact-resistant barriers to protect the public. The wider initial distance is meant to be replaced by "
              "shorter safe distances once the nature and extent of building damage has been investigated and shorter distances can be justified."),
        sources=[("P2055", 179, ["Wide safe distances including block-long", "cordons are warranted until inspectors"]),
                 ("P2055-2", 18, ["the nature and extent of building damage can be investigated, and shorter", "safe distances can be justified"])],
        needs=["cordon", "distance"], audience="professional",
        topic_keys=["structural.cordon_distance"],
    ),
    dict(
        id="ST-09", lang="en", title="Collapse shadow: a wedge, not a full circle",
        text=("A collapse shadow cordon is a wedge or a limited rectangle in the direction a building may fall, not a default 360-degree circle, and this greatly reduces the impact of the cordon "
              "on recovery. It depends on the likely collapse mode, which depends on the damage, the structure type and the stability of the damaged building. Every building damaged enough "
              "to threaten collapse has a fatal flaw that the earthquake exposed, such as unreinforced masonry, non-ductile concrete, a weak story or a torsional irregularity. "
              "Cordon area determination relies on a realistic engineering assessment of the stability and potential collapse of the building."),
        sources=[("P2055-2", 24, ["collapse shadow area as a wedge of a full circle or limited rectangle", "default 360-degree radius", "fatal flaw", "unreinforced masonry, non-ductile concrete, a weak story"]),
                 ("P2055-2", 17, ["Cordon area determination relies on realistic engineering assessment"])],
        needs=["cordon", "distance", "collapse"], audience="professional",
    ),
    dict(
        id="ST-10", lang="en", title="Collapse shadow by collapse mode, part 1 (overturning, story, sidesway, torsion)",
        text=("Collapse shadow cordons by visible damage and collapse mode. Monolithic overturning (visible lean of a ductile concrete core or braced frame): 45-degree wedge along the direction of tilt, "
              "distance D equal to the height of the building above the hinge point. Frame with a story mechanism where progressive collapse is unlikely: rectangle as wide as the building, D equal to the story "
              "height. Frame with a sidesway mechanism where progressive collapse is likely: 45-degree wedge along the tilt, D equal to the building height. Frame with a stable story mechanism: minimal collapse shadow. "
              "Torsional damage: 45-degree wedge, D equal to the height above the hinge point."),
        sources=[("P2055-2", 25, ["45-degree circular wedge area", "D = height of building above hinge", "Story mechanism: Progressive", "D = story height"]),
                 ("P2055-2", 26, ["Sidesway mechanism: Progressive", "D = height of building", "If stable, minimal collapse shadow"]),
                 ("P2055-2", 27, ["Torsional damage", "D = height of building above hinge"])],
        needs=["cordon", "distance", "collapse"], audience="professional",
    ),
    dict(
        id="ST-11", lang="en", title="Collapse shadow by collapse mode, part 2 (pancake, wall fall, rubble pile)",
        text=("Collapse shadow cordons by collapse mode, continued. Pancake collapse of flat concrete slabs with unbraced remaining columns or walls: circle with radius D equal to the height of the unsupported "
              "vertical elements. Tilt-up or other facade panel systems with damaged wall connections: rectangle from each affected wall, D equal to the height of the wall panels. Masonry walls with damaged connections "
              "to the diaphragm: 45-degree wedge, D equal to half the wall panel height, and for buildings up to 4 stories D can be approximated as the building height. Interior column failure with inward tilt of the "
              "perimeter: minimal collapse shadow. Non-engineered masonry, adobe or block buildings partly collapsed as a rubble pile: rectangle from each damaged wall, D equal to 0.15 H."),
        sources=[("P2055-2", 27, ["Circular area, with radius D", "D = height of unsupported vertical"]),
                 ("P2055-2", 28, ["D = height of wall panels", "D = ½ height of wall panels", "up to 4 stories"]),
                 ("P2055-2", 29, ["Minimal collapse shadow", "D = 0.15 H (debris shadow)"])],
        needs=["cordon", "distance", "collapse"], audience="professional",
    ),
    dict(
        id="ST-12", lang="en", title="Falling debris cordons (facade, parapets, chimneys)",
        text=("Debris shadow cordons: small falling debris such as masonry and glass endangers people and vehicles, and larger debris such as parapets, chimneys, infill walls, curtain walls "
              "or cladding can damage adjacent buildings. Set a cordon for buildings with serious visible facade damage or that shed debris onto surfaces used by pedestrians or vehicles, "
              "and include adjacent structures when larger debris is a concern. Keep it until the hazard is mitigated by removal or restraint of damaged elements, until the structure is shown not to shed debris "
              "in aftershocks, or until the threat of aftershocks fades with time. For example, for a 100 ft building the debris distance is recommended as 12 ft."),
        sources=[("P2055-2", 30, ["Small debris shadow cordons should be established", "the debris shadow cordon area should include", "Debris shadow cordons should remain until the debris hazard is", "parapets, chimneys, infill masonry walls"]),
                 ("P2055-2", 31, ["H = 100 ft, the debris shadow distance, D, is recommended as 12 ft"])],
        needs=["cordon", "falling_hazard", "distance"], audience="professional",
    ),
    dict(
        id="ST-13", lang="en", title="Reducing or lifting a cordon, and re-evaluating after an aftershock",
        text=("The cordon can be reduced and eventually removed only after detailed evaluation and monitoring, once shoring is completed, the stability of damaged structures against the intensity of potential "
              "aftershocks is established and the threat of further damage or collapse is mitigated. The perimeter should be re-evaluated after an aftershock. In New Zealand, bus passengers were killed in an aftershock "
              "in an area that had been inside the original cordon, after the perimeter was reduced too soon, likely under pressure to reopen the city."),
        sources=[("P2055-2", 24, ["the cordon area can be reduced", "once shoring actions are completed"]),
                 ("P2055-2", 63, ["The perimeter should be revaluated after an aftershock occurs", "bus passengers were", "reduced too soon"])],
        needs=["cordon", "aftershock", "reopen"], audience="professional",
    ),
    dict(
        id="ST-14", lang="en", title="When to re-evaluate: aftershocks and indicator buildings",
        text=("Most natural hazard incidents have secondary events that call for re-evaluation of the affected buildings, for example a significant aftershock after an earthquake. One approach is to monitor "
              "indicator buildings that represent the local building stock: if they sustain new damage in an aftershock, similar buildings should be re-evaluated, and if not, all similar buildings need not be. "
              "If the authority is told of new damage in any building after an aftershock, that building should be evaluated."),
        sources=[("P2055", 176, ["Most natural hazard incidents have", "inherent secondary events that will warrant", "indicator buildings", "If the AHJ is notified of new damage"])],
        needs=["aftershock", "building_safety", "process"], audience="professional",
    ),
    dict(
        id="ST-15", lang="en", title="Leaning buildings and soft-story collapse: aftershocks can finish the job",
        text=("A leaning story may come to rest in a marginally stable state after an earthquake, and aftershocks can increase the tilt until the destabilizing force exceeds the remaining strength and "
              "the story collapses. Several weak stories in one building can collapse in cascade, and this potential cascading collapse needs a detailed engineering evaluation to inform cordon decisions. "
              "The vast majority of weak or soft story collapses occur during the main shock."),
        sources=[("P2055-2", 39, ["A leaning story may have come to rest in a stable or marginally stable", "Aftershocks will disrupt the marginally stable state"]),
                 ("P2055-2", 40, ["cascading story collapse can occur", "detailed engineering", "the vast majority of weak or soft story collapses occur during the main shock"])],
        needs=["collapse", "aftershock", "lean"], audience="professional",
    ),
    dict(
        id="ST-16", lang="en", title="Undamaged buildings next to a damaged one",
        text=("A building leaning over an adjacent building may lead the authority to post the adjacent building UNSAFE or RESTRICTED USE even if it is undamaged, depending on whether the entire building or "
              "only part of it is exposed. The placards cannot be removed or changed until the hazard is mitigated. Hazards from adjacent damaged buildings are not explicitly addressed in the basic evaluation manual, "
              "except for landslide or rockfall debris from off-site."),
        sources=[("P2055-2", 61, ["a building leaning over an adjacent building", "post the adjacent building UNSAFE or RESTRICTED USE, even if undamaged", "cannot be removed or changed until the hazard is"]),
                 ("P2055-2", 18, ["assessment of the threat posed by adjacent damaged buildings is not explicitly", "addressed"])],
        needs=["adjacent_buildings", "placard", "cordon"], audience="professional",
    ),
    dict(
        id="ST-17", lang="en", title="Gas leak in or near a damaged building",
        text=("Gas leaks pose a serious threat of explosion and fire and should be dealt with immediately. Leak indicators include hissing or blowing noises, dirt thrown into the air, fire from "
              "underground, and water blowing into the air at a pond, creek or river. If you smell natural gas, leave the building and notify the fire department, the utility or an authorized "
              "representative immediately, since they may turn off the gas at the meter. Do not use phones or mobile devices inside the building and avoid anything that may spark, such as starting or "
              "stopping nearby vehicles or machinery. If someone is reported missing or trapped, contact emergency personnel from outside the building."),
        sources=[("P2055", 85, ["Natural gas is normally distributed through a network of underground pipes"]),
                 ("P2055", 86, ["Gas leaks pose a serious threat of", "explosion and fire and should be dealt with immediately", "hissing or blowing noises, dirt thrown into the air",
                                "smell of natural gas", "No phones or", "mobile devices should be used inside the building", "emergency personnel should be contacted from outside", "the building"])],
        needs=["gas", "explosion_risk", "trapped_people", "entry"], audience="public",
    ),
    dict(
        id="ST-18", lang="en", title="Chemical spill or leaking containers near a damaged building",
        text=("If there is an obvious breach of containers or a solid or liquid spill, notify the fire department, barricade, and post a RESTRICTED USE or UNSAFE placard at a safe distance. A chemical release can "
              "burn skin, produce toxic or flammable vapors, injure the respiratory tract and poison through contaminated food or water. The site should be considered too: nearby industrial facilities, storage tanks and "
              "gasoline stations may hold chemicals, and the fire department or the responsible agency should be notified if a release is known."),
        sources=[("P2055", 87, ["the building safety evaluator should notify the fire department, barricade, and", "post RESTRICTED USE or UNSAFE placards at a safe distance", "burns resulting", "from skin contact with corrosive chemicals"]),
                 ("P2055", 88, ["industrial facilities, storage tanks, agricultural land, gasoline stations", "the building safety evaluator should notify the"])],
        needs=["hazmat", "barricade", "fire_department"], audience="professional",
    ),
    dict(
        id="ST-19", lang="en", title="Environmental hazard tiers for a damaged building",
        text=("Environmental hazards in a damaged building can be ranked in tiers. High hazard: imminent danger to habitability, for example active chemical spills or carbon monoxide. Moderate hazard: "
              "potentially serious health and safety risk that can be controlled by rapid repairs or control measures, for example water intrusion. Low hazard: less than serious risk, controlled "
              "with interim measures that allow immediate occupancy. Minimal hazard: a risk that is part of everyday life, for example mice."),
        sources=[("P2055", 85, ["High Hazard: Hazards that pose imminent danger", "Moderate Hazard", "Low Hazard", "Minimal Hazard"])],
        needs=["severity", "building_safety", "hazmat"], audience="professional",
    ),
    dict(
        id="ST-20", lang="en", title="Explosion damage: what is different and what to check",
        text=("Explosions produce pressures higher than typical building design loads, and close blasts cause high-intensity damage to part of the building while distant ones load the whole structure. "
              "Blast pressure can also pull horizontal members and floors upward, which many buildings are not designed for. Non-structural effects include shattered glass and debris, racked doorways, contamination, "
              "damage to mechanical, electrical and plumbing systems, and heat damage to the building envelope. Falling hazards from shattered windows and brittle veneer must be considered. Some explosions are followed by large "
              "fires and others, such as dust explosions, are not. Existing evaluation procedures can be used, since no dedicated guidance exists."),
        sources=[("P2055", 63, ["Explosions generate pressures that are typically greater", "some explosions are followed by large", "dust explosion"]),
                 ("P2055", 64, ["negative bending (uplift) forces", "Shattered glass/debris", "Racked door openings", "falling hazards from"]),
                 ("P2055", 64, ["structures affected by explosion can be evaluated utilizing existing criteria"])],
        needs=["explosion", "building_safety", "falling_hazard"], audience="professional",
    ),
    dict(
        id="ST-21", lang="en", title="Secondary collapse risk differs by incident: earthquake versus fire or explosion",
        text=("The chance of a second extreme loading event is not the same for every incident. After an earthquake, aftershocks justify a conservative approach and re-evaluation. After a fire or an "
              "explosion (except intentionally placed explosions), the probability of a second extreme loading event is low, so a less conservative approach to secondary events can be used in the evaluation."),
        sources=[("P2055", 62, ["the probability of a", "second extreme loading event is low following a fire", "less conservative"]),
                 ("P2055", 64, ["the probability of a second extreme loading event is generally low", "with the exception of intentionally placed"]),
                 ("P2055", 176, ["there may be a significant aftershock that follows the original main shock"])],
        needs=["aftershock", "explosion", "fire", "severity"], audience="professional",
    ),
    dict(
        id="ST-22", lang="en", title="Large cordons displace people and businesses",
        text=("Cordons have a cost. In Christchurch, a cordon of the central business district lasted 857 days and displaced 6,000 businesses, and 47% of buildings in the district were judged unsafe or "
              "restricted. In Santa Cruz after the 1989 Loma Prieta earthquake a 9-block cordon displaced 600 businesses for about 30 days. A cordon sized by a simple 1.5 times height rule around a very tall building "
              "can close an area up to one-half mile in diameter. Over-conservative cordons hinder recovery, but reducing a cordon too soon can also cost lives."),
        sources=[("P2055-2", 59, ["cordon area that", "lasted 857 days", "displacing 6,000 businesses", "9-block cordon", "displacing 600 businesses for about 30 days"]),
                 ("P2055-2", 63, ["47% of buildings in the central business district"]),
                 ("P2055-2", 18, ["one-half mile in diameter", "having an enormous impact to a densely populated urban area"])],
        needs=["cordon", "reopen", "limits"], audience="professional",
        topic_keys=["structural.cordon_distance"],
    ),
    dict(
        id="ST-23", lang="en", title="Two-tier cordon and controlled access for owners",
        text=("After the 1989 Loma Prieta earthquake, authorities set two cordons around vulnerable areas: an outer cordon that kept out the general public but allowed access for media, non-governmental organizations "
              "and healthcare, and an inner cordon with access limited to authorized workers. Later, owners and businesses were allowed to enter the cordoned area briefly to retrieve belongings, "
              "accompanied by safety personnel."),
        sources=[("P2055-2", 19, ["an outer cordon to prevent access to the general", "an inner cordon with limited access only to authorized workers"]),
                 ("P2055-2", 60, ["create an access system for many of", "accompanied by safety personnel"])],
        needs=["cordon", "access", "belongings"], audience="professional",
    ),
    dict(
        id="ST-24", lang="en", title="Managing a cordon: authority, communication, records",
        text=("Experience in New Zealand showed that it is critical to establish clear communications quickly to affirm cordon authority for businesses, owners, residents and tenants, to eliminate confusion and "
              "support safety. Good practice includes a dedicated cordon office, a cordon manager with building official capabilities, thorough documentation of decisions, photos and persons involved, and coordination of "
              "pedestrian, vehicle and emergency vehicle routes around the cordon. The cordon should be flexible and adaptable, and communicate well and often with stakeholders."),
        sources=[("P2055-2", 60, ["critical to establish clear communications quickly to affirm cordon authority"]),
                 ("P2055-2", 61, ["Dedicated Office", "Documentation", "Coordination for pedestrian and vehicular traffic"]),
                 ("P2055-2", 63, ["Cordon Manager", "building official capabilities"]),
                 ("P2055-2", 17, ["flexible, adaptable, improvisational"])],
        needs=["cordon", "communication", "management"], audience="professional",
    ),
    dict(
        id="ST-25", lang="en", title="Scope of the cordon guidance: written for earthquakes",
        text=("The FEMA cordon guidance was written for building collapses caused by earthquakes and aftershocks. Collapses with other causes, such as the apartment building collapses in Davenport, Iowa, and "
              "Miami, Florida, also need cordoning guidance, but this document does not provide it. The collapse-mode distances were therefore not developed for a collapse with an unknown or non-seismic cause."),
        sources=[("P2055-2", 15, ["This report focuses on building collapses caused by earthquakes and aftershocks", "Davenport, Iowa, and Miami, Florida", "other causes of collapse for which cordoning guidance is necessary"])],
        needs=["limits", "collapse", "cordon"], audience="public",
    ),
    dict(
        id="ST-26", lang="en", title="Falling hazards: chimneys, parapets and canopies",
        text=("Damaged parapets, chimneys, canopies and similar elements are falling hazards. An obvious falling hazard leads to a RESTRICTED USE placard and a barricade around the unsafe area. "
              "When a wood-frame structure has burned to the ground but its unreinforced masonry chimney remains, the authority may apply a RESTRICTED USE placard because of the falling hazard of the chimney."),
        sources=[("P2055", 49, ["Damage to nonstructural components,", "such as a damaged parapet or canopy, can lead to a RESTRICTED USE", "placard and a barricade around the unsafe area"]),
                 ("P2055", 61, ["unreinforced masonry chimney remains", "falling hazard the chimney poses"])],
        needs=["falling_hazard", "barricade", "placard"], audience="professional",
    ),
]
