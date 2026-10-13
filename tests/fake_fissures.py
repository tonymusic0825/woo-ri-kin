from datetime import datetime, timedelta, timezone

def _future_expiry(minutes=60):
    t = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")

def fake_fissure(id, node_key, mission, tier, is_hard=False):
    return {
        "id": id,
        "node": node_key,
        "nodeKey": node_key,
        "missionType": mission,
        "missionTypeKey": mission,
        "tier": tier,
        "isHard": is_hard,
        "isStorm": False,
        "expired": False,
        "expiry": _future_expiry(),
    }

# (fake fissure, should it be announced?)
TEST_CASES = [
    (fake_fissure("t1", "Teshub (Void)", "Exterminate", "Axi"), True),
    (fake_fissure("t2", "Hepit (Void)", "Capture", "Lith", is_hard=True), True),
    (fake_fissure("t3", "Tuvul Commons (Zariman)", "Void Cascade", "Omnia", is_hard=True), True),
    (fake_fissure("t4", "Tuvul Commons (Zariman)", "Void Cascade", "Omnia"), False),
    (fake_fissure("t5", "Helene (Saturn)", "Defense", "Neo", is_hard=True), True),
    (fake_fissure("t6", "Helene (Saturn)", "Defense", "Neo"), False),
    (fake_fissure("t7", "Hydron (Sedna)", "Defense", "Meso", is_hard=True), False),
    (fake_fissure("t8", "Mot (Void)", "Survival", "Axi"), False),
    (fake_fissure("t9", "Some Weird Node", "Exterminate", "Lith"), False),
]

FAKE_FISSURES = [f for f, _ in TEST_CASES]