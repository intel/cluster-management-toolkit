#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Curses-based User Interface helpers
"""

# pylint: disable=too-many-lines

# Before calling into this helper you need to call init_colors()

import copy
import curses
import curses.textpad
from datetime import datetime, timedelta
from enum import IntFlag
import errno
from operator import attrgetter
import os
from pathlib import Path, PurePath
import sys
from typing import Any, Callable, cast, Dict, List, Optional
from typing import NamedTuple, NoReturn, Set, Tuple, Type, Union

try:
    from natsort import natsorted
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import natsort; "
             "you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

from cmtio import check_path, join_securitystatus_set
from cmtio_yaml import secure_read_yaml
from cmttypes import DictPath, FilePath, LogLevel, StatusGroup, Retval
from cmttypes import FilePathAuditError, ProgrammingError
from cmttypes import SecurityChecks, SecurityStatus
from cmttypes import deep_get, loglevel_to_name, stgroup_mapping

from ansithemeprint import ANSIThemeStr, ansithemeprint

import cmtlib

theme: Dict = {}
themefile: Optional[FilePath] = None

mousemask = 0  # pylint: disable=invalid-name


# A reference to text formatting
class ThemeAttr(NamedTuple):
    """
    A reference to formatting for a themed string

        Parameters:
            context: The context to use when doing a looking in themes
            key: The key to use when doing a looking in themes
    """
    context: str
    key: str

    def __repr__(self) -> str:
        return f"ThemeAttr('{self.context}', '{self.key}')"


class ThemeStr:
    """
    A themed string for use with curses

        Parameters:
            string: A string
            themeattr: The themeattr used to format the string
            selected (Optional[bool]): Selected or unselected formatting
    """

    def __init__(self, string: str, themeattr: ThemeAttr, selected: bool = False) -> None:
        if not (isinstance(string, str)
                and isinstance(themeattr, ThemeAttr)
                and (selected is None or isinstance(selected, bool))):
            msg = [
                [("ThemeStr()", "emphasis"),
                 (" initialised with invalid argument(s):", "error")],
                [("string = ", "default"),
                 (f"{string}", "argument"),
                 (" (type: ", "default"),
                 (f"{type(string)}", "argument"),
                 (", expected: ", "default"),
                 ("str", "argument"),
                 (")", "default")],
                [("themeattr = ", "default"),
                 (f"{themeattr}", "argument"),
                 (" (type: ", "default"),
                 (f"{type(themeattr)}", "argument"),
                 (", expected: ", "default"),
                 ("ThemeAttr", "argument"),
                 (")", "default")],
                [("selected = ", "default"),
                 (f"{selected}", "argument"),
                 (" (type: ", "default"),
                 (f"{type(selected)}", "argument"),
                 (", expected: ", "default"),
                 ("bool", "argument"),
                 (")", "default")],
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   subexception=TypeError,
                                   severity=LogLevel.ERR,
                                   facility=str(themefile),
                                   formatted_msg=formatted_msg)
        self.string = string
        self.themeattr = themeattr
        self.selected = selected

    def __str__(self) -> str:
        return self.string

    def __len__(self) -> int:
        return len(self.string)

    def __repr__(self) -> str:
        return f"ThemeStr('{self.string}', {repr(self.themeattr)}, {self.selected})"

    def get_themeattr(self) -> ThemeAttr:
        """
        Return the ThemeAttr attribute of the ThemeStr

            Returns:
                (ThemeAttr): The ThemeAttr attribute of the ThemeStr
        """
        return self.themeattr

    def set_themeattr(self, themeattr: ThemeAttr) -> None:
        """
        Replace the ThemeAttr attribute of the ThemeStr

            Parameters:
                themeattr (ThemeAttr): The new ThemeAttr attribute to use
        """
        self.themeattr = themeattr

    def get_selected(self) -> bool:
        """
        Return the selected attribute of the ThemeStr

            Returns:
                (bool): The selected attribute of the ThemeStr
        """
        return self.selected

    def __eq__(self, obj: Any) -> bool:
        if not isinstance(obj, ThemeStr):
            return False

        return repr(obj) == repr(self)


class ThemeRef:
    """
    A reference to a themed string;
    while the type definition is the same as ThemeAttr its use is different.

        Parameters:
            context: The context to use when doing a looking in themes
            key: The key to use when doing a looking in themes
            selected (Optional[bool]): Should the selected or unselected formatting be used
    """

    def __init__(self, context: str, key: str, selected: bool = False) -> None:
        if not (isinstance(context, str)
                and isinstance(key, str)
                and (selected is None or isinstance(selected, bool))):
            msg = [
                [("ThemeRef()", "emphasis"),
                 (" initialised with invalid argument(s):", "error")],
                [("context = ", "default"),
                 (f"{context}", "argument"),
                 (" (type: ", "default"),
                 (f"{type(context)}", "argument"),
                 (", expected: ", "default"),
                 ("str", "argument"),
                 (")", "default")],
                [("key = ", "default"),
                 (f"{key}", "argument"),
                 (" (type: ", "default"),
                 (f"{type(key)}", "argument"),
                 (", expected: ", "default"),
                 ("str", "argument"),
                 (")", "default")],
                [("selected = ", "default"),
                 (f"{selected}", "argument"),
                 (" (type: ", "default"),
                 (f"{type(selected)}", "argument"),
                 (", expected: ", "default"),
                 ("bool", "argument"),
                 (")", "default")],
            ]
            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   facility=str(themefile),
                                   formatted_msg=formatted_msg)
        self.context = context
        self.key = key
        self.selected = selected

    def __str__(self) -> str:
        string = ""
        data = deep_get(theme, DictPath(f"{self.context}#{self.key}"))
        if data is None:
            msg = [
                [("The ThemeRef(", "error"),
                 (f"{self.context}", "argument"),
                 (", ", "error"),
                 (f"{self.key}", "argument"),
                 (") does not exist.", "error")],
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   facility=str(themefile),
                                   formatted_msg=formatted_msg)
        if isinstance(data, dict):
            if self.selected:
                selected = "selected"
            else:
                selected = "unselected"
            array = deep_get(data, DictPath(selected))
        else:
            array = data
        for string_fragment, _attr in array:
            string += string_fragment
        return string

    def __len__(self) -> int:
        return len(str(self))

    def __repr__(self) -> str:
        return f"ThemeRef('{self.context}', '{self.key}', {self.selected})"

    def to_themearray(self) -> List[ThemeStr]:
        """
        Return the themearray representation of the ThemeRef

            Returns:
                (ThemeArray): The themearray representation
        """
        themearray = []
        data = deep_get(theme, DictPath(f"{self.context}#{self.key}"))
        if isinstance(data, dict):
            if self.selected:
                selected = "selected"
            else:
                selected = "unselected"
            array = deep_get(data, DictPath(selected))
        else:
            array = data
        if array is None:
            msg = [
                [("The ThemeRef(", "error"),
                 (f"{self.context}", "argument"),
                 (", ", "error"),
                 (f"{self.key}", "argument"),
                 (") does not exist.", "error")],
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   facility=str(themefile),
                                   formatted_msg=formatted_msg)
        for string, themeattr in array:
            themearray.append(ThemeStr(string,
                              ThemeAttr(themeattr[0], themeattr[1]),
                              self.selected))
        return themearray

    def get_selected(self) -> bool:
        """
        Return the selected attribute of the ThemeRef

            Returns:
                (bool): The selected attribute of the ThemeRef
        """
        return self.selected

    def __eq__(self, obj: Any) -> bool:
        if not isinstance(obj, ThemeRef):
            return False

        return repr(obj) == repr(self)


class ThemeArray:
    """
    An array of themed strings and references to themed strings

        Parameters:
            [ThemeStr|ThemeRef]: The themearray
            selected (bool): Selected or unselected formatting;
                             passing this parameter overrides
                             individual members of the ThemeArray
    """

    def __init__(self, array: List[Union[ThemeRef, ThemeStr]],
                 selected: Optional[bool] = None) -> None:
        if array is None:
            msg = [
                [("ThemeArray()", "emphasis"),
                 (" initialised with an empty array", "error")],
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   facility=str(themefile),
                                   formatted_msg=formatted_msg)

        if not isinstance(array, list):
            msg = [
                [("ThemeArray()", "emphasis"),
                 (" initialised with invalid argument(s):", "error")],
                [("array = ", "default"),
                 (f"{array}", "argument"),
                 (" (type: ", "default"),
                 (f"{type(array)}", "argument"),
                 (", expected: ", "default"),
                 ("list", "argument"),
                 (")", "default")],
                [("selected = ", "default"),
                 (f"{selected}", "argument"),
                 (" (type: ", "default"),
                 (f"{type(selected)}", "argument"),
                 (", expected: ", "default"),
                 ("bool", "argument"),
                 (")", "default")],
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   facility=str(themefile),
                                   formatted_msg=formatted_msg)

        newarray: List[Union[ThemeRef, ThemeStr]] = []
        for item in array:
            if not isinstance(item, (ThemeRef, ThemeStr)):
                msg = [
                    [("ThemeArray()", "emphasis"),
                     (" initialised with invalid argument(s):", "error")],
                    [("array element = ", "default"),
                     (f"{item}", "argument"),
                     (" (type: ", "default"),
                     (f"{type(item)}", "argument"),
                     (", expected: ", "default"),
                     ("ThemeRef", "argument"),
                     (" or ", "default"),
                     ("ThemeStr", "argument"),
                     (")", "default")],
                ]

                unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

                raise ProgrammingError(unformatted_msg,
                                       severity=LogLevel.ERR,
                                       facility=str(themefile),
                                       formatted_msg=formatted_msg)
            if selected is None:
                newarray.append(item)
            elif isinstance(item, ThemeStr):
                newarray.append(ThemeStr(item.string, item.themeattr, selected=selected))
            elif isinstance(item, ThemeRef):
                newarray.append(ThemeRef(item.context, item.key, selected=selected))

        self.array = newarray

    def append(self, item: Union[ThemeRef, ThemeStr]) -> None:
        """
        Append a ThemeRef or ThemeStr to the ThemeArray

            Parameters:
                item (union(ThemeRef, ThemeStr)): The item to append
        """

        if not isinstance(item, (ThemeRef, ThemeStr)):
            msg = [
                [("ThemeArray.append()", "emphasis"),
                 (" called with invalid argument(s):", "error")],
                [("item = ", "default"),
                 (f"{item}", "argument"),
                 (" (type: ", "default"),
                 (f"{type(item)}", "argument"),
                 (", expected: ", "default"),
                 ("ThemeRef", "argument"),
                 (" or ", "default"),
                 ("ThemeStr", "argument"),
                 (")", "default")],
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   facility=str(themefile),
                                   formatted_msg=formatted_msg)
        self.array.append(item)

    def __add__(self, array: Union["ThemeArray",
                List[Union[ThemeRef, ThemeStr]]]) -> "ThemeArray":
        if isinstance(array, ThemeArray):
            return ThemeArray(self.to_list() + array.to_list())

        if not isinstance(array, list):
            msg = [
                [("ThemeArray.__add__()", "emphasis"),
                 (" called with invalid argument(s):", "error")],
                [("array = ", "default"),
                 (f"{array}", "argument"),
                 (" (type: ", "default"),
                 (f"{type(array)}", "argument"),
                 (", expected: ", "default"),
                 ("ThemeArray", "argument"),
                 (" or ", "default"),
                 ("[ThemeRef|ThemeStr]", "argument"),
                 (")", "default")],
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   facility=str(themefile),
                                   formatted_msg=formatted_msg)

        return ThemeArray(self.to_list() + array)

    def __str__(self) -> str:
        string = ""
        for item in self.array:
            string += str(item)
        return string

    def __len__(self) -> int:
        arraylen = 0
        for item in self.array:
            arraylen += len(item)
        return arraylen

    def __repr__(self) -> str:
        references = ""
        first = True
        for item in self.array:
            if first:
                references += f"{repr(item)}"
            else:
                references += f", {repr(item)}"
            first = False
        return f"ThemeArray([{references}])"

    def __eq__(self, obj: Any) -> bool:
        if not isinstance(obj, ThemeArray):
            return False

        return repr(obj) == repr(self)

    def to_list(self) -> List[Union[ThemeRef, ThemeStr]]:
        """
        Return the ThemeArray as a list of ThemeRef|ThemeStr

            Returns:
                ([ThemeRef|ThemeArray]): The list of ThemeRef|ThemeStr
        """
        return self.array


# pylint: disable-next=too-few-public-methods
class CursesConfiguration:
    """
    Configuration options for the curses UI
    """
    abouttext: Optional[List[Tuple[int, List[ThemeStr]]]] = None
    mousescroll_enable: bool = False
    mousescroll_up: int = 0b10000000000000000
    mousescroll_down: int = 0b1000000000000000000000000000


class WidgetLineAttrs(IntFlag):
    """
    Special properties used by lines in windowwidgets
    """
    # No specific attributes
    NORMAL = 0
    # Separators start a new category; they are not selectable
    SEPARATOR = 1
    # Disabled items are not selectable, but are not treated as a new category
    DISABLED = 2
    # Unselectable items are not selectable, but are not skipped when navigating
    UNSELECTABLE = 4
    # Invalid items are not selectable; to be used for parse error etc.
    INVALID = 8


def format_helptext(helptext: List[Tuple[str, str]]) -> List[Dict]:
    """
    Given a helptext in the format [(key, description)],
    format it in a way suitable for windowwidget

        Parameters:
            helptext: [(str, str)]: A list of rows with keypress + effect
        Returns:
            ([dict]): The formatted helptext
    """
    formatted_helptext: List[Dict] = []

    for key, description in helptext:
        formatted_helptext.append({
            "lineattrs": WidgetLineAttrs.NORMAL,
            "columns": [[ThemeStr(key, ThemeAttr("windowwidget", "highlight"))],
                        [ThemeStr(description, ThemeAttr("windowwidget", "default"))]],
            "retval": None,
        })

    return formatted_helptext


def set_mousemask(mask: int) -> None:
    """
    Enable/disable mouse support
    """
    global mousemask  # pylint: disable=global-statement
    curses.mousemask(mask)
    mousemask = mask


def get_mousemask() -> int:
    """
    Get the default mouse mask
    """
    return mousemask


__color: Dict[str, Tuple[int, int]] = {}


__pairs: Dict[Tuple[int, int], int] = {}


color_map: Dict[str, int] = {
    "black": curses.COLOR_BLACK,
    "red": curses.COLOR_RED,
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "blue": curses.COLOR_BLUE,
    "magenta": curses.COLOR_MAGENTA,
    "cyan": curses.COLOR_CYAN,
    "white": curses.COLOR_WHITE,
}


def get_theme_ref() -> Dict:
    """
    Get a reference to the theme

        Returns:
            (str): A reference to the theme
    """
    return theme


def __color_name_to_curses_color(color: Tuple[str, str], color_type: str) -> int:
    col, attr = color

    if not isinstance(attr, str):
        # debuglog.add([
        #         [ANSIThemeStr("Invalid color attribute used in theme; "
        #                          "attribute has to be a string and one of:", "default")],
        #         [ANSIThemeStr("“", "default"),
        #          ANSIThemeStr("normal", "emphasis"),
        #          ANSIThemeStr("“, “", "default"),
        #          ANSIThemeStr("bright", "emphasis"),
        #          ANSIThemeStr("“.", "default")],
        #         [ANSIThemeStr("Using “", "default"),
        #          ANSIThemeStr("normal", "emphasis"),
        #          ANSIThemeStr("“ as fallback.", "default")],
        #        ], severity = LogLevel.ERR, facility = str(themefile))
        attr = "normal"
    elif attr not in ["normal", "bright"]:
        # debuglog.add([
        #         [ANSIThemeStr("Invalid color attribute “", "default"),
        #          ANSIThemeStr(f"{attr}", "emphasis"),
        #          ANSIThemeStr("“ used in theme; "
        #                          "attribute has to be a string and one of:", "default")],
        #         [ANSIThemeStr("“", "default"),
        #          ANSIThemeStr("normal", "emphasis"),
        #          ANSIThemeStr("“, “", "default"),
        #          ANSIThemeStr("bright", "emphasis"),
        #          ANSIThemeStr("“.", "default")],
        #         [ANSIThemeStr("Using “", "default"),
        #          ANSIThemeStr("normal", "emphasis"),
        #          ANSIThemeStr("“ as fallback.", "default")],
        #        ], severity = LogLevel.ERR, facility = str(themefile))
        attr = "normal"
    if isinstance(col, str):
        col = col.lower()

    if not isinstance(col, str) or col not in color_map:
        # debuglog.add([
        #         [ANSIThemeStr("Invalid color type “", "default"),
        #          ANSIThemeStr(f"{col}", "emphasis"),
        #          ANSIThemeStr("“ used in theme; "
        #                          "color has to be a string and one of:", "default"),
        #          ANSIThemeStr("“" + "“, ".join(color_map.keys()) +  "“", "default")],
        #        ], severity = LogLevel.ERR, facility = str(themefile))
        raise ValueError("Invalid color type used in theme; "
                         f"color has to be a string and one of: {', '.join(color_map.keys())}")

    if attr == "bright":
        curses_attr = 8
    else:
        curses_attr = 0

    if (curses_color := deep_get(color_map, DictPath(col))) is None:
        # debuglog.add([
        #         [ANSIThemeStr("Invalid {color_type} color “", "default"),
        #          ANSIThemeStr(f"{col}", "emphasis"),
        #          ANSIThemeStr("“ used in theme; valid colors are:", "default"),
        #          ANSIThemeStr("“" + "“, ".join(color_map.keys()) +  "“", "default")],
        #        ], severity = LogLevel.ERR, facility = str(themefile))
        raise ValueError(f"Invalid {color_type} color {col} used in theme; "
                         f"valid colors are: {', '.join(color_map.keys())}")
    return curses_color + curses_attr


def __convert_color_pair(color_pair: Tuple[Tuple[str, str], Tuple[str, str]]) -> Tuple[int, int]:
    fg, bg = color_pair

    curses_fg = __color_name_to_curses_color(fg, "foreground")
    curses_bg = __color_name_to_curses_color(bg, "background")

    return (curses_fg, curses_bg)


def __init_pair(pair: str, color_pair: Tuple[int, int], color_nr: int) -> None:
    if not curses.has_colors():  # pragma: no cover
        term = os.getenv("TERM", "<unknown>")
        sys.exit(f"Error: Your terminal environment TERM={term} reports that it doesn't\n"
                 "support colors; at least currently cmu requires color support; exiting.")

    fg, bg = color_pair
    bright_black_remapped = False

    if fg == bg:
        # debuglog.add([
        #         [ANSIThemeStr("__init_pair()", "emphasis"),
        #          ANSIThemeStr(" called with a color pair where fg == bg (", "error"),
        #          ANSIThemeStr(f"{fg}", "argument"),
        #          ANSIThemeStr(",", "error"),
        #          ANSIThemeStr(f"{bg}", "argument"),
        #          ANSIThemeStr(")", "error")],
        #        ], severity = LogLevel.ERR, facility = str(themefile))
        raise ValueError(f"The theme contains a color pair ({pair}) where fg == bg ({bg})")

    try:
        curses.init_pair(color_nr, fg, bg)
    except (curses.error, ValueError) as e:
        if str(e) in ("init_pair() returned ERR", "Color number is greater than COLORS-1 (7)."):
            # debuglog.add([
            #         [ANSIThemeStr("init_pair()", "emphasis"),
            #          ANSIThemeStr(" failed; attempting to limit fg & bg to ", "error"),
            #          ANSIThemeStr("0", "argument"),
            #          ANSIThemeStr("-", "error"),
            #          ANSIThemeStr("7", "argument"),
            #          ANSIThemeStr(")", "error")],
            #        ], severity = LogLevel.DEBUG, facility = str(themefile))

            # Most likely we failed due to the terminal only
            # supporting colours 0-7. If "bright black" was
            # requested, we need to remap it. Fallback to blue;
            # hopefully there are no cases of bright black on blue.
            if fg & 7 == curses.COLOR_BLACK:
                fg = curses.COLOR_BLUE
                bright_black_remapped = True
            if fg & 7 == bg & 7:
                # debuglog.add([
                #         [ANSIThemeStr("__init_pair()", "emphasis"),
                #          ANSIThemeStr(" called with a color pair where fg == bg (", "error"),
                #          ANSIThemeStr(f"{fg}", "argument"),
                #          ANSIThemeStr(",", "error"),
                #          ANSIThemeStr(f"{bg}", "argument"),
                #          ANSIThemeStr(f"{bright_black_remapped}", "argument")],
                #        ], severity = LogLevel.ERR, facility = str(themefile))
                raise ValueError(f"The theme contains a color pair ({pair}) where fg == bg ({bg}; "
                                 f"bright black remapped: {bright_black_remapped})") from e
            curses.init_pair(color_nr, fg & 7, bg & 7)
        else:
            raise


def read_theme(configthemefile: FilePath, defaultthemefile: FilePath) -> None:
    """
    Read the theme file and initialise the theme dict

        Parameters:
            configthemefile (FilePath): The theme to read
            defaultthemefile (FilePath): The fallback if the other theme is not available
    """
    global theme  # pylint: disable=global-statement
    global themefile  # pylint: disable=global-statement

    for item in (configthemefile, f"{configthemefile}.yaml", defaultthemefile):
        if item is not None and Path(item).is_file():
            themefile = cast(FilePath, item)
            break

    if themefile is None:
        if configthemefile:
            msg = [
                [("curses_helper.read_theme()", "emphasis"),
                 (" failed to load ", "error"),
                 (f"{configthemefile}", "path"),
                 ("; file not found", "error")],
            ]
        elif defaultthemefile:
            msg = [
                [("curses_helper.read_theme()", "emphasis"),
                 (" failed to load ", "error"),
                 (f"{defaultthemefile}", "path"),
                 ("; file not found", "error")],
            ]
        else:
            msg = [
                [("curses_helper.read_theme()", "emphasis"),
                 (" failed to load theme; both the themefile "
                  "and the defaultthemefile paths are empty", "error")],
            ]

        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

        raise ProgrammingError(unformatted_msg,
                               subexception=FileNotFoundError,
                               severity=LogLevel.ERR,
                               formatted_msg=formatted_msg)

    # The parsers directory itself may be a symlink.
    # This is expected behaviour when installing from a git repo,
    # but we only allow it if the rest of the path components are secure.
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

    violations = check_path(theme_dir, checks=checks)
    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
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

    theme = secure_read_yaml(FilePath(themefile), checks=checks)


def init_curses() -> None:
    """
    Initialise the curses helper; this configures all curses color pairs needed
    for the various ThemeAttrs
    """
    color_last = 1

    # First we set the colour palette
    for col, curses_col in color_map.items():
        rgb = deep_get(theme, DictPath(f"colors#{col}"))
        if rgb is None:
            continue
        r, g, b = rgb
        try:
            curses.init_color(curses_col, r, g, b)
        except curses.error as e:
            if str(e) == "init_extended_color() returned ERR":
                # Most likely remapping the palette is not supported (16-color xterm?);
                # just ignore the remap attempt
                pass
            else:
                raise

    # Next we need to define all necessary colour pairs;
    # most of them come in selected and unselected variants
    for pair in theme["color_pairs_curses"]:
        if isinstance(theme["color_pairs_curses"][pair], list):
            unselected = __convert_color_pair(theme["color_pairs_curses"][pair])
            selected = unselected
        else:
            unselected = __convert_color_pair(theme["color_pairs_curses"][pair]["unselected"])
            selected = __convert_color_pair(theme["color_pairs_curses"][pair]["selected"])

        if unselected not in __pairs:
            __init_pair(pair, unselected, color_last)
            __pairs[unselected] = curses.color_pair(color_last)
            color_last += 1
        unselected_index = __pairs[unselected]
        if selected not in __pairs:
            __init_pair(pair, selected, color_last)
            __pairs[selected] = curses.color_pair(color_last)
            color_last += 1
        selected_index = __pairs[selected]
        __color[pair] = (unselected_index, selected_index)


def dump_themearray(themearray: List[Any]) -> NoReturn:
    """
    Dump all individual parts of a ThemeArray;
    used for debug purposes

        Parameters:
            themearray (list): A themearray
    """
    tmp = ""
    for substr in themearray:
        if isinstance(substr, ThemeStr):
            tmp += "ThemeStr:\n"
            tmp += f"          str: “{substr}“\n"
            tmp += f"       strlen: “{len(substr)}“\n"
            tmp += f"         attr: {substr.themeattr}\n"
            tmp += f"     selected: {substr.selected}\n"
        elif isinstance(substr, ThemeRef):
            tmp += f"   ThemeRef: {substr}\n"
            tmp += f"          str: “{str(substr)}“\n"
            tmp += f"          ctx: {substr.context}\n"
            tmp += f"          key: {substr.key}\n"
            tmp += f"     selected: {substr.selected}\n"
        elif isinstance(substr, tuple):
            tmp += f"      tuple: {substr}\n"
        elif isinstance(substr, list):
            tmp += f"       list: {substr}\n"
        else:
            tmp += f"TYPE {type(substr)}: {substr}\n"
    raise TypeError(f"themearray contains invalid substring(s):\n{tmp}\n{themearray}")


def color_log_severity(severity: LogLevel) -> ThemeAttr:
    """
    Given severity, returns the corresponding ThemeAttr

        Parameters:
            severity (LogLevel): The severity
        Returns:
            (ThemeAttr): The corresponding ThemeAttr
    """
    return ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")


def color_status_group(status_group: StatusGroup) -> ThemeAttr:
    """
    Given status group, returns the corresponding ThemeAttr

        Parameters:
            severity (LogLevel): The status group
        Returns:
            (ThemeAttr): The corresponding ThemeAttr
    """
    return ThemeAttr("main", stgroup_mapping[status_group])


def window_tee_hline(win: curses.window, y: int,
                     start: int, end: int, formatting: Optional[ThemeAttr] = None) -> None:
    """
    Draw a horizontal line with "tees" ("├", "┤") at the ends

        Parameters:
            win (curses.window): The curses window to operate on
            y (int): The y-coordinate
            start (int): the starting point of the hline
            end (int): the ending point of the hline
            formatting (ThemeAttr): Optional ThemeAttr to apply to the line
    """
    ltee = deep_get(theme, DictPath("boxdrawing#ltee"))
    rtee = deep_get(theme, DictPath("boxdrawing#rtee"))
    hline = deep_get(theme, DictPath("boxdrawing#hline"))

    if formatting is None:
        formatting = ThemeAttr("main", "default")

    hlinearray: List[Union[ThemeRef, ThemeStr]] = [
        ThemeStr(ltee, formatting),
        ThemeStr("".rjust(end - start - 1, hline), formatting),
        ThemeStr(rtee, formatting),
    ]

    addthemearray(win, hlinearray, y=y, x=start)


def window_tee_vline(win: curses.window, x: int,
                     start: int, end: int, formatting: Optional[ThemeAttr] = None) -> None:
    """
    Draw a vertical line with "tees" ("┬", "┴") at the ends

        Parameters:
            win (curses.window): The curses window to operate on
            x (int): The y-coordinate
            start (int): the starting point of the vline
            end (int): the ending point of the vline
            formatting (ThemeAttr): Optional ThemeAttr to apply to the line
    """
    ttee = deep_get(theme, DictPath("boxdrawing#ttee"))
    btee = deep_get(theme, DictPath("boxdrawing#btee"))
    vline = deep_get(theme, DictPath("boxdrawing#vline"))

    if formatting is None:
        formatting = ThemeAttr("main", "default")

    y = start

    addthemearray(win, [ThemeStr(ttee, formatting)], y=y, x=x)

    while y < end:
        y += 1
        addthemearray(win, [ThemeStr(vline, formatting)], y=y, x=x)

    addthemearray(win, [ThemeStr(btee, formatting)], y=end, x=x)


# pylint: disable-next=too-many-arguments,too-many-locals
def scrollbar_vertical(win: curses.window, x: int, miny: int, maxy: int,
                       height: int, yoffset: int, clear_color: ThemeAttr) \
        -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int, int]]:
    """
    Draw a vertical scroll bar

        Parameters:
            win (curses.window): The curses window to operate on
            x (int): The x-coordinate
            miny (int): the starting point of the scroll bar
            maxy (int): the ending point of the scroll bar
            height (int): the height of the scrollable area
            yoffset (int): the offset into the scrollable area
            clear_color (ThemeAttr): The theme attr to use if the scrollbar is disabled
        Returns:
            ((int, int), (int, int), (int, int)):
                (int, int): (y, x) for upper arrow
                (int, int): (y, x) for lower arrow
                (int, int): (y, x) for midpoint of dragger
    """
    arrowup = deep_get(theme, DictPath("boxdrawing#arrowup"), "▲")
    arrowdown = deep_get(theme, DictPath("boxdrawing#arrowdown"), "▼")
    scrollbar = deep_get(theme, DictPath("boxdrawing#scrollbar"), "▒")
    verticaldragger_upper = deep_get(theme, DictPath("boxdrawing#verticaldragger_upper"), "█")
    verticaldragger_midpoint = deep_get(theme, DictPath("boxdrawing#verticaldragger_midpoint"), "◉")
    verticaldragger_lower = deep_get(theme, DictPath("boxdrawing#verticaldragger_lower"), "█")
    vline = deep_get(theme, DictPath("boxdrawing#vline"))
    upperarrow = (-1, -1)
    lowerarrow = (-1, -1)
    vdragger = (-1, -1, -1)

    maxoffset = height - (maxy - miny) - 1

    # We only need a scrollbar if we can actually scroll
    if maxoffset > 0:
        addthemearray(win, [ThemeStr(arrowup,
                                     ThemeAttr("main", "scrollbar_arrows"))], y=miny, x=x)
        upperarrow = (miny, x)
        y = miny + 1
        while y < maxy:
            addthemearray(win, [ThemeStr(scrollbar, ThemeAttr("main", "scrollbar"))], y=y, x=x)
            y += 1
        addthemearray(win, [ThemeStr(arrowdown,
                                     ThemeAttr("main", "scrollbar_arrows"))], y=maxy, x=x)
        lowerarrow = (maxy, x)
        curpos = miny + 1 + int((maxy - miny) * (yoffset / (maxoffset)))
        curpos = min(curpos, maxy - 3)
        vdragger = (curpos, x, 3)
        addthemearray(win, [ThemeStr(verticaldragger_upper,
                                     ThemeAttr("main", "dragger"))], y=curpos + 0, x=x)
        addthemearray(win, [ThemeStr(verticaldragger_midpoint,
                                     ThemeAttr("main", "dragger_midpoint"))], y=curpos + 1, x=x)
        addthemearray(win, [ThemeStr(verticaldragger_lower,
                                     ThemeAttr("main", "dragger"))], y=curpos + 2, x=x)
    # But we might need to cover up the lack of one if the window has been resized
    else:
        for y in range(miny, maxy + 1):
            addthemearray(win, [ThemeStr(vline, clear_color)], y=y, x=x)

    # (y, x Upper arrow), (y, x Lower arrow), (y, x, len vertical dragger)
    return upperarrow, lowerarrow, vdragger


# pylint: disable-next=too-many-arguments,too-many-locals
def scrollbar_horizontal(win: curses.window, y: int, minx: int, maxx: int,
                         width: int, xoffset: int, clear_color: ThemeAttr) \
        -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int, int]]:
    """
    Draw a horizontal scroll bar

        Parameters:
            win (curses.window): The curses window to operate on
            y (int): The y-coordinate
            minx (int): the starting point of the scroll bar
            maxx (int): the ending point of the scroll bar
            width (int): the width of the scrollable area
            xoffset (int): the offset into the scrollable area
            clear_color (ThemeAttr): The theme attr to use if the scrollbar is disabled
        Returns:
            ((int, int), (int, int), (int, int)):
                (int, int): (y, x) for left arrow
                (int, int): (y, x) for right arrow
                (int, int): (y, x) for midpoint of dragger
    """
    arrowleft = deep_get(theme, DictPath("boxdrawing#arrowleft"), "▲")
    arrowright = deep_get(theme, DictPath("boxdrawing#arrowright"), "▼")
    scrollbar = deep_get(theme, DictPath("boxdrawing#scrollbar"), "▒")
    horizontaldragger_left = deep_get(theme, DictPath("boxdrawing#horizontaldragger_left"), "█")
    horizontaldragger_midpoint = deep_get(theme,
                                          DictPath("boxdrawing#horizontaldragger_midpoint"), "◉")
    horizontaldragger_right = deep_get(theme, DictPath("boxdrawing#horizontaldragger_right"), "█")
    hline = deep_get(theme, DictPath("boxdrawing#hline"))

    leftarrow = (-1, -1)
    rightarrow = (-1, -1)
    hdragger = (-1, -1, -1)

    maxoffset = width - (maxx - minx) - 1

    scrollbararray: List[Union[ThemeRef, ThemeStr]] = []

    # We only need a scrollbar if we can actually scroll
    if maxoffset > 0:
        scrollbararray += [
            ThemeStr(arrowleft, ThemeAttr("main", "scrollbar_arrows")),
        ]
        leftarrow = (y, minx)

        scrollbararray += [
            ThemeStr("".rjust(maxx - minx - 1, scrollbar), ThemeAttr("main", "scrollbar")),
        ]
        scrollbararray += [
            ThemeStr(arrowright, ThemeAttr("main", "scrollbar_arrows")),
        ]
        rightarrow = (y, maxx)

        curpos = minx + 1 + int((maxx - minx) * (xoffset / (maxoffset)))
        curpos = min(curpos, maxx - 5)

        addthemearray(win, scrollbararray, y=y, x=minx)

        draggerarray: List[Union[ThemeRef, ThemeStr]] = [
            ThemeStr(f"{horizontaldragger_left}{horizontaldragger_left}",
                     ThemeAttr("main", "dragger")),
            ThemeStr(f"{horizontaldragger_midpoint}",
                     ThemeAttr("main", "dragger_midpoint")),
            ThemeStr(f"{horizontaldragger_right}{horizontaldragger_right}",
                     ThemeAttr("main", "dragger")),
        ]

        addthemearray(win, draggerarray, y=y, x=curpos)
        hdragger = (y, curpos, 5)
    # But we might need to cover up the lack of one if the window has been resized
    else:
        scrollbararray += [
            ThemeStr("".rjust(maxx - minx + 1, hline), clear_color),
        ]
        addthemearray(win, scrollbararray, y=y, x=minx)

    # (y, x Upper arrow), (y, x Lower arrow), (y, x, len horizontal dragger)
    return leftarrow, rightarrow, hdragger


def generate_heatmap(maxwidth: int, stgroups: List[StatusGroup],
                     selected: int) -> List[List[Union[ThemeRef, ThemeStr]]]:
    """
    Given [StatusGroup] and an index to the selected item and the max width,
    generate an array of themearrays

        Parameters:
            maxwidth (int): The maximum width of a line
            stgroups ([StatusGroup]): The status group for each item
            selected (int): The selected item (used to draw the cursor); use -1 to disable cursor
        Returns:
            ([ThemeArray]): A list of themearrays
    """
    heatmap: List[Union[ThemeRef, ThemeStr]] = []

    if not stgroups:
        return []

    # Append a dummy entry to avoid special casing
    stgroups.append(StatusGroup.UNKNOWN)

    current_status = None
    status_width = 0

    # Try to minimise the colour changes
    for i, stgroup in enumerate(stgroups):
        new_status = ThemeRef("strings", stgroup_mapping[stgroup], selected=selected == i)
        if current_status is None or current_status != new_status:
            if current_status is not None:
                # We have something to flush
                # Flush
                refarray = current_status.to_themearray()
                if len(refarray) > 1:
                    raise ValueError("generate_heatmap() cannot handle ThemeRef "
                                     "with multiple ThemeStr")
                refthemestr = refarray[0]
                refstr = str(refthemestr)
                refattr = refthemestr.get_themeattr()
                is_selected = refthemestr.get_selected()
                newstr = (refstr * (status_width // len(refstr))
                          + refstr[0:status_width % len(refstr)])
                heatmap.append(ThemeStr(newstr, refattr, selected=is_selected))
            current_status = new_status
            status_width = 1
        else:
            status_width += 1

    return themearray_wrap_line(heatmap, maxwidth + 1, wrap_marker=False)


# pylint: disable-next=too-many-arguments,too-many-locals
def percentagebar(minx: int, maxx: int, total: int,
                  subsets: List[Tuple[int, ThemeRef]]) -> List[Union[ThemeRef, ThemeStr]]:
    """
    Draw a bar of multiple subsets that sum up to a total

        Parameters:
            y (int): The y-position of the percentage bar
            minx (int): The starting position of the percentage bar
            maxx (int): The ending position of the percentage bar
            total (int): The total sum
            subsets (list(subset, themeref)):
                subset (int): The fraction of the total that this subset represents
                themeref (ThemeRef): The theme reference to use for this subset
                                     Note: The string part of the ThemeRef
                                     will be truncated or repeated as necessary.
        Returns:
            (ThemeArray): The themearray with the percentage bar
    """
    themearray: List[Union[ThemeRef, ThemeStr]] = []

    bar_width = maxx - minx + 1
    subset_total = 0

    if total > 0:
        for subset in subsets:
            pct, themeref = subset
            subset_width = int((pct / total) * bar_width)
            subset_total += subset_width
            refarray = themeref.to_themearray()
            if len(refarray) > 1:
                raise ValueError("parcentagebar() cannot handle ThemeRef "
                                 "with multiple ThemeStr")
            refthemestr = refarray[0]
            refstr = str(refthemestr)
            refattr = refthemestr.get_themeattr()
            newstr = refstr * (subset_width // len(refstr)) + refstr[0:subset_width % len(refstr)]
            themearray.append(ThemeStr(newstr, refattr))

    # Pad to full width
    themearray.append(ThemeStr("".ljust(bar_width - subset_total),
                               ThemeAttr("types", "generic")))
    return themearray


# pylint: disable=unused-argument
def __notification(stdscr: Optional[curses.window], y: int, x: int,
                   message: str, formatting: ThemeAttr) -> curses.window:
    height = 3
    width = 2 + len(message)
    ypos = y - height // 2
    xpos = x - width // 2

    win = curses.newwin(height, width, ypos, xpos)
    col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "boxdrawing"))
    win.attrset(col)
    win.clear()
    win.border()
    win.addstr(1, 1, message, themeattr_to_curses_merged(formatting))
    win.noutrefresh()
    curses.doupdate()
    return win


def notice(stdscr: Optional[curses.window], y: int, x: int, message: str) -> curses.window:
    """
    Show a notification

        Parameters:
            stdscr (curses.window): The curses window to operate on
            y (int): the y-coordinate of the window centre point
            x (int): the x-coordinate of the window centre point
            message (str): The message to show
        Returns:
            (curses.window): A reference to the notification window
    """
    return __notification(stdscr, y, x, message, ThemeAttr("windowwidget", "notice"))


def alert(stdscr: Optional[curses.window], y: int, x: int, message: str) -> curses.window:
    """
    Show an alert

        Parameters:
            win (curses.window): The curses window to operate on
            y (int): the y-coordinate of the window centre point
            x (int): the x-coordinate of the window centre point
            message (str): The message to show
        Returns:
            (curses.window): A reference to the notification window
    """
    return __notification(stdscr, y, x, message, ThemeAttr("windowwidget", "alert"))


# pylint: disable-next=too-many-arguments
def progressbar(win: curses.window, y: int, minx: int, maxx: int,
                progress: int, title: Optional[str] = None) -> curses.window:
    """
    A progress bar;
    Usage: Initialise by calling with a reference to a variable set to None
    Pass in progress in 0-100; once done clean up with:
    stdscr.touchwin()
    stdscr.refresh()

        Parameters:
            win (curses.window): The curses window to operate on
            y (int): the y-coordinate
            miny (int): the starting point of the progress bar
            maxy (int): the ending point of the progress bar
            progress (int): 0-100%
            title (str): The title for the progress bar (None for an anonymous window)
        Returns:
            (curses.window): A reference to the progress bar window
    """
    if not (isinstance(y, int) and isinstance(minx, int)
            and isinstance(maxx, int) and isinstance(progress, int)
            and (title is None or isinstance(title, str))):
        msg = [
            [("curses_helper.progressbar()", "emphasis"),
             (" initialised with invalid argument(s):", "error")],
            [("y = ", "default"),
             (f"{y}", "argument"),
             (" (type: ", "default"),
             (f"{type(y)}", "argument"),
             (", expected: ", "default"),
             ("int", "argument"),
             (")", "default")],
            [("minx = ", "default"),
             (f"{minx}", "argument"),
             (" (type: ", "default"),
             (f"{type(minx)}", "argument"),
             (", expected: ", "default"),
             ("int", "argument"),
             (")", "default")],
            [("maxx = ", "default"),
             (f"{maxx}", "argument"),
             (" (type: ", "default"),
             (f"{type(maxx)}", "argument"),
             (", expected: ", "default"),
             ("int", "argument"),
             (")", "default")],
            [("progress = ", "default"),
             (f"{progress}", "argument"),
             (" (type: ", "default"),
             (f"{type(progress)}", "argument"),
             (", expected: ", "default"),
             ("int", "argument"),
             (")", "default")],
            [("title = ", "default"),
             (f"{title}", "argument"),
             (" (type: ", "default"),
             (f"{type(title)}", "argument"),
             (", expected: ", "default"),
             ("str or None", "argument"),
             (")", "default")],
        ]

        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

        raise ProgrammingError(unformatted_msg,
                               severity=LogLevel.ERR,
                               formatted_msg=formatted_msg)

    width = maxx - minx + 1

    if progress < 0:
        msg = [
            [("curses_helper.progressbar()", "emphasis"),
             (" called with progress < 0:", "error")],
            [("progress = ", "default"),
             (f"{progress}", "argument")],
            [("Negative progress is not supported; this is not a regression bar.", "default")],
        ]

        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

        raise ProgrammingError(unformatted_msg,
                               severity=LogLevel.ERR,
                               formatted_msg=formatted_msg)
    if progress > 100:
        msg = [
            [("curses_helper.progressbar()", "emphasis"),
             (" called with progress > 100:", "error")],
            [("progress = ", "default"),
             (f"{progress}", "argument")],
            [("That's impossible. No one can give more than 100%. "
              "By definition, that is the most anyone can give.", "default")],
        ]

        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

        raise ProgrammingError(unformatted_msg,
                               severity=LogLevel.ERR,
                               formatted_msg=formatted_msg)

    if win is None:
        win = curses.newwin(3, width, y, minx)
        col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "boxdrawing"))
        win.attrset(col)
        win.clear()
        win.border()
        col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "default"))
        win.bkgd(" ", col)
        if title is not None:
            win.addstr(0, 1, title, themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))

    # progress is in % of the total length
    solidblock = deep_get(theme, DictPath("boxdrawing#solidblock"))
    dimmedblock = deep_get(theme, DictPath("boxdrawing#dimmedblock"))
    for x in range(0, width - 2):
        try:
            if x < (width * progress) // 100:
                addthemearray(win, [ThemeStr(solidblock, ThemeAttr("main", "progressbar"))],
                              y=1, x=x + 1)
            else:
                addthemearray(win, [ThemeStr(dimmedblock, ThemeAttr("main", "progressbar"))],
                              y=1, x=x + 1)
        except curses.error:
            curses.endwin()
            ansithemeprint([ANSIThemeStr("Critical", "critical"),
                            ANSIThemeStr(": Live resizing progressbar() is currently broken; "
                                         "this is a known issue.", "default")], stderr=True)
            sys.exit(errno.ENOTSUP)

    win.noutrefresh()
    curses.doupdate()

    return win


def inputwrapper(keypress: int) -> int:
    """
    A wrapper used by textpads to change the input behaviour of the Escape key

        Parameters:
            keypress (int): The keypress
        Returns:
            (int): The filtered keypress
    """
    global ignoreinput  # pylint: disable=global-statement

    if keypress == 27:  # ESCAPE
        ignoreinput = True
        return 7
    return keypress


# pylint: disable-next=too-many-arguments
def inputbox(stdscr: curses.window, **kwargs: Any) -> str:
    """
    Show an input box at (y, x)

        Parameters:
            stdscr (curses.window): The curses window to operate on
            **kwargs (dict[str, Any]): Keyword arguments
                y (int): the y-coordinate to draw the box at
                     (default: maxy // 2)
                x (int): the x-coordinate for the left edge of the inputbox
                     (default: 1)
                width (int): the width of the inputbox
                         (default: maxx - 1)
                title (str): The inputbox title (default: "")
        Returns:
            (str): The inputted string
    """
    global ignoreinput  # pylint: disable=global-statement

    maxy, maxx = stdscr.getmaxyx()
    y = deep_get(kwargs, DictPath("y"), maxy // 2)
    x = deep_get(kwargs, DictPath("x"), 1)
    width = deep_get(kwargs, DictPath("width"), maxx - 2)
    title = deep_get(kwargs, DictPath("title"), "")

    # Show the cursor; seems some implementations of curses (or terminals?)
    # might not support toggling the cursor; they will throw an exception instead.
    # Catch this an pretend that everything is fine.
    try:
        curses.curs_set(True)
    except curses.error:
        pass

    ignoreinput = False

    win = curses.newwin(3, width, y, x)
    col, _discard = themeattr_to_curses(ThemeAttr("windowwidget", "boxdrawing"))
    win.attrset(col)
    win.clear()
    win.border()
    if title:
        win.addstr(0, 1, title, themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))
    win.noutrefresh()

    inputarea = win.subwin(1, width - 2, y + 1, x + 1)
    inputarea.bkgd(" ", themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))
    inputarea.attrset(themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))
    inputarea.noutrefresh()

    tpad = curses.textpad.Textbox(inputarea)
    curses.doupdate()

    tpad.edit(inputwrapper)

    if ignoreinput:
        string = ""
    else:
        string = tpad.gather()

    del tpad
    del win

    # Hide the cursor; seems some implementations of curses (or terminals?)
    # might not support toggling the cursor; they will throw an exception instead.
    # Catch this an pretend that everything is fine.
    try:
        curses.curs_set(False)
    except curses.error:
        pass
    stdscr.touchwin()
    stdscr.noutrefresh()
    curses.doupdate()

    return string.rstrip()


# pylint: disable-next=too-many-locals
def confirmationbox(stdscr: curses.window, **kwargs: Any) -> bool:
    """
    Show a confirmation box centered around y

        Parameters:
            stdscr (curses.window): The curses window to operate on
            **kwargs (dict[str, Any]): Keyword arguments
                y (int): the y-coordinate to draw the box at
                     (default: maxy // 2)
                x (int): the x-coordinate for the centre point of the box
                     (default: maxx // 2)
                default (bool): The default value
                title (str): The confirmationbox title (default: "")
        Returns:
            (bool): The response
    """
    global ignoreinput  # pylint: disable=global-statement

    maxy, maxx = stdscr.getmaxyx()
    y = deep_get(kwargs, DictPath("y"), maxy // 2)
    x = deep_get(kwargs, DictPath("x"), maxx // 2)
    default = deep_get(kwargs, DictPath("default"), False)
    title = deep_get(kwargs, DictPath("title"), "")

    ignoreinput = False
    retval = default

    default_option = "Y/n" if default else "y/N"
    question = f"Are you sure [{default_option}]: "
    height = 3
    width = 2 + max(len(question), len(title))
    ypos = y - height // 2
    xpos = x - width // 2

    win = curses.newwin(height, width, ypos, xpos)
    col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "boxdrawing"))
    win.attrset(col)
    win.clear()
    win.border()
    win.addstr(0, 1, title, themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))
    win.addstr(1, 1, question.ljust(width - 2),
               themeattr_to_curses_merged(ThemeAttr("windowwidget", "default")))
    win.noutrefresh()
    curses.doupdate()

    while True:
        stdscr.timeout(100)
        c = stdscr.getch()
        if c == 27:  # ESCAPE
            break

        if c == ord("") or c == ord(""):
            curses.endwin()
            sys.exit()

        if c in (curses.KEY_ENTER, 10, 13):
            break

        if c in (ord("y"), ord("Y")):
            retval = True
            break

        if c in (ord("n"), ord("N")):
            retval = False
            break

    del win
    stdscr.touchwin()
    stdscr.noutrefresh()
    curses.doupdate()

    return retval


def move_cur_with_offset(curypos: int, yoffset: int,
                         maxcurypos: int, maxyoffset: int,
                         movement: int, **kwargs: Any) -> Tuple[int, int]:
    """
    Calculate a new cursor position based on an offset

        Parameters:
            curypos (int): The current cursor on the screen
            yoffset (int): The offset in the range
            maxcurypos (int): The maximum cursor screen position
            maxyoffset (int): The maximum offset in the range
            movement (int): The momvent to make
            **kwargs (dict[str, Any]): Keyword arguments
                wraparound (bool): Should the list wraparound (default: False)
        Returns:
            (int, int):
                (int): The new cursor position
                (int): The new offset in the range
    """
    wraparound: bool = deep_get(kwargs, DictPath("wraparound"), False)

    newcurypos = curypos + movement
    newyoffset = yoffset

    # If we are being asked to move forward but we are already
    # at the end of the list, it is prudent not to move,
    # even if the caller so requests.
    # It is just good manners, really; likewise if we are being asked to move
    # backward past the start of the list.
    #
    # One may gracefully accept the request if so instructed using the wraparound flag, though.
    if movement > 0:
        if newcurypos > maxcurypos:
            if newyoffset == maxyoffset and wraparound:
                newcurypos = 0
                newyoffset = 0
            else:
                newcurypos = maxcurypos
                newyoffset = min(yoffset + movement - (maxcurypos - curypos), maxyoffset)
    elif movement < 0:
        if newcurypos < 0:
            if (yoffset + curypos) + newcurypos < 0 and wraparound:
                newcurypos = maxcurypos
                newyoffset = maxyoffset
            else:
                newcurypos = 0
                newyoffset = max(yoffset + movement + curypos, 0)
    return newcurypos, newyoffset


def addthemearray(win: curses.window,
                  array: List[Union[ThemeRef, ThemeStr]], **kwargs: Any) -> Tuple[int, int]:
    """
    Add a ThemeArray to a curses window

        Parameters:
            win (curses.window): The curses window to operate on
            array ([ThemeRef|ThemeStr]): The themearray to add to the curses window
            **kwargs (dict[str, Any]): Keyword arguments
                y (int): The y-coordinate (-1 to start from current cursor position)
                x (int): The x-coordinate (-1 to start from current cursor position)
                deleted (bool): Should the theme be overridden as deleted?
        Returns:
            (int, int):
                (int): The new y-coordinate
                (int): The new x-coordinate
    """
    y: int = deep_get(kwargs, DictPath("y"), -1)
    x: int = deep_get(kwargs, DictPath("x"), -1)
    deleted: bool = deep_get(kwargs, DictPath("deleted"), False)

    for item in themearray_flatten(array):
        if deleted:
            item.set_themeattr(ThemeAttr("types", "deleted"))
        string, attr = themestring_to_cursestuple(item)
        # If there still are remaining <NUL> occurences, replace them
        string = string.replace("\x00", "<NUL>")
        try:
            win.addstr(y, x, string, attr)
        except curses.error:
            pass
        y, x = win.getyx()
    return y, x


# This extracts the string without formatting;
# once everything uses proper ThemeArray this wo not be necessary anymore
def themearray_to_string(themearray: Union[ThemeArray, List[Union[ThemeRef, ThemeStr]]]) -> str:
    """
    Given a themearray (either a true ThemeArray or List[Union[ThemeRef, ThemeStr]],
    return an unformatted string

        Parameters:
            themearray (ThemeArray): A themearray
        Returns:
            (str): The unformatted string
    """
    string = ""

    if isinstance(themearray, ThemeArray):
        return str(themearray)

    for fragment in themearray:
        string += str(fragment)

    return string


def themearray_truncate(themearray: Union[ThemeArray, List[Union[ThemeRef, ThemeStr]]],
                        max_len: int) -> Union[ThemeArray, List[Union[ThemeRef, ThemeStr]]]:
    output_format = type(themearray)
    truncated_themearray: Union[ThemeArray, List[Union[ThemeRef, ThemeStr]]] = []

    # For the time being (until we implement proper iteration
    # over ThemeArray elements) this is needed.
    if isinstance(themearray, ThemeArray):
        themearray = themearray.to_list()

    # To be able to truncate a themearray that can contain themerefs we need to flatten the array
    # (replace the themerefs with the corresponding themearray) first
    themearray_flattened = themearray_flatten(themearray)

    for element in themearray_flattened:
        max_element_len = max_len - themearray_len(truncated_themearray)
        if len(element) > max_element_len:
            string = str(element)
            attr = element.get_themeattr()
            selected = element.get_selected()
            truncated_themearray.append(ThemeStr(string[0:max_element_len],
                                                 attr, selected=selected))
            break
        truncated_themearray.append(element)

    if output_format == ThemeArray:
        truncated_themearray = ThemeArray(cast(List[Union[ThemeRef, ThemeStr]],
                                               truncated_themearray))

    return truncated_themearray


def themearray_len(themearray: Union[ThemeArray, List[Union[ThemeRef, ThemeStr]]]) -> int:
    """
    Given a themearray (either a true ThemeArray or List[Union[ThemeRef, ThemeStr]],
    return its length

        Parameters:
            themearray (ThemeArray): A themearray
        Returns:
            (int): The length of the unformatted string
    """
    return len(themearray_to_string(themearray))


# pylint: disable-next=too-many-branches
def themeattr_to_curses(themeattr: ThemeAttr, selected: bool = False) -> Tuple[int, int]:
    """
    Given a themeattr returns a tuple with curses color + curses attributes

        Parameters:
            themeattr (ThemeAttr): The ThemeAttr to convert
            selected (bool): [optional] True is selected, False otherwise
        Returns:
            (int, int):
                (int): A curses color
                (int): Curses attributes
    """
    context, key = themeattr
    tmp_attr = deep_get(theme, DictPath(f"{context}#{key}"))

    if tmp_attr is None:
        # debuglog.add([
        #         [ANSIThemeStr("Could not find the tuple (", "default"),
        #          ANSIThemeStr(f"{context}", "emphasis"),
        #          ANSIThemeStr(", ", "default"),
        #          ANSIThemeStr(f"{key}", "emphasis"),
        #          ANSIThemeStr(") in theme.", "default")],
        #         [ANSIThemeStr("Using (", "default"),
        #          ANSIThemeStr("main", "emphasis"),
        #          ANSIThemeStr(", ", "default"),
        #          ANSIThemeStr("default", "emphasis"),
        #          ANSIThemeStr(") as fallback.", "default")],
        #        ], severity=LogLevel.ERR, facility=str(themefile))
        tmp_attr = deep_get(theme, DictPath("main#default"))

    if isinstance(tmp_attr, dict):
        if selected:
            attr = tmp_attr["selected"]
        else:
            attr = tmp_attr["unselected"]
    else:
        attr = tmp_attr

    if isinstance(attr, list):
        col, attr = attr
    else:
        col = attr
        attr = "normal"

    if isinstance(attr, str):
        attr = [attr]
    else:
        attr = list(attr)

    tmp = 0

    for item in attr:
        # if not isinstance(item, str):
        #     debuglog.add([
        #             [ANSIThemeStr("Invalid text attribute used in theme; "
        #                              "attribute has to be a string and one of:", "default")],
        #             [ANSIThemeStr("“", "default"),
        #              ANSIThemeStr("dim", "emphasis"),
        #              ANSIThemeStr("“, “", "default"),
        #              ANSIThemeStr("normal", "emphasis"),
        #              ANSIThemeStr("“, “", "default"),
        #              ANSIThemeStr("bold", "emphasis"),
        #              ANSIThemeStr("“, “", "default"),
        #              ANSIThemeStr("underline", "emphasis"),
        #              ANSIThemeStr("“.", "default")],
        #             [ANSIThemeStr("Using “", "default"),
        #              ANSIThemeStr("normal", "emphasis"),
        #              ANSIThemeStr("“ as fallback.", "default")],
        #     ], severity=LogLevel.ERR, facility=str(themefile))
        if item == "dim":
            tmp |= curses.A_DIM
        elif item == "normal":
            tmp |= curses.A_NORMAL
        elif item == "bold":
            tmp |= curses.A_BOLD
        elif item == "underline":
            tmp |= curses.A_UNDERLINE
        else:
            # debuglog.add([
            #         [ANSIThemeStr("Invalid text attribute “", "default"),
            #          ANSIThemeStr(f"{item}", "emphasis"),
            #          ANSIThemeStr("“ used in theme; attribute has to be one of:", "default")],
            #         [ANSIThemeStr("“", "default"),
            #          ANSIThemeStr("dim", "emphasis"),
            #          ANSIThemeStr("“, “", "default"),
            #          ANSIThemeStr("normal", "emphasis"),
            #          ANSIThemeStr("“, “", "default"),
            #          ANSIThemeStr("bold", "emphasis"),
            #          ANSIThemeStr("“, “", "default"),
            #          ANSIThemeStr("underline", "emphasis"),
            #          ANSIThemeStr("“.", "default")],
            #         [ANSIThemeStr("Using “", "default"),
            #          ANSIThemeStr("normal", "emphasis"),
            #          ANSIThemeStr("“ as fallback.", "default")],
            # ], severity=LogLevel.ERR, facility=str(themefile))
            tmp |= curses.A_NORMAL
    curses_attrs = tmp

    curses_col = __color[col][selected]
    if curses_col is None:
        # debuglog.add([
        #         [ANSIThemeStr("themeattr_to_curses()", "emphasis")],
        #         [ANSIThemeStr("called with non-existing (color, selected) tuple ", "error")],
        #         [ANSIThemeStr(f"{col}", "argument")],
        #         [ANSIThemeStr(", ", "error")],
        #         [ANSIThemeStr(f"{selected}", "argument")],
        #         [ANSIThemeStr(").", "error")],
        # ], severity=LogLevel.ERR, facility=str(themefile))
        raise KeyError(f"themeattr_to_curses: (color: {col}, selected: {selected}) not found")
    return curses_col, curses_attrs


def themeattr_to_curses_merged(themeattr: ThemeAttr, selected: bool = False) -> int:
    """
    Given a themeattr returns merged curses color + curses attributes

        Parameters:
            themeattr (ThemeAttr): The ThemeAttr to convert
            selected (bool): [optional] True is selected, False otherwise
        Returns:
            (int): Curses color | attrs
    """
    curses_col, curses_attrs = themeattr_to_curses(themeattr, selected)
    return curses_col | curses_attrs


def themestring_to_cursestuple(themestring: ThemeStr,
                               selected: Optional[bool] = None) -> Tuple[str, int]:
    """
    Given a themestring returns a cursestuple

        Parameters:
            themestring (ThemeStr): The ThemeStr to convert
            selected (bool): [optional] True is selected, False otherwise
        Returns:
            (str, int): A curses tuple for use with addformattedarray()
    """
    string = str(themestring)
    themeattr = themestring.get_themeattr()

    if selected is None:
        selected = themestring.get_selected()
        if selected is None:
            selected = False

    return (string, themeattr_to_curses_merged(themeattr, selected))


def themearray_flatten(themearray: List[Union[ThemeRef, ThemeStr]],
                       selected: Optional[bool] = None) -> List[ThemeStr]:
    """
    Replace all ThemeRefs in a ThemeArray with ThemeStr

        Parameters:
            themearray (ThemeArray): The themearray to flatten
            selected (bool): [optional] True is selected, False otherwise
        Returns:
            (ThemeArray): The flattened themearray
        Raises:
            ProgrammingError: themearray is not a themearray
    """
    themearray_flattened = []

    for item in themearray:
        if isinstance(item, ThemeStr):
            themearray_flattened.append(item)
        elif isinstance(item, ThemeRef):
            themearray_flattened += item.to_themearray()
        else:
            msg = [
                [("themearray_flatten()", "emphasis"),
                 (" called with invalid argument(s):", "error")],
                [("item = ", "default"),
                 (f"{item}", "argument"),
                 (" (type: ", "default"),
                 (f"{type(item)}", "argument"),
                 (", expected: ", "default"),
                 ("ThemeRef", "argument"),
                 (" or ", "default"),
                 ("ThemeStr", "argument"),
                 (")", "default")],
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   facility=str(themefile),
                                   formatted_msg=formatted_msg)

    return themearray_flattened


def themearray_wrap_line(themearray: List[Union[ThemeRef, ThemeStr]],
                         maxwidth: int = -1, wrap_marker: bool = True,
                         selected: Optional[bool] = None) -> List[List[Union[ThemeRef,
                                                                             ThemeStr]]]:
    """
    Given a themearray, split it into multiple lines, each maxwidth long

        Parameters:
            themearray (ThemeArray): The themearray to wrap
            maxwidth (int): The maximum number of characters before wrapping
            wrap_marker (bool): Should the line end in a wrap marker?
            selected (bool): Should the line(s) be selected?
        Returns:
            ([ThemeArray]): A list of themearrays
    """
    if maxwidth == -1:
        return [themearray]

    themearray_flat = themearray_flatten(themearray, selected=selected)

    linebreak = ThemeRef("separators", "line_break").to_themearray()

    if wrap_marker:
        linebreaklen = len(linebreak)
    else:
        linebreaklen = 0

    themearrays: List[List[Union[ThemeRef, ThemeStr]]] = []
    tmp_themearray: List[Union[ThemeRef, ThemeStr]] = []
    tmplen = 0
    i = 0

    while True:
        # Does the fragment fit?
        tfilen = len(themearray_flat[i])
        if tmplen + tfilen < maxwidth:
            tmp_themearray.append(themearray_flat[i])
            tmplen += tfilen
            i += 1
        # Nope
        else:
            string = str(themearray_flat[i])
            themeattr = themearray_flat[i].get_themeattr()

            tmp_themearray.append(ThemeStr(string[:maxwidth - linebreaklen - tmplen], themeattr))
            if wrap_marker:
                tmp_themearray += linebreak
            themearray_flat[i] = ThemeStr(string[maxwidth - linebreaklen - tmplen:], themeattr)
            themearrays.append(tmp_themearray)
            tmp_themearray = []
            tmplen = 0
            continue
        if i == len(themearray_flat):
            themearrays.append(tmp_themearray)
            break

    return themearrays


ignoreinput: bool = False


# A generic window widget
# items is a list of tuples, like so:
# (widgetlineattr, strarray, strarray, ...)
# A strarray is a list of tuples, where every tuple is of the format (string, attribute)
# Alternatively items can be a list of dicts
# on the format:
# {
#    "lineattrs": ...,
#    "columns": strarray, ...,
#    "retval": the value to return if this item is selected (any type is allowed)
# }
# pylint: disable-next=too-many-arguments,too-many-locals,too-many-statements,too-many-branches
def windowwidget(stdscr: curses.window, maxy: int, maxx: int, y: int, x: int,
                 items: List[Dict[str, Any]],
                 **kwargs: Any) -> Union[Set,
                                         Tuple[int, Union[bool, int, str, None]],
                                         Union[bool, int, str, None]]:
    global ignoreinput  # pylint: disable=global-statement

    headers: Tuple[str, ...] = deep_get(kwargs, DictPath("headers"))
    title: str = deep_get(kwargs, DictPath("title"), "")
    preselection: Union[str, Set[int]] = deep_get(kwargs, DictPath("preselection"), "")
    cursor: bool = deep_get(kwargs, DictPath("cursor"), True)
    taggable: bool = deep_get(kwargs, DictPath("taggable"), False)
    confirm: bool = deep_get(kwargs, DictPath("confirm"), False)
    confirm_buttons: List = deep_get(kwargs, DictPath("confirm_buttons"), [])
    key_f6: bool = deep_get(kwargs, DictPath("KEY_F6"), False)

    stdscr.refresh()
    ignoreinput = False

    padwidth = 2
    listpadheight = len(items)

    if confirm_buttons is None:
        confirm_buttons = []

    if isinstance(items[0], tuple):
        raise ValueError("The text passed to windowwidget() is invalid; "
                         f"please report this!\n\n{items}")

    columns = len(items[0]["columns"])
    lengths = [0] * columns

    if headers is not None:
        if len(headers) != columns:
            raise ValueError("Mismatch: Number of headers passed to windowwidget "
                             f"({len(headers)}) does not match number of columns ({columns})")

        for i in range(0, columns):
            lengths[i] = len(headers[i])

    tagprefix = str(ThemeRef("separators", "tag"))

    # Leave room for a tag prefix column if needed
    if taggable:
        tagprefixlen = len(tagprefix)
    else:
        tagprefixlen = 0

    # Every item is a line
    for item in items:
        for i in range(0, columns):
            length = themearray_len(item["columns"][i])
            lengths[i] = max(lengths[i], length)

    listpadwidth = 0
    for i in range(0, columns):
        if i > 0:
            listpadwidth += padwidth
        listpadwidth += lengths[i]

    if len(title) > listpadwidth:
        lengths[columns - 1] += len(title) - listpadwidth

    listpadwidth = max(listpadwidth, len(title)) + tagprefixlen

    extra_height = 0

    if headers is not None:
        extra_height += 2
    if confirm:
        extra_height += 2

    height = min(maxy - 5, listpadheight) + 2 + extra_height
    maxcurypos = min(height - 3 - extra_height, listpadheight - 1)
    maxyoffset = listpadheight - (height - 2 - extra_height)
    width = min(maxx - 5, listpadwidth) + 2
    button_lengths = 0
    if confirm:
        for button in confirm_buttons[1:]:
            for string, _ in button:
                button_lengths += len(string)
        button_lengths += len(confirm_buttons) - 2
        width = max(button_lengths, width)

    xoffset = 0
    maxxoffset = listpadwidth - (width - 2)

    yoffset = 0

    ypos = y - height // 2
    xpos = x - width // 2

    if headers is not None:
        headerpadypos = ypos + 1
        listpadypos = ypos + 3
        scrollbarypos = 3
    else:
        listpadypos = ypos + 1
        scrollbarypos = 1

    if confirm:
        buttonpadypos = ypos + height - 2

    win = curses.newwin(height, width, ypos, xpos)
    col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "boxdrawing"))
    win.attrset(col)
    win.clear()
    win.border()
    col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "default"))
    win.bkgd(" ", col)
    win.addstr(0, 1, title, themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))
    listpad = curses.newpad(listpadheight + 1, listpadwidth + 1)
    col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "default"))
    listpad.bkgd(" ", col)

    if headers is not None:
        headerpad = curses.newpad(1, listpadwidth + 1)
        col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "header"))
        headerpad.bkgd(" ", col)

    if confirm:
        buttonpad = curses.newpad(1, listpadwidth + 1)
        col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "header"))
        headerpad.bkgd(" ", col)

    selection: Union[int, str, None] = None
    curypos = 0

    headerarray: List[Union[ThemeRef, ThemeStr]] = []

    # Generate headers
    if headers is not None:
        if taggable:
            headerarray.append(ThemeStr(f"{tagprefix}", ThemeAttr("windowwidget", "highlight")))
        for i in range(0, columns):
            extrapad = padwidth
            if i == columns - 1:
                extrapad = 0
            headerarray.append(ThemeStr((headers[i].ljust(lengths[i] + extrapad)),
                                        ThemeAttr("windowwidget", "header")))

    # Move to preselection
    if isinstance(preselection, str):
        if preselection != "":
            for y_, item in enumerate(items):
                if isinstance(item["columns"][0][0], ThemeStr):
                    tmp_selection = str(item["columns"][0][0])
                else:
                    tmp_selection = item["columns"][0][0][0]

                if "retval" in item and item["retval"] == preselection \
                        or "retval" not in item and tmp_selection == preselection:
                    curypos, yoffset = move_cur_with_offset(0, yoffset, maxcurypos, maxyoffset, y_)
                    break
        tagged_items = set()
    elif isinstance(preselection, set):
        tagged_items = preselection.copy()
    else:
        raise ValueError("is_taggable() == True, "
                         f"but type(preselection) == {type(preselection)} (must be str or set())")

    # pylint: disable-next=too-many-nested-blocks
    while selection is None:
        for y_, item in enumerate(items):
            if cursor:
                # These parentheses helps readability
                # pylint: disable-next=superfluous-parens
                selected_ = (yoffset + curypos == y_)
            else:
                selected_ = False

            lineattributes = item["lineattrs"]
            linearray: List[Union[ThemeRef, ThemeStr]] = []

            if taggable:
                if y_ in tagged_items:
                    linearray.append(ThemeStr(f"{tagprefix}", ThemeAttr("windowwidget", "tag")))
                else:
                    linearray.append(ThemeStr("".ljust(tagprefixlen),
                                              ThemeAttr("windowwidget", "tag")))

            for _x, column in enumerate(item["columns"]):
                themearray: List[Union[ThemeRef, ThemeStr]] = []
                length = 0

                for string in column:
                    if isinstance(string, ThemeStr):
                        tmpstring = str(string)
                        attribute = string.themeattr
                    elif isinstance(string, ThemeRef):
                        raise ProgrammingError("FIXME: windowwidget() "
                                               "currently cannot handle ThemeRef")
                    else:
                        raise ProgrammingError("In windowwidget(); "
                                               f"we want to get rid of this: items={items}")
                        # tmpstring = string[0]
                        # attribute = string[1]
                    strlen = len(tmpstring)
                    length += strlen

                    if lineattributes & (WidgetLineAttrs.INVALID) != 0:
                        attribute = ThemeAttr("windowwidget", "alert")
                        themearray.append(ThemeStr(tmpstring, attribute, selected_))
                    elif lineattributes \
                            & (WidgetLineAttrs.DISABLED | WidgetLineAttrs.UNSELECTABLE) != 0:
                        attribute = ThemeAttr("windowwidget", "dim")
                        themearray.append(ThemeStr(tmpstring, attribute, selected_))
                    elif lineattributes & WidgetLineAttrs.SEPARATOR != 0:
                        if attribute == ThemeAttr("windowwidget", "default"):
                            attribute = ThemeAttr("windowwidget", "highlight")
                        tpad = listpadwidth - strlen
                        lpad = int(tpad / 2)
                        rpad = tpad - lpad
                        lpadstr = "".ljust(lpad, "─")
                        rpadstr = "".rjust(rpad, "─")

                        themearray.append(ThemeStr(lpadstr,
                                                   ThemeAttr("windowwidget", "highlight"),
                                          selected_))
                        themearray.append(ThemeStr(tmpstring, attribute, selected_))
                        themearray.append(ThemeStr(rpadstr,
                                                   ThemeAttr("windowwidget", "highlight"),
                                          selected_))
                    else:
                        themearray.append(ThemeStr(tmpstring, attribute, selected_))

                if lineattributes & WidgetLineAttrs.SEPARATOR == 0:
                    padstring = "".ljust(lengths[_x] - length + padwidth)
                    themearray.append(ThemeStr(padstring, attribute, selected_))

                linearray += themearray

            addthemearray(listpad, linearray, y=y_, x=0)

        _upperarrow, _lowerarrow, _vdragger = \
            scrollbar_vertical(win, width - 1, scrollbarypos, height - 2, listpadheight, yoffset,
                               ThemeAttr("windowwidget", "boxdrawing"))
        _leftarrow, _rightarrow, _hdragger = \
            scrollbar_horizontal(win, height - 1, 1, width - 2, listpadwidth, xoffset,
                                 ThemeAttr("windowwidget", "boxdrawing"))

        if headers is not None:
            addthemearray(headerpad, headerarray, y=0, x=0)
            headerxoffset = 0
            if headers:
                headerxoffset = xoffset
            headerpad.noutrefresh(0, headerxoffset,
                                  headerpadypos, xpos + 1, headerpadypos, xpos + width - 2)
            window_tee_hline(win, 2, 0, width - 1, ThemeAttr("windowwidget", "boxdrawing"))

        listpad.noutrefresh(yoffset, xoffset, listpadypos,
                            xpos + 1, ypos + height - 2, xpos + width - 2)

        if confirm:
            x = width - button_lengths - 2
            col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "header"))
            buttonpad.bkgd(" ", col)
            for button in confirm_buttons[1:]:
                _, x = addthemearray(buttonpad, button, y=0, x=x)
                x += 1
            buttonpad.noutrefresh(0, 0, buttonpadypos, xpos + 1, buttonpadypos, xpos + width - 2)
            window_tee_hline(win, height - 3, 0, width - 1,
                             ThemeAttr("windowwidget", "boxdrawing"))

        win.noutrefresh()
        curses.doupdate()

        stdscr.timeout(100)
        oldcurypos = curypos
        oldyoffset = yoffset

        c = stdscr.getch()

        # The following inputs terminate the loop
        if c == curses.KEY_RESIZE:
            curses.endwin()
            ansithemeprint([ANSIThemeStr("Critical", "critical"),
                            ANSIThemeStr(": Live resizing windowwidget() is currently broken; "
                                         "this is a known issue.", "default")], stderr=True)
            sys.exit(errno.ENOTSUP)
        if c == 27:  # ESCAPE
            selection = ""
            confirm_press = c
            break
        if c == ord("") or c == ord(""):
            curses.endwin()
            sys.exit()
        if key_f6 and c == curses.KEY_F6:
            # This is used to toggle categorised list on/off
            selection = -c
            break
        if c in (curses.KEY_ENTER, 10, 13) \
                and items[yoffset + curypos]["lineattrs"] & (WidgetLineAttrs.UNSELECTABLE) == 0 \
                and not confirm:
            if deep_get(items[yoffset + curypos], DictPath("retval")) is None:
                selection = items[yoffset + curypos]["columns"]
            else:
                selection = items[yoffset + curypos]["retval"]
            break
        if confirm and c in confirm_buttons[0]:
            confirm_press = c
            break

        # While all of these are just navigation
        if taggable and c == ord(" "):
            if curypos + yoffset in tagged_items:
                tagged_items.discard(curypos + yoffset)
            else:
                tagged_items.add(curypos + yoffset)
        elif ord("a") <= c <= ord("z") and cursor and not confirm:
            # Find the next entry starting with the pressed letter;
            # wrap around if the bottom is hit stop if oldycurypos + oldyoffset is hit
            while True:
                curypos, yoffset = \
                    move_cur_with_offset(curypos, yoffset,
                                         maxcurypos, maxyoffset, +1, wraparound=True)
                lineattributes = items[yoffset + curypos]["lineattrs"]
                tmp_char = str(items[yoffset + curypos]["columns"][0][0])[0]
                if tmp_char.lower() == chr(c).lower() \
                        and lineattributes & WidgetLineAttrs.DISABLED == 0:
                    break
                if (curypos + yoffset) == (oldcurypos + oldyoffset):
                    # While we are at the same position in the list
                    # we might not be at the same offsets
                    curypos = oldcurypos
                    yoffset = oldyoffset
                    break
        elif ord("A") <= c <= ord("Z") and cursor and not confirm:
            # Find the previous entry starting with the pressed letter;
            # wrap around if the top is hit stop if oldycurypos + oldyoffset is hit
            while True:
                curypos, yoffset = \
                    move_cur_with_offset(curypos, yoffset,
                                         maxcurypos, maxyoffset, -1, wraparound=True)
                lineattributes = items[yoffset + curypos]["lineattrs"]
                tmp_char = str(items[yoffset + curypos]["columns"][0][0])[0]
                if tmp_char.lower() == chr(c).lower() \
                        and lineattributes & WidgetLineAttrs.DISABLED == 0:
                    break
                if (curypos + yoffset) == (oldcurypos + oldyoffset):
                    # While we are at the same position in the list
                    # we might not be at the same offsets
                    curypos = oldcurypos
                    yoffset = oldyoffset
                    break
        elif c == ord("\t") and cursor:
            # Find next group
            while items[yoffset + curypos]["lineattrs"] & WidgetLineAttrs.SEPARATOR == 0:
                curypos, yoffset = \
                    move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, +1)
                if (curypos + yoffset) == (maxcurypos + maxyoffset):
                    break
                # OK, we found a group, now find the first not-group
            while items[yoffset + curypos]["lineattrs"] & WidgetLineAttrs.SEPARATOR != 0:
                curypos, yoffset = \
                    move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, +1)
                if (curypos + yoffset) == (maxcurypos + maxyoffset):
                    break
        elif c == curses.KEY_BTAB and cursor:
            # Find previous group
            while items[yoffset + curypos]["lineattrs"] & WidgetLineAttrs.SEPARATOR == 0:
                curypos, yoffset = \
                    move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, -1)
                if (curypos + yoffset) == 0:
                    break
            # OK, we found a group, now find the previous not-group
            while items[yoffset + curypos]["lineattrs"] & WidgetLineAttrs.SEPARATOR != 0:
                curypos, yoffset = \
                    move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, -1)
                if (curypos + yoffset) == 0:
                    break
            # Finally find the first entry in that group
            while (curypos + yoffset) > 0 \
                    and items[yoffset + curypos]["lineattrs"] & WidgetLineAttrs.SEPARATOR != 0:
                curypos, yoffset = \
                    move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, -1)
                if (curypos + yoffset) == 0:
                    break
        elif c == curses.KEY_UP:
            curypos, yoffset = move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, -1)
        elif c == curses.KEY_DOWN:
            curypos, yoffset = move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, +1)
        elif c == curses.KEY_LEFT:
            xoffset = max(xoffset - 1, 0)
        elif c == curses.KEY_RIGHT:
            xoffset = min(xoffset + 1, maxxoffset)
        elif c == curses.KEY_HOME:
            xoffset = 0
        elif c == curses.KEY_END:
            xoffset = maxxoffset
        elif c == curses.KEY_SHOME:
            curypos = 0
            yoffset = 0
        elif c == curses.KEY_SEND:
            curypos = maxcurypos
            yoffset = maxyoffset
        elif c == curses.KEY_PPAGE:
            curypos, yoffset = move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, -10)
        elif c == curses.KEY_NPAGE:
            curypos, yoffset = move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, +10)

        # These only apply if we use a cursor
        if cursor:
            # Find the last acceptable line
            if (yoffset + curypos) == (maxcurypos + maxyoffset):
                while items[yoffset + curypos]["lineattrs"] \
                        & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
                    curypos, yoffset = move_cur_with_offset(curypos, yoffset,
                                                            maxcurypos, maxyoffset, -1)
            # We tried moving backwards; do we need to go farther?
            if (yoffset + curypos) > (oldyoffset + oldcurypos):
                while (yoffset + curypos) < len(items) \
                        and items[yoffset + curypos]["lineattrs"] \
                        & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
                    curypos, yoffset = \
                        move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, +1)
                if (yoffset + curypos) == len(items) \
                        and items[yoffset + curypos]["lineattrs"] \
                        & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
                    yoffset = oldyoffset
                    curypos = oldcurypos
            # Find the first acceptable line
            elif (yoffset + curypos) == 0:
                while items[yoffset + curypos]["lineattrs"] \
                        & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
                    curypos, yoffset = \
                        move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, +1)
            # We tried moving backwards; do we need to go farther?
            elif (yoffset + curypos) < (oldyoffset + oldcurypos):
                while (yoffset + curypos) \
                        and items[yoffset + curypos]["lineattrs"] \
                        & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
                    curypos, yoffset = \
                        move_cur_with_offset(curypos, yoffset, maxcurypos, maxyoffset, -1)
                if (yoffset + curypos) == 0 \
                        and items[yoffset + curypos]["lineattrs"] \
                        & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
                    curypos = oldcurypos + oldyoffset
                    yoffset = 0

        if not cursor:
            yoffset += curypos
            yoffset = min(maxyoffset, yoffset)
            curypos = 0

    del listpad
    del win

    if taggable:
        return tagged_items

    if confirm:
        return (confirm_press, selection)

    return selection


label_headers = ["Label:", "Value:"]


def get_labels(labels: Optional[Dict]) -> Optional[List[Dict]]:
    """
    Get labels

        Parameters:
            labels (dict): A dict
        Returns:
            ([dict]): A formatted list of labels suitable for the windowwidget
    """
    if labels is None:
        return None

    rlabels = []
    for key, value in labels.items():
        rlabels.append({
            "lineattrs": WidgetLineAttrs.NORMAL,
            "columns": [[ThemeStr(key, ThemeAttr("windowwidget", "highlight"))],
                        [ThemeStr(value.replace("\n", "\\n"),
                                  ThemeAttr("windowwidget", "default"))]],
            "retval": None,
        })
    return rlabels


annotation_headers: Tuple[str, ...] = ("Annotation:", "Value:")


def get_annotations(annotations: Optional[Dict]) -> Optional[List[Dict]]:
    """
    Get annotations

        Parameters:
            annotations (dict): A dict
        Returns:
            ([dict]): A formatted list of annotations suitable for the windowwidget
    """
    return get_labels(annotations)


# pylint: disable-next=too-many-instance-attributes,too-many-public-methods
class UIProps:
    """
    The class used for the UI
    """

    # pylint: disable-next=too-many-statements
    def __init__(self, stdscr: curses.window) -> None:
        self.stdscr: curses.window = stdscr

        # Helptext
        self.helptext: Optional[List[Dict[str, Any]]] = None

        self.update_forced = False

        # The UID of the selected object (if applicable)
        self.selected_uid = None

        # Remember position by UID (if False we remember by cursor position)
        self.remember_uid = True

        # The timestamp
        self.last_timestamp_update: Optional[str] = None

        self.idle_timeout = 5
        self.last_action = datetime.now()

        # Info to use for populating lists, etc.
        self.sorted_list: List[Type] = []
        self.sortorder_reverse = False

        # Used for searching
        self.searchkey = ""

        # Used for label list
        self.labels: Optional[List[Dict]] = None

        # Used for annotation list
        self.annotations: Optional[List[Dict]] = None

        # Reference to the external color class
        self.miny = 0
        self.maxy = 0
        self.minx = 0
        self.maxx = 0
        self.mincurypos = 0
        self.maxcurypos = 0
        self.curypos = 0
        self.yoffset = 0
        self.xoffset = 0
        self.maxyoffset = 0
        self.maxxoffset = 0
        self.last_update: Optional[datetime] = None
        # Number of seconds between updates
        self.update_delay = 0
        # Has an update been requested?
        self.update_triggered = False
        # Update will update the content to display,
        # Refresh just updates the display
        self.refresh = True
        self.sortcolumn = ""
        self.sortkey1 = ""
        self.sortkey2 = ""
        self.field_list: Dict = {}

        self.helpstring = "[F1] / [Shift] + H: Help"
        # Should there be a timestamp in the upper right corner?
        self.timestamp = True

        self.selected: Union[None, Type] = None

        # For generic information
        self.infopadminwidth = 0
        self.infopadypos = 0
        self.infopadxpos = 0
        self.infopadheight = 0
        self.infopadwidth = 0
        self.infopad: Optional[curses.window] = None
        # For lists
        self.headerpadminwidth = 0
        self.headerpadypos = 0
        self.headerpadxpos = 0
        self.headerpadheight = 0
        self.headerpadwidth = 0
        self.headerpad: Optional[curses.window] = None
        self.listlen: int = 0
        # This one really is a misnomer and could possible be confused with the infopad
        self.sort_triggered = False
        self.regenerate_list = False
        self.info: List[Type] = []
        # This is a list of the xoffset for all headers in listviews
        self.tabstops: List[int] = []
        self.listpadypos = 0
        self.listpadxpos = 0
        self.listpadheight = 0
        self.listpadwidth = 0
        self.listpad: Optional[curses.window] = None
        self.listpadminwidth = 0
        self.reversible = True
        # For logs with a timestamp column
        self.tspadypos = 0
        self.tspadxpos = 0
        self.tspadheight = 0
        self.tspadwidth = len("YYYY-MM-DD HH:MM:SS")
        self.tspad: Optional[curses.window] = None
        self.borders = True
        self.logpadypos = 0
        self.logpadxpos = 0
        self.logpadheight = 0
        self.logpadwidth = 0
        self.logpad: Optional[curses.window] = None
        self.loglen = 0
        self.logpadminwidth = 0
        self.statusbar: Optional[curses.window] = None
        self.statusbarypos: int = 0
        self.continuous_log = False
        self.match_index: Optional[int] = None
        self.search_matches: Set[int] = set()
        self.timestamps: Optional[List[datetime]] = None
        self.facilities: Optional[List[str]] = None
        self.severities: Optional[List[LogLevel]] = None
        self.messages: Optional[List[Union[str, ThemeArray,
                                           List[Union[ThemeStr, ThemeRef]]]]] = None
        # For checking clicks/drags of the scrollbars
        self.leftarrow = -1, -1
        self.rightarrow = -1, -1
        self.hdragger = -1, -1, -1
        self.upperarrow = -1, -1
        self.lowerarrow = -1, -1
        self.vdragger = -1, -1, -1

        # Function handler for <enter> / <double-click>
        self.activatedfun: Optional[Callable] = None
        self.on_activation: Dict = {}
        self.extraref: Optional[str] = None
        self.data: Optional[bool] = None

        self.windowheader: str = ""
        self.view: Union[Optional[Tuple[str, str]], str] = ""

    def __del__(self) -> None:
        if self.infopad is not None:
            del self.infopad
        if self.listpad is not None:
            del self.listpad
        if self.headerpad is not None:
            del self.headerpad
        if self.logpad is not None:
            del self.logpad

    def reselect_uid(self) -> None:
        pos = self.curypos + self.yoffset
        if len(self.sorted_list) > pos:
            try:
                self.selected_uid = getattr(self.sorted_list[pos], "__uid")
            except (AttributeError, IndexError):
                self.selected_uid = None

    def update_sorted_list(self) -> None:
        if self.curypos == -1 or self.yoffset == -1:
            self.curypos = 0
            self.yoffset = 0

        if not self.sort_triggered:
            return
        self.sort_triggered = False
        self.list_needs_regeneration(True)

        sortkey1, sortkey2 = self.get_sortkeys()
        try:
            self.sorted_list = natsorted(self.info,
                                         key=attrgetter(sortkey1, sortkey2),
                                         reverse=self.sortorder_reverse)
        except TypeError:
            # We could not sort the list; we should log and just keep the current sort order
            pass

        pos = self.curypos + self.yoffset

        # If self.remember_uid is set we (try to) follow the item;
        # else we remain at the cursor position (if possible)
        if self.remember_uid:
            for y, item in enumerate(self.sorted_list):
                uid = None
                try:
                    uid = getattr(item, "__uid")
                except AttributeError:
                    pass
                # If the first element lacks "__uid" all elemenets will lack it
                if uid is None:
                    break
                if self.selected_uid is None and y == pos:
                    self.selected_uid = uid
                if uid == self.selected_uid:
                    self.move_cur_with_offset(y - pos)

    def update_info(self, info: List[Type]) -> int:
        self.info = info
        self.listlen = len(self.info)
        self.sort_triggered = True

        return self.listlen

    def update_log_info(self, timestamps: Optional[List[datetime]],
                        facilities: Optional[List[str]],
                        severities: Optional[List[LogLevel]],
                        messages: Optional[List[Union[str, ThemeArray,
                                                      List[Union[ThemeStr,
                                                                 ThemeRef]]]]]) -> None:
        self.timestamps = timestamps
        self.facilities = facilities
        self.severities = severities
        self.messages = messages

    def set_update_delay(self, delay: int) -> None:
        self.update_delay = delay
        if delay > 0:
            self.last_update = datetime.now()

    def force_update(self) -> None:
        self.update_triggered = True
        self.refresh = True
        self.sort_triggered = True
        self.list_needs_regeneration(True)

    def force_refresh(self) -> None:
        self.list_needs_regeneration(True)
        self.refresh_all()
        self.refresh_window()
        self.update_window()

    def disable_update(self) -> None:
        self.last_update = None

    def reset_update_delay(self) -> None:
        if self.update_delay > 0:
            self.last_update = datetime.now()

    def is_update_triggered(self) -> bool:
        if self.update_triggered:
            self.update_triggered = False
            return True

        if self.last_update is None or self.update_delay == 0:
            return False

        timediff = datetime.now() - self.last_update
        duration = timediff.days * 24 * 60 * 60 + timediff.seconds

        return duration >= self.update_delay

    def list_needs_regeneration(self, regenerate_list: bool) -> None:
        self.regenerate_list = regenerate_list

    def is_idle(self) -> bool:
        """
        Check whether the UI is considered idle;
        The UI is idle if nothing has updated last_action within
        the last idle_timeout seconds

            Returns:
                (bool): True if idle, False if not idle
        """
        return (datetime.now() - self.last_action).seconds > self.idle_timeout

    def force_idle(self) -> None:
        """
        Set last_action far enough back so that the system is considered idle;
        this should be done when doing a force reload
        """
        self.last_action = datetime.now() - timedelta(seconds=self.idle_timeout)

    def is_list_regenerated(self) -> bool:
        return not self.regenerate_list

    def select(self, selection: Union[None, Type]) -> None:
        self.selected = selection

    def select_if_y(self, y: int, selection: Type) -> None:
        if self.yoffset + self.curypos == y:
            self.select(selection)

    def refresh_selected(self) -> None:
        if not self.sorted_list or self.yoffset + self.curypos >= self.listlen:
            self.selected = None
        else:
            self.selected = self.sorted_list[self.yoffset + self.curypos]

    def is_selected(self, selected: Union[None, Type]) -> bool:
        if selected is None:
            return False

        return self.selected == selected

    def get_selected(self) -> Union[None, Type]:
        return self.selected

    # Default behaviour:
    # timestamps enabled, no automatic updates, default sortcolumn = "status"
    # pylint: disable-next=too-many-arguments
    def init_window(self, **kwargs: Any) -> None:
        field_list: Dict = deep_get(kwargs, DictPath("field_list"), {})
        view: Union[Optional[Tuple[str, str]], str] = deep_get(kwargs, DictPath("view"))
        windowheader: str = deep_get(kwargs, DictPath("windowheader"), "")
        update_delay: int = deep_get(kwargs, DictPath("update_delay"), -1)
        sortcolumn: str = deep_get(kwargs, DictPath("sortcolumn"), "status")
        sortorder_reverse: bool = deep_get(kwargs, DictPath("sortorder_reverse"), False)
        reversible: bool = deep_get(kwargs, DictPath("reversible"), True)
        helptext: Optional[List[Dict[str, Any]]] = deep_get(kwargs, DictPath("helptext"))
        activatedfun: Optional[Callable] = deep_get(kwargs, DictPath("activatedfun"))
        on_activation: Optional[Dict[str, Any]] = deep_get(kwargs, DictPath("on_activation"))
        extraref: Optional[str] = deep_get(kwargs, DictPath("extraref"))
        data: Optional[bool] = deep_get(kwargs, DictPath("data"))

        self.field_list = field_list
        self.searchkey = ""
        self.sortcolumn = sortcolumn
        self.sortorder_reverse = sortorder_reverse
        self.reversible = reversible
        self.sortkey1, self.sortkey2 = self.get_sortkeys()
        self.set_update_delay(update_delay)
        self.view = view

        self.resize_window()

        self.windowheader = windowheader
        self.headerpad = None
        self.listpad = None
        self.infopad = None
        self.tspad = None
        self.borders = True
        self.logpad = None
        self.helptext = helptext

        if on_activation is None:
            on_activation = {}

        self.activatedfun = activatedfun
        self.on_activation = on_activation
        self.extraref = extraref
        self.data = data

    def reinit_window(self, field_list: Dict, sortcolumn: str) -> None:
        self.field_list = field_list
        self.searchkey = ""
        self.sortcolumn = sortcolumn
        self.sortkey1, self.sortkey2 = self.get_sortkeys()
        self.resize_window()

    # pylint: disable-next=too-many-branches
    def update_window(self, update: str = "true") -> None:
        hline = deep_get(theme, DictPath("boxdrawing#hline"))

        maxyx = self.stdscr.getmaxyx()
        if self.maxy != (maxyx[0] - 1) or self.maxx != (maxyx[1] - 1):
            self.resize_window()
        self.stdscr.erase()
        self.stdscr.border()
        # If we do not have sideborders we need to clear the right border we just painted,
        # just in case the content of the logpad is not wide enough to cover it
        if not self.borders:
            for y in range(self.logpadypos, self.maxy - 1):
                self.addthemearray(self.stdscr,
                                   [ThemeStr(" ", ThemeAttr("main", "default"))],
                                   y=y, x=self.maxx)

        self.draw_winheader()
        self.update_timestamp(update=update)

        if self.headerpad is not None:
            self.headerpad.clear()
            # Whether to have one or two hlines depends on if we
            # overlap with the upper border or not
            if self.headerpadypos > 1:
                window_tee_hline(self.stdscr, self.headerpadypos - 1, 0, self.maxx)
            window_tee_hline(self.stdscr, self.headerpadypos + 1, 0, self.maxx)
            if not self.borders:
                if self.headerpadypos > 1:
                    self.addthemearray(self.stdscr,
                                       [ThemeStr(hline, ThemeAttr("main", "default"))],
                                       y=self.headerpadypos - 1, x=0)
                    self.addthemearray(self.stdscr,
                                       [ThemeStr(hline, ThemeAttr("main", "default"))],
                                       y=self.headerpadypos - 1, x=self.maxx)
                self.addthemearray(self.stdscr,
                                   [ThemeStr(hline, ThemeAttr("main", "default"))],
                                   y=self.headerpadypos + 1, x=0)
                self.addthemearray(self.stdscr,
                                   [ThemeStr(hline, ThemeAttr("main", "default"))],
                                   y=self.headerpadypos + 1, x=self.maxx)
        elif self.listpad is not None and not self.borders:
            self.addthemearray(self.stdscr,
                               [ThemeStr(" ", ThemeAttr("main", "default"))],
                               y=self.listpadypos - 1, x=0)
            self.addthemearray(self.stdscr,
                               [ThemeStr(" ", ThemeAttr("main", "default"))],
                               y=self.listpadypos - 1, x=self.maxx)

        if self.logpad is not None:
            if self.logpadypos > 2:
                window_tee_hline(self.stdscr, self.logpadypos - 1, 0, self.maxx)
            if self.borders:
                window_tee_hline(self.stdscr, self.maxy - 2, 0, self.maxx)
                if self.tspad is not None and self.tspadxpos != self.logpadxpos and self.loglen:
                    window_tee_vline(self.stdscr, self.logpadxpos - 1,
                                     self.logpadypos - 1, self.maxy - 2)
            else:
                # If the window lacks sideborders we want lines
                self.addthemearray(self.stdscr,
                                   [ThemeStr(hline, ThemeAttr("main", "default"))],
                                   y=self.logpadypos - 1, x=0)
                self.addthemearray(self.stdscr,
                                   [ThemeStr(hline, ThemeAttr("main", "default"))],
                                   y=self.logpadypos - 1, x=self.maxx)

        self.reset_update_delay()

    # pylint: disable-next=unused-argument
    def update_timestamp(self, ypos: int = 0, xpos: int = -1, update: str = "true") -> None:
        if xpos == -1:
            xpos = self.maxx
        if update == "true" or self.last_timestamp_update is None:
            # Elsewhere we use now(timezone.utc), but here we want the local timezone
            self.last_timestamp_update = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
        rtee = deep_get(theme, DictPath("boxdrawing#rtee"))
        ltee = deep_get(theme, DictPath("boxdrawing#ltee"))

        timestamparray: List[Union[ThemeRef, ThemeStr]] = [
            ThemeStr(rtee, ThemeAttr("main", "default")),
        ]

        if self.helpstring:
            timestamparray += [
                ThemeStr(self.helpstring, ThemeAttr("main", "statusbar")),
                ThemeRef("separators", "statusbar"),
            ]
        if update == "pending":
            timestamparray += [
                ThemeRef("separators", "statusbar_pending"),
            ]
        timestamparray += [
            ThemeStr(self.last_timestamp_update, ThemeAttr("main", "last_update")),
        ]

        if self.borders:
            timestamparray += [
                ThemeStr(ltee, ThemeAttr("main", "default")),
            ]

        xpos -= themearray_len(timestamparray)
        if not self.borders:
            xpos += 1
        self.addthemearray(self.stdscr, timestamparray, y=0, x=xpos)

    def draw_winheader(self) -> None:
        if self.windowheader != "":
            ltee = deep_get(theme, DictPath("boxdrawing#ltee"))
            rtee = deep_get(theme, DictPath("boxdrawing#rtee"))

            winheaderarray: List[Union[ThemeRef, ThemeStr]] = []

            if self.borders:
                winheaderarray += [
                    ThemeStr(rtee, ThemeAttr("main", "default")),
                ]

            winheaderarray += [
                ThemeRef("separators", "mainheader_prefix"),
                ThemeStr(f"{self.windowheader}", ThemeAttr("main", "header")),
                ThemeRef("separators", "mainheader_suffix"),
            ]
            if self.borders:
                winheaderarray += [
                    ThemeStr(ltee, ThemeAttr("main", "default")),
                ]
                self.addthemearray(self.stdscr, winheaderarray, y=0, x=1)
            else:
                self.addthemearray(self.stdscr, winheaderarray, y=0, x=0)

    def refresh_window(self) -> None:
        if self.borders:
            bl = deep_get(theme, DictPath("boxdrawing#llcorner"))
            br = deep_get(theme, DictPath("boxdrawing#lrcorner"))
            self.addthemearray(self.stdscr,
                               [ThemeStr(bl, ThemeAttr("main", "default"))],
                               y=self.maxy - 2, x=0)
            self.addthemearray(self.stdscr,
                               [ThemeStr(br, ThemeAttr("main", "default"))],
                               y=self.maxy - 2, x=self.maxx)

        # The extra status can change,
        # so we need to update the windowheader (which should not change)
        self.draw_winheader()

        mousestatus = "On" if get_mousemask() == -1 else "Off"
        mousearray: List[Union[ThemeRef, ThemeStr]] = [
            ThemeStr("Mouse: ", ThemeAttr("statusbar", "infoheader")),
            ThemeStr(f"{mousestatus}", ThemeAttr("statusbar", "highlight"))
        ]
        xpos = self.maxx - themearray_len(mousearray) + 1
        if self.statusbar is not None:
            self.addthemearray(self.statusbar, mousearray, y=0, x=xpos)
        ycurpos = self.curypos + self.yoffset
        maxypos = self.maxcurypos + self.maxyoffset
        if ycurpos >= 0 and maxypos >= 0:
            curposarray: List[Union[ThemeRef, ThemeStr]] = [
                ThemeStr("Line: ", ThemeAttr("statusbar", "infoheader")),
                ThemeStr(f"{ycurpos + 1}".rjust(len(str(maxypos + 1))),
                         ThemeAttr("statusbar", "highlight")),
                ThemeRef("separators", "statusbar_fraction"),
                ThemeStr(f"{maxypos + 1}", ThemeAttr("statusbar", "highlight"))
            ]
            xpos = self.maxx - themearray_len(curposarray) + 1
            if self.statusbar is not None:
                self.addthemearray(self.statusbar, curposarray, y=1, x=xpos)
        self.stdscr.noutrefresh()

    # This should be called when a resize event is detected
    def resize_window(self) -> None:
        self.stdscr.clear()
        maxyx = self.stdscr.getmaxyx()
        self.miny = 0
        self.maxy = maxyx[0] - 1
        self.maxx = maxyx[1] - 1
        self.mincurypos = self.miny
        # screen position
        self.curypos = self.mincurypos
        # offset relative pad
        self.yoffset = 0
        self.selected_uid = None
        self.maxyoffset = 0
        self.xoffset = 0
        self.maxxoffset = 0

        self.resize_statusbar()
        self.force_update()
        self.reselect_uid()

    def refresh_all(self) -> None:
        self.stdscr.touchwin()
        self.stdscr.noutrefresh()
        if self.infopad:
            self.refresh_infopad()
        if self.listpad:
            self.refresh_listpad()
        if self.logpad:
            self.refresh_logpad()
        if self.statusbar:
            self.refresh_statusbar()
        self.refresh = True

    # For generic information
    # Pass -1 as width to the infopadminwidth
    # pylint: disable-next=too-many-arguments
    def init_infopad(self, height: int, width: int, ypos: int, xpos: int,
                     labels: Optional[Dict] = None,
                     annotations: Optional[Dict] = None) -> curses.window:
        self.infopadminwidth = self.maxx + 1
        self.infopadypos = ypos
        self.infopadxpos = xpos
        self.infopadheight = height
        self.infopadwidth = max(width, self.infopadminwidth)
        self.infopad = curses.newpad(max(self.infopadheight, self.maxy), self.infopadwidth)
        self.labels = get_labels(labels)
        self.annotations = get_annotations(annotations)
        return self.infopad

    # Pass -1 to keep the current height/width
    def resize_infopad(self, height: int, width: int) -> None:
        if self.infopad is None:
            return
        self.infopadminwidth = self.maxx - self.infopadxpos
        if height != -1:
            self.infopadheight = height
        self.infopad.erase()
        if width != -1:
            self.infopadwidth = max(width, self.infopadminwidth)
        self.infopad.resize(max(self.infopadheight, self.maxy), self.infopadwidth)

    def refresh_infopad(self) -> None:
        if self.infopad is not None:
            height = self.infopadheight
            if self.borders:
                if self.logpad is None and self.listpad is None:
                    height = self.maxy - 3
                try:
                    self.infopad.noutrefresh(0, 0, self.infopadypos,
                                             self.infopadxpos, height, self.maxx - 1)
                except curses.error:
                    pass
            else:
                if self.logpad is None and self.listpad is None:
                    height = self.maxy - 2
                try:
                    self.infopad.noutrefresh(0, 0, self.infopadypos, self.infopadxpos - 1,
                                             height, self.maxx)
                except curses.error:
                    pass

            # If there's no logpad and no listpad, then the infopad is responsible for scrollbars
            if self.listpad is None and self.logpad is None and self.borders:
                self.upperarrow, self.lowerarrow, self.vdragger = \
                    scrollbar_vertical(self.stdscr, self.maxx, self.infopadypos,
                                       self.maxy - 3, self.infopadheight, self.yoffset,
                                       ThemeAttr("main", "boxdrawing"))
                self.leftarrow, self.rightarrow, self.hdragger = \
                    scrollbar_horizontal(self.stdscr, self.maxy - 2, self.infopadxpos,
                                         self.maxx - 1, self.infopadwidth - 1, self.xoffset,
                                         ThemeAttr("main", "boxdrawing"))

    # For (optionally) scrollable lists of information,
    # optionally with a header
    # Pass -1 as width to use listpadminwidth
    # pylint: disable-next=too-many-arguments
    def init_listpad(self, listheight: int, width: int, ypos: int, xpos: int,
                     header: bool = True) -> Tuple[Optional[curses.window], curses.window]:
        self.listpadminwidth = self.maxx
        if header:
            self.headerpadypos = ypos
            self.headerpadxpos = xpos
            self.headerpadheight = 1
            self.headerpadwidth = self.listpadminwidth
            self.listpadypos = ypos + 2
            self.headerpad = curses.newpad(self.headerpadheight, self.headerpadwidth)
        else:
            self.listpadypos = ypos
        self.listpadxpos = xpos
        self.listpadheight = self.maxy - 2 - self.listpadypos
        self.listpadwidth = max(width, self.listpadminwidth)
        self.listpad = curses.newpad(self.listpadheight, self.listpadwidth)
        self.curypos = 0
        self.yoffset = 0
        self.select(None)

        return self.headerpad, self.listpad

    # Pass -1 to keep the current height/width
    def resize_listpad(self, width: int) -> None:
        if self.listpad is None:
            return
        self.listpadheight = self.maxy - 2 - self.listpadypos
        self.listpadminwidth = self.maxx
        self.listpad.erase()
        if width != -1:
            self.listpadwidth = max(width + 1, self.listpadminwidth)
        else:
            width = self.listpadwidth

        if self.borders:
            self.maxcurypos = min(self.listpadheight - 1, self.listlen - 1)
        else:
            self.maxcurypos = min(self.listpadheight, self.listlen - 1)
        self.maxyoffset = self.listlen - (self.maxcurypos - self.mincurypos) - 1
        self.headerpadwidth = self.listpadwidth
        self.maxxoffset = max(0, self.listpadwidth - self.listpadminwidth)

        if self.headerpad is not None and self.headerpadheight > 0:
            self.headerpad.resize(self.headerpadheight, self.headerpadwidth)
        if self.listpadheight > 0:
            self.listpad.resize(max(self.listpadheight, self.maxy), self.listpadwidth)
        self.curypos = min(self.curypos, self.maxcurypos)
        self.yoffset = min(self.yoffset, self.maxyoffset)
        self.reselect_uid()

    def refresh_listpad(self) -> None:
        xpos = self.listpadxpos
        maxx = self.maxx - 1
        if not self.borders:
            xpos -= 1
            maxx = self.maxx
        if self.headerpad is not None:
            try:
                self.headerpad.noutrefresh(0, self.xoffset, self.headerpadypos,
                                           xpos, self.headerpadypos, maxx)
            except curses.error:
                pass
        if self.listpad is not None:
            if self.borders:
                try:
                    self.listpad.noutrefresh(0, self.xoffset, self.listpadypos,
                                             xpos, self.maxy - 3, maxx)
                except curses.error:
                    pass
                self.upperarrow, self.lowerarrow, self.vdragger = \
                    scrollbar_vertical(self.stdscr, x=maxx + 1, miny=self.listpadypos,
                                       maxy=self.maxy - 3, height=self.listlen,
                                       yoffset=self.yoffset,
                                       clear_color=ThemeAttr("main", "boxdrawing"))
                self.leftarrow, self.rightarrow, self.hdragger = \
                    scrollbar_horizontal(self.stdscr, y=self.maxy - 2, minx=self.listpadxpos,
                                         maxx=maxx, width=self.listpadwidth - 1,
                                         xoffset=self.xoffset,
                                         clear_color=ThemeAttr("main", "boxdrawing"))
            else:
                try:
                    self.listpad.noutrefresh(0, self.xoffset, self.listpadypos,
                                             xpos, self.maxy - 2, maxx)
                except curses.error:
                    pass

    # Recalculate the xpos of the log; this is needed when timestamps are toggled
    def recalculate_logpad_xpos(self, tspadxpos: int = -1,
                                timestamps: Optional[bool] = None) -> None:
        if tspadxpos == -1:
            if self.tspadxpos is None:
                raise ProgrammingError("logpad is not initialised and no tspad xpos provided")

        if timestamps is None:
            timestamps = self.tspadxpos != self.logpadxpos

        self.tspadxpos = tspadxpos

        if not timestamps:
            self.tspadwidth = 0
            self.logpadxpos = self.tspadxpos
        else:
            self.tspadwidth = len("YYYY-MM-DD HH:MM:SS")
            # self.tspadwidth = len("YYYY-MM-DD")
            self.logpadxpos = self.tspadxpos + self.tspadwidth + 1

    # For (optionally) scrollable log of information with optional timestamps
    # The log widget behaves a bit differently than the list widget;
    # to avoid a lot of wasted memory when most log messages are short and there's one
    # string that can go for miles (if you know what I mean), we keep the pad
    # the same height as the visible area, and only update the content of the pad
    # as the yoffset changes.  The pad is still variable width though.
    #
    # Pass -1 as width to use logpadminwidth
    def init_logpad(self, width: int, ypos: int, xpos: int,
                    timestamps: bool = True) -> Tuple[Optional[curses.window], curses.window]:
        self.match_index = None
        self.search_matches = set()

        self.logpadheight = self.maxy - ypos - 2
        self.recalculate_logpad_xpos(tspadxpos=xpos, timestamps=timestamps)
        if timestamps:
            self.tspadypos = ypos
            self.tspadheight = self.logpadheight
            self.tspad = curses.newpad(self.tspadheight + 1, self.tspadwidth)
        else:
            self.tspad = None
        self.logpadypos = ypos
        self.logpadminwidth = self.maxx - self.logpadxpos
        if width == -1:
            self.logpadwidth = self.logpadminwidth
        else:
            self.logpadwidth = max(width, self.logpadminwidth)
        self.logpad = curses.newpad(self.logpadheight + 1, self.logpadwidth)
        self.loglen = 0

        return self.tspad, self.logpad

    # Pass -1 to keep the current height/width
    # Calling this function directly is not necessary;
    # the pad never grows down, and self.__addstr() calls this when x grows
    def resize_logpad(self, height: int, width: int) -> None:
        self.recalculate_logpad_xpos(tspadxpos=self.tspadxpos)
        if height != -1:
            if self.borders:
                self.tspadheight = height
                self.logpadheight = height
            else:
                self.tspadheight = height + 1
                self.logpadheight = height + 1
        if width != -1:
            self.logpadminwidth = self.maxx - self.logpadxpos
            self.logpadwidth = max(width, self.logpadminwidth)

        if self.logpadheight > 0:
            if self.tspad is not None and self.tspadxpos != self.logpadxpos:
                self.tspad.resize(self.tspadheight + 1, self.tspadwidth + 1)
            if self.logpad is not None:
                self.logpad.resize(self.logpadheight + 1, self.logpadwidth + 1)
        self.maxyoffset = max(0, self.loglen - self.logpadheight)
        self.maxxoffset = max(0, self.logpadwidth - self.logpadminwidth)
        self.yoffset = min(self.yoffset, self.maxyoffset)

    def refresh_logpad(self) -> None:
        if self.logpad is None:
            return

        self.yoffset = min(self.yoffset, self.maxyoffset)
        self.xoffset = min(self.xoffset, self.maxxoffset)

        tspadxpos = self.tspadxpos
        logpadxpos = self.logpadxpos
        if not self.borders:
            tspadxpos -= 1
            logpadxpos -= 1
        if self.tspad is not None and self.tspadxpos != self.logpadxpos:
            hline = deep_get(theme, DictPath("boxdrawing#hline"))
            if self.borders:
                for i in range(0, self.tspadwidth):
                    self.addthemearray(self.stdscr,
                                       [ThemeStr(hline, ThemeAttr("main", "default"))],
                                       y=self.maxy - 2, x=1 + i)
                try:
                    self.tspad.noutrefresh(0, 0, self.tspadypos, tspadxpos,
                                           self.maxy - 3, self.tspadwidth)
                except curses.error:
                    pass
            else:
                try:
                    self.tspad.noutrefresh(0, 0, self.tspadypos, tspadxpos,
                                           self.maxy - 2, self.tspadwidth - 1)
                except curses.error:
                    pass
        if self.borders:
            try:
                self.logpad.noutrefresh(0, self.xoffset, self.logpadypos, logpadxpos,
                                        self.maxy - 3, self.maxx - 1)
            except curses.error:
                pass
            self.upperarrow, self.lowerarrow, self.vdragger = \
                scrollbar_vertical(self.stdscr, self.maxx, self.logpadypos, self.maxy - 3,
                                   self.loglen, self.yoffset, ThemeAttr("main", "boxdrawing"))
            self.leftarrow, self.rightarrow, self.hdragger = \
                scrollbar_horizontal(self.stdscr, self.maxy - 2, logpadxpos, self.maxx - 1,
                                     self.logpadwidth, self.xoffset,
                                     ThemeAttr("main", "boxdrawing"))
        else:
            try:
                self.logpad.noutrefresh(0, self.xoffset, self.logpadypos, logpadxpos,
                                        self.maxy - 2, self.maxx)
            except curses.error:
                pass

    def toggle_timestamps(self, timestamps: Optional[bool] = None) -> None:
        if timestamps is None:
            timestamps = self.tspadxpos == self.logpadxpos

        self.recalculate_logpad_xpos(tspadxpos=self.tspadxpos, timestamps=timestamps)

    def toggle_borders(self, borders: Optional[bool] = None) -> None:
        if borders is None:
            self.borders = not self.borders
        else:
            self.borders = borders

        self.recalculate_logpad_xpos(tspadxpos=self.tspadxpos)
        self.resize_listpad(-1)

    def init_statusbar(self) -> curses.window:
        """
        Initialise the statusbar

            Returns:
                (curses.window): A reference to the statusbar object
        """

        self.resize_statusbar()

        return cast(curses.window, self.statusbar)

    def refresh_statusbar(self) -> None:
        """
        Refresh the statusbar
        """

        if self.statusbar is not None:
            col, __discard = themeattr_to_curses(ThemeAttr("statusbar", "default"))
            self.statusbar.bkgd(" ", col)
            try:
                self.statusbar.noutrefresh(0, 0, self.statusbarypos, 0, self.maxy, self.maxx)
            except curses.error:
                pass

    def resize_statusbar(self) -> None:
        """
        Trigger the statusbar to be resized
        """

        self.statusbarypos = self.maxy - 1
        if self.statusbar is not None:
            self.statusbar.erase()
            self.statusbar.resize(2, self.maxx + 1)
        else:
            self.statusbar = curses.newpad(2, self.maxx + 1)

    # pylint: disable-next=too-many-arguments,too-many-locals
    def addthemearray(self, win: curses.window,
                      array: List[Union[ThemeRef, ThemeStr]], **kwargs: Any) -> Tuple[int, int]:
        """
        Add a ThemeArray to a curses window

            Parameters:
                win (curses.window): The curses window to operate on
                array ([ThemeRef|ThemeStr]): The themearray to add to the curses window
                **kwargs (dict[str, Any]): Keyword arguments
                    y (int): The y-coordinate (-1 to start from current cursor position)
                    x (int): The x-coordinate (-1 to start from current cursor position)
                    deleted (bool): Should the theme be overridden as deleted?
            Returns:
                (int, int): The new (y, x) coordinates
        """
        y: int = deep_get(kwargs, DictPath("y"), -1)
        x: int = deep_get(kwargs, DictPath("x"), -1)
        deleted: bool = deep_get(kwargs, DictPath("deleted"), False)

        for item in themearray_flatten(array):
            if deleted:
                item.set_themeattr(ThemeAttr("types", "deleted"))
            string, attr = themestring_to_cursestuple(item)
            # If there still are remaining <NUL> occurences, replace them
            string = string.replace("\x00", "<NUL>")

            maxy, maxx = win.getmaxyx()
            cury, curx = win.getyx()

            newmaxy = max(y, maxy)
            newmaxx = max(maxx, len(string) + curx + 1)

            if win != self.stdscr:
                win.resize(newmaxy, newmaxx)
            elif win == self.stdscr and (maxy, maxx) != (newmaxy, newmaxx):
                # If the string to print is *exactly* maxx == len(string) + curx,
                # then we check if we can print the last character using addch(),
                # otherwise we give up.
                if (maxy, maxx) == (newmaxy, len(string) + curx):
                    try:
                        win.addch(y, maxx - 1, string[-1:], attr)
                        win.addstr(string[0:-1], attr)
                    except curses.error:
                        cury, curx = win.getyx()
                        return cury, curx
                else:
                    # If the message would resize the window,
                    # just pretend success instead of raising an exception
                    cury, curx = win.getyx()
                    return cury, curx

            try:
                win.addstr(y, x, string, attr)
            except curses.error:
                pass
            y, x = win.getyx()
        return y, x

    def move_xoffset_abs(self, position: int) -> None:
        if self.borders:
            sideadjust = 0
        else:
            sideadjust = 2
        if position == -1:
            self.xoffset = self.maxxoffset - sideadjust
        elif position == 0:
            self.xoffset = 0
        else:
            self.xoffset = max(0, position)
            self.xoffset = min(self.xoffset, self.maxxoffset - sideadjust)
        self.refresh = True

    def move_yoffset_abs(self, position: int) -> None:
        if position == -1:
            self.yoffset = self.maxyoffset
        elif position == 0:
            self.yoffset = 0
        else:
            self.yoffset = max(0, position)
            self.yoffset = min(self.yoffset, self.maxyoffset)
        self.refresh = True
        self.reselect_uid()

    def move_xoffset_rel(self, movement: int) -> None:
        if self.borders:
            sideadjust = 0
        else:
            sideadjust = 2
        self.xoffset = max(0, self.xoffset + movement)
        self.xoffset = min(self.xoffset, self.maxxoffset - sideadjust)
        self.refresh = True

    def move_yoffset_rel(self, movement: int) -> None:
        self.yoffset = max(0, self.yoffset + movement)
        self.yoffset = min(self.maxyoffset, self.yoffset)
        self.refresh = True
        self.reselect_uid()

    def move_cur_abs(self, position: int) -> None:
        if position == -1:
            self.curypos = self.maxcurypos
            self.yoffset = self.maxyoffset
        elif position == 0:
            self.curypos = self.mincurypos
            self.yoffset = 0
        else:
            raise ProgrammingError("FIXME")
        self.list_needs_regeneration(True)
        self.reselect_uid()

    def move_cur_with_offset(self, movement: int) -> None:
        if self.curypos == -1 or self.yoffset == -1:
            self.curypos = 0
            self.yoffset = 0
        newcurypos = self.curypos + movement
        newyoffset = self.yoffset

        # If we are being asked to move forward but we are already
        # at the end of the list, it is prudent not to move,
        # even if the caller so requests.
        # It is just good manners, really.
        if self.yoffset + newcurypos > self.listlen:
            newcurypos = min(newcurypos, self.maxcurypos)
            newyoffset = self.maxyoffset
        elif newcurypos > self.maxcurypos:
            newyoffset = min(self.yoffset - (self.maxcurypos - newcurypos), self.maxyoffset)
            newcurypos = self.maxcurypos
        elif newcurypos < self.mincurypos:
            newyoffset = max(self.yoffset + (newcurypos - self.mincurypos), 0)
            newcurypos = self.mincurypos

        if self.curypos != newcurypos or self.yoffset != newyoffset:
            self.curypos = newcurypos
            self.yoffset = newyoffset
            self.list_needs_regeneration(True)
        self.reselect_uid()

    def find_all_matches_by_searchkey(self,
                                      messages: Optional[List[Union[str, ThemeArray,
                                                                    List[Union[ThemeStr,
                                                                               ThemeRef]]]]],
                                      searchkey: str) -> None:
        self.match_index = None
        self.search_matches.clear()

        if not searchkey or not messages:
            return

        for y, msg in enumerate(messages):
            # The messages can either be raw strings,
            # or themearrays, so we need to flatten them first
            if isinstance(msg, str):
                message = msg
            else:
                message = themearray_to_string(msg)
            # Case-insensitive search
            if searchkey.lower() in message.lower():
                self.search_matches.add(y)

    def find_next_match(self) -> None:
        start = self.match_index
        if start is None:
            start = self.yoffset
        for y in range(start, self.loglen):
            if y in self.search_matches:
                if self.match_index is None or self.match_index != y:
                    self.match_index = y
                    self.yoffset = min(y, self.maxyoffset)
                    break
        self.reselect_uid()

    def find_prev_match(self) -> None:
        end = self.match_index
        if end is None:
            end = self.yoffset
        for y in reversed(range(0, end)):
            if y in self.search_matches:
                # We do not want to return the same match over and over...
                if self.match_index is None or self.match_index != y:
                    self.match_index = y
                    self.yoffset = min(y, self.maxyoffset)
                    break
        self.reselect_uid()

    # Find the next line that has severity > NOTICE
    def next_line_by_severity(self, severities: Optional[List[LogLevel]]) -> None:
        y = 0
        newoffset = self.yoffset

        if severities is None:
            return

        for severity in severities:
            # We are only searching forward
            if y > self.yoffset and severity < LogLevel.NOTICE:
                newoffset = y
                break
            y += 1

        self.yoffset = min(newoffset, self.maxyoffset)
        self.refresh = True

    # Find the prev line that has severity > NOTICE
    def prev_line_by_severity(self, severities: Optional[List[LogLevel]]) -> None:
        y = 0
        newoffset = self.yoffset

        if severities is None:
            return

        for severity in severities:
            # We are only searching backward
            if y == self.yoffset:
                break
            if severity < LogLevel.NOTICE:
                newoffset = y
            y += 1

        self.yoffset = newoffset
        self.refresh = True

    def next_by_sortkey(self, info: List[Type]) -> None:
        if not self.sortkey1:
            return

        pos = self.curypos + self.yoffset
        y = 0
        newpos = 0
        current = ""
        sortkey1, sortkey2 = self.get_sortkeys()
        sortkey = sortkey2 if sortkey1 == "status_group" else sortkey1

        # Search forward within sort category
        # next namespace when sorted by namespace
        # next (existing) letter when sorted by name
        # next status when sorted by status
        # next node when sorted by node
        for entry in natsorted(info, key=attrgetter(sortkey1, sortkey2),
                               reverse=self.sortorder_reverse):
            entryval = getattr(entry, sortkey)

            # OK, from here we want to go to next entry
            if y == pos:
                if sortkey == "age" or self.sortkey1 == "seen":
                    current = cmtlib.seconds_to_age(entryval)
                else:
                    current = entryval
            elif y > pos:
                if sortkey == "name":
                    if current[0] != entryval[0]:
                        newpos = y - pos
                        break
                elif sortkey == "age" or self.sortkey1 == "seen":
                    if current != cmtlib.seconds_to_age(entryval):
                        newpos = y - pos
                        break
                else:
                    if current != entryval:
                        newpos = y - pos
                        break
            y += 1

        # If we do not match we will just end up with the old pos
        self.move_cur_with_offset(newpos)

    # pylint: disable-next=too-many-branches
    def prev_by_sortkey(self, info: List[Type]) -> None:
        if self.sortkey1 is None:
            return

        pos = self.curypos + self.yoffset
        y = 0
        newpos = 0
        current = None
        sortkey1, sortkey2 = self.get_sortkeys()
        sortkey = sortkey2 if sortkey1 == "status_group" else sortkey1

        # Search backward within sort category
        # prev namespace when sorted by namespace
        # prev (existing) letter when sorted by name
        # prev status when sorted by status
        # prev node when sorted by node
        for entry in natsorted(info, key=attrgetter(sortkey1, sortkey2),
                               reverse=self.sortorder_reverse):
            entryval = getattr(entry, sortkey)
            if current is None:
                if sortkey == "age" or self.sortkey1 == "seen":
                    current = cmtlib.seconds_to_age(entryval)
                else:
                    current = entryval

            if y == pos:
                break

            if sortkey == "name" and current is not None and current:
                if current[0] != entryval[0]:
                    current = entryval
                    newpos = y - pos
            elif sortkey == "age":
                if current != cmtlib.seconds_to_age(getattr(entry, sortkey)):
                    current = cmtlib.seconds_to_age(entryval)
                    newpos = y - pos
            else:
                if current != entryval:
                    current = entryval
                    newpos = y - pos
            y += 1

        # If we do not match we will just end up with the old pos
        if not newpos:
            self.move_cur_abs(0)
        else:
            self.move_cur_with_offset(newpos)

    def find_next_by_sortkey(self, info: List[Type], searchkey: str) -> None:
        pos = self.curypos + self.yoffset
        offset = 0

        # Search within sort category
        sorted_list = natsorted(info, key=attrgetter(self.sortkey1, self.sortkey2),
                                reverse=self.sortorder_reverse)
        match = False
        for y in range(pos, len(sorted_list)):
            tmp2 = getattr(sorted_list[y], self.sortcolumn)
            if self.sortkey1 in ("age", "first_seen", "last_restart", "seen"):
                tmp2 = [cmtlib.seconds_to_age(tmp2)]
            else:
                if isinstance(tmp2, (list, tuple)):
                    if isinstance(tmp2[0], tuple):
                        tmp3: List = []
                        for t in tmp2:
                            tmp3 += map(str, t)
                        tmp2 = tmp3
                    else:
                        tmp2 = map(str, tmp2)
                else:
                    tmp2 = [str(tmp2)]
            for part in tmp2:
                part = part[0:len(searchkey)].rstrip().lower()
                if searchkey.lower() == part:
                    offset = y - pos
                    if offset > 0:
                        match = True
                        break
            if match:
                break

        # If we do not match we will just end up with the old pos
        self.move_cur_with_offset(offset)

    def find_prev_by_sortkey(self, info: List[Type], searchkey: str) -> None:
        pos = self.curypos + self.yoffset
        offset = 0

        # Search within sort category
        sorted_list = natsorted(info, key=attrgetter(self.sortkey1, self.sortkey2),
                                reverse=self.sortorder_reverse)
        match = False
        for y in reversed(range(0, pos)):
            tmp2 = getattr(sorted_list[y], self.sortcolumn)
            if self.sortkey1 in ("age", "seen"):
                tmp2 = [cmtlib.seconds_to_age(tmp2)]
            else:
                if isinstance(tmp2, (list, tuple)):
                    tmp2 = map(str, tmp2)
                else:
                    tmp2 = [str(tmp2)]
            for part in tmp2:
                part = part[0:len(searchkey)].rstrip().lower()
                if searchkey.lower() == part:
                    offset = y - pos
                    if offset < 0:
                        match = True
                        break
            if match:
                break

        # If we do not match we will just end up with the old pos
        self.move_cur_with_offset(offset)

    def goto_first_match_by_name_namespace(self, name: str, namespace: str) -> Optional[Type]:
        """
        This function is used to find the first match based on command line input
        The sort order used will still be the default, to ensure that the partial
        match ends up being the first.

            Parameters:
                name (str): The name to search for
                namespace (str): The namespace to search for
            Returns:
                (InfoType): The unique match, the first partial match
                            if no unique match is found, or None if no match is found
        """
        if self.info is None or not self.info or name is None \
                or not name or not hasattr(self.info[0], "name"):
            return None

        # Search within sort category
        sorted_list = natsorted(self.info, key=attrgetter(self.sortkey1, self.sortkey2),
                                reverse=self.sortorder_reverse)
        first_match = None
        unique_match = None
        match_count = 0

        for y, listitem in enumerate(sorted_list):
            if hasattr(sorted_list[0], "namespace"):
                if namespace is not None and listitem.namespace != namespace:
                    continue

            if listitem.name == name:
                first_match = y
                match_count = 1
                break

            if listitem.name.startswith(name):
                if first_match is None:
                    first_match = y
                match_count += 1

        if first_match is not None:
            self.move_cur_with_offset(first_match)
        if match_count == 1:
            unique_match = sorted_list[self.curypos + self.yoffset].ref

        return unique_match

    def next_sortcolumn(self) -> None:
        if self.sortcolumn is None or self.sortcolumn == "":
            return

        match = 0
        for field in self.field_list:
            if self.field_list[field].get("skip", False):
                continue
            if match == 1:
                self.sortcolumn = field
                break
            if field == self.sortcolumn:
                match = 1

        self.sortkey1, self.sortkey2 = self.get_sortkeys()
        self.sort_triggered = True

    def prev_sortcolumn(self) -> None:
        if self.sortcolumn is None or self.sortcolumn == "":
            return

        match = 0
        for field in reversed(self.field_list):
            if match == 1:
                self.sortcolumn = field
                break
            if field == self.sortcolumn:
                match = 1

        self.sortkey1, self.sortkey2 = self.get_sortkeys()
        self.sort_triggered = True

    def get_sortcolumn(self) -> str:
        return self.sortcolumn

    def get_sortkeys(self) -> Tuple[str, str]:
        if self.field_list is None:
            # We do not really care about what the sortkeys are; we do not have a list to sort
            # but if we return valid strings we can at least pacify the type checker
            return "", ""

        field = self.field_list.get(self.sortcolumn)

        if field is None:
            valid_fields = []
            for f in self.field_list:
                valid_fields.append(f)
            raise ValueError(f"Invalid sortcolumn: {self.sortcolumn} does not exist "
                             "in field_list:\n"
                             f"    Valid fields are: {valid_fields}")

        sortkey1 = self.field_list[self.sortcolumn]["sortkey1"]
        sortkey2 = self.field_list[self.sortcolumn]["sortkey2"]
        return sortkey1, sortkey2

    # noqa: E501 pylint: disable-next=too-many-return-statements,too-many-locals,too-many-statements,too-many-branches
    def handle_mouse_events(self, win: curses.window,
                            sorted_list: List[Type], **kwargs: Any) -> Retval:
        activatedfun: Optional[Callable] = deep_get(kwargs, DictPath("activatedfun"))
        extraref: Optional[str] = deep_get(kwargs, DictPath("extraref"))
        data: Optional[bool] = deep_get(kwargs, DictPath("data"))
        selected: Optional[Any]

        try:
            _eventid, x, y, _z, bstate = curses.getmouse()
        except curses.error:
            # Most likely mouse is not supported
            return Retval.NOMATCH

        if win == self.listpad:
            if self.listpad is None:
                return Retval.NOMATCH
            cypos = self.listpadypos
            cxpos = self.listpadxpos
            cheight = self.listpadheight
            selections = True
        elif win == self.logpad:
            if self.logpad is None:
                return False
            cypos = self.logpadypos
            cxpos = self.logpadxpos
            cheight = self.logpadheight
            # We do not care about selection
            selections = False
        else:
            return Retval.NOMATCH

        cmaxy = self.maxy
        cmaxx = self.maxx
        cyoffset = self.yoffset
        ypos = y - cypos
        xpos = x - cxpos

        # if bstate == curses.BUTTON1_PRESSED:
        # Here goes handling of dragging scrollbars
        if bstate == curses.BUTTON1_DOUBLE_CLICKED and selections:
            # double-clicks on list items
            if activatedfun is not None \
                    and cypos <= y < min(cheight + cypos, cmaxy) and cxpos <= x < cmaxx:
                # We want to move the cursor here,
                # if "here" is a valid line
                try:
                    selected = sorted_list[ypos + cyoffset]
                except IndexError:
                    return Retval.NOMATCH
                self.select(selected)
                self.curypos = ypos
                self.reselect_uid()

                if selected.ref is not None:
                    if extraref is not None:
                        view = getattr(selected, extraref, self.view)

                        on_activation = copy.deepcopy(self.on_activation)
                        kind = deep_get(on_activation, DictPath("kind"), view)
                        on_activation.pop("kind", None)
                        if data is not None:
                            _retval = activatedfun(self.stdscr, selected.ref, kind,
                                                   info=data, **on_activation)
                        else:
                            _retval = activatedfun(self.stdscr, selected.ref, kind,
                                                   **on_activation)
                    else:
                        on_activation = copy.deepcopy(self.on_activation)
                        kind = deep_get(on_activation, DictPath("kind"), self.view)
                        on_activation.pop("kind", None)
                        _retval = activatedfun(self.stdscr, selected.ref, kind, **on_activation)
                    if _retval is not None:
                        self.force_refresh()
                    return _retval
        # pylint: disable-next=too-many-nested-blocks
        elif bstate == curses.BUTTON1_CLICKED:
            # clicks on list items
            if cypos <= y < min(cheight + cypos, cmaxy) and cxpos <= x < cmaxx and selections:
                selected = self.get_selected()

                try:
                    here = sorted_list[ypos + cyoffset]
                    new_here = sorted_list[ypos + self.yoffset]
                except IndexError:
                    return Retval.NOMATCH

                # If we are clicking on something that is not selected
                # (or if nothing is selected), move here.
                if selected is None or here is None or selected != here:
                    self.select(new_here)
                    self.curypos = ypos
                    self.reselect_uid()
                else:
                    # If we click an already selected item we open it
                    if selected.ref is not None and activatedfun is not None:
                        self.force_update()
                        if extraref is not None:
                            view = getattr(selected, extraref, self.view)

                            on_activation = copy.deepcopy(self.on_activation)
                            kind = deep_get(on_activation, DictPath("kind"), view)
                            on_activation.pop("kind", None)
                            if data is not None:
                                _retval = activatedfun(self.stdscr, selected.ref, kind,
                                                       info=data, **on_activation)
                            else:
                                _retval = activatedfun(self.stdscr, selected.ref, kind,
                                                       **on_activation)
                        else:
                            on_activation = copy.deepcopy(self.on_activation)
                            kind = deep_get(on_activation, DictPath("kind"), self.view)
                            on_activation.pop("kind", None)
                            _retval = activatedfun(self.stdscr, selected.ref, kind,
                                                   **on_activation)
                        if _retval is not None:
                            self.force_refresh()
                        return _retval
            # clicks on the vertical scrollbar
            elif (y, x) == (self.upperarrow):
                if win == self.listpad:
                    self.move_cur_with_offset(-1)
                else:
                    self.move_yoffset_rel(-1)
            elif (y, x) == (self.lowerarrow):
                if win == self.listpad:
                    self.move_cur_with_offset(1)
                else:
                    self.move_yoffset_rel(1)
            elif x == self.upperarrow[1]:
                if self.upperarrow[0] < y < self.lowerarrow[0]:
                    # Do not count the arrows
                    total = self.lowerarrow[0] - self.upperarrow[0] - 2
                    # Y-position on the bar
                    ypos = y - self.upperarrow[0] - 1
                    # moveoffset
                    moveoffset = int((ypos / total) * self.listpadheight)
                    # start by moving the cursor & offset to 0
                    # that way we can do an relative move
                    self.move_cur_abs(0)
                    self.move_cur_with_offset(moveoffset)
            # clicks on the horizontal scrollbar
            elif (y, x) == (self.leftarrow):
                self.move_xoffset_rel(-1)
            elif (y, x) == (self.rightarrow):
                self.move_xoffset_rel(1)
            elif y == self.leftarrow[0]:
                if self.leftarrow[1] < x < self.rightarrow[1]:
                    # Do not count the arrows
                    total = self.rightarrow[1] - self.leftarrow[1] - 2
                    # X-position on the bar
                    xpos = x - self.leftarrow[1] - 1
                    move = int(self.maxxoffset * (xpos / total))
                    self.move_xoffset_abs(move)
        elif bstate == curses.BUTTON2_CLICKED:
            # Middle button
            pass
        elif bstate == curses.BUTTON3_CLICKED:
            # Right button
            pass
        elif CursesConfiguration.mousescroll_enable \
                and bstate == CursesConfiguration.mousescroll_up:
            # Scroll wheel up
            if self.listpad is not None:
                self.move_cur_with_offset(-5)
            elif self.logpad is not None and not self.continuous_log:
                self.move_yoffset_rel(-5)
            return Retval.MATCH
        elif CursesConfiguration.mousescroll_enable \
                and bstate == CursesConfiguration.mousescroll_down:
            if self.listpad is not None:
                self.move_cur_with_offset(5)
            elif self.logpad is not None and not self.continuous_log:
                self.move_yoffset_rel(5)
            return Retval.MATCH

        return Retval.NOMATCH

    def enter_handler(self, activatedfun: Optional[Callable],
                      extraref: Optional[str], data: Optional[bool]) -> Retval:
        selected = self.get_selected()

        if activatedfun is not None and selected is not None and selected.ref is not None:
            if extraref is not None:
                view = getattr(selected, extraref, self.view)

                on_activation = copy.deepcopy(self.on_activation)
                kind = deep_get(on_activation, DictPath("kind"), view)
                on_activation.pop("kind", None)
                if data is not None:
                    _retval = activatedfun(self.stdscr, selected.ref, kind,
                                           info=data, **on_activation)
                else:
                    _retval = activatedfun(self.stdscr, selected.ref, kind, **on_activation)
            else:
                on_activation = copy.deepcopy(self.on_activation)
                kind = deep_get(on_activation, DictPath("kind"), self.view)
                on_activation.pop("kind", None)
                _retval = activatedfun(self.stdscr, selected.ref, kind, **on_activation)
            if _retval is not None:
                self.force_refresh()
            return _retval

        return Retval.NOMATCH

    # pylint: disable-next=too-many-return-statements,too-many-statements,too-many-branches
    def generic_keycheck(self, c: int) -> Retval:
        # We got some type of keypress; postpone idle
        if c != -1:
            self.last_action = datetime.now()

        if c == curses.KEY_RESIZE:
            self.resize_window()
            return Retval.MATCH
        if c == 27:  # ESCAPE
            del self
            return Retval.RETURNONE
        if c == curses.KEY_MOUSE:
            return self.handle_mouse_events(cast(curses.window, self.listpad),
                                            self.sorted_list, activatedfun=self.activatedfun,
                                            extraref=self.extraref, data=self.data)
        if c in (curses.KEY_ENTER, 10, 13) and self.activatedfun is not None:
            return self.enter_handler(self.activatedfun, self.extraref, self.data)
        if c == ord("M"):
            # Toggle mouse support on/off to allow for copy'n'paste
            if get_mousemask() == 0:
                set_mousemask(-1)
            else:
                set_mousemask(0)
            if self.statusbar is not None:
                self.statusbar.erase()
            self.refresh_all()
            return Retval.MATCH
        if c == ord("") or c == ord(""):
            curses.endwin()
            sys.exit()
        if c == curses.KEY_F1 or c == ord("H"):
            if self.helptext is not None:
                windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
                             items=self.helptext, title="Help", cursor=False)
            self.refresh_all()
            return Retval.MATCH
        if c == curses.KEY_F12:
            if CursesConfiguration.abouttext is not None:
                items = []
                for line in CursesConfiguration.abouttext:
                    items.append({"lineattrs": WidgetLineAttrs.NORMAL,
                                  "columns": [line], "retval": None})
                windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
                             items=items, title="About", cursor=False)
            self.refresh_all()
            return Retval.MATCH
        if c == curses.KEY_F5:
            # We need to rate limit this somehow
            self.force_update()
            self.update_forced = True
            self.force_idle()
            return Retval.MATCH
        if c == ord("r"):
            # Reverse the sort order
            if self.listpad is not None and self.reversible:
                self.sortorder_reverse = not self.sortorder_reverse
                self.sort_triggered = True
            return Retval.MATCH
        if c == curses.KEY_SLEFT:
            # For listpads we switch sort column with this;
            # for logpads we move half a page left/right
            if self.listpad is not None:
                self.prev_sortcolumn()
            elif self.logpad is not None and not self.continuous_log:
                self.move_xoffset_rel(-(self.logpadminwidth // 2))
            return Retval.MATCH
        if c == curses.KEY_SRIGHT:
            if self.listpad is not None:
                self.next_sortcolumn()
            elif self.logpad is not None and not self.continuous_log:
                self.move_xoffset_rel(self.logpadminwidth // 2)
            return Retval.MATCH
        if c == curses.KEY_UP:
            if self.listpad is not None:
                self.move_cur_with_offset(-1)
            elif self.logpad is not None and not self.continuous_log:
                self.move_yoffset_rel(-1)
            return Retval.MATCH
        if c == curses.KEY_DOWN:
            if self.listpad is not None:
                self.move_cur_with_offset(1)
            elif self.logpad is not None and not self.continuous_log:
                self.move_yoffset_rel(1)
            return Retval.MATCH
        if c == curses.KEY_LEFT:
            if self.logpad is not None and self.continuous_log:
                return Retval.MATCH

            self.move_xoffset_rel(-1)
            return Retval.MATCH
        if c == curses.KEY_RIGHT:
            if self.logpad is not None and self.continuous_log:
                return Retval.MATCH

            self.move_xoffset_rel(1)
            return Retval.MATCH
        if c == curses.KEY_HOME:
            if self.logpad is not None and self.continuous_log:
                return Retval.MATCH

            self.move_xoffset_abs(0)
            return Retval.MATCH
        if c == curses.KEY_END:
            if self.logpad is not None and self.continuous_log:
                return Retval.MATCH

            self.move_xoffset_abs(-1)
            return Retval.MATCH
        if c == curses.KEY_SHOME:
            if self.logpad is not None:
                if self.continuous_log:
                    return Retval.MATCH
                self.move_yoffset_abs(0)
            elif self.listpad is not None:
                self.move_cur_abs(0)
            return Retval.MATCH
        if c == curses.KEY_SEND:
            if self.logpad is not None:
                if self.continuous_log:
                    return Retval.MATCH
                self.move_yoffset_abs(-1)
            elif self.listpad is not None:
                self.move_cur_abs(-1)
            return Retval.MATCH
        if c == curses.KEY_PPAGE:
            if self.listpad is not None:
                self.move_cur_with_offset(-10)
            elif self.logpad is not None and not self.continuous_log:
                self.move_yoffset_rel(-(self.logpadheight - 2))
            return Retval.MATCH
        if c == curses.KEY_NPAGE:
            if self.listpad is not None:
                self.move_cur_with_offset(10)
            elif self.logpad is not None and not self.continuous_log:
                self.move_yoffset_rel(self.logpadheight - 2)
            return Retval.MATCH
        if c == ord("\t"):
            if self.listpad is not None:
                self.next_by_sortkey(self.info)
            elif self.logpad is not None and not self.continuous_log:
                self.next_line_by_severity(self.severities)
            return Retval.MATCH
        if c == curses.KEY_BTAB:
            if self.listpad is not None:
                self.prev_by_sortkey(self.info)
            elif self.logpad is not None and not self.continuous_log:
                self.prev_line_by_severity(self.severities)
            return Retval.MATCH
        if c == ord("§"):
            # For listpads this jumps to the next column
            if self.listpad is not None:
                # In case the list empty for some reason
                tabstop = 0
                curxoffset = self.xoffset
                # Find next tabstop
                for tabstop in self.tabstops:
                    if curxoffset < tabstop:
                        if tabstop <= self.maxxoffset:
                            self.move_xoffset_abs(tabstop)
                        break
            return Retval.MATCH
        if c == ord("½"):
            # For listpads this jumps to the previous column
            if self.listpad is not None:
                # In case the list empty for some reason
                tabstop = 0
                curxoffset = self.xoffset
                # Find previous tabstop
                for tabstop in reversed(self.tabstops):
                    if curxoffset > tabstop:
                        self.move_xoffset_abs(tabstop)
                        break
            return Retval.MATCH
        if c == ord("") or c == ord("/"):
            if self.listpad is not None:
                if self.listpadheight < 2:
                    return Retval.MATCH

                search_title = f"Search in “{self.sortcolumn}“: "
                if not (searchkey := inputbox(self.stdscr, title=search_title)):
                    return Retval.MATCH

                self.find_next_by_sortkey(self.info, searchkey)
                self.searchkey = searchkey
            elif self.logpad is not None:
                if self.maxyoffset == 0 or self.continuous_log:
                    return Retval.MATCH

                self.refresh = True
                search_title = "Find: "
                if not (searchkey := inputbox(self.stdscr, title=search_title)):
                    self.match_index = None
                    self.search_matches.clear()
                    return Retval.MATCH

                self.find_all_matches_by_searchkey(self.messages, searchkey)
                self.find_next_match()
            return Retval.MATCH
        if c == ord("?"):
            self.search_matches.clear()

            if self.listpad is not None:
                if self.listpadheight < 2:
                    return Retval.MATCH

                search_title = f"Search in “{self.sortcolumn}“: "
                if not (searchkey := inputbox(self.stdscr, title=search_title)):
                    return Retval.MATCH

                self.find_prev_by_sortkey(self.info, searchkey)
                self.searchkey = searchkey
            elif self.logpad is not None:
                if self.maxyoffset == 0 or self.continuous_log:
                    return Retval.MATCH

                self.refresh = True
                search_title = "Find: "
                if not (searchkey := inputbox(self.stdscr, title=search_title)):
                    self.match_index = None
                    self.search_matches.clear()
                    return Retval.MATCH

                self.find_all_matches_by_searchkey(self.messages, searchkey)
                self.find_next_match()
            return Retval.MATCH
        if c == ord("n"):
            if self.listpad is not None:
                if self.listpadheight < 2:
                    return Retval.MATCH

                if self.searchkey is None or self.searchkey == "":
                    return Retval.MATCH

                self.find_next_by_sortkey(self.info, self.searchkey)
            elif self.logpad is not None:
                if self.maxyoffset == 0 or self.continuous_log or not self.search_matches:
                    return Retval.MATCH

                self.refresh = True
                self.find_next_match()
            return Retval.MATCH
        if c == ord("p"):
            if self.listpad is not None:
                if self.listpadheight < 2:
                    return Retval.MATCH

                if self.searchkey is None or self.searchkey == "":
                    return Retval.MATCH

                self.find_prev_by_sortkey(self.info, self.searchkey)
            elif self.logpad is not None:
                if not self.maxyoffset or self.continuous_log or not self.search_matches:
                    return Retval.MATCH

                self.refresh = True
                self.find_prev_match()
            return Retval.MATCH
        if c == ord("a"):
            if self.annotations is not None:
                title = ""

                windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
                             items=self.annotations, headers=annotation_headers,
                             title=title, cursor=False)

                self.refresh_all()
                return Retval.MATCH
        if c == ord("l"):
            if self.labels is not None:
                title = ""

                windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
                             items=self.labels, headers=label_headers,
                             title=title, cursor=False)

                self.refresh_all()
                return Retval.MATCH

        # Nothing good enough for you, eh?
        return Retval.NOMATCH

    # Shortcuts used in most view
    def __exit_program(self, **kwargs: Any) -> NoReturn:
        retval = deep_get(kwargs, DictPath("retval"))

        curses.endwin()
        sys.exit(retval)

    # pylint: disable-next=unused-argument
    def __refresh_information(self, **kwargs: Any) -> Tuple[Retval, Dict]:
        # XXX: We need to rate limit this somehow
        self.force_update()
        return Retval.MATCH, {}

    def __select_menu(self, **kwargs: Any) -> Tuple[Retval, Dict]:
        refresh_apis = deep_get(kwargs, DictPath("refresh_apis"), False)
        selectwindow = deep_get(kwargs, DictPath("selectwindow"))

        retval = selectwindow(self, refresh_apis=refresh_apis)
        if retval == Retval.RETURNFULL:
            return retval, {}
        self.refresh_all()
        return retval, {}

    # pylint: disable-next=unused-argument
    def __show_about(self, **kwargs: Any) -> Tuple[Retval, Dict]:
        if CursesConfiguration.abouttext is not None:
            items = []
            for line in CursesConfiguration.abouttext:
                items.append({"lineattrs": WidgetLineAttrs.NORMAL,
                              "columns": [line], "retval": None})
            windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
                         items=items, title="About", cursor=False)
        self.refresh_all()
        return Retval.MATCH, {}

    def __show_help(self, **kwargs: Any) -> Tuple[Retval, Dict]:
        helptext = deep_get(kwargs, DictPath("helptext"))

        windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
                     items=helptext, title="Help", cursor=False)
        self.refresh_all()
        return Retval.MATCH, {}

    # pylint: disable-next=unused-argument
    def __toggle_mouse(self, **kwargs: Any) -> Tuple[Retval, Dict]:
        # Toggle mouse support on/off to allow for copy'n'paste
        if get_mousemask() == 0:
            set_mousemask(-1)
        else:
            set_mousemask(0)
        if self.statusbar is not None:
            self.statusbar.erase()
        self.refresh_all()
        return Retval.MATCH, {}

    # pylint: disable-next=unused-argument
    def __toggle_borders(self, **kwargs: Any) -> Tuple[Retval, Dict]:
        self.toggle_borders()
        self.refresh_all()
        self.force_update()
        return Retval.MATCH, {}

    # pylint: disable-next=too-many-locals
    def generate_helptext(self, shortcuts: Dict, **kwargs: Any) -> List[Dict]:
        """
        Generate helptexts to use with generic_inputhandler()

            Parameters:
                shortcuts (dict): A dict of shortcuts
                kwargs (dict): Additional parameters
            Returns:
                ([dict]): A list of dicts formatted for passing to windowwidget()
        """
        read_only_mode = deep_get(kwargs, DictPath("read_only"), False)
        subview = deep_get(kwargs, DictPath("subview"), False)

        # There are (up to) four helptext groups:
        # Global
        # Global F-keys
        # Command
        # Navigation keys
        helptext_groups: List[List] = [[], [], [], []]

        for shortcut_name, shortcut_data in shortcuts.items():
            read_only = deep_get(shortcut_data, DictPath("read_only"), False)
            if read_only_mode and not read_only:
                continue

            helptext_group = deep_get(shortcut_data, DictPath("helpgroup"))
            if helptext_group is None:
                raise ValueError(f"The shortcut {shortcut_name} has no helpgroup; "
                                 "this is a programming error.")
            if (tmp := deep_get(shortcut_data, DictPath("helptext"))) is None:
                raise ValueError(f"The shortcut {shortcut_name} has no helptext; "
                                 "this is a programming error.")

            helptext_groups[helptext_group].append(tmp)

        helptext = []
        if subview:
            helptext.append(("", ""))

        first = True
        for helptexts in helptext_groups:
            if not helptexts:
                continue
            if not first:
                helptext.append(("", ""))
            for key, description in helptexts:
                helptext.append((key, description))
            first = False

        return format_helptext(helptext)

    # pylint: disable-next=too-many-locals,too-many-branches
    def generic_inputhandler(self, shortcuts: Dict, **kwargs: Any) -> Tuple[Retval, Dict]:
        """
        Generic inputhandler for views

            Parameters:
                shortcuts (dict): View-specific shortcuts
                kwargs (dict): Additional parameters
            Returns:
                (Retval, dict): retval, return_args
        """
        __common_shortcuts = {
            "Exit program": {
                "shortcut": [ord(""), ord("")],
                "helptext": ("[Ctrl] + X", "Exit program"),
                "helpgroup": 0,
                "action": "key_callback",
                "action_call": self.__exit_program,
                "action_args": {
                    "retval": 0,
                }
            },
            "Refresh information": {
                "shortcut": curses.KEY_F5,
                "helptext": ("[F5]", "Refresh information"),
                "helpgroup": 1,
                "action": "key_callback",
                "action_call": self.__refresh_information,
            },
            "Show information about the program": {
                "shortcut": curses.KEY_F12,
                "helptext": ("[F12]", "Show information about the program"),
                "helpgroup": 1,
                "action": "key_callback",
                "action_call": self.__show_about,
            },
            "Show this helptext": {
                "shortcut": [curses.KEY_F1, ord("H")],
                "helptext": ("[F1] / [Shift] + H", "Show this helptext"),
                "helpgroup": 1,
                "action": "key_callback",
                "action_call": self.__show_help,
            },
            "Switch main view": {
                "shortcut": curses.KEY_F2,
                "helptext": ("[F2]", "Switch main view"),
                "helpgroup": 1,
                "action": "key_callback",
                "action_call": self.__select_menu,
            },
            "Switch main view (recheck available API resources)": {
                "shortcut": curses.KEY_F3,
                "helptext": ("[F3]", "Switch main view (recheck available API resources)"),
                "helpgroup": 1,
                "action": "key_callback",
                "action_call": self.__select_menu,
                "action_args": {
                    "refresh_apis": True,
                }
            },
            "Toggle mouse on/off": {
                "shortcut": ord("M"),
                "helptext": ("[Shift] + M", "Toggle mouse on/off"),
                "helpgroup": 0,
                "action": "key_callback",
                "action_call": self.__toggle_mouse,
            },
            "Toggle borders": {
                "shortcut": ord("B"),
                "helptext": ("[Shift] + B", "Toggle borders on/off"),
                "helpgroup": 0,
                "action": "key_callback",
                "action_call": self.__toggle_borders,
            },
        }

        self.stdscr.timeout(100)
        c = self.stdscr.getch()
        altkey = False

        # Default return value if we do not manage to match anything
        retval = Retval.NOMATCH

        if c == curses.KEY_RESIZE:
            self.resize_window()
            return Retval.MATCH, {}

        if c == 27:  # Either ESCAPE or ALT+<key>
            self.stdscr.nodelay(True)
            c2 = self.stdscr.getch()
            self.stdscr.nodelay(False)
            # No additional key; this was a real ESCAPE press
            if c2 == -1:
                del self
                return Retval.RETURNONE, {}
            # Additional key pressed; this is ALT+<key>
            altkey = True
            c = c2

        if c == curses.KEY_MOUSE:
            return self.handle_mouse_events(cast(curses.window, self.listpad),
                                            self.sorted_list, activatedfun=self.activatedfun,
                                            extraref=self.extraref, data=self.data), {}

        if c in (curses.KEY_ENTER, 10, 13) and self.activatedfun is not None:
            return self.enter_handler(self.activatedfun, self.extraref, self.data), {}

        # First generate a list of all the shortcuts we should check
        __shortcuts = {}

        # We *always* add the shortcut to exit the program
        __shortcuts["Exit program"] = __common_shortcuts["Exit program"]

        # Now iterate the list of common shortcuts in the shortcuts dict
        for shortcut_name in deep_get(shortcuts, DictPath("__common_shortcuts"), []):
            if shortcut_name not in __common_shortcuts:
                raise ValueError(f"Common shortcut {shortcut_name} is not defined in "
                                 "__common_shortcuts; this is a programming error.")
            __shortcuts[shortcut_name] = deep_get(__common_shortcuts, DictPath(shortcut_name))

        # Finally add all the remaining shortcuts
        for shortcut_name, shortcut_data in shortcuts.items():
            # We've already dealt with this
            if shortcut_name == "__common_shortcuts":
                continue
            __shortcuts[shortcut_name] = shortcut_data

        # Now generate helptext
        helptext = self.generate_helptext(__shortcuts, **kwargs)

        for shortcut_name, shortcut_data in __shortcuts.items():
            keys = deep_get(shortcut_data, DictPath("shortcut"), [])
            # Currently this is only used for [Alt]
            modifier = deep_get(shortcut_data, DictPath("modifier"), "")

            if isinstance(keys, int):
                keys = [keys]

            if c in keys:
                if altkey and modifier.lower() != "alt" \
                   or not altkey and modifier.lower() == "alt":
                    continue

                action = deep_get(shortcut_data, DictPath("action"))
                action_call = deep_get(shortcut_data, DictPath("action_call"))
                _action_args = deep_get(shortcut_data, DictPath("action_args"), {})
                action_args: Dict = {**kwargs, **_action_args}
                action_args["__keypress"] = c
                action_args["helptext"] = helptext
                if action == "key_callback":
                    return action_call(**action_args)

        return retval, {}
