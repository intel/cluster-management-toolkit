#! /usr/bin/env python3
# Requires: python3 (>= 3.8)

"""
Datagetters are used for data extraction that's too complex to be expressed by parameters to generic_infogetter
"""

import re
from typing import Any, Callable, Dict, List, Tuple, Union

from cmtlib import get_since, timestamp_to_datetime
from cmttypes import deep_get, deep_get_with_fallback, DictPath, StatusGroup
import kubernetes_helper
from kubernetes_helper import get_node_status, kind_tuple_to_name, guess_kind

def get_container_status(src_statuses: List[Dict], container: str) -> Tuple[str, StatusGroup, int, str, int]:
	"""
	Return the status for a container

		Parameters:
			src_statuses (dict): A reference to either status#containerStatuses, status#initContainerStatuses, or status#ephemeralContainerStatuses
			container (str): The name of the container
		Returns:
			reason (str), status_group (StatusGroup), restarts (int), message (str), age (int):
				reason: Reason for the status
				status_group: Status group
				restarts: How many times has the container been restarted
				message: Status message, if any
				age: Age of the container
	"""

	reason = "UNKNOWN"
	status_group = StatusGroup.UNKNOWN
	restarts = 0
	message = ""
	age = -1

	if src_statuses is None:
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
					reason = deep_get(container_status, DictPath("state#terminated#reason"), "ErrNotSet")
					if deep_get(container_status, DictPath("state#terminated#exitCode")) == 0:
						status_group = StatusGroup.DONE

					if deep_get(container_status, DictPath("state#terminated#message")) is not None:
						message = deep_get(container_status, DictPath("state#terminated#message"), "").rstrip()
				else:
					reason = deep_get(container_status, DictPath("state#waiting#reason"), "").rstrip()

					if deep_get(container_status, DictPath("state#waiting#message")) is not None:
						message = deep_get(container_status, DictPath("state#waiting#message"), "").rstrip()
			else:
				if running is None:
					reason = deep_get(container_status, DictPath("state#terminated#reason"), "").rstrip()

					if deep_get(container_status, DictPath("state#terminated#message")) is not None:
						message = deep_get(container_status, DictPath("state#terminated#message"), "").rstrip()

					if deep_get(container_status, DictPath("state#terminated#exitCode")) == 0:
						status_group = StatusGroup.DONE
					else:
						status_group = StatusGroup.NOT_OK
				else:
					reason = "Running"
					status_group = StatusGroup.OK
			break

	return reason, status_group, restarts, message, age

# pylint: disable-next=unused-argument
def datagetter_container_status(kh: kubernetes_helper.KubernetesHelper, obj: Dict, path: DictPath, default: Any) -> Tuple[StatusGroup, Dict]:
	"""
	A datagetter that returns the status of a container

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The container object to get status for
			path (str): Unused
			default (Any): Unused
	"""

	if obj is None:
		return "UNKNOWN", {"status_group": StatusGroup.UNKNOWN}

	status = deep_get(obj, DictPath("status"))
	status_group = deep_get(obj, DictPath("status_group"))

	return status, {"status_group": status_group}

def get_endpointslices_endpoints(obj: Dict) -> List[Tuple[str, StatusGroup]]:
	"""
	Get the endpoints for an endpoint slice

		Parameters:
			obj (dict): The endpoint slice object to return endpoints for
		Returns:
			endpoints (list[(str, StatusGroup)]): A list of tuples with the address and status for each endpoint
	"""

	endpoints = []

	if deep_get(obj, DictPath("endpoints")) is not None:
		for endpoint in deep_get(obj, DictPath("endpoints"), []):
			for address in deep_get(endpoint, DictPath("addresses"), []):
				ready = deep_get(endpoint, DictPath("conditions#ready"), False)
				if ready:
					status_group = StatusGroup.OK
				else:
					status_group = StatusGroup.NOT_OK
				endpoints.append((address, status_group))
	else:
		endpoints.append(("<none>", StatusGroup.UNKNOWN))
	return endpoints

