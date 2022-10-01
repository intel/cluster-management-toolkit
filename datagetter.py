#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

import re

from iktlib import deep_get, stgroup

def datagetter_container_status(kh, obj, path, default):
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
					status_group = stgroup.OK
				else:
					status_group = stgroup.NOT_OK
				endpoints.append((address, status_group))
	else:
		endpoints.append(("<none>", stgroup.UNKNOWN))
	return endpoints

def datagetter_eps_endpoints(kh, obj, path, default):
	if obj is None:
		return default

	return get_endpointslices_endpoints(obj), {}

def datagetter_metrics(kh, obj, path, default):
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
	if old_version == version:
		message = "(No newer version available; the API might be deprecated)"
	return (group, version, f"{message}"), {}

def get_endpoint_endpoints(subsets):
	endpoints = []

	if subsets is None:
		subsets = []

	for subset in subsets:
		for address in deep_get(subset, "addresses", []):
			endpoints.append((deep_get(address, "ip"), stgroup.OK))
		for address in deep_get(subset, "notReadyAddresses", []):
			endpoints.append((deep_get(address, "ip"), stgroup.NOT_OK))

	if len(endpoints) == 0:
		endpoints.append(("<none>", stgroup.UNKNOWN))

	return endpoints

def datagetter_endpoint_ips(kh, obj, path, default):
	subsets = deep_get(obj, path)
	endpoints = get_endpoint_endpoints(subsets)
	return endpoints, {}

# Only for internal types for the time being
def datagetter_regex_split_to_tuples(kh, obj, paths, default):
	if obj is None or paths is None or len(paths) < 2:
		return default

	# paths is a tuple; the first item is a regex that specifies how to split,
	# the second one is either a path to a list or a list of paths

	list_fields = []

	if type(paths[1]) == str:
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

# Only for internal types for the time being
def datagetter_pod_status(kh, obj, path, default):
	if obj is None:
		return default

	status, status_group = get_pod_status(obj)

	return status, {"status_group": status_group}

# Only for internal types for the time being
def datagetter_api_support(kh, obj, path, default):
	if obj is None:
		return default

	kind = deep_get(obj, "spec#names#kind", "")
	api_family = deep_get(obj, "spec#group", "")

	available_views = []

	try:
		_kind, _api_group = kh.guess_kind((kind, api_family))
		available_views.append("Known")
	except NameError:
		pass

	for view in views:
		if deep_get(views, f"{view}#kind", ("", "")) == (kind, api_family):
			available_views.append("List")

	if (kind, api_family) in infoviews:
		available_views.append("Info")

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