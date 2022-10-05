#! /usr/bin/env python3

import re

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

import iktlib
from iktlib import deep_get, deep_get_with_fallback, disksize_to_human, get_package_versions, make_set_expression, make_set_expression_list, stgroup, timestamp_to_datetime

def get_allowed_ips(kh, obj, **kwargs):
	allowed_ips = []

	ip_mask_regex = re.compile(r"^(\d+\.\d+\.\d+\.\d+)\/(\d+)")

	for addr in deep_get(obj, "spec#allowedIPs"):
		if "/" in addr:
			tmp = ip_mask_regex.match(addr)
			if tmp is None:
				raise ValueError(f"Could not parse {addr} as an address/address mask")
			ip = tmp[1]
			mask = tmp[2]
			allowed_ips.append({
				"lineattrs": widgetlineattrs.NORMAL,
				"columns": [[(f"{ip}", ("windowwidget", "default")), ("/", ("windowwidget", "dim")), (f"{mask}", ("windowwidget", "default"))]],
			})
		else:
			allowed_ips.append({
				"lineattrs": widgetlineattrs.NORMAL,
				"columns": [[(f"{addr}", ("windowwidget", "default"))]],
			})

	return allowed_ips

def get_conditions(kh, obj, **kwargs):
	condition_list = []

	path = deep_get(kwargs, "path", "status#conditions")

	for condition in deep_get(obj, path, []):
		ctype = deep_get(condition, "type", "")
		status = deep_get_with_fallback(condition, ["status", "phase"], "")
		last_probe = deep_get(condition, "lastProbeTime")
		if last_probe is None:
			last_probe = "<unset>"
		else:
			timestamp = timestamp_to_datetime(last_probe)
			last_probe = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
		last_transition = deep_get(condition, "lastTransitionTime")
		if last_transition is None:
			last_transition = "<unset>"
		else:
			timestamp = timestamp_to_datetime(last_transition)
			last_transition = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
		message = deep_get(condition, "message", "")
		condition_list.append({
			"fields": [ctype, status, last_probe, last_transition, message],
		})
	return condition_list

def get_endpoint_slices(kh, obj, **kwargs):
	svcname = deep_get(obj, "metadata#name")
	svcnamespace = deep_get(obj, "metadata#namespace")
	# We need to find all Endpoint Slices in the same namespace as the service that have this service
	# as its controller
	vlist, status = kh.get_list_by_kind_namespace(("EndpointSlice", "discovery.k8s.io"), svcnamespace, label_selector = f"kubernetes.io/service-name={svcname}")
	tmp = []
	for item in vlist:
		epsnamespace = deep_get(item, "metadata#namespace")
		epsname = deep_get(item, "metadata#name")
		tmp.append([epsnamespace, epsname])
	return tmp

def get_events(kh, obj, **kwargs):
	event_list = []

	kind = deep_get(obj, "kind")
	api_version = deep_get(obj, "apiVersion", "")
	name = deep_get(obj, "metadata#name")
	namespace = deep_get(obj, "metadata#namespace", "")
	tmp = kh.get_events_by_kind_name_namespace(kh.kind_api_version_to_kind(kind, api_version), name, namespace)
	for event in tmp:
		event_list.append({
			"fields": event,
		})

	return event_list

def get_image_list(kh, obj, **kwargs):
	vlist = []
	path = deep_get(kwargs, "path", "")

	for image in deep_get(obj, path, []):
		name = ""
		for name in deep_get(image, "names", []):
			# This is the preferred name
			if "@sha256:" not in name:
				break

		if len(name) == 0:
			continue
		size = disksize_to_human(deep_get(image, "sizeBytes", 0))
		vlist.append([name, size])
	return natsorted(vlist)

def get_key_value(kh, obj, **kwargs):
	vlist = []
	if "path" in kwargs:
		path = deep_get(kwargs, "path", "")
		d = deep_get(obj, path, {})

		for _key in d:
			_value = d[_key]
			if isinstance(_value, list):
				value = ",".join(_value)
			elif isinstance(_value, dict):
				value = ",".join(f"{key}:{val}" for (key, val) in _value.items())
			# We don't need to check for bool, since it's a subclass of int
			elif isinstance(_value, (int, float)):
				value = str(_value)
			elif isinstance(_value, str):
				value = _value
			else:
				raise TypeError(f"Unhandled type {type(_value)} for {field}={value}")
			vlist.append([_key, value])

	return vlist

