"""Fire entries.

FI-01 to FI-08 come from FEMA P-2055 (building safety after a fire, smoke, secondary hazards).
FI-09 to FI-20 add wildfire guidance for residents from three sources: the FEMA wildfire flyer (V-1013, 2018),
the French ministry page on forest and vegetation fires, and a news report of Tunisian civil protection (ONPC)
recommendations. The ONPC item is journalism: its entries are attributed to La Presse and never decide a conflict.
"""

FIRE = [
    dict(
        id="FI-01", lang="en", title="Limits of this knowledge base for fire",
        text=("Limits for fire incidents: this knowledge base gives general wildfire guidance from a FEMA flyer, a French government page and a news report of Tunisian civil protection recommendations, "
              "plus building and smoke information from FEMA P-2055. It does not say what to do when flames are already reaching a house or when a fire cannot be outrun, it gives no firefighting instructions, "
              "and the Tunisian source covers prevention and reporting only. For an approaching fire, follow the orders of the authorities and emergency services. "
              "When the knowledge base has no guidance for a question, say so plainly and refer to the authorities instead of inventing steps."),
        sources=[("P2055", 61, ["Fire incidents can be localized to a single building or affect a wide region", "such as wildfire"])],
        needs=["limits", "evacuate", "flames_approaching"], audience="public",
        meta=True, topic_keys=["fire.smoke_shelter"],
    ),
    dict(
        id="FI-02", lang="en", title="Fires affect buildings unevenly, and damage may not be visible",
        text=("After a fire or wildfire, some structures can be burned so badly that they are essentially destroyed while others are untouched, simply because of the path of the fire. "
              "A fire can be limited to one building or affect a wide region. Heat can degrade structural members in ways that are not obvious: for example, the metal connector plates of wood trusses "
              "can be significantly affected by heat without any significant visible charring of the wood. Rapid evaluations have no effective method for judging intact members exposed to fire."),
        sources=[("P2055", 61, ["some structures are burned so badly as to be essentially destroyed", "others may be untouched simply because of the fire’s path"]),
                 ("P2055", 62, ["metal truss plate", "without any", "significant visible charring of the wood", "rapid evaluations lack an effective methodology"])],
        needs=["after", "building_safety", "return"], audience="professional",
    ),
    dict(
        id="FI-03", lang="en", title="Re-entering a fire-damaged building: what evaluators look at",
        text=("Going back into a house or building after a fire: the safety evaluation of a fire-damaged building asks whether the fire has weakened the vertical load-carrying or lateral force-resisting capacity of structural elements. "
              "Charred members can be assessed for section loss. If the building leans because of fire damage, the standard earthquake criteria for leaning buildings apply. "
              "No dedicated best-practice guidance exists for fire damage, and evaluators use the detailed evaluation criteria of the standard field manual in the meantime."),
        sources=[("P2055", 62, ["No best practice guidance exists for fire damage", "whether fire damage has sufficiently", "weakened the vertical load-carrying or lateral force-resisting capacity"]),
                 ("P2055", 61, ["Qualitative (or quantitative, if possible) evaluation of section loss", "charred members"])],
        needs=["after", "building_safety", "return"], audience="professional",
    ),
    dict(
        id="FI-04", lang="en", title="Soot, fumes and who is most at risk",
        text=("Toxicity of soot and fumes near active burning depends on what is burning, wind direction and speed, and the concentration and size of the particles. Burning plastics common in household "
              "furnishings produce highly toxic soot. People with heart or lung conditions, the elderly, smokers and children may be most affected. Evaluators of burned buildings can also be "
              "exposed to latent chemical hazards from products of combustion."),
        sources=[("P2055", 88, ["the toxicity of soot and fumes will depend", "wind direction and speed", "highly toxic soot", "heart or lung", "conditions), the elderly, smokers, and children"]),
                 ("P2055", 62, ["possible", "exposure of evaluators to latent chemical hazards from products of", "combustion"])],
        needs=["after", "smoke", "health", "vulnerable_people"], audience="public",
    ),
    dict(
        id="FI-05", lang="en", title="Staying indoors during a smoke episode (smoke only, not approaching flames)",
        text=("Smoke exposure, not flame danger: during a smoke episode, a common advisory is to stay indoors, where people can better control their environment. Relief from smoke and heat is best "
              "when buildings have filtered air and climate control, and some communities provide public cleaner-air shelters for people whose buildings lack adequate filtration or cooling. "
              "In high heat, staying cool, hydrated and inside helps. Follow local emergency managers and public health officials on decisions to shelter in place. "
              "This advice concerns smoke, not approaching flames. If flames approach or the authorities order an evacuation, the evacuation order takes priority."),
        sources=[("P2055", 89, ["Wildfire Smoke: A Guide", "stay indoors, where people can better control", "public", "cleaner-air shelters", "should", "follow the guidance of local emergency managers and public health officials"])],
        needs=["during", "smoke", "shelter", "health"], audience="public",
        topic_keys=["fire.smoke_shelter"], resolves="C10",
    ),
    dict(
        id="FI-06", lang="en", title="Active burning found by an evaluator",
        text=("If active burning is found in an area where it has not yet been reported, the building safety evaluator should notify the fire department, barricade, and post a RESTRICTED USE or UNSAFE "
              "placard at a safe distance. For buildings in an area of active burning, the evaluation focuses on outdoor air quality and on the ability of the building systems to filter incoming air."),
        sources=[("P2055", 88, ["active burning is encountered in areas", "notify the", "fire department, barricade, and post RESTRICTED USE or UNSAFE placards at a safe distance",
                                "the building evaluation will", "necessarily focus on the outdoor air quality"])],
        needs=["during", "building_safety", "barricade", "fire_department"], audience="professional",
    ),
    dict(
        id="FI-07", lang="en", title="Fire after an explosion or an earthquake, and delayed ignition",
        text=("Fire can follow another incident. Low explosives such as fuels and gunpowder typically create large fires after detonation, while high explosives such as TNT typically do not. "
              "A fire can start after an earthquake, and fires may ignite with delay because hidden mechanical or electrical faults go unnoticed until power is restored at a building. "
              "For structures affected by fire after an explosion, both the fire and the explosion criteria apply."),
        sources=[("P2055", 63, ["Low explosives, such as fuels and gunpowder, typically create large fires", "criteria in this section", "as well as the recommendation in Section 3.8 (Fire) are applicable"]),
                 ("P2055", 65, ["a fire that occurs after an", "earthquake", "Fires may also ignite with delay", "until power is reestablished at a structure"])],
        needs=["explosion", "secondary_hazard", "power_restoration"], audience="public",
    ),
    dict(
        id="FI-08", lang="en", title="Mudslides and flash floods weeks or months after a wildfire",
        text=("A secondary incident can come long after the first one: mudslides and flash floods can occur weeks or months after wildfires. A secondary incident may seem to occur at the same time as the first, or not for weeks or months."),
        sources=[("P2055", 65, ["not for weeks or months later, such as", "mudslides and flash floods after wildfires"])],
        needs=["after", "secondary_hazard", "landslide", "flood"], audience="public",
    ),

    dict(
        id="FI-09", lang="en", title="Under a wildfire warning: get to safety right away",
        text=("If you are under a wildfire warning, get to safety right away. Leave if told to do so, and leave immediately if the authorities tell you to evacuate. "
              "Listen for emergency information and alerts from your community's alerting systems. Use N95 masks to keep particles out of the air you breathe. "
              "If you are trapped, call the emergency services and give your location, but be aware that the emergency response could be delayed or impossible; turn on lights to help people find you. "
              "The emergency number in the source is for the United States and is not given here."),
        sources=[("V1013", 1, ["IF YOU ARE UNDER A WILDFIRE WARNING", "GET TO SAFETY RIGHT AWAY", "Leave if told to do so", "If trapped, call"]),
                 ("V1013", 2, ["Leave immediately if", "emergency response could be", "Turn on lights to help people find you", "to keep particles"])],
        needs=["during", "evacuate", "flames_approaching", "reporting", "smoke"], audience="public",
        omitted=["the United States emergency number and the names of United States alert systems"],
    ),
    dict(
        id="FI-10", lang="en", title="Before a wildfire: warnings, evacuation routes and supplies",
        text=("FEMA's advice for preparing before a wildfire: sign up for your community's warning system. Know your community's evacuation routes, find several ways to leave the area, "
              "drive the evacuation routes and find shelter locations, and have a plan for pets and livestock. Gather emergency supplies, including N95 respirator masks that filter out particles in the air, "
              "and keep in mind each person's specific needs, including medication and the needs of pets. Keep important documents in a fireproof safe, with password-protected digital copies, "
              "and review insurance coverage to make sure it is enough to replace your property."),
        sources=[("V1013", 2, ["Sign up for your community", "warning system", "Know your community", "evacuation", "find several ways to leave", "shelter locations", "Have a plan for pets and livestock",
                               "N95 respirator masks", "Keep important documents in a fireproof safe", "Review insurance coverage"])],
        needs=["before", "evacuate", "kit", "reporting"], audience="public",
        omitted=["the names of United States alert systems"],
    ),
    dict(
        id="FI-11", lang="en", title="Making a home safer from wildfire: fire-resistant zone and water source",
        text=("FEMA's advice for making a home safer from wildfire: use fire-resistant materials to build, renovate or make repairs. Find an outdoor water source with a hose that can reach any area of your property. "
              "Create a fire-resistant zone that is free of leaves, debris or flammable materials for at least 30 feet from your home."),
        sources=[("V1013", 2, ["Use fire-resistant materials to build", "Find an outdoor water source with a", "hose that can reach any area of your", "Create a fire-resistant zone",
                               "free of leaves, debris, or flammable", "for at least 30 feet from", "your home"])],
        needs=["before", "prevention", "defensible_space", "home_protection"], audience="public",
    ),
    dict(
        id="FI-12", lang="fr", title="Recommandations de la protection civile tunisienne contre les incendies (reportage La Presse)",
        text=("Selon un communiqué de l'ONPC (protection civile tunisienne) rapporté par La Presse le 9 juillet 2026, face à des températures de 40 à 45 degrés et à un risque d'incendie accru, il est recommandé : "
              "de ne pas abandonner de bouteilles en verre dans les forêts et les espaces ouverts, car elles peuvent concentrer les rayons du soleil ; de ne pas jeter de mégots ni d'autres matériaux inflammables "
              "sur les routes ou dans la nature ; de ne pas brûler de déchets, de résidus agricoles ou d'herbes sèches, ni allumer de feux dans les forêts ou près des zones agricoles ; "
              "de surveiller les enfants et de les empêcher de jouer avec des pétards ; de coopérer avec la protection civile et les autorités locales et de respecter leurs instructions ; "
              "de signaler immédiatement toute fumée ou tout incendie au 198 en cas d'urgence. Il s'agit d'un compte rendu de presse, et le communiqué original n'a pas été consulté."),
        sources=[("ONPC", 1, ["9 Juillet 2026", "40 à 45 degrés", "de ne pas abandonner de bouteilles en verre", "concentrer les rayons du soleil", "ni de tout autre matériau inflammable",
                              "ne pas brûler de déchets", "ne pas allumer de feux dans les forêts", "les empêcher de jouer avec les pétards", "coopérer avec les agents de la protection civile",
                              "signaler immédiatement toute fumée ou incendie", "le 198"])],
        needs=["prevention", "reporting", "tunisia_context", "during"], audience="public",
    ),
    dict(
        id="FI-13", lang="en", title="Leave when told, or shelter in a cleared house: how the sources fit together",
        text=("Two kinds of advice need to be read together when a wildfire threatens. FEMA says to evacuate and leave immediately if the authorities tell you to do so, and to listen for emergency information and alerts. "
              "The French government page says that a person who sees a fire starting should alert the rescue services and take shelter in a house cleared of vegetation until rescuers arrive, "
              "and that a car is not a safe shelter because it could burn. Both give priority to instructions from the authorities. If the authorities order an evacuation, leave. "
              "The sources do not say when to leave rather than shelter in a cleared house, and give no further instructions for flames already reaching a house."),
        sources=[("V1013", 2, ["Evacuate. Leave immediately if authorities tell you to do so", "Listen to EAS, NOAA Weather Radio, or local alerting systems"]),
                 ("MTE", 1, ["Je me mets à l'abri dans une habitation débroussaillée en attendant l'intervention des secours", "La voiture n'est pas un abri sûr car elle pourrait brûler",
                             "me conforme aux consignes des secours ou de la mairie"])],
        needs=["during", "evacuate", "shelter", "flames_approaching"], audience="public",
        resolves="C11",
    ),
    dict(
        id="FI-14", lang="fr", title="Début d'incendie : alerter, se protéger, s'informer",
        text=("Si vous êtes témoin d'un début d'incendie, donnez l'alerte aux services de secours et essayez de localiser le feu. "
              "En attendant l'intervention des secours, mettez-vous à l'abri dans une habitation débroussaillée : la voiture n'est pas un abri sûr car elle pourrait brûler. "
              "Restez informé de la situation et suivez les consignes des secours ou de la mairie."),
        sources=[("MTE", 1, ["je donne l'alerte en appelant", "j'essaie de localiser le feu", "Je me mets à l'abri dans une habitation débroussaillée en attendant l'intervention des secours",
                             "La voiture n'est pas un abri sûr car elle pourrait brûler", "me conforme aux consignes des secours ou de la mairie"])],
        needs=["during", "shelter", "reporting", "flames_approaching"], audience="public",
        omitted=["the French emergency numbers, which do not apply in Tunisia"],
    ),
    dict(
        id="FI-15", lang="fr", title="Éviter les départs de feu : barbecue, mégots, travaux",
        text=("Pour éviter les départs de feu, la page du ministère français conseille de faire les barbecues chez soi, sur une terrasse et loin de la végétation, de jeter les mégots dans un cendrier, "
              "et de réaliser les travaux loin de la pelouse et des herbes sèches en prévoyant un extincteur à portée de main en cas de départ de feu."),
        sources=[("MTE", 1, ["J'organise les barbecues chez moi, sur une terrasse et loin de la végétation", "Je jette mes mégots dans un cendrier",
                             "Je réalise mes travaux loin de la pelouse et des herbes sèches", "je prévois un extincteur à portée de main"])],
        needs=["prevention"], audience="public",
    ),
    dict(
        id="FI-16", lang="fr", title="Se protéger dans son habitation avant l'arrivée du feu",
        text=("Pour se protéger dans son habitation avant l'arrivée du feu, la page du ministère français conseille de rentrer le tuyau d'arrosage, qui pourra servir après le passage du feu à éteindre les dernières braises ; "
              "de boucher les aérations et le bas des portes pour que les fumées toxiques et les flammèches ne puissent pas pénétrer dans l'habitation ; "
              "et de se couvrir le nez et la bouche d'un linge humide pour se protéger de la fumée."),
        sources=[("MTE", 1, ["je rentre mon tuyau d'arrosage", "éteindre les dernières braises", "Je bouche les aérations et les bas de porte", "fumées toxiques et les flammèches",
                             "Je me couvre le nez et la bouche d'un linge humide"])],
        needs=["during", "home_protection", "smoke"], audience="public",
    ),
    dict(
        id="FI-17", lang="fr", title="Anticiper : débroussailler, stocker, adapter la maison",
        text=("Pour anticiper et protéger son habitation contre les feux de forêt, la page du ministère français conseille de stocker le bois et les bouteilles de gaz dans un abri fermé, éloigné de l'habitation ; "
              "avant l'été, de débroussailler autour de la maison en coupant la végétation basse et en élaguant les arbres pour qu'ils ne se touchent pas, afin d'éviter que le feu n'atteigne l'habitation, "
              "ce qui est une obligation dans les zones à risque ; et, dans une zone couverte par un plan de prévention du risque de feu de forêt, d'adapter la maison (volets, gouttières, toiture, aération). "
              "Selon la page, 90 % des maisons détruites lors des feux de forêt ne sont pas, ou sont mal, débroussaillées."),
        sources=[("MTE", 1, ["Je stocke les matériaux et produits inflammables (bois, bouteilles de gaz) dans un abri fermé", "Avant l’été, je débroussaille autour de ma maison",
                             "je coupe la végétation basse et j’élague les arbres pour qu’ils ne se touchent pas", "Dans les zones à risque, c’est une obligation",
                             "plan de prévention du risque de feu de forêt", "90% des maisons détruites lors des feux de forêt ne sont pas, ou sont mal, débroussaillées"])],
        needs=["before", "prevention", "defensible_space", "home_protection"], audience="public",
    ),
    dict(
        id="FI-18", lang="en", title="Protecting yourself from smoke: N95 mask or damp cloth",
        text=("Two ways to protect yourself from smoke are given. FEMA advises using N95 masks to keep particles out of the air you breathe. "
              "The French government page advises covering the nose and mouth with a damp cloth to protect against smoke. "
              "The sources do not compare the two or say how well a damp cloth filters smoke. The mask that FEMA recommends is the N95, which is designed to keep particles out."),
        sources=[("V1013", 2, ["Use an N95 masks to keep particles", "out of the air you breathe"]),
                 ("MTE", 1, ["Je me couvre le nez et la bouche d'un linge humide pour me protéger de la fumée"])],
        needs=["smoke", "health", "during"], audience="public",
        resolves="C12",
    ),
    dict(
        id="FI-19", lang="en", title="After a wildfire: when to return and what to avoid",
        text=("After a wildfire, listen to the authorities to find out whether it is safe to return and whether the water is safe to drink. Avoid hot ash, charred trees, smoldering debris and live embers. "
              "The ground may contain heat pockets that can burn you or spark another fire. Consider the danger to pets and livestock walking the ground. "
              "Send text messages or use social media to reach family and friends, because phone systems are often busy after a disaster, and make calls only in emergencies. "
              "Document property damage with photographs, make an inventory and contact your insurance company."),
        sources=[("V1013", 2, ["Listen to authorities to find out if it", "is safe to return and whether water is", "Avoid hot ash, charred trees,", "live embers", "heat pockets that can burn you or spark another",
                               "Consider the danger to pets", "Phone systems are often busy", "Make calls only in", "Document property damage with photographs"])],
        needs=["after", "return", "health"], audience="public",
    ),
    dict(
        id="FI-20", lang="fr", title="Après un feu de forêt : ne pas se rendre sur les lieux",
        text=("Après un feu de forêt, la page du ministère français conseille de ne pas se rendre sur les lieux de l'incendie, même s'il est fixé ou éteint, pour laisser les pompiers travailler et ne pas encombrer les accès. "
              "Les pompiers peuvent avoir besoin de plusieurs jours pour éteindre complètement le feu et sécuriser la zone. Une fois le feu éteint, les chutes d'arbres et de rochers sont fréquentes et des glissements de terrain sont possibles. "
              "Avant de retourner en forêt, il faut se tenir informé auprès de la préfecture et suivre strictement les consignes des autorités locales."),
        sources=[("MTE", 1, ["Je ne me rends pas sur les lieux de l'incendie", "Même si le feux est fixé ou éteint", "laisser l'espace aux services de secours",
                             "plusieurs jours pour éteindre complétement le feu", "les chutes d'arbres, de rochers sont fréquentes", "des glissements de terrain sont possibles",
                             "Avant de retourner en forêt", "Je suis strictement les consignes des autorités locales"])],
        needs=["after", "return"], audience="public",
    ),
]


