#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
This module parses command line options and generate helptexts
"""

import errno
import sys
from typing import Any, Optional, TypedDict
from collections.abc import Callable

from clustermanagementtoolkit import about

from clustermanagementtoolkit import cmtlib

from clustermanagementtoolkit.ansithemeprint import ANSIThemeStr
from clustermanagementtoolkit.ansithemeprint import ansithemeprint, init_ansithemeprint
from clustermanagementtoolkit.ansithemeprint import themearray_len, themearray_ljust

from clustermanagementtoolkit.cmttypes import deep_get, DictPath, FilePath

from clustermanagementtoolkit import cmtvalidators

programname: str = ""
programversion: str = ""
programdescription: str = ""
programauthors: str = ""


class ValidationTypeOptional(TypedDict, total=False):
    """
    Optional fields in the TypedDict for argument validation.

        Parameters:
            allowlist ([str]): A list of explicitly allowed values used by the allowlist validator
            regex (str): A regular expression used by the regex validator
            list_separator (str): A separator to use to split the argument into a list
            valid_range (([Optional[int], Optional[int]])): A range of valid values
    """
    allowlist: list[str]
    regex: str
    list_separator: str
    valid_range: tuple[Optional[int], Optional[int]]


class ValidationType(ValidationTypeOptional):
    """
    A TypedDict for argument validation.

        Parameters:
            validator (str): The name of the validator to use
    """
    validator: str


class ArgumentWithDefaultType(TypedDict, total=False):
    """
    Argument TypedDict to use when a default argument can be valid.

        Parameters:
            default (str): The default value for an argument
    """
    default: str


class ArgumentWithOptionalDefaultType(ArgumentWithDefaultType):
    """
    Argument TypedDict to use with optional default argument; to be used
    when the argument is optional, since mandatory arguments cannot have a default.

        Parameters:
            name (str)   # The name of the argument
            string ([ANSIThemeStr]): An ANSIThemeArray with a description of the argument
            validation  (ValidationType): Information about validation to perform on the argument
    """
    name: str
    string: list[ANSIThemeStr]
    validation: ValidationType


class ArgumentType(TypedDict):
    """
    The TypedDict for use with required arguments.

        Parameters:
            name (str)   # The name of the argument
            string ([ANSIThemeStr]): An ANSIThemeArray with a description of the argument
            validation  (ValidationType): Information about validation to perform on the argument
    """
    name: str
    string: list[ANSIThemeStr]
    validation: ValidationType


class OptionTypeOptional(TypedDict, total=False):
    """
    Optional fields that are part of the TypedDict for options.

        Parameters:
            extended_description ([[ANSIThemeStr]]): A multi-line description of the option
            requires_arg (bool): Does the option require an argument?
            values  ([ANSIThemeStr]): An ANSIThemeArray with ARGUMENTs to the option
            validation (ValidationType): Information about validation to perform on the argument
    """
    extended_description: list[list[ANSIThemeStr]]
    requires_arg: bool
    values: list[ANSIThemeStr]
    validation: ValidationType


class OptionType(OptionTypeOptional):
    """
    A TypedDict for options.

        Parameters:
            description ([ANSIThemeStr]): A description of the option
    """
    description: list[ANSIThemeStr]


class CommandTypeOptional(TypedDict, total=False):
    """
    Optional fields for the TypedDict for commands.

        Parameters:
            command_alias (str): A string with an alias for the command
            values ([ANSIThemeStr]): An ANSIThemeArray with ARGUMENTs to the command
            options (dict[str, Optional[OptionType]]): A dict of command options
            implicit_options: ([(str, Any)]): A list of implicit options
            extended_description ([[ANSIThemeStr]]): A multi-line description of the command
    """
    command_alias: str
    values: list[ANSIThemeStr]
    options: dict[str, OptionType]
    implicit_options: list[tuple[str, Any]]
    extended_description: list[list[ANSIThemeStr]]


class CommandType(CommandTypeOptional):
    """
    A TypedDict for commands.

        Parameters:
            command ([str]): A list of command aliases
            description ([ANSIThemeStr]): An ANSIThemeArray with a description of the command
            required_args ([ArgumentType]): A list of required arguments
            optional_args ([ArgumentWithOptionalDefaultType]): A list of optional arguments
            callback (Optional[Callable]): The callback to use
    """
    command: list[str]
    description: list[ANSIThemeStr]
    required_args: list[ArgumentType]
    optional_args: list[ArgumentWithOptionalDefaultType]
    callback: Optional[Callable]


commandline: dict[str, Any] = {}


# pylint: disable-next=unused-argument
def __version(options: list[tuple[str, str]], args: list[str]) -> int:
    """
    Display version information.

        Parameters:
            options ([(str, str)]): Unused
            args (dict): Unused
        Returns:
            (int): 0
    """
    ansithemeprint([ANSIThemeStr(f"{programname} ", "programname"),
                    ANSIThemeStr(f"{programversion}", "version")])
    ansithemeprint([ANSIThemeStr(f"{about.PROGRAM_SUITE_FULL_NAME} "
                                 f"({about.PROGRAM_SUITE_NAME}) ", "programname"),
                    ANSIThemeStr(f"{about.PROGRAM_SUITE_VERSION}", "version")])
    print()
    print(about.COPYRIGHT)
    print(about.LICENSE)
    print()
    print(programauthors)
    return 0


# pylint: disable-next=too-many-locals,too-many-branches
def __sub_usage(command: str) -> int:
    """
    Display usage information for a single command.

        Parameters:
            command (str): The command to show help for
        Returns:
            (int): 0
    """
    assert commandline is not None

    commandinfo = {}
    headerstring: list[ANSIThemeStr] = []
    command_found = False

    for _key, value in commandline.items():
        if command in deep_get(value, DictPath("command"), {}):
            commandstring = deep_get(value, DictPath("command_alias"), command)
            headerstring = [ANSIThemeStr(f"{programname}", "programname"),
                            ANSIThemeStr(f" {commandstring}", "command")]
            commandinfo = value
            command_found = True
            break

    if not command_found:
        ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                        ANSIThemeStr(": unrecognised command “", "default"),
                        ANSIThemeStr(f"{command}", "command"),
                        ANSIThemeStr("“.", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("Try “", "default"),
                        ANSIThemeStr(f"{programname} ", "programname"),
                        ANSIThemeStr("help", "command"),
                        ANSIThemeStr("“ for more information.", "default")], stderr=True)
        sys.exit(errno.EINVAL)

    values = deep_get(commandinfo, DictPath("values"), [])
    options = deep_get(commandinfo, DictPath("options"), [])
    description = deep_get(commandinfo, DictPath("description"), [])
    extended_description = deep_get(commandinfo, DictPath("extended_description"), [])

    if not description and not extended_description:
        ansithemeprint([ANSIThemeStr("Error", "warning"),
                        ANSIThemeStr(": Could not find help entry for command "
                                     f"{command}; aborting.", "default")], stderr=True)
        sys.exit(errno.ENOENT)

    if options:
        headerstring += [ANSIThemeStr(" [", "separator"),
                         ANSIThemeStr("OPTION", "option"),
                         ANSIThemeStr("]", "separator"),
                         ANSIThemeStr("...", "option")]
    if values:
        headerstring += [ANSIThemeStr(" ", "separator")] + values

    ansithemeprint(headerstring)
    print()
    ansithemeprint(description)
    print()
    if extended_description:
        for line in extended_description:
            ansithemeprint([ANSIThemeStr("  ", "description")] + line)
        print()

    if options:
        max_optionlen = 0
        for option, optiondata in options.items():
            optionlen = len(option) + 4 + themearray_len(deep_get(optiondata,
                                                                  DictPath("values"), ""))
            max_optionlen = max(max_optionlen, optionlen)

        ansithemeprint([ANSIThemeStr("Options:", "description")])
        for option, optiondata in options.items():
            optionline = [ANSIThemeStr(f"  {option}", "option")]
            values = deep_get(optiondata, DictPath("values"), [])
            description = deep_get(optiondata, DictPath("description"), [])
            extended_description = deep_get(optiondata, DictPath("extended_description"), [])

            if values:
                optionline += [ANSIThemeStr(" ", "option")] + values
            pad = " ".rjust(max_optionlen - themearray_len(optionline))
            optionline += [ANSIThemeStr(pad, "description")] + description
            ansithemeprint(optionline)

            pad = " ".rjust(max_optionlen)
            for extended_line in extended_description:
                ansithemeprint([ANSIThemeStr(pad, "description")] + extended_line)

    return 0


# pylint: disable-next=unused-argument,too-many-locals,too-many-branches,too-many-statements
def __usage(options: list[tuple[str, str]], args: list[str]) -> int:
    """
    Display usage information.

        Parameters:
            options ([(str, str)]): Options to use when executing this action
            args (dict): Unused
        Returns:
            (int): 0
    """
    assert commandline is not None

    has_commands: bool = False
    has_options: bool = False
    has_args: bool = False

    output: list[list[ANSIThemeStr]] = []
    output_format: str = "default"

    for opt, optarg in options:
        if opt == "--format":
            output_format = optarg

    maxlen = 0
    commands = []
    commandcount = 0
    globaloptioncount = 0

    # Do we have any arguments?
    for key, value in commandline.items():
        required_args_ = deep_get(commandline, DictPath(f"{key}#required_args"), [])
        optional_args_ = deep_get(commandline, DictPath(f"{key}#optional_args"), [])
        if (required_args_ or optional_args_
                or deep_get(commandline, DictPath(f"{key}#max_args"), 0)) and key != "Help":
            has_args = True
            break

    # Do we have any options?
    for key, value in commandline.items():
        if key in ("__default", "__*", "extended_description") or key.startswith("spacer"):
            continue

        if key.startswith("__"):
            globaloptioncount += 1
        else:
            commandcount += 1

        key_options = deep_get(commandline, DictPath(f"{key}#options"))
        if key_options is not None and key not in ("Help", "Help2"):
            has_options = True

    # Do we have any commands?
    if commandcount > 3:
        has_commands = True

    if not has_commands:
        commandline.pop("Help", None)

    if output_format == "default":
        headerstring = [ANSIThemeStr(f"{programname}", "programname")]
    elif output_format == "markdown":  # pragma: no branch
        headerstring = [ANSIThemeStr(f"# ___{programname}___", "default")]

    if has_commands:
        if output_format == "default":
            headerstring += [ANSIThemeStr(" COMMAND", "command")]
        elif output_format == "markdown":  # pragma: no branch
            headerstring += [ANSIThemeStr(" __COMMAND__", "default")]

    if has_options:
        if output_format == "default":
            headerstring += [ANSIThemeStr(" [", "separator"),
                             ANSIThemeStr("OPTION", "option"),
                             ANSIThemeStr("]", "separator"),
                             ANSIThemeStr("...", "option")]
        elif output_format == "markdown":  # pragma: no branch
            headerstring += [ANSIThemeStr(" _\\[OPTION\\]_...", "default")]
    if has_args:
        if output_format == "default":
            headerstring += [ANSIThemeStr(" [", "separator"),
                             ANSIThemeStr("ARGUMENT", "argument"),
                             ANSIThemeStr("]", "separator"),
                             ANSIThemeStr("...", "argument")]
        elif output_format == "markdown":  # pragma: no branch
            headerstring += [ANSIThemeStr(" _\\[ARGUMENT\\]_...", "default")]

    output.append(headerstring)
    output.append([ANSIThemeStr("", "default")])
    output.append([ANSIThemeStr(programdescription, "description")])
    output.append([ANSIThemeStr("", "default")])

    if has_commands:
        if output_format == "default":
            output.append([ANSIThemeStr("Commands:", "description")])
        elif output_format == "markdown":  # pragma: no branch
            output.append([ANSIThemeStr("## Commands:", "description")])
    elif globaloptioncount:
        if output_format == "default":
            output.append([ANSIThemeStr("Global Options:", "description")])
        elif output_format == "markdown":  # pragma: no branch
            output.append([ANSIThemeStr("## Global Options:", "description")])

    for key, value in commandline.items():
        if key in ("__default", "extended_description", "__*"):
            continue

        if key.startswith("spacer"):
            commands.append(([ANSIThemeStr("  ", "default")],
                             [ANSIThemeStr("  ", "default")]))
            continue

        if key == "__global_options" and has_commands:
            if output_format == "default":
                commands.append(([ANSIThemeStr("Global Options:", "description")],
                                 [ANSIThemeStr("", "default")]))
            elif output_format == "markdown":  # pragma: no branch
                commands.append(([ANSIThemeStr("### _Global Options:_", "description")],
                                 [ANSIThemeStr("", "default")]))

        tmp: list[ANSIThemeStr] = []
        separator = "|"
        for cmd in deep_get(value, DictPath("command"), []):
            if key.startswith("__"):
                continue

            if tmp:
                tmp.append(ANSIThemeStr(f"{separator}", "separator"))
            tmp.append(ANSIThemeStr(f"{cmd}", "command"))
        if tmp and output_format == "markdown":  # pragma: no branch
            tmp.insert(0, ANSIThemeStr("### ", "command"))

        values = deep_get(value, DictPath("values"))
        if values is not None:
            if output_format == "default":
                tmp.append(ANSIThemeStr(" ", "default"))
            elif output_format == "markdown":  # pragma: no branch
                tmp.append(ANSIThemeStr(" _", "default"))
            for part in values:
                tmp.append(part)
            if output_format == "markdown":
                tmp.append(ANSIThemeStr("_", "default"))

        tlen = themearray_len(tmp)
        maxlen = max(maxlen, tlen)
        if tlen:
            description = deep_get(value, DictPath("description"))
            if output_format == "default":
                commands.append((tmp, description))
            elif output_format == "markdown":  # pragma: no branch
                description.insert(0, ANSIThemeStr("#### ", "default"))
                commands.append((tmp, description))
                commands.append(([ANSIThemeStr("  ", "default")],
                                 [ANSIThemeStr("  ", "default")]))

        extended_description = deep_get(value, DictPath("extended_description"), [])
        if output_format == "default":
            for line in extended_description:
                commands.append(([ANSIThemeStr("", "default")], line))
        elif output_format == "markdown":  # pragma: no branch
            tmp_extended_description = []
            for i, line in enumerate(extended_description):
                if i:
                    tmp_extended_description += [ANSIThemeStr(" ", "default")]
                tmp_extended_description += line
            if tmp_extended_description:
                commands.append(([ANSIThemeStr("", "default")], tmp_extended_description))
                commands.append(([ANSIThemeStr("  ", "default")],
                                 [ANSIThemeStr("  ", "default")]))

        options = deep_get(value, DictPath("options"), [])
        for option in options:
            indent = ""
            if tmp:
                indent = "  "
            tmp2 = [ANSIThemeStr(f"{indent}", "option")]
            if key.startswith("__"):
                if output_format == "default":
                    tmp2.append(ANSIThemeStr(f"  {option}", "option"))
                elif output_format == "markdown":  # pragma: no branch
                    tmp2.append(ANSIThemeStr(f"  __{option}__", "option"))
            else:
                if output_format == "default":
                    tmp2.append(ANSIThemeStr(f"{option}", "option"))
                elif output_format == "markdown":  # pragma: no branch
                    tmp2.append(ANSIThemeStr(f"__{option}__", "option"))
            values = deep_get(value, DictPath(f"options#{option}#values"))
            if values is not None:
                tmp2.append(ANSIThemeStr(" ", "default"))
                if output_format == "markdown":
                    tmp2.append(ANSIThemeStr("_", "default"))

                for part in values:
                    tmp2.append(part)
                if output_format == "markdown":
                    tmp2.append(ANSIThemeStr("_", "default"))
            tlen = themearray_len(tmp2)
            maxlen = max(maxlen, tlen)
            description = deep_get(value, DictPath(f"options#{option}#description"))
            if indent:
                description = [ANSIThemeStr(indent, "default")] + description
            if output_format == "markdown":
                description.append(ANSIThemeStr("  ", "default"))
            commands.append((tmp2, description))
            extended_description = deep_get(value,
                                            DictPath(f"options#{option}#extended_description"), [])
            for line in extended_description:
                if indent:
                    commands.append(([ANSIThemeStr("", "default")],
                                     [ANSIThemeStr(indent, "default")] + line))
                else:
                    commands.append(([ANSIThemeStr("", "default")], line))

    # cmd[0]: formatted cmd/option
    # cmd[1]: formatted description
    for cmd in commands:
        if output_format == "default":
            if themearray_len(cmd[0]) > 27 or \
                    themearray_len(cmd[0]) + 2 + themearray_len(cmd[1]) > 79 or \
                    themearray_len(cmd[1]) > 51:
                output.append(cmd[0])
                string = themearray_ljust([ANSIThemeStr("", "default")], 29) + cmd[1]
                output.append(string)
                # if themearray_len(string) > 79:
                #     sys.exit(f"FIXME: {themearray_len(string)} > 79 characters; "
                #               "please file a bug report.")
            else:
                string = themearray_ljust(cmd[0], 29) + cmd[1]
                output.append(string)
        elif output_format == "markdown":  # pragma: no branch
            output.append(cmd[0])
            output.append(cmd[1])

    if "extended_description" in commandline:
        output.append([ANSIThemeStr("", "default")])
        for line in deep_get(commandline, DictPath("extended_description"), []):
            output.append(line)

    # Post-processing filtering
    for line in output:
        if output_format == "markdown":
            tmpline = []
            for segment in line:
                themeref = segment.get_themeref()
                string = str(segment)
                string = string.replace("<", "\\<")
                string = string.replace(">", "\\>")
                string = string.replace("`", "\\`")
                if themeref in ("option", "emphasis"):
                    stripped, lcount = cmtlib.lstrip_count(string, " ")
                    stripped, rcount = cmtlib.rstrip_count(stripped, " ")
                    if stripped and not stripped.startswith("__") and not stripped.endswith("__"):
                        string = "".ljust(lcount) + f"__{stripped}__" + "".ljust(rcount)
                        segment = ANSIThemeStr(string, themeref)
                elif themeref in ("argument", "note", "path", "version"):
                    stripped, lcount = cmtlib.lstrip_count(string, " ")
                    stripped, rcount = cmtlib.rstrip_count(stripped, " ")
                    if stripped and not stripped.startswith("_") and not stripped.endswith("_"):
                        string = "".ljust(lcount) + f"_{stripped}_" + "".ljust(rcount)
                        segment = ANSIThemeStr(string, themeref)
                # elif themeref not in ("command", "default",
                #                       "description", "programname", "separator"):
                #     sys.exit(themeref)
                tmpline.append(segment)
            line = tmpline
        ansithemeprint(line)

    return 0


def __command_usage(options: list[tuple[str, str]], args: list[str]) -> int:
    """
    Display usage information for a single command.

        Parameters:
            options ([(str, str)]): Unused
            args (dict): The command to show help for
        Returns:
            (int): 0
    """
    assert commandline is not None

    if not args:
        return __usage(options, args)
    return __sub_usage(args[0])


def __find_command(__commandline: dict[str, Any], arg: str) -> \
        tuple[str, Optional[Callable[[tuple[str, str], list[str]], None]],
              str, int, int, list[dict], list[dict]]:
    command = None
    commandname = ""
    required_args = []
    optional_args = []
    min_args = 0
    max_args = 0
    key = ""

    for key, value in __commandline.items():
        if key == "extended_description":
            continue

        for cmd in deep_get(value, DictPath("command"), []):
            if cmd == arg:
                commandname = cmd
                command = deep_get(value, DictPath("callback"))
                required_args = deep_get(value, DictPath("required_args"), [])
                optional_args = deep_get(value, DictPath("optional_args"), [])
                min_args = len(required_args)
                max_args = min_args + len(optional_args)
                break
        if command is not None:
            break

    return commandname, command, key, min_args, max_args, required_args, optional_args


COMMANDLINEDEFAULTS: dict[str, CommandType] = {
    "Help": {
        "command": ["help"],
        "values": [ANSIThemeStr("COMMAND", "argument")],
        "description": [ANSIThemeStr("Display help about ", "description"),
                        ANSIThemeStr("COMMAND", "argument"),
                        ANSIThemeStr(" and exit", "description")],
        "options": {
            "--format": {
                "values": [ANSIThemeStr("FORMAT", "argument")],
                "description": [ANSIThemeStr("Output the help as ", "description"),
                                ANSIThemeStr("FORMAT", "argument"),
                                ANSIThemeStr(" instead", "description")],
                "extended_description": [
                    [ANSIThemeStr("Valid formats are:", "description")],
                    [ANSIThemeStr("default", "argument"),
                     ANSIThemeStr(", ", "separator"),
                     ANSIThemeStr("markdown", "argument")],
                ],
                "requires_arg": True,
                "validation": {
                    "validator": "allowlist",
                    "allowlist": ["default", "markdown"],
                },
            },
        },
        "required_args": [],
        "optional_args": [
            {
                "name": "command",
                "string": [
                    ANSIThemeStr("COMMAND", "argument")],
                "validation": {
                    "validator": "regex",
                    "regex": r"^[a-z][a-z0-9-]*$",
                },
            },
        ],
        "callback": __command_usage,
    },
    "Help2": {
        "command": ["help", "--help"],
        "description": [ANSIThemeStr("Display this help and exit", "description")],
        "options": {
            "--format": {
                "values": [ANSIThemeStr("FORMAT", "argument")],
                "description": [ANSIThemeStr("Output the help as ", "description"),
                                ANSIThemeStr("FORMAT", "argument"),
                                ANSIThemeStr(" instead", "description")],
                "extended_description": [
                    [ANSIThemeStr("Valid formats are:", "description")],
                    [ANSIThemeStr("default", "argument"),
                     ANSIThemeStr(", ", "separator"),
                     ANSIThemeStr("markdown", "argument")],
                ],
                "requires_arg": True,
                "validation": {
                    "validator": "allowlist",
                    "allowlist": ["default", "markdown"],
                },
            },
        },
        "required_args": [],
        "optional_args": [],
        "callback": __usage,
    },
    "Version": {
        "command": ["version", "--version"],
        "description": [ANSIThemeStr("Output version information and exit", "description")],
        "required_args": [],
        "optional_args": [],
        "callback": __version,
    },
}


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def parse_commandline(__programname: str, __programversion: str,
                      __programdescription: str, __programauthors: str,
                      argv: list[str],
                      __commandline: dict[str, Any],
                      default_command: Optional[str] = None,
                      theme: Optional[FilePath] = None) -> tuple[Callable,
                                                                 list[tuple[str, str]],
                                                                 list[str]]:
    """
    Parse the command line.

        Parameters:
            __programname (str): The name of the program
                                 (used in usage and version information, and in error messages)
            __programversion (str): The version of the program (used in version information)
            __programdescription (str): The description of the program (used in usage information)
            __programauthors (str): The authors of the program (used in version information)
            argv ([str]): The command line from sys.argv
            __commandline (dict): The command line struct
            default_command (str): The command to run if none was provided
            theme (FilePath): The theme to use
        Returns:
            (Callable, [(str, str)], [str]):
                (Callable): The command to call
                ([(str, str)]): The options to pass to the command
                ([str]): The arguments to pass to the command
    """
    global commandline  # pylint: disable=global-statement
    global programname  # pylint: disable=global-statement
    global programversion  # pylint: disable=global-statement
    global programdescription  # pylint: disable=global-statement
    global programauthors  # pylint: disable=global-statement

    i: int = 1

    programname = __programname
    cmtvalidators.set_programname(programname)
    programversion = __programversion
    programdescription = __programdescription
    programauthors = __programauthors

    commandline = {**__commandline, **COMMANDLINEDEFAULTS}

    if theme is not None:
        init_ansithemeprint(theme)

    commandname = ""
    command = None
    key = None
    options: list[tuple[str, str]] = []
    args: list[str] = []
    min_args = 0
    max_args = 0

    # pylint: disable-next=too-many-nested-blocks
    while i < len(argv):
        if "\x00" in argv[i]:
            ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                            ANSIThemeStr(": argument “", "default"),
                            ANSIThemeStr(argv[i].replace("\x00", "<NUL>"), "command"),
                            ANSIThemeStr("“ contains NUL-bytes (replaced here);\n", "default"),
                            ANSIThemeStr("this is either a programming error, a system error, "
                                         "file or memory corruption, ", "default"),
                            ANSIThemeStr("or a deliberate attempt to bypass "
                                         "security; aborting.", "default")], stderr=True)
            sys.exit(errno.EINVAL)

        # Have we got a command to execute?
        if command is None:
            commandname, command, key, min_args, max_args, \
                required_args, optional_args = __find_command(commandline, argv[i])

            if command is None:
                if default_command is not None:
                    commandname, command, key, min_args, max_args, required_args, \
                        optional_args = __find_command(commandline, default_command)
                elif "__*" in commandline:
                    commandname, command, key, min_args, max_args, required_args, \
                        optional_args = __find_command(commandline, "*")

                if command is None:
                    ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                                    ANSIThemeStr(": unrecognised command “", "default"),
                                    ANSIThemeStr(f"{argv[i]}", "command"),
                                    ANSIThemeStr("“.", "default")], stderr=True)
                    ansithemeprint([ANSIThemeStr("Try “", "default"),
                                    ANSIThemeStr(f"{programname} ", "programname"),
                                    ANSIThemeStr("help", "command"),
                                    ANSIThemeStr("“ for more information.", "default")],
                                   stderr=True)
                    sys.exit(errno.EINVAL)

                # If we defaulted we do not want to consume any options
                continue
        # OK, we have a command, time to check for options
        elif argv[i].startswith("-"):
            # All commands except [--]help and [--]version have their own help pages
            if argv[i] == "--help" and \
                    commandname not in ("--help", "help", "--version", "version") and \
                    not commandname.startswith("__"):
                __sub_usage(commandname)
                sys.exit()

            if args:
                # I came here to have an argument, but this is an option!
                ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                                ANSIThemeStr(": option “", "default"),
                                ANSIThemeStr(f"{argv[i]}", "option"),
                                ANSIThemeStr("“ found after arguments.", "default")],
                               stderr=True)
                ansithemeprint([ANSIThemeStr("Try “", "default"),
                                ANSIThemeStr(f"{programname} ", "programname"),
                                ANSIThemeStr("help", "command"),
                                ANSIThemeStr("“ for more information.", "default")],
                               stderr=True)
                sys.exit(errno.EINVAL)
            else:
                # Is this option valid for this command?
                match = None
                __key = key
                for opt in deep_get(commandline, DictPath(f"{__key}#options"), {}):
                    if isinstance(argv[i], str) and argv[i] == opt:
                        match = opt
                        break
                # Check global options
                if match is None:
                    for opt in deep_get(commandline, DictPath("__global_options#options"), {}):
                        if isinstance(argv[i], str) and argv[i] == opt:
                            __key = "__global_options"
                            match = opt
                            break

                if match is None:
                    ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                                    ANSIThemeStr(": “", "default"),
                                    ANSIThemeStr(f"{commandname}", "command"),
                                    ANSIThemeStr("“ does not support option “", "default"),
                                    ANSIThemeStr(f"{argv[i]}", "option"),
                                    ANSIThemeStr("“.", "default")], stderr=True)
                    ansithemeprint([ANSIThemeStr("Try “", "default"),
                                    ANSIThemeStr(f"{programname} ", "programname"),
                                    ANSIThemeStr("help", "command"),
                                    ANSIThemeStr("“ for more information.", "default")],
                                   stderr=True)
                    sys.exit(errno.EINVAL)
                else:
                    arg: str = ""
                    option: str = match

                    # Does this option require arguments?
                    requires_arg = deep_get(commandline,
                                            DictPath(f"{__key}#options#{option}#requires_arg"),
                                            False)

                    if requires_arg:
                        i += 1
                        if i >= len(argv):
                            ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                                            ANSIThemeStr(": “", "default"),
                                            ANSIThemeStr(f"{option}", "option"),
                                            ANSIThemeStr("“ requires an argument.", "default")],
                                           stderr=True)
                            ansithemeprint([ANSIThemeStr("Try “", "default"),
                                            ANSIThemeStr(f"{programname} ", "programname"),
                                            ANSIThemeStr("help", "command"),
                                            ANSIThemeStr("“ for more information.", "default")],
                                           stderr=True)
                            sys.exit(errno.EINVAL)
                        arg = argv[i]

                        # Validate the option argument
                        validator_options = \
                            deep_get(commandline,
                                     DictPath(f"{__key}#options#{option}#validation"), {})

                        # validate_argument() will terminate by default if validation fails
                        _result = \
                            cmtvalidators.validate_argument(arg,
                                                            [ANSIThemeStr(f"{option}", "option")],
                                                            validator_options)
                    options.append((option, arg))
        else:
            args.append(argv[i])
        i += 1

    if command is None and default_command is not None:
        commandname, command, key, min_args, max_args, required_args, \
            optional_args = __find_command(commandline, default_command)

    if not max_args and args:
        ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                        ANSIThemeStr(": “", "default"),
                        ANSIThemeStr(f"{commandname}", "command"),
                        ANSIThemeStr("“ does not accept arguments.", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("Try “", "default"),
                        ANSIThemeStr(f"{programname} ", "programname"),
                        ANSIThemeStr("help", "command"),
                        ANSIThemeStr("“ for more information.", "default")], stderr=True)
        sys.exit(errno.EINVAL)
    elif len(args) < min_args and min_args != max_args:
        ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                        ANSIThemeStr(": “", "default"),
                        ANSIThemeStr(f"{commandname}", "command"),
                        ANSIThemeStr(f"“ requires at least {min_args} arguments.", "default")],
                       stderr=True)
        ansithemeprint([ANSIThemeStr("Try “", "default"),
                        ANSIThemeStr(f"{programname} ", "programname"),
                        ANSIThemeStr("help", "command"),
                        ANSIThemeStr("“ for more information.", "default")], stderr=True)
        sys.exit(errno.EINVAL)
    elif len(args) != min_args and min_args == max_args:
        ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                        ANSIThemeStr(": “", "default"),
                        ANSIThemeStr(f"{commandname}", "command"),
                        ANSIThemeStr(f"“ requires exactly {min_args} arguments.", "default")],
                       stderr=True)
        ansithemeprint([ANSIThemeStr("Try “", "default"),
                        ANSIThemeStr(f"{programname} ", "programname"),
                        ANSIThemeStr("help", "command"),
                        ANSIThemeStr("“ for more information.", "default")], stderr=True)
        sys.exit(errno.EINVAL)
    elif len(args) > max_args:
        ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                        ANSIThemeStr(": “", "default"),
                        ANSIThemeStr(f"{commandname}", "command"),
                        ANSIThemeStr(f"“ requires at most {max_args} arguments.", "default")],
                       stderr=True)
        ansithemeprint([ANSIThemeStr("Try “", "default"),
                        ANSIThemeStr(f"{programname} ", "programname"),
                        ANSIThemeStr("help", "command"),
                        ANSIThemeStr("“ for more information.", "default")], stderr=True)
        sys.exit(errno.EINVAL)

    # The command was called without any command and no default was defined; this is an error
    if command is None:
        ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                        ANSIThemeStr(": missing operand.", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("Try “", "default"),
                        ANSIThemeStr(f"{programname} ", "programname"),
                        ANSIThemeStr("help", "command"),
                        ANSIThemeStr("“ for more information.", "default")],
                       stderr=True)
        sys.exit(errno.EINVAL)
    else:
        # Are there implicit options?
        options += deep_get(commandline, DictPath(f"{key}#implicit_options"), [])

    # Validate the args against required_args and optional_args
    for i, argdict in enumerate(required_args + optional_args):
        if i >= len(args):
            break

        # Validate the argument
        validator_options = deep_get(argdict, DictPath("validation"), {})

        # validate_argument() will terminate by default if validation fails
        _result = cmtvalidators.validate_argument(args[i], argdict["string"], validator_options)

    options.append(("__commandname", commandname))

    return command, options, args
