{
  "T1": {
    "checked": 342,
    "fails": []
  },
  "T2": {
    "checked": 34,
    "fails": []
  },
  "T3": {
    "groups": [
      {
        "group": "vehicle",
        "topic": "flood",
        "entries": [
          "FL-04",
          "FL-05",
          "FL-14"
        ],
        "sources": [
          "FALC",
          "RC"
        ],
        "status": "reconciled",
        "detail": "C1: Depth that sweeps a vehicle away: Red Cross 12 in (30 cm), French poster 'a few centimetres'."
      },
      {
        "group": "light",
        "topic": "flood",
        "entries": [
          "FL-10",
          "FL-22"
        ],
        "sources": [
          "FALC",
          "P2055",
          "RC"
        ],
        "status": "reconciled",
        "detail": "C2: Candle: listed in the French 72 h kit, discouraged by the Red Cross (fire risk)."
      },
      {
        "group": "utilities",
        "topic": "flood",
        "entries": [
          "FL-12",
          "FL-17",
          "FL-21",
          "FL-22",
          "FL-24"
        ],
        "sources": [
          "FALC",
          "P2055",
          "RC"
        ],
        "status": "reconciled",
        "detail": "C3: Cut gas and power (French poster) versus do not touch wet electrical equipment (Red Cross) versus leave on gas smell (FEMA P-2055)."
      },
      {
        "group": "stay_go",
        "topic": "flood",
        "entries": [
          "FL-01",
          "FL-02",
          "FL-03",
          "FL-07",
          "FL-13",
          "FL-17"
        ],
        "sources": [
          "FALC",
          "RC"
        ],
        "status": "reconciled",
        "detail": "C4: Shelter upstairs and do not travel (French) versus move to higher ground and evacuate on advice (Red Cross)."
      },
      {
        "group": "mold",
        "topic": "flood",
        "entries": [
          "FL-19",
          "FL-20",
          "FL-25",
          "FL-26"
        ],
        "sources": [
          "P2055",
          "RC"
        ],
        "status": "agreement",
        "detail": "Dry within 24 to 48 hours, mold likely after that (Red Cross and P-2055)."
      },
      {
        "group": "co",
        "topic": "flood",
        "entries": [
          "FL-21"
        ],
        "sources": [
          "P2055",
          "RC"
        ],
        "status": "agreement",
        "detail": "Carbon monoxide: Red Cross rules for appliances indoors, P-2055 adds a 20 ft generator distance. Complementary, no contradiction."
      },
      {
        "group": "contamination",
        "topic": "flood",
        "entries": [
          "FL-15",
          "FL-16",
          "FL-25"
        ],
        "sources": [
          "P2055",
          "RC"
        ],
        "status": "agreement",
        "detail": "Floodwater is contaminated: Red Cross and P-2055 agree."
      },
      {
        "group": "cordon_distance",
        "topic": "structural",
        "entries": [
          "ST-07",
          "ST-10",
          "ST-22"
        ],
        "sources": [
          "P2055",
          "P2055-2"
        ],
        "status": "reconciled",
        "detail": "C5: Cordon distance: 1.5 x building height (P-2055, fire-service practice) versus height above hinge point (P-2055-2)."
      },
      {
        "group": "smoke_shelter",
        "topic": "fire",
        "entries": [
          "FI-05"
        ],
        "sources": [
          "P2055"
        ],
        "status": "single source",
        "detail": ""
      }
    ],
    "fails": []
  },
  "T4": {
    "fails": []
  },
  "T5": {
    "min": 20,
    "max": 140,
    "mean": 72.8,
    "fails": []
  },
  "T6": {
    "similar_pairs": [
      [
        0.52,
        "FL-04",
        "FL-14"
      ],
      [
        0.36,
        "FL-02",
        "FL-03"
      ]
    ],
    "fails": []
  },
  "T7": {
    "matrix": {
      "flood": {
        "before": [
          "FL-02",
          "FL-10",
          "FL-11"
        ],
        "during": [
          "FL-04",
          "FL-05",
          "FL-06",
          "FL-07",
          "FL-08",
          "FL-09",
          "FL-12",
          "FL-13",
          "FL-14",
          "FL-26"
        ],
        "after": [
          "FL-15",
          "FL-16",
          "FL-17",
          "FL-18",
          "FL-19",
          "FL-20",
          "FL-21",
          "FL-22",
          "FL-23",
          "FL-24",
          "FL-25",
          "FL-26"
        ],
        "evacuate": [
          "FL-02",
          "FL-03",
          "FL-13"
        ],
        "vehicle": [
          "FL-04",
          "FL-05",
          "FL-14"
        ],
        "power": [
          "FL-12",
          "FL-21",
          "FL-22"
        ],
        "gas": [
          "FL-12"
        ],
        "health": [
          "FL-15",
          "FL-16",
          "FL-18",
          "FL-19",
          "FL-20",
          "FL-21"
        ],
        "mold": [
          "FL-19",
          "FL-20"
        ],
        "kit": [
          "FL-10",
          "FL-11"
        ],
        "shelter": [
          "FL-07",
          "FL-13"
        ],
        "roads_blocked": [
          "FL-04",
          "FL-05",
          "FL-14"
        ],
        "rising_water": [
          "FL-13",
          "FL-26"
        ],
        "vulnerable_people": [
          "FL-09"
        ],
        "electrocution": [
          "FL-12",
          "FL-17"
        ],
        "cleanup": [
          "FL-15",
          "FL-18",
          "FL-19",
          "FL-24"
        ],
        "basement": [
          "FL-05",
          "FL-07"
        ],
        "children": [
          "FL-07"
        ]
      },
      "structural": {
        "cordon": [
          "ST-06",
          "ST-07",
          "ST-08",
          "ST-09",
          "ST-10",
          "ST-11",
          "ST-12",
          "ST-13",
          "ST-16",
          "ST-22",
          "ST-23",
          "ST-24",
          "ST-25"
        ],
        "distance": [
          "ST-07",
          "ST-08",
          "ST-09",
          "ST-10",
          "ST-11",
          "ST-12"
        ],
        "collapse": [
          "ST-04",
          "ST-07",
          "ST-09",
          "ST-10",
          "ST-11",
          "ST-15",
          "ST-25"
        ],
        "trapped_people": [
          "ST-05",
          "ST-17"
        ],
        "entry": [
          "ST-05",
          "ST-17"
        ],
        "gas": [
          "ST-17"
        ],
        "placard": [
          "ST-03",
          "ST-04",
          "ST-16",
          "ST-26"
        ],
        "aftershock": [
          "ST-06",
          "ST-13",
          "ST-14",
          "ST-15",
          "ST-21"
        ],
        "building_safety": [
          "ST-01",
          "ST-02",
          "ST-03",
          "ST-04",
          "ST-05",
          "ST-14",
          "ST-19",
          "ST-20"
        ],
        "falling_hazard": [
          "ST-04",
          "ST-12",
          "ST-20",
          "ST-26"
        ],
        "limits": [
          "ST-01",
          "ST-22",
          "ST-25"
        ],
        "explosion": [
          "ST-20",
          "ST-21"
        ],
        "hazmat": [
          "ST-18",
          "ST-19"
        ],
        "authority": [
          "ST-01"
        ],
        "adjacent_buildings": [
          "ST-16"
        ]
      },
      "fire": {
        "limits": [
          "FI-01"
        ],
        "flames_approaching": [
          "FI-01"
        ],
        "smoke": [
          "FI-04",
          "FI-05"
        ],
        "shelter": [
          "FI-05"
        ],
        "health": [
          "FI-04",
          "FI-05"
        ],
        "after": [
          "FI-02",
          "FI-03",
          "FI-04",
          "FI-08"
        ],
        "building_safety": [
          "FI-02",
          "FI-03",
          "FI-06"
        ]
      }
    },
    "fails": [],
    "known_gaps": {
      "flood": [
        "what to do if water reaches the upper floor or you are trapped (no source gives it)",
        "Tunisian warning services and emergency numbers (no Tunisian source supplied)",
        "after-flood advice is in English only (the French source has none)"
      ],
      "structural": [
        "search and rescue and what bystanders should do for trapped people (sources only say do not enter an obviously unsafe building and call emergency personnel from outside)",
        "cordon distance for a tall building whose damage point is unknown",
        "no French-language structural source, and cordon material is written for earthquakes"
      ],
      "fire": [
        "wildfire prevention, evacuation, defensible space and firefighting (no source supplied)",
        "Tunisian civil protection guidance (no source supplied)",
        "everything here comes from one building-evaluation guide, none of it is written for residents"
      ]
    }
  },
  "T8": {
    "rows": [
      {
        "qid": "Q01",
        "topic": "flood",
        "lang": "en",
        "query": "can I drive through water on a flooded road",
        "expected": [
          "FL-04",
          "FL-14",
          "FL-05"
        ],
        "top3": [
          "FL-14",
          "FL-04",
          "FL-01"
        ],
        "rank": 1
      },
      {
        "qid": "Q02",
        "topic": "flood",
        "lang": "en",
        "query": "how long can a house stay wet before mold starts",
        "expected": [
          "FL-19"
        ],
        "top3": [
          "FL-19",
          "FL-20",
          "FL-15"
        ],
        "rank": 1
      },
      {
        "qid": "Q03",
        "topic": "flood",
        "lang": "en",
        "query": "is it safe to run a generator in the garage after the flood",
        "expected": [
          "FL-21"
        ],
        "top3": [
          "FL-21",
          "FL-14",
          "FL-23"
        ],
        "rank": 1
      },
      {
        "qid": "Q04",
        "topic": "flood",
        "lang": "en",
        "query": "should I switch off the electricity when water gets into the house",
        "expected": [
          "FL-12"
        ],
        "top3": [
          "FL-12",
          "FL-14",
          "FL-25"
        ],
        "rank": 1
      },
      {
        "qid": "Q05",
        "topic": "flood",
        "lang": "en",
        "query": "storm surge warning, when do we leave",
        "expected": [
          "FL-03"
        ],
        "top3": [
          "FL-03",
          "FL-01",
          "FL-02"
        ],
        "rank": 1
      },
      {
        "qid": "Q06",
        "topic": "flood",
        "lang": "en",
        "query": "can we eat food that got wet or warm",
        "expected": [
          "FL-16"
        ],
        "top3": [
          "FL-16",
          "FL-23",
          "FL-19"
        ],
        "rank": 1
      },
      {
        "qid": "Q07",
        "topic": "flood",
        "lang": "en",
        "query": "what protective gear for cleaning up flood damage",
        "expected": [
          "FL-18"
        ],
        "top3": [
          "FL-18",
          "FL-01",
          "FL-02"
        ],
        "rank": 1
      },
      {
        "qid": "Q08",
        "topic": "flood",
        "lang": "en",
        "query": "water is rising fast and the roads are blocked, where should people go",
        "expected": [
          "FL-13",
          "FL-02",
          "FL-03",
          "FL-07"
        ],
        "top3": [
          "FL-14",
          "FL-13",
          "FL-01"
        ],
        "rank": 2
      },
      {
        "qid": "Q09",
        "topic": "flood",
        "lang": "en",
        "query": "floodwater moved chemicals and a propane tank into the yard",
        "expected": [
          "FL-24"
        ],
        "top3": [
          "FL-24",
          "FL-15",
          "FL-14"
        ],
        "rank": 1
      },
      {
        "qid": "Q10",
        "topic": "flood",
        "lang": "en",
        "query": "when can I go back home after being evacuated",
        "expected": [
          "FL-17"
        ],
        "top3": [
          "FL-17",
          "FL-01",
          "FL-16"
        ],
        "rank": 1
      },
      {
        "qid": "Q11",
        "topic": "flood",
        "lang": "en",
        "query": "feeling anxious after the flood",
        "expected": [
          "FL-23"
        ],
        "top3": [
          "FL-21",
          "FL-16",
          "FL-23"
        ],
        "rank": 3
      },
      {
        "qid": "Q12",
        "topic": "flood",
        "lang": "en",
        "query": "candles or flashlight during the power cut",
        "expected": [
          "FL-22"
        ],
        "top3": [
          "FL-22",
          "FL-12",
          "FL-17"
        ],
        "rank": 1
      },
      {
        "qid": "Q13",
        "topic": "flood",
        "lang": "en",
        "query": "is the tap water safe to drink after flooding",
        "expected": [
          "FL-16"
        ],
        "top3": [
          "FL-16",
          "FL-14",
          "FL-12"
        ],
        "rank": 1
      },
      {
        "qid": "Q14",
        "topic": "flood",
        "lang": "fr",
        "query": "que mettre dans le sac d'urgence pour trois jours",
        "expected": [
          "FL-10"
        ],
        "top3": [
          "FL-10",
          "FL-11",
          "FL-05"
        ],
        "rank": 1
      },
      {
        "qid": "Q15",
        "topic": "flood",
        "lang": "fr",
        "query": "est-ce que je peux prendre ma voiture pendant l'inondation",
        "expected": [
          "FL-05"
        ],
        "top3": [
          "FL-05",
          "FL-06",
          "FL-08"
        ],
        "rank": 1
      },
      {
        "qid": "Q16",
        "topic": "flood",
        "lang": "fr",
        "query": "faut-il descendre a la cave ou monter a l'etage",
        "expected": [
          "FL-07"
        ],
        "top3": [
          "FL-07",
          "FL-06",
          "FL-26"
        ],
        "rank": 1
      },
      {
        "qid": "Q17",
        "topic": "flood",
        "lang": "fr",
        "query": "comment aider les voisins isoles ou ages",
        "expected": [
          "FL-09"
        ],
        "top3": [
          "FL-09",
          "FL-08",
          "FL-05"
        ],
        "rank": 1
      },
      {
        "qid": "Q18",
        "topic": "flood",
        "lang": "fr",
        "query": "ou trouver l'information et qui ecouter pendant la crue",
        "expected": [
          "FL-08"
        ],
        "top3": [
          "FL-08",
          "FL-10",
          "FL-05"
        ],
        "rank": 1
      },
      {
        "qid": "Q19",
        "topic": "flood",
        "lang": "fr",
        "query": "rester loin des berges et des ponts",
        "expected": [
          "FL-06"
        ],
        "top3": [
          "FL-06",
          "FL-08",
          "FL-11"
        ],
        "rank": 1
      },
      {
        "qid": "Q20",
        "topic": "flood",
        "lang": "fr",
        "query": "quand verifier le contenu du kit et les piles",
        "expected": [
          "FL-11"
        ],
        "top3": [
          "FL-11",
          "FL-10",
          "FL-08"
        ],
        "rank": 1
      },
      {
        "qid": "Q21",
        "topic": "structural",
        "lang": "en",
        "query": "building partly collapsed and people may still be inside, should I go in",
        "expected": [
          "ST-05",
          "ST-17"
        ],
        "top3": [
          "ST-17",
          "ST-13",
          "ST-09"
        ],
        "rank": 1
      },
      {
        "qid": "Q22",
        "topic": "structural",
        "lang": "en",
        "query": "how far should the cordon be around a leaning building",
        "expected": [
          "ST-07",
          "ST-08",
          "ST-10"
        ],
        "top3": [
          "ST-01",
          "ST-24",
          "ST-07"
        ],
        "rank": 3
      },
      {
        "qid": "Q23",
        "topic": "structural",
        "lang": "en",
        "query": "there is a smell of gas near the collapsed building",
        "expected": [
          "ST-17"
        ],
        "top3": [
          "ST-17",
          "ST-18",
          "ST-04"
        ],
        "rank": 1
      },
      {
        "qid": "Q24",
        "topic": "structural",
        "lang": "en",
        "query": "what do the red, yellow and green signs on a damaged building mean",
        "expected": [
          "ST-03"
        ],
        "top3": [
          "ST-03",
          "ST-20",
          "ST-09"
        ],
        "rank": 1
      },
      {
        "qid": "Q25",
        "topic": "structural",
        "lang": "en",
        "query": "do damaged buildings need to be checked again after an aftershock",
        "expected": [
          "ST-14",
          "ST-13",
          "ST-15"
        ],
        "top3": [
          "ST-14",
          "ST-13",
          "ST-15"
        ],
        "rank": 1
      },
      {
        "qid": "Q26",
        "topic": "structural",
        "lang": "en",
        "query": "a chimney or parapet could fall onto the street",
        "expected": [
          "ST-26",
          "ST-04",
          "ST-12"
        ],
        "top3": [
          "ST-26",
          "ST-12",
          "ST-04"
        ],
        "rank": 1
      },
      {
        "qid": "Q27",
        "topic": "structural",
        "lang": "en",
        "query": "damage to a building after a blast, broken windows",
        "expected": [
          "ST-20"
        ],
        "top3": [
          "ST-20",
          "ST-04",
          "ST-14"
        ],
        "rank": 1
      },
      {
        "qid": "Q28",
        "topic": "structural",
        "lang": "en",
        "query": "who decides how big the safety zone should be",
        "expected": [
          "ST-01"
        ],
        "top3": [
          "ST-01",
          "ST-24",
          "ST-14"
        ],
        "rank": 1
      },
      {
        "qid": "Q29",
        "topic": "structural",
        "lang": "en",
        "query": "spilled chemicals next to a damaged building",
        "expected": [
          "ST-18"
        ],
        "top3": [
          "ST-18",
          "ST-03",
          "ST-16"
        ],
        "rank": 1
      },
      {
        "qid": "Q30",
        "topic": "structural",
        "lang": "en",
        "query": "how long does the safety perimeter stay in place",
        "expected": [
          "ST-13",
          "ST-22",
          "ST-12"
        ],
        "top3": [
          "ST-01",
          "ST-13",
          "ST-06"
        ],
        "rank": 2
      },
      {
        "qid": "Q31",
        "topic": "structural",
        "lang": "en",
        "query": "the cause of the collapse is unknown, does the cordon guidance still apply",
        "expected": [
          "ST-25"
        ],
        "top3": [
          "ST-25",
          "ST-06",
          "ST-07"
        ],
        "rank": 1
      },
      {
        "qid": "Q32",
        "topic": "structural",
        "lang": "en",
        "query": "an undamaged building beside a leaning one",
        "expected": [
          "ST-16"
        ],
        "top3": [
          "ST-16",
          "ST-15",
          "ST-07"
        ],
        "rank": 1
      },
      {
        "qid": "Q33",
        "topic": "fire",
        "lang": "en",
        "query": "flames are near the first houses and the wind blows toward the village",
        "expected": [
          "FI-01",
          "FI-05"
        ],
        "top3": [
          "FI-04",
          "FI-08",
          "FI-01"
        ],
        "rank": 3
      },
      {
        "qid": "Q34",
        "topic": "fire",
        "lang": "en",
        "query": "wildfire smoke, should we stay indoors",
        "expected": [
          "FI-05"
        ],
        "top3": [
          "FI-05",
          "FI-01",
          "FI-08"
        ],
        "rank": 1
      },
      {
        "qid": "Q35",
        "topic": "fire",
        "lang": "en",
        "query": "who suffers most from smoke and soot",
        "expected": [
          "FI-04"
        ],
        "top3": [
          "FI-04",
          "FI-05",
          "FI-01"
        ],
        "rank": 1
      },
      {
        "qid": "Q36",
        "topic": "fire",
        "lang": "en",
        "query": "is it safe to go back into a house after the fire",
        "expected": [
          "FI-03",
          "FI-02"
        ],
        "top3": [
          "FI-03",
          "FI-01",
          "FI-07"
        ],
        "rank": 1
      },
      {
        "qid": "Q37",
        "topic": "fire",
        "lang": "en",
        "query": "mudslide danger in burned hills",
        "expected": [
          "FI-08"
        ],
        "top3": [
          "FI-08",
          "FI-04",
          "FI-06"
        ],
        "rank": 1
      },
      {
        "qid": "Q38",
        "topic": "fire",
        "lang": "en",
        "query": "a fire started after the explosion",
        "expected": [
          "FI-07"
        ],
        "top3": [
          "FI-07",
          "FI-01",
          "FI-03"
        ],
        "rank": 1
      }
    ],
    "summary": {
      "hit@1": 0.87,
      "hit@3": 1.0,
      "hit@5": 1.0,
      "mrr": 0.92,
      "n": 38
    }
  },
  "T9": {
    "fails": []
  },
  "selftest": [
    [
      "number changed (30 cm to 50 cm)",
      true
    ],
    [
      "cordon factor changed (1.5 to 2.5)",
      true
    ],
    [
      "anchor cited on the wrong page",
      true
    ],
    [
      "invented sentence cited as anchor",
      true
    ],
    [
      "emergency number injected",
      true
    ],
    [
      "url injected",
      true
    ],
    [
      "candle added to the kit entry",
      true
    ],
    [
      "reconciliation entry loses a source",
      true
    ],
    [
      "stay-indoors advice without the flames caveat",
      true
    ],
    [
      "duplicate entry added",
      true
    ],
    [
      "a required need removed (gas, structural)",
      true
    ],
    [
      "entry with a missing field",
      true
    ]
  ],
  "counts": {
    "entries": 60,
    "by_topic": {
      "flood": 26,
      "structural": 26,
      "fire": 8
    }
  }
}