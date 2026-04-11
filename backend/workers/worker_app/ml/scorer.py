from datetime import datetime
from backend.models.user import User
from backend.models.opportunity import Opportunity

def build_user_profile_text(user: User) -> str:
    parts = [
        user.field_of_study or "",
        " ".join(user.interests or []),
        " ".join(user.skills or []),
        user.bio or "",
    ]
    return " ".join(p for p in parts if p).strip() or "general student"

def score_opportunity(user: User, opp: Opportunity, semantic_sim: float, now: datetime) -> tuple[float, dict]:
    breakdown: dict[str, float] = {}

    breakdown["semantic_similarity"] = round(max(0.0, float(semantic_sim)), 4)

    user_skills = set(s.lower() for s in (user.skills or []))
    opp_skills = set(s.lower() for s in (opp.required_skills or []))
    if opp_skills:
        overlap = len(user_skills & opp_skills) / len(user_skills | opp_skills)
    else:
        overlap = 0.5
    breakdown["skill_overlap"] = round(overlap, 4)

    user_interests = set(i.lower() for i in (user.interests or []))
    opp_domain = opp.domain.value if hasattr(opp.domain, "value") else str(opp.domain)
    domain_match = 1.0 if opp_domain in user_interests else 0.3
    breakdown["domain_match"] = domain_match

    user_level = user.academic_level.value if user.academic_level else None
    opp_level = opp.level.value if hasattr(opp.level, "value") else str(opp.level)
    if opp_level == "all" or user_level is None:
        level_match = 0.8
    elif opp_level == user_level:
        level_match = 1.0
    else:
        level_match = 0.2
    breakdown["level_match"] = level_match

    if opp.deadline:
        days_left = (opp.deadline - now).days
        if days_left < 0:
            deadline_score = 0.0
        elif days_left <= 14:
            deadline_score = 1.0
        elif days_left <= 60:
            deadline_score = 0.8
        elif days_left <= 120:
            deadline_score = 0.5
        else:
            deadline_score = 0.3
    else:
        deadline_score = 0.5
    breakdown["deadline_proximity"] = deadline_score

    preferred_locations = user.preferences.get("locations", []) if user.preferences else []
    opp_loc_type = opp.location_type.value if hasattr(opp.location_type, "value") else ""
    if not preferred_locations:
        location_score = 0.7
    elif opp_loc_type in preferred_locations or ("remote" in preferred_locations and opp_loc_type == "remote"):
        location_score = 1.0
    else:
        location_score = 0.4
    breakdown["location_preference"] = location_score

    weights = {
        "semantic_similarity": 0.35,
        "skill_overlap": 0.25,
        "domain_match": 0.15,
        "level_match": 0.10,
        "deadline_proximity": 0.08,
        "location_preference": 0.07,
    }

    score = sum(breakdown[k] * w for k, w in weights.items())
    return round(score, 4), breakdown
