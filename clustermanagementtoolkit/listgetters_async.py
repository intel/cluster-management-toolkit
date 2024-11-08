#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Get list data asynchronously
"""

import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from natsort import natsorted
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import natsort; "
             "you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

from clustermanagementtoolkit import cmtlib
from clustermanagementtoolkit.cmttypes import deep_get, DictPath, StatusGroup, ProgrammingError
from clustermanagementtoolkit import infogetters


# pylint: disable-next=unused-argument,disable-next=too-many-locals
def get_kubernetes_list(*args: Any,
                        **kwargs: Any) -> tuple[list[Any], int | str | list[StatusGroup]]:
    """
    Fetch a list of Kubernetes objects, optionally with postprocessing.

        Parameters:
            *args [Any]: Positional arguments (unused)
            **kwargs (dict[str, Any]): Keyword arguments
                kind ((str, str)): The Kubernetes kind (required)
                namespace (str): The Kubernetes namespace (optional)
                label_selector (str): A label selector (optional)
                field_selector (str): A field selector (optional)
                fetch_args (dict): Specific arguments (optional)
                    sort_key (str): The sort-key to use if sorting the list (optional)
                    sort_reverse (bool): Should the list be returned
                                         with reversed sort order? (optional)
                    postprocess (str): Post-processing (if any) to apply (optional)
                    limit (int): The max number of items to return (optional)
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                kh_cache (KubernetesResourceCache): A reference to a KubernetesResourceCache object
        Returns:
            ([dict], int|str|[StatusGroup]):
                ([dict]): A list of Kubernetes objects
                (int|str|[StatusGroup]): Server status (int),
                                         unused (str),
                                         or the individual StatusGroup for all objects
        Raises:
            ProgrammingError: Function called without kubernetes_helper
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("get_kubernetes_list() called without kubernetes_helper")
    kh_cache = deep_get(kwargs, DictPath("kh_cache"))

    kind = deep_get(kwargs, DictPath("kind"))
    namespace = deep_get(kwargs, DictPath("namespace"), "")
    label_selector = deep_get(kwargs, DictPath("label_selector"), "")
    field_selector = deep_get(kwargs, DictPath("field_selector"), "")
    fetch_args = deep_get(kwargs, DictPath("fetch_args"), {})
    sort_key: str = deep_get(fetch_args, DictPath("sort_key"), "")
    sort_reverse: bool = deep_get(fetch_args, DictPath("sort_reverse"), False)
    postprocess: str = deep_get(fetch_args, DictPath("postprocess"), "")
    postprocessor: str | Callable = deep_get(kwargs, DictPath("postprocessor"), "")
    limit = deep_get(fetch_args, DictPath("limit"))
    extra_data = []

    vlist, status = kh.get_list_by_kind_namespace(kind, namespace,
                                                  label_selector=label_selector,
                                                  field_selector=field_selector,
                                                  resource_cache=kh_cache)
    if sort_key:
        vlist = natsorted(vlist,
                          key=lambda x: deep_get(x, DictPath(sort_key), ""), reverse=sort_reverse)
    if postprocess == "node":
        vlist = infogetters.get_node_info(**{"vlist": vlist})
        extra_data = [s.status_group for s in vlist]
    elif postprocess == "pod":
        vlist = infogetters.get_pod_info(**{"vlist": vlist,
                                            "in_depth_node_status": False,
                                            "kubernetes_helper": kh})
        extra_data = [s.status_group for s in vlist]
    elif callable(postprocessor) or postprocessor in listgetter_postprocessors:
        if not callable(postprocessor):
            postprocessor = listgetter_postprocessors[postprocessor]
        vlist, extra_data = postprocessor(vlist=vlist, status=status, **kwargs)
    else:
        extra_data = status
    if limit is not None:
        vlist = vlist[:limit]
    return vlist, extra_data


def get_inventory_list() -> None:
    """
    Dummy function used as a cookie for inventory list.
    """
    return


