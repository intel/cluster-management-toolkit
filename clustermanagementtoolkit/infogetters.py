#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

# pylint: disable=too-many-lines

"""
Get information
"""

import base64
from datetime import datetime, timedelta
# ujson is much faster than json,
# but it might not be available
try:  # pragma: no cover
    import ujson as json
# The exception raised by ujson when parsing fails is different
# from what json raises
    DecodeException = ValueError
except ModuleNotFoundError:  # pragma: no cover
    import json  # type: ignore
    DecodeException = json.decoder.JSONDecodeError  # type: ignore
import os
import re
import sys
from typing import Any, cast, Optional, Type, Union
from collections.abc import Callable, Sequence
import yaml

try:
    from natsort import natsorted
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import natsort; "
             "you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

from clustermanagementtoolkit import about

from clustermanagementtoolkit.ansible_helper import ansible_get_logs

from clustermanagementtoolkit.cmtio import execute_command_with_response, secure_which
from clustermanagementtoolkit.cmtio_yaml import secure_read_yaml

from clustermanagementtoolkit import cmtlib
from clustermanagementtoolkit.cmtlib import make_label_selector, make_set_expression_list
from clustermanagementtoolkit.cmtlib import none_timestamp, timestamp_to_datetime, get_since
from clustermanagementtoolkit.cmtlib import normalise_cpu_usage_to_millicores
from clustermanagementtoolkit.cmtlib import normalise_mem_to_bytes, normalise_mem_bytes_to_str
from clustermanagementtoolkit.cmtlib import split_msg

from clustermanagementtoolkit import cmtlog

from clustermanagementtoolkit.cmtpaths import BINDIR

from clustermanagementtoolkit.cmttypes import deep_get, deep_get_list, deep_get_with_fallback
from clustermanagementtoolkit.cmttypes import deep_set, DictPath, FilePath, SecurityPolicy
from clustermanagementtoolkit.cmttypes import ProgrammingError, StatusGroup, name_to_loglevel

from clustermanagementtoolkit.curses_helper import color_status_group
from clustermanagementtoolkit.curses_helper import get_theme_ref, themearray_len
from clustermanagementtoolkit.curses_helper import ThemeAttr, ThemeRef, ThemeStr

from clustermanagementtoolkit import datagetters
from clustermanagementtoolkit.datagetters import datagetter_allowlist

from clustermanagementtoolkit.fieldgetters import fieldgetter_allowlist

from clustermanagementtoolkit import formatters
from clustermanagementtoolkit.formatters import formatter_allowlist

from clustermanagementtoolkit import itemgetters

from clustermanagementtoolkit.kubernetes_helper import get_node_roles, get_node_status
from clustermanagementtoolkit.kubernetes_helper import get_containers
from clustermanagementtoolkit.kubernetes_helper import get_controller_from_owner_references
from clustermanagementtoolkit.kubernetes_helper import get_pod_restarts_total
from clustermanagementtoolkit.kubernetes_helper import get_image_version
from clustermanagementtoolkit.kubernetes_helper import KubernetesResourceCache

from clustermanagementtoolkit import listgetters

import clustermanagementtoolkit.logparser as logparsers
from clustermanagementtoolkit.logparser import LogLevel

from clustermanagementtoolkit.ansithemeprint import ANSIThemeStr


def __process_string(value: str, replace_quotes: str) -> str:
    # We do not want any newlines, and extra trailing whitespace
    if value is None:
        value = ""
    if isinstance(value, str):
        value = value.replace("\n", "\\n").rstrip()
        if replace_quotes == "pretty":
            value = value.replace("\\\"", "“")
        elif replace_quotes == "same":
            value = value.replace("\\\"", "\"")
    return value


def __process_sum_numerical(value: Sequence[Union[int, float]]) -> Union[float, int]:
    return sum(value)


def __process_stringify_list(values: Sequence[Any]) -> list[str]:
    tmp: list[str] = []
    for value in values:
        tmp.append(str(value))
    return tmp


def __process_sum_cpu_usage(values: list[str]) -> str:
    cpu_usage_sum = 0.0
    for value in values:
        cpu_usage_sum += normalise_cpu_usage_to_millicores(value)
    return f"{cpu_usage_sum:0.1f}"


def __process_sum_mem_usage(values: list[str]) -> str:
    mem_usage_sum = 0
    for value in values:
        mem_usage_sum += normalise_mem_to_bytes(value)
    return normalise_mem_bytes_to_str(mem_usage_sum)


def __process_timestamp(value: Union[Sequence[Union[int, str]], str],
                        action: str, formatter: str) -> Union[datetime, int]:
    new_value: Any = None

    if action in ("earliest", "latest") and isinstance(value, (list, tuple)):
        tmp_timestamp: datetime = none_timestamp()
        for tmp1 in value:
            if tmp1 is None or tmp1 == -1:
                continue
            # The only valid integer value is -1
            timestamp = timestamp_to_datetime(cast(str, tmp1))
            if tmp_timestamp == none_timestamp():
                tmp_timestamp = timestamp
            else:
                if timestamp < tmp_timestamp and action == "earliest":
                    tmp_timestamp = timestamp
                elif timestamp > tmp_timestamp and action == "latest":
                    tmp_timestamp = timestamp
        new_value = tmp_timestamp
    else:
        if value == -1:
            new_value = none_timestamp()
        elif isinstance(value, str) and value.startswith("<") and value.endswith(">"):
            new_value = value
        else:
            new_value = timestamp_to_datetime(cast(str, value))

    if formatter == "age":
        # If we are gonna format this as age we want this passed through get_since()
        return get_since(new_value)

    return new_value


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def process_value(value: Any, vtype: str, **kwargs: Any) -> \
        Union[int, float, str, list[str], list[tuple[str]], datetime, None]:
    """
    Reformat values; returns data in a format suitable for further processing.

        Parameters:
            value (Any): The value to process
            vtype (str): The value-type
            **kwargs (dict[str, Any]): Keyword arguments
                action (str): Additional actions to perform when processing
                field_index (str): The field index for formatting of a particular kind
                field_name (str): The name of the field the data originates from
                formatter (str): Formatter to use (specifically used when processing timestamps)
                replace_quotes (str): Quote replacement policy (no, pretty, same)
                view (str): The view being processed
        Returns:
            (int|float|str|[str]|datetime): The processed value
    """
    action: str = deep_get(kwargs, DictPath("action"))
    field_index: str = deep_get(kwargs, DictPath("field_index"))
    field_name: str = deep_get(kwargs, DictPath("field_name"))
    formatter: str = deep_get(kwargs, DictPath("formatter"))
    replace_quotes: str = deep_get(kwargs, DictPath("replace_quotes"))
    view: str = deep_get(kwargs, DictPath("view"))

    override_kind = \
        deep_get_with_fallback(cmtlib.cmtconfig,
                               [DictPath(f"Views#{view}#kind_format_{field_index}"),
                                DictPath(f"Views#{view}#kind_format"),
                                DictPath(f"Global#kind_format_{field_index}"),
                                DictPath("Global#kind_format")], "mixed")

    new_value: Union[int, float, str, list[str], datetime, None] = None

    if vtype == "str":
        new_value = __process_string(value, replace_quotes)
    elif vtype in ("float", "int", "bool"):
        if isinstance(value, (list, tuple)) and action == "sum":
            new_value = __process_sum_numerical(value)
        elif isinstance(value, tuple):
            new_value = __process_stringify_list(value)
        else:
            new_value = str(value)
    elif vtype in ("cpu_usage", "cpu_usage_round"):
        if isinstance(value, list) and action == "sum":
            new_value = __process_sum_cpu_usage(value)
        elif vtype == "cpu_usage_round":
            tmp_float = normalise_cpu_usage_to_millicores(value)
            new_value = f"{int(tmp_float / 1000)}"
        else:
            tmp_float = normalise_cpu_usage_to_millicores(value)
            new_value = f"{tmp_float:0.1f}"
    elif vtype == "mem_usage":
        if isinstance(value, list) and action == "sum":
            new_value = __process_sum_mem_usage(value)
        else:
            tmp_int = normalise_mem_to_bytes(value)
            new_value = normalise_mem_bytes_to_str(tmp_int)
    elif vtype == "disk_usage":
        new_value = cmtlib.disksize_to_human(value)
    elif vtype == "len":
        if value is None:
            new_value = "0"
        else:
            new_value = str(len(cast(Union[str, Sequence], value)))
    elif vtype == "unix_timestamp":
        new_value = datetime.fromtimestamp(value)
    elif vtype == "timestamp":
        new_value = __process_timestamp(value, action, formatter)
    elif isinstance(vtype, list):
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"Field {field_name}: type({value}) is {vtype}; "
                             f"for type {vtype} pathtype must be a multi-element type")
        _values = []
        override_kind = deep_get_with_fallback(cmtlib.cmtconfig,
                                               [DictPath(f"Views#{view}#kind_format_{field_index}"),
                                                DictPath(f"Views#{view}#kind_format"),
                                                DictPath(f"Global#kind_format_{field_index}"),
                                                DictPath("Global#kind_format")], "mixed")
        for i, data in enumerate(value):
            if i < len(vtype):
                _vtype = vtype[i]
            else:
                _vtype = "raw"
            if _vtype in ("raw", "name"):
                _values.append(data)
            elif _vtype == "kind":
                if override_kind == "skip":
                    _values.append("")
                else:
                    _values.append(data)
            elif _vtype == "api_group":
                if override_kind == "skip":
                    _values.append("")
                    continue

                if data is not None and "/" in data:
                    if override_kind == "full" or override_kind == "mixed" and "." in data:
                        _values.append(data.split("/", maxsplit=1)[0])
                    else:
                        _values.append("")
                else:
                    _values.append("")
            elif _vtype == "skip":
                _values.append("")
            else:
                raise ValueError(f"Field {field_name}: type[{i}] ({vtype}) is unknown")
        if isinstance(value, list):
            new_value = _values
        elif isinstance(value, tuple):
            new_value = tuple(cast(list, _values))
    elif vtype == "raw":
        # Do not convert this type
        new_value = value
    else:
        theme = get_theme_ref()

        # Is a custom type used for theming?
        if vtype not in theme["types"]:
            raise ValueError(f"Unknown value type {vtype}; the view file is probably invalid")
        new_value = value
    return new_value


def transform_filter(value: DictPath, transformations: dict) -> Any:
    """
    Given a transformation dictionary,
    look up and return the corresponding value.

        Parameters:
            value (DictPath): The value to look up
            transformations (dict[str, Any]): The transformation dictionary
        Returns:
            (Any): The transformed value
    """
    if transformations and value in transformations:
        value = deep_get(transformations, value)
    return value


