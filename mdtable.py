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

# Copyright David Weinehall
# SPDX-License-Identifier: MIT

import errno
import re
import sys
from typing import Any, NoReturn

PROGRAMNAME = "mdtable.py"
PROGRAMVERSION = "v0.0.4"

PROGRAMDESCRIPTION = "Reformat tabulated data to Markdown"
PROGRAMAUTHORS = "Written by David Weinehall."

COPYRIGHT = "Copyright © 2024 David Weinehall"

LICENSE = "This is free software; see the source for copying conditions.  There is NO\n"
LICENSE += "warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE."


# pylint: disable-next=too-many-branches
def format_table(file: str, separator: str, headers: list[str], **kwargs: Any) -> None:
    """
    Format field-separated data as a Markdown table.

        Parameters:
            file (str): The name of the file to read data from
            separator (str): The separator that separates te field
            headers ([str]): The field headers
            **kwargs (dict[str, Any]): Keyword arguments
                bold_regex (str): A regular expression to check for matches to apply bold to
                italics_regex (str): A regular expression to check for matches to apply italics to
    """
    lines: str = ""
    bold_regex: str = ""
    italics_regex: str = ""
    if "bold_regex" in kwargs:
        bold_regex = kwargs["bold_regex"]
    if "italics_regex" in kwargs:
        italics_regex = kwargs["italics_regex"]

    try:
        with open(file, "r", encoding="utf-8") as f:
            lines = f.read()
    except FileNotFoundError:
        print(f"{PROGRAMNAME}: \"{file}\": File not found.")
        sys.exit(errno.ENOENT)

    column_count: int = len(headers)
    widths: list[int] = [len(header.strip()) + 2 for header in headers]
    adjusts: list[int] = [0 for header in headers]
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

        for i, column in enumerate(columns):
            adjust = 0
            if bold_regex:
                if re.match(bold_regex, column) is not None:
                    adjust = 2
            if italics_regex and not adjust:
                if re.match(italics_regex, column) is not None:
                    adjust = 1
            adjusts[i] = max(adjusts[i], adjust)
            widths[i] = max(widths[i], len(column.strip()) + adjust)

    table: str = "|"

    for i, header in enumerate(headers):
        if widths[i] == 2:
            continue
        table += " " + header.strip().strip("=").ljust(widths[i] + adjusts[i])
        table += " |"

    table += "\n|"

    for i, header in enumerate(headers):
        if widths[i] == 2:
            continue
        table += " "
        if header.startswith("="):
            if header.endswith("="):
                table += ":".ljust(widths[i] + adjusts[i] - 1, "-")
                table += ":"
            else:
                table += ":".ljust(widths[i] + adjusts[i], "-")
        elif header.endswith("="):
            table += "".ljust(widths[i] + adjusts[i] - 1, "-")
            table += ":"
        else:
            table += ":".ljust(widths[i] + adjusts[i], "-")
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

            before = ""
            after = ""
            if bold_regex:
                if re.match(bold_regex, column) is not None:
                    before = "**"
                    after = "**"
            if italics_regex and before == "":
                if re.match(italics_regex, column) is not None:
                    before = "*"
                    after = "*"

            column = column.strip()
            column = f"{before}{column}{after}"
            table += " " + column.ljust(widths[i] + adjusts[i])
            table += " |"

    print(table)


def usage() -> NoReturn:
    """
    Display usage information.
    """
    print(f"{PROGRAMNAME} [OPTIONS] FILE [=]HEADER[=]...")
    print()
    print(PROGRAMDESCRIPTION)
    print()
    print("=HEADER  will left-align column (default behaviour)")
    print(" HEADER= will right-align column")
    print("=HEADER= will center-align column")
    print()
    print("Options:")
    print("  --separator SEPARATOR    The separator used in FILE; default \"|\"")
    print("  --bold-regex REGEX       A regular expression to apply bold formatting to")
    print("  --italics-regex REGEX    A regular expression to apply italics formatting to")
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

    if len(sys.argv) == 1:
        print(f"{PROGRAMNAME}: Missing operand.")
        print(f"Try \"{PROGRAMNAME} --help\" for more information.")
        sys.exit(errno.EINVAL)

    separator: str = "|"
    bold_regex: str = ""
    italics_regex: str = ""

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
        elif opt == "--bold-regex":
            if len(sys.argv) < i + 1:
                print(f"{PROGRAMNAME}: \"--bold-regex\" missing argument.")
                print(f"Try \"{PROGRAMNAME} --help\" for more information.")
                sys.exit(errno.EINVAL)
            bold_regex = sys.argv[i]
            i += 1
        elif opt == "--italics-regex":
            if len(sys.argv) < i + 1:
                print(f"{PROGRAMNAME}: \"--italics-regex\" missing argument.")
                print(f"Try \"{PROGRAMNAME} --help\" for more information.")
                sys.exit(errno.EINVAL)
            italics_regex = sys.argv[i]
            i += 1
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

    format_table(file, separator, headers, bold_regex=bold_regex, italics_regex=italics_regex)

    return 0


if __name__ == "__main__":
    main()
