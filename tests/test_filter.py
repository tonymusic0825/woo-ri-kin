from utils.utils import GoodFissures
from tests.fake_fissures import TEST_CASES

gf = GoodFissures()
passed = 0

for f, expected in TEST_CASES:
    result = gf.is_good(f["isHard"], f["nodeKey"], f["missionTypeKey"])
    ok = result == expected
    passed += ok
    print(f"{'PASS' if ok else 'FAIL'}  {f['nodeKey']:<26} {f['missionTypeKey']:<13} "
          f"SP={str(f['isHard']):<5}  expected={expected}  got={result}")

print(f"\n{passed}/{len(TEST_CASES)} passed")