# pylint: disable-next=too-many-return-statements,too-many-locals,too-many-branches,too-many-statements # noqa: E501
def when_filter(when_path: dict, item: dict, key: Optional[str] = None, value: Any = None) -> bool:
    """
    A filter used by infogetters. Given a dictionary of when-conditions,
    # and either a dict or a key/value pair, return True if all conditions
    # evaluate to true, or False if at least one condition evaluates to false.

        Parameters:
            when_path (dict[str, list[dict[str, Any]]]): A dictionary of when-conditions
            item (dict[str, Any]): An item to filter
            key (str): A key
            value (Any): A value
        Returns:
            (bool): True if all conditions evaluated to True,
                    False if at least one condition evaluated to False
    """
    when_conditions = deep_get(when_path, DictPath("when"), [])

    _key = key
    _value = value

    for when_condition in when_conditions:
        # These apply to the key
        if _key is None:
            key = deep_get(when_condition, DictPath("key"))

        # These do not make sense when using when#key, since we already know the key
        if key is not None:
            when_key_eq = deep_get(when_condition, DictPath("key_eq"))
            when_key_ne = deep_get(when_condition, DictPath("key_ne"))
            when_key_in = deep_get(when_condition, DictPath("key_in"))
            when_key_notin = deep_get(when_condition, DictPath("key_notin"))
            when_key_startswith = deep_get(when_condition, DictPath("key_startswith"))
            when_key_notstartswith = deep_get(when_condition, DictPath("key_notstartswith"))
            when_key_endswith = deep_get(when_condition, DictPath("key_endswith"))
            when_key_notendswith = deep_get(when_condition, DictPath("key_notendswith"))
            if when_key_eq is not None and when_key_eq != key:
                return False
            if when_key_ne is not None and when_key_eq == key:
                return False
            if when_key_in is not None and key not in when_key_in:
                return False
            if when_key_notin is not None and key in when_key_notin:
                return False
            if when_key_startswith is not None and not key.startswith(when_key_startswith):
                return False
            if when_key_notstartswith is not None and key.startswith(when_key_notstartswith):
                return False
            if when_key_endswith is not None and not key.endswith(when_key_endswith):
                return False
            if when_key_notendswith is not None and key.endswith(when_key_notendswith):
                return False

        # Check for none
        if _value is None:
            if key is None:
                raise ValueError("key is None")
            value = deep_get(item, DictPath(key))

        # These check whether the key has a value
        when_none = deep_get(when_condition, DictPath("none"))
        when_notnone = deep_get(when_condition, DictPath("notnone"))

        # All these check the value
        when_eq = deep_get(when_condition, DictPath("eq"))
        when_ne = deep_get(when_condition, DictPath("ne"))
        when_lt = deep_get(when_condition, DictPath("lt"))
        when_lte = deep_get(when_condition, DictPath("lte"))
        when_gt = deep_get(when_condition, DictPath("gt"))
        when_gte = deep_get(when_condition, DictPath("gte"))

        when_in = deep_get(when_condition, DictPath("in"))
        when_notin = deep_get(when_condition, DictPath("notin"))

        when_missing = deep_get(when_condition, DictPath("missing"))
        when_notmissing = deep_get(when_condition, DictPath("notmissing"))

        when_startswith = deep_get(when_condition, DictPath("startswith"))
        when_notstartswith = deep_get(when_condition, DictPath("notstartswith"))
        when_endswith = deep_get(when_condition, DictPath("endswith"))
        when_notendswith = deep_get(when_condition, DictPath("notendswith"))

        # These check dict values
        when_isdict = deep_get(when_condition, DictPath("isdict"))
        when_notisdict = deep_get(when_condition, DictPath("notisdict"))
        when_dicthaskey = deep_get(when_condition, DictPath("dicthaskey"))
        when_notdicthaskey = deep_get(when_condition, DictPath("notdicthaskey"))

        # Check for existance
        if when_missing is not None and when_missing in item:
            return False
        if when_notmissing is not None and when_notmissing not in item:
            return False

        if when_notnone is not None and value is None:
            return False
        if when_none is not None and value is not None:
            return False

        # dict-based checks
        if when_isdict is not None and not isinstance(value, dict):
            return False
        if when_notisdict is not None and isinstance(value, dict):
            return False
        if when_dicthaskey is not None \
                and (value is None
                     or (not isinstance(value, dict) or when_dicthaskey not in value)):
            return False
        if when_notdicthaskey is not None \
                and (value is not None
                     and (not isinstance(value, dict) or when_notdicthaskey in value)):
            return False

        # Set-based checks
        if when_in is not None and value not in when_in:
            return False
        if when_notin is not None and value in when_notin:
            return False

        # Check for equality
        if when_eq is not None and (value is None or value != type(value)(when_eq)):
            return False
        if when_ne is not None and (value is None or value == type(value)(when_ne)):
            return False

        if when_lt is not None and (value is None or value >= type(value)(when_lt)):
            return False
        if when_lte is not None and (value is None or value > type(value)(when_lte)):
            return False
        if when_gt is not None and (value is None or value <= type(value)(when_gt)):
            return False
        if when_gte is not None and (value is None or value >= type(value)(when_gte)):
            return False

        if when_startswith is not None \
                and (value is None or not value.startswith(when_startswith)):
            return False
        if when_notstartswith is not None \
                and (value is None or value.startswith(when_notstartswith)):
            return False
        if when_endswith is not None \
                and (value is None or not value.endswith(when_endswith)):
            return False
        if when_notendswith is not None \
                and (value is None or value.endswith(when_notendswith)):
            return False

    return True


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def transform_list(vlist: Union[list, dict], transform: dict) -> list[Any]:
    """
    Given data as a list or dict, modify the data according the rules
    in a transformation ruleset.

        Parameters:
            sorted (booled): Should the result be sorted? True to sort, False to keep order
            key_regexes: Regexes to apply to the key
            key_groups: Regex groups to extract from the key
            key_join: Separator to use when joining the key groups
            key_defaults: Default values to use if the key regexes doesn't match
            value_regexes: Regexes to apply to the value
            value_groups: Regex groups to extract from the value
            value_join: Separator to use when joining the value groups
            value_defaults: Default values to use if the value regexes doesn't match
            output: The expected output; can be any combination of key, value
    """
    sort: bool = deep_get(transform, DictPath("sorted"), False)
    key_regexes: list[str] = deep_get(transform, DictPath("key#regex"), [])
    key_groups: list[int] = deep_get(transform, DictPath("key#groups"), [])
    key_join = deep_get(transform, DictPath("key#join"))
    key_defaults: list = deep_get(transform, DictPath("key#default"), [])
    value_regexes: list[str] = deep_get(transform, DictPath("value#regex"), [])
    value_groups: list[int] = deep_get(transform, DictPath("value#groups"), [])
    value_join = deep_get(transform, DictPath("value#join"))
    value_defaults: list = deep_get(transform, DictPath("value#default"), [])
    output: list[str] = deep_get(transform, DictPath("output"), ["key", "value"])

    result: list = []

    # This handles both lists and dicts
    # pylint: disable-next=too-many-nested-blocks
    for key in vlist:
        if not isinstance(vlist, dict):
            value = None
        else:
            value = vlist[key]

        key_data = []

        if key is None:
            continue

        key = str(key)

        if not key_regexes:
            key_data.append(key)
        else:
            for _regex in key_regexes:
                _tmp = re.match(_regex, key)
                if _tmp is not None:
                    for group in key_groups:
                        if group < len(_tmp.groups()):
                            _tmp2 = _tmp.groups()[group]
                            if _tmp2 is None and group < len(key_defaults):
                                key_data.append(key_defaults[group])
                            else:
                                key_data.append(_tmp2)
                if key_join is not None and len(key_data) > 1:
                    tmp = ""
                    for i, element in enumerate(key_data):
                        tmp += element
                        if i < len(key_data) - 1:
                            tmp += key_join[min(i, len(key_join) - 1)]
                    key_data = [tmp]

        value_data = []
        for _regex in value_regexes:
            if value is None:
                continue

            value = str(value)

            _tmp = re.match(_regex, value)
            if _tmp is not None:
                for group in value_groups:
                    if group < len(_tmp.groups()):
                        _tmp2 = _tmp.groups()[group]
                        if _tmp2 is None and group < len(value_defaults):
                            value_data.append(value_defaults[group])
                        else:
                            value_data.append(_tmp2)
            if value_join is not None and len(value_data) > 1:
                tmp = ""
                for i, element in enumerate(value_data):
                    tmp += element
                    if i < len(value_data) - 1:
                        tmp += value_join[min(i, len(value_join) - 1)]
                value_data = [tmp]

        tmp3 = []
        for _output in output:
            if _output == "key":
                if len(key_data) == 1:
                    tmp3.append(key_data[0])
                else:
                    tmp3.append(tuple(key_data))
            elif _output == "value":
                if len(value_data) == 1:
                    tmp3.append(value_data[0])
                else:
                    tmp3.append(tuple(value_data))
        if len(tmp3) == 1:
            result.append(tmp3[0])
        else:
            result.append(tuple(tmp3))

    if sort:
        return cast(list[Any], natsorted(result))

    return result


