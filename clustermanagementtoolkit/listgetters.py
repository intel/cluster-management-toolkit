#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

# pylint: disable=too-many-lines

"""
Get list data synchronously.
"""

import concurrent.futures
import copy
import csv
from datetime import datetime
from itertools import zip_longest
try:
    import ujson as json
    # The exception raised by ujson when parsing fails is different
    # from what json raises
    DecodeException = ValueError
except ModuleNotFoundError:
    import json  # type: ignore
    DecodeException = json.decoder.JSONDecodeError  # type: ignore
from operator import itemgetter
import os
from pathlib import Path
import re
import sys
from typing import Any, cast, Union
from collections.abc import Callable

try:
    from natsort import natsorted
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import natsort; "
             "you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

from clustermanagementtoolkit.cmtpaths import HOMEDIR

from clustermanagementtoolkit.cmtio import secure_read_string

from clustermanagementtoolkit.cmtio_yaml import secure_read_yaml

from clustermanagementtoolkit import cmtlib
from clustermanagementtoolkit.cmtlib import disksize_to_human, get_since
from clustermanagementtoolkit.cmtlib import timestamp_to_datetime
from clustermanagementtoolkit.cmtlib import make_label_selector, make_set_expression_list

from clustermanagementtoolkit.cmttypes import deep_get, deep_get_with_fallback, deep_set, DictPath
from clustermanagementtoolkit.cmttypes import FilePath, FilePathAuditError
from clustermanagementtoolkit.cmttypes import ProgrammingError, StatusGroup

from clustermanagementtoolkit.datagetters import get_container_status

from clustermanagementtoolkit import formatters

from clustermanagementtoolkit.kubernetes_helper import get_node_status
from clustermanagementtoolkit.kubernetes_helper import resource_kind_to_rtype

from clustermanagementtoolkit import listgetters_async


def check_matchlists(item: str,
                     exacts: tuple[str, ...], prefixes: tuple[str, ...],
                     suffixes: tuple[str, ...], ins: tuple[str, ...]) -> bool:
    """
    Check whether a string has a match in a set of matchlists.

        Parameters:
            item (str): The item to match against the matchlists
            exacts ((str, ...)): A tuple of exact matches
            prefixes ((str, ...)): A tuple of prefix matches
            suffixes ((str, ...)): A tuple of suffix matches
            ins ((str, ...)): A tuple of infix matches
        Returns:
            (bool): True if the item matches any of the match items
    """
    if item in exacts:
        return True
    for in_ in ins:
        if in_ in item:
            return True
    if prefixes and item.startswith(prefixes) or suffixes and item.endswith(suffixes):
        return True
    return False


# Takes an unprocessed matchlist, splits it into individual matchlists, and checks for matches
def check_matchlist(item: str, matchlist: list[str]) -> bool:
    """
    Given a string and a list of match items, check whether the string matches
    any of the match items.

        Parameters:
            matchlist ([str]): A list of strings to match against
        Returns:
            (bool): True if the item matches any of the match items
    """
    exacts, prefixes, suffixes, ins = split_matchlist(matchlist)
    return check_matchlists(item, exacts=exacts, prefixes=prefixes, suffixes=suffixes, ins=ins)


def get_device_model(obj: dict, device: DictPath) -> str:
    """
    Return the device model for a partition.

        Parameters:
            obj (dict): The object to extract device model information from
            device (DictPath): The device to extract model information for
        Returns:
            (str): The device model
    """
    for dev in deep_get(obj, DictPath("ansible_devices"), {}):
        partitions = deep_get(obj, DictPath(f"ansible_devices#{dev}#partitions"), {})
        model = deep_get(obj, DictPath(f"ansible_devices#{dev}#model"), "")
        for partition in partitions:
            if device in partition:
                return model
    return ""


def split_matchlist(matchlist: list[str]) -> tuple[tuple[str, ...], tuple[str, ...],
                                                   tuple[str, ...], tuple[str, ...]]:
    """
    Takes a list and splits it into four types of match lists:
    exact matches (for entries in the matchlist that doesn't start or end with *)
    prefixes (for entries in the matchlist that start with *)
    suffixes (for entries in the matchlist that end with *)
    ins (for entries in the matchlist that start and end with *).

        Parameters:
            matchlist ([str]): A list of strings to match against
        Returns:
            (((str, ...), (str, ...), (str, ...), (str, ...))):
                ((str, ...)): Strings to match with ==
                ((str, ...)): Strings to match with .startswith()
                ((str, ...)): Strings to match with .endswith()
                ((str, ...)): Strings to match with in
    """
    exacts: list[str] = []
    prefixes: list[str] = []
    suffixes: list[str] = []
    ins: list[str] = []

    for item in matchlist:
        if item.startswith("*") and item.endswith("*"):
            ins.append(item[1:-1])
        elif item.endswith("*"):
            prefixes.append(item[:-1])
        elif item.startswith("*"):
            suffixes.append(item[1:])
        else:
            exacts.append(item)
    return tuple(exacts), tuple(prefixes), tuple(suffixes), tuple(ins)


# Returns True if the item should be skipped
# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def filter_list_entry(obj: dict[str, Any], caller_obj: dict[str, Any], filters: dict) -> bool:
    """
    Filter an object based on a set of rules and return whether the object should be skipped
    Usage is typically to pass in an object from a listgetter (hence the name)
    and filter it against data in the referenced object.

        Parameters:
            obj (dict): The primary dict
            caller_obj (dict): The secondary dict
            filters (dict): The filters to apply
        Returns:
            (bool): True to deny the entry, False to allow the entry
    """
    skip: bool = False

    # pylint: disable-next=too-many-nested-blocks
    for f in filters:
        if not deep_get(filters[f], DictPath("enabled"), True):
            continue

        # If len(allow) > 0, we only allow fields that match
        allow = deep_get(filters[f], DictPath("allow"), [])
        # If len(block) > 0, we skip fields that match
        block = deep_get(filters[f], DictPath("block"), [])
        if allow:
            # If all field + value pairs match we allow
            for rule in allow:
                rtype = deep_get(rule, DictPath("type"), "")
                if rtype == "":
                    key = deep_get(rule, DictPath("key"), "")
                    values = deep_get(rule, DictPath("values"), [])
                    substitutions = {}
                    for subst, subst_with in deep_get(rule, DictPath("substitutions"), {}).items():
                        if isinstance(subst_with, list):
                            subst_with = deep_get_with_fallback(caller_obj, subst_with)
                        substitutions[subst] = subst_with
                    key = cmtlib.substitute_string(key, substitutions)
                    if deep_get(rule, DictPath("values#source"), "object") == "caller":
                        src = caller_obj
                    else:
                        src = obj
                    if deep_get(rule, DictPath("exists"), False) and deep_get(src, DictPath(key)):
                        continue
                    if isinstance(values, dict):
                        values_path = deep_get(rule, DictPath("values#path"), "")
                        values = deep_get(src, DictPath(values_path), [])
                        if isinstance(values, str):
                            values = [values]

                    _listref = deep_get(rule, DictPath("list"))
                    if _listref is not None:
                        _list = deep_get(obj, DictPath(_listref), [])
                        for _item in _list:
                            if deep_get(_item, DictPath(key), "").rstrip() in values:
                                break
                        else:
                            skip = True
                            break
                    elif deep_get(obj, DictPath(key), "").rstrip() not in values:
                        skip = True
                        break
                elif rtype == "dictlist":
                    path = deep_get(rule, DictPath("path"), "")
                    target_dict = deep_get(obj, DictPath(path), {})
                    matched = False
                    for _dict in target_dict:
                        for key, value in deep_get(rule, DictPath("fields"), {}).items():
                            if isinstance(value, dict):
                                if deep_get(value, DictPath("source"), "object") == "caller":
                                    src = caller_obj
                                else:
                                    src = target_dict
                                value_path = deep_get(value, DictPath("path"), "")
                                if value_path:
                                    value = deep_get(src, DictPath(value_path))
                            if key == "api_family":
                                target_value = deep_get(_dict, DictPath("apiVersion"))
                                if "/" in target_value:
                                    target_value = target_value.split("/", 1)[0]
                                else:
                                    target_value = ""
                            else:
                                target_value = deep_get(_dict, DictPath(key))
                            # pylint: disable-next=unidiomatic-typecheck
                            if type(value) == type(target_value) \
                                    and value == target_value:  # noqa: E721
                                matched = True
                            else:
                                # This particular dict did not fully match
                                matched = False
                                break
                        if matched:
                            break
                    if not matched:
                        skip = True
                        break
                else:
                    sys.exit(f"filter: unknown rule-type: {rtype}")

        if block:
            # If all field + value pairs match we block
            for rule in block:
                key = deep_get(rule, DictPath("key"), "")
                values = deep_get(rule, DictPath("values"), [])
                if isinstance(values, dict):
                    if deep_get(rule, DictPath("values#source"), "object") == "caller":
                        src = caller_obj
                    else:
                        src = obj
                    values_path = deep_get(rule, DictPath("values#path"), "")
                    values = deep_get(src, DictPath(values_path), [])
                    if isinstance(values, str):
                        values = [values]
                if deep_get(obj, DictPath(key), "").rstrip() in values:
                    skip = True
                    break
        if skip:
            break
    return skip