# pylint: disable-next=too-many-locals
def get_context_list(**kwargs: Any) -> Tuple[List[Dict], List[str]]:
    """
    Get the list of Kubernetes contexts.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): The KubernetesHelper object to use (required)
                tag_prefix (str): The prefix to use for the tagged list item (optional)
        Returns:
            ([dict], [str]):
                [dict]: The list of context information
                [str]: The list of API-servers for those contexts
        Raises:
            ProgrammingError: Function called without kubernetes_helper
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("get_context_list() called without kubernetes_helper")

    vlist = []
    hosts = []

    context_list = kh.list_contexts()
    tag_prefix = deep_get(kwargs, DictPath("tag_prefix"), "✓ ")

    inventory_dict: Dict = {
        "all": {
            "hosts": {},
        }
    }

    server_address_regex = re.compile(r"^(https?://)(.+)(:\d+)$")

    for is_current_context, name, cluster, authinfo, namespace, server in context_list:
        if is_current_context:
            current = tag_prefix
        else:
            current = "".ljust(len(tag_prefix))

        server_address = ""
        tmp = server_address_regex.match(server)
        if tmp is not None:
            server_address = tmp[2]
            hosts.append(server_address)

        vlist.append({
            "current": current,
            "name": name,
            "cluster": cluster,
            "authinfo": authinfo,
            "namespace": namespace,
            "server": server,
            "server_address": server_address,
            # Before we ping the hosts their status is unknown
            "status": "UNKNOWN",
        })

        if server_address:
            inventory_dict["all"]["hosts"][server_address] = {}
            inventory_dict["all"]["hosts"][server_address]["status"] = "UNKNOWN"
            inventory_dict["all"]["vars"] = {}

    return vlist, hosts


# pylint: disable-next=too-many-branches
def add_resource(key: str, units: dict[str, list[str]],
                 resources: int | float | list[str],
                 resource: Optional[str | int | float]) -> int | float | list[str]:
    """
    Add a resource to the node resource list.

        Parameters:
            key (str): The name of the resource
            units (dict): The list of known resource types
            resources (int|float|[str]): The current resources
            resource (str|int|float): The new resource to add
        Returns:
            (int|float|[str]): The new sum/list of resources
    """
    if resource is None:
        return resources

    if key in deep_get(units, DictPath("millicores"), []) and isinstance(resources, (int, float)):
        # Either float or [str]
        try:
            resources += cmtlib.normalise_cpu_usage_to_millicores(str(resource))
        except ValueError:
            if resources == 0:
                resources = []
            if isinstance(resources, list):
                resources.append(str(resource))
    elif key in deep_get(units, DictPath("mem"), []) and isinstance(resources, (int, float)):
        # Either int or [str]
        try:
            resources += cmtlib.normalise_mem_to_bytes(str(resource))
        except ValueError:
            if resources == 0:
                resources = []
            if isinstance(resources, list):
                resources.append(str(resource))
    else:
        val = resource
        try:
            val = int(resource)
        except ValueError:
            try:
                val = float(resource)
            except ValueError:
                pass
        if isinstance(val, (int, float)) \
                and isinstance(val, (int, float)) and isinstance(resources, (int, float)):
            resources += val
        elif isinstance(resources, list):
            resources.append(str(resource))
    return resources


# pylint: disable-next=too-many-locals
def postprocessor_node_resources(**kwargs: Any) -> tuple[list[dict], int | str]:
    """
    Postprocessor for node resources. Extracts the node resources
    from the list of all nodes and sums them up and groups them by type.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                vlist ([dict]): The list of node data
                status (int|str): The status of the data fetch
                units (dict): A dict of units for various resources
        Returns:
            (([dict], int|float)):
                ([dict]): A list of dicts for each resource
                (int|str): The status of the data fetch
    """
    vlist = deep_get(kwargs, DictPath("vlist"), [])
    status = deep_get(kwargs, DictPath("status"))
    units = deep_get(kwargs, DictPath("units"), {})
    resources: Dict = {}
    vresources: List[Dict] = []

    if status == 200:
        for node in vlist:
            capacities = deep_get(node, DictPath("status#capacity"), {})
            allocatables = deep_get(node, DictPath("status#allocatable"), {})
            for key, capacity in capacities.items():
                if key not in resources:
                    resources[key] = {"capacity": 0, "allocatable": 0}
                resources[key]["capacity"] = \
                    add_resource(key, units, resources[key]["capacity"], capacity)
                resources[key]["allocatable"] = \
                    add_resource(key, units, resources[key]["allocatable"],
                                 deep_get(allocatables, DictPath(key)))
        for resource, data in resources.items():
            vresources.append({
                "name": resource,
                "allocatable": deep_get(data, DictPath("allocatable"), 0),
                "capacity": deep_get(data, DictPath("capacity"), 0),
            })

    return vresources, status


listgetter_postprocessors: Dict[str, Callable] = {
    "postprocessor_node_resources": postprocessor_node_resources,
}

# Asynchronous listgetters acceptable for direct use in view files
listgetter_async_allowlist: Dict[str, Callable] = {
    # Used by listpad
    "get_context_list": get_context_list,
    "get_inventory_list": get_inventory_list,
    "get_kubernetes_list": get_kubernetes_list,
}
