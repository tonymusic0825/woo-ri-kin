TRANSLATIONS = {
    # --- Relic / Fissure Tiers ---
    "Lith": "리스",
    "Meso": "메소",
    "Neo": "네오",
    "Axi": "액시",
    "Requiem": "레퀴엠",
    "Omnia": "옴니아",

    # --- Standard Mission Types ---
    "Assassination": "암살",
    "Assault": "습격",
    "Capture": "생포",
    "Defense": "방어",
    "Disruption": "교란",
    "Excavation": "발굴",
    "Extermination": "섬멸",
    "Exterminate": "섬멸",
    "Hijack": "탈취",
    "Interception": "감청",
    "Mobile Defense": "이동방어",
    "Orbiter": "오비터",
    "Rescue": "구출",
    "Sabotage": "파괴공작",
    "Spy": "첩보활동",
    "Survival": "생존",

    # --- Open World / Bounties & Specialized Missions ---
    "Free Roam": "자유탐색",
    "Bounty": "의뢰",
    "Isolation Vault": "격리 금고",
    "Alchemy": "연금술",
    "Mirror Defense": "거울 방어",
    "Void Cascade": "보이드 범람",
    "Void Flood": "보이드 홍수",
    "Void Armageddon": "보이드 아포칼립스",
    "Netracells": "네트라셀",
    "Deep Archimedea": "심층 아르키메디아",
}



def get_fissure_thumbnail(missionKey, planet, tier):

    if planet == "Void":
        return "void"

    if missionKey == "Void Cascade":
        return "cascade"

    return tier

class GoodFissures:
    def __init__(self):
        self.best_missions = {
            "Exterminate": None,
            "Capture": None,
            "Defense": ["토성", "에리스", "보이드", "천왕성"],
            "Void Cascade": None,
        }

    def parse_nodekey(self, nodeKey):
        if " (" not in nodeKey:
            return nodeKey, ""
        node, planet = nodeKey.rsplit(" (", 1)
        return node, planet.rstrip(")")

    def is_good(self, isHard, nodeKey, missionKey):
        node, planet = self.parse_nodekey(nodeKey)

        # Defense: Steel Path only, and only on the listed planets
        if missionKey == "Defense":
            return isHard and planet in self.best_missions["Defense"]

        # Exterminate / Capture / etc. in the Void (normal or Steel Path)
        if planet == "보이드" and missionKey in self.best_missions:
            return True

        # Void Cascade: Steel Path only
        if missionKey == "Void Cascade" and isHard:
            return True

        return False