def format_controller(controller: tuple[tuple[str, str], str], show_kind: str) -> tuple[str, str]:
    """
    Reformat a controller kind + name tuple.

        Parameters:
            controller ((str, str), str): The controller kind
            show_kind (str): "short" / "full" / "mixed"
        Returns:
            (str, str): A tuple with a possibly reformatted controller kind + name
    """
    pod = controller[1]

    if not show_kind:
        fmt_controller = ""
    elif show_kind == "short":
        fmt_controller = controller[0][0]
    elif show_kind == "full":
        fmt_controller = ".".join(controller[0])
    elif show_kind == "mixed":
        # Strip the API group for standard controllers,
        # but show for custom controllers
        if controller[0] in (("StatefulSet", "apps"), ("ReplicaSet", "apps"),
                             ("DaemonSet", "apps"), ("Job", "batch"),
                             ("CronJob", "batch"), ("Node", "")):
            fmt_controller = controller[0][0]
        else:
            fmt_controller = ".".join(controller[0])
    else:
        raise ValueError(f"unknown value passed to show_kind: {show_kind}")

    if fmt_controller.endswith("."):
        fmt_controller = fmt_controller[:-1]
    return (fmt_controller, pod)


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def get_obj(obj: dict, field_dict: dict, field_names: list[str],
            field_index: str, view: str, **kwargs: Any) -> Type:
    """
    Extract data for all fields in a list row from an object.

        Parameters:
            obj (dict): The object to extract data from
            field_dict (dict): The dict containing the description of the field
            field_names ([str]): The names of the fields to populate
            field_index (str): The index for the field list
            view (str): The name of the view
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
                filters (dict): The filters to apply
                deleted (bool): Is the entry deleted?
                caller_obj (dict): Used for lookups when doing path substitutions
        Returns:
            (InfoClass): An InfoClass object with the data for all fields in the field_names list
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError(f"{__name__}() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    d = {}

    filters: dict[str, Any] = deep_get(kwargs, DictPath("filters"), {})
    deleted: bool = deep_get(kwargs, DictPath("deleted"), False)
    caller_obj: dict = deep_get(kwargs, DictPath("caller_obj"), {})
    duration: int = -1

    # fields both specify formatting and where to get the data from;
    # here we are only concerned with the data
    # pylint: disable-next=too-many-nested-blocks
    for field_name in field_names:
        name = field_name
        field = field_dict[name]
        path = deep_get(field, DictPath("path"))
        paths = deep_get(field, DictPath("paths"), [])
        path_substitutions = deep_get(field, DictPath("path_substitutions"), {})
        unique_values = deep_get(field, DictPath("unique"), False)
        if caller_obj and path_substitutions:
            substitutions = {}
            for subst, subst_with in path_substitutions.items():
                if isinstance(subst_with, list):
                    subst_with = deep_get_with_fallback(caller_obj, subst_with)
                substitutions[subst] = subst_with
            path = cmtlib.substitute_string(path, substitutions)
        datagetter = deep_get(field, DictPath("datagetter"))
        if datagetter is not None:
            if isinstance(datagetter, str):
                datagetter = deep_get(datagetter_allowlist, DictPath(datagetter))
        if "default" not in field:
            default = ""
        else:
            default = deep_get(field, DictPath("default"))
        global_default = default
        fallback_on_empty = deep_get(field, DictPath("fallback_on_empty"), False)
        formatter = deep_get(field, DictPath("formatter"))
        action = None
        replace_quotes = None

        if (path is None and not paths or path is not None and paths) and datagetter is None:
            raise ValueError(f"Field {name}: exactly one of path and paths must be non-empty "
                             f"unless a datagetter is specified\npath={path}\n"
                             f"paths={paths}\ndatagetter={datagetter}")

        if datagetter is not None:
            d[name], extradata = datagetter(obj, kubernetes_helper=kh, path=path, default=default)
            for key, value in extradata.items():
                d[key] = value
        else:
            _values = []

            if path is not None:
                if deep_get(field, DictPath("type")) is None:
                    raise ValueError(f"Field {name}: the path field has no default type; "
                                     "type must always be specified")
                tmp_value = deep_get(obj, DictPath(path), global_default)
                if tmp_value is not None and isinstance(tmp_value, (str, list)) \
                        and not tmp_value and fallback_on_empty:
                    tmp_value = global_default
                _values.append((tmp_value, deep_get(field, DictPath("type"))))

            _path = None
            for _path in paths:
                default = deep_get(_path, DictPath("default"))
                vtype = deep_get(_path, DictPath("type"), "raw")
                path = deep_get(_path, DictPath("path"))
                mpaths = deep_get(_path, DictPath("paths"))
                if path is not None and mpaths is not None or path is None and mpaths is None:
                    raise ValueError(f"Field {name}: exactly one of path & paths must be used "
                                     f"in a 'paths:' block\npath={path}\npaths={paths}")

                if mpaths is None:
                    if isinstance(path, str):
                        path = [path]
                    mpaths = [path]

                ptype = deep_get(_path, DictPath("pathtype"), "list")
                limit = deep_get(_path, DictPath("limit"))
                action = deep_get(_path, DictPath("action"), "")
                subpath = deep_get(_path, DictPath("subpath"), "")
                subpaths = deep_get(_path, DictPath("subpaths"), [])
                fallback_on_empty = deep_get(_path, DictPath("fallback_on_empty"), False)
                replace_quotes = deep_get(_path, DictPath("replace_quotes"), "no")
                if ptype == "list":
                    tmp = deep_get_with_fallback(obj, path, default=default,
                                                 fallback_on_empty=fallback_on_empty)
                    if deep_get(_path, DictPath("sorted"), False) and tmp is not None:
                        tmp = natsorted(tmp)

                    if tmp is not None and tmp in ("None", ["None"]) \
                            and deep_get(_path, DictPath("none_str_as_none"), False):
                        tmp = default

                    # Just return the list, unless a subset has been requested
                    if limit is not None and tmp is not None:
                        value = tmp[0:limit]
                    else:
                        value = tmp

                    _values.append((value, vtype))
                elif ptype == "dictlist":
                    _raw = deep_get_with_fallback(obj, path, default=default,
                                                  fallback_on_empty=fallback_on_empty)
                    transform = deep_get(_path, DictPath("transform"), {})
                    if _raw is not None:
                        for tmp in transform_list(_raw, transform=transform):
                            _values.append((tmp, vtype))
                # This takes a list of paths as indata, and--for all numerical entries in the list,
                # builds ranges; all non-numerical entries are included as is
                elif ptype == "ranges":
                    rawvals = []
                    for p in path:
                        tmp = deep_get(obj, DictPath(p))
                        if tmp is not None:
                            rawvals += tmp
                    rangevals = []
                    if tmp is not None:
                        firstnum = None
                        lastnum = None
                        sortedvals = natsorted(tmp)
                        for i, sortedval in enumerate(sortedvals):
                            # The range is sorted; this means that we add everything as is except
                            # None until we reach the first numerical, create ranges for
                            # the numericals, then add everything as is except None until the end
                            if sortedval is None:
                                continue
                            # pylint: disable-next=unidiomatic-typecheck
                            if type(sortedval) == int:  # noqa: E721
                                if firstnum is None:
                                    firstnum = sortedval
                                else:
                                    if lastnum is None or sortedval == lastnum + 1:
                                        lastnum = sortedval
                                    else:
                                        # Flush and start a new range
                                        rangevals.append((f"{firstnum}", f"{lastnum}", ""))
                                        firstnum = sortedval
                                        lastnum = None
                            else:
                                if firstnum is not None:
                                    if lastnum is None:
                                        rangevals.append((f"{firstnum}", "", ""))
                                    else:
                                        rangevals.append((f"{firstnum}", f"{lastnum}", ""))
                                        lastnum = None
                                    firstnum = None
                                rangevals.append(("", "", sortedval))
                        if firstnum is not None:
                            if lastnum is None:
                                rangevals.append((f"{firstnum}", "", ""))
                            else:
                                rangevals.append((f"{firstnum}", f"{lastnum}", ""))
                    _values.append((rangevals, "raw"))
                elif ptype == "identify_type":
                    tmp = deep_get_with_fallback(obj, path, {})
                    vtype, _value = cmtlib.decode_value(tmp)
                    _values.append((vtype, "str"))
                elif ptype == "key_value":
                    value = []
                    tmp = deep_get_with_fallback(obj, path, {})
                    subtype = deep_get(_path, DictPath("subtype"), "dict")
                    # This is to be for key_value-lists provided as strings
                    if subtype == "strlist" and isinstance(tmp, str):
                        strlist = {}
                        for kv in tmp.split(","):
                            kv_tuple = kv.split("=")
                            if len(kv_tuple) != 2:
                                break
                            strlist[kv_tuple[0]] = kv_tuple[1]
                            tmp = strlist
                    if isinstance(tmp, list):
                        tmp2: dict[str, Any] = {}
                        for item in tmp:
                            if not isinstance(item, dict):
                                break
                            tmp2 = {**tmp2, **item}
                        tmp = tmp2
                    for _key, _value in tmp.items():
                        subpaths = deep_get(_path, DictPath("subpaths"), [])
                        if subpaths:
                            _value = deep_get_with_fallback(_value, subpaths)
                        if not when_filter(_path, item=None, key=_key, value=_value):
                            continue
                        _regexes_key = deep_get(_path, DictPath("key#regex"), [])
                        _regexes_value = deep_get(_path, DictPath("value#regex"), [])
                        if isinstance(_regexes_key, str):
                            _regexes_key = [_regexes_key]
                        if isinstance(_regexes_value, str):
                            _regexes_value = [_regexes_value]
                        _key = transform_filter(_key,
                                                deep_get(_path, DictPath("key#transform"), {}))
                        _value = transform_filter(_value,
                                                  deep_get(_path, DictPath("value#transform"), {}))
                        # A regex for key/value is required to capture only one group;
                        # (though conceivably there might be scenario for joining),
                        # thus the first non-None capture group will exit the match;
                        # when using multiple regexes the first matching regex exits
                        match = False
                        for _regex in _regexes_key:
                            _tmp = re.match(_regex, _key)
                            if _tmp is None:
                                continue

                            for group in _tmp.groups():
                                if group is not None:
                                    _key = group
                                    match = True
                            if match:
                                break
                        match = False
                        for _regex in _regexes_value:
                            _tmp = re.match(_regex, _value)
                            if _tmp is None:
                                continue

                            for group in _tmp.groups():
                                if group is not None:
                                    _value = group
                                    match = True
                            if match:
                                break
                        # A transform might yield multiple identical key/value pairs;
                        # ignore all except the first one
                        if (_key, _value) in value:
                            continue
                        value.append((_key, _value))
                    if not value:
                        if default is None:
                            value = []
                        else:
                            value = default
                    for tmp in value:
                        _values.append((tmp, vtype))
                elif ptype in ("match_expression", "toleration"):
                    tmp = deep_get_with_fallback(obj, path)
                    if isinstance(tmp, list):
                        value = []
                        subpath = deep_get(_path, DictPath("subpath"))
                        if subpath is None:
                            value = make_set_expression_list(tmp, toleration=ptype=="toleration")
                        else:
                            value = make_set_expression_list(tmp, toleration=ptype=="toleration")
                            for _tmp in tmp:
                                __tmp = deep_get(_tmp, DictPath(subpath), _tmp)
                                value.append(make_set_expression_list(__tmp))
                        if len(value) == 1:
                            _values.append((value[0], "raw"))
                        else:
                            for tmp in value:
                                _values.append((tmp, "raw"))
                    elif isinstance(tmp, dict):
                        value = make_set_expression_list(tmp, toleration=ptype=="toleration")
                        _values.append((value, "raw"))
                    else:
                        _values.append((default, "raw"))
                elif ptype == "lookup":
                    lookup_kind, lookup_api_group, lookup_namespace, \
                        lookup_name, tmp_lookup_selector = path
                    if isinstance(lookup_kind, list):
                        lookup_kind = deep_get_with_fallback(obj, lookup_kind, "")
                    if isinstance(lookup_api_group, list):
                        lookup_api_group = deep_get_with_fallback(obj, lookup_api_group, "")
                    if isinstance(lookup_namespace, list):
                        lookup_namespace = deep_get_with_fallback(obj, lookup_namespace, "")
                    if isinstance(lookup_name, list):
                        lookup_name = deep_get_with_fallback(obj, lookup_name, "")
                    if not tmp_lookup_selector:
                        lookup_selector = ""
                    else:
                        _lookup_selector = {}
                        for ls in tmp_lookup_selector:
                            ls_key = ls[0]
                            ls_value = ls[1]
                            if isinstance(ls_value, list):
                                ls_value = deep_get_with_fallback(obj, ls_value)
                            _lookup_selector[ls_key] = ls_value
                        lookup_selector = make_label_selector(_lookup_selector)

                    try:
                        if not lookup_name:
                            lookup_obj, _status = \
                                kh.get_list_by_kind_namespace((lookup_kind, lookup_api_group),
                                                              lookup_namespace,
                                                              label_selector=lookup_selector,
                                                              resource_cache=kh_cache)
                        else:
                            lookup_obj = \
                                kh.get_ref_by_kind_name_namespace((lookup_kind, lookup_api_group),
                                                                  lookup_name, lookup_namespace,
                                                                  resource_cache=kh_cache)
                    except NameError:
                        unknown = deep_get(_path, DictPath("unknown"), "Unknown Kind")
                        _values.append((unknown, "raw"))
                        continue
                    if lookup_obj is None \
                            or isinstance(lookup_obj, dict) and not when_filter(_path,
                                                                                item=lookup_obj):
                        _values.append((default, "raw"))
                        continue
                    subpaths = deep_get(_path, DictPath("subpaths"), [])
                    value = []
                    if subpaths:
                        tmp = []
                        if isinstance(lookup_obj, dict):
                            lookup_obj = [lookup_obj]

                        for _lookup_obj in lookup_obj:
                            for i, subpath in enumerate(subpaths):
                                tmp.append(deep_get(_lookup_obj, DictPath(subpath)))
                        if len(tmp) == 1:
                            value.append(tmp[0])
                        else:
                            value.append(tuple(tmp))

                    if not value:
                        value = default

                    substitute = deep_get(_path, DictPath("substitute"))
                    if substitute is not None:
                        value = substitute
                    _values.append((value, "raw"))
                elif ptype == "remap":
                    value = []
                    substitutions = deep_get(_path, DictPath("substitutions"), "")
                    tmp = deep_get_with_fallback(obj, path)
                    if tmp is None:
                        tmp = []

                    if type(tmp) in (bool, int, str):
                        tmp = [tmp]

                    if isinstance(tmp, list):
                        for _tmp in tmp:
                            if isinstance(_tmp, bool):
                                _tmp = f"__{str(_tmp)}"

                            if _tmp in substitutions:
                                value.append(substitutions.get(_tmp))
                            elif "__default" in substitutions:
                                value.append(substitutions.get("__default"))
                            else:
                                value.append(_tmp)
                    else:
                        raise ValueError(f"remap is not supported yet for type {type(tmp)}")
                    if not value:
                        if default is None:
                            continue
                        value.append(default)
                    for tmp in value:
                        _values.append((tmp, vtype))
                elif ptype == "substitution":
                    value = []
                    substitute = deep_get(_path, DictPath("substitute"), "")
                    tmp = deep_get_with_fallback(obj, path)
                    if tmp is None:
                        tmp = []
                    if isinstance(tmp, dict):
                        tmp = [tmp]
                    for _tmp in tmp:
                        if not when_filter(_path, item=_tmp):
                            continue
                        value.append(substitute)
                        break
                    else:
                        if "else" in _path:
                            tmp = deep_get(_path, DictPath("else"))
                            if isinstance(tmp, list):
                                tmp = deep_get_with_fallback(obj, tmp)
                            if tmp:
                                value.append(tmp)
                    if not value:
                        if default is None:
                            continue
                        value.append(default)
                    for tmp in value:
                        _values.append((tmp, vtype))
                elif ptype == "transform":
                    transform = deep_get(_path, DictPath("transform"), {})
                    tmp = deep_get_with_fallback(obj, path)
                    tmp_type = type(tmp)
                    if not isinstance(tmp, (dict, list)):
                        tmp = [tmp]
                    tmp = transform_list(tmp, transform)
                    if tmp_type not in (dict, list) and len(tmp) == 1:
                        tmp = tmp[0]
                    _values.append((tmp, vtype))
                elif ptype == "timediff":
                    if len(mpaths) != 2:
                        raise ValueError(f"Field {name}: when using pathtype: 'timediff' "
                                         "path must be [start_time_path(s), end_time_path(s)]")
                    start_time = deep_get_with_fallback(obj, mpaths[0], default=None)
                    end_time = deep_get_with_fallback(obj, mpaths[1], default=None)
                    if end_time is None or start_time is None:
                        duration = -1
                    else:
                        datetime_start = timestamp_to_datetime(start_time)
                        if isinstance(end_time, int):
                            datetime_end = start_time + timedelta(seconds=end_time)
                        else:
                            datetime_end = timestamp_to_datetime(end_time)
                        timediff = datetime_end - datetime_start
                        duration = int(timediff.total_seconds())
                        _values.append((duration, "raw"))
                elif ptype == "comparison":
                    # Input is two paths; output is the value of the first path
                    # and -2/-1/0/1 (for type mismatch, lt, eq, gt)
                    if isinstance(default, list) and len(default) == 2:
                        _default1 = default[0]
                        _default2 = default[1]
                    else:
                        _default1 = default
                        _default2 = default
                    val1 = deep_get(obj, DictPath(path[0]), _default1)
                    val2 = deep_get(obj, DictPath(path[1]), _default2)
                    # pylint: disable-next=unidiomatic-typecheck
                    if type(val1) != type(val2):  # noqa: E721
                        res = -2
                    elif val1 == val2:
                        res = 0
                    elif val1 < val2:
                        res = -1
                    else:
                        res = 1
                    _values.append(((val1, res), "raw"))
                elif ptype == "timestamp_with_age":
                    # The first array is assumed to be the start time, the second array the end time
                    start_time = None
                    end_time = None
                    start_time_index = -1
                    end_time_index = -1
                    for i, mpath in enumerate(mpaths):
                        if isinstance(mpath, list):
                            if start_time_index == -1:
                                start_time_index = i
                                start_time = deep_get_with_fallback(obj, mpath, default=None)
                            elif end_time_index == -1:
                                end_time_index = i
                                end_time = deep_get_with_fallback(obj, mpath, default=None)
                            else:
                                raise ValueError(f"{field_name} received too many timestamp paths; "
                                                 "the view file is most likely malformed")
                    if end_time is None or start_time is None:
                        end_time = None
                        duration = -1
                    else:
                        timediff = \
                            timestamp_to_datetime(end_time) - timestamp_to_datetime(start_time)
                        if (duration := timediff.days * 24 * 60 * 60 + timediff.seconds) == 0:
                            duration = 1
                        # If the task completes so quickly that start_time == end_time
                        # duration will end up as 0. The result of this would be that
                        # it's represented as <unset>.
                        # To work around this we set duration to 1 if duration == 0.
                    __values = []
                    for i, mpath in enumerate(mpaths):
                        if i == start_time_index:
                            __values.append(end_time)
                        elif i == end_time_index:
                            __values.append(duration)
                        else:
                            __values.append(mpath)
                    _values.append((tuple(__values), "raw"))
                elif ptype == "fieldgetter":
                    fieldgetter_data = deep_get_with_fallback(obj, path, {})
                    if not fieldgetter_data:
                        continue
                    fieldgetter_tmp = deep_get(fieldgetter_data, DictPath("fieldgetter"))
                    fieldgetter = deep_get(fieldgetter_allowlist, DictPath(fieldgetter_tmp))
                    if fieldgetter is None:
                        raise ValueError(f"{fieldgetter_tmp} is not a valid fieldgetter; "
                                         "the view-file is probably incorrect.")
                    fieldgetter_args = deep_get(fieldgetter_data, DictPath("fieldgetter_args"), {})
                    tmp = fieldgetter(**fieldgetter_args, kubernetes_helper=kh)
                    _values.append((tmp, vtype))
                elif ptype in ("items", "appenditems"):
                    if subpath:
                        if subpaths:
                            raise ValueError(f"Field {name}: when using action: 'items' exactly "
                                             "one of subpath and subpaths must be specified")
                        subpaths = [subpath]
                    value = []
                    items = []
                    index = deep_get(_path, DictPath("index"))
                    for mpath in mpaths:
                        if isinstance(mpath, str):
                            mpath = [mpath]
                        tmp = deep_get_list(obj, mpath, default=[],
                                            fallback_on_empty=fallback_on_empty)
                        if index is not None:
                            try:
                                tmp = [tmp[index]]
                            except IndexError:
                                pass
                        # XXX: This is to avoid breaking anything
                        # Ideally the "appenditems" behaviour should be the only one,
                        # but requires rewriting a lot of files
                        if ptype == "items":
                            items += tmp
                        else:
                            items.append(tmp)
                    for item in items:
                        if not when_filter(_path, item):
                            continue

                        tmp = []
                        for i, subpath in enumerate(subpaths):
                            if isinstance(default, list):
                                if i < len(default):
                                    _default = default[i]
                                else:
                                    _default = None
                            else:
                                _default = default

                            if (vtype in ("int", "float") or action in ["sum"]) \
                                    and type(default) not in (int, float):
                                _default = 0

                            if isinstance(subpath, dict):
                                _subpath = deep_get(subpath, DictPath("str"))
                                if _subpath is not None:
                                    tmp.append(_subpath)
                                else:
                                    _subpath = deep_get(subpath, DictPath("subpath"))
                                    _fallback_path = deep_get(subpath, DictPath("fallback_path"))
                                    _fallback_value = deep_get(obj, DictPath(_fallback_path))
                                    if _fallback_value is not None and _default is None:
                                        _default = _fallback_value
                                    if isinstance(_subpath, str):
                                        _subpath = [_subpath]
                                    _regexes = deep_get(subpath, DictPath("regex"), [])
                                    if isinstance(_regexes, str):
                                        _regexes = [_regexes]
                                    _raw = deep_get_with_fallback(item, _subpath, _default)
                                    _raw = transform_filter(_raw,
                                                            deep_get(subpath,
                                                                     DictPath("transform"), {}))
                                    for _regex in _regexes:
                                        _tmp = re.match(_regex, _raw)
                                        if _tmp is not None:
                                            for group in _tmp.groups():
                                                if group is not None:
                                                    tmp.append(group)
                                            break
                                        tmp.append("")
                                    if not tmp or not _regexes:
                                        tmp.append(_raw)
                            else:
                                prefix = deep_get(_path, DictPath("prefix"), [])
                                suffix = deep_get(_path, DictPath("suffix"), [])
                                _subpath = subpath
                                if isinstance(_subpath, str):
                                    _subpath = [_subpath]
                                tmp_ = deep_get_with_fallback(item, _subpath, _default)
                                if isinstance(tmp_, str):
                                    tmp_ = __process_string(tmp_, replace_quotes="same")
                                if isinstance(prefix, str):
                                    if isinstance(tmp_, str):
                                        tmp_ = prefix + tmp_
                                    else:
                                        tmp_ = [prefix] + tmp_
                                else:
                                    tmp += prefix

                                if isinstance(suffix, str):
                                    if isinstance(tmp_, str):
                                        tmp_ += suffix
                                    else:
                                        tmp_ += [suffix]

                                tmp.append(tmp_)

                                if isinstance(suffix, list):
                                    tmp += suffix
                        if len(tmp) == 1:
                            value.append(tmp[0])
                        else:
                            value.append(tuple(tmp))
                    if not value:
                        value = default
                    if value is not None:
                        if action in ("sum", "latest", "earliest"):
                            _values.append((value, vtype))
                        else:
                            for tmp in value:
                                _values.append((tmp, vtype))
                elif ptype == "count":
                    count = 0
                    for p in path:
                        count += len(deep_get(obj, DictPath(p), {}))
                    _values.append((count, vtype))
                elif ptype == "split":
                    value = []
                    separator = deep_get(_path, DictPath("separator"), ",")
                    _raw = deep_get_with_fallback(obj, path, "")
                    if _raw is not None:
                        for tmp in _raw.split(separator):
                            _values.append((tmp, vtype))
                elif ptype == "regex":
                    value = []
                    _raw = deep_get_with_fallback(obj, path, "")
                    _regexes = deep_get(_path, DictPath("regex"), [])
                    if isinstance(_regexes, str):
                        _regexes = [_regexes]
                    if _raw is not None and _raw:
                        for _regex in _regexes:
                            _tmp = re.match(_regex, _raw)
                            if _tmp is not None:
                                for group in _tmp.groups():
                                    if group is not None:
                                        value.append(group)
                                break
                    elif default:
                        value = default
                    value = tuple(value)
                    _values.append((value, "raw"))
                elif ptype == "tuple":
                    value = []
                    if not when_filter(_path, item=obj):
                        continue
                    for i, element in enumerate(path):
                        if isinstance(default, list):
                            if i < len(default):
                                _default = default[i]
                            else:
                                _default = None
                        else:
                            _default = default

                        if vtype in ("int", "float") and type(default) not in (int, float):
                            _default = 0

                        # This is a literal string, not a path
                        if isinstance(element, str):
                            tmp = element
                        else:
                            tmp = deep_get_with_fallback(obj, element, default=_default,
                                                         fallback_on_empty=fallback_on_empty)

                        if vtype == "api_group":
                            override_paths = [DictPath(f"Views#{view}#kind_format_{field_index}"),
                                              DictPath(f"Views#{view}#kind_format"),
                                              DictPath(f"Global#kind_format_{field_index}"),
                                              DictPath("Global#kind_format")]
                            override_kind = \
                                deep_get_with_fallback(cmtlib.cmtconfig, override_paths, "mixed")
                            if override_kind == "skip" \
                                    or override_kind == "mixed" and "." not in tmp:
                                tmp = ""
                            vtype = "kind"
                        value.append(tmp)
                    if isinstance(deep_get(_path, DictPath("substitute")), list):
                        value = deep_get(_path, DictPath("substitute"))
                    value = tuple(value)
                    _values.append((value, vtype))
                elif ptype == "status_tuple":
                    if "lookup" in _path:
                        lookup_kind = deep_get(_path, DictPath("lookup#kind"))
                        lookup_api_family = deep_get(_path, DictPath("lookup#api_family"))
                        lookup_status = deep_get(_path, DictPath("lookup#status"))
                    else:
                        raise ValueError(f"Field {name}: currently status_tuple "
                                         "only supports 'lookup'")
                    path = deep_get(_path, DictPath("path"))
                    value = deep_get(obj, DictPath(path))
                    tmp = kh.get_ref_by_kind_name_namespace((lookup_kind, lookup_api_family),
                                                            value, "", resource_cache=kh_cache)
                    if lookup_status == "highlight":
                        if tmp is None:
                            status_group = StatusGroup.NOT_OK
                        else:
                            status_group = StatusGroup.OK
                        value = (value, status_group)
                    elif lookup_status == "message":
                        if tmp is None:
                            value = (deep_get(_path, DictPath("lookup#messages#not_ok")),
                                     StatusGroup.NEUTRAL)
                        else:
                            value = (deep_get(_path, DictPath("lookup#messages#ok")),
                                     StatusGroup.NEUTRAL)
                    _values.append((value, "raw"))
                elif ptype == "dictkeys":
                    for mpath in mpaths:
                        tmp = list(deep_get_with_fallback(obj, mpath, {}).keys())
                        if tmp:
                            _values.append((tmp, "raw"))
                elif ptype == "dictfields":
                    subpaths = deep_get_with_fallback(_path, [DictPath("subpaths"),
                                                              DictPath("subpath")], [])
                    if isinstance(subpaths, str):
                        subpaths = [[subpaths]]
                    for mpath in mpaths:
                        tmp = deep_get_with_fallback(obj, mpath)
                        if not when_filter(_path, item=tmp):
                            continue
                        value = []
                        for key in subpaths:
                            if isinstance(key, str):
                                value.append(key)
                            else:
                                value.append(deep_get_with_fallback(tmp, key, default))
                        if len(value) == 1:
                            _values.append((value[0], "raw"))
                        else:
                            _values.append((tuple(value), "raw"))
                else:
                    value = deep_get_with_fallback(obj, path, default,
                                                   fallback_on_empty=fallback_on_empty)
                    if value is not None:
                        _values.append((value, vtype))
            values = []

            processor_args = {
                "action": action,
                "field_index": field_index,
                "field_name": name,
                "formatter": formatter,
                "regex_": deep_get(_path, DictPath("regex")),
                "replace_quotes": replace_quotes,
                "view": view,
            }
            if unique_values:
                unique = []
                _values = [unique.append(x) for x in _values if x not in unique]
                _values = unique
            for value, vtype_ in _values:
                if isinstance(vtype_, list):
                    if value is None or not value:
                        value = []
                if isinstance(value, list) and vtype_ == "raw":
                    values += value
                    continue
                if isinstance(value, list) and isinstance(vtype_, list):
                    tmp = []
                    for value_ in value:
                        tmp.append(process_value(value_, vtype_, **processor_args))
                else:
                    tmp = process_value(value, vtype_, **processor_args)
                values.append(tmp)

            if not values:
                values = global_default

            if isinstance(values, list) and len(values) == 1 and formatter != "list":
                d[name] = values[0]
            else:
                d[name] = values

    # We've got all the information we can get now; time to apply filters
    skip = False
    for f in filters:
        if not deep_get(filters[f], DictPath("enabled"), True):
            continue

        # If len(allow) > 0, we only allow fields that match
        allow = deep_get(filters[f], DictPath("allow"), [])
        # If len(block) > 0, we skip fields that match
        block = deep_get(filters[f], DictPath("block"), [])
        source = deep_get(filters[f], DictPath("source"), "")
        if source == "object":
            src = obj
        else:
            src = d
        if allow:
            # If all field + value pairs match we allow
            for rule in allow:
                key = deep_get(rule, DictPath("key"), "")
                values = deep_get(rule, DictPath("values"), "")

                if deep_get(src, DictPath(key), "").rstrip() not in values:
                    skip = True
                    break
        if block:
            # If all field + value pairs match we block
            for rule in block:
                key = deep_get(rule, DictPath("key"), "")
                values = deep_get(rule, DictPath("values"), "")
                if deep_get(src, DictPath(key), "").rstrip() in values:
                    skip = True
                    break
        if skip:
            break
    if skip:
        entry = None
    else:
        d["ref"] = obj
        d["__deleted"] = deleted
        d["__uid"] = deep_get(obj, DictPath("metadata#uid"))
        entry = type("InfoClass", (), d)

    return entry


def generic_infogetter(**kwargs: Any) -> list[Type]:
    """
    Generic getter for information from an object.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
                _vlist ([dict]): A list of already populated entries
                field_dict (dict): The dict containing the description of the field
                field_names ([str]): The names of the fields to populate
                field_index (str): The index for the field list
                filters (dict): The filters to apply
                extra_data (dict): Extra data to add to the obj
                caller_obj (dict): Used for lookups when doing path substitutions
        Returns:
            ([InfoClass]): A list of InfoClass objects
                           with the data for all fields in the field_names list
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError(f"{__name__}() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    info: list[Type] = []

    # Generate an empty entry
    if not (vlist := deep_get(kwargs, DictPath("_vlist"), [])):
        return []

    field_dict = deep_get(kwargs, DictPath("_field_dict"), {})
    field_names = deep_get(kwargs, DictPath("_field_names"), [])
    field_index = deep_get(kwargs, DictPath("_field_index"), "Normal")
    filters = deep_get(kwargs, DictPath("_filters"), {})
    extra_data = deep_get(kwargs, DictPath("extra_data"), {})
    caller_obj = deep_get(kwargs, DictPath("caller_obj"), {})

    if not field_dict or not field_names:
        sys.exit(f"generic_infogetter() received empty field_dict {field_dict} "
                 f"or field_names {field_names}; this is a programming error")

    # If we know the view we can use it to get overrides from cmt.yaml
    view = deep_get(kwargs, DictPath("_view"), "")
    for obj in vlist:
        if extra_data:
            obj["_extra_data"] = extra_data
        deleted = False
        if deep_get(obj, DictPath("metadata#deletionTimestamp")) is not None:
            deleted = True
        tmp = get_obj(obj, field_dict=field_dict, field_names=field_names, field_index=field_index,
                      view=view, filters=filters, deleted=deleted, caller_obj=caller_obj,
                      kubernetes_helper=kh, kh_cache=kh_cache)
        if tmp is None:
            continue

        info.append(tmp)

    return info


# pylint: disable-next=too-many-locals
def get_pod_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for Pods.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                vlist ([dict[str, Any]]): The list of Pod info
                in_depth_node_status (bool): Should in-depth node status be shown?
                extra_vars (dict): Extra variables
                filters ([dict]): A dict of filters to apply
        Returns:
            ([InfoClass]): A list with info
    """
    in_depth_node_status: bool = deep_get(kwargs, DictPath("in_depth_node_status"), True)
    extra_vars: dict[str, Any] = deep_get(kwargs, DictPath("extra_vars"),
                                          {"show_kind": "", "show_evicted": True})
    filters: list[dict[str, Any]] = deep_get(kwargs, DictPath("filters"), [])
    info: list[Type] = []

    if not (vlist := deep_get(kwargs, DictPath("vlist"))):
        return []

    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("get_pod_info() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    for obj in vlist:
        skip = False

        # Sadly field_labels do not support all fields we might want to filter on,
        # so we have to complicate things a bit
        for key, value in filters:
            ovalue = deep_get(obj, DictPath(key), None)
            if ovalue is None or ovalue != value:
                skip = True
                break

        if skip:
            continue

        phase = deep_get(obj, DictPath("status#phase"))
        reason = deep_get(obj, DictPath("status#reason"), "").rstrip()

        if (not deep_get(extra_vars, DictPath("show_evicted"), False)
                and phase == "Failed" and reason == "Evicted"):
            continue

        namespace = deep_get(obj, DictPath("metadata#namespace"))
        name = deep_get(obj, DictPath("metadata#name"))
        ref = obj
        nodename = deep_get(obj, DictPath("spec#nodeName"), "<none>")
        status, status_group = \
            datagetters.get_pod_status(obj, kubernetes_helper=kh,
                                       kh_cache=kh_cache,
                                       in_depth_node_status=in_depth_node_status)

        if in_depth_node_status:
            timestamp = \
                timestamp_to_datetime(deep_get(obj, DictPath("metadata#creationTimestamp")))
            age = get_since(timestamp)

            owr = deep_get(obj, DictPath("metadata#ownerReferences"), [])
            controller_ = get_controller_from_owner_references(owr)
            show_kind = deep_get(extra_vars, DictPath("show_kind"), "").lower()
            controller = format_controller(controller_, show_kind)

            pod_ip = deep_get(obj, DictPath("status#podIP"), "<unset>")
            pod_restarts, restarted_at = get_pod_restarts_total(obj)
            if restarted_at == -1:
                last_restart = -1
            else:
                last_restart = get_since(restarted_at)
            container_list = deep_get(obj, DictPath("spec#containers"), [])
            container_statuses = deep_get(obj, DictPath("status#containerStatuses"), [])
            init_container_list = deep_get(obj, DictPath("spec#initContainers"), [])
            init_container_statuses = deep_get(obj, DictPath("status#initContainerStatuses"), [])
            tolerations = itemgetters.get_pod_tolerations(obj)
            containers = get_containers(containers=init_container_list,
                                        container_statuses=init_container_statuses)
            containers += get_containers(containers=container_list,
                                         container_statuses=container_statuses)

            info.append(type("InfoClass", (), {
                "namespace": namespace,
                "name": name,
                # The reference to the "true" resource object
                "ref": ref,
                "status": status,
                "status_group": status_group,
                "node": nodename,
                "pod_ip": pod_ip,
                "age": age,
                "restarts": pod_restarts,
                "last_restart": last_restart,
                "controller": controller,
                "tolerations": tolerations,
                "containers": containers,
            }))
        else:
            # This is to speed up the cluster overview,
            # which doesn't use most of this information anyway;
            # for clusters with a huge amount of pods
            # this can make a quite significant difference.
            info.append(type("InfoClass", (), {
                "namespace": namespace,
                "name": name,
                # The reference to the "true" resource object
                "ref": ref,
                "status": status,
                "status_group": status_group,
                "node": nodename,
            }))
    return info


# pylint: disable-next=too-many-locals
def get_node_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for Nodes.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                vlist ([dict[str, Any]]): The list of Node objects
        Returns:
            info (list[InfoClass]): A list with info
    """
    info: list[Type] = []

    if (vlist := deep_get(kwargs, DictPath("vlist"))) is None or not vlist:
        return []

    for obj in vlist:
        name = deep_get(obj, DictPath("metadata#name"))
        # For now we do not do anything with external IPs; we should
        hostname, internal_ips, _external_ips = \
            get_node_addresses(deep_get(obj, DictPath("status#addresses")))
        ref = obj
        kubernetes_roles = get_node_roles(obj)
        timestamp = \
            timestamp_to_datetime(deep_get(obj, DictPath("metadata#creationTimestamp")))
        age = get_since(timestamp)
        cpu = (deep_get(obj, DictPath("status#allocatable"))["cpu"],
               deep_get(obj, DictPath("status#capacity"))["cpu"])
        # Strip Ki suffix
        mem = (deep_get(obj, DictPath("status#allocatable"))["memory"][:-2],
               deep_get(obj, DictPath("status#capacity"))["memory"][:-2])
        status, status_group, taints, _full_taints = get_node_status(obj)
        kubelet_version = deep_get(obj, DictPath("status#nodeInfo#kubeletVersion"))
        container_runtime = deep_get(obj, DictPath("status#nodeInfo#containerRuntimeVersion"))
        operating_system = deep_get(obj, DictPath("status#nodeInfo#osImage"))
        kernel = deep_get(obj, DictPath("status#nodeInfo#kernelVersion"))

        info.append(type("InfoClass", (), {
            "name": name,
            "hostname": hostname,
            "ref": ref,
            "status": status,
            "status_group": status_group,
            "kubernetes_roles": kubernetes_roles,
            "age": age,
            "kubelet_version": kubelet_version,
            "internal_ips": internal_ips,
            "os": operating_system,
            "kernel": kernel,
            "container_runtime": container_runtime,
            "cpu": cpu,
            "mem": mem,
            "taints": taints,
        }))

    return info


def get_node_addresses(addresses: list[dict]) -> tuple[str, list[str], list[str]]:
    """
    Given the addresses list return all internal/external IPs and the hostname.

        Parameters:
            addresses ([dict]): A list of address objects
        Returns:
            ((str, [str], [str])):
                (str): Hostname
                ([str]): Internal IPs
                ([str]): External IPs
    """
    iips = []
    eips = []

    new_name = None

    for address in addresses:
        address_type = deep_get(address, DictPath("type"))
        address_address = deep_get(address, DictPath("address"))
        if address_type == "InternalIP":
            iips.append(address_address)
        elif address_type == "ExternalIP":
            eips.append(address_address)
        # handle external IPs too
        elif address_type == "Hostname":
            if new_name is None:
                new_name = address_address
            else:
                msg = [
                    [("A host was encountered with multiple hostnames; ", "default"),
                     (f"{about.UI_PROGRAM_NAME}", "programname"),
                     (" currently only supports single hostnames.", "default")],
                    [("Please file a bugreport and include a YAML or JSON-dump "
                      "for the node ", "default"),
                     (f"{new_name}", "hostname"),
                     (".", "default")],
                ]
                unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)
                cmtlog.log(LogLevel.ERR, msg=unformatted_msg, messages=formatted_msg)
        else:
            continue

    if not iips:
        iips = ["<unset>"]
        eips = ["<unset>"]
    if not eips:
        eips = ["<none>"]
    if new_name is None:
        new_name = "<unset>"

    return new_name, iips, eips


