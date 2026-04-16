import argparse
import os
import subprocess

if __name__ == "__main__":
    pid = os.getpid()
    guessed_path = f"/tmp/guessed_{pid}"
    declared_path = f"/tmp/declared_{pid}"

    parser = argparse.ArgumentParser(
        description=(
            "Uses pipreqs to identify potential requirements"
            "mismatches with a specific requirements file"
        )
    )
    parser.add_argument("project_root")
    parser.add_argument("requirements_file")
    args = parser.parse_args()

    result = subprocess.run(
        ["pipreqs", "--print", args.project_root], capture_output=True, text=True
    )
    guessed_reqs = result.stdout.split("\n")
    guessed_reqs = [r.lower().replace("_", "-") for r in guessed_reqs]
    guessed_reqs = sorted(guessed_reqs)

    with open(args.requirements_file) as f:
        declared_reqs = [line.strip() for line in f.readlines()]
        declared_reqs = sorted(declared_reqs)

    with open(guessed_path, "w") as f:
        f.writelines([f"{req}\n" for req in guessed_reqs if len(req) > 0])

    with open(declared_path, "w") as f:
        f.writelines([f"{req}\n" for req in declared_reqs])

    result = subprocess.run(
        ["diff", "-u", declared_path, guessed_path], capture_output=True, text=True
    )
    if len(result.stdout) > 0:
        print("\nFound the following potential requirements mismatches:")
        print(result.stdout)

    os.remove(guessed_path)
    os.remove(declared_path)
