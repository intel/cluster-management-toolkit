#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Datagetters are used for data extraction that is too complex
to be expressed through parameters to generic_infogetter()
"""

import re
from typing import Any
from collections.abc import Callable

from clustermanagementtoolkit.cmtlib import get_since, timestamp_to_datetime

from clustermanagementtoolkit.cmttypes import deep_get, deep_get_with_fallback, DictPath
from clustermanagementtoolkit.cmttypes import StatusGroup, ProgrammingError

from clustermanagementtoolkit.kubernetes_helper import get_node_status
from clustermanagementtoolkit.kubernetes_helper import kind_tuple_to_name, guess_kind


# pylint: disable-next=too-many-branches
def get_container_status(src_statuses: list[dict],
                         container: str) -> tuple[str, StatusGroup, int, str, int]:
    """
    Return the status for a container.

        Parameters:
            src_statuses (dict): A reference to either
                                 status#containerStatuses,
                                 status#initContainerStatuses, or
                                 status#ephemeralContainerStatuses
            container (str): The name of the container
        Returns:
            (str, StatusGroup, int, str, int):
                (str): Reason for the status
                (StatusGroup): Status group
                (int): How many times has the container been restarted
                (str): Status message, if any
                (int): Age of the container
    """
    reason = "UNKNOWN"
    status_group = StatusGroup.UNKNOWN
    restarts = 0
    message = ""
    age = -1

    if src_statuses is None or not src_statuses:
        return reason, status_group, -1, message, -1

    for container_status in src_statuses:
        if deep_get(container_status, DictPath("name")) == container:
            restarts = deep_get(container_status, DictPath("restartCount"))
            running = deep_get(container_status, DictPath("state#running"))
            ts = deep_get_with_fallback(container_status, [
                DictPath("state#terminated#finishedAt"),
                DictPath("lastState#terminated#finishedAt"),
                DictPath("state#running#startedAt")], "")
            age = get_since(timestamp_to_datetime(ts))

            if not deep_get(container_status, DictPath("ready")):
                status_group = StatusGroup.NOT_OK

                if running is not None:
                    reason = "Running"
                elif deep_get(container_status, DictPath("state#terminated")) is not None:
                    reason = deep_get(container_status,
                                      DictPath("state#terminated#reason"), "ErrNotSet")
                    if not deep_get(container_status, DictPath("state#terminated#exitCode")):
                        status_group = StatusGroup.DONE

                    if deep_get(container_status,
                                DictPath("state#terminated#message")) is not None:
                        message = deep_get(container_status,
                                           DictPath("state#terminated#message"), "").rstrip()
                else:
                    reason = deep_get(container_status,
                                      DictPath("state#waiting#reason"), "").rstrip()

                    if deep_get(container_status,
                                DictPath("state#waiting#message")) is not None:
                        message = deep_get(container_status,
                                           DictPath("state#waiting#message"), "").rstrip()
            else:
                if running is None:
                    reason = deep_get(container_status,
                                      DictPath("state#terminated#reason"), "").rstrip()

                    if deep_get(container_status,
                                DictPath("state#terminated#message")) is not None:
                        message = deep_get(container_status,
                                           DictPath("state#terminated#message"), "").rstrip()

                    if not deep_get(container_status, DictPath("state#terminated#exitCode")):
                        status_group = StatusGroup.DONE
                    else:
                        status_group = StatusGroup.NOT_OK
                else:
                    reason = "Running"
                    status_group = StatusGroup.OK
            break

    return reason, status_group, restarts, message, age


# pylint: disable-next=unused-argument
def datagetter_container_status(obj: dict[str, Any], **kwargs: Any) -> tuple[StatusGroup, dict]:
    """
    A datagetter that returns the status of a container.

        Parameters:
            obj (dict): The container object to get status for
            **kwargs (dict[str, Any]): Keyword arguments [unused]
    """
    if obj is None:
        return "UNKNOWN", {"status_group": StatusGroup.UNKNOWN}

    status = deep_get(obj, DictPath("status"))
    status_group = deep_get(obj, DictPath("status_group"))

    return status, {"status_group": status_group}


# pylint: disable-next=unused-argument
def get_endpointslices_endpoints(obj: dict[str, Any],
                                 **kwargs: Any) -> list[tuple[str, StatusGroup]]:
    """
    Get the endpoints for an endpoint slice.

        Parameters:
            obj (dict): The endpoint slice object to return endpoints for
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ([(str, StatusGroup)]): A list of (address, status) for each endpoint
    """
    endpoints = []
    for endpoint in deep_get(obj, DictPath("endpoints"), []):
        for address in deep_get(endpoint, DictPath("addresses"), []):
            ready = deep_get(endpoint, DictPath("conditions#ready"), False)
            if ready:
                status_group = StatusGroup.OK
            else:
                status_group = StatusGroup.NOT_OK
            endpoints.append((address, status_group))
    if not endpoints:
        endpoints.append(("<none>", StatusGroup.UNKNOWN))
    return endpoints


# pylint: disable-next=unused-argument
def datagetter_eps_endpoints(obj: dict[str, Any],
                             **kwargs: Any) -> tuple[list[tuple[str, StatusGroup]], dict]:
    """
    A datagetter that returns the endpoints for an endpoint slice.

        Parameters:
            obj (dict): The endpoint slice object to return endpoints for
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            The return value from get_endpointslices_endpoints and an empty dict
    """
    return get_endpointslices_endpoints(obj), {}


def datagetter_metrics(obj: dict[str, Any], **kwargs: Any) -> tuple[list[str], dict]:
    """
    A datagetter that returns metrics for the specified path.

        Parameters:
            obj (dict): The object with metrics
            **kwargs (dict[str, Any]): Keyword arguments
                path (DictPath): The path to the metrics to get
                default ([str]): The list to return if obj or path is None
        Returns:
            result ([str]), {} (dict): A list with metrics and an empty dict
    """
    path = deep_get(kwargs, DictPath("path"))
    default: list[str] = deep_get(kwargs, DictPath("default"), [])

    if obj is None or not obj or path is None:
        return default, {}

    result = []

    for field in path:
        result.append(deep_get(obj, DictPath(f"fields#{field}"), ""))

    return result, {}


def datagetter_deprecated_api(obj: dict[str, Any],
                              **kwargs: Any) -> tuple[tuple[str, str, str], dict]:
    """
    A datagetter that returns deprecated API information for the specified path.

        Parameters:
            obj (dict): The object with metrics
            kwargs (dict):
        **kwargs (dict[str, Any]): Keyword arguments
            path (str): The path to the metrics to get
            default ([str]): The list to return if obj or path is None
        Returns:
            (str, str, [str], dict):
                (str): Kind for the deprecated API
                (str): API-family for the deprecated API
                ([str]): Metrics for the deprecated API
                (dict): Additional vars
    """
    path = deep_get(kwargs, DictPath("path"))
    default = deep_get(kwargs, DictPath("default"), [])

    result, extra_vars = datagetter_metrics(obj, path=path, default=default)
    kind, api_family = guess_kind((result[0], result[1]))
    return (kind, api_family, result[2]), extra_vars


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def datagetter_latest_version(obj: dict[str, Any],
                              **kwargs: Any) -> tuple[tuple[str, str, str], dict]:
    """
    A datagetter that returns the latest available API for kind as passed in path.

        Parameters:
            obj (dict): The object to get the old API information from
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
                path ([kind_path, api_family_path, old_version_path)]:
                                         Paths to Kind, API-family, and the old version of the API
                default: Unused?
        Returns:
            (str, str, str, dict):
                (str): new API-group (since it might change)
                (str): The latest version of the API, or old_version if no newer version available
                (str): If the API is deprecated, the deprecation message (if one available),
                       or a default message (if not)
                (dict): An empty dict
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("datagetter_latest_version() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    path = deep_get(kwargs, DictPath("path"))
    default = deep_get(kwargs, DictPath("default"), ("", "", ""))

    if obj is None or path is None:
        return default, {}

    # path is paths to kind, api_family
    kind = deep_get(obj, DictPath(path[0]))
    api_family = deep_get(obj, DictPath(path[1]))
    old_version = deep_get(obj, DictPath(path[2]))
    kind = guess_kind((kind, api_family))

    latest_api = kh.get_latest_api(kind)
    if "/" in latest_api:
        group, version = latest_api.split("/")
    else:
        group = ""
        version = latest_api

    message = ""

    # Check if there's a deprecation message in the CRD
    ref = kh.get_ref_by_kind_name_namespace(("CustomResourceDefinition", "apiextensions.k8s.io"),
                                            kind_tuple_to_name(kind), "", resource_cache=kh_cache)

    if ref is not None:
        versions: dict = {}
        sorted_versions = []

        for version_entry in deep_get(ref, DictPath("spec#versions"), {}):
            version_name = deep_get(version_entry, DictPath("name"), "")
            deprecated = deep_get(version_entry, DictPath("deprecated"), False)
            deprecation_message = deep_get(version_entry, DictPath("deprecationWarning"), "")
            versions[version_name] = {
                "deprecated": deprecated,
                "deprecation_message": deprecation_message
            }
        # Kubernetes versions come in three different types
        # vX, vXbetaX, and vXalphaX
        version_regex = re.compile(r"^v(\d+)($|beta\d+|alpha\d+)$")
        tmp_versions = []
        for version in versions:
            tmp = version_regex.match(version)
            if tmp is None:
                raise ValueError(f"Failed to parse version number {version}")
            try:
                major = int(tmp[1])
            except ValueError as e:
                raise ValueError(f"Failed to parse version number {version}") from e
            if tmp[2] == "":
                minor = 0
                patch = 0
            elif tmp[2].startswith("beta"):
                minor = -1
                try:
                    patch = int(tmp[2].removeprefix("beta"))
                except ValueError as e:
                    raise ValueError(f"Failed to parse version number {version}") from e
            elif tmp[2].startswith("alpha"):
                minor = -2
                try:
                    patch = int(tmp[2].removeprefix("alpha"))
                except ValueError as e:
                    raise ValueError(f"Failed to parse version number {version}") from e
            else:
                raise ValueError(f"Failed to parse version number {version}")
            tmp_versions.append((major, minor, patch))
        sorted_versions = sorted(tmp_versions, reverse=True)
        latest_major = f"v{sorted_versions[0][0]}"
        latest_minor = ""
        if sorted_versions[0][1] == 0:
            latest_minor = ""
        elif sorted_versions[0][1] == -1:
            latest_minor = f"beta{sorted_versions[0][2]}"
        elif sorted_versions[0][1] == -2:
            latest_minor = f"alpha{sorted_versions[0][2]}"
        latest_version = f"{latest_major}{latest_minor}"

        if deep_get(versions, DictPath(f"{latest_version}#deprecated"), False):
            message = deep_get(versions, DictPath(f"{latest_version}#deprecation_message"), "")
            message = f"({message})"

    else:
        latest_version = version

    if old_version == latest_version and not message:
        message = "(No newer version available; the API might be deprecated)"

    return (group, latest_version, message), {}


def get_endpoint_endpoints(subsets: list[dict]) -> list[tuple[str, StatusGroup]]:
    """
    Get the endpoints for an endpoint.

        Parameters:
            subsets ([subset]): The subsets to return endpoints for
        Returns:
            ([(str, StatusGroup)]): A list of tuples with address and status for each endpoint
    """
    endpoints = []

    if subsets is None:
        subsets = []

    for subset in subsets:
        for address in deep_get(subset, DictPath("addresses"), []):
            endpoints.append((deep_get(address, DictPath("ip")), StatusGroup.OK))
        for address in deep_get(subset, DictPath("notReadyAddresses"), []):
            endpoints.append((deep_get(address, DictPath("ip")), StatusGroup.NOT_OK))

    if not endpoints:
        endpoints.append(("<none>", StatusGroup.UNKNOWN))

    return endpoints


def datagetter_endpoint_ips(obj: dict[str, Any],
                            **kwargs: Any) -> tuple[list[tuple[str, StatusGroup]], dict]:
    """
    A datagetter that returns the endpoints for an endpoint.

        Parameters:
            obj (dict): The endpoint object to return endpoints for
            **kwargs (dict[str, Any]): Keyword arguments
               (str): The path to the endpoint subsets
        Returns:
            (([(str, StatusGroup)], dict)):
                ([(str, StatusGroup)]): A list of tuples with address and status for each endpoint
                (dict): An empty dict
    """
    path = deep_get(kwargs, DictPath("path"))

    subsets = deep_get(obj, DictPath(path))
    endpoints = get_endpoint_endpoints(subsets)
    return endpoints, {}


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def get_pod_status(obj: dict[str, Any], **kwargs: Any) -> tuple[str, StatusGroup]:
    """
    Get status for a Pod.

        Parameters:
            obj (dict): The pod object to return status for
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
        Returns:
            (str, StatusGroup):
                (str): The phase of the pod
                (StatusGroup): The StatusGroup of the pod
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("get_pod_status() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    in_depth_node_status = deep_get(kwargs, DictPath("in_depth_node_status"), True)

    if deep_get(obj, DictPath("metadata#deletionTimestamp")) is not None:
        status = "Terminating"
        status_group = StatusGroup.PENDING
        return status, status_group

    phase = deep_get(obj, DictPath("status#phase"))

    if phase == "Pending":
        status = phase
        status_group = StatusGroup.PENDING

        # Any containers in ContainerCreating or similar?
        for condition in deep_get(obj, DictPath("status#conditions"), []):
            condition_type = deep_get(condition, DictPath("type"))
            condition_status = deep_get(condition, DictPath("status"))
            reason = deep_get(condition, DictPath("reason"), "")

            if condition_type == "PodScheduled" and \
                    condition_status == "False" and reason == "Unschedulable":
                status = reason
                status_group = StatusGroup.NOT_OK
                break

            if condition_type == "ContainersReady" and condition_status == "False":
                for container in deep_get(obj, DictPath("status#initContainerStatuses"), []):
                    if deep_get(container, DictPath("ready")):
                        continue
                    reason = deep_get(container, DictPath("state#waiting#reason"), "").rstrip()
                    if reason is None or not reason:
                        continue
                    if reason in ("CrashLoopBackOff", "ImagePullBackOff"):
                        status_group = StatusGroup.NOT_OK
                    status = f"Init:{reason}"
                    break
                for container in deep_get(obj, DictPath("status#containerStatuses"), []):
                    if deep_get(container, DictPath("ready")):
                        continue
                    reason = deep_get(container, DictPath("state#waiting#reason"), "").rstrip()
                    if reason is None or not reason:
                        continue
                    if reason in ("CrashLoopBackOff", "ErrImageNeverPull", "ErrImagePull"):
                        status_group = StatusGroup.NOT_OK
                    status = reason
                    break

        return status, status_group

    if phase == "Running":
        status = "Running"
        status_group = StatusGroup.OK

        # Any container failures?
        for condition in deep_get(obj, DictPath("status#conditions"), []):
            condition_type = deep_get(condition, DictPath("type"))
            condition_status = deep_get(condition, DictPath("status"))

            if condition_type == "Ready" and condition_status == "False":
                status_group = StatusGroup.NOT_OK
                status = "NotReady"
                # Can we get more info? Is the host available?
                if in_depth_node_status:
                    node_name = deep_get(obj, DictPath("spec#nodeName"))
                    node = kh.get_ref_by_kind_name_namespace(("Node", ""), node_name, "",
                                                             resource_cache=kh_cache)
                    node_status = get_node_status(node)
                    if node_status[0] == "Unreachable":
                        status = "NodeUnreachable"
                break

            if condition_type == "ContainersReady" and condition_status == "False":
                status_group = StatusGroup.NOT_OK

                for container in deep_get(obj, DictPath("status#initContainerStatuses"), []):
                    status, status_group, _restarts, _message, _age = \
                        get_container_status(deep_get(obj,
                                                      DictPath("status#initContainerStatuses")),
                                             deep_get(container, DictPath("name")))

                    # If we have a failed container,
                    # break here
                    if status_group == StatusGroup.NOT_OK:
                        break

                for container in deep_get(obj, DictPath("status#containerStatuses"), []):
                    status, status_group, _restarts, _message, _age = \
                        get_container_status(deep_get(obj, DictPath("status#containerStatuses")),
                                             deep_get(container, DictPath("name")))
                    # If we have a failed container,
                    # break here
                    if status_group == StatusGroup.NOT_OK:
                        break

        return status, status_group

    if phase == "Failed":
        # Failed
        status_group = StatusGroup.NOT_OK
        status = deep_get(obj, DictPath("status#reason"), phase).rstrip()
        return status, status_group

    # Succeeded
    status_group = StatusGroup.DONE
    return phase, status_group


def datagetter_pod_status(obj: dict[str, Any], **kwargs: Any) -> tuple[str, dict]:
    """
    A datagetter that returns the status for a pod.

        Parameters:
            obj (dict): The pod object to return pod status for
            **kwargs (dict[str, Any]): Keyword arguments
                kh (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
                default (Any): [unused]
        Returns:
            The return value from get_endpointslices_endpoints and an empty dict
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("datagetter_pod_status() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    default = deep_get(kwargs, DictPath("default"))

    if obj is None:
        return default, {}

    status, status_group = get_pod_status(obj, kubernetes_helper=kh, kh_cache=kh_cache)

    return status, {"status_group": status_group}


def datagetter_api_support(obj: dict[str, Any], **kwargs: Any) -> tuple[list[str], dict]:
    """
    A datagetter that returns the level of support that CMT provides for an API;
    can be one of:
    * Known (CMT has an API definition)
    * List (CMT has a list view)
    * Info (CMT has an info view)

        Parameters:
            obj (dict): The object to get the API-name from
            kwargs (dict):
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                default (Any): [unused]
        Returns:
            ([str], dict):
                ([str]): A list with zero or more of "Known", "List", "Info"
                (dict): An empty dict
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("datagetter_api_support() called without kubernetes_helper")

    default = deep_get(kwargs, DictPath("default"))

    if obj is None:
        return default, {}

    kind = deep_get(obj, DictPath("spec#names#kind"), "")
    api_family = deep_get(obj, DictPath("spec#group"), "")

    available_apis, _status, _modified = kh.get_available_kinds()

    available_views = []

    try:
        kind = guess_kind((kind, api_family))
        available_views.append("Known")
        if deep_get(available_apis[kind], DictPath("list"), False):
            available_views.append("List")
        if deep_get(available_apis[kind], DictPath("info"), False):
            available_views.append("Info")
    except NameError:
        pass

    if not available_views:
        available_views = default

    return available_views, {}


# Datagetters acceptable for direct use in view files
datagetter_allowlist: dict[str, Callable] = {
    "datagetter_container_status": datagetter_container_status,
    "datagetter_deprecated_api": datagetter_deprecated_api,
    "datagetter_latest_version": datagetter_latest_version,
    "datagetter_metrics": datagetter_metrics,
    "datagetter_endpoint_ips": datagetter_endpoint_ips,
    "datagetter_eps_endpoints": datagetter_eps_endpoints,
}
