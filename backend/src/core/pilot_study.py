import re

# Matches hospital names like "Pilot Study", "Pilot Study - AIIMS", "PS - AIIMS",
# "PD - AIIMS", "Pilot Deployment" — i.e. pilot-study/pilot-deployment institutes,
# which get routed to the separate pinkshield-pd.tanuh.ai portal.
_PILOT_STUDY_NAME_RE = re.compile(r"^(pilot\s*study|pilot\s*deployment|ps|pd)(\s|-|$)", re.IGNORECASE)


def is_pilot_study_hospital(hospital_name: str) -> bool:
    return bool(hospital_name) and bool(_PILOT_STUDY_NAME_RE.match(hospital_name.strip()))
