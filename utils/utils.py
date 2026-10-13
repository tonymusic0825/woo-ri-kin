
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
            "Defense": ["Saturn", "Eris", "Void", "Uranus"],
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
        if planet == "Void" and missionKey in self.best_missions:
            return True

        # Void Cascade: Steel Path only
        if missionKey == "Void Cascade" and isHard:
            return True

        return False