def get_list_as_list(kh, obj, **kwargs):
	vlist = []
	if "path" in kwargs:
		path = deep_get(kwargs, "path")
		_regex = deep_get(kwargs, "regex")
		if _regex is not None:
			compiled_regex = re.compile(_regex)
		items = deep_get(obj, path, [])
		for item in items:
			if _regex is not None:
				tmp = compiled_regex.match(item)
				vlist.append(tmp.groups())
			else:
				vlist.append([item])
	elif "paths" in kwargs:
		# lists that run out of elements will return ""
		# strings will be treated as constants and thus returned for every row
		paths = deep_get(kwargs, "paths", [])
		maxlen = 0
		for column in paths:
			tmp = deep_get(obj, column)
			if isinstance(tmp, list):
				maxlen = max(len(tmp), maxlen)
		for i in range(0, maxlen):
			item = []
			for column in paths:
				tmp = deep_get(obj, column)
				if isinstance(tmp, str):
					item.append(tmp)
				elif isinstance(tmp, list):
					if len(tmp) > i:
						item.append(tmp[i])
					else:
						item.append(" ")
			vlist.append(item)

	return vlist

def get_list_fields(kh, obj, **kwargs):
	vlist = []

	if "path" in kwargs and "fields" in kwargs:
		path = deep_get(kwargs, "path")
		fields = deep_get(kwargs, "fields", [])
		pass_ref = deep_get(kwargs, "pass_ref", False)
		override_types = deep_get(kwargs, "override_types", [])
		for item in deep_get(obj, path, []):
			tmp = []
			for i in range(0, len(fields)):
				field = fields[i]
				default = ""
				if isinstance(field, dict):
					default = deep_get(field, "default", "")
					field = deep_get(field, "name")
				_value = deep_get(item, field, default)
				if isinstance(_value, list) or (i < len(fields) and i < len(override_types) and override_types[i] == "list"):
					value = ", ".join(_value)
				elif isinstance(_value, dict) or (i < len(fields) and i < len(override_types) and override_types[i] == "dict"):
					value = ", ".join(f"{key}:{val}" for (key, val) in _value.items())
				# We don't need to check for bool, since it's a subclass of int
				elif isinstance(_value, (int, float)) or (i < len(fields) and i < len(override_types) and override_types[i] == "str"):
					value = str(_value)
				elif isinstance(_value, str):
					if i < len(fields) and i < len(override_types) and override_types[i] == "timestamp":
						if _value is None:
							value = "<unset>"
						else:
							timestamp = timestamp_to_datetime(_value)
							value = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
					elif i < len(fields) and i < len(override_types) and override_types[i] == "age":
						if _value is None:
							value = "<unset>"
						else:
							timestamp = timestamp_to_datetime(_value)
							value = iktlib.seconds_to_age(get_since(timestamp))
					else:
						value = _value
				else:
					raise Exception(f"Unhandled type {type(_value)} for {field}={value}")
				tmp.append(value)
			if pass_ref == True:
				vlist.append({"fields": tmp, "ref": item})
			else:
				vlist.append(tmp)
	return vlist

def get_package_version_list(kh, obj, **kwargs):
	name_path = deep_get(kwargs, "name_path", "")
	hostname = deep_get(obj, name_path)
	hostname = deep_get(kwargs, "name", hostname)
	try:
		package_versions = get_package_versions(hostname)
	except ValueError:
		package_versions = None
	return package_versions

def get_pod_affinity(kh, obj, **kwargs):
	affinities = []

	for affinity in deep_get(obj, "spec#affinity", []):
		atype = affinity
		policy_regex = re.compile(r"^(ignored|preferred|required)DuringScheduling(Ignored|Preferred|Required)DuringExecution$")

		for policy in deep_get(obj, f"spec#affinity#{atype}", ""):
			tmp = policy_regex.match(policy)
			if tmp is None:
				scheduling = "Unknown"
				execution = "Unknown"
			else:
				scheduling = tmp[1].capitalize()
				execution = tmp[2]

			selectors = ""
			for item in deep_get(obj, f"spec#affinity#{atype}#{policy}", []):
				topology = ""
				if isinstance(item, dict):
					items = [item]
				elif isinstance(item, str):
					items = deep_get(obj, f"spec#affinity#{atype}#{policy}#{item}", [])

				for selector in items:
					weight = deep_get(selector, f"weight", "")
					if isinstance(weight, int):
						weight = f"/{weight}"
					topology = deep_get(selector, f"topologyKey", "")
					# We're combining a few different policies, so the expressions can be in various places; not simultaneously though
					selectors += make_set_expression(deep_get(selector, "labelSelector#matchExpressions", {}))
					selectors += make_set_expression(deep_get(selector, "labelSelector#matchFields", {}))
					selectors += make_set_expression(deep_get(selector, "preference#matchExpressions", {}))
					selectors += make_set_expression(deep_get(selector, "preference#matchFields", {}))
					selectors += make_set_expression(deep_get(selector, "matchExpressions", {}))
					selectors += make_set_expression(deep_get(selector, "matchFields", {}))
					affinities.append([atype, f"{scheduling}{weight}", execution, selectors, topology])

	return affinities

