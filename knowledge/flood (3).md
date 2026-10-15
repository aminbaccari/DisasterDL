"""Flood entries. Each entry: one self-contained statement taken from the sources.

sources: list of (source key, PDF page, [verbatim anchors]) checked by qa_kb.py.
needs: what a user in a flood might need this for. audience: public or professional.
"""

FLOOD = [
    dict(
        id="FL-01", lang="en", title="What a flood is and why it kills",
        text=("Flood: a temporary overflow of water onto land that is normally dry. Floods can result from rain, snow, "
              "coastal storms, storm surges, overflows of rivers and dam failure. People die by drowning when they do not "
              "evacuate before floodwaters come or when they enter floodwaters. Flooding can develop slowly or quickly, and "
              "flash floods can be sudden and violent. Floods can damage buildings and roads, cause power outages and create landslides."),
        sources=[("RC", 1, ["temporary overflow of water onto land that is normally dry",
                            "People die by drowning when they don't evacuate before floodwaters come or when they enter floodwaters",
                            "Flash floods can be sudden and violent"])],
        needs=["understand", "severity"], audience="public",
    ),
    dict(
        id="FL-02", lang="en", title="Before a flood: know your risk and plan a higher place to go",
        text=("Flood preparation: learn which types of flooding can affect your home and community, for example flash floods, "
              "river floods, storm surges, coastal floods, debris flows, dam breaks and levee failures. Ask the local office of "
              "emergency management for advice. Flash floods may give little to no warning, so choose in advance a place on higher "
              "ground that you can reach quickly and plan to move there before flooding begins."),
        sources=[("RC", 1, ["Learn about the types of flooding", "Reach out to your local office of",
                            "Designate a place on higher ground that", "Plan to move to higher ground before flooding begins"])],
        needs=["before", "evacuate"], audience="public",
        topic_keys=["flood.stay_or_go"],
    ),
    dict(
        id="FL-03", lang="en", title="Be ready to evacuate on official advice (rivers, storm surge, coast)",
        text=("Evacuation during river floods, storm surge and coastal flooding: review your evacuation plan so you can leave "
              "quickly if officials advise you to evacuate. A storm surge can raise water levels quickly and flood large areas in "
              "just minutes, so be prepared to evacuate immediately if local officials advise. For coastal flooding, move inland "
              "before flooding begins."),
        sources=[("RC", 1, ["Review your", "evacuation plan so that you can leave", "A storm", "flood large areas in just minutes",
                            "Move", "inland before flooding begins"])],
        needs=["evacuate", "coastal"], audience="public",
        topic_keys=["flood.stay_or_go"],
    ),
    dict(
        id="FL-04", lang="en", title="Never walk, swim or drive through floodwater (Red Cross figures)",
        text=("Turn around, do not drown: never walk, swim or drive through floodwater. Just 6 in (15 cm) of fast-moving "
              "floodwater can knock you over, and 12 in (30 cm) can carry your vehicle away."),
        sources=[("RC", 1, ["Never walk, swim, or drive through", "floodwater. Just 6 in (15 cm) of fast-moving floodwater can knock you over",
                            "12 in", "(30 cm) can carry your vehicle away"])],
        needs=["during", "vehicle", "roads_blocked"], audience="public",
        topic_keys=["flood.vehicle"],
    ),
    dict(
        id="FL-05", lang="fr", title="Ne prenez pas la voiture pendant une inondation",
        text=("Inondation, premiers réflexes : ne prenez pas votre voiture, quelques centimètres d'eau suffisent à l'emporter. "
              "Reportez tous vos déplacements, à pied ou en voiture. Ne descendez pas dans les sous-sols ni dans les parkings souterrains."),
        sources=[("FALC", 9, ["Ne prenez pas la voiture"]),
                 ("FALC", 10, ["quelques centimetres d'eau", "Reportez tous", "vos deplacements", "Ne descendez pas"])],
        needs=["during", "vehicle", "roads_blocked", "basement"], audience="public",
        topic_keys=["flood.vehicle", "flood.basement"],
    ),
    dict(
        id="FL-06", lang="fr", title="Éloignez-vous des cours d'eau, des berges et des ponts",
        text=("Fortes pluies et inondation dangereuses, premier réflexe : éloignez-vous des cours d'eau, des berges et des ponts. "
              "On peut sauver des vies si on a les bons réflexes, c'est-à-dire ce qu'il faut savoir faire tout de suite."),
        sources=[("FALC", 3, ["On peut sauver des vies si on a les bons réflexes", "Un réflexe c’est ce qu’il faut savoir faire tout de suite"]),
                 ("FALC", 9, ["Éloignez-vous des cours d'eau", "des berges et des ponts"])],
        needs=["during", "bridges_rivers"], audience="public",
    ),
    dict(
        id="FL-07", lang="fr", title="Restez ou mettez-vous à l'abri, allez à l'étage",
        text=("Fortes pluies et inondation dangereuses : restez ou mettez-vous à l'abri et ne vous déplacez pas. Réfugiez-vous à l'étage "
              "du bâtiment. Laissez vos enfants en sécurité à l'école. Ne descendez pas au sous-sol."),
        sources=[("FALC", 9, ["Restez ou mettez-vous à l’abri", "Ne vous déplacez pas", "Laissez vos enfants en sécurité à l’école",
                              "Ne descendez pas au sous-sol", "Allez à l'étage du bâtiment"]),
                 ("FALC", 10, ["Refugiez-vous", "a l'etage"])],
        needs=["during", "shelter", "children", "basement"], audience="public",
        topic_keys=["flood.stay_or_go", "flood.basement"],
    ),
    dict(
        id="FL-08", lang="fr", title="Restez informé et écoutez les consignes des secours et de la mairie",
        text=("Inondation : restez toujours informé et écoutez les consignes des secours et de la mairie. Si les fortes pluies et les "
              "inondations sont dangereuses, appliquez tout de suite les bons réflexes."),
        sources=[("FALC", 9, ["Restez toujours informé", "écoutez les consignes des secours et de la mairie"])],
        needs=["during", "information", "authorities"], audience="public",
        topic_keys=["flood.stay_or_go"],
    ),
    dict(
        id="FL-09", lang="fr", title="Aidez les personnes fragiles et isolées, par SMS",
        text=("Inondation : aidez les personnes autour de vous. Prévenez les personnes fragiles et isolées par SMS, de préférence "
              "aux appels."),
        sources=[("FALC", 9, ["prévenez les personnes fragiles et isolées par SMS"]),
                 ("FALC", 10, ["vulnerables et isolees", "SMS"])],
        needs=["during", "vulnerable_people"], audience="public",
    ),
    dict(
        id="FL-10", lang="fr", title="Kit d'urgence 72 heures : contenu",
        text=("Kit d'urgence 72 heures pour une inondation : un sac prêt et facile à trouver, qui permet de rester chez soi 72 heures, "
              "soit 3 jours, si les routes sont coupées ou l'électricité aussi. Contenu : 6 litres d'eau par personne, nourriture qui se "
              "conserve et se mange sans cuisson, lampe de poche et radio à piles avec piles de rechange, couteau ou ouvre-boîte, "
              "trousse de premiers secours, médicaments, copie des papiers d'identité dans une pochette étanche, argent liquide, "
              "vêtements chauds et couverture de survie, doubles des clés, chargeur de téléphone, lunettes de secours, jeux."),
        sources=[("FALC", 5, ["avec ce kit vous devez pouvoir rester seul chez-vous pendant 72 heures", "c’est-à-dire 3 jours"]),
                 ("FALC", 6, ["6 litres par personne", "se mange sans cuisson", "une lampe de poche avec des piles",
                              "une radio avec des piles en plus", "un couteau ou un ouvre-boîte", "un double de vos clés de maison",
                              "la photocopie de votre carte d’identité dans un sac étanche", "des vêtements chauds"]),
                 ("FALC", 8, ["couverture de survie", "Chargeur", "Lunettes de vue", "Argent liquide"])],
        needs=["before", "kit"], audience="public",
        omitted=["a candle with matches or a lighter (the Red Cross advises against candles, see FL-22)"],
        topic_keys=["flood.light"],
    ),
    dict(
        id="FL-11", lang="fr", title="Kit d'urgence : vérification annuelle et emplacement",
        text=("Kit d'urgence inondation : placez-le dans un endroit facile d'accès et gardez-le toujours prêt. Une fois par an, vérifiez "
              "son contenu, en particulier la date de péremption des médicaments et des denrées, et remplacez les piles. Si vous "
              "l'avez utilisé, réapprovisionnez-le."),
        sources=[("FALC", 5, ["toujours être prêt", "facile à trouver"]),
                 ("FALC", 7, ["Vérifiez tous les ans le contenu de votre kit d’urgence"]),
                 ("FALC", 8, ["Une fois par an", "date de péremption des médicaments et des denrées", "Remplacez les piles", "réapprovisionner"])],
        needs=["before", "kit"], audience="public",
    ),
    dict(
        id="FL-12", lang="en", title="Cutting gas and electricity during a flood: only when it is safe",
        text=("Gas and electricity during a flood: the French guidance says to cut off gas, electricity and heating if possible and "
              "without putting yourself in danger. The Red Cross says not to touch electrical equipment if it is wet or if you are "
              "standing in water, because you could be electrocuted. Apply both together: switch off supplies only if you can do it "
              "safely and dry, and never while standing in water or touching wet equipment. If you smell gas, do not operate anything "
              "that may spark, leave the building and notify the fire department or the gas utility."),
        sources=[("FALC", 9, ["Coupez le gaz et l’électricité", "sans vous mettre en danger"]),
                 ("FALC", 10, ["Coupez, si possible", "sans vous mettre en danger"]),
                 ("RC", 2, ["Do not touch electrical equipment if it is wet or", "standing in water because you could get electrocuted"]),
                 ("P2055", 86, ["smell of natural gas", "building safety evaluator should leave the building and notify", "may spark"])],
        needs=["during", "power", "gas", "electrocution"], audience="public",
        topic_keys=["flood.utilities"], resolves="C3",
    ),
    dict(
        id="FL-13", lang="en", title="Stay or leave? Follow officials first, otherwise go up and do not travel",
        text=("Deciding between sheltering and leaving in a flood: the sources differ in emphasis, not in substance. The Red Cross says to move "
              "to higher ground before flooding begins and to evacuate immediately if local officials advise. The French guidance says to stay or take "
              "shelter, not to travel, to go to an upper floor, never to go to a basement, and to follow the instructions of rescuers and the "
              "town hall. Both give priority to official instructions. Without instructions during sudden intense flooding with rising water, do not "
              "travel through water and move to an upper floor. The sources reviewed give no further instructions for the case where water reaches the upper floor."),
        sources=[("RC", 1, ["Plan to move to higher ground before flooding begins", "Be prepared to evacuate", "if local officials advise"]),
                 ("FALC", 9, ["Restez ou mettez-vous à l’abri", "Allez à l'étage du bâtiment", "écoutez les consignes des secours et de la mairie"])],
        needs=["during", "evacuate", "shelter", "rising_water"], audience="public",
        topic_keys=["flood.stay_or_go"], resolves="C4",
    ),
    dict(
        id="FL-14", lang="en", title="Driving in floodwater: no depth is safe to assume",
        text=("Driving through floodwater: the Red Cross gives figures, 6 in (15 cm) of fast-moving water can knock a person over and 12 in (30 cm) "
              "can carry a vehicle away. The French guidance says a few centimetres of water are enough to carry a car away. The figures are "
              "not identical, so no depth should be treated as safe. Both sources give the same instruction: do not drive or walk through floodwater, "
              "and postpone trips when the roads are flooded or blocked."),
        sources=[("RC", 1, ["12 in", "(30 cm) can carry your vehicle away", "Never walk, swim, or drive through"]),
                 ("FALC", 10, ["quelques centimetres d'eau", "suffisent a l'emporter"])],
        needs=["during", "vehicle", "roads_blocked"], audience="public",
        topic_keys=["flood.vehicle"], resolves="C1",
    ),
    dict(
        id="FL-15", lang="en", title="Staying out of floodwater: contamination",
        text=("Flood contamination: stay away from floodwaters, they may contain sewage, sharp items and chemicals that can make you ill. "
              "Floodwater may carry blackwater with sewage, bacteria, viruses and parasites. Blackwater cannot be reliably identified by looking at it, "
              "so treat floodwater as contaminated if sewer or septic damage is evident, or if chemical or biological pollutants are suspected, and avoid all contact."),
        sources=[("RC", 2, ["Stay away from floodwaters", "sewage, sharp items, and chemicals that can"]),
                 ("P2055", 89, ["Floodwaters may be contaminated with blackwater", "Blackwater cannot be reliably identified visually"]),
                 ("P2055", 90, ["Avoid all contact with contaminated water"])],
        needs=["after", "health", "cleanup"], audience="public",
        topic_keys=["flood.contamination"],
    ),
    dict(
        id="FL-16", lang="en", title="Drinking water and food after a flood",
        text=("Health after a flood: floodwater can contaminate drinking water, so check with the local public health department about "
              "drinking water safety. Throw out food that got wet or warm. When in doubt, throw it out."),
        sources=[("RC", 2, ["Flooding can contaminate drinking water", "Check with your local public health", "Throw", "out food that got wet or warm", "When in doubt,"])],
        needs=["after", "health", "water", "food"], audience="public",
    ),
    dict(
        id="FL-17", lang="en", title="Returning home after evacuation, power lines and debris",
        text=("After a flood: if you evacuated, wait for officials to say it is safe before going home. Avoid fallen power lines, poles and wires, "
              "because they can electrocute you. Watch out for falling trees and other debris."),
        sources=[("RC", 2, ["If you evacuated, wait for officials to say it is", "safe before going home", "Avoid fallen power lines, poles, and wires", "Watch out for falling trees and other debris"])],
        needs=["after", "return", "electrocution"], audience="public",
    ),
    dict(
        id="FL-18", lang="en", title="Cleanup safety: protective equipment and pacing",
        text=("Flood cleanup safety: many injuries happen during cleanup. Wear protective equipment such as boots, long pants, work gloves, eyewear and an "
              "N95 respirator to protect your lungs, and follow the advice of local public health officials. Cleaning up is a big job: work with a partner "
              "and take frequent breaks."),
        sources=[("RC", 2, ["Many injuries happen during cleanup", "boots, long", "N95 respirator", "Work with a partner and take"])],
        needs=["after", "cleanup", "health"], audience="public",
    ),
    dict(
        id="FL-19", lang="en", title="Drying a flooded home and preventing mold",
        text=("Flooded home: if possible, dry the home and everything in it as quickly as you can, within 24 to 48 hours. If you cannot dry it within "
              "24 to 48 hours, assume you have mold growth. When it is safe to return, dry everything completely, clean up the mold and make sure no "
              "moisture problem remains. Keep wet areas well ventilated and throw away wet materials that cannot be repaired or dried. A building that was "
              "flooded and not dried out within 24 to 48 hours is likely to develop mold, and time spent in such conditions should be limited."),
        sources=[("RC", 2, ["within 24 to 48 hours", "you should", "assume you have mold growth", "Keep wet areas well-ventilated", "Throw", "away wet materials that can’t be repaired"]),
                 ("P2055", 89, ["If the building was flooded and", "not dried out within 24-48 hours, mold proliferation is likely", "Time spent in", "conditions should be limited"])],
        needs=["after", "mold", "cleanup", "health"], audience="public",
        topic_keys=["flood.mold_window"], numbers_agree=["24", "48"],
    ),
    dict(
        id="FL-20", lang="en", title="Mold health effects and where to look",
        text=("Mold after flooding: floodwater wicks up drywall by capillary action and stimulates mold growth. Mold exposure can worsen asthma symptoms and cause allergic "
              "reactions, and persistent mold and dampness can cause coughing, wheezing, upper respiratory symptoms and shortness of breath. Persistent dampness inside "
              "walls, crawlspaces, attics or ventilation chases can support mold growth that might only be noticeable by a musty odor. If mold is suspected, "
              "evaluate the building from the outside only."),
        sources=[("P2055", 89, ["floodwater wicks up drywall by capillary action", "Mold exposure can result in worsening asthma symptoms and allergic"]),
                 ("P2055", 90, ["Persistent dampness inside walls, crawlspaces, attics or HVAC chases", "only be noticeable by musty odors", "the building safety evaluator should perform an exterior evaluation only"])],
        needs=["after", "mold", "health"], audience="professional",
    ),
    dict(
        id="FL-21", lang="en", title="Carbon monoxide after a flood: generators, heaters, charcoal",
        text=("Carbon monoxide after a flood: gasoline, propane, natural gas or charcoal-burning devices should never be used inside a home, basement, garage, tent or "
              "camper, or even outside near an open window. Portable generators should be kept outdoors and at least 20 feet from doors, windows or any other building "
              "opening. Carbon monoxide cannot be seen or smelled but can kill you fast. If you start to feel sick, dizzy or weak, get to fresh air right away and do not delay."),
        sources=[("RC", 2, ["Prevent carbon monoxide poisoning", "never be", "used inside a home, basement, garage,", "can kill you fast", "get to", "fresh air right away"]),
                 ("P2055", 86, ["keeping portable generators outdoors and at least 20 feet from", "doors, windows, or any other building opening", "odorless, colorless, and toxic gas"])],
        needs=["after", "power", "generator", "health"], audience="public",
        topic_keys=["flood.co"],
    ),
    dict(
        id="FL-22", lang="en", title="Lighting during and after a flood: flashlights, not candles",
        text=("Lighting during a power cut after a flood: use flashlights or battery-powered lanterns rather than candles, to reduce fire risk. The French "
              "emergency kit list includes a candle with matches or a lighter, which conflicts with this advice. The safer option is a flashlight with spare batteries, "
              "and ignition sources are to be avoided if you smell gas."),
        sources=[("RC", 2, ["Use flashlights or battery-powered lanterns", "rather than candles, to reduce fire risk"]),
                 ("FALC", 6, ["une bougie avec des allumettes ou un briquet", "une lampe de poche avec des piles"]),
                 ("P2055", 86, ["potential ignition", "sources", "should be avoided"])],
        needs=["after", "power", "light", "fire_risk"], audience="public",
        topic_keys=["flood.light"], resolves="C2",
    ),
    dict(
        id="FL-23", lang="en", title="Emotional strain after a flood",
        text=("After a flood it is normal to have a lot of bad feelings, stress or anxiety. Eat healthy food and get enough sleep to help deal with stress. The "
              "Red Cross lists a free disaster distress helpline, but its number is for the United States only and does not apply in Tunisia."),
        sources=[("RC", 2, ["It’s normal to have a lot of bad feelings", "Eat healthy food and get enough sleep", "Disaster Distress"])],
        needs=["after", "mental_health"], audience="public",
    ),
    dict(
        id="FL-24", lang="en", title="Chemicals, propane tanks and car batteries moved by floodwater",
        text=("Hazards moved by floodwater: floodwater may bury or move industrial chemicals from their storage places, and residue chemicals may remain in porous "
              "materials such as drywall and wood. Propane tanks pose a danger of fire or explosion, and if any are found the local police or fire department or the "
              "authority having jurisdiction should be contacted immediately. Car batteries may still hold an electrical charge and spilled acid, so make no contact. "
              "Containers of dry chemicals that became wet can be dangerous, so notify the local fire department."),
        sources=[("P2055", 87, ["residue chemicals may remain in buildings", "embedded in porous materials"]),
                 ("P2055", 88, ["Flood waters may bury or move industrial chemicals", "Propane tanks pose the danger of fire or explosion",
                                "Car batteries may still contain an", "no contact should be", "made", "Containers of dry chemicals may have become wet"])],
        needs=["after", "hazmat", "cleanup"], audience="professional",
    ),
    dict(
        id="FL-25", lang="en", title="Flooded building: when it should be restricted or declared unsafe",
        text=("Safety evaluation of a flooded building: standard practice is to post a RESTRICTED USE placard when there is evidence that the water level rose above the "
              "sill plate. In one training example, a flooded building with mold was posted RESTRICTED USE and entry was acceptable only for retrieving possessions, with "
              "personal protection against mold. After blackwater and contaminants are removed and repairs are completed by qualified contractors, the local authority may allow a "
              "certified contractor to change or remove the placard. This guidance comes from the United States and the authority and process differ by country."),
        sources=[("P2055", 90, ["give the building a", "RESTRICTED USE placard if there is evidence that water levels rose above", "possession retrieval only"]),
                 ("P2055", 179, ["blackwater and contaminants have been removed", "the AHJ may", "allow a certified contractor to change or remove the placard"])],
        needs=["after", "building_safety", "return"], audience="professional",
    ),
    dict(
        id="FL-26", lang="en", title="Water may recede and rise again",
        text=("Flood follow-up: floodwaters may recede and then rise again, and mold growth may be made worse in the meantime. A building evaluated after a flood may need "
              "to be evaluated again if a secondary event occurs."),
        sources=[("P2055", 176, ["Flood", "waters may recede and then rise again", "Mold growth may be exacerbated", "secondary incidents may raise the question of whether a", "reevaluation"])],
        needs=["during", "after", "rising_water", "building_safety"], audience="public",
    ),
]
