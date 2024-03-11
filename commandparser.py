#! /usr/bin/env python3
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
This module parses command line options and generate helptexts
"""

import errno
import sys
from typing import cast, Callable, Dict, List, Optional, Tuple

import about

import cmtlib
from ansithemeprint import ANSIThemeString
from ansithemeprint import ansithemeprint, init_ansithemeprint, themearray_len, themearray_ljust
from cmttypes import deep_get, DictPath, FilePath
import cmtvalidators

programname = None  # pylint: disable=invalid-name
programversion = None  # pylint: disable=invalid-name
programdescription = None  # pylint: disable=invalid-name
programauthors = None  # pylint: disable=invalid-name

commandline = None  # pylint: disable=invalid-name


# pylint: disable-next=unused-argument
def __version(options: List[Tuple[str, str]], args: List[str]) -> int:
    """
    Display version information

        Parameters:
            options (list[(str, str)]): Unused
            args (dict): Unused
        Returns:
            0
    """
    ansithemeprint([ANSIThemeString(f"{programname} ", "programname"),
                    ANSIThemeString(f"{programversion}", "version")])
    ansithemeprint([ANSIThemeString(f"{about.PROGRAM_SUITE_FULL_NAME} "
                                    f"({about.PROGRAM_SUITE_NAME}) ", "programname"),
                    ANSIThemeString(f"{about.PROGRAM_SUITE_VERSION}", "version")])
    print()
    print(about.COPYRIGHT)
    print(about.LICENSE)
    print()
    print(programauthors)
    return 0


def __sub_usage(command: str) -> int:
    """
    Display usage information for a single command

        Parameters:
            command (str): The command to show help for
        Returns:
            0
    """
    assert commandline is not None

    commandinfo = {}
    headerstring = None
    command_found = False

    for _key, value in commandline.items():
        if command in deep_get(value, DictPath("command"), {}):
            commandstring = deep_get(value, DictPath("command_alias"), command)
            headerstring = [ANSIThemeString(f"{programname}", "programname"),
                            ANSIThemeString(f" {commandstring}", "command")]
            commandinfo = value
            command_found = True
            break

    if not command_found:
        ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
                        ANSIThemeString(": unrecognised command “", "default"),
                        ANSIThemeString(f"{command}", "command"),
                        ANSIThemeString("“.", "default")], stderr=True)
        ansithemeprint([ANSIThemeString("Try “", "default"),
                        ANSIThemeString(f"{programname} ", "programname"),
                        ANSIThemeString("help", "command"),
                        ANSIThemeString("“ for more information.", "default")], stderr=True)
        sys.exit(errno.EINVAL)

    if headerstring is None:
        ansithemeprint([ANSIThemeString("Error", "warning"),
                        ANSIThemeString(": Could not find help entry for command "
                                        f"{command}; aborting.", "default")], stderr=True)
        sys.exit(errno.ENOENT)

    values = deep_get(commandinfo, DictPath("values"), [])
    options = deep_get(commandinfo, DictPath("options"), [])
    description = deep_get(commandinfo, DictPath("description"), [])
    extended_description = deep_get(commandinfo, DictPath("extended_description"), [])

    if options:
        headerstring += [ANSIThemeString(" [", "separator"),
                         ANSIThemeString("OPTION", "option"),
                         ANSIThemeString("]", "separator"),
                         ANSIThemeString("...", "option")]
    if values:
        headerstring += [ANSIThemeString(" ", "separator")] + values

    ansithemeprint(headerstring)
    print()
    ansithemeprint(description)
    print()
    if extended_description:
        for line in extended_description:
            ansithemeprint([ANSIThemeString("  ", "description")] + line)
        print()

    if options:
        max_optionlen = 0
        for option, optiondata in options.items():
            optionlen = len(option) + 4 + themearray_len(deep_get(optiondata,
                                                                  DictPath("values"), ""))
            max_optionlen = max(max_optionlen, optionlen)

        ansithemeprint([ANSIThemeString("Options:", "description")])
        for option, optiondata in options.items():
            optionline = [ANSIThemeString(f"  {option}", "option")]
            values = deep_get(optiondata, DictPath("values"), [])
            description = deep_get(optiondata, DictPath("description"), [])
            extended_description = deep_get(optiondata, DictPath("extended_description"), [])

            if values:
                optionline += [ANSIThemeString(" ", "option")] + values
            pad = " ".rjust(max_optionlen - themearray_len(optionline))
            optionline += [ANSIThemeString(pad, "description")] + description
            ansithemeprint(optionline)

            pad = " ".rjust(max_optionlen)
            for extended_line in extended_description:
                ansithemeprint([ANSIThemeString(pad, "description")] + extended_line)

    return 0


# pylint: disable-next=unused-argument
def __usage(options: List[Tuple[str, str]], args: List[str]) -> int:
    """
    Display usage information

        Parameters:
            options ([(opt, optarg)]): Options to use when executing this action
            args (dict): Unused
        Returns:
            0
    """
    assert commandline is not None

    has_commands: bool = False
    has_options: bool = False
    has_args: bool = False

    output: List[List[ANSIThemeString]] = []
    output_format = "default"

    for opt, optarg in options:
        if opt == "--format":
            output_format = optarg

    maxlen = 0
    commands = []
    commandcount = 0
    globaloptioncount = 0

    for key, value in commandline.items():
        if key in ("__default", "__*", "extended_description") or key.startswith("spacer"):
            continue

        if key.startswith("__"):
            globaloptioncount += 1
        else:
            commandcount += 1

        if deep_get(commandline, DictPath(f"{key}#options")) is not None:
            has_options = True

        if deep_get(commandline, DictPath(f"{key}#max_args"), 0):
            has_args = True

    if commandcount > 3 or not globaloptioncount:
        has_commands = True
    else:
        has_options = True

    if output_format == "default":
        headerstring = [ANSIThemeString(f"{programname}", "programname")]
    elif output_format == "markdown":
        headerstring = [ANSIThemeString(f"# ___{programname}___", "default")]

    if has_commands:
        if output_format == "default":
            headerstring += [ANSIThemeString(" COMMAND", "command")]
        elif output_format == "markdown":
            headerstring += [ANSIThemeString(" __COMMAND__", "default")]

    if has_options:
        if output_format == "default":
            headerstring += [ANSIThemeString(" [", "separator"),
                             ANSIThemeString("OPTION", "option"),
                             ANSIThemeString("]", "separator"),
                             ANSIThemeString("...", "option")]
        elif output_format == "markdown":
            headerstring += [ANSIThemeString(" _\\[OPTION\\]_...", "default")]
    if has_args:
        if output_format == "default":
            headerstring += [ANSIThemeString(" [", "separator"),
                             ANSIThemeString("ARGUMENT", "argument"),
                             ANSIThemeString("]", "separator"),
                             ANSIThemeString("...", "argument")]
        elif output_format == "markdown":
            headerstring += [ANSIThemeString(" _\\[ARGUMENT\\]_...", "default")]

    output.append(headerstring)
    output.append([ANSIThemeString("", "default")])
    output.append([ANSIThemeString(programdescription, "description")])
    output.append([ANSIThemeString("", "default")])

    if has_commands:
        if output_format == "default":
            output.append([ANSIThemeString("Commands:", "description")])
        elif output_format == "markdown":
            output.append([ANSIThemeString("## Commands:", "description")])
    else:
        if output_format == "default":
            output.append([ANSIThemeString("Global Options:", "description")])
        elif output_format == "markdown":
            output.append([ANSIThemeString("## Global Options:", "description")])

    for key, value in commandline.items():
        if key in ("__default", "extended_description", "__*"):
            continue

        if key.startswith("spacer"):
            commands.append(([ANSIThemeString("  ", "default")],
                             [ANSIThemeString("  ", "default")]))
            continue

        if key == "__global_options" and has_commands:
            if output_format == "default":
                commands.append(([ANSIThemeString("Global Options:", "description")],
                                 [ANSIThemeString("", "default")]))
            elif output_format == "markdown":
                commands.append(([ANSIThemeString("### _Global Options:_", "description")],
                                 [ANSIThemeString("", "default")]))

        tmp = []
        separator = "|"
        for cmd in deep_get(value, DictPath("command"), []):
            if key.startswith("__"):
                continue

            if tmp:
                tmp.append(ANSIThemeString(f"{separator}", "separator"))
            tmp.append(ANSIThemeString(f"{cmd}", "command"))
        if tmp and output_format == "markdown":
            tmp.insert(0, ANSIThemeString("### ", "command"))

        values = deep_get(value, DictPath("values"))
        if values is not None:
            if output_format == "default":
                tmp.append(ANSIThemeString(" ", "default"))
            elif output_format == "markdown":
                tmp.append(ANSIThemeString(" _", "default"))
            for part in values:
                tmp.append(part)
            if output_format == "markdown":
                tmp.append(ANSIThemeString("_", "default"))

        tlen = themearray_len(tmp)
        maxlen = max(maxlen, tlen)
        if tlen:
            description = deep_get(value, DictPath("description"))
            if output_format == "default":
                commands.append((tmp, description))
            elif output_format == "markdown":
                description.insert(0, ANSIThemeString("#### ", "default"))
                commands.append((tmp, description))
                commands.append(([ANSIThemeString("  ", "default")],
                                 [ANSIThemeString("  ", "default")]))

        extended_description = deep_get(value, DictPath("extended_description"), [])
        if output_format == "default":
            for line in extended_description:
                commands.append(([ANSIThemeString("", "default")], line))
        elif output_format == "markdown":
            tmp_extended_description = []
            for i, line in enumerate(extended_description):
                if i:
                    tmp_extended_description += [ANSIThemeString(" ", "default")]
                tmp_extended_description += line
            if tmp_extended_description:
                commands.append(([ANSIThemeString("", "default")], tmp_extended_description))
                commands.append(([ANSIThemeString("  ", "default")],
                                 [ANSIThemeString("  ", "default")]))

        options = deep_get(value, DictPath("options"), [])
        for option in options:
            indent = ""
            if tmp:
                indent = "  "
            tmp2 = [ANSIThemeString(f"{indent}", "option")]
            if isinstance(option, tuple):
                for _opt in option:
                    # The first string is the initial indentation
                    if len(tmp2) > 1:
                        tmp2.append(ANSIThemeString("  ", "separator"))
                    if output_format == "default":
                        tmp2.append(ANSIThemeString(f"{_opt}", "option"))
                    elif output_format == "markdown":
                        tmp2.append(ANSIThemeString(f"__{_opt}__", "option"))
            elif key.startswith("__"):
                if output_format == "default":
                    tmp2.append(ANSIThemeString(f"  {option}", "option"))
                elif output_format == "markdown":
                    tmp2.append(ANSIThemeString(f"  __{option}__", "option"))
            else:
                if output_format == "default":
                    tmp2.append(ANSIThemeString(f"{option}", "option"))
                elif output_format == "markdown":
                    tmp2.append(ANSIThemeString(f"__{option}__", "option"))
            values = deep_get(value, DictPath(f"options#{option}#values"))
            if values is not None:
                tmp2.append(ANSIThemeString(" ", "default"))
                if output_format == "markdown":
                    tmp2.append(ANSIThemeString("_", "default"))

                for part in values:
                    tmp2.append(part)
                if output_format == "markdown":
                    tmp2.append(ANSIThemeString("_", "default"))
            tlen = themearray_len(tmp2)
            maxlen = max(maxlen, tlen)
            description = deep_get(value, DictPath(f"options#{option}#description"))
            if indent:
                description = [ANSIThemeString(indent, "default")] + description
            if output_format == "markdown":
                description.append(ANSIThemeString("  ", "default"))
            commands.append((tmp2, description))
            extended_description = deep_get(value,
                                            DictPath("options#{option}#extended_description"), [])
            for line in extended_description:
                if indent:
                    commands.append(([ANSIThemeString("", "default")],
                                     [ANSIThemeString(indent, "default")] + line))
                else:
                    commands.append(([ANSIThemeString("", "default")], line))

    # cmd[0]: formatted cmd/option
    # cmd[1]: formatted description
    for cmd in commands:
        if output_format == "default":
            if themearray_len(cmd[0]) > 27 or \
                    themearray_len(cmd[0]) + 2 + themearray_len(cmd[1]) > 79 or \
                    themearray_len(cmd[1]) > 51:
                output.append(cmd[0])
                string = themearray_ljust([ANSIThemeString("", "default")], 29) + cmd[1]
                output.append(string)
                # if themearray_len(string) > 79:
                #     sys.exit(f"FIXME: {themearray_len(string)} > 79 characters; "
                #               "please file a bug report.")
            else:
                string = themearray_ljust(cmd[0], 29) + cmd[1]
                output.append(string)
        elif output_format == "markdown":
            output.append(cmd[0])
            output.append(cmd[1])

    if "extended_description" in commandline:
        output.append([ANSIThemeString("", "default")])
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
                        segment = ANSIThemeString(string, themeref)
                elif themeref in ("argument", "note", "path", "version"):
                    stripped, lcount = cmtlib.lstrip_count(string, " ")
                    stripped, rcount = cmtlib.rstrip_count(stripped, " ")
                    if stripped and not stripped.startswith("_") and not stripped.endswith("_"):
                        string = "".ljust(lcount) + f"_{stripped}_" + "".ljust(rcount)
                        segment = ANSIThemeString(string, themeref)
                # elif themeref not in ("command", "default",
                #                       "description", "programname", "separator"):
                #     sys.exit(themeref)
                tmpline.append(segment)
            line = tmpline
        ansithemeprint(line)

    return 0


# pylint: disable-next=unused-argument
def __command_usage(options: List[Tuple[str, str]], args: List[str]) -> int:
    """
    Display usage information for a single command

        Parameters:
            options (list[(str, str)]): Unused
            args (dict): The command to show help for
        Returns:
            0
    """
    assert commandline is not None

    if not args:
        return __usage(options, args)
    return __sub_usage(args[0])


def __find_command(__commandline: Dict, arg: str) -> \
        Tuple[str, Optional[Callable[[Tuple[str, str], List[str]], None]],
              str, int, int, List[Dict], List[Dict]]:
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
                min_args = deep_get(value, DictPath("min_args"))
                max_args = deep_get(value, DictPath("max_args"))
                if min_args is None:
                    min_args = len(required_args)
                if max_args is None:
                    max_args = min_args + len(optional_args)
                break
        if command is not None:
            break

    return commandname, command, key, min_args, max_args, required_args, optional_args


COMMANDLINEDEFAULTS = {
    "Help": {
        "command": ["help"],
        "values": [ANSIThemeString("COMMAND", "argument")],
        "description": [ANSIThemeString("Display help about ", "description"),
                        ANSIThemeString("COMMAND", "argument"),
                        ANSIThemeString(" and exit", "description")],
        "options": {
            "--format": {
                "values": [ANSIThemeString("FORMAT", "argument")],
                "description": [ANSIThemeString("Output the help as ", "description"),
                                ANSIThemeString("FORMAT", "argument"),
                                ANSIThemeString(" instead", "description")],
                "extended_description": [
                    [ANSIThemeString("Valid formats are:", "description")],
                    [ANSIThemeString("default", "argument"),
                     ANSIThemeString(", ", "separator"),
                     ANSIThemeString("markdown", "argument")],
                ],
                "requires_arg": True,
                "validation": {
                    "validator": "allowlist",
                    "allowlist": ["default", "markdown"],
                },
            },
        },
        "min_args": 0,
        "max_args": 1,
        "callback": __command_usage,
    },
    "Help2": {
        "command": ["help", "--help"],
        "description": [ANSIThemeString("Display this help and exit", "description")],
        "options": {
            "--format": {
                "values": [ANSIThemeString("FORMAT", "argument")],
                "description": [ANSIThemeString("Output the help as ", "description"),
                                ANSIThemeString("FORMAT", "argument"),
                                ANSIThemeString(" instead", "description")],
                "extended_description": [
                    [ANSIThemeString("Valid formats are:", "description")],
                    [ANSIThemeString("default", "argument"),
                     ANSIThemeString(", ", "separator"),
                     ANSIThemeString("markdown", "argument")],
                ],
                "requires_arg": True,
                "validation": {
                    "validator": "allowlist",
                    "allowlist": ["default", "markdown"],
                },
            },
        },
        "min_args": 0,
        "max_args": 0,
        "callback": __usage,
    },
    "Version": {
        "command": ["version", "--version"],
        "description": [ANSIThemeString("Output version information and exit", "description")],
        "min_args": 0,
        "max_args": 0,
        "callback": __version,
    },
}


# pylint: disable-next=line-too-long
def parse_commandline(__programname: str, __programversion: str,
                      __programdescription: str, __programauthors: str,
                      argv: List[str],
                      __commandline: Dict,
                      default_command: Optional[str] = None,
                      theme: Optional[FilePath] = None) -> Tuple[Callable,
                                                                 List[Tuple[str, str]],
                                                                 List[str]]:
    """
    Parse the command line

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

    i = 1

    programname = __programname
    cmtvalidators.set_programname(programname)
    programversion = __programversion
    programdescription = __programdescription
    programauthors = __programauthors

    commandline = {**__commandline, **COMMANDLINEDEFAULTS}

    if theme is not None:
        init_ansithemeprint(theme)

    commandname = None
    command = None
    key = None
    options: List[Tuple[str, str]] = []
    args: List[str] = []
    min_args = 0
    max_args = 0

    while i < len(argv):
        if "\x00" in argv[i]:
            ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
                            ANSIThemeString(": argument “", "default"),
                            ANSIThemeString(argv[i].replace("\x00", "<NUL>"), "command"),
                            ANSIThemeString("“ contains NUL-bytes (replaced here);\n", "default"),
                            ANSIThemeString("this is either a programming error, a system error, "
                                            "file or memory corruption, ", "default"),
                            ANSIThemeString("or a deliberate attempt to bypass "
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
                    ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
                                    ANSIThemeString(": unrecognised command “", "default"),
                                    ANSIThemeString(f"{argv[i]}", "command"),
                                    ANSIThemeString("“.", "default")], stderr=True)
                    ansithemeprint([ANSIThemeString("Try “", "default"),
                                    ANSIThemeString(f"{programname} ", "programname"),
                                    ANSIThemeString("help", "command"),
                                    ANSIThemeString("“ for more information.", "default")],
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

            if len(args) > 0:
                # I came here to have an argument, but this is an option!
                ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
                                ANSIThemeString(": option “", "default"),
                                ANSIThemeString(f"{argv[i]}", "option"),
                                ANSIThemeString("“ found after arguments.", "default")],
                               stderr=True)
                ansithemeprint([ANSIThemeString("Try “", "default"),
                                ANSIThemeString(f"{programname} ", "programname"),
                                ANSIThemeString("help", "command"),
                                ANSIThemeString("“ for more information.", "default")],
                               stderr=True)
                sys.exit(errno.EINVAL)
            else:
                # Is this option valid for this command?
                match = None
                __key = key
                for opt in deep_get(commandline, DictPath(f"{__key}#options"), {}):
                    if isinstance(opt, str) and argv[i] == opt or \
                            isinstance(opt, tuple) and argv[i] in opt:
                        match = opt
                        break
                # Check global options
                if match is None:
                    for opt in deep_get(commandline, DictPath("__global_options#options"), {}):
                        if isinstance(opt, str) and \
                                argv[i] == opt or isinstance(opt, tuple) and argv[i] in opt:
                            __key = "__global_options"
                            match = opt
                            break

                if match is None:
                    ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
                                    ANSIThemeString(": “", "default"),
                                    ANSIThemeString(f"{commandname}", "command"),
                                    ANSIThemeString("“ does not support option “", "default"),
                                    ANSIThemeString(f"{argv[i]}", "option"),
                                    ANSIThemeString("“.", "default")], stderr=True)
                    ansithemeprint([ANSIThemeString("Try “", "default"),
                                    ANSIThemeString(f"{programname} ", "programname"),
                                    ANSIThemeString("help", "command"),
                                    ANSIThemeString("“ for more information.", "default")],
                                   stderr=True)
                    sys.exit(errno.EINVAL)
                else:
                    arg = None
                    option = match

                    # Does this option require arguments?
                    requires_arg = deep_get(commandline,
                                            DictPath(f"{__key}#options#{option}#requires_arg"),
                                            False)

                    if requires_arg:
                        i += 1
                        if i >= len(argv):
                            ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
                                            ANSIThemeString(": “", "default"),
                                            ANSIThemeString(f"{option}", "option"),
                                            ANSIThemeString("“ requires an argument.", "default")],
                                           stderr=True)
                            ansithemeprint([ANSIThemeString("Try “", "default"),
                                            ANSIThemeString(f"{programname} ", "programname"),
                                            ANSIThemeString("help", "command"),
                                            ANSIThemeString("“ for more information.", "default")],
                                           stderr=True)
                            sys.exit(errno.EINVAL)
                        arg = argv[i]

                        # Validate the option argument
                        validator_options = \
                            deep_get(commandline,
                                     DictPath(f"{__key}#options#{option}#validation"), {})

                        # validate_argument() will terminate by default if validation fails
                        _result = cmtvalidators.validate_argument(arg,
                                                                  [ANSIThemeString(f"{option}",
                                                                                   "option")],
                                                                  validator_options)
                    options.append((option, arg))
        else:
            args.append(argv[i])
        i += 1

    if command is None and default_command is not None:
        commandname, command, key, min_args, max_args, required_args, \
            optional_args = __find_command(commandline, default_command)

    if not max_args and args:
        ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
                        ANSIThemeString(": “", "default"),
                        ANSIThemeString(f"{commandname}", "command"),
                        ANSIThemeString("“ does not accept arguments.", "default")], stderr=True)
        ansithemeprint([ANSIThemeString("Try “", "default"),
                        ANSIThemeString(f"{programname} ", "programname"),
                        ANSIThemeString("help", "command"),
                        ANSIThemeString("“ for more information.", "default")], stderr=True)
        sys.exit(errno.EINVAL)
    elif len(args) < min_args and min_args != max_args:
        ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
                        ANSIThemeString(": “", "default"),
                        ANSIThemeString(f"{commandname}", "command"),
                        ANSIThemeString(f"“ requires at least {min_args} arguments.", "default")],
                       stderr=True)
        ansithemeprint([ANSIThemeString("Try “", "default"),
                        ANSIThemeString(f"{programname} ", "programname"),
                        ANSIThemeString("help", "command"),
                        ANSIThemeString("“ for more information.", "default")], stderr=True)
        sys.exit(errno.EINVAL)
    elif len(args) != min_args and min_args == max_args:
        ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
                        ANSIThemeString(": “", "default"),
                        ANSIThemeString(f"{commandname}", "command"),
                        ANSIThemeString(f"“ requires exactly {min_args} arguments.", "default")],
                       stderr=True)
        ansithemeprint([ANSIThemeString("Try “", "default"),
                        ANSIThemeString(f"{programname} ", "programname"),
                        ANSIThemeString("help", "command"),
                        ANSIThemeString("“ for more information.", "default")], stderr=True)
        sys.exit(errno.EINVAL)
    elif len(args) > max_args:
        ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
                        ANSIThemeString(": “", "default"),
                        ANSIThemeString(f"{commandname}", "command"),
                        ANSIThemeString(f"“ requires at most {max_args} arguments.", "default")],
                       stderr=True)
        ansithemeprint([ANSIThemeString("Try “", "default"),
                        ANSIThemeString(f"{programname} ", "programname"),
                        ANSIThemeString("help", "command"),
                        ANSIThemeString("“ for more information.", "default")], stderr=True)
        sys.exit(errno.EINVAL)

    # The command was called without any command and no default was defined; this is an error
    if command is None:
        ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
                        ANSIThemeString(": missing operand.", "default")], stderr=True)
        ansithemeprint([ANSIThemeString("Try “", "default"),
                        ANSIThemeString(f"{programname} ", "programname"),
                        ANSIThemeString("help", "command"),
                        ANSIThemeString("“ for more information.", "default")],
                       stderr=True)
        sys.exit(errno.EINVAL)
    else:
        # Are there implicit options?
        options += deep_get(commandline, DictPath(f"{key}#implicit_options"), [])

    # Validate the args against required_args and optional_args
    for i, arg in enumerate(required_args + optional_args):
        if i >= len(args):
            break

        # Validate the argument
        validator_options = deep_get(arg, DictPath("validation"), {})

        # validate_argument() will terminate by default if validation fails
        _result = cmtvalidators.validate_argument(args[i], arg["string"], validator_options)

    options.append(("__commandname", cast(str, commandname)))

    return command, options, args
