#! /usr/bin/env python3

"""
Get items from lists for use in windowwidget
"""

import re
import sys

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

from curses_helper import WidgetLineAttrs

import iktlib
from iktlib import deep_get, deep_get_with_fallback, disksize_to_human, get_package_versions, get_since, make_set_expression, split_msg, timestamp_to_datetime

KNOWN_PV_TYPES = {
	"awsElasticBlockStore": {
		"type": "AWS Elastic Block Storage",
		"description": "Represents a Persistent Disk resource in AWS",
		"properties": {
			"Volume ID:": { "path": "volumeID" },
			"Partition #:": { "path": "partition" },
			"Filesystem Type:": { "path": "fsType", "default": "ext4" },
			"Read Only:": { "path": "readyOnly", "default": False },
		},
	},
	"azureDisk": {
		"type": "Azure Disk",
		"description": "Azure Data Disk mount on the host and bind mount to the pod",
		"properties": {
			"Disk Name:": { "path": "diskName" },
			"Disk URI:": { "path": "diskURI" },
			"Filesystem Type:": { "path": "fsType", "default": "ext4" },
			"Read Only:": { "path": "readyOnly", "default": False },
			"Caching Mode:": { "path": "cachingMode" },
			"Kind:": { "path": "kind", "default": "shared" },
		},
	},
	"azureFile": {
		"type": "Azure File",
		"description": "Azure File Service mount on the host and bind mount to the pod",
		"properties": {
			"Share Name:": { "path": "shareName" },
			"Read Only:": { "path": "readyOnly", "default": False },
			# These two should combine to a shortcut to a secret; needs formatting + helper
			"Secret Name:": { "path": "secretName" },
			"Secret Namespace:": { "path": "secretNamespace", "default": "<pod namespace>" },
		},
	},
	"cephfs": {
		"type": "Ceph",
		"properties": {
			"Path:": { "path": "path", "default": "/" },
#			"Monitors:": { "path": "monitors", "processor": field_processor_list },
			"Read Only:": { "path": "readOnly", "default": "False" },
			"Rados User": { "path": "user", "default": "admin" },
			# Should be a shortcut to a secret; needs formatting
			#"Secret:": { "path": "secretRef" },
			"Secret File:": { "path": "secretFile", "default": "/etc/ceph/user.secret" },
		},
	},
	"cinder": {
		# Deprecated
		"type": "OpenStack Cinder Volume",
		"properties": {
			"Volume ID:": { "path": "volumeID" },
			"Filesystem Type:": { "path": "fsType", "default": "ext4" },
			"Read Only:": { "path": "readOnly", "default": "False" },
			# Should be a shortcut to a secret; needs formatting
			#"Secret:": { "path": "secretRef" },
		},
	},
	"csi": {
		"type": "External CSI Volume",
		"description": "Storage managed by an external CSI volume driver",
		"properties": {
			"Volume Handle:": { "path": "volumeHandle" },
			"Driver:": { "path": "driver" },
			"Filesystem Type:": { "path": "fsType" },
			#{ "path": "controllerExpandSecretRef" },
			#{ "path": "controllerPublishSecretRef" },
			#{ "path": "nodeExpandSecretRef" },
			#{ "path": "nodePublishSecretRef" },
			"Read Only:": { "path": "readOnly" },
			#{ "path": "volumeAttributes" }, #dict(str, str)
		},
	},
	"fc": {
		"type": "Fibre Channel Volume",
		"properties": {
			"Filesystem Type:": { "path": "fsType", "default": "ext4" },
#			"WorldWide Identifiers:": { "path": "wwids", "processor": field_processor_list },
#			"Target WorldWide Names:": { "path": "targetWWNs", "processor": field_processor_list },
			"Logical Unit Number:": { "path": "lun" },
			"Read Only:": { "path": "readOnly", "default": "False" },
		},
	},
	"flexVolume": {
		"type": "FlexPersistentVolumeSource",
		"description": "Generic persistent volume resource provisioned/attached using an exec based plugin",
		"properties": {
			"Driver:": { "path": "driver" },
			"Filesystem Type:": { "path": "fsType", "default": "<script dependent>" },
			"Read Only:": { "path": "readOnly", "default": "False" },
			# Should be a shortcut to a secret; needs formatting
			#"Secret:": { "path": "secretRef" },
			"Options": { "path": "options", "default": {} },
		},
	},
	"flocker": {
		"type": "Flocker Volume",
		"description": "Flocker Volume mounted by the Flocker agent",
		"properties": {
			"Dataset Name:": { "path": "datasetName" },
			"Dataset UUID:": { "path": "datasetUUID" },
		},
	},
	"gcePersistentDisk": {
		"type": "GCE Persistent Disk",
		"description": "Google Compute Engine Persistent Disk resource",
		"properties": {
			"PD Name:": { "path": "pdName" },
			"Partition:": { "path": "partition" },
			"Filesystem Type:": { "path": "fsType", "default": "ext4" },
			"Read Only:": { "path": "readOnly", "default": "False" },
		},
	},
	"glusterfs": {
		"type": "GlusterFS",
		"description": "Glusterfs mount that lasts the lifetime of a pod",
		"properties": {
			"Path:": { "path": "path" },
			"Endpoints:": { "path": "endpoints" },
			"Endpoints Namespace:": { "path": "endpoints", "default": "<PVC namespace>" },
			"Read Only:": { "path": "readOnly", "default": "False" },
		},
	},
	"hostPath": {
		# Only works in single-node clusters
		"type": "Host Path",
		"description": "Host path mapped into a pod",
		"properties": {
			"Path:": { "path": "path" },
			"Host Path Type:": { "path": "type", "default": "" },
		},
	},
	"iscsi": {
		"type": "iSCSI Disk",
		"properties": {
			"iSCSI Qualified Name:": { "path": "iqn" },
			"Logical Unit Number:": { "path": "lun" },
			"Target Portal:": { "path": "targetPortal" },
#			"Target Portals:": { "path": "targetPortals", "processor": field_processor_list },
			"Filesystem Type:": { "path": "fsType", "default": "ext4" },
			"Chap Auth Discovery:": { "path": "chapAuthDiscovery" },
			"Chap Auth Session:": { "path": "chapAuthSession" },
			"iSCSI Initiator:": { "path": "initiatorName" },
			"iSCSI Interface:": { "path": "iscsiInterface", "default": "tcp" },
			"Read Only:": { "path": "readOnly", "default": "False" },
			# Should be a shortcut to a secret; needs formatting
			#"Secret:": { "path": "secretRef" },
		},
	},
	"local": {
		"type": "Local",
		"description": "Directly-attached storage with node affinity",
		"properties": {
			"Path:": { "path": "path" },
			"Filesystem Type:": { "path": "fsType", "default": "<auto-detect>" },
		},
	},
	"nfs": {
		"type": "NFS",
		"description": "NFS mount that lasts the lifetime of a pod",
		"properties": {
			"Server:": { "path": "server" },
			"Path:": { "path": "path" },
			"Read Only:": { "path": "readOnly", "default": "False" },
		},
	},
	"portworxVolume": {
		"type": "Portworx volume",
		"properties": {
			"Volume ID:": { "path": "volumeID" },
			"Filesystem Type:": { "path": "fsType", "default": "ext4" },
			"Read Only:": { "path": "readOnly", "default": "False" },
		},
	},
	"quobyte": {
		"type": "Quobyte Mount",
		"description": "Quobyte mount that lasts the lifetime of a pod",
		"properties": {
			"Volume Name:": { "path": "volume" },
#			"Registry:": {
#				"path": "registry",
#				"processor": field_processor_str_to_list,
#				"formatting": {
#					"iskeyvalue": True,
#					"field_separators": [("separators", "host")]
#				}
#			}, # str(host:port, host:port, ...)
			"Read Only:": { "path": "readOnly", "default": "False" },
			"Tenant:": { "path": "tenant" },
			"User:": { "path": "user", "default": "<service account user>" },
			"Group:": { "path": "group", "default": None },
		},
	},
	"rbd": {
		"type": "RBD",
		"description": "Rados Block Device mount that lasts the lifetime of a pod",
		"properties": {
			"Image:": { "path": "image" },
			"Pool:": { "path": "pool", "default": "rbd" },
			"Filesystem Type:": { "path": "fsType", "default": "ext4" },
#			"Monitors:": { "path": "monitors", "processor": field_processor_list },
			"Read Only:": { "path": "readOnly" },
			"Rados User": { "path": "user", "default": "admin" },
			"Keyring:": { "path": "keyring", "default": "/etc/ceph/keyring" },
			# Should be a shortcut to a secret; needs formatting
			#"Secret:": { "path": "secretRef" },
		},
	},
	"scaleIO": {
		# Deprecated
		"type": "Persistent ScaleIO Volume",
		"properties": {
			"Volume Name:": { "path": "volumeName" },
			"Gateway:": { "path": "gateway" },
			"Storage Pool:": { "path": "storagePool" },
			"Storage System:": { "path": "system" },
			"Storage Mode:": { "path": "storageMode", "default": "ThinProvisioned" },
			"Filesystem Type:": { "path": "fsType", "default": "xfs" },
			"Protection Domain:": { "path": "protectionDomain" },
			"SSL Enabled:": { "path": "sslEnabled", "default": "False" },
			"Read Only:": { "path": "readOnly" },
			# Should be a shortcut to a secret; needs formatting
			#"Secret:": { "path": "secretRef" },
		},
	},
	"storageos": {
		"type": "Persistent StorageOS Volume",
		"properties": {
			"Volume Name:": { "path": "volumeName" },
			"Volume Namespace:": { "path": "volumeNamespace", "default": "<pod namespace>" },
			"Filesystem Type:": { "path": "fsType", "default": "ext4" },
			"Read Only:": { "path": "readOnly" },
			# Should be a shortcut to a secret; needs formatting
			#"Secret:": { "path": "secretRef" },
		},
	},
	"vsphereVolume": {
		"type": "vSphere Volume",
		"properties": {
			"Volume Path:": { "path": "volumePath" },
			"Filesystem Type:": { "path": "fsType", "default": "ext4" },
			"Storage Policy ID:": { "path": "storagePolicyID" },
			"Storage Policy Name:": { "path": "storagePolicyName" },
		},
	},
}

