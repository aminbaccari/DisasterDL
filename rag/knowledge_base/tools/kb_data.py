"""Aggregates entries and the declared conflict and agreement records."""
from entries_flood import FLOOD
from entries_structural import STRUCTURAL
from entries_fire import FIRE
from sources_data import SOURCES

ENTRIES = []
for topic, items in (("flood", FLOOD), ("structural", STRUCTURAL), ("fire", FIRE)):
    for e in items:
        e = dict(e)
        e["topic"] = topic
        e.setdefault("topic_keys", [])
        e.setdefault("omitted", [])
        e.setdefault("meta", False)
        ENTRIES.append(e)

# Cross-source topics. Detection is automatic (see GROUPS in qa_kb.py). A group that appears in two or more
# sources must be either resolved by a reconciliation entry or declared as an agreement.
CONFLICTS = {
    "C1": dict(group="vehicle", summary="Depth that sweeps a vehicle away: Red Cross 12 in (30 cm), French poster 'a few centimetres'.",
               resolver="FL-14", must_contain=["30 cm", "centimetres", "no depth"]),
    "C2": dict(group="light", summary="Candle: listed in the French 72 h kit, discouraged by the Red Cross (fire risk).",
               resolver="FL-22", must_contain=["candle", "flashlight", "conflicts"]),
    "C3": dict(group="utilities", summary="Cut gas and power (French poster) versus do not touch wet electrical equipment (Red Cross) versus leave on gas smell (FEMA P-2055).",
               resolver="FL-12", must_contain=["wet", "electric", "gas", "never while standing in water"]),
    "C4": dict(group="stay_go", summary="Shelter upstairs and do not travel (French) versus move to higher ground and evacuate on advice (Red Cross).",
               resolver="FL-13", must_contain=["higher ground", "upper floor", "officials"]),
    "C5": dict(group="cordon_distance", summary="Cordon distance: 1.5 x building height (P-2055, fire-service practice) versus height above hinge point (P-2055-2).",
               resolver="ST-07", must_contain=["1.5", "hinge point", "three stories"]),
    "C10": dict(group="smoke_shelter", summary="Stay indoors during smoke (P-2055) must not be read as advice when flames approach.",
                resolver="FI-05", must_contain=["smoke", "flames", "evacuation order"]),
    "C11": dict(group="stay_go_fire", summary="Leave immediately when told (FEMA V-1013) versus shelter in a cleared house and not in a car until rescue (French ministry page) versus stay indoors in smoke (P-2055).",
                resolver="FI-13", must_contain=["leave", "cleared", "car", "authorities", "do not say"], must_cite=["V1013", "MTE"]),
    "C12": dict(group="smoke_protection", summary="Smoke protection: N95 mask (FEMA V-1013) versus damp cloth over nose and mouth (French ministry page). The sources do not compare them.",
                resolver="FI-18", must_contain=["N95", "damp cloth", "do not compare"], must_cite=["V1013", "MTE"]),
}

AGREEMENTS = {
    "mold": dict(entries=["FL-19"], numbers=["24", "48"], summary="Dry within 24 to 48 hours, mold likely after that (Red Cross and P-2055)."),
    "co": dict(entries=["FL-21"], numbers=[], summary="Carbon monoxide: Red Cross rules for appliances indoors, P-2055 adds a 20 ft generator distance. Complementary, no contradiction."),
    "contamination": dict(entries=["FL-15"], numbers=[], summary="Floodwater is contaminated: Red Cross and P-2055 agree."),
    "defensible_space": dict(entries=["FI-11"], numbers=["30"], summary="Clear flammable material around the house: FEMA gives at least 30 feet, the French page requires clearing in risk zones and gives no distance. Complementary, no contradiction."),
    "return_after": dict(entries=["FI-19", "FI-20"], numbers=[], summary="After a fire, wait for the authorities before returning: FEMA, the French prefecture notice and the P-2055 evaluators agree."),
    "report_fire": dict(entries=["FI-09", "FI-12", "FI-14"], numbers=[], summary="Alert the emergency services: FEMA, the French page and the ONPC report agree. Numbers differ by country, only Tunisia's 198 (from the ONPC report) is kept."),
}

