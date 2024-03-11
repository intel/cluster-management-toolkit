#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Get information
"""

from typing import Any, Dict, List, Tuple, Type

import cmtlib
from cmttypes import deep_get, DictPath, ProgrammingError
import itemgetters
import datagetters
from kubernetes_helper import get_node_roles, get_node_status, get_containers
from kubernetes_helper import get_controller_from_owner_references, get_pod_restarts_total


def format_controller(controller: Tuple[Tuple[str, str], str], show_kind: str) -> Tuple[str, str]:
    """
    Reformat a controller kind + name tuple

        Parameters:
            controller ((str, str), str): The controller kind
            show_kind (str): "short" / "full" / "mixed"
        Returns:
            (str, str): A tuple with a possibly reformatted controller kind + name
    """
    if show_kind:
        if show_kind == "short" or not controller[0][1]:
            fmt_controller = (f"{controller[0][0]}", f"{controller[1]}")
        elif show_kind == "full":
            fmt_controller = (f"{controller[0][0]}.{controller[0][1]}", f"{controller[1]}")
        elif show_kind == "mixed":
            # Strip the API group for standard controllers,
            # but show for custom controllers
            if controller[0] in (("StatefulSet", "apps"), ("ReplicaSet", "apps"),
                                 ("DaemonSet", "apps"), ("Job", "batch"),
                                 ("CronJob", "batch"), ("Node", "")):
                fmt_controller = (f"{controller[0][0]}", f"{controller[1]}")
            else:
                fmt_controller = (f"{controller[0][0]}.{controller[0][1]}", f"{controller[1]}")
        else:
            raise ValueError(f"unknown value passed to show_kind: {show_kind}")
    else:
        fmt_controller = ("", f"{controller[1]}")

    return fmt_controller


# pylint: disable-next=too-many-locals
def get_pod_info(**kwargs: Any) -> List[Type]:
    """
    Infogetter for Pods

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                in_depth_node_status (bool): Should in-depth node status be shown?
                extra_vars (dict): Extra variables
                filters ([dict]): A dict of filters to apply
        Returns:
            ([InfoClass]): A list with info
    """
    in_depth_node_status: bool = deep_get(kwargs, DictPath("in_depth_node_status"), True)
    extra_vars: Dict[str, Any] = deep_get(kwargs, DictPath("extra_vars"),
                                          {"show_kind": "", "show_evicted": True})
    filters: List[Dict[str, Any]] = deep_get(kwargs, DictPath("filters"), [])
    info: List[Type] = []

    if not (vlist := deep_get(kwargs, DictPath("vlist"))):
        return []

    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("get_kubernetes_list() called without kubernetes_helper")
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
                cmtlib.timestamp_to_datetime(deep_get(obj, DictPath("metadata#creationTimestamp")))
            age = cmtlib.get_since(timestamp)

            owr = deep_get(obj, DictPath("metadata#ownerReferences"), [])
            controller_ = get_controller_from_owner_references(owr)
            show_kind = deep_get(extra_vars, DictPath("show_kind"), "").lower()
            controller = format_controller(controller_, show_kind)

            pod_ip = deep_get(obj, DictPath("status#podIP"), "<unset>")
            pod_restarts, restarted_at = get_pod_restarts_total(obj)
            if restarted_at == -1:
                last_restart = -1
            else:
                last_restart = cmtlib.get_since(restarted_at)
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


# pylint: disable-next=unused-argument,too-many-locals
def get_node_info(**kwargs: Any) -> List[Type]:
    """
    Infogetter for Nodes

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                vlist ([dict[str, Any]]): The list of Node objects
        Returns:
            info (list[InfoClass]): A list with info
    """
    info: List[Type] = []

    if (vlist := deep_get(kwargs, DictPath("vlist"))) is None or not vlist:
        return []

    for obj in vlist:
        # For now we do not do anything with external IPs; we should
        name, internal_ips, _external_ips = \
            get_node_addresses(deep_get(obj, DictPath("status#addresses")))
        ref = obj
        kubernetes_roles = get_node_roles(obj)
        timestamp = \
            cmtlib.timestamp_to_datetime(deep_get(obj, DictPath("metadata#creationTimestamp")))
        age = cmtlib.get_since(timestamp)
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


def get_node_addresses(addresses: List[Dict]) -> Tuple[str, List[str], List[str]]:
    """
    Given the addresses list return all internal/external IPs and the hostname

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
                pass
                # debuglog.add([
                #         [ANSIThemeString("We need to handle multiple hostnames "
                #                          "in a better way", "default")],
                #        ], severity = LogLevel.ERR)
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