# pylint: disable-next=too-many-locals
def get_auth_rule_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for Istio Authorization Policy Rules.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                _obj (Dict): The dict to extract data from
        Returns:
            ([InfoClass]): A list with info
    """
    obj = deep_get(kwargs, DictPath("_obj"))
    info: list[Type] = []

    if obj is None:
        return []

    for item in deep_get(obj, DictPath("spec#rules"), []):
        sources = []
        operations = []
        conditions = []

        for source in deep_get(item, DictPath("from"), []):
            principals = ",".join(deep_get(source, DictPath("source#principals"), []))
            not_principals = ",".join(deep_get(source, DictPath("source#notPrincipals"), []))
            request_principals = \
                ",".join(deep_get(source, DictPath("source#requestPrincipals"), []))
            not_request_principals = \
                ",".join(deep_get(source, DictPath("source#notRequestPrincipals"), []))
            namespaces = ",".join(deep_get(source, DictPath("source#namespaces"), []))
            not_namespaces = ",".join(deep_get(source, DictPath("source#notNamespaces"), []))
            ip_blocks = ",".join(deep_get(source, DictPath("source#ipBlocks"), []))
            not_ip_blocks = ",".join(deep_get(source, DictPath("source#notIpBlocks"), []))
            sources.append((principals, not_principals,
                            request_principals, not_request_principals,
                            namespaces, not_namespaces,
                            ip_blocks, not_ip_blocks))

        for operation in deep_get(item, DictPath("to"), []):
            hosts = ",".join(deep_get(operation, DictPath("operation#hosts"), []))
            not_hosts = ",".join(deep_get(operation, DictPath("operation#notHosts"), []))
            ports = ",".join(deep_get(operation, DictPath("operation#ports"), []))
            not_ports = ",".join(deep_get(operation, DictPath("operation#notPorts"), []))
            methods = ",".join(deep_get(operation, DictPath("operation#methods"), []))
            not_methods = ",".join(deep_get(operation, DictPath("operation#notMethods"), []))
            paths = ",".join(deep_get(operation, DictPath("operation#paths"), []))
            not_paths = ",".join(deep_get(operation, DictPath("operation#notPaths"), []))
            operations.append((hosts, not_hosts,
                               ports, not_ports,
                               methods, not_methods,
                               paths, not_paths))

        for condition in deep_get(item, DictPath("when"), []):
            key = deep_get(condition, DictPath("key"))
            values = ",".join(deep_get(condition, DictPath("values"), []))
            not_values = ",".join(deep_get(condition, DictPath("notValues"), []))
            conditions.append((key, values, key, not_values))

        if sources or operations or conditions:
            info.append(type("InfoClass", (), {
                "sources": sources,
                "operations": operations,
                "conditions": conditions,
            }))
    return info


def get_eps_subsets_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for EndpointSlice subsets.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                _obj (Dict): The dict to extract data from
        Returns:
            info (list[InfoClass]): A list with info
    """
    if (obj := deep_get(kwargs, DictPath("_obj"))) is None:
        return []

    addresstype = deep_get(obj, DictPath("addressType"))
    subsets = []
    ports = []

    for port in deep_get(obj, DictPath("ports"), []):
        port_name = deep_get(port, DictPath("name"), "")
        ports.append((port_name, deep_get(port, DictPath("port")),
                      deep_get(port, DictPath("protocol"))))

    for endpoint in deep_get(obj, DictPath("endpoints"), []):
        ready_addresses = []
        not_ready_addresses = []

        for address in deep_get(endpoint, DictPath("addresses"), []):
            if deep_get(endpoint, DictPath("conditions#ready")):
                ready_addresses.append(address)
            else:
                not_ready_addresses.append(address)
        target_ref = (deep_get(endpoint, DictPath("targetRef#kind"), ""),
                      deep_get(endpoint, DictPath("targetRef#apiVersion"), ""),
                      deep_get(endpoint, DictPath("targetRef#namespace"), ""),
                      deep_get(endpoint, DictPath("targetRef#name"), ""))
        topology = []
        # If nodeName is available this is the new API
        # where topology is replaced by nodeName and zone
        if "nodeName" in endpoint:
            topology.append(("nodeName", deep_get(endpoint, DictPath("nodeName"), "<unset>")))
            if "zone" in endpoint:
                topology.append(("zone", deep_get(endpoint, DictPath("zone"), "<unset>")))
        else:
            for key, value in deep_get(endpoint, DictPath("topology"), {}).items():
                topology.append((key, value))

        if ready_addresses:
            subsets.append(type("InfoClass", (), {
                "addresstype": addresstype,
                "addresses": ready_addresses,
                "ports_eps": ports,
                "status": "Ready",
                "status_group": StatusGroup.OK,
                "target_ref": target_ref,
                "topology": topology,
            }))
        if not_ready_addresses:
            subsets.append(type("InfoClass", (), {
                "addresstype": addresstype,
                "addresses": not_ready_addresses,
                "ports_eps": ports,
                "status": "Not Ready",
                "status_group": StatusGroup.NOT_OK,
                "target_ref": target_ref,
                "topology": topology,
            }))
    return subsets


