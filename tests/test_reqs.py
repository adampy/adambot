from pathlib import Path
import pkg_resources
from enum import Enum


class DEPENDENCY(Enum):
    IS_SATISFIED = 0
    IS_MISSING = 1
    IS_CONFLICTED = 2
    IS_BROKEN = 3


def get_unsat_requirements() -> list[list[str, DEPENDENCY]]:
    """
    Test that each required package is:
        - Available
        - Of the correct version where it can be determined
    """

    with open(Path(__file__).parent.with_name("requirements.txt")) as d:
        a = list(filter("".__ne__, [line.rstrip() for line in d]))

    c = [[b, DEPENDENCY.IS_SATISFIED] for b in a]
    requirements = pkg_resources.parse_requirements([str(b).replace(".git", "").split("/")[-1:][0] for b in a])
    for i, requirement in enumerate(requirements):
        requirement = str(requirement)
        try:
            pkg_resources.require(requirement)
        except pkg_resources.DistributionNotFound:
            c[i][1] = DEPENDENCY.IS_MISSING
        except pkg_resources.VersionConflict:
            c[i][1] = DEPENDENCY.IS_CONFLICTED
        except Exception:
            c[i][1] = DEPENDENCY.IS_BROKEN  # some unknown error has occurred
    return c


if __name__ == "__main__":  # can be run as independent test
    output = get_unsat_requirements()
    missing = ','.join([str(f[0]) for f in output if f[1] == DEPENDENCY.IS_MISSING])
    conflicts = ','.join([str(g[0]) for g in output if g[1] == DEPENDENCY.IS_CONFLICTED])
    broken = ','.join([str(h[0]) for h in output if h[1] == DEPENDENCY.IS_BROKEN])
    if missing:
        print(f"Missing dependencies {missing}")

    if conflicts:
        print(f"Version conflicts {conflicts}")

    if broken:
        print(f"Broken dependencies {broken}")

    if not missing and not conflicts:
        print("All dependencies satisfied!")
