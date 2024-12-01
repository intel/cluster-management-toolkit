#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
This generates and post-processes elements for various more complex types
"""

# pylint: disable=too-many-lines

import copy
from datetime import datetime
import re
from typing import Any, cast, Optional, Type, Union
from collections.abc import Callable
import yaml

from clustermanagementtoolkit.ansithemeprint import ANSIThemeStr

from clustermanagementtoolkit.curses_helper import color_status_group
from clustermanagementtoolkit.curses_helper import themearray_len, themearray_to_string
from clustermanagementtoolkit.curses_helper import themearray_select
from clustermanagementtoolkit.curses_helper import ThemeAttr, ThemeRef, ThemeStr, get_theme_ref

from clustermanagementtoolkit import cmtlib
from clustermanagementtoolkit.cmtlib import datetime_to_timestamp, timestamp_to_datetime

from clustermanagementtoolkit.cmttypes import deep_get, deep_get_with_fallback, DictPath
from clustermanagementtoolkit.cmttypes import StatusGroup, LogLevel, ProgrammingError

from clustermanagementtoolkit import datagetters


def format_special(string: str, selected: bool) -> Optional[Union[ThemeRef, ThemeStr]]:
    """
    Given a string, substitute any special strings with their formatted version.

        Parameters:
            string (str): The string to format
            selected (bool): Is the string selected?
        Returns:
            (ThemeRef | ThemeStr): A ThemeStr
    """
    formatted_string: Optional[Union[ThemeRef, ThemeStr]] = None

    if string in ("<none>", "<unknown>"):
        fmt = ThemeAttr("types", "none")
        formatted_string = ThemeStr(string, fmt, selected)
    elif string in ("<undefined>", "<unspecified>"):
        fmt = ThemeAttr("types", "undefined")
        formatted_string = ThemeStr(string, fmt, selected)
    elif string in ("<empty>", "<unset>"):
        fmt = ThemeAttr("types", "unset")
        formatted_string = ThemeStr(string, fmt, selected)
    elif string == "<not ready>":
        fmt = color_status_group(StatusGroup.NOT_OK)
        formatted_string = ThemeStr(string, fmt, selected)

    return formatted_string


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def format_list(items: Any, fieldlen: int, pad: int,
                **kwargs: Any) -> list[Union[ThemeRef, ThemeStr]]:
    """
    Format the elements of a list.

        Parameters:
            items (Any): The list items
            fieldlen (int): The length of the field
            pad (int): The amount of padding to insert after the field
            **kwargs (dict[str, Any]): Keyword arguments
                ralign (bool): Align the data to the right?
                selected (bool): Mark the field as selected?
                item_separator (ThemeRef): The separator between each item
                field_separators ([ThemeRef]): The separators between each field
                ellipsise (int): Ellipsise after this many elements (-1 == disabled)
                ellipsis (ThemeRef): The marker to use when ellipsising the list
                field_prefixes ([[ThemeRef]]): Prefixes for each element
                field_suffixes ([[ThemeRef]]): Suffixes for each element
                mapping (dict): Mappings passed to map_value()
                field_formatters (list[Callable]): A list of field formatters
        Returns:
            (ThemeArray): The formatted themearray
    """
    ralign: bool = deep_get(kwargs, DictPath("ralign"), False)
    selected: bool = deep_get(kwargs, DictPath("selected"), False)
    item_separator: Optional[ThemeRef] = deep_get(kwargs, DictPath("item_separator"))
    field_separators: Optional[list[ThemeRef]] = deep_get(kwargs, DictPath("field_separators"))
    field_colors: Optional[list[ThemeAttr]] = deep_get(kwargs, DictPath("field_colors"))
    ellipsise: int = deep_get(kwargs, DictPath("ellipsise"), -1)
    ellipsis: Optional[ThemeRef] = deep_get(kwargs, DictPath("ellipsis"))
    field_prefixes: list[list[ThemeRef]] = deep_get(kwargs, DictPath("field_prefixes"))
    field_suffixes: list[list[ThemeRef]] = deep_get(kwargs, DictPath("field_suffixes"))
    mapping: dict = deep_get(kwargs, DictPath("mapping"), {})
    field_formatters: list[Optional[Callable]] = \
        deep_get(kwargs, DictPath("field_formatters"), [])

    array: list[Union[ThemeRef, ThemeStr]] = []

    if item_separator is None:
        item_separator = ThemeRef("separators", "list", selected)

    if ellipsis is None:
        ellipsis = ThemeRef("separators", "ellipsis", selected)

    if field_separators is None:
        field_separators = [ThemeRef("separators", "field", selected)]

    if field_colors is None:
        field_colors = [ThemeAttr("types", "generic")]

    if not isinstance(field_separators, list):
        raise TypeError("field_separators should be a list of ThemeRef, "
                        f"not a single tuple; {field_separators}")

    if not isinstance(field_colors, list):
        raise TypeError("field_colors should be a list of ThemeAttr, "
                        f"not a single tuple; {field_colors}")

    if not isinstance(items, list):
        items = [items]

    elcount = 0
    skip_separator = True

    for item in items:
        if array:
            item_sep = item_separator
            item_sep.selected = selected
            array.append(item_sep)
            elcount += 1

        if elcount == ellipsise:
            ell = ellipsis
            ell.selected = selected
            array.append(ellipsis)
            break

        # Treat all types as tuples no matter if they are;
        # since tuples consist of 2+ elements we add None.
        if not isinstance(item, tuple):
            item = (item, None)

        for i, data in enumerate(item):
            if data is None:
                continue

            string = str(data)

            if not string:
                continue

            if i and not skip_separator:
                field_sep = field_separators[min(i - 1, len(field_separators) - 1)]
                field_sep.selected = selected
                array.append(field_sep)

            field_formatter: Optional[Callable] = None
            if field_formatters:
                field_formatter = field_formatters[min(i, len(field_formatters) - 1)]
            if (tmp := format_special(string, selected)) is not None:
                formatted_string = tmp
            elif field_formatter:
                formatted_string = field_formatter(string, "numerical", selected)
            else:
                default_field_color = cast(ThemeAttr, field_colors[min(i, len(field_colors) - 1)])
                formatted_string, __string = map_value(string, selected=selected,
                                                       default_field_color=default_field_color,
                                                       mapping=mapping)

            # OK, we know now that we will be appending the field, so do the prefix
            if field_prefixes is not None and i < len(field_prefixes):
                array += themearray_select(field_prefixes[i], selected=selected, force=True)
            if isinstance(formatted_string, list):
                array += formatted_string
            else:
                array.append(formatted_string)
            # And now the suffix
            if field_suffixes is not None and i < len(field_suffixes):
                array += themearray_select(field_suffixes[i], selected=selected, force=True)
            skip_separator = False

    return align_and_pad(array, pad, fieldlen, ralign, selected)


# pylint: disable-next=too-many-locals,too-many-statements,too-many-branches
def map_value(value: Any, selected: bool = False,
              default_field_color: ThemeAttr = ThemeAttr("types", "generic"),
              **kwargs: Any) -> tuple[Union[ThemeRef, ThemeStr], str]:
    """
    Perform value based mappings; either by doing numerical ranges,
    or by doing string comparisons (optionally case insensitive).

        Parameters:
            value (Any): The value to map
            references (Any): The references to map against (unsupported for now)
            selected (bool): Is the string selected?
            default_field_color (ThemeAttr): The default colour to use if no mapping occurs
            **kwargs (dict[str, Any]): Keyword arguments
                mapping (dict): The mapping rules
        Returns:
            (ThemeArray, str):
                (ThemeArray): The formatted themearray
                (str): The string-representation of the value
    """
    # If we lack a mapping, use the default color for this field
    if not deep_get(kwargs, DictPath("mapping"), {}):
        return ThemeStr(value, default_field_color, selected), value

    substitutions = deep_get(kwargs, DictPath("mapping#substitutions"), {})
    ranges = deep_get(kwargs, DictPath("mapping#ranges"), [])
    match_case = deep_get(kwargs, DictPath("mapping#match_case"), True)
    mappings = deep_get(kwargs, DictPath("mapping#mappings"), {})

    field_colors = None

    if value in substitutions:
        # We do not need to check for bool, since it is a subclass of int
        if isinstance(value, int):
            value = substitutions[f"__{str(value)}"]
        else:
            value = substitutions[value]

        # If the substitution is a dict it is either a ThemeRef to a separator or a string,
        # or a ThemeStr
        if isinstance(value, dict):
            context: str = deep_get(value, DictPath("context"), "main")
            attr_ref: str = deep_get(value, DictPath("type"))
            string: str = deep_get(value, DictPath("string"))
            if string is None:
                themeref = ThemeRef(context, attr_ref, selected)
                return themeref, str(themeref)
            themestring = ThemeStr(string, ThemeAttr(context, attr_ref))
            return themestring, str(themestring)
        if isinstance(value, ThemeRef):
            return value, str(value)

    # OK, so we want to output output_value, but compare using reference_value
    if isinstance(value, tuple) and ranges:
        output_value, reference_value = value
    else:
        output_value = value
        reference_value = value

    if isinstance(reference_value, (int, float)) and ranges:
        default_index = -1
        for i, data in enumerate(ranges):
            if deep_get(data, DictPath("default"), False):
                if default_index != -1:
                    raise ValueError("Range cannot contain more than one default")
                default_index = i
                continue
            _min = deep_get(data, DictPath("min"))
            _max = deep_get(data, DictPath("max"))
            if (_min is None or reference_value >= _min) \
                    and (_max is None or reference_value < _max):
                field_colors = deep_get(data, DictPath("field_colors"))
                break
        if field_colors is None and default_index != -1:
            field_colors = deep_get(ranges[default_index], DictPath("field_colors"))
        string = str(output_value)
    elif isinstance(reference_value, (str, bool)) or not ranges:
        string = str(output_value)
        _string = string
        if not match_case:
            matched = False
            if string in mappings and string.lower() in mappings and string != string.lower():
                raise ValueError("When using match_case == False "
                                 "the mapping cannot contain keys that only differ in case")
            for key in mappings:
                if key.lower() == string.lower():
                    _string = key
                matched = True
            if not matched and "__default" in mappings:
                _string = "__default"
        elif _string not in mappings and "__default" in mappings:
            _string = "__default"
        field_colors = deep_get(mappings, DictPath(f"{_string}#field_colors"))
    else:
        raise TypeError(f"Unknown type {type(value)} for mapping/range")

    if field_colors is not None:
        context = deep_get(field_colors[0], DictPath("context"), "main")
        attr_ref = deep_get(field_colors[0], DictPath("type"))
        fmt = ThemeAttr(context, attr_ref)
    else:
        fmt = ThemeAttr("types", "generic")
    return ThemeStr(string, fmt, selected), string


def align_and_pad(array: list[Union[ThemeRef, ThemeStr]], pad: int,
                  fieldlen: int, ralign: bool,
                  selected: bool) -> list[Union[ThemeRef, ThemeStr]]:
    """
    Given a field, align to the left or right, and pad it to the field length.

        Parameters:
            array (ThemeArray): The themearray to align and pad
            pad (int): The amount of padding to insert after the field
            fieldlen (int): The length of the field
            ralign (bool): Align the data to the right?
            selected (bool): Mark the field as selected?
        Returns:
            (ThemeArray): The formatted list
    """
    tmp_array: list[Union[ThemeRef, ThemeStr]] = []
    stringlen = themearray_len(array)

    if ralign:
        tmp_array.append(ThemeStr("".ljust(fieldlen - stringlen),
                                  ThemeAttr("types", "generic"), selected))
        tmp_array += array
    else:
        tmp_array += array
        tmp_array.append(ThemeStr("".ljust(fieldlen - stringlen),
                                  ThemeAttr("types", "generic"), selected))
    if pad:
        tmp_array.append(ThemeRef("separators", "pad", selected))
    return tmp_array


# pylint: disable-next=too-many-branches
def format_numerical_with_units(string: str, ftype: str,
                                selected: bool, non_units: Optional[set] = None,
                                separator_lookup: Optional[dict] = None) \
        -> list[Union[ThemeRef, ThemeStr]]:
    """
    Given a string, return it formatted formatted with the numerical parts
    highlighted with the formatting for numerical values, and the remaining
    characters formatted as units.
    Note that decimal points will also be formatted as units.

        Parameters:
            string (str): The string to format
            ftype (str): The formatting type for the non-units
            selected (bool): Should the string be treated as selected?
            non_units (set[str]): The characters to treat as non-units (default: 0-9)
            separator_lookup (dict): The formatting to use for units
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    substring: str = ""
    array: list[Union[ThemeRef, ThemeStr]] = []
    numeric = None
    # This is necessary to be able to use pop
    liststring = list(string)

    if separator_lookup is None:
        separator_lookup = {}

    if "default" not in separator_lookup:
        separator_lookup["default"] = ThemeAttr("types", "unit")

    if non_units is None:
        non_units = set("0123456789₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹")
    else:
        non_units = set(non_units)

    while liststring:
        char = liststring.pop(0)
        if numeric is None:
            numeric = char in non_units
            substring += char
        elif numeric:
            # Do we need to flush?
            if char not in non_units:
                if selected is None:
                    array.append(ThemeStr(substring, ThemeAttr("types", ftype)))
                else:
                    array.append(ThemeStr(substring, ThemeAttr("types", ftype), selected))
                substring = ""
                numeric = False

            substring += char
        else:
            # Do we need to flush?
            if char in non_units:
                fmt = cast(ThemeAttr,
                           deep_get_with_fallback(separator_lookup,
                                                  [DictPath(substring), DictPath("default")]))
                if selected is None:
                    array.append(ThemeStr(substring, fmt))
                else:
                    array.append(ThemeStr(substring, fmt, selected))
                substring = ""
                numeric = True
            substring += char

        if not liststring:
            if numeric:
                if selected is None:
                    array.append(ThemeStr(substring, ThemeAttr("types", ftype)))
                else:
                    array.append(ThemeStr(substring, ThemeAttr("types", ftype), selected))
            else:
                fmt = cast(ThemeAttr, deep_get_with_fallback(separator_lookup,
                                                             [DictPath(substring),
                                                              DictPath("default")]))
                if selected is None:
                    array.append(ThemeStr(substring, fmt))
                else:
                    array.append(ThemeStr(substring, fmt, selected))

    if not array:
        array = [
            ThemeStr("", ThemeAttr("types", "generic"), selected)
        ]

    return array