def get_key_value_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for key/value-based information.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                vlist ([dict[str, Any]]): The list of key/value objects
        Returns:
            ([InfoClass]): A list with info
    """
    info: list[Type] = []

    vlist = deep_get(kwargs, DictPath("_vlist"))
    if vlist is None:
        return info

    for key, value in vlist.items():
        decoded_value = ""

        vtype, value = cmtlib.decode_value(value)
        vlen = len(value)
        decoded_value = value

        if not vlen:
            value = ""
            vtype = "empty"

        if vtype.startswith("base64-utf-8"):
            fully_decoded_value = base64.b64decode(decoded_value).decode("utf-8")
        else:
            fully_decoded_value = decoded_value

        if len(decoded_value) > 8192 and value:
            vtype = f"{vtype} [truncated]"
            decoded_value = value[0:8192 - 1]

        ref = {
            "key": key,
            "value": value,
            "decoded_value": decoded_value,
            "fully_decoded_value": fully_decoded_value,
            "vtype": vtype,
            "vlen": vlen,
        }
        info.append(type("InfoClass", (), {
            "key": key,
            "ref": ref,
            "decoded_value": decoded_value,
            "value": value,
            "vtype": vtype,
            "vlen": vlen,
        }))

    return info


def get_limit_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for Limits.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
        Returns:
            ([InfoClass]): A list with info
    """
    obj = deep_get(kwargs, DictPath("_obj"))
    info: list[Type] = []

    if obj is None:
        return []

    for limit in deep_get(obj, DictPath("spec#limits"), []):
        resources = set()

        for item in deep_get(limit, DictPath("default"), []):
            resources.add(item)
        for item in deep_get(limit, DictPath("defaultRequest"), []):
            resources.add(item)
        for item in deep_get(limit, DictPath("min"), []):
            resources.add(item)
        for item in deep_get(limit, DictPath("max"), []):
            resources.add(item)
        for item in deep_get(limit, DictPath("max"), []):
            resources.add(item)
        for item in deep_get(limit, DictPath("maxLimitRequestRatio"), []):
            resources.add(item)
        ltype = deep_get(limit, DictPath("type"))

        for item in resources:
            lmin = deep_get(limit, DictPath(f"min#{item}"), "-")
            lmax = deep_get(limit, DictPath(f"max#{item}"), "-")
            default_request = deep_get(limit, DictPath(f"defaultRequest#{item}"), "-")
            default_limit = deep_get(limit, DictPath(f"default#{item}"), "-")
            max_lr_ratio = deep_get(limit, DictPath(f"maxLimitRequestRatio#{item}"), "-")
            info.append(type("InfoClass", (), {
                "name": item,
                "ref": limit,
                "ltype": ltype,
                "lmin": lmin,
                "lmax": lmax,
                "default_request": default_request,
                "default_limit": default_limit,
                "max_lr_ratio": max_lr_ratio,
            }))
    return info