# pylint: disable-next=unused-argument
def datagetter_eps_endpoints(kh: kubernetes_helper.KubernetesHelper, obj: Dict, path: DictPath, default: Any) -> Tuple[List[Tuple[str, StatusGroup]], Dict]:
	"""
	A datagetter that returns the endpoints for an endpoint slice

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The endpoint slice object to return endpoints for
			path (str): Unused
			default (opaque): Unused
		Returns:
			The return value from get_endpointslices_endpoints and an empty dict
	"""

	if obj is None:
		return ("<none>", StatusGroup.UNKNOWN), {}

	return get_endpointslices_endpoints(obj), {}

# pylint: disable-next=unused-argument
def datagetter_metrics(kh: kubernetes_helper.KubernetesHelper, obj: Dict, path: DictPath, default: Any) -> Tuple[List[str], Dict]:
	"""
	A datagetter that returns metrics for the specified path

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The object with metrics
			path (DictPath): The path to the metrics to get
			default (Any): Unused?
		Returns:
			result (list[str]), {} (dict): A list with metrics and an empty dict
	"""

	if obj is None or path is None:
		if default is None:
			default = []
		return default, {}

	result = []

	for field in path:
		result.append(deep_get(obj, DictPath(f"fields#{field}"), ""))

	return result, {}

def datagetter_deprecated_api(kh: kubernetes_helper.KubernetesHelper, obj: Dict, path: DictPath, default: Any) -> Tuple[Tuple[str, str, str], Dict]:
	"""
	A datagetter that returns deprecated API information for the specified path

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The object with metrics
			path (str): The path to the metrics to get
			default (Any): Unused?
		Returns:
			kind, api_family, metrics, extra_vars:
				kind (str): Kind for the deprecated API
				api_family (str): API-family for the deprecated API
				metrics (list[str]): Metrics for the deprecated API
				extra_vars (dict): Additional vars
	"""

	result, extra_vars = datagetter_metrics(kh, obj, path, default)
	kind, api_family = guess_kind((result[0], result[1]))
	return (kind, api_family, result[2]), extra_vars

def datagetter_latest_version(kh: kubernetes_helper.KubernetesHelper, obj: Dict, path: DictPath, default: Any) -> Tuple[Tuple[str, str, str], Dict]:
	"""
	A datagetter that returns the latest available API for kind as passed in path

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The object to get the old API information from
			path (list[kind_path, api_family_path, old_version_path)]: Paths to Kind, API-family, and the old version of the API
			default: Unused?
		Returns:
			(group (str), latest_version (str), message (str)) (tuple(str, str, str), {} (dict):
				group: new API-group (since it might change)
				latest_version: The latest version of the API, or old_version if no newer version available
				message: If the API is deprecated, the deprecation message (if one available), or a default message (if not)
				{}: An empty dict
	"""

	if obj is None or path is None:
		if default is None:
			default = ("", "", "")
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
	ref = kh.get_ref_by_kind_name_namespace(("CustomResourceDefinition", "apiextensions.k8s.io"), kind_tuple_to_name(kind), "")

	if ref is not None:
		versions: Dict = {}
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
					patch = int(tmp[2][len("beta"):])
				except ValueError as e:
					raise ValueError(f"Failed to parse version number {version}") from e
			elif tmp[2].startswith("alpha"):
				minor = -2
				try:
					patch = int(tmp[2][len("alpha"):])
				except ValueError as e:
					raise ValueError(f"Failed to parse version number {version}") from e
			else:
				raise ValueError(f"Failed to parse version number {version}")
			tmp_versions.append((major, minor, patch))
		sorted_versions = sorted(tmp_versions, reverse = True)
		latest_major = f"v{sorted_versions[0][0]}"
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

	if old_version == latest_version and message == "":
		message = "(No newer version available; the API might be deprecated)"

	return (group, latest_version, message), {}

