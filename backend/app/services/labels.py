"""Shot-scale vocabulary: dataset label keys -> display names, ordered tightest to widest."""

LABELS: dict[str, dict] = {
    "detail":          {"name": "Detail / Extreme Close-Up", "abbr": "ECU", "order": 0,
                        "lens": "100mm macro lens", "use": "Isolates a single detail or object that matters to the story."},
    "closeUp":         {"name": "Close-Up",                  "abbr": "CU",  "order": 1,
                        "lens": "85mm lens, shallow depth of field", "use": "Puts emotion and reaction front and centre."},
    "mediumCloseUp":   {"name": "Medium Close-Up",           "abbr": "MCU", "order": 2,
                        "lens": "50-85mm lens", "use": "Balances facial expression with a hint of body language."},
    "mediumShot":      {"name": "Medium Shot",               "abbr": "MS",  "order": 3,
                        "lens": "50mm lens", "use": "The workhorse framing for dialogue and interaction."},
    "fullShot":        {"name": "Full Shot",                 "abbr": "FS",  "order": 4,
                        "lens": "35mm lens", "use": "Shows the subject head to toe, establishing posture and movement."},
    "longShot":        {"name": "Long Shot",                 "abbr": "LS",  "order": 5,
                        "lens": "24mm lens", "use": "Places the subject within the environment for context and geography."},
    "extremeLongShot": {"name": "Extreme Long Shot",         "abbr": "ELS", "order": 6,
                        "lens": "16mm wide-angle lens", "use": "Lets the landscape dominate to establish scale and location."},
    "ambiguous":       {"name": "Ambiguous",                 "abbr": "?",   "order": 7,
                        "lens": "", "use": "Does not fit a single standard framing."},
}


def label_info(key: str) -> dict:
    info = LABELS.get(key)
    if info is None:
        return {"name": key, "abbr": key[:3].upper(), "order": 99, "lens": "", "use": ""}
    return info
