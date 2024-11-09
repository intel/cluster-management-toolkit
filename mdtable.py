#! /bin/sh
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# pylint: disable-next=anomalous-backslash-in-string
''''eval version=$( ls /usr/bin/python3.* | \
    grep '.*[0-9]$' | sort -nr -k2 -t. | head -n1 ) && \
    version=${version##/usr/bin/python3.} && [ ${version} ] && \
    [ ${version} -ge 9 ] && exec /usr/bin/python3.${version} "$0" "$@" || \
    exec /usr/bin/env python3 "$0" "$@"' #'''
# The above hack is to handle distros where /usr/bin/python3
# doesn't point to the latest version of python3 they provide

# Requires: python3 (>= 3.9)

# Copyright David Weinehall
# SPDX-License-Identifier: MIT

import errno
import sys
from typing import NoReturn

PROGRAMNAME = "mdtable.py"
PROGRAMVERSION = "v0.0.1"

PROGRAMDESCRIPTION = "Reformat tabulated data to as Markdown"
PROGRAMAUTHORS = "Written by David Weinehall."

COPYRIGHT = "Copyright © 2024 David Weinehall"

LICENSE = "This is free software; see the source for copying conditions.  There is NO\n"
LICENSE += "warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE."


def format_table(file: str, separator: str, headers: list[str]) -> None:
    lines: str = ""

    try:
        with open(file, "r") as f:
            lines = f.read()
    except FileNotFoundError:
        print(f"{PROGRAMNAME}: \"{file}\": File not found.")
        sys.exit(errno.ENOENT)

    column_count: int = len(headers)
    widths: list[int] = [len(header.strip()) + 2 for header in headers]
    i: int = 0

    # First check for consistency and tabulate column widths
    for i, line in enumerate(lines.split("\n")):
        # End when we encounter an empty line
        if not line:
            break

        columns: list[str] = line.split(separator)
        if column_count != len(columns):
            if i == 0:
                print(f"{PROGRAMNAME}: Inconsistent input data.")
                print(f"{column_count} headers were provided, "
                      f"while line {i} has {len(columns)} columns.")
            else:
                print(f"{PROGRAMNAME}: Inconsistent input data.")
                print(f"The first line has {column_count} columns, "
                      f"while line {i} has {len(columns)} columns.")
            sys.exit(errno.EINVAL)

        widths = [max(widths[i], len(column.strip())) for i, column in enumerate(columns)]

    table: str = "|"

    for i, header in enumerate(headers):
        if widths[i] == 2:
            continue
        table += " " + header.strip().ljust(widths[i])
        table += " |"

    table += "\n|"

    for i, header in enumerate(headers):
        if widths[i] == 2:
            continue
        table += " "
        table += "".ljust(widths[i], "-")
        table += " |"

    # Now format the data
    for line in lines.split("\n"):
        if not line:
            break

        columns = line.split(separator)
        table += "\n|"
        for i, column in enumerate(columns):
            if widths[i] == 2:
                continue

            table += " " + column.strip().ljust(widths[i])
            table += " |"

    print(table)


def usage() -> NoReturn:
    print(f"{PROGRAMNAME} [OPTIONS] FILE HEADER...")
    print()
    print(PROGRAMDESCRIPTION)
    print()
    print("Options:")
    print("  --separator SEPARATOR    The separator used in FILE; default \"|\"")
    sys.exit(0)


def version() -> NoReturn:
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

    if len(sys.argv) == 1:
        print(f"{PROGRAMNAME}: Missing operand.")
        print(f"Try \"{PROGRAMNAME} --help\" for more information.")
        sys.exit(errno.EINVAL)

    separator: str = "|"

    i = 1

    while i < len(sys.argv):
        opt = sys.argv[i]
        if not opt.startswith("--"):
            break
        i += 1
        if opt == "--help":
            usage()
        elif opt == "--version":
            version()
        elif opt == "--separator":
            if len(sys.argv) < i + 1:
                print(f"{PROGRAMNAME}: \"--separator\" missing argument.")
                print(f"Try \"{PROGRAMNAME} --help\" for more information.")
                sys.exit(errno.EINVAL)
            separator = sys.argv[i]
            i += 1

    if len(sys.argv) - i < 1:
        print(f"{PROGRAMNAME}: Missing FILE.")
        print(f"Try \"{PROGRAMNAME} --help\" for more information.")
        sys.exit(errno.EINVAL)

    file = sys.argv[i]

    if len(sys.argv) - 2 < 1:
        print(f"{PROGRAMNAME}: Missing HEADER...")
        print(f"Try \"{PROGRAMNAME} --help\" for more information.")
        sys.exit(errno.EINVAL)

    headers = sys.argv[i + 1:]

    format_table(file, separator, headers)

    return 0


if __name__ == "__main__":
    main()