def get_endpoint_endpoints(subsets: List[Dict]) -> List[Tuple[str, StatusGroup]]:
	"""
	Get the endpoints for an endpoint

		Parameters:
			subsets (list[subset]): The subsets to return endpoints for
		Returns:
			endpoints (list[(str, StatusGroup)]): A list of tuples with the address and status for each endpoint
	"""

	endpoints = []

	if subsets is None:
		subsets = []

	for subset in subsets:
		for address in deep_get(subset, DictPath("addresses"), []):
			endpoints.append((deep_get(address, DictPath("ip")), StatusGroup.OK))
		for address in deep_get(subset, DictPath("notReadyAddresses"), []):
			endpoints.append((deep_get(address, DictPath("ip")), StatusGroup.NOT_OK))

	if len(endpoints) == 0:
		endpoints.append(("<none>", StatusGroup.UNKNOWN))

	return endpoints

# pylint: disable-next=unused-argument
def datagetter_endpoint_ips(kh: kubernetes_helper.KubernetesHelper, obj: Dict, path: DictPath, default: Any) -> Tuple[List[Tuple[str, StatusGroup]], Dict]:
	"""
	A datagetter that returns the endpoints for an endpoint

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The endpoint object to return endpoints for
			path (str): Unused
			default (opaque): Unused
		Returns:
			The return value from get_endpointslices_endpoints and an empty dict
	"""

	subsets = deep_get(obj, DictPath(path))
	endpoints = get_endpoint_endpoints(subsets)
	return endpoints, {}

# XXX: Can this be replaced with generic_listgetter()?
# pylint: disable-next=unused-argument
def datagetter_regex_split_to_tuples(kh: kubernetes_helper.KubernetesHelper, obj: Dict,
				     paths: List[DictPath], default: Any) -> Tuple[List[Union[str, Tuple[str, str]]], Dict]:
	"""
	A datagetter that uses a regex to split a path into tuples

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The object to split into tuples
			path (tuple(raw str, list[str]): The path(s) to split using the regex
			default (opaque): Unused
		Returns:
			The return value from get_endpointslices_endpoints and an empty dict
	"""

	if obj is None or paths is None or len(paths) < 2:
		return default, {}

	# paths is a tuple; the first item is a regex that specifies how to split,
	# the second one is either a path to a list or a list of paths

	list_fields: List[Union[str, Tuple[str, str]]] = []

	if isinstance(paths[1], str):
		for item in deep_get(obj, DictPath(paths[1]), []):
			tmp = re.match(paths[0], item)
			if tmp is not None:
				# This handles ("").*("") | (""); we need to generalise this somehow
				if len(tmp.groups()) >= 2 and tmp[1] is not None and tmp[2] is not None:
					list_fields.append((tmp[1], tmp[2]))
				elif len(tmp.groups()) >= 3:
					list_fields.append(("", tmp[3]))
			else:
				list_fields.append(("", ""))
	else:
		for path in paths[1]:
			item = deep_get(obj, DictPath(path), "")
			tmp = re.match(paths[0], str(item))
			if tmp is not None:
				# This handles ("").*("") | (""); we need to generalise this somehow
				if len(tmp.groups()) == 1 and tmp[1] is not None:
					list_fields.append(tmp[1])
				if len(tmp.groups()) >= 2 and tmp[1] is not None and tmp[2] is not None:
					list_fields.append((tmp[1], tmp[2]))
				elif len(tmp.groups()) >= 3:
					list_fields.append(("", tmp[3]))
			else:
				list_fields.append(("", ""))

	return list_fields, {}

