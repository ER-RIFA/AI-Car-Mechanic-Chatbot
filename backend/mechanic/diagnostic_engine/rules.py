"""Structured diagnostic rule definitions.

Rules describe automotive knowledge; matching behavior lives in matcher.py.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiagnosticRule:
    rule_id: str
    symptom_group: str
    keyword_groups: dict[str, tuple[str, ...]]
    required_information: tuple[str, ...]
    information_signals: dict[str, tuple[str, ...]]
    follow_up_questions: dict[str, str]
    possible_diagnoses: tuple[str, ...]
    recommended_service: str
    safety_guidance: str
    follow_up_answer_signals: dict[str, tuple[str, ...]] = field(default_factory=dict)
    yes_no_follow_up_keys: tuple[str, ...] = ()


DIAGNOSTIC_RULES = (
    DiagnosticRule(
        "no_start", "starting problem",
        {"start": ("start", "starting", "ignite", "turn on"), "vehicle": ("car", "vehicle", "engine"), "no_start": ("not start", "cannot start", "will not start", "start problem")},
        ("cranks", "dashboard_lights", "clicking", "battery_history"),
        {"cranks": ("crank", "cranking", "turns over", "engine spins", "no crank"), "dashboard_lights": ("dashboard", "dash lights", "warning lights", "instrument lights"), "clicking": ("click", "clicking", "rapid clicks"), "battery_history": ("weak battery", "dead battery", "slow start", "dim lights", "battery recently")},
        {"cranks": "Does the engine crank or turn over when you try to start it?", "dashboard_lights": "Do the dashboard lights come on?", "clicking": "Do you hear a click or repeated clicking?", "battery_history": "Have you noticed a weak battery, slow starting, or dim lights recently?"},
        ("Weak or discharged battery", "Starter motor or electrical connection issue", "Fuel or ignition system fault"),
        "Battery and starting-system inspection",
        "If the vehicle is in an unsafe location, move to safety and arrange roadside assistance rather than repeatedly trying to start it.",
    ),
    DiagnosticRule(
        "starting_click", "clicking noise when starting",
        {"start": ("start", "starting", "turn on"), "click": ("click", "clicking", "rapid clicks"), "starting_context": ("when starting", "while starting", "during starting", "trying to start")},
        ("click_pattern", "dashboard_lights"),
        {"click_pattern": ("one click", "single click", "rapid click", "repeated click", "clicking"), "dashboard_lights": ("dashboard", "dash lights", "warning lights", "dim lights")},
        {"click_pattern": "Is it one solid click or a rapid series of clicks?", "dashboard_lights": "Do the dashboard lights dim or go out when you try to start?"},
        ("Low battery charge", "Loose or corroded battery connection", "Starter motor fault"),
        "Battery, connections, and starter inspection",
        "Avoid repeated starting attempts if cables or wiring become hot, and arrange assistance if the vehicle is stranded.",
    ),
    DiagnosticRule(
        "engine_overheat", "engine overheating",
        {"engine": ("engine", "motor"), "overheat": ("overheat", "hot", "temperature high", "temperature gauge"), "coolant": ("coolant", "antifreeze", "steam", "radiator")},
        ("temperature", "coolant_or_leak", "warning_signs"),
        {"temperature": ("temperature gauge", "in red", "hot", "overheat"), "coolant_or_leak": ("coolant", "antifreeze", "radiator", "leak"), "warning_signs": ("steam", "smoke", "warning light", "hot smell")},
        {"temperature": "How high is the temperature gauge, or is an overheating warning light on?", "coolant_or_leak": "Is coolant leaking or is the coolant level low?", "warning_signs": "Do you see steam, smoke, or smell something hot?"},
        ("Low coolant or coolant leak", "Thermostat or radiator problem", "Cooling fan or water pump fault"),
        "Cooling-system inspection and pressure test",
        "Stop safely, switch off the engine, and do not continue driving while severely overheated. Do not open a hot radiator cap.",
    ),
    DiagnosticRule(
        "brake_noise", "brake squealing or grinding",
        {"brakes": ("brakes", "brake", "stopping"), "noise": ("squeal", "squeaking", "grind", "grinding", "scraping")},
        ("noise_type", "braking_effect", "recent_brake_work"),
        {"noise_type": ("squeal", "squeaking", "grind", "grinding", "scraping"), "braking_effect": ("stopping", "brake pedal", "pedal soft", "takes longer", "pull"), "recent_brake_work": ("new brakes", "brake job", "brake work", "pads replaced")},
        {"noise_type": "Is the sound a light squeal, or a harsh grinding or scraping noise?", "braking_effect": "Has braking performance changed or does the pedal feel soft?", "recent_brake_work": "Has brake work been done recently?"},
        ("Worn brake pads or wear indicator", "Brake rotor damage", "Debris or sticking brake component"),
        "Brake inspection, including pads, rotors, and calipers",
        "If grinding is severe, the pedal is soft, or braking performance is reduced, do not drive; arrange professional assistance.",
        {"braking_effect": (
            "brakes is a bit hard", "brakes feel hard", "brakes feel harder", "brakes feels harder",
            "brakes performance has changed", "brakes feels different",
            "breaking is a bit hard", "breaking feels hard", "breaking feels harder",
            "pedal feels hard", "pedal is hard", "pedal is harder", "pedal feels harder",
            "pedal feels soft", "brakes feels normal", "brakes feel normal",
            "brakes is normal", "braking feels normal",
        )},
        ("noise_type", "braking_effect", "recent_brake_work"),
    ),
    DiagnosticRule(
        "check_engine_light", "check-engine light",
        {"engine_light": ("engine light", "check engine", "service engine"), "warning": ("light", "warning", "dashboard")},
        ("light_behavior", "driveability", "recent_work"),
        {"light_behavior": ("flashing", "blinking", "solid", "steady"), "driveability": ("rough", "misfire", "stall", "power loss", "running poorly"), "recent_work": ("recent repair", "fuel cap", "refuel", "service")},
        {"light_behavior": "Is the check-engine light steady or flashing?", "driveability": "Is the engine running rough, losing power, or stalling?", "recent_work": "Did this start after refueling or recent service?"},
        ("Stored emissions or sensor fault", "Ignition or fuel-system problem", "Loose fuel-cap seal"),
        "Diagnostic scan and engine-system inspection",
        "A flashing engine light or severe loss of power can indicate a damaging fault; reduce driving and seek professional assistance promptly.",
    ),
    DiagnosticRule(
        "brake_pull_vibration", "pulling or vibration while braking",
        {"brakes": ("brakes", "braking", "brake pedal"), "pull": ("pull", "drift", "one side"), "vibration": ("vibration", "shake", "shaking", "judder", "steering wheel")},
        ("direction", "speed_or_condition", "braking_effect"),
        {"direction": ("left", "right", "one side", "pull"), "speed_or_condition": ("high speed", "low speed", "hard braking", "when braking"), "braking_effect": ("soft pedal", "long pedal", "takes longer", "reduced braking")},
        {"direction": "Which direction does the vehicle pull, if any?", "speed_or_condition": "At what speed or braking condition does it happen?", "braking_effect": "Has braking distance or pedal feel changed?"},
        ("Uneven brake operation", "Warped brake rotor", "Suspension or tire problem"),
        "Brake, tire, and suspension inspection",
        "If the vehicle pulls sharply or braking is reduced, avoid driving and arrange professional assistance.",
    ),
    DiagnosticRule(
        "tire_pressure", "flat tire or low tire pressure",
        {"tire": ("tire", "tyre", "wheel"), "pressure": ("pressure", "low", "underinflated"), "flat": ("flat", "puncture", "blowout")},
        ("affected_tire", "visible_damage", "pressure_reading"),
        {"affected_tire": ("front", "rear", "left", "right", "driver", "passenger"), "visible_damage": ("nail", "screw", "cut", "sidewall", "damage"), "pressure_reading": ("psi", "pressure", "tire light")},
        {"affected_tire": "Which tire is affected?", "visible_damage": "Can you see a puncture, cut, bulge, or sidewall damage?", "pressure_reading": "What pressure reading do you see, if available?"},
        ("Puncture or leaking valve", "Low tire pressure", "Tire damage requiring replacement"),
        "Tire inspection, repair, or replacement",
        "Do not drive on a flat or visibly damaged tire, especially with sidewall damage; use a spare or roadside assistance.",
    ),
    DiagnosticRule(
        "battery_warning", "battery warning or dim lights",
        {"battery": ("battery", "charging"), "electrical": ("dim lights", "flicker", "electrical"), "warning": ("battery light", "charging light", "warning light")},
        ("warning_behavior", "starting_behavior", "electrical_symptoms"),
        {"warning_behavior": ("battery light", "charging light", "warning light"), "starting_behavior": ("slow start", "no start", "clicking", "hard start"), "electrical_symptoms": ("dim lights", "flicker", "radio resets", "electrical")},
        {"warning_behavior": "Is the battery or charging warning light on steadily?", "starting_behavior": "Has starting become slow or intermittent?", "electrical_symptoms": "Are lights dimming or other electrical systems cutting out?"},
        ("Alternator or charging-system fault", "Weak battery", "Loose belt or electrical connection"),
        "Battery and charging-system test",
        "A charging warning with dimming lights can precede a stall; avoid unnecessary driving and arrange assistance if symptoms worsen.",
    ),
    DiagnosticRule(
        "oil_leak", "oil leak",
        {"oil": ("oil", "engine oil"), "leak": ("leak", "drip", "puddle", "spot")},
        ("leak_size", "location", "fluid_identity"),
        {"leak_size": ("small", "large", "puddle", "dripping", "rapid"), "location": ("under engine", "under car", "front", "rear"), "fluid_identity": ("oil", "brown", "black", "slippery", "fuel", "gasoline")},
        {"leak_size": "Is it a small spot or a rapidly growing puddle?", "location": "Where under the vehicle is the fluid appearing?", "fluid_identity": "What color and texture is the fluid, and does it smell like fuel?"},
        ("Engine oil leak", "Filter, drain plug, or seal leak", "Possible fuel or fluid leak"),
        "Fluid-leak inspection and level check",
        "Do not drive with a major leak or low oil level. If fuel is suspected, avoid ignition sources and arrange immediate professional inspection.",
    ),
    DiagnosticRule(
        "steering_vibration", "steering vibration",
        {"steering": ("steering wheel", "steering"), "vibration": ("vibration", "shake", "shaking", "wobble")},
        ("speed", "when_occurs", "recent_impact"),
        {"speed": ("speed", "mph", "kmh", "highway"), "when_occurs": ("while driving", "braking", "accelerating", "turning"), "recent_impact": ("pothole", "curb", "impact", "collision")},
        {"speed": "At what speed does the steering vibration begin?", "when_occurs": "Does it happen while driving, braking, accelerating, or turning?", "recent_impact": "Did it begin after a pothole, curb, or other impact?"},
        ("Wheel balance or alignment issue", "Bent wheel or tire damage", "Steering or suspension wear"),
        "Tire, wheel, alignment, and steering inspection",
        "If steering control is affected or vibration is severe, reduce speed safely and arrange an inspection rather than continuing to drive.",
    ),
    DiagnosticRule(
        "exhaust_smoke", "strange exhaust smoke",
        {"exhaust": ("exhaust", "tailpipe"), "smoke": ("smoke", "smoking"), "color": ("white", "blue", "black", "gray", "grey")},
        ("smoke_color", "smoke_amount", "engine_symptoms"),
        {"smoke_color": ("white", "blue", "black", "gray", "grey"), "smoke_amount": ("small", "thick", "heavy", "constant", "only cold"), "engine_symptoms": ("rough", "misfire", "power loss", "oil", "coolant")},
        {"smoke_color": "What color is the smoke?", "smoke_amount": "Is the smoke brief, thick, or continuous?", "engine_symptoms": "Are there misfires, power loss, or low oil or coolant levels?"},
        ("Oil burning", "Coolant entering the combustion system", "Over-fueling or air-intake fault"),
        "Engine and exhaust-system inspection",
        "Heavy smoke, a strong fuel smell, or rapid overheating warrants stopping safely and professional inspection before continued driving.",
    ),
    DiagnosticRule(
        "ac_not_cooling", "air conditioning not cooling",
        {"ac": ("ac", "air conditioning", "air conditioner"), "cooling": ("not cold", "not cooling", "warm air", "hot air", "cool air")},
        ("air_temperature", "airflow", "recent_service"),
        {"air_temperature": ("warm air", "hot air", "not cold", "cold air"), "airflow": ("weak airflow", "no airflow", "blower", "airflow"), "recent_service": ("recharged", "refrigerant", "ac service", "recent repair")},
        {"air_temperature": "Is the air warm, or only less cold than usual?", "airflow": "Is the airflow weak, or is there no airflow at all?", "recent_service": "Has the AC been serviced or recharged recently?"},
        ("Low refrigerant from a leak", "Compressor or electrical fault", "Blower or airflow restriction"),
        "Air-conditioning performance and leak inspection",
        "Avoid opening refrigerant components yourself; arrange inspection, especially if there is a chemical smell or unusual belt noise.",
    ),
)