def get_allowed_ips(kh, obj, **kwargs):
	del kh
	del kwargs

	allowed_ips = []

	# Safe
	ip_mask_regex = re.compile(r"^(\d+\.\d+\.\d+\.\d+)\/(\d+)")

	for addr in deep_get(obj, "spec#allowedIPs"):
		if "/" in addr:
			tmp = ip_mask_regex.match(addr)
			if tmp is None:
				raise ValueError(f"Could not parse {addr} as an address/address mask")
			ip = tmp[1]
			mask = tmp[2]
			allowed_ips.append({
				"lineattrs": WidgetLineAttrs.NORMAL,
				"columns": [[(f"{ip}", ("windowwidget", "default")), ("/", ("windowwidget", "dim")), (f"{mask}", ("windowwidget", "default"))]],
			})
		else:
			allowed_ips.append({
				"lineattrs": WidgetLineAttrs.NORMAL,
				"columns": [[(f"{addr}", ("windowwidget", "default"))]],
			})

	return allowed_ips

def get_conditions(kh, obj, **kwargs):
	del kh

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
	del kwargs

	svcname = deep_get(obj, "metadata#name")
	svcnamespace = deep_get(obj, "metadata#namespace")
	# We need to find all Endpoint Slices in the same namespace as the service that have this service
	# as its controller
	vlist, _status = kh.get_list_by_kind_namespace(("EndpointSlice", "discovery.k8s.io"), svcnamespace, label_selector = f"kubernetes.io/service-name={svcname}")
	tmp = []
	for item in vlist:
		epsnamespace = deep_get(item, "metadata#namespace")
		epsname = deep_get(item, "metadata#name")
		tmp.append([epsnamespace, epsname])
	return tmp