def get_promrules_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for Prometheus Rules.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                _obj (Dict): The dict to extract data from
        Returns:
            info (list[InfoClass]): A list with info
    """
    obj = deep_get(kwargs, DictPath("_obj"))
    info: list[Type] = []

    if obj is None:
        return []

    for group in deep_get(obj, DictPath("spec#groups"), []):
        for rule in deep_get(group, DictPath("rules")):
            name = deep_get(group, DictPath("name"))
            alert = deep_get(rule, DictPath("alert"), "")
            record = deep_get(rule, DictPath("record"), "")
            if alert and record:
                # This is an invalid entry; just ignore it
                continue
            if alert:
                rtype = "Alert"
                alertrecord = alert
            elif record:
                rtype = "Record"
                alertrecord = record
            else:
                # This is an invalid entry; just ignore it
                continue
            _extra_data = {
                "name": alertrecord,
                "group": name,
                "rtype": rtype,
            }
            if "_extra_data" not in rule:
                rule["_extra_data"] = _extra_data
            ref = rule
            age = deep_get(rule, DictPath("for"), "")
            duration = cmtlib.age_to_seconds(age)
            info.append(type("InfoClass", (), {
                "group": name,
                "ref": ref,
                "rtype": rtype,
                "alertrecord": alertrecord,
                "duration": duration,
            }))
    return info


def get_rq_item_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for Resource Quotas.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                _obj (Dict): The dict to extract data from
        Returns:
            info (list[InfoClass]): A list with info
    """
    obj = deep_get(kwargs, DictPath("_obj"))
    hard_path = deep_get(kwargs, DictPath("hard_path"), DictPath("spec#hard"))
    used_path = deep_get(kwargs, DictPath("used_path"), DictPath("status#used#hard"))
    info = []

    if obj is None:
        return []

    for resource in deep_get(obj, hard_path, []):
        used = deep_get(obj, DictPath(f"{used_path}#{resource}"), [])
        hard = deep_get(obj, DictPath(f"{hard_path}#{resource}"), [])

        info.append(type("InfoClass", (), {
            "resource": resource,
            "used": used,
            "hard": hard,
        }))
    return info


