import subprocess
import sys
from ..tests import test_reqs


def handle_dependencies():
    output = test_reqs.get_unsat_requirements()  # check for unsatisfied requirements - these need to be resolved
    missing = [str(f[0]) for f in output if f[1] == test_reqs.DEPENDENCY.IS_MISSING]
    conflicted = [str(g[0]) for g in output if g[1] == test_reqs.DEPENDENCY.IS_CONFLICTED]
    broken = [str(h[0]) for h in output if h[1] == test_reqs.DEPENDENCY.IS_BROKEN]  # package is e.g. corrupt
    not_resolved = []

    print(f"Missing dependencies {','.join(missing)}" if missing else "No missing dependencies!")
    print(f"Conflicting dependencies {','.join(conflicted)}" if conflicted else "No conflicting dependencies!")

    if missing + broken + conflicted:
        """    
        missing, broken then conflicted - then you can do all of missing and broken
        conflicted will always need input since each case is different
        """

        print("Checking for pip update, please wait...")

        outdated_packages = subprocess.check_output([sys.executable, "-m", "pip", "list", "-o"]).decode("utf-8").split("\n")  # NOTE: this is HELLA slow so it's a good job it'll mostly only be run once
        installed_packages = subprocess.check_output([sys.executable, "-m", "pip", "list"]).decode("utf-8").split("\n")
        if not [k for k in installed_packages if k.startswith("wheel ")]:
            outdated_packages.append("wheel not-installed installed")

        helpful_update = []
        for i, package in enumerate(outdated_packages):
            if package.startswith("pip ") or package.startswith("setuptools ") or package.startswith("wheel "):
                parsed = [line.rstrip() for line in list(filter("".__ne__, package.split(" ")))]
                helpful_update.append([*parsed])
        if helpful_update:
            try:
                upgrade_helpfuls = input(f"Install & upgrade the following core packages:\n\n{chr(10).join([f'{package[0]} {package[1]} -> {package[2]}' for package in helpful_update])}\n\nThis may reduce installation issues. (Y/N) ").lower()
            except EOFError:  # for remote systems where input is not allowed
                upgrade_helpfuls = "y"

            if upgrade_helpfuls == "y":
                for helpful in helpful_update:
                    try:
                        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", helpful[0], "--user"])
                    except Exception as e:
                        print(f"WARNING: Something went wrong with upgrading {helpful}\n{type(e).__name__}: {e}")
        try:
            do_missing = input("Install all missing and broken dependencies without further prompt? (Y/N) ").lower()
        except EOFError:
            do_missing = "y"

        for miss in missing + conflicted + broken:
            if miss in conflicted or do_missing != "y":
                a = input(f"Resolve dependency: {miss}? (Y/N) "
                          f"{f'{chr(10)}WARNING: This will uninstall your current version conflicting with {miss}  ' if miss in conflicted else ''}").lower()
            else:
                a = "y"

            if a == "y":
                try:
                    if miss in broken:
                        subprocess.check_call(
                            [sys.executable, "-m", "pip", "install", "--upgrade", "--force-reinstall", miss, "--user"])
                    else:
                        subprocess.check_call([sys.executable, "-m", "pip", "install", miss, "--user"])
                except Exception:
                    not_resolved.append(miss)
            else:
                not_resolved.append(miss)

    if not_resolved:
        print(f"The following missing/conflicted dependencies have not been resolved: {', '.join(not_resolved)}"
              f"{chr(10)}Exiting...")
        exit(1)


if __name__ == "__main__":
    handle_dependencies()