def get_pod_tolerations(kh, obj, **kwargs):
	tolerations = []

	for toleration in deep_get_with_fallback(obj, ["spec#tolerations", "scheduling#tolerations"], []):
		status_group = stgroup.OK

		effect = deep_get(toleration, "effect", "All")
		key = deep_get(toleration, "key", "All")
		operator = deep_get(toleration, "operator", "Equal")

		# According to spec only "Exists"
		# is valid in combination with "All"
		if key == "All" and operator != "Exists":
			status_group = stgroup.NOT_OK

		# Eviction timeout
		toleration_seconds = deep_get(toleration, "tolerationSeconds")
		if toleration_seconds is None:
			timeout = "Never"
		elif toleration_seconds <= 0:
			timeout = "Immediately"
		else:
			timeout = str(toleration_seconds)

		value = deep_get(toleration, "value", "")

		# According to spec only an empty value
		# is valid in combination with "Exists"
		if operator == "Exists" and value != "":
			status_group = stgroup.NOT_OK

		tolerations.append([key, operator, value, effect, timeout])

	return tolerations

def get_resource_list(kh, obj, **kwargs):
	vlist = []

	for res in deep_get(obj, "status#capacity", {}):
		capacity = deep_get(obj, f"status#capacity#{res}", "")
		allocatable = deep_get(obj, f"status#allocatable#{res}", "")
		vlist.append([res, allocatable, capacity])
	return vlist

def get_resources(kh, obj, **kwargs):
	resources = []

	for limit in list(deep_get(obj, "spec#resources#limits", {})):
		if limit == "cpu":
			resources.append(("CPU", "Limit", deep_get(obj, "spec#resources#limits#cpu")))
		elif limit == "memory":
			resources.append(("CPU", "Limit", deep_get(obj, "spec#resources#limits#memory")))
		elif limit.startswith("hugepages-"):
			resources.append((f"H{limit[1:]}", "Limit", deep_get(obj, "spec#resources#limits#" + limit)))

	for request in list(deep_get(obj, "spec#resources#requests", {})):
		if request == "cpu":
			resources.append(("CPU", "Limit", deep_get(obj, "spec#resources#requests#cpu")))
		elif request == "memory":
			resources.append(("CPU", "Limit", deep_get(obj, "spec#resources#requests#memory")))
		elif request.startswith("hugepages-"):
			resources.append((f"H{request[1:]}", "Limit", deep_get(obj, "spec#resources#requests#" + request)))

	return resources

def get_strings_from_string(kh, obj, **kwargs):
	vlist = []
	if "path" in kwargs:
		path = deep_get(kwargs, "path")
		tmp = deep_get(obj, path, [])
		if tmp is not None and len(tmp) > 0:
			for line in split_msg(tmp):
				vlist.append([line])
	return vlist

def get_endpoint_ips(subsets):
	endpoints = []
	notready = 0

	if subsets is None:
		return ["<none>"]

	for subset in subsets:
		# Keep track of whether we have not ready addresses
		if deep_get(subset, "notReadyAddresses") is not None and len(deep_get(subset, "notReadyAddresses")) > 0:
			notready += 1

		if deep_get(subset, "addresses") is None:
			continue

		for address in deep_get(subset, "addresses", []):
			endpoints.append(deep_get(address, "ip"))

	if endpoints == []:
		if notready > 0:
			return ["<not ready>"]
		else:
			return ["<none>"]

	return endpoints