# pylint: disable-next=too-many-return-statements
def get_pod_status(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> Tuple[str, StatusGroup]:
	"""
	Get status for a Pod

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The pod object to return status for
		Returns:
			phase (str), status_group (StatusGroup): The phase and status group of the pod
	"""

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

			if condition_type == "PodScheduled" and condition_status == "False" and reason == "Unschedulable":
				status = reason
				status_group = StatusGroup.NOT_OK
				break

			if condition_type == "ContainersReady" and condition_status == "False":
				for container in deep_get(obj, DictPath("status#initContainerStatuses"), []):
					if not deep_get(container, DictPath("ready")):
						reason = deep_get(container, DictPath("state#waiting#reason"), "").rstrip()
						if reason is not None and len(reason) > 0:
							if reason in ("CrashLoopBackOff", "ImagePullBackOff"):
								status_group = StatusGroup.NOT_OK
							reason = f"Init:{reason}"
							return reason, status_group
				for container in deep_get(obj, DictPath("status#containerStatuses"), []):
					if not deep_get(container, DictPath("ready")):
						reason = deep_get(container, DictPath("state#waiting#reason"), "").rstrip()
						if reason is not None and len(reason) > 0:
							if reason in ("CrashLoopBackOff", "ErrImageNeverPull", "ErrImagePull"):
								status_group = StatusGroup.NOT_OK
							return reason, status_group

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
					node = kh.get_ref_by_kind_name_namespace(("Node", ""), node_name, "")
					node_status = get_node_status(node)
					if node_status[0] == "Unreachable":
						status = "NodeUnreachable"
				break

			if condition_type == "ContainersReady" and condition_status == "False":
				status_group = StatusGroup.NOT_OK

				for container in deep_get(obj, DictPath("status#initContainerStatuses"), []):
					status, status_group, _restarts, _message, _age =\
						get_container_status(deep_get(obj, DictPath("status#initContainerStatuses")), deep_get(container, DictPath("name")))

					# If we have a failed container,
					# break here
					if status_group == StatusGroup.NOT_OK:
						break

				for container in deep_get(obj, DictPath("status#containerStatuses"), []):
					status, status_group, _restarts, _message, _age =\
						get_container_status(deep_get(obj, DictPath("status#containerStatuses")), deep_get(container, DictPath("name")))
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

# XXX: Only for internal types for the time being
# pylint: disable-next=unused-argument
def datagetter_pod_status(kh: kubernetes_helper.KubernetesHelper, obj: Dict, path: DictPath, default: str) -> Tuple[str, Dict]:
	"""
	A datagetter that returns the status for a pod

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The pod object to return pod status for
			path (str): Unused
			default (opaque): Unused?
		Returns:
			The return value from get_endpointslices_endpoints and an empty dict
	"""

	if obj is None:
		return default, {}

	status, status_group = get_pod_status(kh, obj)

	return status, {"status_group": status_group}

# Only for internal types for the time being
# pylint: disable-next=unused-argument
def datagetter_api_support(kh: kubernetes_helper.KubernetesHelper, obj: Dict, path: DictPath, default: List[str]) -> Tuple[List[str], Dict]:
	"""
	A datagetter that returns the level of support that CMT provides for an API;
	can be one of:
	* Known (CMT has an API definition)
	* List (CMT has a list view)
	* Info (CMT has an info view)

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The pod object to return pod status for
			path (str): Unused
			default (opaque): Unused?
		Returns:
			available_views (list[str]), {}:
				available_views: A list with zero or more of "Known", "List", "Info"
				{}: An empty dict
	"""

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

	if len(available_views) == 0:
		available_views = default

	return available_views, {}

# Datagetters acceptable for direct use in view files
datagetter_allowlist: Dict[str, Callable[[kubernetes_helper.KubernetesHelper, Dict, DictPath, Any], Tuple[Any, Dict]]] = {
	"datagetter_container_status": datagetter_container_status,
	"datagetter_deprecated_api": datagetter_deprecated_api,
	"datagetter_latest_version": datagetter_latest_version,
	"datagetter_metrics": datagetter_metrics,
	"datagetter_endpoint_ips": datagetter_endpoint_ips,
	"datagetter_eps_endpoints": datagetter_eps_endpoints,
}
