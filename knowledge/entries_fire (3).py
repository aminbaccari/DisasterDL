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
}

AGREEMENTS = {
    "mold": dict(entries=["FL-19"], numbers=["24", "48"], summary="Dry within 24 to 48 hours, mold likely after that (Red Cross and P-2055)."),
    "co": dict(entries=["FL-21"], numbers=[], summary="Carbon monoxide: Red Cross rules for appliances indoors, P-2055 adds a 20 ft generator distance. Complementary, no contradiction."),
    "contamination": dict(entries=["FL-15"], numbers=[], summary="Floodwater is contaminated: Red Cross and P-2055 agree."),
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
    "FI-05": ["This advice concerns smoke.", "The sources reviewed do not give instructions for flames approaching houses, so an evacuation order from the authorities takes priority."],
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
]
