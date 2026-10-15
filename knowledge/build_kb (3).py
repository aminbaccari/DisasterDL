"""Fire entries. LIMITED: the only fire material in the four supplied sources is in FEMA P-2055.

There is no source here on wildfire prevention, evacuation or firefighting. The entries say so.
"""

FIRE = [
    dict(
        id="FI-01", lang="en", title="Limits of this knowledge base for fire",
        text=("Limits for fire incidents: the sources in this knowledge base cover the safety evaluation of buildings after a fire and the health effects of smoke and soot. "
              "They do not give instructions for evacuating before a wildfire, for protecting a house from approaching flames, or for fighting a fire. "
              "For an approaching fire, follow the orders of the authorities and emergency services, and do not rely on this knowledge base for evacuation steps."),
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
              "This advice concerns smoke. The sources reviewed do not give instructions for flames approaching houses, so an evacuation order from the authorities takes priority."),
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
]
