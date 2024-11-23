#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Print themed strings to the console
"""

import errno
import getpass
import copy
from pathlib import Path, PurePath
import subprocess  # nosec
import sys
from typing import Any, Optional, Union
from collections.abc import Sequence

try:
    # python3-yaml is installed by cmt-install; thus we cannot rely on yaml being importable
    # pylint: disable-next=unused-import
    import yaml  # noqa
    from clustermanagementtoolkit.cmtio_yaml import secure_read_yaml
    USE_FALLBACK_THEME = False
except ModuleNotFoundError:
    USE_FALLBACK_THEME = True

from clustermanagementtoolkit.cmtpaths import SYSTEM_DEFAULT_THEME_FILE

from clustermanagementtoolkit.cmttypes import deep_get, DictPath, FilePath
from clustermanagementtoolkit.cmttypes import FilePathAuditError, ProgrammingError, LogLevel
from clustermanagementtoolkit.cmttypes import SecurityChecks, SecurityPolicy, SecurityStatus

from clustermanagementtoolkit import cmtio


class ANSIThemeStr:
    """
    A themed string for printing with ANSI control codes

        Parameters:
            string: A string
            themeref: The reference to use when doing a looking in themes
    """

    def __init__(self, string: str, themeref: str) -> None:
        """
        Initialize an ANSIThemeStr

            Parameters:
                string (str): The string to format
                themeref (str): The reference to the formatting to use
        """
        if not isinstance(string, str) or not isinstance(themeref, str):
            raise TypeError("ANSIThemeStr only accepts (str, str); "
                            f"received ({type(string)}, {type(themeref)})")
        self.string = str(string)
        self.themeref = str(themeref)

    def __str__(self) -> str:
        """
        Return the string part of the ANSIThemeStr

            Returns:
                (str): The string part of the ANSIThemeStr
        """
        return self.string

    def __len__(self) -> int:
        """
        Return the length to the ANSIThemeStr

            Returns:
                (int): The length of the ANSIThemeStr
        """
        return len(self.string)

    def __repr__(self) -> str:
        return f"ANSIThemeStr(string=\"{self.string}\", themeref=\"{self.themeref}\")"

    def format(self, themeref: str) -> "ANSIThemeStr":
        """
        Apply new formatting to the ANSIThemeStr

            Parameters:
                (str): The reference to the formatting part of the ANSIThemeStr
            Returns:
                (ANSIThemeStr): The ANSIThemeStr with new formatting applied
        """
        if not isinstance(themeref, str):
            raise TypeError("ANSIThemeStr().format() only accepts (str); "
                            f"received ({type(themeref)})")
        self.themeref = str(themeref)
        return self

    def get_themeref(self) -> str:
        """
        Return the reference to the formatting part of the ANSIThemeStr

            Returns:
                (str): The reference to the formatting part of the ANSIThemeStr
        """
        return self.themeref

    def upper(self) -> "ANSIThemeStr":
        """
        Return the upper-case version of the ANSIThemeStr

            Returns:
                (ANSIThemeStr): The upper-case version of the ANSIThemeStr
        """
        return ANSIThemeStr(self.string.upper(), self.themeref)

    def lower(self) -> "ANSIThemeStr":
        """
        Return the lower-case version of the ANSIThemeStr

            Returns:
                (ANSIThemeStr): The lower-case version of the ANSIThemeStr
        """
        return ANSIThemeStr(self.string.lower(), self.themeref)

    def capitalize(self) -> "ANSIThemeStr":
        """
        Return the capitalised version of the ANSIThemeStr

            Returns:
                (ANSIThemeStr): The capitalized version of the ANSIThemeStr
        """
        return ANSIThemeStr(self.string.capitalize(), self.themeref)

    def __eq__(self, themestring: Any) -> bool:
        """
        Compare two ANSIThemeStrs and return True if both string and formatting are identical

            Parameters:
                themestring (ANSIThemeStr): The ANSIThemeStr to compare to
            Returns:
                (bool): True if the strings match, False if not
        """
        return self.string == themestring.string and self.themeref == themestring.themeref

    @classmethod
    def tuplelist_to_ansithemearray(cls, msg: list[tuple[str, str]]) -> list["ANSIThemeStr"]:
        """
        Given a structured message return its ANSIThemeArray representation

            Parameters:
                msg ([(str, str)]): A structured message for format
            Returns:
                (ANSIThemeArray): The ANSIThemeArray representations of the message
            Raises:
                ProgrammingError(TypeError): Invalid indata
        """
        themearray = []

        if not isinstance(msg, list):
            raise ProgrammingError("ANSIThemeStr.tuplelist_to_ansithemearray() "
                                   "called with invalid argument(s):\n"
                                   f"msg={msg} (type: {type(msg)}, expected: list)",
                                   subexception=TypeError,
                                   severity=LogLevel.ERR,
                                   formatted_msg=[[("ANSIThemeStr.tuplelist_to_ansithemearray()",
                                                    "emphasis"),
                                                   (" called with invalid argument(s):", "error")],
                                                  [("msg = ", "default"),
                                                   (f"{msg}", "argument"),
                                                   (" (type: ", "default"),
                                                   (f"{type(msg)}", "argument"),
                                                   (", expected: ", "default"),
                                                   ("list", "argument"),
                                                   (")", "default")]])

        for item in msg:
            if not (isinstance(item, tuple) and len(item) == 2
                    and isinstance(item[0], str) and isinstance(item[1], str)):
                raise ProgrammingError("ANSIThemeStr.tuplelist_to_ansithemearray() "
                                       "called with invalid argument(s):\n"
                                       f"msg={msg} (type: {type(msg)}, expected: list[(str, str)])",
                                       subexception=TypeError,
                                       severity=LogLevel.ERR,
                                       formatted_msg=[
                                           [("ANSIThemeStr.tuplelist_to_ansithemearray()",
                                             "emphasis"),
                                            (" called with invalid argument(s):", "error")],
                                           [("msg = ", "default"),
                                            (f"{msg}", "argument"),
                                            (" (type: ", "default"),
                                            (f"{type(msg)}", "argument"),
                                            (", expected: ", "default"),
                                            ("list", "argument"),
                                            (")", "default")]])
            themearray.append(ANSIThemeStr(item[0], item[1]))
        return themearray

    @classmethod
    def format_error_msg(cls, msg: list[list[tuple[str, str]]]) -> \
            tuple[str, list[list["ANSIThemeStr"]]]:
        """
        Given a structured error message return both its string and ANSIThemeArray representations;
        the main use-case for this is to feed into enhanced exceptions that accept
        both formatted and plaintext strings.

            Parameters:
                msg ([[(str, str)]]): A structured message for format
            Returns:
                (str, [ANSIThemeArray]): The string and ANSIThemeArray
                                         representations of the message
            Raises:
                ProgrammingError(TypeError): Invalid indata
        """
        joined_strings = []
        themearray_list = []

        if not isinstance(msg, list):
            raise ProgrammingError("ANSIThemeStr.format_error_msg() "
                                   "called with invalid argument(s):\n"
                                   f"msg={msg} (type: {type(msg)}, expected: list)",
                                   subexception=TypeError,
                                   severity=LogLevel.ERR,
                                   formatted_msg=[[("ANSIThemeStr.format_error_msg()",
                                                    "emphasis"),
                                                   (" called with invalid argument(s):", "error")],
                                                  [("msg = ", "default"),
                                                   (f"{msg}", "argument"),
                                                   (" (type: ", "default"),
                                                   (f"{type(msg)}", "argument"),
                                                   (", expected: ", "default"),
                                                   ("list", "argument"),
                                                   (")", "default")]])

        for line in msg:
            if not isinstance(line, list):
                raise ProgrammingError("ANSIThemeStr.format_error_msg() "
                                       "called with invalid argument(s):\n"
                                       f"line={line} (type: {type(line)}, expected: list)",
                                       subexception=TypeError,
                                       severity=LogLevel.ERR,
                                       formatted_msg=[[("ANSIThemeStr.format_error_msg()",
                                                        "emphasis"),
                                                       (" called with invalid argument(s):",
                                                        "error")],
                                                      [("line=", "default"),
                                                       (f"{line}", "argument"),
                                                       (" (type: ", "default"),
                                                       (f"{type(line)}", "argument"),
                                                       (", expected: ", "default"),
                                                       ("list", "argument"),
                                                       (")", "default")]])

            themearray = []
            joined_string = ""
            for items in line:
                if not (isinstance(items, tuple) and len(items) == 2
                        and isinstance(items[0], str) and isinstance(items[1], str)):
                    raise ProgrammingError("ANSIThemeStr.format_error_msg() "
                                           "called with invalid argument(s):\n"
                                           f"items={items} (type: {type(items)}, "
                                           "expected: tuple(str, str))",
                                           subexception=TypeError,
                                           severity=LogLevel.ERR,
                                           formatted_msg=[[("ANSIThemeStr.format_error_msg()",
                                                            "emphasis"),
                                                           (" called with invalid argument(s):",
                                                            "error")],
                                                          [("items=", "default"),
                                                           (f"{items}", "argument"),
                                                           (" (type: ", "default"),
                                                           (f"{type(items)}", "argument"),
                                                           (", expected: ", "default"),
                                                           ("tuple(str, str)", "argument"),
                                                           (")", "default")]])

                string, formatting = items
                joined_string += string
                themearray.append(ANSIThemeStr(string, formatting))
            themearray_list.append(copy.deepcopy(themearray))
            joined_strings.append(joined_string)

        return "\n".join(joined_strings), themearray_list


theme: Optional[dict] = None
themepath: Optional[FilePath] = None


FALLBACK_THEME = {
    "term": {
        "default": "\033[0m",                           # reset
        "programname": "\033[1;37m",                    # white + bright
        "version": "\033[0;32m",                        # green
        "candidateversion": "\033[1;36m",               # cyan + bright
        # Having command the same colour as action is probably not a good choice
        "command": "\033[1;36m",                        # cyan + bright
        "option": "\033[0;36m",                         # cyan
        "argument": "\033[0;32m",                       # green
        "separator": "\033[38;5;240m",                  # grey + dim
        "description": "\033[0m",                       # reset
        "hostname": "\033[1;37m",                       # white + bright
        "path": "\033[0;36m",                           # cyan
        "url": "\033[1;4;37m",                          # white + bright + underline
        "header": "\033[0;4;37m",                       # white + underline
        "underline": "\033[0;4;37m",                    # white + underline
        "emphasis": "\033[1;37m",                       # white + bright
        "skip": "\033[38;5;240m\033[1m",                # grey + dim + bold
        "ok": "\033[1;37m",                             # white + bright
        "notok": "\033[1;31m",                          # red + bright
        "success": "\033[1;32m",                        # green + bright
        "note": "\033[0;32m",                           # green
        "error": "\033[1;31m",                          # red + bright
        "warning": "\033[1;33m",                        # yellow + bright
        "critical": "\033[1;41;93m",                    # red + bright + inverted
        "errorvalue": "\033[0;31m",                     # red
        "phase": "\033[1;33m",                          # yellow + bright
        "action": "\033[1;36m",                         # cyan + bright
        "play": "\033[0;36m",                           # cyan
        "none": "\033[38;5;240m\033[1m",                # grey + dim + bold
        "unknown": "\033[0;31m",                        # red
        "reset": "\033[0m",                             # reset all attributes
        "yaml_list": "\033[1;33m",                      # yellow + bright
        "yaml_key": "\033[1;36m",                       # cyan + bright
        "yaml_key_separator": "\033[0;37m",             # white
        "yaml_value": "\033[0m",                        # reset
        "namespace": "\033[0;36m",                      # cyan
    }
}


def clear_screen() -> int:
    """
    Clear the screen.

        Returns:
            retval (int): 0 on success, errno on failure
    """
    try:
        cpath = cmtio.secure_which(FilePath("/usr/bin/clear"), fallback_allowlist=[],
                                   security_policy=SecurityPolicy.ALLOWLIST_STRICT)
    except FileNotFoundError:
        return errno.ENOENT

    return subprocess.run([cpath], check=False).returncode


def __themearray_to_raw_string(themearray: list[ANSIThemeStr]) -> str:
    """
    Strip the formatting from an ANSIThemeArray (list[ANSIThemeStr]).

        Parameters:
            themearray ([ANSIThemeStr]): The array to strip formatting from
        Returns:
            (str): The stripped string
    """
    string: str = ""
    for themestring in themearray:
        if not isinstance(themestring, ANSIThemeStr):
            raise TypeError("__themarray_to_string() only accepts arrays "
                            f"of AnsiThemeStr; this themearray consists of:\n{themearray}")

        theme_string = str(themestring)
        string += theme_string

    return string


def ansithemearray_to_str(themearray: list[ANSIThemeStr], **kwargs: Any) -> str:
    """
    Convert an ANSIThemeArray (list[ANSIThemeStr]) to a string,
    conditionally with ANSI-formatting.

        Parameters:
            themearray ([ANSIThemeStr]): The array to strip formatting from
            **kwargs (dict[str, Any]): Keyword arguments
                color (bool): True to emit ANSI-formatting, False to output a plain string
        Returns:
            (str): The string
        Raises:
            ProgrammingError: Function called without initializing ansithemestr
    """
    color: str = deep_get(kwargs, DictPath("color"), "auto")

    if theme is None or themepath is None:
        raise ProgrammingError("ansithemearray_to_str() used without calling "
                               "init_ansithemestr() first; this is a programming error.")
    string: str = ""
    for themestring in themearray:
        if not isinstance(themestring, ANSIThemeStr):
            raise TypeError("ansithemearray_to_str() only accepts arrays of AnsiThemeStr; "
                            f"this themearray consists of:\n{themearray}")

        theme_attr_ref = themestring.themeref
        theme_string = str(themestring)

        if theme is not None and color:
            if theme_attr_ref in theme["term"]:
                attr = theme["term"][theme_attr_ref]
                reset = theme["term"]["reset"]
                string += f"{attr}{theme_string}{reset}"
            else:
                raise KeyError(f"attribute (\"term\", \"{theme_attr_ref}\") "
                               f"does not exist in {themepath}")
        else:
            string += theme_string

    if string:
        string = string.replace("\x0033", "\033")

    return string


def themearray_override_formatting(themearray: list[ANSIThemeStr],
                                   formatting: Optional[str]) -> list[ANSIThemeStr]:
    """
    Override the formatting of an ANSIThemeArray (list[ANSIThemeStr]).

        Parameters:
            themearray ([ANSIThemeStr]): The themearray to reformat
            formatting (str): The new formatting to apply
        Return:
            ([ANSIThemeStr]): The reformatted ANSIThemeArray
    """
    new_themearray = []

    for themestr in themearray:
        new_themestr = copy.deepcopy(themestr)
        if formatting is not None:
            themestr = new_themestr.format(formatting)
        new_themearray.append(new_themestr)

    return new_themearray


def themearray_len(themearray: list[ANSIThemeStr]) -> int:
    """
    Return the length of a themearray.

        Parameters:
            themearray ([ANSIThemeStr]): The themearray to return the length of
        Return:
            The length of the themearray
    """
    return sum(map(len, themearray))


def themearray_ljust(themearray: list[ANSIThemeStr], width: int) -> list[ANSIThemeStr]:
    """
    Return a ljust:ed themearray (will always pad with ANSIThemeStr("", "default")).

        Parameters:
            themearray ([ANSIThemeStr]): The themearray to ljust
        Return:
            The ljust:ed themearray
    """
    tlen = themearray_len(themearray)
    if tlen < width:
        themearray = themearray + [ANSIThemeStr("".ljust(width - tlen), "default")]
    return themearray


def ansithemestr_join_list(items: Sequence[Union[str, ANSIThemeStr]],
                           **kwargs: Any) -> list[ANSIThemeStr]:
    """
    Given a list of ANSIThemeStrs or strings + formatting, join them separated by a separator.

        Parameters:
            items ([str | ANSIThemeStr]): The items to join into an ANSIThemeStr list
            **kwargs (dict[str, Any]): Keyword arguments
                formatting (str): The formatting to use if the list is a string-list
                separator (ANSIThemeStr): The list separator to use
        Return:
            themearray ([ANSIThemeStr]): The resulting ANSIThemeStr list
    """
    formatting: str = deep_get(kwargs, DictPath("formatting"), "default")
    if "separator" in kwargs:
        separator: Optional[ANSIThemeStr] = deep_get(kwargs, DictPath("separator"))
    else:
        separator = ANSIThemeStr(", ", "separator")

    themearray = []
    first = True

    for item in items:
        if isinstance(item, str):
            tmpitem = ANSIThemeStr(item, formatting)
        else:
            tmpitem = item

        if not first:
            if separator is not None:
                themearray.append(separator)
        else:
            first = False
        themearray.append(tmpitem)

    return themearray


def ansithemeinput(themearray: list[ANSIThemeStr], **kwargs: Any) -> str:
    """
    Print a themearray and input a string;
    a themearray is a list of format strings of the format:
    (string, theme_attr_ref); context is implicitly understood to be term.

        Parameters:
            themearray ([(str, str)]): The themearray to print
            **kwargs (dict[str, Any]): Keyword arguments
                color (str):
                    "always": Always use ANSI-formatting
                    "never": Never use ANSI-formatting
                    "auto": Use ANSI-formatting except when redirected
        Returns:
            string (str): The inputted string
        Raises:
            ProgrammingError: Function called without initializing ansithemestr
    """
    color: str = deep_get(kwargs, DictPath("color"), "auto")

    use_color = None

    if theme is None or themepath is None:
        raise ProgrammingError("ansithemeinput() used without calling init_ansithemeprint() first; "
                               "this is a programming error.")

    if color == "auto":
        if not sys.stdout.isatty():  # pragma: no cover
            use_color = False
        else:
            use_color = True
    elif color == "always":
        use_color = True
    elif color == "never":
        use_color = False
    else:
        raise ValueError("Incorrect value for color passed to ansithemeinput(); "
                         "the only valid values are ”always”, ”auto”, and ”never”; "
                         "this is a programming error.")

    string = ansithemearray_to_str(themearray, color=use_color)
    try:
        tmp = input(string)  # nosec
    except KeyboardInterrupt:  # pragma: no cover
        print()
        sys.exit(errno.ECANCELED)
    return tmp.replace("\x00", "<NUL>")


def ansithemeinput_password(themearray: list[ANSIThemeStr], **kwargs: Any) -> str:
    """
    Print a themearray and input a password;
    a themearray is a list of format strings of the format:
    (string, theme_attr_ref); context is implicitly understood to be term.

        Parameters:
            themearray ([(str, str)]): The themearray to print
        Returns:
            string (str): The inputted password
            **kwargs (dict[str, Any]): Keyword arguments
                color (str):
                    "always": Always use ANSI-formatting
                    "never": Never use ANSI-formatting
                    "auto": Use ANSI-formatting except when redirected
        Raises:
            ProgrammingError: Function called without initializing ansithemestr
    """
    color: str = deep_get(kwargs, DictPath("color"), "auto")

    use_color = None

    if theme is None or themepath is None:
        raise ProgrammingError("ansithemeinput_password() used without calling "
                               "init_ansithemeprint() first; this is a programming error.")

    if color == "auto":
        if not sys.stdout.isatty():  # pragma: no cover
            use_color = False
        else:
            use_color = True
    elif color == "always":
        use_color = True
    elif color == "never":
        use_color = False
    else:
        raise ValueError("Incorrect value for color passed to ansithemeinput_password(); "
                         "the only valid values are ”always”, ”auto”, and ”never”; "
                         "this is a programming error.")

    string = ansithemearray_to_str(themearray, color=use_color)
    try:
        tmp = getpass.getpass(string)
    except KeyboardInterrupt:  # pragma: no cover
        print()
        sys.exit(errno.ECANCELED)
    return tmp.replace("\x00", "<NUL>")


def ansithemeprint(themearray: list[ANSIThemeStr], **kwargs: Any) -> None:
    """
    Print a themearray;
    a themearray is a list of format strings of the format:
    (string, theme_attr_ref); context is implicitly understood to be term.

        Parameters:
            themearray ([ANSIThemeStr]): The themearray to print
            **kwargs (dict[str, Any]): Keyword arguments
                stderr (bool): True to print to stderr, False to print to stdout
                color (str):
                    "always": Always use ANSI-formatting
                    "never": Never use ANSI-formatting
                    "auto": Use ANSI-formatting except when redirected
        Raises:
            ProgrammingError: Function called without initializing ansithemestr
    """
    stderr: bool = deep_get(kwargs, DictPath("stderr"), False)
    color: str = deep_get(kwargs, DictPath("color"), "auto")

    use_color = None

    if theme is None or themepath is None:
        raise ProgrammingError("ansithemeprint() used without calling init_ansithemeprint() first; "
                               "this is a programming error.")

    if color == "auto":
        if stderr and not sys.stderr.isatty():  # pragma: no cover
            use_color = False
        elif not stderr and not sys.stdout.isatty():  # pragma: no cover
            use_color = False
        else:
            use_color = True
    elif color == "always":
        use_color = True
    elif color == "never":
        use_color = False
    else:
        raise ValueError("Incorrect value for color passed to ansithemeprint(); "
                         "the only valid values are ”always”, ”auto”, and ”never”; "
                         "this is a programming error.")

    string = ansithemearray_to_str(themearray, color=use_color)

    if stderr:
        print(string, file=sys.stderr)
    else:
        print(string)


def init_ansithemeprint(themefile: Optional[FilePath] = None) -> None:
    """
    Initialise ansithemeprint.

        Parameters:
            themefile (str): Path to the theme to use
    """
    global theme  # pylint: disable=global-statement
    global themepath  # pylint: disable=global-statement

    # If we get None as theme we use the builtin fallback theme
    if themefile is None:
        theme = FALLBACK_THEME
        themepath = FilePath("<built-in default>")
        return

    # If we get a theme but it doesn't exist we use the system theme file
    if themefile and not Path(themefile).is_file():
        themefile = SYSTEM_DEFAULT_THEME_FILE

    themepath = themefile

    # The themes directory itself may be a symlink.
    # This is expected behaviour when installing from a git repo,
    # but we only allow it if the rest of the path components are secure
    checks = [
        SecurityChecks.PARENT_RESOLVES_TO_SELF,
        SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
        SecurityChecks.OWNER_IN_ALLOWLIST,
        SecurityChecks.PARENT_PERMISSIONS,
        SecurityChecks.PERMISSIONS,
        SecurityChecks.EXISTS,
        SecurityChecks.IS_DIR,
    ]

    theme_dir = FilePath(PurePath(themefile).parent)

    violations = cmtio.check_path(theme_dir, checks=checks)
    if violations != [SecurityStatus.OK]:
        violations_joined = cmtio.join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=theme_dir)

    # We do not want to check that parent resolves to itself,
    # because when we have an installation with links directly to the git repo
    # the themes directory will be a symlink
    checks = [
        SecurityChecks.RESOLVES_TO_SELF,
        SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
        SecurityChecks.OWNER_IN_ALLOWLIST,
        SecurityChecks.PARENT_PERMISSIONS,
        SecurityChecks.PERMISSIONS,
        SecurityChecks.EXISTS,
        SecurityChecks.IS_FILE,
    ]

    if USE_FALLBACK_THEME:  # pragma: no cover
        theme = FALLBACK_THEME
        themepath = FilePath("<built-in default>")
    else:
        try:
            theme = secure_read_yaml(themefile, checks=checks)
        except (FileNotFoundError, FilePathAuditError) as e:
            # This is equivalent to FileNotFoundError
            if "SecurityStatus.DOES_NOT_EXIST" not in str(e):
                raise
            # In practice this shouldn't happen since check_path should cover this
            theme = FALLBACK_THEME
            ansithemeprint([ANSIThemeStr("Warning", "warning"),
                            ANSIThemeStr(": themefile ”", "default"),
                            ANSIThemeStr(f"{themefile}", "path"),
                            ANSIThemeStr("” does not exist; "
                                         "using built-in fallback theme.", "default")], stderr=True)
