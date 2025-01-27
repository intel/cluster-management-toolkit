#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Get items from lists for use in windowwidget
"""

# pylint: disable=too-many-lines

import re
import sys
from typing import Any, cast, Optional, Union
from collections.abc import Callable

try:
    from natsort import natsorted
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import natsort; "
             "you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

from clustermanagementtoolkit.cmttypes import deep_get, deep_get_with_fallback, DictPath
from clustermanagementtoolkit.cmttypes import ProgrammingError

from clustermanagementtoolkit import cmtlib
from clustermanagementtoolkit.cmtlib import disksize_to_human, get_package_versions, get_since
from clustermanagementtoolkit.cmtlib import make_label_selector, make_set_expression
from clustermanagementtoolkit.cmtlib import split_msg, timestamp_to_datetime

from clustermanagementtoolkit import kubernetes_helper

from clustermanagementtoolkit.pvtypes import KNOWN_PV_TYPES


def get_conditions(obj: dict, **kwargs: Any) -> list[dict]:
    """
    Get a list of conditions.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
              path (str): The path to the conditions list
        Returns:
            ([dict]): A list of conditions
    """
    condition_list = []

    path: Union[str, DictPath] = deep_get(kwargs, DictPath("path"), DictPath("status#conditions"))

    for condition in deep_get(obj, DictPath(path), []):
        ctype = deep_get(condition, DictPath("type"), "")
        status = deep_get_with_fallback(condition, [DictPath("status"), DictPath("phase")], "")
        last_probe = deep_get(condition, DictPath("lastProbeTime"))
        if last_probe is None:
            last_probe = "<unset>"
        else:
            timestamp = timestamp_to_datetime(last_probe)
            last_probe = f"{timestamp.astimezone():%Y-%m-%d %H:%M:%S}"
        last_transition = deep_get(condition, DictPath("lastTransitionTime"))
        if last_transition is None:
            last_transition = "<unset>"
        else:
            timestamp = timestamp_to_datetime(last_transition)
            last_transition = f"{timestamp.astimezone():%Y-%m-%d %H:%M:%S}"
        message = deep_get(condition, DictPath("message"), "")
        condition_list.append({
            "fields": [ctype, status, last_probe, last_transition, message],
        })
    return condition_list


# pylint: disable-next=too-many-locals
def get_kubernetes_objects(obj: dict, **kwargs: Any) -> list[tuple[str, ...]]:
    """
    Get a list of fields from Kubernetes objects.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
                field_paths ([DictPath]): A list of DictPath to get data from
                kind (str): The Kubernetes kind to get objects from
                kind_path (str): The path to the Kubernetes kind to get objects from
                api_family (str): The Kubernetes API-family to get objects from
                api_family_path (str): The path to the Kubernetes API-family to get objects from
                name (str): The name to use in the selector
                name_path (str): The path to the name to use in the selector
                namespace (str): The namespace for the objects
                namespace_path (str): The path to the namespace for the objects
                selector_type (str): "field" or "label"
                selector (str): The selector to use; if name is provided the selector will use name,
                                otherwise the selector will be used bare
        Returns:
            ([(str, str)]): A list of fields from Kubernetes objects
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("get_kubernetes_objects() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    field_paths = deep_get(kwargs, DictPath("field_paths"), [])
    kind_path = deep_get(kwargs, DictPath("kind_path"))
    kind = deep_get(kwargs, DictPath("kind"))
    kind = deep_get(obj, DictPath(kind_path), kind)

    api_family_path = deep_get(kwargs, DictPath("api_family_path"))
    api_family = deep_get(kwargs, DictPath("api_family"), "")
    api_family = deep_get(obj, DictPath(api_family_path), api_family)

    namespace_path = deep_get(kwargs, DictPath("namespace_path"))
    namespace = deep_get(kwargs, DictPath("namespace"), "")
    namespace = deep_get(obj, DictPath(namespace_path), namespace)

    name_path = deep_get(kwargs, DictPath("name_path"))
    name = deep_get(kwargs, DictPath("name"))
    name = deep_get(obj, DictPath(name_path), name)

    selector_type = deep_get(kwargs, DictPath("selector_type"), "label")
    selector_str = deep_get(kwargs, DictPath("selector"))

    label_selector = ""
    field_selector = ""

    if selector_str:
        if name:
            selector = f"{selector_str}={name}"
        else:
            selector = selector_str

        if selector_type == "label":
            label_selector = selector
        else:
            field_selector = selector

    vlist, status = \
        kh.get_list_by_kind_namespace((kind, api_family),
                                      namespace,
                                      label_selector=label_selector,
                                      field_selector=field_selector,
                                      resource_cache=kh_cache)

    tmp: list[tuple[str, ...]] = []
    if vlist is None or status != 200:
        return tmp

    for item in vlist:
        entry = []
        for field_path in field_paths:
            entry.append(deep_get(item, DictPath(field_path)))
        tmp.append(tuple(entry))

    return tmp


def get_events(obj: dict, **kwargs: Any) -> list[dict]:
    """
    Get a list of events.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
        Returns:
            ([dict]): A list of events
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("get_events() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    event_list = []

    kind = deep_get(obj, DictPath("kind"))
    api_version = deep_get(obj, DictPath("apiVersion"), "")
    name = deep_get(obj, DictPath("metadata#name"))
    namespace = deep_get(obj, DictPath("metadata#namespace"), "")
    tmp = kh.get_events_by_kind_name_namespace(kh.kind_api_version_to_kind(kind, api_version),
                                               name, namespace, resource_cache=kh_cache)
    for event in tmp:
        event_list.append({
            "fields": event,
        })

    return event_list


def get_image_list(obj: dict, **kwargs: Any) -> list[tuple[str, str]]:
    """
    Get a list of container images.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                path (str): The path to the image list
        Returns:
            ([dict]): A list of container images
    """
    vlist = []
    path = deep_get(kwargs, DictPath("path"), "")

    for image in deep_get(obj, DictPath(path), []):
        name = ""
        for name in deep_get(image, DictPath("names"), []):
            # This is the preferred name
            if "@sha256:" not in name:
                break

        if not name:
            continue
        size = disksize_to_human(deep_get(image, DictPath("sizeBytes"), "0"))
        vlist.append((name, size))
    return cast(list[tuple[str, str]], natsorted(vlist))


def get_key_value(obj: dict, **kwargs: Any) -> list[tuple[str, Any]]:
    """
    Get a list of key/value data.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                path (str): The path to the key/value-pairs to get
        Returns:
            ([dict]): A list of key/value data
        Raises:
            TypeError: The type for value is not supported by get_key_value()
    """
    vlist = []

    if (path := deep_get(kwargs, DictPath("path"), "")):
        d = deep_get(obj, DictPath(path), {})

        for key_, value_ in d.items():
            if isinstance(value_, (list, tuple)):
                value = ",".join(value_)
            elif isinstance(value_, dict):
                value = ",".join(f"{key}:{val}" for (key, val) in value_.items())
            # We do not need to check for bool, since it is a subclass of int,
            # and str(str) == str
            elif isinstance(value_, (int, float, str)):
                value = str(value_)
            else:
                raise TypeError(f"Unhandled type {type(value_)} for {key_}={value_}")
            vlist.append((key_, value))
    return vlist


# pylint: disable-next=too-many-branches
def get_list_as_list(obj: dict, **kwargs: Any) -> list[Any]:
    """
    Get data in list format.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                path (str): The path to the list
        Returns:
            ([dict]): A list of data
    """
    vlist: list[Any] = []
    # pylint: disable-next=too-many-nested-blocks
    if "path" in kwargs:
        raw_path = deep_get(kwargs, DictPath("path"))
        if isinstance(raw_path, str):
            raw_path = [raw_path]
        paths = []
        for path in raw_path:
            paths.append(DictPath(path))
        _regex = deep_get(kwargs, DictPath("regex"))
        if _regex is not None:
            compiled_regex = re.compile(_regex)
        for item in deep_get_with_fallback(obj, paths, []):
            if not item:
                continue
            if _regex is not None:
                tmp = compiled_regex.match(item)
                if tmp is not None:
                    tmp2 = []
                    for group in tmp.groups():
                        if group is not None:
                            tmp2.append(group)
                    vlist.append(tmp2)
            else:
                vlist.append([item])
    elif "paths" in kwargs:
        # lists that run out of elements will return ""
        # strings will be treated as constants and thus returned for every row
        paths = deep_get(kwargs, DictPath("paths"), [])
        maxlen = 0
        for column in paths:
            tmp = deep_get(obj, DictPath(column))
            if isinstance(tmp, list):
                maxlen = max(len(tmp), maxlen)
        for i in range(0, maxlen):
            item = []
            for column in paths:
                tmp = deep_get(obj, DictPath(column))
                if isinstance(tmp, str):
                    item.append(tmp)
                elif isinstance(tmp, list):
                    if len(tmp) > i:
                        item.append(tmp[i])
                    else:
                        item.append(" ")
            vlist.append(item)
    return vlist


# pylint: disable-next=too-many-locals
def get_dict_list(obj: dict, **kwargs: Any) -> list[Any]:
    """
    Given a path to a dict (or a list of dicts), generate a list with all items
    as a list of dicts with the key and the value in the fields as "key" and "value",
    respectively, where value can itself be any type, not just simple types;
    fields is then used to further specify the path to the individual fields
    to form the final list from.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                path (str): The path to the dict
        Returns:
            list[dict]: A list of data
    """
    vlist: list[Any] = []
    tmp_vlist = []

    path: Union[str, DictPath] = deep_get(kwargs, DictPath("path"))
    fields = deep_get(kwargs, DictPath("fields"))

    data: Union[dict, list[dict]] = deep_get(obj, DictPath(path), [])

    if isinstance(data, dict):
        data = [data]

    for item in data:
        for key, value in item.items():
            tmp_vlist.append({"key": key, "value": value})

    # pylint: disable-next=too-many-nested-blocks
    for item in tmp_vlist:
        newobj: list[tuple] = []
        for field in fields:
            if isinstance(field, dict):
                field_ = deep_get(field, DictPath("field"), "")
                field_regex = deep_get(field, DictPath("regex"), "")
                if (tmp := deep_get(item, DictPath(field_))) is not None:
                    tmp = str(tmp)
                    if field_regex:
                        tmp2 = re.match(field_regex, tmp)
                        if tmp2 is not None:
                            tmp = tmp2.group(1)
                        else:
                            tmp = " "
                else:
                    tmp = " "
            else:
                if (tmp := deep_get(item, DictPath(field))) is not None:
                    tmp = str(tmp)
                else:
                    tmp = " "
            newobj.append(tmp)
        vlist.append(tuple(newobj))
    return vlist


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def get_list_fields(obj: dict, **kwargs: Any) -> list[Any]:
    """
    Get the specified fields from a dict list in list format.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                path (str): The path to the dict
        Returns:
            list[dict]: A list of data
    """
    vlist: list[Any] = []

    # pylint: disable-next=too-many-nested-blocks
    if "path" in kwargs and "fields" in kwargs:
        raw_path = deep_get(kwargs, DictPath("path"))
        if isinstance(raw_path, str):
            raw_path = [raw_path]
        paths = []
        for path in raw_path:
            paths.append(DictPath(path))
        fields = deep_get(kwargs, DictPath("fields"), [])
        pass_ref = deep_get(kwargs, DictPath("pass_ref"), False)
        override_types = deep_get(kwargs, DictPath("override_types"), [])
        for item_index, item in enumerate(deep_get_with_fallback(obj, paths, [])):
            tmp = []
            for i, field in enumerate(fields):
                default = ""
                value_type = "value"
                quote = False
                index_template = "<<<index>>>"
                if isinstance(field, dict):
                    default = deep_get(field, DictPath("default"), "")
                    index_template = deep_get(field, DictPath("index_template"), "<<<index>>>")
                    value_type = deep_get(field, DictPath("value"), "value")
                    quote = deep_get(field, DictPath("quote"), False)
                    # Needs to be last here, since it overwrites field
                    field = deep_get(field, DictPath("name"), "")

                # Instead of inserting a field here we insert a field containing list index
                if value_type == "index":
                    index_str = cmtlib.substitute_string(index_template,
                                                         {"<<<index>>>": str(item_index)})
                    tmp.append(index_str)
                    continue

                if isinstance(field, str):
                    field = [DictPath(field)]

                value_ = deep_get_with_fallback(item, field, default)
                if value_type == "key":
                    for key in field:
                        if key in item:
                            value = key
                elif (isinstance(value_, list)
                        or (i < len(fields) and i < len(override_types)
                            and override_types[i] == "list")):
                    value = ", ".join(value_)
                elif (isinstance(value_, dict)
                        or (i < len(fields) and i < len(override_types)
                            and override_types[i] == "dict")):
                    value = ", ".join(f"{key}:{val}" for (key, val) in value_.items())
                # We do not need to check for bool, since it is a subclass of int
                elif (isinstance(value_, (int, float))
                        or (i < len(fields) and i < len(override_types)
                            and override_types[i] == "str")):
                    value = str(value_)
                elif isinstance(value_, str):
                    if (i < len(fields) and i < len(override_types)
                            and override_types[i] == "timestamp"):
                        if value_ is None:
                            value = "<unset>"
                        else:
                            timestamp = timestamp_to_datetime(value_)
                            value = f"{timestamp.astimezone():%Y-%m-%d %H:%M:%S}"
                    elif (i < len(fields) and i < len(override_types)
                            and override_types[i] == "age"):
                        if value_ is None:
                            value = "<unset>"
                        else:
                            timestamp = timestamp_to_datetime(value_)
                            value = cmtlib.seconds_to_age(get_since(timestamp))
                    else:
                        value = value_
                else:
                    raise ValueError(f"Unhandled type {type(value_)} for {field}={value}")
                if quote:
                    value = f"\"{value}\""
                tmp.append(value)
            if pass_ref:
                vlist.append({"fields": tmp, "ref": item})
            else:
                vlist.append(tmp)
    return vlist


def get_package_version_list(obj: dict, **kwargs: Any) -> Optional[list[tuple[str, str]]]:
    """
    Get the package version list.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                name_path (str): The path to the name of the node
        Returns:
            ([(str, str)]): A list of package versions
    """
    name_path = deep_get(kwargs, DictPath("name_path"), "")
    hostname = deep_get(obj, DictPath(name_path))
    hostname = deep_get(kwargs, DictPath("name"), hostname)
    try:
        package_versions = get_package_versions(hostname)
    except ValueError:
        package_versions = None
    return package_versions


# pylint: disable-next=too-many-locals,too-many-branches
def get_pod_affinity(obj: dict, **kwargs: Any) -> list[tuple[str, str, str, str, str]]:
    """
    Get a list of pod affinities.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
        Returns:
            ([dict]): A list of conditions
    """
    affinities: list[tuple[str, str, str, str, str]] = []
    path: str = deep_get(kwargs, DictPath("path"), "spec#affinity")

    for affinity in deep_get(obj, DictPath(path), []):
        atype = affinity
        policy_regex = re.compile(r"^(ignored|preferred|required)DuringScheduling"
                                  r"(Ignored|Preferred|Required)DuringExecution$")

        for policy in deep_get(obj, DictPath(f"{path}#{atype}"), ""):
            tmp = policy_regex.match(policy)
            if tmp is None:
                scheduling = "Unknown"
                execution = "Unknown"
            else:
                scheduling = tmp[1].capitalize()
                execution = tmp[2]

            selectors = ""
            for item in deep_get(obj, DictPath(f"{path}#{atype}#{policy}"), []):
                items = []
                topology = ""
                if isinstance(item, dict):
                    items = [item]
                elif isinstance(item, str):
                    items = deep_get(obj, DictPath(f"spec#affinity#{atype}#{policy}#{item}"), [])

                for selector in items:
                    weight = deep_get(selector, DictPath("weight"), "")
                    if isinstance(weight, int):
                        weight = f"/{weight}"
                    topology = deep_get_with_fallback(selector,
                                                      [DictPath("podAffinityTerm#topologyKey"),
                                                       DictPath("topologyKey")], "")
                    # We are combining a few different policies,
                    # so the expressions can be in various places; not simultaneously though
                    # hence += should be OK.
                    # The best thing would probably be to use deep_get_with_fallback though.
                    paths = [
                        DictPath("podAffinityTerm#labelSelector#matchExpressions"),
                        DictPath("podAffinityTerm#labelSelector#matchFields"),
                        DictPath("labelSelector#matchExpressions"),
                        DictPath("labelSelector#matchFields"),
                        DictPath("labelSelector#matchLabels"),
                        DictPath("preference#matchExpressions"),
                        DictPath("preference#matchFields"),
                        DictPath("matchExpressions"),
                        DictPath("matchFields"),
                    ]

                    tmp2 = deep_get_with_fallback(selector, paths)

                    if tmp2 is None:
                        continue
                    if isinstance(tmp2, list):
                        selectors = make_set_expression(tmp2)
                    elif isinstance(tmp2, dict):
                        selectors = make_label_selector(tmp2)
                    else:
                        # XXX: We have no idea how to handle this
                        continue
                    affinities.append((atype, f"{scheduling}{weight}",
                                       execution, selectors, topology))
    return affinities


# pylint: disable-next=too-many-locals,too-many-branches
def get_pod_configmaps(obj: dict, **kwargs: Any) -> Optional[list[tuple[str, str]]]:
    """
    Get a list of all pods referencing a configmap.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
        Returns:
            ([(str, str)]):
                (str): Namespace of the pod using this ConfigMap
                (str): Name of the pod using this ConfigMap
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("get_pod_configmaps() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    cm_namespace = deep_get(kwargs, DictPath("cm_namespace"))
    if isinstance(cm_namespace, list):
        cm_namespace = deep_get_with_fallback(obj, cm_namespace)
    cm_name = deep_get(kwargs, DictPath("cm_name"))
    if isinstance(cm_name, list):
        cm_name = deep_get_with_fallback(obj, cm_name)
    pod_name = deep_get(kwargs, DictPath("pod_name"))
    if isinstance(pod_name, list):
        pod_name = deep_get_with_fallback(obj, pod_name)
    if cm_namespace is None or cm_name is None:
        return None

    vlist = []

    field_selector = ""
    if pod_name is not None and pod_name:
        field_selector = f"metadata.name={pod_name}"

    plist, _status = kh.get_list_by_kind_namespace(("Pod", ""),
                                                   cm_namespace,
                                                   field_selector=field_selector,
                                                   resource_cache=kh_cache)

    plist = cast(list, plist)

    for item in plist:
        pod_name = deep_get(item, DictPath("metadata#name"), "")
        matched = False
        for volume in deep_get(item, DictPath("spec#volumes"), []):
            if deep_get(volume, DictPath("configMap#name"), "") == cm_name:
                matched = True
                vlist.append((cm_namespace, pod_name))
                break
            for source in deep_get(volume, DictPath("projected#sources"), []):
                if deep_get(source, DictPath("configMap#name"), "") == cm_name:
                    matched = True
                    vlist.append((cm_namespace, pod_name))
                    break
            if matched:
                break
        if matched:
            continue
        for container in deep_get(item, DictPath("spec#containers"), []):
            for env in deep_get(container, DictPath("env"), []):
                if deep_get(env, DictPath("ValueFrom#configMapKeyRef#name"), "") == cm_name:
                    matched = True
                    vlist.append((cm_namespace, pod_name))
                    break
            if matched:
                break
            for env_from in deep_get(container, DictPath("envFrom"), []):
                if deep_get(env_from, DictPath("configMapKeyRef#name"), "") == cm_name:
                    vlist.append((cm_namespace, pod_name))
                    break

    if not vlist:
        return None

    return vlist


# pylint: disable-next=too-many-locals
def get_prepopulated_list(obj: dict, **kwargs: Any) -> list[dict]:
    """
    Get a prepopulated list of actions;
    this itemgetter can be used, for instance, to populate
    a list of actions that can be performed on an object.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                items ([Any]): The data to populate the list from
        Returns:
            ([dict]): A list of prepulated items
    """
    items = deep_get(kwargs, DictPath("items"), [])

    vlist: list[dict] = []

    for item in items:
        action = deep_get(item, DictPath("action"))
        action_call = deep_get(item, DictPath("action_call"))
        action_args = deep_get(item, DictPath("action_args"), {})
        kind = deep_get(action_args, DictPath("kind"))
        kind_path = deep_get(action_args, DictPath("kind_path"))
        kind = deep_get(obj, DictPath(kind_path), kind)
        api_family = deep_get(action_args, DictPath("api_family"), "")
        api_family_path = deep_get(action_args, DictPath("api_family_path"))
        api_family = deep_get(obj, DictPath(api_family_path), api_family)
        name_path = deep_get(action_args, DictPath("name_path"))
        name = deep_get(obj, DictPath(name_path))
        namespace_path = deep_get(action_args, DictPath("namespace_path"))
        namespace = deep_get(obj, DictPath(namespace_path), "")
        kind = kubernetes_helper.guess_kind((kind, api_family))
        tmp_columns = deep_get(item, DictPath("columns"), [])
        args = deep_get(action_args, DictPath("args"), {})

        columns: list = []

        # Where necessary do path lookups
        for column in tmp_columns:
            if isinstance(column, list):
                column = deep_get_with_fallback(obj, column, "")
            columns.append(column)

        vlist.append({
            "fields": columns,
            "ref": {
                "action": action,
                "action_call": action_call,
                "action_args": {
                    "kind": kind,
                    "name": name,
                    "namespace": namespace,
                    "args": args,
                },
            },
        })

    return vlist


# pylint: disable-next=unused-argument
def get_pod_tolerations(obj: dict, **kwargs: Any) -> list[tuple[str, str, str, str, str]]:
    """
    Get a list of pod tolerations.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments (Unused)
        Returns:
            ([(str, str, str, str, str)]): A list of pod tolerations
                (str): key
                (str): operator
                (str): value
                (str): effect
                (str): timeout
    """
    tolerations: list[tuple[str, str, str, str, str]] = []

    for toleration in deep_get_with_fallback(obj, [DictPath("spec#tolerations"),
                                                   DictPath("scheduling#tolerations")], []):
        effect = deep_get(toleration, DictPath("effect"), "All")
        key = deep_get(toleration, DictPath("key"), "All")
        operator = deep_get(toleration, DictPath("operator"), "Equal")

        # Eviction timeout
        toleration_seconds = deep_get(toleration, DictPath("tolerationSeconds"))
        if toleration_seconds is None:
            timeout = "Never"
        elif toleration_seconds <= 0:
            timeout = "Immediately"
        else:
            timeout = str(toleration_seconds)

        value = deep_get(toleration, DictPath("value"), "")
        tolerations.append((key, operator, value, effect, timeout))

    return tolerations


# pylint: disable-next=unused-argument
def get_resource_list(obj: dict, **kwargs: Any) -> list[tuple[str, str, str]]:
    """
    Get a list of resources.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments (Unused)
        Returns:
            ([(str, str)]): A list of resources
                (str): Resource
                (str): Allocatable
                (str): Capacity
    """
    vlist: list[tuple[str, str, str]] = []

    for res in deep_get(obj, DictPath("status#capacity"), {}):
        capacity = deep_get(obj, DictPath(f"status#capacity#{res}"), "")
        allocatable = deep_get(obj, DictPath(f"status#allocatable#{res}"), "")
        vlist.append((res, allocatable, capacity))
    return vlist


# pylint: disable-next=unused-argument
def get_resources(obj: dict, **kwargs: Any) -> list[tuple[str, str, str]]:
    """
    Get a list of Prometheus resources.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments (Unused)
        Returns:
            ([(str, str)]): A list of resources
                (str): Resource
                (str): Type
                (str): Capacity
    """
    resources: list[tuple[str, str, str]] = []

    for limit in list(deep_get(obj, DictPath("spec#resources#limits"), {})):
        if limit == "cpu":
            resources.append(("CPU", "Limit",
                              deep_get(obj, DictPath("spec#resources#limits#cpu"))))
        elif limit == "memory":
            resources.append(("Memory", "Limit",
                              deep_get(obj, DictPath("spec#resources#limits#memory"))))
        elif limit.startswith("hugepages-"):
            resources.append((f"H{limit[1:]}", "Limit",
                              deep_get(obj, DictPath(f"spec#resources#limits#{limit}"))))

    for request in list(deep_get(obj, DictPath("spec#resources#requests"), {})):
        if request == "cpu":
            resources.append(("CPU", "Limit",
                              deep_get(obj, DictPath("spec#resources#requests#cpu"))))
        elif request == "memory":
            resources.append(("Memory", "Limit",
                              deep_get(obj, DictPath("spec#resources#requests#memory"))))
        elif request.startswith("hugepages-"):
            resources.append((f"{request.capitalize()}", "Limit",
                              deep_get(obj, DictPath(f"spec#resources#requests#{request}"))))
    return resources


def get_strings_from_string(obj: dict, **kwargs: Any) -> list[list[str]]:
    """
    Get a list of strings from a string with embedded newlines.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                path (str): The path to the string
        Returns:
            ([[str]]): A list of lists of strings
    """
    vlist = []
    if "path" in kwargs:
        path: DictPath = DictPath(deep_get(kwargs, DictPath("path"), ""))
        tmp = deep_get(obj, DictPath(path), "")
        if tmp is not None and tmp:
            for line in split_msg(tmp):
                vlist.append([line])
    return vlist


def get_endpoint_ips(subsets: list[dict]) -> list[str]:
    """
    Get a list of endpoint IPs.
    Note: this is a helper, not an itemgetter.

        Parameters:
            subsets ([dict]): The subsets to get endpoint IPs from
        Returns:
            ([str]): A list of endpoint IPs
    """
    endpoints = []
    notready = 0

    if subsets is None:
        return ["<none>"]

    for subset in subsets:
        # Keep track of whether we have not ready addresses
        if (deep_get(subset, DictPath("notReadyAddresses")) is not None
                and deep_get(subset, DictPath("notReadyAddresses"))):
            notready += 1

        if deep_get(subset, DictPath("addresses")) is None:
            continue

        for address in deep_get(subset, DictPath("addresses"), []):
            endpoints.append(deep_get(address, DictPath("ip")))

    if not endpoints:
        if notready:
            return ["<not ready>"]
        return ["<none>"]

    return endpoints


security_context_values: dict[str, list[DictPath]] = {
    "Run as User": [
        DictPath("spec#securityContext#runAsUser"),
        DictPath("spec#template#spec#securityContext#runAsUser")],
    "Run as non-Root": [
        DictPath("spec#securityContext#runAsNonRoot"),
        DictPath("spec#template#spec#securityContext#runAsNonRoot")],
    "Run as Group": [
        DictPath("spec#securityContext#runAsGroup"),
        DictPath("spec#template#spec#securityContext#runAsGroup")],
    "FS Group": [
        DictPath("spec#securityContext#fsGroup"),
        DictPath("spec#template#spec#securityContext#fsGroup")],
    "FS Group-change Policy": [
        DictPath("spec#securityContext#fsGroupChangePolicy"),
        DictPath("spec#template#spec#securityContext#fsGroupChangePolicy")],
    "Allow Privilege Escalation": [
        DictPath("spec#securityContext#allowPrivilegeEscalation"),
        DictPath("spec#template#spec#securityContext#allowPrivilegeEscalation")],
    "Capabilities": [
        DictPath("spec#securityContext#capabilities"),
        DictPath("spec#template#spec#securityContext#capabilities")],
    "Privileged": [
        DictPath("spec#securityContext#privileged"),
        DictPath("spec#template#spec#securityContext#privileged")],
    "Proc Mount": [
        DictPath("spec#securityContext#procMount"),
        DictPath("spec#template#spec#securityContext#procMount")],
    "Read-only Root Filesystem": [
        DictPath("spec#securityContext#readOnlyRootFilesystem"),
        DictPath("spec#template#spec#securityContext#readOnlyRootFilesystem")],
    "SELinux Options": [
        DictPath("spec#securityContext#seLinuxOptions"),
        DictPath("spec#template#spec#securityContext#seLinuxOptions")],
    "Seccomp Profile": [
        DictPath("spec#securityContext#seccompProfile"),
        DictPath("spec#template#spec#securityContext#seccompProfile")],
    "Windows Options": [
        DictPath("spec#securityContext#windowsOptions"),
        DictPath("spec#template#spec#securityContext#windowsOptions")],
}


# pylint: disable-next=unused-argument
def get_security_context(obj: dict, **kwargs: Any) -> list[tuple[str, str]]:
    """
    Get security context information.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments (Unused)
        Returns:
            ([(str, str)]): A list of security context information
    """
    security_policies = []

    for name, path in security_context_values.items():
        if (policy := deep_get_with_fallback(obj, path)) is not None:
            security_policies.append((name, str(policy)))

    return security_policies


# pylint: disable-next=too-many-locals
def get_svc_port_target_endpoints(obj: dict, **kwargs: Any) -> list[tuple[str, str, str, str]]:
    """
    Get the Service port target endpoints.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
        Returns:
            ([(str, str, str, str)]): A list of Service port target endpoints
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("get_svc_port_target_endpoints() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    svcname = deep_get(obj, DictPath("metadata#name"))
    svcnamespace = deep_get(obj, DictPath("metadata#namespace"))
    port_target_endpoints = []
    stype = deep_get(obj, DictPath("spec#type"))
    cluster_ip = deep_get(obj, DictPath("spec#clusterIP"))
    endpoints = []

    ref = kh.get_ref_by_kind_name_namespace(("Endpoints", ""),
                                            svcname, svcnamespace, resource_cache=kh_cache)
    endpoints = get_endpoint_ips(deep_get(ref, DictPath("subsets")))

    for port in deep_get(obj, DictPath("spec#ports"), []):
        name = deep_get(port, DictPath("name"), "")
        svcport = deep_get(port, DictPath("port"), "")
        protocol = deep_get(port, DictPath("protocol"), "")
        if stype in ("NodePort", "LoadBalancer"):
            node_port = deep_get(port, DictPath("nodePort"), "Auto Allocate")
        else:
            node_port = "N/A"
        if cluster_ip is not None:
            target_port = deep_get(port, DictPath("targetPort"), "")
        else:
            target_port = ""
        endpointstr = f":{target_port}, ".join(endpoints)
        if endpointstr:
            endpointstr += f":{target_port}"
        port_target_endpoints.append((f"{name}:{svcport}/{protocol}",
                                      f"{node_port}", f"{target_port}/{protocol}", endpointstr))

    if not port_target_endpoints:
        port_target_endpoints = [("<none>", "", "", "")]

    return port_target_endpoints


def get_pv_type(obj: dict) -> Optional[str]:
    """
    Given a volume object, return its type.
    Note: this is a helper, not an itemgetter.

        Parameters:
            obj (dict): The object to get data from
        Returns:
            (str): The volume type
    """
    for pv_type, _pv_data in KNOWN_PV_TYPES.items():
        if pv_type in deep_get(obj, DictPath("spec"), {}):
            return pv_type
    return None


# pylint: disable-next=unused-argument
def get_volume_properties(obj: dict, **kwargs: Any) -> list[tuple[str, str]]:
    """
    Get the properties for a persistent volume.

        Parameters:
            obj (dict): The object to get data from
            **kwargs (dict[str, Any]): Keyword arguments (Unused)
        Returns:
            ([(str, str)]): A list of volume properties
    """
    volume_properties: list[tuple[str, str]] = []

    # First find out what kind of volume we are dealing with
    pv_type = get_pv_type(obj)
    if pv_type is None:
        return volume_properties

    properties = deep_get(KNOWN_PV_TYPES, DictPath(f"{pv_type}#properties"), {})
    for key in properties:
        default = deep_get(properties, DictPath(f"{key}#default"), "")
        path = deep_get(properties, DictPath(f"{key}#path"), "")
        value = deep_get(obj, DictPath(f"spec#{pv_type}#{path}"), default)
        if isinstance(value, list):
            value = ",".join(value)
        elif isinstance(value, dict):
            value = ",".join(f"{key}:{val}" for (key, val) in value.items())
        # We do not need to check for bool, since it is a subclass of int
        elif isinstance(value, (int, float, str)):
            value = str(value)
        else:
            raise TypeError(f"Unhandled type {type(value)} for {key}={value}")
        volume_properties.append((key, value))

    return volume_properties


# Itemgetters acceptable for direct use in view files
itemgetter_allowlist: dict[str, Callable] = {
    "get_conditions": get_conditions,
    "get_kubernetes_objects": get_kubernetes_objects,
    "get_events": get_events,
    "get_image_list": get_image_list,
    "get_key_value": get_key_value,
    "get_list_as_list": get_list_as_list,
    "get_dict_list": get_dict_list,
    "get_list_fields": get_list_fields,
    "get_package_version_list": get_package_version_list,
    "get_pod_affinity": get_pod_affinity,
    "get_pod_configmaps": get_pod_configmaps,
    "get_prepopulated_list": get_prepopulated_list,
    "get_pod_tolerations": get_pod_tolerations,
    "get_resource_list": get_resource_list,
    "get_resources": get_resources,
    "get_strings_from_string": get_strings_from_string,
    "get_security_context": get_security_context,
    "get_svc_port_target_endpoints": get_svc_port_target_endpoints,
    "get_volume_properties": get_volume_properties,
}
