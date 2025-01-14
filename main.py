import os
import subprocess
import json
from collections import defaultdict
from alive_progress import alive_bar
from termcolor import colored, cprint
import profanity_check

TITLE = """
 ▄▄▄· ▄• ▄▌▄▄▄▄▄       ▐▄▄▄▄• ▄▌·▄▄▄▄   ▄▄ • ▄▄▄ .
▐█ ▀█ █▪██▌•██  ▪       ·███▪██▌██▪ ██ ▐█ ▀ ▪▀▄.▀·
▄█▀▀█ █▌▐█▌ ▐█.▪ ▄█▀▄ ▪▄ ███▌▐█▌▐█· ▐█▌▄█ ▀█▄▐▀▀▪▄
▐█ ▪▐▌▐█▄█▌ ▐█▌·▐█▌.▐▌▐▌▐█▌▐█▄█▌██. ██ ▐█▄▪▐█▐█▄▄▌
 ▀  ▀  ▀▀▀  ▀▀▀  ▀█▄▀▪ ▀▀▀• ▀▀▀ ▀▀▀▀▀• ·▀▀▀▀  ▀▀▀ 
"""


# Only accepts GitHub Repo urls so far...
def verify_url(url: str):
    rules = [
        # Add rules here
        url.startswith("https://github.com/"),
        " " not in url,
        "\t" not in url,
        "\n" not in url,
        "\r" not in url
    ]

    return all(rules)


# remove temp folder
def remove_temp_dir():
    if os.path.exists("temp/"):
        s = subprocess.Popen("rm -rf temp", shell=True)
        s.wait()

# Creates empty temp folder


def create_temp_dir():
    remove_temp_dir()

    if os.path.exists("temp/"):
        create_temp_dir()
    else:
        os.mkdir("temp")


# Prints the title
def title():
    subprocess.run(["clear"])
    cprint(TITLE)

    print(
        f"Made with {colored('*magic*', attrs=['bold'])} by Nathan the intern.\n")


# Clones a git repository to temp
def clone_repo(url):
    if not verify_url(url):
        cprint("Link is not valid!", "red")
        return

    create_temp_dir()

    return subprocess.run([f"GIT_ASKPASS=true git clone {url} temp/"], capture_output=True, shell=True)


# Get the number of commits in temp
def get_commit_n():
    try:
        count = int(subprocess.run(
            ["cd temp; git rev-list --all --count"],
            capture_output=True,
            shell=True).stdout)
    except ValueError:
        count = 0

    return count


def get_first_commit_date():
    try:
        date = subprocess.run(
            ["cd temp; git log --pretty=format:%cd --date=format-local:'%Y-%m-%d %I:%M:%S %p' | tail -1"],
            capture_output=True, shell=True).stdout.rstrip()
    except ValueError:
        date = 0

    return date


def get_last_commit_date():
    try:
        date = subprocess.run(
            ["cd temp; git log -1 --format=%cd --date=format-local:'%Y-%m-%d %I:%M:%S %p' | tail -1"],
            capture_output=True, shell=True).stdout.strip()
    except ValueError:
        date = 0

    return date


def get_most_additions():
    try:
        date = subprocess.run(
            ["cd temp; git log --stat --oneline | grep 'insertions' | sort -nr -k4 | head -1"],
            capture_output=True, shell=True).stdout.strip()
    except ValueError:
        date = 0

    return date


def get_file_stats(file):
    suspicious = []
    line_number = 0

    try:
        for line in file:
            line_number += 1
            if (p := profanity_check.predict_prob([line])[0]) > 0.7:
                suspicious.append(
                    f"{line_number} - {p} - {line.strip()}")
    except (UnicodeDecodeError, OSError):
        pass

    return (suspicious, line_number)


# Walks through temp folder and returns statistics
# If nothing is suspicious, dictionary is empty
def walk_temp():
    profanity_log = dict()
    total_lines = 0

    for dir in os.walk("temp"):
        if any(bad in dir[0].lower() for bad in
               [".git", "package.json",
                "babel.config.js",
                "package-lock.json", ".lock"
                ".png", ".jpg", "jpeg", ".svg", ".webp", ".gif",
                "node_modules", "venv", ".vscode",
                "venv", ".expo", ".pem",
                "__pycache__", ".ico", ".csv", ".json"]
               ):
            continue

        # Check for suspicious lines
        for file in dir[2]:
            with open(dir[0] + '/' + file) as live_file:
                suspicious, line_number = get_file_stats(live_file)
                total_lines += line_number
                if len(suspicious) > 0:
                    profanity_log[dir[0] + '/' + file] = suspicious

    commit_n = get_commit_n()
    if commit_n < 10 or len(profanity_log) > 0:
        profanity_log['commit_number'] = commit_n
        profanity_log['lines_checked'] = total_lines

    return profanity_log


def create_csv(urls):
    results = defaultdict(dict)

    cprint("✔ Cloning repositories...", "green")

    with alive_bar(len(urls), spinner="waves2", ctrl_c=False) as progress:
        for url in urls:
            url = url.strip()

            repo_name = url.split('/')[4][:-4]
            repo_name_padded = "↓ " + (repo_name + " "*100)[:15]
            progress.title(colored(repo_name_padded, "yellow"))

            if (clone_result := clone_repo(url.strip())).returncode != 0:
                results[url]["error"] = clone_result.stderr.decode("utf-8")
                progress()
                continue

            repo_name_padded = "⌕ " + (repo_name + " "*100)[:15]
            progress.title(colored(repo_name_padded, "cyan"))
            if len(faults := walk_temp()) > 0:
                results[url]["flagged_files"] = faults

            # First commit
            results[url]["first_commit"] = get_first_commit_date().decode("utf-8")
            # Last commit
            results[url]["last_commit"] = get_last_commit_date().decode("utf-8")
            # Most additions
            results[url]["most_additions"] = get_most_additions().decode("utf-8")

            progress()

        repo_name_padded = "✔ " + (repo_name + " "*100)[:15]
        progress.title(colored(repo_name_padded, "green"))

    print()
    print(
        f"{len([r for r in results if 'flagged_files' in r])} projects with profanity.")
    export = json.dumps(results, indent=2)
    with open("output.json", "w") as live_file:
        live_file.write(export)
        cprint("Wrote to output.json", "blue")

    remove_temp_dir()


if __name__ == "__main__":
    title()
    cprint("✔ Opening input file...", "green")
    with open("input.txt", "r") as urls:
        create_csv(urls.readlines())