def get_events(kh, obj, **kwargs):
	del kwargs

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
	del kh

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
	del kh

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
				raise TypeError(f"Unhandled type {type(_value)} for {_key}={value}")
			vlist.append([_key, value])

	return vlist

def get_list_as_list(kh, obj, **kwargs):
	del kh

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
	del kh

	vlist = []

	if "path" in kwargs and "fields" in kwargs:
		path = deep_get(kwargs, "path")
		fields = deep_get(kwargs, "fields", [])
		pass_ref = deep_get(kwargs, "pass_ref", False)
		override_types = deep_get(kwargs, "override_types", [])
		for item in deep_get(obj, path, []):
			tmp = []
			for i, field in enumerate(fields):
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
	del kh

	name_path = deep_get(kwargs, "name_path", "")
	hostname = deep_get(obj, name_path)
	hostname = deep_get(kwargs, "name", hostname)
	try:
		package_versions = get_package_versions(hostname)
	except ValueError:
		package_versions = None
	return package_versions

def get_pod_affinity(kh, obj, **kwargs):
	del kh
	del kwargs

	affinities = []

	for affinity in deep_get(obj, "spec#affinity", []):
		atype = affinity
		# Safe
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
					weight = deep_get(selector, "weight", "")
					if isinstance(weight, int):
						weight = f"/{weight}"
					topology = deep_get(selector, "topologyKey", "")
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
	del kh
	del kwargs

	tolerations = []

	for toleration in deep_get_with_fallback(obj, ["spec#tolerations", "scheduling#tolerations"], []):
		effect = deep_get(toleration, "effect", "All")
		key = deep_get(toleration, "key", "All")
		operator = deep_get(toleration, "operator", "Equal")

		# Eviction timeout
		toleration_seconds = deep_get(toleration, "tolerationSeconds")
		if toleration_seconds is None:
			timeout = "Never"
		elif toleration_seconds <= 0:
			timeout = "Immediately"
		else:
			timeout = str(toleration_seconds)

		value = deep_get(toleration, "value", "")
		tolerations.append([key, operator, value, effect, timeout])

	return tolerations

