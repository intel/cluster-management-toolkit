#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Get information
"""

import base64
from typing import Any, Type

from clustermanagementtoolkit import cmtlib

from clustermanagementtoolkit.cmttypes import deep_get, deep_set, DictPath
from clustermanagementtoolkit.cmttypes import ProgrammingError, StatusGroup

from clustermanagementtoolkit import itemgetters

from clustermanagementtoolkit import datagetters

from clustermanagementtoolkit.kubernetes_helper import get_node_roles, get_node_status
from clustermanagementtoolkit.kubernetes_helper import get_containers
from clustermanagementtoolkit.kubernetes_helper import get_controller_from_owner_references
from clustermanagementtoolkit.kubernetes_helper import get_pod_restarts_total


def format_controller(controller: tuple[tuple[str, str], str], show_kind: str) -> tuple[str, str]:
    """
    Reformat a controller kind + name tuple

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


# pylint: disable-next=too-many-locals
def get_pod_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for Pods

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


# pylint: disable-next=too-many-locals
def get_node_info(**kwargs: Any) -> list[Type]:
    """
    Infogetter for Nodes

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


def get_node_addresses(addresses: list[dict]) -> tuple[str, list[str], list[str]]:
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
                #         [ANSIThemeStr("We need to handle multiple hostnames "
                #                       "in a better way", "default")],
                #        ], severity=LogLevel.ERR)
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
    Infogetter for Istio Authorization Policy Rules

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
    Infogetter for EndpointSlice subsets

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
    Infogetter for key/value-based information

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
    Infogetter for Limits

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
    Infogetter for Prometheus Rules

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
    Infogetter for Resource Quotas

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
    Infogetter for Service Account secrets

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
    Infogetter for Telemetry Aware Scheduling policies

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
    Infogetter for Endpoint subsets

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
    This is effectively a noop, but we need to have an infogetter

        Parameters:
            obj (dict): The themearrays object
            **kwargs (dict[str, Any]): Keyword arguments (Unused)
        Returns:
            (dict): The themearrays
    """
    return obj
