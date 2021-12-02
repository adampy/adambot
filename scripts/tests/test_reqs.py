from pathlib import Path
try:
    import pkg_resources
except ImportError:  # is part of setuptools
    import sys
    import subprocess
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', '--force-reinstall', 'setuptools', '--user'])
        print("Please restart the project for changes to take effect.")
    except Exception as e:
        print(f"Something has gone horribly wrong and the dependencies cannot be tested, please check your Python installation\n{type(e).__name__}: {e}")
    finally:
        exit(1)

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

    parents = 0
    filepath = Path(__file__)
    while filepath == Path(__file__):
        """
        Weird hack to basically keep going up a directory level until the requirements.txt is found
        This is to allow the script to run independently within any directory within the project
        """

        try:
            temp = filepath
            for i in range(parents):
                temp = getattr(temp, "parent", None)
                if temp is None:
                    print("Could not find requirements.txt, exiting...")
                    exit(1)
            temp = temp.with_name("requirements.txt")
            filepath = open(temp)
        except Exception:
            parents += 1

    with filepath as d:
        a = list(filter("".__ne__, [line.rstrip() for line in d]))
    filepath.close()

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
