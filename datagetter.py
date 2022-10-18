#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
datagetters are used for data extraction that's too complext to be expressed by parameters to generic_infogetter
"""

import re

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

from iktlib import deep_get, deep_get_with_fallback, StatusGroup, timestamp_to_datetime
from kubernetes_helper import get_node_status, kind_tuple_to_name

def get_container_status(src_statuses, container):
	reason = "UNKNOWN"
	status_group = StatusGroup.UNKNOWN
	restarts = 0
	message = ""
	age = -1

	if src_statuses is None:
		return reason, status_group, -1, message, -1

	for container_status in src_statuses:
		if deep_get(container_status, "name") == container:
			restarts = deep_get(container_status, "restartCount")
			running = deep_get(container_status, "state#running")
			ts = deep_get_with_fallback(container_status, ["state#terminated#finishedAt", "lastState#terminated#finishedAt", "state#running#startedAt"], None)
			age = timestamp_to_datetime(ts)

			if deep_get(container_status, "ready") == False:
				status_group = StatusGroup.NOT_OK

				if running is not None:
					reason = "Running"
				elif deep_get(container_status, "state#terminated") is not None:
					reason = deep_get(container_status, "state#terminated#reason", "ErrNotSet")
					if deep_get(container_status, "state#terminated#exitCode") == 0:
						status_group = StatusGroup.DONE

					if deep_get(container_status, "state#terminated#message") is not None:
						message = deep_get(container_status, "state#terminated#message", "").rstrip()
				else:
					reason = deep_get(container_status, "state#waiting#reason", "").rstrip()

					if deep_get(container_status, "state#waiting#message") is not None:
						message = deep_get(container_status, "state#waiting#message", "").rstrip()
			else:
				if running is None:
					reason = deep_get(container_status, "state#terminated#reason", "").rstrip()

					if deep_get(container_status, "state#terminated#message") is not None:
						message = deep_get(container_status, "state#terminated#message", "").rstrip()

					if deep_get(container_status, "state#terminated#exitCode") == 0:
						status_group = StatusGroup.DONE
					else:
						status_group = StatusGroup.NOT_OK
				else:
					reason = "Running"
					status_group = StatusGroup.OK
			break

	return reason, status_group, restarts, message, age

def datagetter_container_status(kh, obj, path, default):
	del kh
	del path

	if obj is None:
		return default
	status = deep_get(obj, "status")
	status_group = deep_get(obj, "status_group")

	return status, {"status_group": status_group}

def get_endpointslices_endpoints(obj):
	endpoints = []

	if deep_get(obj, "endpoints") is not None:
		for endpoint in deep_get(obj, "endpoints", []):
			for address in deep_get(endpoint, "addresses", []):
				ready = deep_get(endpoint, "conditions#ready", False)
				if ready == True:
					status_group = StatusGroup.OK
				else:
					status_group = StatusGroup.NOT_OK
				endpoints.append((address, status_group))
	else:
		endpoints.append(("<none>", StatusGroup.UNKNOWN))
	return endpoints

def datagetter_eps_endpoints(kh, obj, path, default):
	del kh
	del path

	if obj is None:
		return default

	return get_endpointslices_endpoints(obj), {}

def datagetter_metrics(kh, obj, path, default):
	del kh

	if obj is None or path is None:
		return default

	result = []

	for field in path:
		result.append(deep_get(obj, f"fields#{field}", ""))

	result = tuple(result)

	return result, {}

def datagetter_deprecated_api(kh, obj, path, default):
	result, extra_vars = datagetter_metrics(kh, obj, path, default)
	kind = kh.guess_kind((result[0], result[1]))
	return (kind[0], kind[1], result[2]), extra_vars

def datagetter_latest_version(kh, obj, path, default):
	if obj is None or path is None:
		return default

	# path is paths to kind, api_family
	kind = deep_get(obj, path[0])
	api_family = deep_get(obj, path[1])
	old_version = deep_get(obj, path[2])
	kind = kh.guess_kind((kind, api_family))

	latest_api = kh.get_latest_api(kind)
	if "/" in latest_api:
		group, version = latest_api.split("/")
	else:
		group = ""
		version = latest_api

	message = ""

	# Check if there's a deprecation message in the CRD
	ref = kh.get_ref_by_kind_name_namespace("CustomResourceDefinition", kind_tuple_to_name(kind), "")

	if ref is not None:
		versions = {}
		sorted_versions = []

		for version in deep_get(ref, "spec#versions", []):
			version_name = deep_get(version, "name", "")
			deprecated = deep_get(version, "deprecated", False)
			deprecation_message = deep_get(version, "deprecationWarning", "")
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
				raise ParseError(f"Failed to parse version number {version}")
			try:
				major = int(tmp[1])
			except ParseError:
				raise ParseError(f"Failed to parse version number {version}")
			if tmp[2] == "":
				minor = 0
				patch = 0
			elif tmp[2].startswith("beta"):
				minor = -1
				try:
					patch = int(tmp[2][len("beta"):])
				except ParseError:
					raise ParseError(f"Failed to parse version number {version}")
			elif tmp[2].startswith("alpha"):
				minor = -2
				try:
					patch = int(tmp[2][len("alpha"):])
				except ParseError:
					raise ParseError(f"Failed to parse version number {version}")
			else:
				raise ParseError(f"Failed to parse version number {version}")
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

		if deep_get(versions, f"{latest_version}#deprecated", False) == True:
			message = deep_get(versions, f"{latest_version}#deprecation_message", "")
			message = f"({message})"

	else:
		latest_version = version

	if old_version == latest_version and message == "":
		message = "(No newer version available; the API might be deprecated)"

	return (group, latest_version, message), {}

def get_endpoint_endpoints(subsets):
	endpoints = []

	if subsets is None:
		subsets = []

	for subset in subsets:
		for address in deep_get(subset, "addresses", []):
			endpoints.append((deep_get(address, "ip"), StatusGroup.OK))
		for address in deep_get(subset, "notReadyAddresses", []):
			endpoints.append((deep_get(address, "ip"), StatusGroup.NOT_OK))

	if len(endpoints) == 0:
		endpoints.append(("<none>", StatusGroup.UNKNOWN))

	return endpoints

def datagetter_endpoint_ips(kh, obj, path, default):
	del kh
	del default

	subsets = deep_get(obj, path)
	endpoints = get_endpoint_endpoints(subsets)
	return endpoints, {}

# Only for internal types for the time being
def datagetter_regex_split_to_tuples(kh, obj, paths, default):
	del kh

	if obj is None or paths is None or len(paths) < 2:
		return default

	# paths is a tuple; the first item is a regex that specifies how to split,
	# the second one is either a path to a list or a list of paths

	list_fields = []

	if isinstance(paths[1], str):
		for item in deep_get(obj, paths[1], []):
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
			item = deep_get(obj, path, "")
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
def get_pod_status(kh, pod):
	if deep_get(pod, "metadata#deletionTimestamp") is not None:
		status = "Terminating"
		status_group = StatusGroup.PENDING
		return status, status_group

	phase = deep_get(pod, "status#phase")

	if phase == "Pending":
		status = phase
		status_group = StatusGroup.PENDING

		# Any containers in ContainerCreating or similar?
		for condition in deep_get(pod, "status#conditions", []):
			condition_type = deep_get(condition, "type")
			condition_status = deep_get(condition, "status")
			reason = deep_get(condition, "reason", "")

			if condition_type == "PodScheduled" and condition_status == "False" and reason == "Unschedulable":
				status = reason
				status_group = StatusGroup.NOT_OK
				break

			if condition_type == "ContainersReady" and condition_status == "False":
				for container in deep_get(pod, "status#initContainerStatuses", []):
					if deep_get(container, "ready") == False:
						reason = deep_get(container, "state#waiting#reason", "").rstrip()
						if reason is not None and len(reason) > 0:
							return reason, status_group
				for container in deep_get(pod, "status#containerStatuses", []):
					if deep_get(container, "ready") == False:
						reason = deep_get(container, "state#waiting#reason", "").rstrip()
						if reason is not None and len(reason) > 0:
							return reason, status_group

		return status, status_group

	if phase == "Running":
		status = "Running"
		status_group = StatusGroup.OK

		# Any container failures?
		for condition in deep_get(pod, "status#conditions", []):
			condition_type = deep_get(condition, "type")
			condition_status = deep_get(condition, "status")

			if condition_type == "Ready" and condition_status == "False":
				status_group = StatusGroup.NOT_OK
				status = "NotReady"
				# Can we get more info? Is the host available?
				node_name = deep_get(pod, "spec#nodeName")
				node = kh.get_ref_by_kind_name_namespace(("Node", ""), node_name, None)
				node_status = get_node_status(node)
				if node_status[0] == "Unreachable":
					status = "NodeUnreachable"
				break

			if condition_type == "ContainersReady" and condition_status == "False":
				status_group = StatusGroup.NOT_OK

				for container in deep_get(pod, "status#initContainerStatuses", []):
					status, status_group, _restarts, _message, _age = get_container_status(deep_get(pod, "status#initContainerStatuses"), deep_get(container, "name"))
					# If we have a failed container,
					# break here
					if status_group == StatusGroup.NOT_OK:
						break

				for container in deep_get(pod, "status#containerStatuses", []):
					status, status_group, _restarts, _message, _age = get_container_status(deep_get(pod, "status#containerStatuses"), deep_get(container, "name"))
					# If we have a failed container,
					# break here
					if status_group == StatusGroup.NOT_OK:
						break

		return status, status_group

	if phase == "Failed":
		# Failed
		status_group = StatusGroup.NOT_OK
		status = deep_get(pod, "status#reason", phase).rstrip()
		return status, status_group

	# Succeeded
	status_group = StatusGroup.DONE
	return phase, status_group

# Only for internal types for the time being
def datagetter_pod_status(kh, obj, path, default):
	del path

	if obj is None:
		return default

	status, status_group = get_pod_status(kh, obj)

	return status, {"status_group": status_group}

# Only for internal types for the time being
def datagetter_api_support(kh, obj, path, default):
	del path

	if obj is None:
		return default

	kind = deep_get(obj, "spec#names#kind", "")
	api_family = deep_get(obj, "spec#group", "")

	available_apis, _status, _modified = kh.get_available_api_families()

	available_views = []

	try:
		kind = kh.guess_kind((kind, api_family))
		available_views.append("Known")
		if deep_get(available_apis[kind], "list", False) == True:
			available_views.append("List")
		if deep_get(available_apis[kind], "info", False) == True:
			available_views.append("Info")
	except NameError:
		pass

	if len(available_views) == 0:
		available_views = default

	return available_views, {}

# Datagetters acceptable for direct use in view files
datagetter_allowlist = {
	"datagetter_container_status": datagetter_container_status,
	"datagetter_deprecated_api": datagetter_deprecated_api,
	"datagetter_latest_version": datagetter_latest_version,
	"datagetter_metrics": datagetter_metrics,
	"datagetter_endpoint_ips": datagetter_endpoint_ips,
	"datagetter_eps_endpoints": datagetter_eps_endpoints,
}