# listview, listpad
def generic_listgetter(kind: tuple[str, str], namespace: str,
                       **kwargs: Any) -> tuple[list[dict[str, Any]], Union[int, str]]:
    """
    Fetch data from Kubernetes.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
                label_selector (str): A comma-separated string with a list of label selectors
                field_selector (str): A comma-separated string with a list of field selectors
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list of Kubernetes objects
                (int): The status for the Kubernetes request
        Raises:
            ProgrammingError: Function called without kubernetes_helper
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError(f"{__name__}() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    label_selector = deep_get(kwargs, DictPath("label_selector"), "")
    field_selector = deep_get(kwargs, DictPath("field_selector"), "")
    filters = deep_get(kwargs, DictPath("filters"), [])
    vlist, status = kh.get_list_by_kind_namespace(kind, namespace, label_selector=label_selector,
                                                  field_selector=field_selector,
                                                  resource_cache=kh_cache)
    if not vlist or status != 200 or not filters:
        return vlist, status

    vlist2 = []

    for item in vlist:
        if filter_list_entry(item, deep_get(kwargs, DictPath("_obj"), {}), filters):
            continue
        vlist2.append(item)

    return vlist2, status


# pylint: disable-next=too-many-locals
def get_metrics_list(**kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Get a list of Kubernetes metrics.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list of metrics
                (int): The status for the Kubernetes request
        Raises:
            ProgrammingError: Function called without kubernetes_helper
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError(f"{__name__}() called without kubernetes_helper")

    filters: list[str] = deep_get(kwargs, DictPath("filter"), [])

    vlist: list[dict[str, Any]] = []

    metrics, status = kh.get_metrics()

    # metrics are on the form:
    # apiserver_audit_event_total 0
    # aggregator_openapi_v2_regeneration_count{apiservice="*",reason="startup"} 0
    # apiserver_requested_deprecated_apis{group="autoscaling",removed_release="1.25",
    # resource="horizontalpodautoscalers",subresource="",version="v2beta1"} 1

    metrics_regex = re.compile(r"^([^{]*){([^}]*)}\s\d+$")

    metric_set = set()
    for line in metrics:
        if (tmp := metrics_regex.match(line)) is None:
            continue
        metric = tmp[1]
        metric_set.add(metric)

        if filters is not None and metric not in filters:
            continue

        fields = [f"{x}" for x in next(csv.reader([tmp[2]], delimiter=",", quotechar="\""))]
        if not fields:
            continue
        d: dict[str, Any] = {
            "name": metric,
            "fields": {},
        }
        for field in fields:
            key_value = [f"{x}" for x in next(csv.reader([field], delimiter="=", quotechar="\""))]
            key, value = key_value
            d["fields"][key] = value.strip("\"")

        vlist.append(d)

    return vlist, status


# pylint: disable-next=too-many-locals
def get_pod_containers_list(**kwargs: Any) -> tuple[list[dict[str, Any]], Union[int, str]]:
    """
    Get a list of all pods with a separate entry for every container.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list of Kubernetes objects
                (int): The status for the Kubernetes request
        Raises:
            ProgrammingError: Function called without kubernetes_helper
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError(f"{__name__}() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    vlist: list[dict[str, Any]] = []
    _vlist, status = kh.get_list_by_kind_namespace(("Pod", ""), "", resource_cache=kh_cache)

    if status == 200:
        for obj in _vlist:
            namespace = deep_get(obj, DictPath("metadata#namespace"))
            name = deep_get(obj, DictPath("metadata#name"))
            node_name = deep_get(obj, DictPath("spec#nodeName"))
            for container in deep_get(obj, DictPath("spec#containers")):
                container_name = deep_get(container, DictPath("name"))
                reason, status_group, _restarts, _message, _age = \
                    get_container_status(deep_get(obj, DictPath("status#containerStatuses")),
                                         container_name)
                container_status = None
                for container_status in deep_get(obj, DictPath("status#containerStatuses"), []):
                    if deep_get(container_status, DictPath("name")) == container_name:
                        break
                if container_status is not None:
                    image_id = deep_get(container_status, DictPath("imageID"), "")
                else:
                    image_id = "<unavailable>"
                vlist.append({
                    "namespace": namespace,
                    "name": name,
                    "container": container_name,
                    "status": reason,
                    "status_group": status_group,
                    "node_name": node_name,
                    "image_id": image_id,
                })

    return vlist, status


def __recurse_data(path: dict, obj: Any) -> Any:
    datapath = deep_get(path, DictPath("path"), "")
    pathtype = deep_get(path, DictPath("pathtype"), "raw")
    nextpath = deep_get(path, DictPath("data"), {})

    if pathtype == "raw":
        return obj
    if pathtype == "list":
        if obj is None or len(obj) < datapath:
            return obj
        data = obj[datapath]
    else:
        data = deep_get(obj, datapath)

    if not nextpath:
        return data

    return __recurse_data(nextpath, data)


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def listgetter_files(**kwargs: Any) -> tuple[list[Union[str, dict[str, Any]]],
                                             Union[int, str, None]]:
    """
    Custom listgetter mainly for use with the version data checker.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
        Returns:
            (([dict[str, Any]], int)):
                ([str|dict[str, Any]]): The list of Kubernetes objects
                (int): The status for the Kubernetes request
    """
    paths = \
        deep_get_with_fallback(kwargs,
                               [DictPath("paths"),
                                DictPath("extra_values#_extra_data#paths")], [],
                               fallback_on_empty=True)
    file_not_found_status = \
        deep_get_with_fallback(kwargs,
                               [DictPath("file_not_found_status"),
                                DictPath("extra_values#_extra_data#file_not_found_status")],
                               "File not found", fallback_on_empty=True)
    skip_empty_paths = deep_get(kwargs, DictPath("skip_empty_paths"), False)
    vlist: list[Union[str, dict[str, Any]]] = []
    status = None

    for path in paths:
        filepath = deep_get(path, DictPath("filepath"), "")
        if "_obj" in kwargs:
            for substkey, substpath in deep_get(path, DictPath("substitutions"), {}).items():
                substval = deep_get(kwargs, DictPath(f"_obj#{substpath}"), "")
                filepath = filepath.replace(f"<<<{substkey}>>>", substval)
        filetype = deep_get(path, DictPath("filetype"), "text")
        matchtype = deep_get(path, DictPath("data#matchtype"), "all")
        regex = deep_get(path, DictPath("data#regex"))
        key = deep_get(path, DictPath("data#key"))

        # Substitute {HOME}/ for {HOMEDIR}
        if filepath.startswith(("{HOME}/", "{HOME}\\")):
            filepath = HOMEDIR.joinpath(filepath[len('{HOME}/'):])

        d: Any = ""

        try:
            if filetype == "yaml":
                try:
                    d = dict(secure_read_yaml(filepath))
                except TypeError:
                    d = {}
            else:
                d = secure_read_string(filepath)
        except FilePathAuditError as e:
            if "SecurityStatus.PARENT_DOES_NOT_EXIST" in str(e) \
                    or "SecurityStatus.DOES_NOT_EXIST" in str(e):
                if status is None:
                    status = file_not_found_status
                continue
            raise

        if not d:
            continue

        # We've successfully read data at least once
        status = "OK"

        # Get the mtime of the file
        p = Path(FilePath(filepath))
        mtime = p.stat().st_mtime

        item: dict[str, Any] = {key: []}
        # pylint: disable-next=too-many-nested-blocks
        if filetype == "text":
            if regex:
                match = False
                for line in d.splitlines():
                    if (tmp := re.match(regex, line)):
                        for group in tmp.groups():
                            if group:
                                item[key].append(group)
                        match = True
                        if matchtype == "first":
                            if len(item[key]) == 1:
                                item[key] = item[key][0]
                            break
                if not match:
                    continue
            else:
                item = d
        else:
            item = __recurse_data(path, d)
        if (item is None or not item) and skip_empty_paths:
            continue
        extra_data = deep_get(path, DictPath("_extra_data"), {})
        extra_data["mtime"] = mtime

        if extra_data and isinstance(item, dict):
            item = {**item, "_extra_data": extra_data}

        vlist.append(item)

    return vlist, status


def listgetter_dir(**kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Get a list of directory entries. If prefixes and/or suffixes are set,
    any entries not matching the prefixes/suffixes will be skipped.

        Parameters:
            dirpath (str): The path to get the directory entries from
            prefixes ([str]): A list of accepted prefixes
            suffixes ([str]): A list of accepted suffixes
            types ([str]): A list of entry types to include; if empty all types will
                           be included; currently supported filters are [file, dir]
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The directory entries
                (int): The status for the request
    """
    status: int = 200

    dirpath = deep_get(kwargs, DictPath("dirpath"), "")
    types = deep_get(kwargs, DictPath("types"), [])
    # Substitute {HOME} for {HOMEDIR}
    if dirpath.startswith("{HOME}"):
        dirpath = dirpath.replace("{HOME}", HOMEDIR, 1)
    prefixes: list[str] = deep_get(kwargs, DictPath("prefixes"), [])
    suffixes: list[str] = deep_get(kwargs, DictPath("suffixes"), [])
    kind = deep_get(kwargs, DictPath("kind"))

    vlist: list[dict[str, Any]] = []

    if os.path.isdir(dirpath):
        for filename in os.listdir(dirpath):
            if prefixes and not filename.startswith(tuple(prefixes)):
                continue
            if suffixes and not filename.endswith(tuple(suffixes)):
                continue
            if types:
                if os.path.isfile(filename):
                    if "file" not in types:
                        continue
                elif os.path.isdir(filename):
                    if "dir" not in types:
                        continue
                else:
                    # We don't support other types in the filter
                    continue

            filepath: FilePath = FilePath(dirpath).joinpath(filename)
            filepath_entry: Path = Path(filepath)
            fstat: os.stat_result = filepath_entry.stat()
            mtime: datetime = datetime.fromtimestamp(fstat.st_mtime)
            ctime: datetime = datetime.fromtimestamp(fstat.st_ctime)
            filesize: str = disksize_to_human(fstat.st_size)

            vlist.append({
                "name": filename,
                "mtime": mtime,
                "ctime": ctime,
                "filesize": filesize,
                "ref": {
                    "name": filename,
                    "filepath": FilePath(filepath),
                    "filesize": filesize,
                    "mtime": mtime,
                    "ctime": ctime,
                },
                "kind": kind,
            })

    return vlist, status

# Used by listpad


# pylint: disable-next=unused-argument,too-many-locals
def get_hpa_metrics(obj: dict, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Get horizontal pod autoscaler metrics.

        Parameters:
            obj (dict): The object to extract data from
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The metrics
                (int): The status for the request
    """
    vlist: list[dict[str, Any]] = []
    status: int = 200

    for metric in deep_get(obj, DictPath("spec#metrics"), []):
        if "type" not in metric:
            continue
        metric_type = deep_get(metric, DictPath("type"))
        metric_name = metric_type[0].lower() + metric_type[1:]
        target_type = deep_get(metric, DictPath(f"{metric_name}#target#type"), "")
        if target_type == "Utilization":
            target_type = "AverageUtilization"
        target_type_name = target_type[0].lower() + target_type[1:]

        kind = ""
        name = ""
        api_group = ""
        object_name = ""

        if metric_name in ("resource", "containerResource"):
            name = deep_get(metric, DictPath(f"{metric_name}#name"))
        elif metric_name in ("pods", "object", "external"):
            name = deep_get(metric, DictPath(f"{metric_name}#metric#name"))
            api_version = ""
            if metric_type == "Object":
                kind = deep_get(metric, DictPath(f"{metric_name}#describedObject#kind"))
                api_version = \
                    deep_get(metric, DictPath(f"{metric_name}#describedObject#apiVersion"))
                object_name = deep_get(metric, DictPath(f"{metric_name}#describedObject#name"))
            api_group = api_version.split("/")[0]
        else:
            metric_type += " (Unsupported)"

        target_value = deep_get(metric, DictPath(f"{metric_name}#target#{target_type_name}"), "")
        selector = deep_get(metric, DictPath(f"{metric_name}#metric#selector#matchLabels"), {})

        d = {
            "metric_type": metric_type,
            "name": name,
            "target_type": target_type,
            "described_object_kind": kind,
            "described_object_api_group": api_group,
            # The autoscaler shares namespace with the described object
            "described_object_namespace": deep_get(obj, DictPath("metadata#namespace"), ""),
            "described_object_name": object_name,
            "selector": selector,
            "target_value": target_value,
        }
        vlist.append(d)
    return vlist, status


# pylint: disable-next=unused-argument
def get_ingress_rule_list(obj: dict, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Listgetter for Ingress rules.

        Parameters:
            obj (Dict): The object to extract ingress rule information from
            **kwargs (dict[str, Any]): Keyword arguments
        Returns:
            (([dict], int)):
                ([dict[str, Any]]): The ingress rules
                (int): The status for the request
    """
    vlist: list[dict[str, Any]] = []
    status: int = 200

    for item in deep_get(obj, DictPath("spec#rules"), []):
        host = deep_get(item, DictPath("host"), "*")

        if deep_get(item, DictPath("http")) is not None:
            for path in deep_get(item, DictPath("http#paths")):
                rpath = deep_get(path, DictPath("path"), "")
                path_type = deep_get(path, DictPath("pathType"), "")
                if "service" in deep_get(path, DictPath("backend"), {}):
                    backend_kind = ("Service", "")
                    name = deep_get(path, DictPath("backend#service#name"))
                    port = (deep_get(path, DictPath("backend#service#port#number"), ""),
                            deep_get(path, DictPath("backend#service#port#name"), ""))
                elif "resource" in deep_get(path, DictPath("backend"), {}):
                    backend_kind = (deep_get(path, DictPath("backend#resource#kind"), ""),
                                    deep_get(path, DictPath("backend#resource#apiGroup"), ""))
                    name = deep_get(path, DictPath("backend#resource#name"), "")
                    port = ("", "")
                # Old-style ingress rule
                else:
                    backend_kind = ("Service", "")
                    name = deep_get(path, DictPath("backend#serviceName"))
                    port = (deep_get(path, DictPath("backend#servicePort"), ""), "")

                vlist.append({
                    "host": host,
                    "path": rpath,
                    "path_type": path_type,
                    "backend_kind": backend_kind,
                    "name": name,
                    "port": port,
                })

    return vlist, status


# pylint: disable-next=unused-argument,too-many-locals
def get_netpol_rule_list(obj: dict, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Get a list of network policy rules.

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The network policy rules
                (int): The status for the request
    """
    vlist: list[dict[str, Any]] = []
    status: int = 200

    for item in deep_get(obj, DictPath("spec#ingress"), []):
        policy_type = "ingress"
        ports = []
        for port in deep_get(item, DictPath("ports"), []):
            ports.append((deep_get(port, DictPath("port"), ""),
                          deep_get(port, DictPath("protocol"), "")))
        pod_label_selector = deep_get(item, DictPath("podSelector#matchLabels"), {})
        namespace_label_selector = deep_get(item, DictPath("namespaceSelector#matchLabels"), {})
        # Specific to AdminNetworkPolicy
        action: str = deep_get(item, DictPath("action"), "")
        name: str = deep_get(item, DictPath("name"), "")

        from_rules = deep_get(item, DictPath("from"), [])

        for source in from_rules:
            ipblock = deep_get(source, DictPath("cidr"))
            ipblock_exceptions = deep_get(source, DictPath("except"))
            pods_pod_label_selector = \
                deep_get(source, DictPath("pods#podSelector#matchLabels"), pod_label_selector)
            pods_namespace_label_selector = \
                deep_get(source, DictPath("pods#namespaceSelector#matchLabels"),
                         namespace_label_selector)
            vlist.append({
                "policy_type": policy_type,
                "ipblock": ipblock,
                "ipblock_exceptions": ipblock_exceptions,
                "ports": ports,
                "pod_label_selector": pods_pod_label_selector,
                "namespace_label_selector": pods_namespace_label_selector,
                "action": action,
                "name": name,
            })

        if not from_rules:
            vlist.append({
                "policy_type": policy_type,
                "ipblock": "",
                "ipblock_exceptions": [],
                "ports": ports,
                "pod_label_selector": pod_label_selector,
                "namespace_label_selector": namespace_label_selector,
                "action": action,
                "name": name,
            })

    for item in deep_get(obj, DictPath("spec#egress"), []):
        policy_type = "egress"
        ports = []
        for port in deep_get(item, DictPath("ports"), []):
            ports.append((deep_get(port, DictPath("port"), ""),
                          deep_get(port, DictPath("protocol"), "")))
        pod_label_selector = deep_get(item, DictPath("podSelector#matchLabels"), {})
        namespace_label_selector = deep_get(item, DictPath("namespaceSelector#matchLabels"), {})
        # Specific to AdminNetworkPolicy
        action = deep_get(item, DictPath("action"), "")
        name = deep_get(item, DictPath("name"), "")

        to_rules = deep_get(item, DictPath("to"), [])

        for source in to_rules:
            ipblock = deep_get(source, DictPath("cidr"))
            ipblock_exceptions = deep_get(source, DictPath("except"))
            pods_pod_label_selector = \
                deep_get(source, DictPath("pods#podSelector#matchLabels"), pod_label_selector)
            pods_namespace_label_selector = \
                deep_get(source, DictPath("pods#namespaceSelector#matchLabels"),
                         namespace_label_selector)
            vlist.append({
                "policy_type": policy_type,
                "ipblock": ipblock,
                "ipblock_exceptions": ipblock_exceptions,
                "ports": ports,
                "pod_label_selector": pods_pod_label_selector,
                "namespace_label_selector": pods_namespace_label_selector,
                "action": action,
                "name": name,
            })

        if not to_rules:
            vlist.append({
                "policy_type": policy_type,
                "ipblock": "",
                "ipblock_exceptions": [],
                "ports": ports,
                "pod_label_selector": pod_label_selector,
                "namespace_label_selector": namespace_label_selector,
                "action": action,
                "name": name,
            })

    return vlist, status


def get_pv_from_pvc_name(pvc_name: str, **kwargs: Any) -> tuple[dict[str, Any], str]:
    """
    Given the name of a Persistent Volume Claim,
    return the corresponding PersistentVolume.

        Parameters:
            pvc_name (str): The name of the Persistent Volume Claim
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
        Returns:
            ((dict[str, Any], str)):
                (dict[str, Any]): Persistent Volume object
                (str): The name of the Persistent Volume.
        Raises:
            ProgrammingError: Function called without kubernetes_helper
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError(f"{__name__}() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    pv: dict[str, Any] = {}
    pv_name: str = ""
    field_selector = f"metadata.name={pvc_name}"

    vlist, status = kh.get_list_by_kind_namespace(("PersistentVolumeClaim", ""), "",
                                                  field_selector=field_selector,
                                                  resource_cache=kh_cache)
    if status == 200:
        for pvc in vlist:
            if deep_get(pvc, DictPath("metadata#name")) == pvc_name:
                volume_name = deep_get(pvc, DictPath("spec#volumeName"), "")
                if volume_name:
                    pv_name = volume_name
                    pv = kh.get_ref_by_kind_name_namespace(("PersistentVolume", ""),
                                                           pv_name, None, resource_cache=kh_cache)
                    break

    return pv, pv_name


def get_pv_status(obj: dict[str, Any]) -> tuple[str, StatusGroup]:
    """
    Given a Persistent Volume object, return its status.

        Parameters:
            obj (dict[str, Any]): The Persistent Volume object
        Returns:
            ((str, StatusGroup)):
                (str): The status of the Persistent Volume
                (StatusGroup): The StatusGroup of the status
    """
    phase: str = deep_get(obj, DictPath("status#phase"), "")

    if phase in ("Bound", "Available"):
        reason = phase
        status_group = StatusGroup.OK
    elif phase in ("Released", "Pending"):
        reason = phase
        status_group = StatusGroup.PENDING
    else:
        reason = deep_get(obj, DictPath("status#reason"), "").strip()
        status_group = StatusGroup.NOT_OK
    return reason, status_group


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def get_pod_resource_list(obj: dict[str, Any], **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Return a list of resources for a pod.

        Parameters:
            obj (dict): The pod object.
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list of pod resources.
                (int): The status for the request
        Raises:
            ProgrammingError: Function called without kubernetes_helper
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError(f"{__name__}() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    vlist: list[dict[str, Any]] = []

    init_containers = True
    containers = True
    ephemeral_containers = True

    pod_name = deep_get(obj, DictPath("metadata#name"))
    pod_namespace = deep_get(obj, DictPath("metadata#namespace"))

    # We'll be one-shotting all of these, so we won't use reexecutor
    executor_ = concurrent.futures.ThreadPoolExecutor()
    executors = {}

    filter_resources = deep_get(cmtlib.cmtconfig, DictPath("Pod#filter_resources"), [])

    container_resources = []
    if init_containers:
        kind = ("InitContainer", "")
        for container in deep_get(obj, DictPath("spec#initContainers"), []):
            # We need these when iterating containers
            container_resources.append((kind, container,
                                        deep_get(obj, DictPath("status#initContainerStatuses"))))
    if containers:
        kind = ("Container", "")
        for container in deep_get(obj, DictPath("spec#containers"), []):
            # We need these when iterating containers
            container_resources.append((kind, container,
                                        deep_get(obj, DictPath("status#containerStatuses"))))
    if ephemeral_containers:
        kind = ("EphemeralContainer", "")
        for container in deep_get(obj, DictPath("spec#ephemeralContainers"), []):
            # We need these when iterating containers
            container_resources.append((kind, container,
                                        deep_get(obj,
                                                 DictPath("status#ephemeralContainerStatuses"))))

    for kind, container, container_status in container_resources:
        rtype = resource_kind_to_rtype(kind)
        ref = container
        name = deep_get(container, DictPath("name"))
        resource_tuple = ("", "", name)
        status, _status_group, restarts, message, age = \
            get_container_status(container_status, name)
        vlist.append({
            "ref": ref,
            "namespace": pod_namespace,
            "name": name,
            "kind": kind[0],
            "api_group": kind[1],
            "type": rtype,
            "resource_tuple": resource_tuple,
            "status": status,
            "restarts": restarts,
            "message": message,
            "age": age,
        })

    if "node" not in filter_resources:
        kind = ("Node", "")
        rtype = resource_kind_to_rtype(kind)
        name = deep_get(obj, DictPath("spec#nodeName"))
        ref = None
        if name is not None:
            ref = kh.get_ref_by_kind_name_namespace(("Node", ""),
                                                    name, None, resource_cache=kh_cache)
        if name is None:
            name = "<unset>"
        resource_tuple = ("", "", name)

        if ref is not None:
            status, _status_group, _taints, _full_taints = get_node_status(ref)
        else:
            status = "<unset>"

        vlist.append({
            "ref": ref,
            "namespace": pod_namespace,
            "name": name,
            "kind": kind[0],
            "api_group": kind[1],
            "type": rtype,
            "resource_tuple": resource_tuple,
            "status": status,
            "restarts": "",
            "message": "",
            "age": -1,
        })

    controller_name = ""
    controller_kind = ""

    # pylint: disable-next=too-many-nested-blocks
    for owr in deep_get(obj, DictPath("metadata#ownerReferences"), []):
        owr_kind = deep_get(owr, DictPath("kind"), "")
        owr_api_version = deep_get(owr, DictPath("apiVersion"), "")
        if "/" in owr_api_version:
            owr_api_version = owr_api_version.split("/")[0]
        else:
            owr_api_version = ""
        owr_kind = (owr_kind, owr_api_version)
        owr_name = deep_get(owr, DictPath("name"), "")
        is_controller = deep_get(owr, DictPath("controller"), False)
        if is_controller:
            controller_name = owr_name
            controller_kind = owr_kind[0]
            if "controller" in filter_resources:
                continue
            rtype = "[controller]"
        elif owr_kind == ("CronJob", "batch"):
            if "cronjob" in filter_resources:
                continue
            rtype = "[cronjob]"
        else:
            if "owner_reference" in filter_resources:
                continue
            rtype = "[owner_reference]"

        status = ""

        ref = kh.get_ref_by_kind_name_namespace(owr_kind, owr_name, pod_namespace,
                                                resource_cache=kh_cache)
        if ref is None:
            status = "<missing>"
        else:
            conditions = deep_get(ref, DictPath("status#conditions"), [])
            for condition in conditions:
                if deep_get(condition, DictPath("type"), "") == "Ready":
                    _status = deep_get(condition, DictPath("status"), "")
                    reason = deep_get(condition, DictPath("reason"), "")
                    if reason:
                        status = reason
                    else:
                        if _status == "True":
                            status = "Ready"
                        elif _status == "False":
                            status = "NotReady"
                        elif _status == "Unknown":
                            status = "Unknown"

        resource_tuple = (owr_kind[0], owr_kind[1], owr_name)
        vlist.append({
            "ref": ref,
            "namespace": pod_namespace,
            "name": owr_name,
            "kind": owr_kind[0],
            "api_group": owr_kind[1],
            "type": rtype,
            "resource_tuple": resource_tuple,
            "status": status,
            "restarts": "",
            "message": "",
            "age": -1,
        })

    if controller_kind == "Node":
        trivy_kind = "Pod"
        trivy_name = pod_name
    else:
        trivy_kind = controller_kind
        trivy_name = controller_name
    selector_dict: dict[str, str] = {
        "trivy-operator.resource.kind": trivy_kind,
        "trivy-operator.resource.name": trivy_name,
    }
    trivy_selector = make_label_selector(selector_dict)

    # OK, we have the controller kind (and thus trivy_selector);
    # time to fire off the requests for lists.
    for resource, kwargs in (
            ("event", {
                "kind": ("Event", ""),
                "namespace": pod_namespace,
                "field_selector": make_label_selector({
                    "involvedObject.name": pod_name,
                    "involvedObject.namespace": pod_namespace})}),
            ("pod_disruption_budget", {
                "kind": ("PodDisruptionBudget", "policy"),
                "namespace": pod_namespace}),
            ("pod_metrics", {
                "kind": ("PodMetrics", "metrics.k8s.io")}),
            ("config_audit_report", {
                "kind": ("ConfigAuditReport", "aquasecurity.github.io"),
                "namespace": pod_namespace,
                "label_selector": trivy_selector}),
            ("infra_assessment_report", {
                "kind": ("InfraAssessmentReport", "aquasecurity.github.io"),
                "namespace": pod_namespace,
                "label_selector": trivy_selector}),
            ("vulnerability_report", {
                "kind": ("VulnerabilityReport", "aquasecurity.github.io"),
                "namespace": pod_namespace,
                "label_selector": trivy_selector}),
            ("exposed_secret_report", {
                "kind": ("ExposedSecretReport", "aquasecurity.github.io"),
                "namespace": pod_namespace,
                "label_selector": trivy_selector}),
            ("sbom_report", {
                "kind": ("SbomReport", "aquasecurity.github.io"),
                "namespace": pod_namespace,
                "label_selector": trivy_selector}),
            ("antrea_agent", {
                "kind": ("AntreaAgentInfo", "crd.antrea.io")}),
            ("antrea_controller", {
                "kind": ("AntreaControllerInfo", "crd.antrea.io")}),
            ("service", {
                "kind": ("Service", ""), "namespace": pod_namespace}),
            ("resourceclaim", {
                "kind": ("ResourceClaim", "resource.k8s.io"),
                "namespace": pod_namespace})):
        kind = deep_get(kwargs, DictPath("kind"))
        if "kubernetes_helper" not in kwargs:
            kwargs["kubernetes_helper"] = kh
            kwargs["kh_cache"] = kh_cache
        if resource not in filter_resources and kh.is_kind_available(kind):
            executors[kind] = executor_.submit(listgetters_async.get_kubernetes_list, **kwargs)

    if "persistent_volume_claim" not in filter_resources:
        for volume in deep_get(obj, DictPath("spec#volumes"), []):
            if deep_get(volume, DictPath("persistentVolumeClaim")) is None:
                continue

            kind = ("PersistentVolume", "")
            rtype = resource_kind_to_rtype(kind)

            claim_name = deep_get(volume, DictPath("persistentVolumeClaim#claimName"))
            pv, pv_name = get_pv_from_pvc_name(claim_name, kubernetes_helper=kh)

            if pv:
                status, _status_group = get_pv_status(pv)
            else:
                pv_name = "<INVALID PV>"
                status = "Error"
            ref = pv
            resource_tuple = ("", "", pv_name)
            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": status,
                "restarts": "",
                "message": "",
                "age": -1,
            })

    if "service_account" not in filter_resources \
            and deep_get(obj, DictPath("spec#serviceAccountName")) is not None:
        kind = ("ServiceAccount", "")
        rtype = resource_kind_to_rtype(kind)

        name = deep_get(obj, DictPath("spec#serviceAccountName"))
        ref = kh.get_ref_by_kind_name_namespace(kind, name, pod_namespace, resource_cache=kh_cache)
        resource_tuple = ("", "", name)
        vlist.append({
            "ref": ref,
            "namespace": pod_namespace,
            "name": name,
            "kind": kind[0],
            "api_group": kind[1],
            "type": rtype,
            "resource_tuple": resource_tuple,
            "status": "",
            "restarts": "",
            "message": "",
            "age": -1,
        })

    for vol in deep_get(obj, DictPath("spec#volumes"), []):
        status = ""

        if deep_get(vol, DictPath("secret")) is not None and "secret" not in filter_resources:
            kind = ("Secret", "")
            rtype = resource_kind_to_rtype(kind)
            secret_name = deep_get(vol, DictPath("secret#secretName"))
            optional = deep_get(vol, DictPath("secret#optional"), False)
            resource_tuple = ("", "", secret_name)
            ref = kh.get_ref_by_kind_name_namespace(kind, secret_name, pod_namespace,
                                                    resource_cache=kh_cache)
            if ref is None:
                if not optional:
                    status = "<missing>"
                else:
                    status = "<optional>"
            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": secret_name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": status,
                "restarts": "",
                "message": "",
                "age": -1,
            })

        if deep_get(vol, DictPath("configMap")) is not None \
                and "config_map" not in filter_resources:
            kind = ("ConfigMap", "")
            rtype = resource_kind_to_rtype(kind)
            cm_name = deep_get(vol, DictPath("configMap#name"))
            optional = deep_get(vol, DictPath("configMap#optional"), False)
            resource_tuple = ("", "", cm_name)
            ref = kh.get_ref_by_kind_name_namespace(kind, cm_name, pod_namespace,
                                                    resource_cache=kh_cache)
            if ref is None:
                if not optional:
                    status = "<missing>"
                else:
                    status = "<optional>"
            else:
                if not deep_get(ref, DictPath("data"), []):
                    status = "<empty>"
            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": cm_name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": status,
                "restarts": "",
                "message": "",
                "age": -1,
            })

    if "secret" not in filter_resources:
        for vol in deep_get(obj, DictPath("spec#imagePullSecrets"), []):
            kind = ("Secret", "")
            rtype = "[image_pull_secret]"
            secret_name = deep_get(vol, DictPath("name"))
            resource_tuple = ("", "", secret_name)
            ref = kh.get_ref_by_kind_name_namespace(kind, secret_name, pod_namespace,
                                                    resource_cache=kh_cache)
            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": secret_name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": "",
                "restarts": "",
                "message": "",
                "age": -1,
            })

    if "pod_metrics" not in filter_resources:
        kind = ("PodMetrics", "metrics.k8s.io")
        podmetrics = kh.get_ref_by_kind_name_namespace(kind, pod_name, pod_namespace,
                                                       resource_cache=kh_cache)
        if podmetrics is not None and podmetrics:
            ref = podmetrics
            rtype = resource_kind_to_rtype(kind)
            resource_tuple = ("", "", pod_name)
            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": pod_name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": "",
                "restarts": "",
                "message": "",
                "age": -1,
            })

    if "cilium_endpoint" not in filter_resources:
        # Check if there's a matching cilium endpoint
        kind = ("CiliumEndpoint", "cilium.io")
        ref = kh.get_ref_by_kind_name_namespace(kind, pod_name, pod_namespace,
                                                resource_cache=kh_cache)
        if ref is not None and ref:
            rtype = resource_kind_to_rtype(kind)
            resource_tuple = ("", "", pod_name)
            status = deep_get(ref, DictPath("status#state"), "Unknown")
            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": pod_name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": status.capitalize(),
                "restarts": "",
                "message": "",
                "age": -1,
            })

    if "runtimeclass" not in filter_resources:
        kind = ("RuntimeClass", "node.k8s.io")
        name = deep_get(obj, DictPath("spec#runtimeClassName"))
        ref = None
        if name is not None:
            ref = kh.get_ref_by_kind_name_namespace(kind, name, "", resource_cache=kh_cache)
        if ref is not None and ref:
            rtype = resource_kind_to_rtype(kind)
            resource_tuple = ("", "", name)
            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": "",
                "restarts": "",
                "message": "",
                "age": -1,
            })

    # pylint: disable-next=too-many-nested-blocks
    for kind, ex in executors.items():
        vlist_, status_ = ex.result()
        # We ignore failures
        if status_ != 200 or not vlist_:
            continue
        rtype = resource_kind_to_rtype(kind)

        if kind == ("Event", ""):
            tmp_vlist = []
            for event in vlist_:
                ref = event
                # For kind we do not want the api_family
                event_name = deep_get(event, DictPath("metadata#name"))
                resource_tuple = (kind[0], "", event_name)
                status = deep_get(event, DictPath("type"))
                ts = deep_get_with_fallback(event, [DictPath("series#lastObservedTime"),
                                                    DictPath("deprecatedLastTimestamp"),
                                                    DictPath("lastTimestamp"),
                                                    DictPath("eventTime"),
                                                    DictPath("deprecatedFirstTimestamp"),
                                                    DictPath("firstTimestamp")])
                tmp = timestamp_to_datetime(ts)
                seen = get_since(tmp)
                message = deep_get(event, DictPath("message"), "")
                message = message.replace("\n", "\\n").rstrip()

                tmp_vlist.append({
                    "ref": ref,
                    "namespace": pod_namespace,
                    "name": event_name,
                    "kind": kind[0],
                    "api_group": kind[1],
                    "type": rtype,
                    "resource_tuple": resource_tuple,
                    "status": status,
                    "restarts": "",
                    "message": message,
                    "age": seen,
                })
            for event in natsorted(tmp_vlist, key=itemgetter("age")):
                vlist.append(event)
            continue

        if kind == ("PodDisruptionBudget", "policy"):
            for pdb in vlist_:
                pdb_name = deep_get(pdb, DictPath("metadata#name"))
                pdb_namespace = deep_get(pdb, DictPath("metadata#namespace"))
                pdb_selector = deep_get(pdb, DictPath("spec#selector#matchLabels"))
                obj_labels = deep_get(obj, DictPath("metadata#labels"), {})
                # If the selector matches we're happy
                if pdb_selector.items() & obj_labels.items() != pdb_selector.items():
                    continue
                resource_tuple = ("", "", pdb_name)
                ref = pdb
                vlist.append({
                    "ref": ref,
                    "namespace": pdb_namespace,
                    "name": pdb_name,
                    "kind": kind[0],
                    "api_group": kind[1],
                    "type": rtype,
                    "resource_tuple": resource_tuple,
                    "status": "",
                    "restarts": "",
                    "message": "",
                    "age": -1,
                })
            continue

        if kind == ("ConfigAuditReport", "aquasecurity.github.io"):
            ref = vlist_[0]
            if ref is None or not ref:
                continue

            report_name = deep_get(ref, DictPath("metadata#name"))

            resource_tuple = (kind[0], "", report_name)

            critical = deep_get(ref, DictPath("report#summary#criticalCount"), 0)
            high = deep_get(ref, DictPath("report#summary#highCount"), 0)
            medium = deep_get(ref, DictPath("report#summary#mediumCount"), 0)
            low = deep_get(ref, DictPath("report#summary#lowCount"), 0)

            message = ""
            message_array = []

            status = "OK"

            if low:
                status = "Warning"
                message_array.append(f"{low} Low")
            if medium:
                status = "Warning"
                message_array.insert(0, f"{medium} Medium")
            if high:
                status = "Warning"
                message_array.insert(0, f"{high} High")
            if critical:
                status = "Warning"
                message_array.insert(0, f"{critical} Critical")

            if message_array:
                message = "Reported issues: "
                message += " / ".join(message_array)

            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": pod_name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": status,
                "restarts": "",
                "message": message,
                "age": -1,
            })
            continue

        if kind == ("InfraAssessmentReport", "aquasecurity.github.io"):
            ref = vlist_[0]
            if ref is None or not ref:
                continue

            report_name = deep_get(ref, DictPath("metadata#name"))

            resource_tuple = (kind[0], "", report_name)

            critical = deep_get(ref, DictPath("report#summary#criticalCount"), 0)
            high = deep_get(ref, DictPath("report#summary#highCount"), 0)
            medium = deep_get(ref, DictPath("report#summary#mediumCount"), 0)
            low = deep_get(ref, DictPath("report#summary#lowCount"), 0)

            message = ""
            message_array = []

            status = "OK"

            if low:
                status = "Warning"
                message_array.append(f"{low} Low")
            if medium:
                status = "Warning"
                message_array.insert(0, f"{medium} Medium")
            if high:
                status = "Warning"
                message_array.insert(0, f"{high} High")
            if critical:
                status = "Warning"
                message_array.insert(0, f"{critical} Critical")

            if message_array:
                message = "Reported issues: "
                message += " / ".join(message_array)

            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": pod_name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": status,
                "restarts": "",
                "message": message,
                "age": -1,
            })
            continue

        if kind == ("VulnerabilityReport", "aquasecurity.github.io"):
            ref = vlist_[0]
            if ref is None or not ref:
                continue

            report_name = deep_get(ref, DictPath("metadata#name"))

            resource_tuple = (kind[0], "", report_name)

            critical = deep_get(ref, DictPath("report#summary#criticalCount"), 0)
            high = deep_get(ref, DictPath("report#summary#highCount"), 0)
            medium = deep_get(ref, DictPath("report#summary#mediumCount"), 0)
            unknown = deep_get(ref, DictPath("report#summary#unknownCount"), 0)
            low = deep_get(ref, DictPath("report#summary#lowCount"), 0)

            message = ""
            message_array = []

            status = "OK"

            if low:
                status = "Warning"
                message_array.append(f"{low} Low")
            if unknown:
                status = "Warning"
                message_array.insert(0, f"{unknown} Unknown")
            if medium:
                status = "Warning"
                message_array.insert(0, f"{medium} Medium")
            if high:
                status = "Warning"
                message_array.insert(0, f"{high} High")
            if critical:
                status = "Warning"
                message_array.insert(0, f"{critical} Critical")

            if message_array:
                message = "Reported issues: "
                message += " / ".join(message_array)

            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": pod_name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": status,
                "restarts": "",
                "message": message,
                "age": -1,
            })
            continue

        if kind == ("ExposedSecretReport", "aquasecurity.github.io"):
            ref = vlist_[0]
            if ref is None or not ref:
                continue

            report_name = deep_get(ref, DictPath("metadata#name"))

            resource_tuple = (kind[0], "", report_name)

            critical = deep_get(ref, DictPath("report#summary#criticalCount"), 0)
            high = deep_get(ref, DictPath("report#summary#highCount"), 0)
            medium = deep_get(ref, DictPath("report#summary#mediumCount"), 0)
            low = deep_get(ref, DictPath("report#summary#lowCount"), 0)

            message = ""
            message_array = []

            status = "OK"

            if low:
                status = "Warning"
                message_array.append(f"{low} Low")
            if medium:
                status = "Warning"
                message_array.insert(0, f"{medium} Medium")
            if high:
                status = "Warning"
                message_array.insert(0, f"{high} High")
            if critical:
                status = "Warning"
                message_array.insert(0, f"{critical} Critical")

            if message_array:
                message = "Reported issues: "
                message += " / ".join(message_array)

            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": pod_name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": status,
                "restarts": "",
                "message": message,
                "age": -1,
            })
            continue

        if kind == ("SbomReport", "aquasecurity.github.io"):
            ref = vlist_[0]
            if ref is None or not ref:
                continue

            report_name = deep_get(ref, DictPath("metadata#name"))

            resource_tuple = (kind[0], "", report_name)

            message = ""
            message_array = []

            status = ""

            if message_array:
                message = "Reported issues: "
                message += " / ".join(message_array)

            vlist.append({
                "ref": ref,
                "namespace": pod_namespace,
                "name": pod_name,
                "kind": kind[0],
                "api_group": kind[1],
                "type": rtype,
                "resource_tuple": resource_tuple,
                "status": status,
                "restarts": "",
                "message": message,
                "age": -1,
            })
            continue

        # OK, this pod is an antrea-agent, so we should look for one that matches it
        if kind == ("AntreaAgentInfo", "crd.antrea.io"):
            for item in vlist_:
                if deep_get(item, DictPath("podRef#namespace"), "") == pod_namespace \
                        and deep_get(item, DictPath("podRef#name"), "") == pod_name:
                    ref = item
                    name = deep_get(item, DictPath("metadata#name"))
                    status = "Unknown"
                    for condition in deep_get(item, DictPath("agentConditions"), {}):
                        if deep_get(condition, DictPath("type")) == "AgentHealthy":
                            healthy = deep_get(condition, DictPath("status"), "Unknown")
                            if healthy == "True":
                                status = "Healthy"
                            elif healthy == "False":
                                status = "Unhealthy"
                    resource_tuple = ("", "", name)

                    vlist.append({
                        "ref": ref,
                        "namespace": pod_namespace,
                        "name": name,
                        "kind": kind[0],
                        "api_group": kind[1],
                        "type": rtype,
                        "resource_tuple": resource_tuple,
                        "status": status,
                        "restarts": "",
                        "message": "",
                        "age": -1,
                    })
                    break
            continue

        # OK, this pod is an antrea-agent, so we should look for one that matches it
        if kind == ("AntreaControllerInfo", "crd.antrea.io"):
            for item in vlist_:
                if deep_get(item, DictPath("podRef#namespace"), "") == pod_namespace \
                        and deep_get(item, DictPath("podRef#name"), "") == pod_name:
                    ref = item
                    name = deep_get(item, DictPath("metadata#name"))
                    status = "Unknown"
                    for condition in deep_get(item, DictPath("controllerConditions"), {}):
                        if deep_get(condition, DictPath("type")) == "ControllerHealthy":
                            healthy = deep_get(condition, DictPath("status"), "Unknown")
                            if healthy == "True":
                                status = "Healthy"
                            elif healthy == "False":
                                status = "Unhealthy"
                    rtype = resource_kind_to_rtype(kind)
                    resource_tuple = ("", "", name)
                    vlist.append({
                        "ref": ref,
                        "namespace": pod_namespace,
                        "name": name,
                        "kind": kind[0],
                        "api_group": kind[1],
                        "type": rtype,
                        "resource_tuple": resource_tuple,
                        "status": status,
                        "restarts": "",
                        "message": "",
                        "age": -1,
                    })
                    break
            continue

        # Find service(s) that has a selector that points to this pod
        if kind == ("Service", ""):
            for item in vlist_:
                selector = deep_get(item, DictPath("spec#selector"), {})
                if not selector:
                    continue
                vlist2_, status = \
                    kh.get_list_by_kind_namespace(("Pod", ""), pod_namespace,
                                                  label_selector=make_label_selector(selector),
                                                  field_selector=f"metadata.name={pod_name},"
                                                                 "metadata.namespace="
                                                                 f"{pod_namespace}",
                                                  resource_cache=kh_cache)
                if vlist2_:
                    ref = item
                    name = deep_get(item, DictPath("metadata#name"))
                    namespace = deep_get(item, DictPath("metadata#namespace"))
                    resource_tuple = ("", "", name)
                    vlist.append({
                        "ref": ref,
                        "namespace": namespace,
                        "name": name,
                        "kind": kind[0],
                        "api_group": kind[1],
                        "type": rtype,
                        "resource_tuple": resource_tuple,
                        "status": "",
                        "restarts": "",
                        "message": "",
                        "age": -1,
                    })
            continue

        if kind == ("ResourceClaim", "resource.k8s.io"):
            for item in vlist_:
                owr = deep_get(item, DictPath("metadata#ownerReferences"), [])
                for owner_reference in owr:
                    if deep_get(owner_reference, DictPath("controller"), False) and \
                       deep_get(owner_reference, DictPath("kind"), "") == "Pod" and \
                       deep_get(owner_reference, DictPath("name"), "") == pod_name:
                        name = deep_get(item, DictPath("metadata#name"))
                        resource_tuple = ("", "", name)
                        vlist.append({
                            "ref": item,
                            "namespace": pod_namespace,
                            "name": name,
                            "kind": kind[0],
                            "api_group": kind[1],
                            "type": rtype,
                            "resource_tuple": resource_tuple,
                            "status": "",
                            "restarts": "",
                            "message": "",
                            "age": -1,
                        })
            continue

    return vlist, 200


# pylint: disable-next=too-many-locals
def get_info_by_last_applied_configuration(obj: dict, **kwargs: Any) -> tuple[list[dict], int]:
    """
    Given a kind tuple, get a list of all its resources, and check for a last applied
    configuration, optionally matching by API-version.

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
                kind ((str, str)): The kind tuple to get resources for
                match_api_version (bool): Should the information be filtered by API-version?
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list of pod resources.
                (int): The status for the request
        Raises:
            ProgrammingError: Function called without kubernetes_helper
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError(f"{__name__}() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    if (kind := deep_get(kwargs, DictPath("kind"), ("", ""))) == ("", ""):
        return [], 404

    configuration: dict[str, str] = {
        "kind": kind[0]
    }

    if deep_get(kwargs, DictPath("match_api_version"), False):
        version_path = deep_get(kwargs, DictPath("version_path"))
        group_path = deep_get(kwargs, DictPath("group_path"))
        api_version = f"{deep_get(obj, DictPath(group_path))}/" \
                      f"{deep_get(obj, DictPath(version_path))}"
        configuration["apiVersion"] = api_version

    resource_info: list[dict] = []

    items, status = kh.get_list_by_kind_namespace(kind, "", resource_cache=kh_cache)
    if status != 200:
        return resource_info, status

    for item in items:
        last_applied_configuration = \
            deep_get(item, DictPath("metadata#annotations#kubectl.kubernetes.io/"
                                    "last-applied-configuration"), {})
        if last_applied_configuration is None or not last_applied_configuration:
            continue
        try:
            data = json.loads(last_applied_configuration)
        except DecodeException:
            # The data is malformed; skip the entry
            continue

        match = True
        for key, conf in configuration.items():
            if key not in data or conf != data[key]:
                match = False
                break
        if match:
            name = deep_get(item, DictPath("metadata#name"))
            namespace = deep_get(item, DictPath("metadata#namespace"), "")
            d = {
                "kind": kind,
                "metadata": {
                    "namespace": namespace,
                    "name": name,
                }
            }
            resource_info.append(d)

    return resource_info, status


# pylint: disable-next=unused-argument
def get_sidecar_rule_list(obj: dict, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Return a list of Istio sidecar rules.

        Parameters:
            obj (dict): The pod object.
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list of sidecar rules.
                (int): The status for the request
    """
    vlist: list[dict[str, Any]] = []

    for traffic_type, items in (("Ingress", deep_get(obj, DictPath("spec#ingress"), [])),
                                ("Egress", deep_get(obj, DictPath("spec#egress"), []))):
        for item in items:
            pport: str = deep_get(item, DictPath("port#number"), "")
            name: str = deep_get(item, DictPath("port#name"), "")
            protocol: str = deep_get(item, DictPath("port#protocol"), "")
            port: tuple[str, str, str] = (name, pport, protocol)
            ref = item
            bind: str = deep_get(item, DictPath("bind"), "")
            capture_mode: str = deep_get(item, DictPath("captureMode"), "NONE")
            # Required
            default_endpoint: str = deep_get(item, DictPath("defaultEndpoint"), "")
            # N/A
            hosts: list[str] = deep_get(item, DictPath("hosts"), [])
            vlist.append({
                "traffic_type": traffic_type,
                "port": port,
                "ref": ref,
                "bind": bind,
                "capture_mode": capture_mode,
                "default_endpoint": default_endpoint,
                "hosts": hosts,
            })

    return vlist, 200


# pylint: disable-next=unused-argument
def get_virtsvc_rule_list(obj: dict, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Extracts data from an Istio Virtual Service.

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): A list of virtual service rules
                (int): The status for the request
    """
    vlist: list[dict[str, Any]] = []

    for rule_path, rule_type in [("spec#http", "HTTP"), ("spec#tls", "TLS"), ("spec#tcp", "TCP")]:
        destinations: list[tuple[str, str, str]] = []

        for rule in deep_get(obj, DictPath(rule_path), []):
            for item in deep_get(rule, DictPath("route"), []):
                host = deep_get(item, DictPath("destination#host"), "")
                subset = deep_get(item, DictPath("destination#subset"))
                if subset is None:
                    subset = "*"
                port = deep_get(item, DictPath("destination#port#number"), "")
                destinations.append((host, subset, port))

        if destinations:
            vlist.append({
                "rule_type": rule_type,
                "destinations": destinations,
            })

    return vlist, 200


# pylint: disable-next=unused-argument
def listgetter_ansible_volumes(obj: dict, **kwargs: Any) -> tuple[list[dict[str, Any]], str]:
    """
    Given an Ansible facts dict for a host, return information about its volumes.

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list of data
                (int): The status for the request
    """
    vlist: list[dict[str, Any]] = []

    # Find all mounts
    for item in deep_get(obj, DictPath("ansible_mounts"), []):
        d: dict[str, Any] = {}
        device = deep_get(item, DictPath("device"), "")
        if not device:
            continue
        fstype = deep_get(item, DictPath("fstype"), "")
        size_total = deep_get(item, DictPath("size_total"), 0)
        if not size_total:
            continue
        size_available = deep_get(item, DictPath("size_available"), 0)
        partition_size_total = disksize_to_human(size_total)
        partition_size_used = disksize_to_human(size_total - size_available)
        mountpoint = deep_get(item, DictPath("mount"), "")
        options = deep_get(item, DictPath("options"), "").split(",")
        # NFS mounts can be added directly; no need to do lookups
        if fstype == "nfs":
            d = {
                "mountpoint": mountpoint,
                "fstype": fstype,
                "options": options,
                "device": device,
                "model": "",
                "partition_size_used": partition_size_used,
                "partition_size_total": partition_size_total,
            }
            vlist.append(d)
            continue
        device = os.path.basename(device)

        if check_matchlist(mountpoint,
                           deep_get(cmtlib.cmtconfig,
                                    DictPath("__Inventory#mountpoint_skiplist"),
                                    ["/boot/efi",
                                     "/var/lib/origin/*",
                                     "/var/snap/*",
                                     "/run/*",
                                     "*@docker*"])):
            continue
        if check_matchlist(device,
                           deep_get(cmtlib.cmtconfig,
                                    DictPath("__Inventory#device_skiplist"),
                                    ["loop*"])):
            continue

        model = get_device_model(obj, device)
        d = {
            "mountpoint": mountpoint,
            "fstype": fstype,
            "options": options,
            "device": device,
            "partition_size_used": partition_size_used,
            "partition_size_total": partition_size_total,
            "model": model,
        }
        vlist.append(d)

    return vlist, "OK"


# pylint: disable-next=unused-argument
def listgetter_configmap_data(obj: dict, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Get a list of the data in a configmap.

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list of data
                (int): The status for the request
    """
    vlist: list[dict[str, Any]] = []

    cm_name = deep_get(obj, DictPath("metadata#name"))
    cm_namespace = deep_get(obj, DictPath("metadata#namespace"), "")

    for key, value in deep_get(obj, DictPath("binary_data"), {}).items():
        vlist.append({
            "cm_name": cm_name,
            "cm_namespace": cm_namespace,
            "configmap": key,
            "type": "Binary",
            "formatter": None,
            "data": value,
        })

    for key, value in deep_get(obj, DictPath("data"), {}).items():
        data_type, formatter = formatters.identify_cmdata(key, cm_name, cm_namespace, value)
        vlist.append({
            "cm_name": cm_name,
            "cm_namespace": cm_namespace,
            "configmap": key,
            "type": data_type,
            "formatter": formatter,
            "data": value,
        })

    return vlist, 200


def listgetter_dict_list(obj: dict[str, Any], **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Given a dict, return a list of dicts.
    The format of the newly generated dict is:
    {"key": key_from_dict, "value": value_from_dict}
    This is to ensure that we can get the key without knowing the name of the key.

        Parameters:
            obj (dict): The object to convert to a list
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list representation of the dict
                (int): The status for the request
    """
    path = deep_get(kwargs, DictPath("path"))
    vlist = []
    for key, value in deep_get(obj, DictPath(path), {}).items():
        vlist.append({"key": key, "value": value})
    return vlist, 200


def listgetter_field(obj: dict[str, Any], **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    A listgetter that returns a list from a dict.
    Note: Shouldn't this be merged with listgetter_path() ?!

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments
                path (str): The path to the list
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list representation of the dict
                (int): The status for the request
    """
    path = deep_get(kwargs, DictPath("path"))
    vlist = deep_get(obj, DictPath(path))
    return vlist, 200


# key_paths: the dict keys that should be turned into values
# key_name: name for the key that holds these values
# fields: paths the fields in the dict that should be added to the list
#
# Thus:
# "a": {
#     "b": {
#        "d": 1,
#        "e": 2
#     },
#     "c": {
#        "d": 2,
#        "e": 3,
#     },
# }
# key_paths = ["a#b", "a#c"]
# key_name = "foo"
# fields = [{"path": "a#b", "name": "bar"}, {"path": "a#c", "name": "baz"}]
# would generate the list
# [{"foo": "d", "bar": 1, "baz": 2}, {"foo": "e", "bar": 2, "baz": 3}]
def listgetter_join_dicts_to_list(obj: dict[str, Any],
                                  **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Join dicts into a single list.

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments
                key_paths (str): The paths to join paths from
                key_name (str): The name to give to the give key field
                fields ([dict[str, str]]): A list of dict paths, and the names to give them
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list representation of the dicts
                (int): The status for the request
    """
    vlist: list[dict[str, Any]] = []
    key_paths = deep_get(kwargs, DictPath("key_paths"), "")
    key_name = deep_get(kwargs, DictPath("key_name"), "")
    fields = deep_get(kwargs, DictPath("fields"), [])

    keys = set()

    for key_path in key_paths:
        for key in deep_get(obj, DictPath(key_path), {}):
            keys.add(key)

    for key in keys:
        d = {
            key_name: key
        }
        for field in fields:
            path = deep_get(field, DictPath("path"), "")
            name = deep_get(field, DictPath("name"))
            if name is None:
                continue
            value = deep_get(obj, DictPath(f"{path}#{key}"))
            d[name] = value
        if len(d) <= 1:
            continue
        vlist.append(d)

    return vlist, 200


def listgetter_join_lists(obj: dict[str, Any], **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    A listgetter that takes two or more lists and joins them into one list.

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list of objects
                (int): The status for the request
    """
    paths = deep_get(kwargs, DictPath("paths"))
    vlist = []

    for path in paths:
        name_key = deep_get(path, DictPath("name_key"), "")
        name_value = deep_get(path, DictPath("name_value"), "")
        list_path = deep_get(path, DictPath("path"), [])
        d = {}
        if name_key:
            d[name_key] = name_value
        for key, value in deep_get_with_fallback(obj, list_path, []).items():
            d[key] = value
        vlist.append(d)
    return vlist, 200


# pylint: disable-next=unused-argument
def listgetter_matchrules(obj: dict, **kwargs: Any) -> tuple[list[dict], str]:
    """
    Extract match rules from an object.

        Parameters:
            obj (dict[str, Any]): The object to extract a list of matchrules from
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ([dict[str, Any]], str):
                ([dict]): The list of data
                (str): Always "OK"
    """
    match_list = []
    status = "OK"

    for match_any in deep_get(obj, DictPath("matchAny"), []):
        for match_feature in deep_get(match_any, DictPath("matchFeatures"), []):
            feature = deep_get(match_feature, DictPath("feature"), "")
            match_expressions_dict = deep_get(match_feature, DictPath("matchExpressions"), {})
            match_expressions = []
            for match_expression_name, match_expression in match_expressions_dict.items():
                tmp = make_set_expression_list([match_expression], match_expression_name)[0]
                match_expressions.append(tmp)
            match_list.append({
                "feature": f"Any:{feature}",
                "match_expressions": match_expressions,
            })

    for match_feature in deep_get(obj, DictPath("matchFeatures"), []):
        feature = deep_get(match_feature, DictPath("feature"), "")
        match_expressions_dict = deep_get(match_feature, DictPath("matchExpressions"), {})
        match_expressions = []
        for match_expression_name, match_expression in match_expressions_dict.items():
            tmp = make_set_expression_list([match_expression], match_expression_name)[0]
            match_expressions.append(tmp)
        match_list.append({
            "feature": f"{feature}",
            "match_expressions": match_expressions,
        })

    return match_list, status


# pylint: disable-next=too-many-locals
def listgetter_namespaced_resources(obj: dict, **kwargs: Any) -> \
        tuple[list, Union[str, int, list[StatusGroup]]]:
    """
    Given a Namespace object, find all objects that belong to that Namespace.

        Parameters:
            obj (dict): The object to extract a list of data from
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
                resources ([(str, str)]): A list of Kinds; if resources is not provided
                                          all namespaced resources will be searched
                label_selector (str): A label selector (optional)
                namespace (str): The name of the namespace to fetch namespaced resources for
                namespace_path (str): The path to get the name
                                      of the namespace to fetch namespaced resources for
        Returns:
            (([dict[str, Any]], int)): A list of Kubernetes objects of various Kinds
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError(f"{__name__}() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    vlist = []
    status: Union[str, int, list[StatusGroup]] = 200

    namespaced_resources = deep_get(kwargs, DictPath("resources"),
                                    kh.get_list_of_namespaced_resources())
    label_selector = deep_get(kwargs, DictPath("label_selector"), "")

    kind = ("Namespace", "")
    namespace_path = deep_get(kwargs, DictPath("namespace_path"), "")
    namespace = deep_get(kwargs, DictPath("namespace"), "")
    namespace = deep_get(obj, DictPath(namespace_path), namespace)

    # We'll be one-shotting all of these, so we won't use reexecutor
    executor_ = concurrent.futures.ThreadPoolExecutor()
    executors = {}
    for kind in namespaced_resources:
        executors[kind] = executor_.submit(listgetters_async.get_kubernetes_list,
                                           kind=kind, namespace=namespace,
                                           kubernetes_helper=kh, kh_cache=kh_cache,
                                           label_selector=label_selector)
    for kind, ex in executors.items():
        vlist_, status_ = ex.result()
        if status_ != 200:
            # 404 means no resources found; this is OK
            if status_ != 404:
                status = status_
            continue
        if not vlist_:
            continue
        # We are (potentially) listing a lot of different types of resources,
        # and they do not contain kind/apiVersion, so it will be tricky to tell them apart...
        for obj_ in vlist_:
            obj_["__kind_tuple"] = kind
        vlist += vlist_
    # If cancel_futures is supported we should use it
    if sys.version_info[0:2] >= (3, 9):
        executor_.shutdown(wait=False, cancel_futures=True)
    else:
        executor_.shutdown(wait=False)
    return vlist, status


# pylint: disable-next=unused-argument
def listgetter_noop(obj: dict, **kwargs: Any) -> tuple[list, str]:
    """
    A noop listgetter that returns an empty list.

        Parameters:
            obj (dict): The object to extract data from [unused]
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ([], str):
                ([]): An empty list
                (str): Always "OK"
    """
    return [], "OK"


def listgetter_feature_gates(obj: dict, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    """
    Listgetter for FeatureGate.config.openshift.io.

        Parameters:
            obj (dict): The object to extract data from
            **kwargs (dict[str, Any]): Keyword arguments
                path (str): The path to the list of feature gates
        Returns:
            (([dict[str, Any]], int)):
                ([dict[str, Any]]): The list of data
                (int): The status for the request
    """
    vlist = []
    path = deep_get(kwargs, DictPath("path"))

    for payload_version_data in deep_get(obj, DictPath(path), []):
        version = deep_get(payload_version_data, DictPath("version"), "<unknown>")
        for enabled_feature_gate in deep_get(payload_version_data, DictPath("enabled"), []):
            name = deep_get(enabled_feature_gate, DictPath("name"), "<unknown>")
            item = {
                "enabled": True,
                "version": version,
                "name": name,
            }
            vlist.append(item)
        for disabled_feature_gate in deep_get(payload_version_data, DictPath("disabled"), []):
            name = deep_get(disabled_feature_gate, DictPath("name"), "<unknown>")
            item = {
                "enabled": False,
                "version": version,
                "name": name,
            }
            vlist.append(item)
    return vlist, 200


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def listgetter_path(obj: dict, **kwargs: Any) -> tuple[Union[dict, list[dict]], int]:
    """
    Listgetter for paths.

        Parameters:
            obj (Dict): The object to extract a list of data from
            **kwargs (dict[str, Any]): Keyword arguments
        Returns:
            (vlist, retval):
                vlist (list[dict]): The list of data
                retval (int): The return value
    """
    vlists = []
    vlist = []

    rename_bare = deep_get(kwargs, DictPath("rename_bare"), None)
    flatten_dicts = deep_get(kwargs, DictPath("flatten_dicts"), False)
    paths = deep_get(kwargs, DictPath("paths"))
    multipath = deep_get(kwargs, DictPath("multipath"))
    join_key = deep_get(kwargs, DictPath("join_key"))
    # "standard", "reverse", ""
    enumeration: str = deep_get(kwargs, DictPath("enumeration"), "")

    # A multipath is a path to a dict that in turn contains lists, where you'd want the name
    # of the path containing the lists as a newly created key
    if multipath is not None:
        subpaths = deep_get(kwargs, DictPath("subpaths"))
        for path in subpaths:
            for item in deep_get(obj, DictPath(f"{multipath}#{path}"), []):
                tmp = copy.deepcopy(item)
                tmp["_key"] = path
                vlist.append(tmp)
        return vlist, 200

    # pylint: disable-next=too-many-nested-blocks
    if paths is not None:
        for path in paths:
            ppath = deep_get(path, DictPath("path"))
            ptype = deep_get(path, DictPath("type"))
            key_name = deep_get(path, DictPath("key_name"))
            key_value = deep_get(path, DictPath("key_value"))

            if ptype == "list":
                tmp = []
                for item in deep_get(obj, DictPath(ppath), []):
                    tmpitem = copy.deepcopy(item)
                    if key_name is not None and key_value is not None:
                        tmpitem[key_name] = key_value
                    tmp.append(tmpitem)
                vlists.append(tmp)
            else:
                for key in deep_get(obj, DictPath(ppath), []):
                    for item in deep_get(obj, DictPath(f"{ppath}#{key}"), []):
                        tmpitem = copy.deepcopy(item)
                        if key_name is not None and key_value is not None:
                            tmpitem[key_name] = key_value
                        vlist.append(tmpitem)
        if join_key is None:
            for tmp in vlists:
                vlist += tmp
        else:
            # XXX: What was intended here? join_key isn't used
            for tmp in vlists:
                vlist = [{**u, **v} for u, v in cast(dict, zip_longest(vlist, tmp, fillvalue={}))]
        return vlist, 200

    path = deep_get(kwargs, DictPath("path"))
    subpath = deep_get(kwargs, DictPath("subpath"))
    path_fields = deep_get(kwargs, DictPath("path_fields"))

    # As a special case passing the empty string as path will return the object instead of a list
    if not path:
        return obj, 200

    # If a subpath and path_fields are set path_fields from path will be merged into subpath
    # and the subpath lists are flattened into the path list.
    # pylint: disable-next=too-many-nested-blocks
    if subpath is not None and path_fields is not None:
        for item in deep_get(obj, DictPath(path), []):
            for subobj in deep_get(item, DictPath(subpath), []):
                for path_field in path_fields:
                    subobj[path_field] = deep_get(item, DictPath(path_field))
                vlist.append(subobj)
    else:
        tmp2: list[dict[str, Any]] = deep_get(obj, DictPath(path), [])
        vlist = []
        if rename_bare is not None and tmp2 is not None:
            for dictitem in tmp2:
                if not isinstance(dictitem, dict):
                    d = {rename_bare: dictitem}
                    if flatten_dicts and isinstance(deep_get(tmp2, DictPath(dictitem)), dict):
                        for key, value in deep_get(tmp2, DictPath(dictitem), {}).items():
                            d[key] = value
                    vlist.append(d)
                else:
                    vlist.append(dictitem)
        elif flatten_dicts and tmp2 is not None:
            for item in tmp2:
                d = {}
                for key, value in item.items():
                    d["key"] = key
                    d["value"] = value
                    vlist.append(d)
        elif enumeration:
            for i, item in enumerate(tmp2):
                if isinstance(item, dict):
                    if enumeration == "standard":
                        deep_set(item, DictPath("_extra_data#enumeration"), i,
                                 create_path=True)
                    elif enumeration == "reverse":
                        deep_set(item, DictPath("_extra_data#enumeration"), len(tmp2) - i,
                                 create_path=True)
                    vlist.append(item)
        else:
            vlist = tmp2

    return vlist, 200


# pylint: disable-next=unused-argument,too-many-branches,too-many-locals
def listgetter_policy_rules(obj: dict, **kwargs: Any) -> tuple[list[dict], int]:
    """
    Listgetter for Role & ClusterRole policy rules.

        Parameters:
            obj (Dict): The object to extract Role & ClusterRole policy rule information from
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (([dict], int)):
                ([dict]): The policy rules
                (int): The return value
    """
    vlist: list[dict] = []

    if obj is None:
        return [], 200

    # We want one entry per resource, hence a dict
    # Structure:
    # (api_group, resource): {
    #    "non_resource_urls": [],
    #    "resource_names": [],
    #    "verbs": [],
    # }
    resources: dict = {}

    for rule in deep_get(obj, DictPath("rules"), []):
        non_resource_urls = deep_get(rule, DictPath("nonResourceURLs"), [])
        resource_names = deep_get(rule, DictPath("resourceNames"), [])
        verbs = deep_get(rule, DictPath("verbs"), [])
        api_groups = deep_get(rule, DictPath("apiGroups"), [""])
        resourcelist = deep_get(rule, DictPath("resources"), [""])

        for api_group in api_groups:
            for resource in resourcelist:
                tmp = (resource, api_group)
                if tmp not in resources:
                    resources[tmp] = {
                        "non_resource_urls": {},
                        "resource_names": {},
                        "verbs": {},
                    }
                for non_resource_url in non_resource_urls:
                    resources[tmp]["non_resource_urls"][non_resource_url] = {}
                for resource_name in resource_names:
                    resources[tmp]["resource_names"][resource_name] = {}
                for verb in verbs:
                    resources[tmp]["verbs"][verb] = {}

    for item in resources.items():
        resource, data = item
        resource, api_group = resource
        non_resource_urls = list(deep_get(data, DictPath("non_resource_urls"), {}))
        resource_names = list(deep_get(data, DictPath("resource_names"), {}))
        verbs = list(deep_get(data, DictPath("verbs"), {}))
        verbs_all = "*" in verbs
        # "*" includes all other verbs
        if verbs_all:
            verbs_get = True
            verbs_list = True
            verbs_watch = True
            verbs_create = True
            verbs_update = True
            verbs_patch = True
            verbs_delete = True
            verbs_misc = ["*"]
        else:
            verbs_get = "get" in verbs
            verbs_list = "list" in verbs
            verbs_watch = "watch" in verbs
            verbs_create = "create" in verbs
            verbs_update = "update" in verbs
            verbs_patch = "patch" in verbs
            verbs_delete = "delete" in verbs
            verbs_misc = []
            for verb in verbs:
                if verb not in ("*", "get", "list", "watch",
                                "create", "update", "patch", "delete"):
                    verbs_misc.append(verb)

        vlist.append({
            "resource": resource,
            "api_group": api_group,
            "non_resource_urls": non_resource_urls,
            "resource_names": resource_names,
            "verbs": verbs,
            "verbs_all": verbs_all,
            "verbs_get": verbs_get,
            "verbs_list": verbs_list,
            "verbs_watch": verbs_watch,
            "verbs_create": verbs_create,
            "verbs_update": verbs_update,
            "verbs_patch": verbs_patch,
            "verbs_delete": verbs_delete,
            "verbs_misc": natsorted(verbs_misc)
        })

    return vlist, 200


# Listgetters acceptable for direct use in view files
listgetter_allowlist: dict[str, Callable] = {
    # Used by listview, listpad
    "generic_listgetter": generic_listgetter,
    "get_metrics_list": get_metrics_list,
    "get_pod_containers_list": get_pod_containers_list,
    "listgetter_files": listgetter_files,
    "listgetter_dir": listgetter_dir,
    # Used by listpad
    "get_hpa_metrics": get_hpa_metrics,
    "get_ingress_rule_list": get_ingress_rule_list,
    "get_netpol_rule_list": get_netpol_rule_list,
    "get_pod_resource_list": get_pod_resource_list,
    "get_info_by_last_applied_configuration": get_info_by_last_applied_configuration,
    "get_sidecar_rule_list": get_sidecar_rule_list,
    "get_virtsvc_rule_list": get_virtsvc_rule_list,
    "listgetter_ansible_volumes": listgetter_ansible_volumes,
    "listgetter_configmap_data": listgetter_configmap_data,
    "listgetter_dict_list": listgetter_dict_list,
    "listgetter_field": listgetter_field,
    "listgetter_join_dicts_to_list": listgetter_join_dicts_to_list,
    "listgetter_join_lists": listgetter_join_lists,
    "listgetter_matchrules": listgetter_matchrules,
    "listgetter_namespaced_resources": listgetter_namespaced_resources,
    "listgetter_noop": listgetter_noop,
    "listgetter_feature_gates": listgetter_feature_gates,
    "listgetter_path": listgetter_path,
    "listgetter_policy_rules": listgetter_policy_rules,
}