def get_security_context(kh, obj, **kwargs):
	security_policies = []

	tmp = [
		("Run as User", deep_get_with_fallback(obj, ["spec#securityContext#runAsUser", "spec#template#spec#securityContext#runAsUser"])),
		("Run as non-Root", deep_get_with_fallback(obj, ["spec#securityContext#runAsNonRoot", "spec#template#spec#securityContext#runAsNonRoot"])),
		("Run as Group", deep_get_with_fallback(obj, ["spec#securityContext#runAsGroup", "spec#template#spec#securityContext#runAsGroup"])),
		("FS Group", deep_get_with_fallback(obj, ["spec#securityContext#fsGroup", "spec#template#spec#securityContext#fsGroup"])),
		("FS Group-change Policy", deep_get_with_fallback(obj, ["spec#securityContext#fsGroupChangePolicy", "spec#template#spec#securityContext#fsGroupChangePolicy"])),
		("Allow Privilege Escalation", deep_get_with_fallback(obj, ["spec#securityContext#allowPrivilegeEscalation", "spec#template#spec#securityContext#allowPrivilegeEscalation"])),
		("Capabilities",deep_get_with_fallback(obj, ["spec#securityContext#capabilities", "spec#template#spec#securityContext#capabilities"])),
		("Privileged", deep_get_with_fallback(obj, ["spec#securityContext#privileged", "spec#template#spec#securityContext#privileged"])),
		("Proc Mount", deep_get_with_fallback(obj, ["spec#securityContext#procMount", "spec#template#spec#securityContext#procMount"])),
		("Read-only Root Filesystem", deep_get_with_fallback(obj, ["spec#securityContext#readOnlyRootFilesystem", "spec#template#spec#securityContext#readOnlyRootFilesystem"])),
		("SELinux Options", deep_get_with_fallback(obj, ["spec#securityContext#seLinuxOptions", "spec#template#spec#securityContext#seLinuxOptions"])),
		("Seccomp Profile", deep_get_with_fallback(obj, ["spec#securityContext#seccompProfile", "spec#template#spec#securityContext#seccompProfile"])),
		("Windows Options", deep_get_with_fallback(obj, ["spec#securityContext#windowsOptions", "spec#template#spec#securityContext#windowsOptions"])),
	]

	for policy in tmp:
		if policy[1] is not None:
			security_policies.append([policy[0], str(policy[1])])

	return security_policies

def get_svc_port_target_endpoints(kh, obj, **kwargs):
	svcname = deep_get(obj, "metadata#name")
	svcnamespace = deep_get(obj, "metadata#namespace")
	port_target_endpoints = []
	stype = deep_get(obj, "spec#type")
	cluster_ip = deep_get(obj, "spec#clusterIP")
	endpoints = []

	ref = kh.get_ref_by_kind_name_namespace(("Endpoints", ""), svcname, svcnamespace)
	endpoints = get_endpoint_ips(deep_get(ref, "subsets"))

	for port in deep_get(obj, "spec#ports", []):
		name = deep_get(port, "name", "")
		svcport = deep_get(port, "port", "")
		protocol = deep_get(port, "protocol", "")
		if stype in ["NodePort", "LoadBalancer"]:
			node_port = deep_get(port, "nodePort", "Auto Allocate")
		else:
			node_port = "N/A"
		if cluster_ip is not None:
			target_port = deep_get(port, "targetPort", "")
		else:
			target_port = ""
		endpointstr = (":%s, " % target_port).join(endpoints)
		if len(endpointstr) > 0:
			endpointstr += ":%s" % target_port
		port_target_endpoints.append((f"{name}:{svcport}/{protocol}", f"{node_port}", f"{target_port}/{protocol}", endpointstr))

	if len(port_target_endpoints) == 0:
		port_target_endpoints = [("<none>", "", "", "")]

	return port_target_endpoints

def get_volume_properties(kh, obj, **kwargs):
	volume_properties = []

	# First find out what kind of volume we're dealing with
	pv_type = get_pv_type(obj)
	if pv_type is None:
		return volume_properties

	properties = deep_get(known_pv_types, f"{pv_type}#properties", {})
	for volume_property in properties:
		default = deep_get(properties, f"{volume_property}#default", "")
		path = deep_get(properties, f"{volume_property}#path", "")
		value = deep_get(obj, f"spec#{pv_type}#{path}", default)
		if isinstance(value, list):
			value = ",".join(value)
		elif isinstance(value, dict):
			value = ",".join(f"{key}:{val}" for (key, val) in value.items())
		# We don't need to check for bool, since it's a subclass of int
		elif isinstance(value, (int, float)):
			value = str(value)
		elif isinstance(value, str):
			value = value
		else:
			raise Exception(f"Unhandled type {type(value)} for {field}={value}")
		volume_properties.append([volume_property, value])

	return volume_properties

# Itemgetters acceptable for direct use in view files
itemgetter_allowlist = {
	"get_allowed_ips": get_allowed_ips,
	"get_endpoint_slices": get_endpoint_slices,
	"get_image_list": get_image_list,
	"get_key_value": get_key_value,
	"get_list_as_list": get_list_as_list,
	"get_list_fields": get_list_fields,
	"get_package_version_list": get_package_version_list,
	"get_pod_affinity": get_pod_affinity,
	"get_pod_tolerations": get_pod_tolerations,
	"get_resource_list": get_resource_list,
	"get_resources": get_resources,
	"get_strings_from_string": get_strings_from_string,
	"get_svc_port_target_endpoints": get_svc_port_target_endpoints,
	"get_volume_properties": get_volume_properties,
}