def get_resource_list(kh, obj, **kwargs):
	del kh
	del kwargs

	vlist = []

	for res in deep_get(obj, "status#capacity", {}):
		capacity = deep_get(obj, f"status#capacity#{res}", "")
		allocatable = deep_get(obj, f"status#allocatable#{res}", "")
		vlist.append([res, allocatable, capacity])
	return vlist

def get_resources(kh, obj, **kwargs):
	del kh
	del kwargs

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
	del kh

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

	if len(endpoints) == 0:
		if notready > 0:
			return ["<not ready>"]
		return ["<none>"]

	return endpoints

def get_security_context(kh, obj, **kwargs):
	del kh
	del kwargs

	security_policies = []

	tmp = [
		("Run as User",
		 deep_get_with_fallback(obj, ["spec#securityContext#runAsUser", "spec#template#spec#securityContext#runAsUser"])),
		("Run as non-Root",
		 deep_get_with_fallback(obj, ["spec#securityContext#runAsNonRoot", "spec#template#spec#securityContext#runAsNonRoot"])),
		("Run as Group",
		 deep_get_with_fallback(obj, ["spec#securityContext#runAsGroup", "spec#template#spec#securityContext#runAsGroup"])),
		("FS Group",
		 deep_get_with_fallback(obj, ["spec#securityContext#fsGroup", "spec#template#spec#securityContext#fsGroup"])),
		("FS Group-change Policy",
		 deep_get_with_fallback(obj, ["spec#securityContext#fsGroupChangePolicy", "spec#template#spec#securityContext#fsGroupChangePolicy"])),
		("Allow Privilege Escalation",
		 deep_get_with_fallback(obj, ["spec#securityContext#allowPrivilegeEscalation", "spec#template#spec#securityContext#allowPrivilegeEscalation"])),
		("Capabilities",
		 deep_get_with_fallback(obj, ["spec#securityContext#capabilities", "spec#template#spec#securityContext#capabilities"])),
		("Privileged",
		 deep_get_with_fallback(obj, ["spec#securityContext#privileged", "spec#template#spec#securityContext#privileged"])),
		("Proc Mount",
		 deep_get_with_fallback(obj, ["spec#securityContext#procMount", "spec#template#spec#securityContext#procMount"])),
		("Read-only Root Filesystem",
		 deep_get_with_fallback(obj, ["spec#securityContext#readOnlyRootFilesystem", "spec#template#spec#securityContext#readOnlyRootFilesystem"])),
		("SELinux Options",
		 deep_get_with_fallback(obj, ["spec#securityContext#seLinuxOptions", "spec#template#spec#securityContext#seLinuxOptions"])),
		("Seccomp Profile",
		 deep_get_with_fallback(obj, ["spec#securityContext#seccompProfile", "spec#template#spec#securityContext#seccompProfile"])),
		("Windows Options",
		 deep_get_with_fallback(obj, ["spec#securityContext#windowsOptions", "spec#template#spec#securityContext#windowsOptions"])),
	]

	for policy in tmp:
		if policy[1] is not None:
			security_policies.append([policy[0], str(policy[1])])

	return security_policies

