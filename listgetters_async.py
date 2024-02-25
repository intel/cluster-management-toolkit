#! /usr/bin/env python3
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Get list data asynchronously
"""

import re
import sys
from typing import Any, Dict, List, Tuple, Union

try:
	from natsort import natsorted
except ModuleNotFoundError:  # pragma: no cover
	sys.exit("ModuleNotFoundError: Could not import natsort; you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

from cmttypes import deep_get, DictPath, StatusGroup, ProgrammingError
import infogetters

# pylint: disable-next=unused-argument
def get_kubernetes_list(*args, **kwargs) -> Tuple[List[Any], Union[int, str, List[StatusGroup]]]:
	"""
	Fetch a list of Kubernetes objects, optionally with postprocessing

		Parameters:
			*args [Any]: Positional arguments (unused)
			**kwargs (dict[str, Any]): Keyword arguments
				kind ((str, str)): The Kubernetes kind (required)
				namespace (str): The Kubernetes namespace (optional)
				label_selector (str): A label selector (optional)
				field_selector (str): A field selector (optional)
				fetch_args (dict): Specific arguments (optional)
					sort_key (str): The sort-key to use if sorting the list (optional)
					sort_reverse (bool): Should the list be returned with reversed sort order? (optional)
					postprocess (str): Post-processing (if any) to apply (optional)
					limit (int): The max number of items to return (optional)
		Returns:
			([dict], int|str|[StatusGroup]):
				[dict]: A list of Kubernetes objects
				int|str|[StatusGroup]: Server status (int), unused (str), or the individual StatusGroup for all objects
	"""

	if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
		raise ProgrammingError("get_kubernetes_list() called without kubernetes_helper")

	kind = deep_get(kwargs, DictPath("kind"))
	namespace = deep_get(kwargs, DictPath("namespace"), "")
	label_selector = deep_get(kwargs, DictPath("label_selector"), "")
	field_selector = deep_get(kwargs, DictPath("field_selector"), "")
	fetch_args = deep_get(kwargs, DictPath("fetch_args"), {})
	sort_key = deep_get(fetch_args, DictPath("sort_key"), "")
	sort_reverse = deep_get(fetch_args, DictPath("sort_reverse"), False)
	postprocess = deep_get(fetch_args, DictPath("postprocess"), "")
	limit = deep_get(fetch_args, DictPath("limit"))
	extra_data = []

	vlist, status = kh.get_list_by_kind_namespace(kind, namespace, label_selector = label_selector, field_selector = field_selector)
	if sort_key:
		vlist = natsorted(vlist, key = lambda x: deep_get(x, DictPath(sort_key), ""), reverse = sort_reverse)
	if postprocess == "node":
		vlist = infogetters.get_node_info(**{"vlist": vlist})
		extra_data = [s.status_group for s in vlist]
	elif postprocess == "pod":
		vlist = infogetters.get_pod_info(**{"vlist": vlist, "in_depth_node_status": False, "kubernetes_helper": kh})
		extra_data = [s.status_group for s in vlist]
	else:
		extra_data = status
	if limit is not None:
		vlist = vlist[:limit]
	return vlist, extra_data

def get_inventory_list() -> None:
	"""
	Dummy function used as a cookie for inventory list
	"""
	return

# pylint: disable-next=unused-argument
def get_context_list(**kwargs: Any) -> Tuple[List[Dict], List[str]]:
	"""
	Get the list of Kubernetes contexts

		Parameters:
			**kwargs (dict[str, Any]): Keyword arguments
				kubernetes_helper (KubernetesHelper): The KubernetesHelper object to use (required)
				tag_prefix (str): The prefix to use for the tagged list item (optional)
		Returns:
			([dict], [str]):
				[dict]: The list of context information
				[str]: The list of API-servers for those contexts
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

# Asynchronous listgetters acceptable for direct use in view files
listgetter_async_allowlist = {
	# Used by listpad
	"get_kubernetes_list": get_kubernetes_list,
	"get_context_list": get_context_list,
	"get_inventory_list": get_inventory_list,
}