# French translations of key English entries, so that French queries reach the same guidance (e5 prefers same-language text).
# Written by the project team. The English entry is the reference: same sources, same anchors, same needs.
_EN = {e["id"]: e for e in FIRE}


def _translation(new_id, of, title, text, **extra):
    src = _EN[of]
    return dict(id=new_id, lang="fr", title=title, text=text, sources=src["sources"], needs=src["needs"],
                audience=src["audience"], translation_of=of, **extra)


FIRE += [
    _translation(
        "FI-21", "FI-09", "En cas d'alerte feu de forêt : se mettre en sécurité immédiatement",
        ("En cas d'alerte feu de forêt, mettez-vous en sécurité immédiatement. Partez si l'on vous le demande, et partez sans attendre si les autorités vous ordonnent d'évacuer. "
         "Écoutez les informations et les alertes d'urgence diffusées par les systèmes d'alerte de votre commune. Utilisez un masque N95 pour empêcher les particules de pénétrer dans l'air que vous respirez. "
         "Si vous êtes bloqué, appelez les secours et donnez votre position, mais sachez que l'intervention des secours peut être retardée ou impossible ; allumez les lumières pour que l'on puisse vous repérer. "
         "Le numéro d'urgence de la source est celui des États-Unis et n'est pas reproduit ici."),
        omitted=["the United States emergency number and the names of United States alert systems"],
    ),
    _translation(
        "FI-22", "FI-10", "Avant un feu de forêt : alertes, itinéraires d'évacuation et fournitures",
        ("Conseils de la FEMA pour se préparer avant un feu de forêt : inscrivez-vous au système d'alerte de votre commune. Connaissez les itinéraires d'évacuation de votre commune, repérez plusieurs façons de quitter la zone, "
         "parcourez les itinéraires d'évacuation, repérez les lieux d'hébergement et prévoyez un plan pour les animaux domestiques et le bétail. Rassemblez des fournitures d'urgence, dont des masques respiratoires N95 qui filtrent "
         "les particules de l'air, en tenant compte des besoins de chacun, notamment les médicaments, et de ceux des animaux. Conservez les documents importants dans un coffre ignifugé, avec des copies numériques protégées par mot de passe, "
         "et vérifiez que votre assurance suffit à remplacer vos biens."),
        omitted=["the names of United States alert systems"],
    ),
    _translation(
        "FI-23", "FI-11", "Mieux protéger une maison contre les feux de forêt : zone résistante au feu et point d'eau",
        ("Conseils de la FEMA pour mieux protéger une maison contre les feux de forêt : utilisez des matériaux résistants au feu pour construire, rénover ou réparer. "
         "Prévoyez un point d'eau extérieur avec un tuyau qui atteint toutes les zones de votre terrain. "
         "Créez une zone résistante au feu, dépourvue de feuilles, de débris et de matériaux inflammables, sur au moins 30 pieds (feet) autour de votre maison."),
    ),
    _translation(
        "FI-24", "FI-13", "Partir sur ordre ou s'abriter dans une habitation débroussaillée : comment les sources se complètent",
        ("Deux types de conseils doivent être lus ensemble lorsqu'un feu de forêt menace. La FEMA dit d'évacuer et de partir immédiatement si les autorités vous le demandent, et d'écouter les informations et les alertes d'urgence. "
         "La page du gouvernement français dit que la personne qui voit un feu naissant doit alerter les secours et se mettre à l'abri dans une habitation débroussaillée jusqu'à l'arrivée des secours, "
         "et que la voiture n'est pas un abri sûr car elle pourrait brûler. Les deux donnent la priorité aux consignes des autorités. Si les autorités ordonnent une évacuation, partez. "
         "Les sources ne disent pas quand partir plutôt que s'abriter dans une habitation débroussaillée, et ne donnent pas d'autres consignes si les flammes atteignent déjà une maison."),
    ),
    _translation(
        "FI-25", "FI-18", "Se protéger de la fumée : masque N95 ou linge humide",
        ("Deux moyens de se protéger de la fumée sont indiqués. La FEMA conseille d'utiliser un masque N95 pour empêcher les particules de pénétrer dans l'air que l'on respire. "
         "La page du gouvernement français conseille de se couvrir le nez et la bouche d'un linge humide pour se protéger de la fumée. "
         "Les sources ne comparent pas les deux et n'indiquent pas dans quelle mesure un linge humide filtre la fumée. Le masque recommandé par la FEMA est le N95, conçu pour retenir les particules."),
    ),
    _translation(
        "FI-26", "FI-19", "Après un feu de forêt : quand revenir et ce qu'il faut éviter",
        ("Après un feu de forêt, écoutez les autorités pour savoir s'il est sûr de revenir et si l'eau est potable. Évitez les cendres chaudes, les arbres calcinés, les débris qui couvent et les braises encore vives. "
         "Le sol peut contenir des poches de chaleur qui peuvent vous brûler ou déclencher un nouveau feu. Pensez au danger pour les animaux domestiques et le bétail qui marchent sur le sol. "
         "Envoyez des SMS ou utilisez les réseaux sociaux pour joindre vos proches, car les réseaux téléphoniques sont souvent saturés après une catastrophe, et ne passez des appels qu'en cas d'urgence. "
         "Photographiez les dégâts, faites un inventaire et contactez votre assureur."),
    ),
]