def get_svc_port_target_endpoints(kh, obj, **kwargs):
	del kwargs

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
		if stype in ("NodePort", "LoadBalancer"):
			node_port = deep_get(port, "nodePort", "Auto Allocate")
		else:
			node_port = "N/A"
		if cluster_ip is not None:
			target_port = deep_get(port, "targetPort", "")
		else:
			target_port = ""
		endpointstr = f":{target_port}, ".join(endpoints)
		if len(endpointstr) > 0:
			endpointstr += f":{target_port}"
		port_target_endpoints.append((f"{name}:{svcport}/{protocol}", f"{node_port}", f"{target_port}/{protocol}", endpointstr))

	if len(port_target_endpoints) == 0:
		port_target_endpoints = [("<none>", "", "", "")]

	return port_target_endpoints

def get_pv_type(obj):
	for pv_type, _pv_data in KNOWN_PV_TYPES.items():
		if pv_type in deep_get(obj, "spec", []):
			return pv_type
	return None

def get_volume_properties(kh, obj, **kwargs):
	del kh
	del kwargs

	volume_properties = []

	# First find out what kind of volume we're dealing with
	pv_type = get_pv_type(obj)
	if pv_type is None:
		return volume_properties

	properties = deep_get(KNOWN_PV_TYPES, f"{pv_type}#properties", {})
	for key in properties:
		default = deep_get(properties, f"{key}#default", "")
		path = deep_get(properties, f"{key}#path", "")
		value = deep_get(obj, f"spec#{pv_type}#{path}", default)
		if isinstance(value, list):
			value = ",".join(value)
		elif isinstance(value, dict):
			value = ",".join(f"{key}:{val}" for (key, val) in value.items())
		# We don't need to check for bool, since it's a subclass of int
		elif isinstance(value, (int, float, str)):
			value = str(value)
		else:
			raise TypeError(f"Unhandled type {type(value)} for {key}={value}")
		volume_properties.append([key, value])

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