def generator_age_raw(value: Union[int, str], selected: bool) -> list[Union[ThemeRef, ThemeStr]]:
    """
    A generator for age that operates directly on a value instead of doing a lookup first.

        Parameters:
            value (Any): The value to convert to age
            selected (bool): Is the string selected?
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    array: list[Union[ThemeRef, ThemeStr]] = []

    if value == -1:
        string = ""
    elif isinstance(value, str):
        string = value
    else:
        string = cmtlib.seconds_to_age(value, negative_is_skew=True)

    if (tmp := format_special(string, selected)) is not None:
        array = [tmp]
    elif string == "<clock skew detected>":
        fmt = ThemeAttr("main", "status_not_ok")
        array = [
            ThemeStr(string, fmt, selected)
        ]
    else:
        array = format_numerical_with_units(string, "age", selected)

    return array


# pylint: disable-next=unused-argument,too-many-arguments,too-many-positional-arguments
def generator_age(obj: dict, field: str, fieldlen: int, pad: int,
                  ralign: bool, selected: bool,
                  **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    A generator for age.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    array: list[Union[ThemeRef, ThemeStr]] = []
    value = getattr(obj, field)

    array = generator_age_raw(value, selected)

    return align_and_pad(array, pad, fieldlen, ralign, selected)


# noqa: E501 pylint: disable-next=too-many-arguments,too-many-locals,too-many-branches,too-many-positional-arguments
def generator_address(obj: dict, field: str, fieldlen: int, pad: int,
                      ralign: bool, selected: bool,
                      **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    A generator for IP-addresses and IP-masks.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    item_separator = deep_get(formatting, DictPath("item_separator"))

    items = getattr(obj, field, [])
    if items is None:
        items = []

    if isinstance(items, str) and items in ("<unset>", "<none>"):
        return format_list([items], fieldlen, pad, ralign=ralign, selected=selected)

    if isinstance(items, (str, tuple)):
        items = [items]

    separator_lookup = {}

    separators = deep_get(formatting, DictPath("field_separators"))
    if not separators:
        separators = [ThemeRef("separators", "ipv4address", selected),
                      ThemeRef("separators", "ipv6address", selected),
                      ThemeRef("separators", "ipmask", selected)]

    for separator in separators:
        separator_lookup[str(separator)] = separator

    array: list[Union[ThemeRef, ThemeStr]] = []

    subnet = False

    for item in items:
        _vlist = []
        tmp = ""
        for ch in item:
            if ch in separator_lookup:
                if tmp:
                    if subnet:
                        _vlist.append(ThemeStr(tmp, ThemeAttr("types", "ipmask"), selected))
                    else:
                        _vlist.append(ThemeStr(tmp, ThemeAttr("types", "address"), selected))
                _vlist.append(separator_lookup[ch])
                tmp = ""

                if ch == "/":
                    subnet = True
            else:
                tmp += ch

        if tmp:
            if subnet:
                _vlist.append(ThemeStr(tmp, ThemeAttr("types", "ipmask"), selected))
            else:
                _vlist.append(ThemeStr(tmp, ThemeAttr("types", "address"), selected))
        if array:
            array.append(item_separator)
        array += _vlist

    return align_and_pad(array, pad, fieldlen, ralign, selected)


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def generator_basic(obj: dict, field: str, fieldlen: int, pad: int,
                    ralign: bool, selected: bool,
                    **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    The default generator; it knows about certain special strings,
    but otherwise will use the provided formatting.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    array: list[Union[ThemeRef, ThemeStr]] = []
    value = getattr(obj, field)
    string = str(value)
    field_colors = deep_get(formatting, DictPath("field_colors"), [ThemeAttr("types", "generic")])

    if string == "None":
        string = "<none>"

    if string in ("<none>", "<unknown>"):
        fmt = ThemeAttr("types", "none")
    elif string == "<default>":
        fmt = ThemeAttr("types", "default")
    elif string in ("<undefined>", "<unspecified>"):
        fmt = ThemeAttr("types", "undefined")
    elif string in ("<empty>", "<unset>"):
        fmt = ThemeAttr("types", "unset")
    else:
        context, attr_ref = field_colors[0]
        fmt = ThemeAttr(context, attr_ref)

    array = [
        ThemeStr(string, fmt, selected)
    ]

    return align_and_pad(array, pad, fieldlen, ralign, selected)


# pylint: disable-next=unused-argument,too-many-arguments,too-many-positional-arguments
def generator_hex(obj: dict, field: str, fieldlen: int, pad: int,
                  ralign: bool, selected: bool,
                  **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    A generator for hexadecimal values.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    array: list[Union[ThemeRef, ThemeStr]] = []
    value = getattr(obj, field)
    string = str(value)

    array = format_numerical_with_units(string, "field",
                                        selected, non_units=set("0123456789abcdefABCDEF"))

    return align_and_pad(array, pad, fieldlen, ralign, selected)


# pylint: disable-next=too-many-locals,too-many-arguments,too-many-positional-arguments
def generator_list(obj: dict, field: str, fieldlen: int, pad: int,
                   ralign: bool, selected: bool,
                   **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    Generate a formatted list, with support for custom list separators,
    grouped tuples, ellipsising after a certain length, etc.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    items = getattr(obj, field)

    item_separator = deep_get(formatting, DictPath("item_separator"),
                              ThemeRef("separators", "list", selected))

    field_separators = deep_get(formatting, DictPath("field_separators"),
                                [ThemeRef("separators", "field", selected)])

    field_colors = deep_get(formatting, DictPath("field_colors"),
                            [ThemeAttr("types", "field")])

    ellipsise = deep_get(formatting, DictPath("ellipsise"), -1)

    ellipsis = deep_get(formatting, DictPath("ellipsis"),
                        ThemeRef("separators", "ellipsis", selected))

    field_prefixes = deep_get(formatting, DictPath("field_prefixes"))
    field_suffixes = deep_get(formatting, DictPath("field_suffixes"))

    mapping = deep_get(formatting, DictPath("mapping"), {})

    field_formatters = deep_get(formatting, DictPath("field_formatters"))

    return format_list(items, fieldlen, pad,
                       ralign=ralign,
                       selected=selected,
                       item_separator=item_separator,
                       field_separators=field_separators,
                       field_colors=field_colors,
                       ellipsise=ellipsise,
                       ellipsis=ellipsis,
                       field_prefixes=field_prefixes,
                       field_suffixes=field_suffixes,
                       mapping=mapping,
                       field_formatters=field_formatters)


# noqa: E501 pylint: disable-next=too-many-branches,too-many-locals,too-many-arguments,too-many-positional-arguments
def generator_list_with_status(obj: dict, field: str, fieldlen: int, pad: int,
                               ralign: bool, selected: bool,
                               **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    Generate a formatted list, mapping the items based on their status.
    FIXME: This implementation is really ugly.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    items = getattr(obj, field)
    if isinstance(items, tuple):
        items = [items]

    item_separator = deep_get(formatting, DictPath("item_separator"))
    if item_separator is None:
        item_separator = ThemeRef("separators", "list", selected)

    field_separators = deep_get(formatting, DictPath("field_separators"))
    if field_separators is None:
        field_separators = [ThemeRef("separators", "field", selected)]

    ellipsise = deep_get(formatting, DictPath("ellipsise"), -1)

    ellipsis = deep_get(formatting, DictPath("ellipsis"))
    if ellipsis is None:
        ellipsis = ThemeRef("separators", "ellipsis", selected)

    field_prefixes = deep_get(formatting, DictPath("field_prefixes"))
    field_suffixes = deep_get(formatting, DictPath("field_prefixes"))

    # Well, this works:ish, but it is ugly beyond belief.
    # it would be solved so much better with a mapping that uses a secondary value.
    newitems = []
    field_colors = [
        ThemeAttr("main", "status_done"),
        ThemeAttr("main", "status_ok"),
        ThemeAttr("main", "status_pending"),
        ThemeAttr("main", "status_warning"),
        ThemeAttr("main", "status_admin"),
        ThemeAttr("main", "status_not_ok"),
        ThemeAttr("main", "status_unknown"),
        ThemeAttr("main", "status_critical"),
        ThemeAttr("types", "generic")]
    field_separators = [ThemeRef("separators", "no_pad", selected)]

    for item, status in items:
        if status == StatusGroup.DONE:
            newitems.append((item))
        if status == StatusGroup.OK:
            newitems.append(("", item))
        elif status == StatusGroup.PENDING:
            newitems.append(("", "", item))
        elif status == StatusGroup.WARNING:
            newitems.append(("", "", "", item))
        elif status == StatusGroup.ADMIN:
            newitems.append(("", "", "", "", item))
        elif status == StatusGroup.NOT_OK:
            newitems.append(("", "", "", "", "", item))
        elif status == StatusGroup.UNKNOWN:
            newitems.append(("", "", "", "", "", "", item))
        elif status == StatusGroup.CRIT:
            newitems.append(("", "", "", "", "", "", "", item))
        elif status == StatusGroup.NEUTRAL:
            newitems.append(("", "", "", "", "", "", "", "", item))
        else:
            newitems.append(("", "", "", "", "", "", "", "", item))

    return format_list(newitems, fieldlen, pad,
                       ralign=ralign,
                       selected=selected,
                       item_separator=item_separator,
                       field_separators=field_separators,
                       field_colors=field_colors,
                       ellipsise=ellipsise,
                       ellipsis=ellipsis,
                       field_prefixes=field_prefixes,
                       field_suffixes=field_suffixes)


# pylint: disable-next=unused-argument,too-many-arguments,too-many-positional-arguments
def generator_mem(obj: dict, field: str, fieldlen: int, pad: int,
                  ralign: bool, selected: bool,
                  **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    Generate formatting for memory usage tuples (free / total).

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    array: list[Union[ThemeRef, ThemeStr]] = []
    tmp_free, tmp_total = getattr(obj, field)
    free = __remove_units(tmp_free)
    total = __remove_units(tmp_total)

    if free is None and total is None:
        return generator_basic(obj, field, fieldlen, pad, ralign, selected)

    used = f"{100 - (100 * int(free) / int(total)):0.1f}"

    if float(used) < 80.0:
        fmt = ThemeAttr("types", "watermark_low")
    elif float(used) < 90.0:
        fmt = ThemeAttr("types", "watermark_medium")
    else:
        fmt = ThemeAttr("types", "watermark_high")

    total = f"{int(total) / (1024 * 1024):0.1f}"
    unit = "GiB"

    array = [
        ThemeStr(used, fmt, selected),
        ThemeRef("separators", "percentage", selected),
        ThemeStr(" ", fmt, selected),
        ThemeRef("separators", "fraction", selected),
        ThemeStr(" ", fmt, selected),
        ThemeStr(total, ThemeAttr("types", "numerical"), selected),
        ThemeStr(unit, ThemeAttr("types", "unit"), selected),
    ]

    return align_and_pad(array, pad, fieldlen, ralign, selected)


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def generator_numerical_with_units(obj: dict, field: str, fieldlen: int, pad: int,
                                   ralign: bool, selected: bool,
                                   **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    Generate numerical values with units.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    array: list[Union[ThemeRef, ThemeStr]] = []
    value = getattr(obj, field)

    if value in ("<none>", "<unset>", "<unknown>"):
        fmt = ThemeAttr("types", "none")
        array = [ThemeStr(value, fmt, selected)]
        return align_and_pad(array, pad, fieldlen, ralign, selected)

    # Currently allow_signed seems to be unused
    if value == -1 and not deep_get(formatting, DictPath("allow_signed")):
        string = ""
    else:
        string = str(value)

    array = format_numerical_with_units(string, "numerical", selected)

    return align_and_pad(array, pad, fieldlen, ralign, selected)


# pylint: disable-next=unused-argument,too-many-arguments,too-many-positional-arguments
def generator_status(obj: dict, field: str, fieldlen: int, pad: int,
                     ralign: bool, selected: bool,
                     **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    Generate formatting for status messages.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    array: list[Union[ThemeRef, ThemeStr]] = []
    status = getattr(obj, field)
    status_group = getattr(obj, "status_group")
    fmt = color_status_group(status_group)

    array = [
        ThemeStr(status, fmt, selected)
    ]

    return align_and_pad(array, pad, fieldlen, ralign, selected)


# pylint: disable-next=unused-argument,too-many-arguments,too-many-positional-arguments
def generator_timestamp(obj: dict, field: str, fieldlen: int, pad: int,
                        ralign: bool, selected: bool,
                        **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    Generate a formatted string either from a timestamp or a string;
    special strings such as "<none>" are also handled.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    array: list[Union[ThemeRef, ThemeStr]] = []
    string: str = ""
    value = getattr(obj, field)

    if isinstance(value, str):
        if (tmp := format_special(value, selected)) is not None:
            array = [tmp]
        string = value

    if not array:
        if not isinstance(value, str):
            string = datetime_to_timestamp(value)
        if value is None:
            array = [
                ThemeStr(string, ThemeAttr("types", "generic"), selected)
            ]
        elif value == datetime.fromtimestamp(0).astimezone():
            array = [
                ThemeStr(string, ThemeAttr("types", "generic"), selected)
            ]
        else:
            array = format_numerical_with_units(string, "timestamp", selected)

    return align_and_pad(array, pad, fieldlen, ralign, selected)


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def generator_timestamp_with_age(obj: dict, field: str, fieldlen: int, pad: int,
                                 ralign: bool, selected: bool,
                                 **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    Generate a formatted string either from a timestamp or a string;
    with both timestamp *and* age. Typically used to represent timestamp + duration.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    array: list[Union[ThemeRef, ThemeStr]] = []
    values = getattr(obj, field)

    if len(deep_get(formatting, DictPath("field_colors"), [])) < 2 < len(values):
        raise ValueError("Received more than 2 fields for timestamp_with_age "
                         "but no formatting to specify what the values signify")

    if len(values) == 2:
        if values[0] is None:
            array = [
                ThemeStr("<none>", ThemeAttr("types", "none"), selected)
            ]
        else:
            timestamp_string = datetime_to_timestamp(values[0])
            array = format_numerical_with_units(timestamp_string, "timestamp", selected)
            array += [
                ThemeStr(" (", ThemeAttr("types", "generic"), selected)
            ]
            array += generator_age_raw(values[1], selected)
            array += [
                ThemeStr(")", ThemeAttr("types", "generic"), selected)
            ]
    else:
        array = []

        for i, data in enumerate(values):
            # If there's no formatting for this field we assume that
            # it is a generic string
            if len(deep_get(formatting, DictPath("field_colors"), [])) <= i:
                fmt = ThemeAttr("types", "generic")
                array += [ThemeStr(data, fmt, selected)]
            elif formatting["field_colors"][i] == ThemeAttr("types", "timestamp"):
                if data is None:
                    array += [
                        ThemeStr("<unset>", ThemeAttr("types", "none"), selected)
                    ]
                    break

                timestamp = timestamp_to_datetime(data)
                timestamp_string = f"{timestamp.astimezone():%Y-%m-%d %H:%M:%S}"
                array += format_numerical_with_units(timestamp_string, "timestamp", selected)
            elif formatting["field_colors"][i] == ThemeAttr("types", "age"):
                array += generator_age_raw(data, selected)
            else:
                array += [
                    ThemeStr(data, formatting["field_colors"][i], selected)
                ]

    return align_and_pad(array, pad, fieldlen, ralign, selected)


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def generator_value_mapper(obj: dict, field: "str", fieldlen: int, pad: int,
                           ralign: bool, selected: bool,
                           **formatting: dict) -> list[Union[ThemeRef, ThemeStr]]:
    """
    Generate a formatted string with value mapping.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
            fieldlen (int): The length of the field
            pad (int): The amount of padding
            ralign (bool): Should the text be right-aligned?
            selected (bool): Should the generated field be selected?
            **formatting (dict): Formatting for the data
        Returns:
            ([ThemeRef | ThemeStr]): A formatted string
    """
    array: list[Union[ThemeRef, ThemeStr]] = []
    value = getattr(obj, field)

    default_field_color = cast(ThemeAttr,
                               deep_get(formatting, DictPath("field_colors"),
                                        [("types", "generic")])[0])

    formatted_string, _string = map_value(value,
                                          selected=selected,
                                          default_field_color=default_field_color,
                                          mapping=deep_get(formatting, DictPath("mapping"), {}))
    array = [
        formatted_string
    ]
    return align_and_pad(array, pad, fieldlen, ralign, selected)


# Processors should be possible to be replaced by using generator + str().

def processor_timestamp(obj: dict, field: str) -> str:
    """
    A processor for timestamps; given a value,
    return the processed string for that value.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
        Returns:
            (str): The processed value
    """
    if (value := getattr(obj, field)) is None:
        return ""

    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return f"{value.astimezone():%Y-%m-%d %H:%M:%S}"
    return str(value)


def processor_timestamp_with_age(obj: dict, field: str, formatting: dict) -> str:
    """
    A processor for timestamps with age; given a value,
    return the processed string for that value.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
        Returns:
            (str): The processed value
    """
    values = getattr(obj, field)

    if len(deep_get(formatting, DictPath("field_colors"), [])) < 2 < len(values):
        raise ValueError("Received more than 2 fields for timestamp_with_age "
                         "but no formatting to specify what the values signify")

    if len(values) == 2:
        if values[0] is None:
            array: list[Union[ThemeRef, ThemeStr]] = [
                ThemeStr("<none>", ThemeAttr("types", "none"))
            ]
        else:
            timestamp_string = datetime_to_timestamp(values[0])
            array = format_numerical_with_units(timestamp_string, "timestamp", False)
            array += [
                ThemeStr(" (", ThemeAttr("types", "generic"))
            ]
            array += generator_age_raw(values[1], False)
            array += [
                ThemeStr(")", ThemeAttr("types", "generic"))
            ]
    else:
        array = []

        for i, data in enumerate(values):
            # If there is no formatting for this field we assume that
            # it is a generic string
            if len(deep_get(formatting, DictPath("field_colors"), [])) <= i:
                fmt = ThemeAttr("types", "generic")
                array += [
                    ThemeStr(data, fmt)
                ]
            elif formatting["field_colors"][i] == ThemeAttr("types", "timestamp"):
                if data is None:
                    array += [
                        ThemeStr("<none>", ThemeAttr("types", "none"))
                    ]
                else:
                    # timestamp_string = datetime_to_timestamp(values[0])
                    array += format_numerical_with_units(data, "timestamp", False)
            elif formatting["field_colors"][i] == ThemeAttr("types", "age"):
                array += generator_age_raw(data, False)
            else:
                array += [
                    ThemeStr(data, formatting["field_colors"][i])
                ]

    return themearray_to_string(array)


def __fix_to_str(fix: Union[list[Union[ThemeRef,
                                       tuple[str, str]]], ThemeRef, tuple[str, str]]) -> str:
    """
    Convert a prefix or suffix into a str.

        Parameters:
            fix ([ThemeRef|(str, str)]|ThemeRef|(str, str)): The pre- or suffixes
        Returns:
            (str): A string combining all pre- or suffixes
    """
    fixstr = ""

    if isinstance(fix, list):
        for subfix in fix:
            if isinstance(subfix, ThemeRef):
                fixstr += str(subfix)
            elif isinstance(subfix, dict):
                context = deep_get(subfix, DictPath("context"), "separators")
                key = deep_get(subfix, DictPath("type"))
                fixstr += str(ThemeRef(context, key))
            elif isinstance(subfix, tuple) and len(subfix) == 2:
                fixstr += str(ThemeRef(subfix[0], subfix[1]))
            else:
                raise TypeError(f"__fix_to_str(): Unable to process fix '{fix}'")
    elif isinstance(fix, ThemeRef):
        fixstr += str(fix)
    elif isinstance(fix, tuple) and len(fix) == 2:
        fixstr += str(ThemeRef(fix[0], fix[1]))
    else:
        raise TypeError(f"__fix_to_str(): Unable to process fix '{fix}'")
    return fixstr


# For the list processor to work we need to know the length of all the separators
# pylint: disable-next=too-many-locals
def processor_list(obj: Type, field: str, **kwargs: Any) -> str:
    """
    Return the field with separators, prefixes, suffixes, ellipsis, etc.,
    but with formatting stripped; to be used when calculating string length.
    This processor is used for lists.

        Parameters:
            obj (InfoClass): The object to extract the field from
            field (str): The field to process
            **kwargs (dict[str, Any]): Keyword arguments
                item_separator (ThemeRef): The separator between each element in the list
                field_separators ([ThemeRef|ThemeStr]): The separators between each part
                                                        of the field
                ellipsise (bool): After how many elements should the list be ellipsised;
                                  -1 = never
                ellipsis (ThemeRef): The ellipsis to use when ellipsising
                field_prefixes ([ThemeRef]): Prefixes before each part of the list
                field_suffixes ([ThemeRef]): Suffixes after each part of the list
        Returns:
            (str): The processed, unformatted string
    """
    item_separator: ThemeRef = deep_get(kwargs, DictPath("item_separator"))
    field_separators: list[Union[ThemeRef, ThemeStr]] = \
        deep_get(kwargs, DictPath("field_separators"))
    ellipsise: int = deep_get(kwargs, DictPath("ellipsise"))
    ellipsis: ThemeRef = deep_get(kwargs, DictPath("ellipsis"))
    field_prefixes: list[ThemeRef] = deep_get(kwargs, DictPath("field_prefixes"))
    field_suffixes: list[ThemeRef] = deep_get(kwargs, DictPath("field_suffixes"))

    items = getattr(obj, field)

    strings: list[str] = []

    elcount = 0
    skip_separator = True

    if items is None:
        items = []
    if isinstance(items, tuple):
        items = [items]

    for item in items:
        if elcount == ellipsise:
            strings.append(themearray_to_string([ellipsis]))
            break

        if not isinstance(item, tuple):
            item = (item, None)

        # Join all elements of the field into one string
        string = ""

        for i, data in enumerate(item):
            if data is None:
                continue

            if not (tmp := str(data)):
                continue

            if i and not skip_separator:
                string += themearray_to_string([field_separators[min(i - 1,
                                                                     len(field_separators) - 1)]])

            if field_prefixes is not None and i < len(field_prefixes):
                string += __fix_to_str(field_prefixes[i])
            string += tmp
            if field_suffixes is not None and i < len(field_suffixes):
                string += __fix_to_str(field_suffixes[i])
            skip_separator = False

        strings.append(string)
        elcount += 1

    vstring = themearray_to_string([item_separator]).join(strings)

    return vstring


# For the list processor to work we need to know the length of all the separators
# pylint: disable-next=too-many-locals
def processor_list_with_status(obj: Type, field: str, **kwargs: Any) -> str:
    """
    Return the field with separators, prefixes, suffixes, ellipsis, etc.,
    but with formatting stripped; to be used when calculating string length.
    This processor is used for lists with status.

        Parameters:
            obj (InfoClass): The object to extract the field from
            field (str): The field to process
            **kwargs (dict[str, Any]): Keyword arguments
                item_separator (ThemeRef): The separator between each element in the list
                field_separators ([ThemeRef|ThemeStr]): The separators between each part
                                                        of the field
                ellipsise (bool): After how many elements should the list be ellipsised;
                                  -1 = never
                ellipsis (ThemeRef): The ellipsis to use when ellipsising
                field_prefixes ([ThemeStr]): Prefixes before each part of the list
                field_suffixes ([ThemeStr]): Suffixes after each part of the list
        Returns:
            (str): The processed, unformatted string
    """
    item_separator: ThemeRef = deep_get(kwargs, DictPath("item_separator"))
    field_separators: list[Union[ThemeRef, ThemeStr]] = \
        deep_get(kwargs, DictPath("field_separators"))
    ellipsise: int = deep_get(kwargs, DictPath("ellipsise"))
    ellipsis: ThemeRef = deep_get(kwargs, DictPath("ellipsis"))
    field_prefixes: list[ThemeRef] = deep_get(kwargs, DictPath("field_prefixes"))
    field_suffixes: list[ThemeRef] = deep_get(kwargs, DictPath("field_suffixes"))

    items = getattr(obj, field)
    if items is None:
        items = []

    strings: list[str] = []

    elcount = 0
    skip_separator = True

    newitems = []
    for item in items:
        newitems.append(item[0])

    for item in newitems:
        if elcount == ellipsise:
            strings.append(themearray_to_string([ellipsis]))
            break

        item = (item, None)

        # Join all elements of the field into one string
        string = ""

        for i, data in enumerate(item):
            if data is None:
                continue

            if not (tmp := str(data)):
                continue

            if i and not skip_separator:
                string += themearray_to_string([field_separators[min(i - 1,
                                                                     len(field_separators) - 1)]])

            if field_prefixes is not None and i < len(field_prefixes):
                string += __fix_to_str(field_prefixes[i])
            string += tmp
            if field_suffixes is not None and i < len(field_suffixes):
                string += __fix_to_str(field_suffixes[i])
            skip_separator = False

        strings.append(string)
        elcount += 1

    vstring = themearray_to_string([item_separator]).join(strings)

    return vstring


def processor_age(obj: dict, field: str) -> str:
    """
    A processor for timestamps in age format; given a value,
    return the processed string for that value.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
        Returns:
            (str): The processed value
    """
    seconds = getattr(obj, field)
    return cmtlib.seconds_to_age(seconds, negative_is_skew=True)


def __remove_units(numstr: str) -> str:
    if not (unitfree := re.match(r"^(\d+).*", numstr)):
        raise ValueError(f"Could not remove unit from string {numstr}")
    return unitfree[1]


def processor_mem(obj: dict, field: str) -> str:
    """
    A processor for memory usage tuples (free / total); given two values,
    return the processed string for those values.

        Parameters:
            obj (dict): The object to get data from
            field (str): The field in the object to get data from
        Returns:
            (str): The processed value
    """
    tmp_free, tmp_total = getattr(obj, field)
    free = __remove_units(tmp_free)
    total = __remove_units(tmp_total)

    string = f"{100 - (100 * int(free)) / int(total):0.1f}"
    string += str(ThemeRef("separators", "percentage"))
    string += " "
    string += str(ThemeRef("separators", "fraction"))
    string += " "
    string += f"{int(total) / (1024 * 1024):0.1f}"
    string += "GiB"

    return string


default_processor: dict[Callable, Callable] = {
    generator_age: processor_age,
    generator_list: processor_list,
    generator_list_with_status: processor_list_with_status,
    generator_mem: processor_mem,
    generator_timestamp: processor_timestamp,
}


# The return type of the formatting will be the same
# as the type of the default, so default == None is a programming error
# pylint: disable-next=too-many-branches
def get_formatting(field: dict[str, Any],
                   formatting: str,
                   default: dict[str, Any]) \
        -> Union[list[Union[ThemeAttr, ThemeStr, ThemeRef]], ThemeRef]:
    """
    Given a field dict, the formatting we want to extract, and the default value to return
    if there's no suitable formatting, extract the formatting.

        Parameters:
            field (dict): The field dict to extract formatting from
            formatting (str): The name of the formatting to extract
            default (dict): The default formatting to return if no field-specific formatting
                            is available
    """
    result: list[Union[ThemeAttr, ThemeStr, ThemeRef]] = []
    items: Union[dict, list[dict]] = deep_get(field, DictPath(f"formatting#{formatting}"))

    if items is None:
        return deep_get(default, DictPath(f"{formatting}"))

    if not isinstance(items, (dict, list)):
        raise TypeError("Formatting must be either "
                        "list[dict | ThemeAttr | ThemeRef | ThemeStr] or list[list[dict]]; "
                        f"is type: {type(items)}")

    if default is None:
        raise ValueError(f"default cannot be None for field {field}, "
                         f"formatting {formatting}; this is a programming error")

    if len(items) < 1:
        raise ValueError(f"field {field}, formatting {formatting}: format list item is empty; "
                         "this is likely an error in the view file")

    default_context = None
    if formatting in ("item_separator", "field_separators",
                      "ellipsis", "field_prefixes", "field_suffixes"):
        default_context = "separators"
    elif formatting == "field_colors":
        default_context = "types"

    if isinstance(items, dict):
        context = deep_get(items, DictPath("context"), default_context)
        key = deep_get(items, DictPath("type"))
        return ThemeRef(context, key)

    for item in items:
        # field_prefixes/suffixes can be either list[ThemeRef | ThemeStr],
        # list[list[ThemeRef | ThemeStr]],
        # or ThemeRef | ThemeStr; in the latter case turn it into a list
        if isinstance(item, (ThemeAttr, ThemeRef, ThemeStr)):
            result.append(item)
        elif isinstance(item, list):
            new_item = []
            for subitem in item:
                context = deep_get(subitem, DictPath("context"), default_context)
                key = deep_get(subitem, DictPath("type"))
                new_item.append(ThemeRef(context, key, selected=None))
            result.append(new_item)
        elif isinstance(item, dict):
            context = deep_get(item, DictPath("context"), default_context)
            key = deep_get(item, DictPath("type"))
            if formatting in ("field_separators", "ellipsis"):
                result.append(ThemeRef(context, key))
            elif formatting == "field_colors":
                result.append(ThemeAttr(context, key))
            else:
                raise TypeError(f"Unknown formatting type {formatting}")
        else:
            raise TypeError(f"Formatting is of invalid type {type(item)}")

    return result


formatter_to_generator_and_processor: dict[str, dict[str, Any]] = {
    "list": {
        "generator": generator_list,
        "processor": processor_list,
    },
    "list_with_status": {
        "generator": generator_list_with_status,
        "processor": processor_list_with_status,
    },
    "hex": {
        "generator": generator_hex,
        "processor": None,
    },
    "numerical": {
        "generator": generator_numerical_with_units,
        "processor": None,
    },
    "address": {
        "generator": generator_address,
        "processor": None,
        "field_separators_default": [],
    },
    "timestamp": {
        "generator": generator_timestamp,
        "processor": processor_timestamp,
    },
    "timestamp_with_age": {
        "generator": generator_timestamp_with_age,
        "processor": processor_timestamp_with_age,
    },
    "age": {
        "generator": generator_age,
        "processor": processor_age,
    },
    "value_mapper": {
        "generator": generator_value_mapper,
        "processor": None,
    },
}


# This generates old-style fields from new-style fields
# pylint: disable-next=too-many-locals
def get_formatter(field: dict) -> dict:
    """
    Based on formatter, generator, processor, etc and data type,
    figure out what the rest of the fields need to be.
    For instance, given only formatter this function will
    return also the generator and (if relevant), the processor.

        Parameters:
            field (dict): The field to complete
        Returns:
            (dict): A dict with new formatting information
    """
    tmp_field = {}

    formatter = deep_get(field, DictPath("formatter"))
    generator = deep_get(field, DictPath("generator"), generator_basic)
    if isinstance(generator, str):
        generator = deep_get(generator_allowlist, DictPath(generator), generator_basic)
    processor = deep_get(field, DictPath("processor"))

    field_separators_default = [ThemeRef("separators", "field")]

    if formatter is not None:
        if formatter not in formatter_to_generator_and_processor:
            msg = [
                [("get_formatter()", "emphasis"),
                 (" called with invalid argument(s):", "error")],
                [("field=", "default"),
                 (yaml.dump(field), "argument"),
                 (" has an invalid ", "default"),
                 ("formatter", "argument")]
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   formatted_msg=formatted_msg)

        generator = deep_get(formatter_to_generator_and_processor,
                             DictPath(f"{formatter}#generator"))
        processor = deep_get(formatter_to_generator_and_processor,
                             DictPath(f"{formatter}#processor"))
        field_separators_default = deep_get(formatter_to_generator_and_processor,
                                            DictPath(f"{formatter}#field_separators_default"),
                                            field_separators_default)

    theme = get_theme_ref()
    if deep_get(field, DictPath("formatting#field_colors")) is None:
        if "type" in field and field["type"] in theme["types"]:
            field_colors: list[ThemeAttr] = [ThemeAttr("types", deep_get(field, DictPath("type")))]
        else:
            field_colors = cast(list[ThemeAttr],
                                get_formatting(field, "field_colors",
                                               {"field_colors": [ThemeAttr("types", "field")]}))
    else:
        field_colors = cast(list[ThemeAttr],
                            get_formatting(field, "field_colors",
                                           {"field_colors": [ThemeAttr("types", "field")]}))

    field_prefixes = get_formatting(field, "field_prefixes", {"field_prefixes": []})
    field_suffixes = get_formatting(field, "field_suffixes", {"field_suffixes": []})
    field_separators = get_formatting(field, "field_separators",
                                      {"field_separators": field_separators_default})
    ellipsise = deep_get(field, DictPath("formatting#ellipsise"), -1)
    ellipsis = get_formatting(field, "ellipsis", {"ellipsis": ThemeRef("separators", "ellipsis")})
    item_separator = get_formatting(field, "item_separator",
                                    {"item_separator": ThemeRef("separators", "list")})
    mapping = deep_get(field, DictPath("formatting#mapping"), {})
    field_formatters = []
    for field_formatter in deep_get(field, DictPath("formatting#field_formatters"), []):
        field_formatters.append(deep_get(field_formatter_allowlist, DictPath(field_formatter)))

    tmp_field["generator"] = generator
    tmp_field["processor"] = processor
    # Fix all of these to use the new format
    tmp_field["field_colors"] = field_colors
    tmp_field["field_prefixes"] = field_prefixes
    tmp_field["field_suffixes"] = field_suffixes
    tmp_field["field_separators"] = field_separators
    tmp_field["ellipsise"] = ellipsise
    tmp_field["ellipsis"] = ellipsis
    tmp_field["item_separator"] = item_separator
    tmp_field["mapping"] = mapping
    if "align" in field:
        align = deep_get(field, DictPath("align"), "left")
        tmp_field["ralign"] = align == "right"
    tmp_field["field_formatters"] = field_formatters

    formatting = {
        "item_separator": item_separator,
        "field_separators": field_separators,
        "field_colors": field_colors,
        "ellipsise": ellipsise,
        "ellipsis": ellipsis,
        "field_prefixes": field_prefixes,
        "field_suffixes": field_suffixes,
        "mapping": mapping,
        "field_formatters": field_formatters,
    }

    tmp_field["formatting"] = formatting

    return tmp_field


builtin_fields: dict[str, dict[str, Any]] = {
    "age": {
        "header": "Age:",
        "paths": [{
            "path": ["metadata#creationTimestamp"],
            "type": "timestamp",
            "default": -1,
        }],
        "formatter": "age",
        "align": "right",
    },
    "api_support": {
        "header": "API Support:",
        "datagetter": datagetters.datagetter_api_support,
        "formatter": "list",
    },
    "mem": {
        "header": "Mem% / Total:",
        "paths": [
            {
                "path": "status#allocatable#memory",
                "pathtype": "str",
            },
            {
                "path": "status#capacity#memory",
                "pathtype": "str",
            },
        ],
        "generator": generator_mem,
        "ralign": True,
    },
    "name": {
        "header": "Name:",
        "path": "metadata#name",
        "type": "str",
    },
    "namespace": {
        "header": "Namespace:",
        "path": "metadata#namespace",
        "type": "str",
        "formatting": {
            "field_colors": [
                {
                    "type": "namespace",
                },
            ],
        },
    },
    "pod_status": {
        "header": "Status:",
        "datagetter": datagetters.datagetter_pod_status,
        "generator": generator_status,
    },
}


# pylint: disable-next=too-many-branches,too-many-locals
def fieldgenerator(view: str, selected_namespace: str = "",
                   **kwargs: Any) -> tuple[dict, list[str], str, bool]:
    """
    Generate a dict with the fields necessary for a view.

        Parameters:
            view (str): The view to generate the dict for
            field_index (str): The field_index to use
            field_indexes (dict): A dict with the field indexes to choose between
            fields (dict): The fields to available to the field indexes
            denylist (list[str]): Fields to exclude
        Returns:
            (field_dict, field_names, sortcolumn, sortorder_reverse):
                field_dict (dict): The generated dict
                field_names (list[str]): The fields after pruning using the denylist
                sortcolumn (str): The column to use when sorting
                sortorder_reverse (bool): Should the list be sorted in reverse order
    """

    fields = deep_get(kwargs, DictPath("fields"))
    field_index = deep_get(kwargs, DictPath("field_index"))
    field_indexes = deep_get(kwargs, DictPath("field_indexes"))

    if field_indexes is None or not field_indexes:
        return {}, [], "", False

    field_names = copy.deepcopy(deep_get(field_indexes, DictPath(f"{field_index}#fields"), []))
    sortcolumn = deep_get(field_indexes, DictPath(f"{field_index}#sortcolumn"), "")
    sortorder_reverse = deep_get(field_indexes, DictPath(f"{field_index}#sortorder_reverse"), False)

    denylist = copy.deepcopy(deep_get(kwargs, DictPath("denylist"), []))

    if selected_namespace != "" and "namespace" not in denylist:
        denylist.append("namespace")

    # delete all denylisted fields
    for field in denylist:
        try:
            field_names.remove(field)
        except ValueError:
            pass

    # OK, we've pruned the denylisted fields; now we need to check
    # whether the sort column still applies, and if not try to pick
    # another sortcolumn
    if not sortcolumn or sortcolumn not in field_names:
        if "name" in field_names:
            sortcolumn = "name"
        elif "namespace" in field_names:
            sortcolumn = "namespace"
        else:
            sortcolumn = field_names[0]

    field_dict = {}
    for field in field_names:
        if field in fields:
            field_dict[field] = deep_get(fields, DictPath(field), {})
        elif field in builtin_fields:
            field_dict[field] = deep_get(builtin_fields, DictPath(field), {})
        else:
            msg = [
                [("fieldgenerator()", "emphasis"),
                 (" called with invalid argument(s):", "error")],
                [("View ", "default"),
                 (f"{view}", "argument"),
                 (": field “", "default"),
                 (f"{field}", "argument"),
                 ("“ cannot be found in view or builtin_fields", "default")],
                [(f"View fields: {fields}", "default")],
                [(f"field_names: {field_names}", "default")],
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   formatted_msg=formatted_msg)

    tmp_fields = {}

    for field_name, field in field_dict.items():
        # This is a custom field, so we need to construct one that's usable here
        tmp_fields[field_name] = copy.deepcopy(field_dict[field_name])

        if (tmp_field := get_formatter(field)) is None:
            continue

        for key, value in tmp_field.items():
            tmp_fields[field_name][key] = value
        tmp_fields[field_name]["sortkey1"] = field_name
        # If sortkey1 == sortcolumn this "fails", but it is good enough
        tmp_fields[field_name]["sortkey2"] = sortcolumn

    return tmp_fields, field_names, sortcolumn, sortorder_reverse


# Formatters acceptable for use with list fields
field_formatter_allowlist: dict[str, Callable] = {
    "numerical_with_units": format_numerical_with_units,
}


# Generators acceptable for direct use in view files
generator_allowlist: dict[str, Callable] = {
    "generator_mem": generator_mem,
    "generator_status": generator_status,
}
