#! /bin/sh
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# pylint: disable-next=anomalous-backslash-in-string
''''eval version=$( ls /usr/bin/python3.* | \
    grep '.*[0-9]$' | sort -nr -k2 -t. | head -n1 ) && \
    version=${version##/usr/bin/python3.} && [ ${version} ] && \
    [ ${version} -ge 8 ] && exec /usr/bin/python3.${version} "$0" "$@" || \
    exec /usr/bin/env python3 "$0" "$@"' #'''
# The above hack is to handle distros where /usr/bin/python3
# doesn't point to the latest version of python3 they provide

# Requires: python3 (>= 3.8)
# Requires: python3-jinja2
import os
from pathlib import Path, PosixPath
import sys
import yaml

try:  # pragma: no cover
    from jinja2 import Environment, FileSystemLoader
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import jinja2; "
             "you may need to (re-)run `cmt-install` or `pip3 install jinja2`; aborting.")


def main() -> None:
    """
    Main function for the program.
    """

    # Before doing anything else, make sure that the user is not running as root
    if os.geteuid() == 0:
        sys.exit("CRITICAL: This program should not be run as the root user; aborting.")

    # This program should be called with the path to the directory to process .j2 files in
    # as well as a path to the directory that holds the variables to use in substitutions.
    if not (2 < len(sys.argv) < 5):
        sys.exit(f"Usage: build.py TEMPLATE_DIRECTORY VARIABLE_DIRECTORY [OUTPUT_DIRECTORY]")
    template_path = sys.argv[1]
    variable_path = sys.argv[2]
    if len(sys.argv) > 3:
        output_path = sys.argv[3]
    else:
        output_path = template_path
    if template_path == variable_path:
        sys.exit(f"TEMPLATE_DIRECTORY cannot be same as VARIABLE_DIRECTORY; aborting.")
    template_entry = Path(template_path)
    variable_entry = Path(variable_path)
    output_entry = Path(output_path)

    if not template_entry.is_dir():
        sys.exit(f"{template_path} is not a directory; aborting.")
    if not variable_entry.is_dir():
        sys.exit(f"{variable_path} is not a directory; aborting.")
    if not output_entry.is_dir():
        sys.exit(f"{output_path} is not a directory; aborting.")

    # Load variables
    context = {}
    for filepath in variable_entry.iterdir():
        if not filepath.is_file() or not filepath.name.endswith(".var"):
            continue
        string: str = ""
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            tmp = f.read()
        context[filepath.name[:-len(".var")]] = tmp[:-1]

    # Initialise Jinja2
    environment = Environment(loader=FileSystemLoader(template_path), keep_trailing_newline=True)

    for filepath in template_entry.iterdir():
        if not filepath.name.endswith(".j2"):
            continue
        template = environment.get_template(filepath.name)
        dest_filename = filepath.name[:-len(".j2")]
        with open(str(PosixPath(output_path).joinpath(dest_filename)),
                  mode="w", encoding="utf-8") as f:
            f.write(template.render(context))


if __name__ == "__main__":
    main()