# pylint: disable-next=too-many-locals,too-many-statements
def get_sas_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for Service Account secrets.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                _obj (Dict): The dict to extract data from
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
        Returns:
            ([InfoClass]): A list with info
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("get_sas_info() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    obj = deep_get(kwargs, DictPath("_obj"))
    info: list[Type] = []

    if obj is None:
        return []

    saname = deep_get(obj, DictPath("metadata#name"))
    sanamespace = deep_get(obj, DictPath("metadata#namespace"))

    for secret in deep_get(obj, DictPath("secrets"), []):
        snamespace = deep_get(secret, DictPath("namespace"),
                              deep_get(obj, DictPath("metadata#namespace")))
        secret_name = deep_get(secret, DictPath("name"))

        # Get a reference to the secret
        ref = kh.get_ref_by_kind_name_namespace(("Secret", ""),
                                                secret_name, snamespace, resource_cache=kh_cache)

        info.append(type("InfoClass", (), {
            "name": secret_name,
            "ref": ref,
            "namespace": snamespace,
            "kind": ("Secret", ""),
            "type": "Mountable",
        }))

    for secret in deep_get(obj, DictPath("imagePullSecrets"), []):
        deep_set(ref, DictPath("kind"), "Secret", create_path=True)
        deep_set(ref, DictPath("apiVersion"), "", create_path=True)
        snamespace = deep_get(secret, DictPath("namespace"),
                              deep_get(obj, DictPath("metadata#namespace")))
        secret_name = deep_get(secret, DictPath("name"))

        # Get a reference to the secret
        ref = kh.get_ref_by_kind_name_namespace(("Secret", ""), secret_name,
                                                snamespace, resource_cache=kh_cache)

        info.append(type("InfoClass", (), {
            "name": secret_name,
            "ref": ref,
            "namespace": snamespace,
            "kind": ("Secret", ""),
            "type": "Image Pull",
        }))

    vlist, _status = kh.get_list_by_kind_namespace(("RoleBinding", "rbac.authorization.k8s.io"),
                                                   "", resource_cache=kh_cache)

    # Get all Role Bindings that bind to this ServiceAccount
    for ref in vlist:
        deep_set(ref, DictPath("kind"), "RoleBinding", create_path=True)
        deep_set(ref, DictPath("apiVersion"), "rbac.authorization.k8s.io/", create_path=True)
        for subject in deep_get(ref, DictPath("subjects"), []):
            subjectkind = deep_get(subject, DictPath("kind"), "")
            subjectname = deep_get(subject, DictPath("name"), "")
            subjectnamespace = deep_get(subject, DictPath("namespace"), "")
            if subjectkind == "ServiceAccount" \
                    and subjectname == saname and subjectnamespace == sanamespace:
                info.append(type("InfoClass", (), {
                    "name": deep_get(ref, DictPath("metadata#name")),
                    "ref": ref,
                    "namespace": deep_get(ref, DictPath("metadata#namespace")),
                    "kind": ("RoleBinding", "rbac.authorization.k8s.io"),
                    "type": "",
                }))

                # Excellent, we have a Role Binding, now add the role it binds to
                rolerefkind = (deep_get(ref, DictPath("roleRef#kind"), ""),
                               deep_get(ref, DictPath("roleRef#apiGroup")))
                rolerefname = deep_get(ref, DictPath("roleRef#name"), "")
                rolerefnamespace = deep_get(ref, DictPath("metadata#namespace"), "")
                roleref = kh.get_ref_by_kind_name_namespace(rolerefkind, rolerefname,
                                                            rolerefnamespace,
                                                            resource_cache=kh_cache)
                if roleref is not None:
                    deep_set(roleref, DictPath("kind"), rolerefkind[0], create_path=True)
                    deep_set(roleref, DictPath("apiVersion"), f"{rolerefkind[1]}/",
                             create_path=True)
                info.append(type("InfoClass", (), {
                    "name": rolerefname,
                    "ref": roleref,
                    "namespace": subjectnamespace,
                    "kind": rolerefkind,
                    "type": "",
                }))
                break

    vlist, _status = \
        kh.get_list_by_kind_namespace(("ClusterRoleBinding", "rbac.authorization.k8s.io"), "",
                                      resource_cache=kh_cache)

    # Get all Cluster Role Bindings that bind to this ServiceAccount
    for ref in vlist:
        deep_set(ref, DictPath("kind"), "ClusterRoleBinding", create_path=True)
        deep_set(ref, DictPath("apiVersion"), "rbac.authorization.k8s.io/", create_path=True)
        for subject in deep_get(ref, DictPath("subjects"), []):
            subjectkind = deep_get(subject, DictPath("kind"), "")
            subjectname = deep_get(subject, DictPath("name"), "")
            subjectnamespace = deep_get(subject, DictPath("namespace"), "")
            if subjectkind == "ServiceAccount" \
                    and subjectname == saname and subjectnamespace == sanamespace:
                info.append(type("InfoClass", (), {
                    "name": deep_get(ref, DictPath("metadata#name")),
                    "ref": ref,
                    "namespace": deep_get(ref, DictPath("metadata#namespace")),
                    "kind": ("ClusterRoleBinding", "rbac.authorization.k8s.io"),
                    "type": "",
                }))

                # Excellent, we have a Cluster Role Binding, now add the role it binds to
                rolerefkind = (deep_get(ref, DictPath("roleRef#kind"), ""),
                               deep_get(ref, DictPath("roleRef#apiGroup")))
                rolerefname = deep_get(ref, DictPath("roleRef#name"), "")
                roleref = kh.get_ref_by_kind_name_namespace(rolerefkind, rolerefname,
                                                            subjectnamespace,
                                                            resource_cache=kh_cache)
                if roleref is not None:
                    deep_set(roleref, DictPath("kind"), rolerefkind[0], create_path=True)
                    deep_set(roleref, DictPath("apiVersion"), f"{rolerefkind[1]}/",
                             create_path=True)
                info.append(type("InfoClass", (), {
                    "name": rolerefname,
                    "ref": roleref,
                    "namespace": subjectnamespace,
                    "kind": rolerefkind,
                    "type": "",
                }))
                break

    return info


def get_strategy_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for Telemetry Aware Scheduling policies.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                _obj (Dict): The dict to extract data from
        Returns:
            ([InfoClass]): A list with info
    """
    obj = deep_get(kwargs, DictPath("_obj"))
    info = []

    if obj is None:
        return []

    labeling_rules = deep_get(obj, DictPath("spec#strategies#labeling#rules"), [])
    deschedule_rules = deep_get(obj, DictPath("spec#strategies#deschedule#rules"), [])
    dontschedule_rules = deep_get(obj, DictPath("spec#strategies#dontschedule#rules"), [])
    scheduleonmetric_rules = deep_get(obj, DictPath("spec#strategies#scheduleonmetric#rules"), [])

    if deschedule_rules:
        strategy = "deschedule"
        rule = deschedule_rules[0]

        # Even though this is an array there's only one rule
        name = deep_get(rule, DictPath("metricname"), "")
        operator = deep_get(rule, DictPath("operator"), "")
        target = deep_get(rule, DictPath("target"), -1)
        info.append(type("InfoClass", (), {
            "strategy": strategy,
            "name": name,
            "operator": operator,
            "target": target,
            "labels": [],
        }))

    if dontschedule_rules:
        strategy = "dontschedule"
        # dontschedule can have multiple rules; if it does we build a hackish tree
        if len(dontschedule_rules) > 1:
            info.append(type("InfoClass", (), {
                "strategy": strategy,
                "name": "",
                "operator": "",
                "target": -1,
                "labels": [],
            }))
            for rule in dontschedule_rules:
                name = rule.get("metricname", "")
                operator = rule.get("operator", "")
                target = rule.get("target", -1)
                info.append(type("InfoClass", (), {
                    "strategy": "",
                    "name": rule.get("metricname", ""),
                    "operator": rule.get("operator", ""),
                    "target": rule.get("target", -1),
                    "labels": [],
                }))
        else:
            rule = dontschedule_rules[0]
            name = rule.get("metricname", "")
            operator = rule.get("operator", "")
            target = rule.get("target", -1)
            info.append(type("InfoClass", (), {
                "strategy": strategy,
                "name": name,
                "operator": operator,
                "target": target,
                "labels": [],
            }))

    if scheduleonmetric_rules:
        strategy = "scheduleonmetric"
        rule = deschedule_rules[0]

        # Even though this is an array there's only one rule
        name = rule.get("metricname", "")
        operator = rule.get("operator", "")
        target = rule.get("target", -1)
        info.append(type("InfoClass", (), {
            "strategy": strategy,
            "name": name,
            "operator": operator,
            "target": target,
            "labels": [],
        }))

    for rule in labeling_rules:
        strategy = "labeling"

        # Even though this is an array there's only one rule
        name = rule.get("metricname", "")
        operator = rule.get("operator", "")
        target = rule.get("target", -1)
        labels = rule.get("labels", [])
        info.append(type("InfoClass", (), {
            "strategy": strategy,
            "name": name,
            "operator": operator,
            "target": target,
            "labels": labels,
        }))

    return info


# pylint: disable-next=too-many-locals,too-many-branches
def get_subsets_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for Endpoint subsets.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                _obj (Dict): The dict to extract data from
        Returns:
            ([InfoClass]): A list with info
    """
    if (obj := deep_get(kwargs, DictPath("_obj"))) is None:
        return []

    subsets_ = []
    subsets = []

    # Policy for subsets expansion
    expand_subsets = deep_get(cmtlib.cmtconfig, DictPath("Endpoints#expand_subsets"), "None")
    if expand_subsets not in ("None", "Port", "Address", "Both"):
        expand_subsets = "None"

    for subset in deep_get(obj, DictPath("subsets"), []):
        ready_addresses = []
        not_ready_addresses = []
        ports = []

        if deep_get(subset, DictPath("ports")) is None:
            continue

        if not deep_get(subset, DictPath("addresses"), []) \
                and not deep_get(subset, DictPath("notReadyAddresses"), []):
            continue

        for port in deep_get(subset, DictPath("ports"), []):
            name = deep_get(port, DictPath("name"), "")
            ports.append((name,
                          deep_get(port, DictPath("port")),
                          deep_get(port, DictPath("protocol"))))

        for address in deep_get(subset, DictPath("addresses"), []):
            ready_addresses.append(deep_get(address, DictPath("ip")))

        for not_ready_address in deep_get(subset, DictPath("notReadyAddresses"), []):
            not_ready_addresses.append(deep_get(not_ready_address, DictPath("ip")))

        if expand_subsets == "None":
            if ready_addresses:
                subsets.append((ready_addresses, ports, "Ready", StatusGroup.OK))
            if not_ready_addresses:
                subsets.append((not_ready_addresses, ports, "Not Ready", StatusGroup.NOT_OK))
        elif expand_subsets == "Port":
            for port in ports:
                if ready_addresses:
                    subsets.append((ready_addresses, [port], "Ready", StatusGroup.OK))
                if not_ready_addresses:
                    subsets.append((not_ready_addresses, [port], "Not Ready", StatusGroup.NOT_OK))
        elif expand_subsets == "Address":
            for address in ready_addresses:
                subsets.append(([address], ports, "Ready", StatusGroup.OK))
            for address in not_ready_addresses:
                subsets.append(([address], ports, "Not Ready", StatusGroup.NOT_OK))
        elif expand_subsets == "Both":
            for port in ports:
                for address in ready_addresses:
                    subsets.append(([address], [port], "Ready", StatusGroup.OK))
                for address in not_ready_addresses:
                    subsets.append(([address], [port], "Not Ready", StatusGroup.NOT_OK))
        else:  # pragma: nocover
            raise ProgrammingError("get_subsets_info() got expand_subsets={expand_subsets}; "
                                   "this shouldn't be possible")

    for addresses, ports, status, status_group in subsets:
        subsets_.append(type("InfoClass", (), {
            "addresses": addresses,
            "ports": ports,
            "status": status,
            "status_group": status_group,
        }))
    return subsets_


# pylint: disable-next=unused-argument
def get_themearrays(obj: dict, **kwargs: Any) -> dict:
    """
    This is effectively a noop, but we need to have an infogetter.

        Parameters:
            obj (dict): The themearrays object
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (dict): The themearrays
    """
    return obj


# pylint: disable-next=unused-argument,too-many-locals
def get_traceflow(obj: dict, **kwargs: Any) -> \
        tuple[list[datetime], list[Union[str, tuple[str, str]]], list[LogLevel],
              list[Union[list[Union[ThemeRef, ThemeStr]], str]]]:
    """
    Extract log entries from a traceflow.

        Parameters:
            obj (dict): The object to extract log entries from
            **kwargs (dict[str, Any]): Keyword arguments
        Returns:
            (([datetime], [str], [str], [str])):
                ([str]): A list of timestamps
                ([str|(str, str)]): A list of facilities
                ([str]): A list of severities
                ([ThemeArray]|str): A list of ThemeArrays
    """
    timestamps: list[datetime] = []
    facilities: list[Union[str, tuple[str, str]]] = []
    severities: list[LogLevel] = []
    messages: list[Union[list[Union[ThemeRef, ThemeStr]], str]] = []

    for result in deep_get(obj, DictPath("status#results"), []):
        node = deep_get(result, DictPath("node"), "<unset>")
        nodestr_len = len(node) + themearray_len([ThemeRef("separators", "facility_prefix"),
                                                  ThemeRef("separators", "facility_suffix"),
                                                  ThemeRef("separators", "facility_padding")])
        tmp_timestamp = deep_get(result, DictPath("timestamp"), -1)
        if tmp_timestamp >= 0:
            saved_timestamp = datetime.fromtimestamp(tmp_timestamp)
        else:
            saved_timestamp = none_timestamp()
        message: list[Union[ThemeRef, ThemeStr]] = []
        for observation in deep_get(result, DictPath("observations"), []):
            facility = node
            timestamp = saved_timestamp
            for key, value in sorted(observation.items()):
                facilities.append(facility)
                timestamps.append(timestamp.astimezone())
                message = []
                if not facility and node:
                    message.append(ThemeStr("".ljust(nodestr_len), ThemeAttr("main", "default")))
                message += [
                    ThemeStr(key, ThemeAttr("types", "yaml_key")),
                    ThemeRef("separators", "yaml_key_separator"),
                    ThemeRef("separators", "space"),
                    ThemeStr(value, ThemeAttr("types", "yaml_value")),
                ]
                messages.append(message)
                facility = ""
                timestamp = none_timestamp()

    return timestamps, facilities, severities, messages


# pylint: disable-next=too-many-locals,too-many-branches
def get_journalctl_log(obj: dict, **kwargs: Any) -> \
        tuple[list[datetime], list[Union[str, tuple[str, str]]], list[LogLevel],
              list[Union[list[Union[ThemeRef, ThemeStr]], str]]]:
    """
    Extract log entries from journalctl.

        Parameters:
            obj (dict): The object to extract log entries from
            **kwargs (dict[str, Any]): Keyword arguments
                _show_raw (bool): Return unformatted entries?
        Returns:
            (([datetime], [str], [LogLevel], [ThemeRef|ThemeStr])):
                ([datetime]): A list of timestamps
                ([str|(str, str)]): A list of facilities
                ([LogLevel]): A list of severities
                ([[ThemeRef|ThemeStr]|str]): A list of messages
    """
    timestamps: list[datetime] = []
    facilities: list[Union[str, tuple[str, str]]] = []
    severities: list[LogLevel] = []
    messages: list[Union[list[Union[ThemeRef, ThemeStr]], str]] = []

    show_raw: bool = deep_get(kwargs, DictPath("_show_raw"), False)
    objlist = deep_get(obj, DictPath("obj"))
    parser = deep_get(objlist[0], DictPath("parser"))

    for line in objlist[1:]:
        try:
            d = json.loads(line)
        except DecodeException:
            d = {}

        timestamp = \
            datetime.fromtimestamp(int(deep_get(d, DictPath("__REALTIME_TIMESTAMP")), 0) / 1000000)
        severity = LogLevel.DEFAULT
        facility = ""
        remnants = None
        msg = ""

        raw_severity = int(deep_get(d, DictPath("PRIORITY"), "6"))
        raw_msg = deep_get(d, DictPath("MESSAGE"), "")

        if show_raw:
            msg = raw_msg
        elif parser == "glog":
            msg, severity, facility, remnants, matched = \
                logparsers.split_glog(raw_msg, severity=raw_severity)

            if not matched:
                severity = raw_severity
                remnants = None
                msg = raw_msg
        elif "=" in raw_msg and parser == "key_value":
            facility, severity, msg, remnants = \
                logparsers.key_value(raw_msg, severity=raw_severity, fold_msg=False)
        else:
            severity = raw_severity
            msg = raw_msg

        timestamps.append(timestamp.astimezone())
        facilities.append(facility)
        if severity == LogLevel.DEFAULT:
            severity = raw_severity
        severities.append(severity)
        messages.append(msg)

        if remnants is not None:
            if isinstance(remnants, tuple):
                fmt_remnants, remnant_severity = remnants

                for remnant in fmt_remnants:
                    timestamps.append(none_timestamp())
                    facilities.append("")
                    severities.append(remnant_severity)
                    messages.append(remnant)
            else:
                for remnant, remnant_severity in remnants:
                    timestamps.append(none_timestamp())
                    facilities.append("")
                    severities.append(remnant_severity)
                    messages.append(remnant)

    return timestamps, facilities, severities, messages


# pylint: disable-next=unused-argument
def get_task_log(obj: dict, **kwargs: Any) -> list[list[Union[ThemeRef, ThemeStr]]]:
    """
    Get logs from Ansible tasks.

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments
                log#skipped (bool): Was the log task skipped? True if the task was skipped
                log#stdout_lines (list[str]): Output to stdout
                log#stderr_lines (list[str]): Output to stderr
                log#msg_lines (list[str]): Merged output
        Returns:
            ([[ThemeRef|ThemeStr]]): A list of messages
    """
    field: list = []

    skipped = deep_get(obj, DictPath("log#skipped"), False)
    stdout_lines = deep_get(obj, DictPath("log#stdout_lines"), [])
    stderr_lines = deep_get(obj, DictPath("log#stderr_lines"), [])
    msg_lines = deep_get(obj, DictPath("log#msg_lines"), [])

    if skipped:
        field.append([ThemeStr("[skipped]", ThemeAttr("types", "unset"))])
        return field

    if stderr_lines:
        field.append([ThemeStr("stderr:", ThemeAttr("main", "paragraphheader"))])
        for line in stderr_lines:
            field.append([ThemeStr(f"{line}", color_status_group(StatusGroup.NOT_OK))])

    if stdout_lines:
        if field:
            field.append([ThemeStr("", ThemeAttr("main", "default"))])
        field.append([ThemeStr("stdout:", ThemeAttr("main", "paragraphheader"))])
        for line in stdout_lines:
            field.append([ThemeStr(f"{line}", ThemeAttr("main", "default"))])

    if msg_lines:
        if field:
            field.append([ThemeStr("", ThemeAttr("main", "default"))])
            field.append([ThemeStr("", ThemeAttr("main", "default"))])
        field.append([ThemeStr("msg:", ThemeAttr("main", "paragraphheader"))])
        for line in msg_lines:
            field.append([ThemeStr(f"{line}", color_status_group(StatusGroup.OK))])

    return field


def logpad_files(obj: dict, **kwargs: Any) -> list[list[Union[ThemeRef, ThemeStr]]]:
    """
    A wrapper around listgetter_files() to use it as an infogetter.

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments
                _pass_obj (bool): Should the object be passed to listgetter_files()?
                _show_raw (bool): Return unformatted entries?
                _extra_data#formatter (str): The formatter to use on the data
                _extra_data#formatter_args (dict): Arguments to pass to the formatter
                extra_values_lookup (dict): name/path to extra values to populate kwargs with
                                            from the object before passing it to listgetter_files()
    """
    # This is essentially just a wrapper around listgetter_files
    show_raw: bool = deep_get(kwargs, DictPath("_show_raw"), False)
    extra_values_lookup = deep_get(kwargs, DictPath("extra_values_lookup"), {})
    if (formatter := deep_get(obj, DictPath("_extra_data#formatter"))) is None:
        formatter = deep_get(kwargs, DictPath("formatter"), "none")

    for key, path in extra_values_lookup.items():
        if "extra_values" not in kwargs:
            kwargs["extra_values"] = {}
        kwargs["extra_values"][key] = deep_get_with_fallback(obj, path, "")
    if "_pass_obj" in kwargs:
        kwargs["_obj"] = obj

    kwargs.pop("extra_values_lookup", "")

    vlist, status = listgetters.listgetter_files(**kwargs)

    if status != "OK":
        return []

    if (formatter_args := deep_get(obj, DictPath("_extra_data#formatter_args"))) is None:
        formatter_args = deep_get(kwargs, DictPath("formatter_args"), {})

    if not show_raw and formatter == "markdown":
        return formatters.format_markdown(cast(str, vlist[0]), **formatter_args)
    return formatters.format_none(cast(str, vlist[0]), **formatter_args)


def logpad_formatted(obj: dict, **kwargs: Any) -> list[list[Union[ThemeRef, ThemeStr]]]:
    """
    Takes an object and dumps it using the specified format (if possible).

        Parameters:
            obj (dict): The dict to dump
            **kwargs (dict[str, Any]): Keyword arguments
                path (str): The path to get the data from
                formatter (str): The formatter to use for formatting the message
        Returns:
            ([[ThemeRef|ThemeStr]]): A list of messages
    """
    path: DictPath = DictPath(deep_get(kwargs, DictPath("path"), ""))
    dump_formatter_tmp = deep_get(kwargs, DictPath("formatter"), "format_none")
    dump_formatter = deep_get(formatter_allowlist, DictPath(dump_formatter_tmp))
    if dump_formatter is None:
        raise ValueError(f"{dump_formatter_tmp} is not a valid formatter; "
                         "the view-file is probably incorrect.")

    return dump_formatter(deep_get(obj, path, ""))


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def get_cmt_log(obj: dict, **kwargs: Any) -> \
        tuple[list[str], list[Union[str, tuple[str, str]]], list[LogLevel],
              list[Union[list[Union[ThemeRef, ThemeStr]], str]]]:
    """
    Extract log entries from CMT log.

        Parameters:
            obj (dict): The object to extract log entries from
            **kwargs (dict[str, Any]): Keyword arguments
                severity_prefixes (str): Prefix every message with the severity;
                                         useful when using a limited terminal,
                                         for use with CVD, etc.
                filepath (str): The path to the file to read log messages from
        Returns:
            (([str], [str], [str], [str])):
                ([str]): A list of formatted timestamps
                ([str|(str, str)]): A list of facilities
                ([LogLevel]): A list of severities
                ([ThemeArray]): A list of ThemeArrays
    """
    filepath = deep_get(obj, DictPath("filepath"), "")
    severity_prefixes = deep_get(kwargs, DictPath("severity_prefixes"), False)
    timestamps: list[str] = []
    facilities: list[Union[str, tuple[str, str]]] = []
    severities: list[LogLevel] = []
    messages: list[Union[list[Union[ThemeRef, ThemeStr]], str]] = []

    d = []

    try:
        d = list(secure_read_yaml(filepath))
    except (FileNotFoundError, TypeError):
        pass

    if not d or not isinstance(d, list):
        return timestamps, facilities, severities, messages

    for message in d:
        timestamp = deep_get(message, DictPath("timestamp"), "")
        severitystr = deep_get(message, DictPath("severity"), "")
        severity = name_to_loglevel(severitystr)
        facility = deep_get(message, DictPath("facility"), "")
        file = deep_get(message, DictPath("file"), "")
        function = deep_get(message, DictPath("function"), "")
        lineno = deep_get(message, DictPath("lineno"), "")

        facilitystr = f"{file}:{lineno} [{function}()]"

        themestrings = True
        msgs = deep_get(message, DictPath("themearray"), [])
        if not msgs:
            themestrings = False
            msgs = deep_get(message, DictPath("strarray"), [])

        first = True

        d_timestamp = timestamp_to_datetime(timestamp)
        for msg in msgs:
            if first:
                timestamps.append(d_timestamp.astimezone())
                if facility:
                    facilities.append((facilitystr, facility))
                else:
                    facilities.append(facilitystr)
                first = False
            else:
                timestamps.append(none_timestamp())
                if facility:
                    facilities.append(("".ljust(len(facilitystr)), "".ljust(len(facility))))
                else:
                    facilities.append("".ljust(len(facilitystr)))
            severities.append(severity)

            reformatted_msg: list[Union[ThemeRef, ThemeStr]] = []
            for substring in msg:
                if themestrings:
                    # These log messages are in ANSIThemeStr format;
                    # hence we need to convert them to ThemeStrs.
                    # Luckily ANSIThemeStr has fewer formats
                    # than ThemeStr. We should probably have
                    # a cross-reference table in themes though.
                    string = deep_get(substring, DictPath("string"))
                    themeref = deep_get(substring, DictPath("themeref"))
                else:
                    string = substring
                    themeref = "default"
                fmt = None
                if themeref == "default":
                    # When prepending the severity in front of the message we do not need to
                    # highlight the text, otherwise we use the severity as highlight colour.
                    if severity_prefixes:
                        fmt = ThemeAttr("main", "default")
                    else:
                        themeref = severitystr.lower()
                elif themeref == "emphasis":
                    fmt = ThemeAttr("main", "highlight")
                elif themeref in ("path", "hostname", "programname", "errorvalue", "separator"):
                    fmt = ThemeAttr("types", themeref)
                elif themeref == "argument":
                    fmt = ThemeAttr("main", "infoheader")
                if themeref in ("debug", "info", "warning", "error", "critical"):
                    fmt = ThemeAttr("logview", f"severity_{themeref}")
                if fmt is None:
                    fmt = ThemeAttr("main", "default")
                reformatted_msg.append(ThemeStr(string, cast(ThemeAttr, fmt)))
            messages.append(reformatted_msg)

    return timestamps, facilities, severities, messages


def logpad_yaml(obj: dict, **kwargs: Any) -> list[list[Union[ThemeRef, ThemeStr]]]:
    """
    Takes an object and dumps it as formatted YAML.

        Parameters:
            obj (dict): The dict to dump formatted as YAML
            **kwargs (dict[str, Any]): Keyword arguments
        Returns:
            ([themearray]): A list of themearrays
    """
    path = deep_get(kwargs, DictPath("path"), "")
    messages: list = []

    try:
        if path:
            data = deep_get(obj, DictPath(path))
        else:
            data = obj
        if data is not None:
            tmp = yaml.dump(data, width=16384)
            messages = formatters.format_yaml(tmp, **kwargs)
    except yaml.YAMLError:
        pass

    return messages


def logpad_msg_getter(obj: dict, **kwargs: Any) -> list[list[Union[ThemeRef, ThemeStr]]]:
    """
    Get a string with embedded newlines, split it into a list of ThemeArrays.

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments
                path (str): Path to the string
        Returns:
            ([themearray]): A list of themearrays
    """
    messages: list[list[Union[ThemeRef, ThemeStr]]] = []

    path = deep_get(kwargs, DictPath("path"))
    tmp = deep_get(obj, DictPath(path), "")

    for line in split_msg(tmp):
        messages.append([ThemeStr(f"{line}", ThemeAttr("main", "default"))])

    return messages


# pylint: disable-next=unused-argument,too-many-locals
def get_log_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for logs.

        Parameters:
            **kwargs (dict): Additional parameters
        Returns:
            ([InfoClass]): A list with info
    """
    info: list[Type] = []

    # Fetch kubelet log, if available (for now only useful if run on the control plane)
    sudo_path: FilePath = secure_which(FilePath("sudo"),
                                       fallback_allowlist=["/bin", "/usr/bin"],
                                       security_policy=SecurityPolicy.ALLOWLIST_STRICT)
    journalctl_path: FilePath = secure_which(FilePath(os.path.join(BINDIR, "journalctl")),
                                             fallback_allowlist=["/bin", "/usr/bin"],
                                             security_policy=SecurityPolicy.ALLOWLIST_STRICT)
    args: list[str] = [sudo_path, journalctl_path, "--no-pager", "-o", "json"]

    logs: list[tuple[str, str, list[str], str]] = [
        ("Latest boot, last 1h", "[dmesg]",
         ["-k", "-b", "--since", "1 hour ago", "--lines", "10000"], "glog"),
        ("Latest 1000 lines", "[kubelet]",
         ["--lines", "1000", "-u", "kubelet"], "glog"),
        ("Latest 1000 lines", "[containerd]",
         ["--lines", "1000", "-u", "containerd"], "key_value"),
        ("Latest 1000 lines", "[cri-o]",
         ["--lines", "1000", "-u", "crio"], "key_value"),
    ]

    try:
        for name, action, log, parser in logs:
            response = execute_command_with_response(args + log)
            if not response:
                continue

            # The first entry in the obj list holds metadata;
            # the rest of the entries are strings
            split_response: list[Any] = [{
                # "parser": str
                # "name": str
                # "host": str
                # "created_at": datetime
                "parser": parser,
            }]
            split_response += response.splitlines()
            latestentry: str = cast(str, split_response[1])

            d = json.loads(latestentry)

            split_response[0]["name"] = deep_get(d, DictPath("SYSLOG_IDENTIFIER"), "<unknown>")
            hostname = deep_get(d, DictPath("_HOSTNAME"), "<unknown>")
            split_response[0]["host"] = hostname
            created_at = \
                datetime.fromtimestamp(int(deep_get(d, DictPath("__REALTIME_TIMESTAMP"))) / 1000000)
            split_response[0]["created_at"] = created_at

            info.append(type("InfoClass", (), {
                "name": f"<dynamic> {hostname}: {name}",
                "ref": {
                    "ref": split_response,
                    "kind": "__JournalctlLogView",
                },
                "action": action,
                "message": deep_get(d, DictPath("MESSAGE"), ""),
                "created_at": created_at,
                "log_type": "journalctl",
            }))
    except FileNotFoundError:
        pass

    # Get the list of available Ansible logs
    ansible_logs = ansible_get_logs()

    # TODO: Here we might possibly want to insert other logs?

    for name, action, ref, created_at in ansible_logs:
        log_type = "Ansible Play"
        info.append(type("InfoClass", (), {
            "name": name,
            "ref": {
                "ref": ref,
                "kind": "__AnsibleLog",
            },
            "action": action,
            "created_at": created_at,
            "log_type": log_type,
        }))
    return info


# We should probably have a real type for container_type here
def __get_container_info(obj: dict, container_type: str,
                         spec_path: DictPath, status_path: DictPath) -> dict:
    containers: dict = {}

    for container in deep_get(obj, spec_path, []):
        container_name = deep_get(container, DictPath("name"))
        container_image = deep_get(container, DictPath("image"))
        image_version = get_image_version(container_image)

        # To get the image ID we need to cross-reference container_image
        # against status#{status_path}->image"
        image_id = None
        for item in deep_get(obj, status_path, []):
            if deep_get(item, DictPath("name"), "") == container_name:
                image_id = deep_get(item, DictPath("imageID"))
        # This (most likely) means that the pod has not managed to instantiate a container
        if image_id is None:
            image_id = "<unknown>"
        key = (container_name, container_type, image_version, image_id)

        # If this container is in the dict already, just add a pod reference
        # This is unlikely to ever happen (this would mean that the same pod
        # uses the same image multiple times which seems unlikely), but better safe than sorry
        if key not in containers:
            containers[key] = {}
            containers[key]["pod_references"] = []
            containers[key]["instances"] = 0

        containers[key]["pod_references"].append(obj)
        containers[key]["instances"] += 1

    return containers


# pylint: disable-next=too-many-locals
def get_container_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for containers.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
        Returns:
            ([InfoClass]): A list with info
    """
    if (kh_ := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("get_container_info() called without kubernetes_helper")
    kh_cache_: Optional[KubernetesResourceCache] = deep_get(kwargs, DictPath("kh_cache"))

    info: list[Type] = []
    containers: dict = {}

    # There's no direct way to get a list of unique containers
    # as defined by the tuple (name, type, version, image_id),
    # so we need to iterate the list of all pods and extract this
    # information.
    vlist, status = kh_.get_list_by_kind_namespace(("Pod", ""), "", resource_cache=kh_cache_)
    if status != 200:
        return info

    for obj in vlist:
        tmp = __get_container_info(obj, "InitContainer",
                                   DictPath("spec#initContainers"),
                                   DictPath("status#initContainerStatuses"))
        for key, value in tmp.items():
            instances = value["instances"]
            pod_references = value["pod_references"]
            if key not in containers:
                containers[key] = {}
                containers[key]["instances"] = 0
                containers[key]["pod_references"] = []

            containers[key]["instances"] += instances
            containers[key]["pod_references"] += pod_references
        tmp = __get_container_info(obj, "Container",
                                   DictPath("spec#containers"),
                                   DictPath("status#containerStatuses"))
        for key, value in tmp.items():
            instances = value["instances"]
            pod_references = value["pod_references"]
            if key not in containers:
                containers[key] = {}
                containers[key]["instances"] = 0
                containers[key]["pod_references"] = []

            containers[key]["instances"] += instances
            containers[key]["pod_references"] += pod_references

    for name, container_type, image_version, image_id in containers:
        pod_references = containers[(name, container_type,
                                     image_version, image_id)]["pod_references"]
        pods = []
        for pod in pod_references:
            pods.append((deep_get(pod, DictPath("metadata#namespace")),
                         deep_get(pod, DictPath("metadata#name"))))
        instances = containers[(name, container_type, image_version, image_id)]["instances"]
        info.append(type("InfoClass", (), {
            "name": name,
            # This replaces ref
            "ref": {
                "name": name,
                "container_type": container_type,
                "image_version": image_version,
                "image_id": image_id,
                "pod_references": pod_references,
            },
            "container_type": container_type,
            "image_version": image_version,
            "instances": instances,
            "image_id": image_id,
            "pods": pods,
            "pod_references": pod_references,
        }))
    return info


# Infogetters acceptable for direct use in view files
infogetter_allowlist: dict[str, Callable] = {
    # Used by listview, infopad, and listpad
    "generic_infogetter": generic_infogetter,
    # Used by listview
    "get_container_info": get_container_info,
    "get_log_info": get_log_info,
    # Used by listpad
    "get_auth_rule_info": get_auth_rule_info,
    "get_eps_subsets_info": get_eps_subsets_info,
    "get_key_value_info": get_key_value_info,
    "get_limit_info": get_limit_info,
    "get_promrules_info": get_promrules_info,
    "get_rq_item_info": get_rq_item_info,
    "get_sas_info": get_sas_info,
    "get_strategy_info": get_strategy_info,
    "get_subsets_info": get_subsets_info,
    # Used by logpad
    "logpad_formatted": logpad_formatted,
    # XXX: We should aim to replace this with logpad_formatted
    "logpad_msg_getter": logpad_msg_getter,
    # XXX: We should aim to replace this with logpad_formatted
    "logpad_yaml": logpad_yaml,
    "logpad_files": logpad_files,
    "get_journalctl_log": get_journalctl_log,
    "get_task_log": get_task_log,
    "get_cmt_log": get_cmt_log,
    "get_themearrays": get_themearrays,
    "get_traceflow": get_traceflow,
}
