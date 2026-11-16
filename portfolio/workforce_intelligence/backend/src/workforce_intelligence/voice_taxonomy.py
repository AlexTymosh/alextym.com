"""Versioned themes and possible labels for synthetic survey evidence."""

TAXONOMY_VERSION = "voice-1"
THEMES = {
    "workload": "Workload and capacity",
    "rostering": "Rostering and working hours",
    "recruitment": "Recruitment process",
    "candidate-communication": "Candidate communication",
    "onboarding": "Onboarding",
    "leadership": "Leadership and management",
    "communication": "General communication",
    "wellbeing": "Wellbeing",
    "psychological-safety": "Psychological safety",
    "speaking-up": "Freedom to Speak Up",
    "development": "Learning and development",
    "progression": "Career progression",
    "inclusion": "Inclusion and fairness",
    "equipment": "Equipment and systems",
    "recognition": "Recognition",
    "safety": "Staff or patient safety",
    "emerging": "Emerging theme",
}
CLASSIFICATIONS = (
    "Complaint",
    "Concern",
    "Safety concern",
    "Suggestion",
    "Improvement initiative",
    "Positive feedback",
    "Request for clarification",
    "Neutral observation",
)
SEVERITIES = ("Low", "Medium", "High", "Critical")
SERIOUS_THEMES = {"safety", "speaking-up", "inclusion"}

DIMENSIONS = {
    "service": "Service line",
    "organisation": "Organisational unit",
    "location": "Location group",
    "role": "Role family",
    "pay_band": "Pay band",
    "clinical": "Clinical grouping",
    "employment_type": "Employment type",
    "fte": "FTE band",
    "tenure": "Tenure band",
    "role_months": "Months in current role",
    "promoted": "Recently promoted",
    "qualified": "Recently qualified (synthetic proxy)",
    "qualification": "Qualification group (synthetic proxy)",
    "starter": "New starter cohort",
    "leaver": "Leaver cohort",
    "source": "Recruitment source",
    "pdr": "PDR status",
    "learning": "Learning participation",
    "age": "Synthetic age band",
    "ethnicity": "Synthetic ethnicity group",
    "disability": "Synthetic disability group",
}
WEIGHT_DIMENSIONS = {"service", "organisation", "location", "role", "tenure", "employment_type"}

QUESTION_BANK = (
    {
        "code": "experience",
        "prompt": "What helped or made work harder during this period?",
        "kind": "comment",
    },
    {
        "code": "onboarding",
        "prompt": "What would make the first weeks in your role easier?",
        "kind": "comment",
    },
    {
        "code": "development",
        "prompt": "What helped or limited your learning and progression?",
        "kind": "comment",
    },
    {
        "code": "support",
        "prompt": "I received the support I needed.",
        "kind": "rating",
        "scale_max": 5,
    },
    {
        "code": "clarity",
        "prompt": "I knew how to raise a concern or ask for help.",
        "kind": "rating",
        "scale_max": 5,
    },
)

SERIES = {
    "general": "Wellbeing and Communication",
    "onboarding": "New starter and onboarding experience",
    "development": "Career Development and Progression",
}

# Each tuple is a literal synthetic sentence and its known generator labels.
_FEEDBACK = {
    "general": (
        (
            "rostering",
            "Concern",
            "Medium",
            "Short notice rota changes made it difficult to plan recovery time.",
        ),
        (
            "workload",
            "Complaint",
            "Medium",
            "Demand regularly exceeded the staffing available on the shift.",
        ),
    ),
    "onboarding": (
        (
            "onboarding",
            "Concern",
            "Medium",
            "I started shifts before the induction checklist was complete.",
        ),
        (
            "candidate-communication",
            "Suggestion",
            "Medium",
            "An earlier update before my first shift would have helped.",
        ),
    ),
    "development": (
        (
            "development",
            "Concern",
            "Medium",
            "Scheduled training was repeatedly displaced by shift cover.",
        ),
        (
            "progression",
            "Suggestion",
            "Medium",
            "Clearer criteria would help staff understand progression opportunities.",
        ),
    ),
}
_SUPPORT = (
    (
        "leadership",
        "Positive feedback",
        "Low",
        "Regular team check-ins made it easier to ask for help.",
    ),
    (
        "recognition",
        "Positive feedback",
        "Low",
        "The team recognised the extra effort colleagues put into handovers.",
    ),
)
_SAFETY = (
    (
        "safety",
        "Safety concern",
        "Critical",
        "A missing equipment check could have put someone at risk.",
    ),
    (
        "speaking-up",
        "Concern",
        "High",
        "It was not clear how to raise a safety concern confidentially.",
    ),
)


def generated_feedback(random, series, mode, direction, possible_concern, ambiguous, severity):
    if ambiguous:
        return "It depended on the shift and is difficult to describe in this survey.", []
    if direction == "positive":
        choices = _SUPPORT
    elif possible_concern:
        choices = (
            _SAFETY if (mode == "significant" and random.random() < 0.78) else _FEEDBACK[series]
        )
        if mode == "emerging" and random.random() < 0.44:
            choices = (
                *choices,
                (
                    "emerging",
                    "Neutral observation",
                    "Low",
                    "The new handover format worked differently across teams.",
                ),
            )
    elif direction == "negative":
        choices = (
            ("communication", "Suggestion", "Low", "Handover notes could be easier to find."),
        )
    else:
        return "My experience was broadly similar to the previous period.", []
    first = random.choice(choices)
    mentions = [first]
    if len(choices) > 1 and random.random() < 0.25:
        mentions.append(next(item for item in choices if item != first))
    if severity and possible_concern:
        mentions = [
            (theme, classification, severity, excerpt)
            for theme, classification, _, excerpt in mentions
        ]
    return " ".join(item[3] for item in mentions), mentions
