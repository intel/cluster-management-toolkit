#! /bin/sh
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
''''eval version=$( ls /usr/bin/python3.* | \
    grep '.*[0-9]$' | sort -nr -k2 -t. | head -n1 ) && \
    version=${version##/usr/bin/python3.} && [ ${version} ] && \
    [ ${version} -ge 9 ] && exec /usr/bin/python3.${version} "$0" "$@" || \
    exec /usr/bin/env python3 "$0" "$@"' #'''
# The above hack is to handle distros where /usr/bin/python3
# doesn't point to the latest version of python3 they provide

# Requires: python3 (>= 3.9)
# Requires: python3-jinja2
import os
import re
import subprocess  # nosec
from subprocess import PIPE, STDOUT  # nosec
import sys
from typing import Any, NoReturn
import yaml

PROGRAMNAME = "genstats.py"
PROGRAMVERSION = "v0.0.1"

PROGRAMDESCRIPTION = "Generate statistics that are useful for release notes"
PROGRAMAUTHORS = "Written by David Weinehall."

COPYRIGHT = "Copyright © 2025 David Weinehall"

LICENSE = "This is free software; see the source for copying conditions.  There is NO\n"
LICENSE += "warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE."



def usage() -> NoReturn:
    """
    Display usage information.
    """
    print(f"{PROGRAMNAME} TAG")
    print()
    print(PROGRAMDESCRIPTION)
    sys.exit(0)


def version() -> NoReturn:
    """
    Display version information.
    """
    print(f"{PROGRAMNAME} {PROGRAMVERSION}")
    print()
    print(COPYRIGHT)
    print(LICENSE)
    print()
    print(PROGRAMAUTHORS)

    sys.exit(0)


def main() -> None:
    """
    Main function for the program.
    """

    if "--help" in sys.argv:
        usage()

    if "--version" in sys.argv:
        version()

    if len(sys.argv) != 2:
        usage()

    tag = sys.argv[1]

    # First get the diffstat in --stat format
    args = ["/usr/bin/git", "diff", "--stat", tag]
    result = subprocess.run(args, stdout=PIPE, stderr=STDOUT, check=False)
    if result.returncode:
        print(f"{PROGRAMNAME}: \"{' '.join(args)}\" returned {result.returncode}; aborting.")
        sys.exit(result.returncode)

    output = result.stdout.decode("utf-8", errors="replace")
    stats = output.splitlines()[-1:][0].strip()

    # Now get the diffstat in --numstat format, to simplify processing
    args = ["/usr/bin/git", "diff", "--numstat", "-w", tag]
    result = subprocess.run(args, stdout=PIPE, stderr=STDOUT, check=False)
    if result.returncode:
        print(f"{PROGRAMNAME}: \"{' '.join(args)}\" returned {result.returncode}; aborting.")
        sys.exit(result.returncode)

    output = result.stdout.decode("utf-8", errors="replace")

    api_stats = {}
    file_stats = {}
    file_properties = {}

    numstat_regex = re.compile(r"(\d+)\s+(\d+)\s+(.*)")
    for line in output.splitlines():
        # numstat format: added, removed, filename (might include rename)
        if (tmp := numstat_regex.match(line)) is None:
            continue

        path = tmp[3]
        added = int(tmp[1])
        removed = int(tmp[2])
        # These are pure renames; ignore them
        if " => " in path:
            if added == removed:
                continue
            path = path.split(" => ")[-1]
        # Probably minor changes
        if added < 5 and removed < 5:
            continue
        file_stats[path] = abs(added - removed)
        # If this is a view, find the API
        if path.startswith("views/"):
            if len(path.split(".")) > 2:
                api = ".".join(path.split(".")[1:-1])
                if api not in api_stats:
                    api_stats[api] = 1
                else:
                    api_stats[api] += 1

    # Finally we want the --name-status, to know what files are new
    # (new files are not notable changes)
    args = ["/usr/bin/git", "diff", "--name-status", tag]
    result = subprocess.run(args, stdout=PIPE, stderr=STDOUT, check=False)
    if result.returncode:
        print(f"{PROGRAMNAME}: \"{' '.join(args)}\" returned {result.returncode}; aborting.")
        sys.exit(result.returncode)

    output = result.stdout.decode("utf-8", errors="replace")

    property_regex = re.compile(r"(\S+?)\s+(.*)")
    for line in output.splitlines():
        if (tmp := property_regex.match(line)) is None:
            continue
        path = tmp[2]
        if tmp[1].startswith("R"):
            # rename
            path = path.split("\t", maxsplit=1)[1].strip()
            file_properties[path] = "M"
        elif tmp[1].strip() in ("A", "D", "M"):
            # added
            file_properties[path] = tmp[1][0]

    sorted_api_stats = sorted(api_stats.items(), key=lambda x: x[1], reverse=True)
    sorted_lines_stats = sorted(file_stats.items(), key=lambda x: x[1], reverse=True)

    header = False
    for api, count in sorted_api_stats:
        if count >= 5:
            if not header:
                print("Notable view-file changes (changed API-files) include:\n")
                header = True
            print(f"* {api} ({count} changed files)")

    header = False
    parser_files_added = 0

    for path, count in sorted_lines_stats:
        if path.startswith("parsers") and file_properties[path] == "A":
            parser_files_added += 1
            continue
        if not path.startswith("views/"):
            continue
        if file_properties[path] in ("D", "A"):
            continue
        if count >= 50:
            if not header:
                print("\nNotable view-file changes (changed line count) include:\n")
                header = True
            print(f"* {path} ({count} changed lines)")

    if parser_files_added:
        print(f"\n{parser_files_added} parserfiles were added.")

    print(f"\ndiffstat: {stats}")


if __name__ == "__main__":
    main()