# Sentences written by the project team, not taken from a source. They are checked to be present in the entry
# text and are shown in the md files as team notes. Reconciliation entries (resolves=...) are team syntheses of cited sources.
TEAM_NOTES = {
    "FL-12": ["Apply both together: switch off supplies only if you can do it safely and dry, and never while standing in water or touching wet equipment."],
    "FL-13": ["Both give priority to official instructions.",
              "Without instructions during sudden intense flooding with rising water, do not travel through water and move to an upper floor.",
              "The sources reviewed give no further instructions for the case where water reaches the upper floor."],
    "FL-14": ["The figures are not identical, so no depth should be treated as safe."],
    "FL-22": ["The safer option is a flashlight with spare batteries, and ignition sources are to be avoided if you smell gas."],
    "FL-23": ["Red Cross lists a free disaster distress helpline, but its number is for the United States only and does not apply in Tunisia."],
    "FL-25": ["This guidance comes from the United States and the authority and process differ by country."],
    "ST-07": ["The sources give no distance for a tall building whose damage point is unknown.", "Any wider default cordon is temporary until evaluators can justify a shorter distance."],
    "ST-25": ["The collapse-mode distances were therefore not developed for a collapse with an unknown or non-seismic cause."],
    "FI-01": ["Limits for fire incidents:"],
    "FI-05": ["This advice concerns smoke, not approaching flames.", "If flames approach or the authorities order an evacuation, the evacuation order takes priority."],
    "FI-09": ["The emergency number in the source is for the United States and is not given here."],
    "FI-12": ["Il s'agit d'un compte rendu de presse, et le communiqué original n'a pas été consulté."],
    "FI-13": ["Both give priority to instructions from the authorities.", "If the authorities order an evacuation, leave.",
              "The sources do not say when to leave rather than shelter in a cleared house, and give no further instructions for flames already reaching a house."],
    "FI-18": ["The sources do not compare the two or say how well a damp cloth filters smoke."],
    "FI-21": ["Le numéro d'urgence de la source est celui des États-Unis et n'est pas reproduit ici."],
    "FI-24": ["Les deux donnent la priorité aux consignes des autorités.", "Si les autorités ordonnent une évacuation, partez.",
              "Les sources ne disent pas quand partir plutôt que s'abriter dans une habitation débroussaillée, et ne donnent pas d'autres consignes si les flammes atteignent déjà une maison."],
    "FI-25": ["Les sources ne comparent pas les deux et n'indiquent pas dans quelle mesure un linge humide filtre la fumée."],
}

# Content read in the sources and deliberately left out, with the reason. Reported in the README.
EXCLUSIONS = [
    ("FALC p4-5", "Meteo-France vigilance and Vigicrues services, sites and app", "French-only services, not usable in Tunisia"),
    ("FALC p6", "Candle with matches or lighter in the kit list", "Conflicts with the Red Cross advice, handled in FL-22"),
    ("FALC p3, p14-15", "Climate background and rainfall figures (more than 10 cm in 1 hour)", "Background, not an action. Could support severity later"),
    ("FALC p11-13", "Overseas site, risk-box game, witness video", "Not guidance"),
    ("RC p1", "FEMA Flood Map Service Center", "US-only service"),
    ("RC p2", "Disaster Distress Helpline number and Emergency App", "US-only number and app, flagged in FL-23"),
    ("P-2055 ch. 2.3-2.6, 5, 6 (most), 7, 8", "Legislation, grants, certification, resource typing, mutual aid, data collection, quality assurance", "Programme management in the United States, not useful to an incident assistant"),
    ("P-2055 ch. 3.4-3.7, 3.11", "Land instability, volcanoes, hail, snow and ice, historic resources", "Outside the three incident types"),
    ("P-2055 ch. 4.4.6-4.4.11", "Asbestos, lead paint, parasites, animals, insects, debris", "Possible later extension for flooded buildings"),
    ("P-2055 p87-88", "US Coast Guard hotline number, NFPA diamond, IICRC category names", "US-only identifiers"),
    ("P-2055-2 ch. 2.3, 3.2 narratives, appendix A", "Case histories and literature review behind the collapse modes", "Evidence behind the tables, kept out to avoid repeating the table rules"),
    ("P-2055-2 ch. 4", "Building-code authority, grants, cordon office funding, CERA organisation", "US and New Zealand administration"),
    ("V-1013 p1-2", "9-1-1, Emergency Alert System, NOAA Weather Radio, FEMA app, Ready.gov", "US-only numbers and services"),
    ("V-1013 p1", "Cover facts (what a wildfire is, causes, flooding and transport problems afterwards)", "Background, not an action"),
    ("French ministry page", "French emergency numbers, Météo des forêts, Géorisques, prefecture access rules, campaign video, partner list", "French-only services and numbers, not usable in Tunisia"),
    ("French ministry page", "Statistics on French forest area", "Background, not an action"),
    ("allAfrica article", "Heat context and the reproduction-rights notice", "Not guidance. The article is paraphrased and quoted only in short phrases"),
    ("FEMA P-2143 (2023)", "The newer flyer was not obtained", "The ready.gov copy carries the number V-1013 and the date May 2018, so V-1013 is cited"),
]
