#! /usr/bin/env python3

"""
Get items from lists for use in windowwidget
"""

import re
import sys
from typing import Any, cast, Dict, List, Optional, Tuple

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

from curses_helper import ThemeAttr, ThemeString, WidgetLineAttrs

from ikttypes import deep_get, deep_get_with_fallback, DictPath

import iktlib
from iktlib import disksize_to_human, get_package_versions, get_since, make_set_expression, split_msg, timestamp_to_datetime

import kubernetes_helper

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
#					"field_separators": [ThemeRef("separators", "host")]
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

# pylint: disable-next=unused-argument
def get_allowed_ips(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Dict]:
	"""
	Get a list of allowed IP-addresses

		Parameters:
			kh (KubernetesHelper): Unused
			obj (dict): The object to get data from
			kwargs (dict): Unused
		Returns:
			list[dict]: A list of allowed IPs
	"""

	allowed_ips = []

	# Safe
	ip_mask_regex = re.compile(r"^(\d+\.\d+\.\d+\.\d+)\/(\d+)")

	for addr in deep_get(obj, DictPath("spec#allowedIPs")):
		if "/" in addr:
			tmp = ip_mask_regex.match(addr)
			if tmp is None:
				raise ValueError(f"Could not parse {addr} as an address/address mask")
			ip = tmp[1]
			mask = tmp[2]
			allowed_ips.append({
				"lineattrs": WidgetLineAttrs.NORMAL,
				"columns": [[ThemeString(f"{ip}", ThemeAttr("windowwidget", "default")),
					     ThemeString("/", ThemeAttr("windowwidget", "dim")),
					     ThemeString(f"{mask}", ThemeAttr("windowwidget", "default"))]],
			})
		else:
			allowed_ips.append({
				"lineattrs": WidgetLineAttrs.NORMAL,
				"columns": [[ThemeString(f"{addr}", ThemeAttr("windowwidget", "default"))]],
			})

	return allowed_ips

# pylint: disable-next=unused-argument
def get_conditions(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Dict]:
	"""
	Get a list of conditions

		Parameters:
			kh (KubernetesHelper): Unused
			obj (dict): The object to get data from
			kwargs (dict): Additional parameters
		Returns:
			list[dict]: A list of conditions
	"""

	condition_list = []

	path = deep_get(kwargs, DictPath("path"), "status#conditions")

	for condition in deep_get(obj, DictPath(path), []):
		ctype = deep_get(condition, DictPath("type"), "")
		status = deep_get_with_fallback(condition, [DictPath("status"), DictPath("phase")], "")
		last_probe = deep_get(condition, DictPath("lastProbeTime"))
		if last_probe is None:
			last_probe = "<unset>"
		else:
			timestamp = timestamp_to_datetime(last_probe)
			last_probe = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
		last_transition = deep_get(condition, DictPath("lastTransitionTime"))
		if last_transition is None:
			last_transition = "<unset>"
		else:
			timestamp = timestamp_to_datetime(last_transition)
			last_transition = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
		message = deep_get(condition, DictPath("message"), "")
		condition_list.append({
			"fields": [ctype, status, last_probe, last_transition, message],
		})
	return condition_list

# pylint: disable-next=unused-argument
def get_endpoint_slices(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Tuple[str, str]]:
	"""
	Get a list of endpoint slices

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The object to get data from
			kwargs (dict): Unused
		Returns:
			list[(str, str)]: A list of endpoint slices
	"""

	svcname = deep_get(obj, DictPath("metadata#name"))
	svcnamespace = deep_get(obj, DictPath("metadata#namespace"))
	# We need to find all Endpoint Slices in the same namespace as the service that have this service
	# as its controller
	vlist, _status = kh.get_list_by_kind_namespace(("EndpointSlice", "discovery.k8s.io"), svcnamespace, label_selector = f"kubernetes.io/service-name={svcname}")
	tmp: List[Tuple[str, str]] = []
	if vlist is None or _status != 200:
		return tmp

	for item in vlist:
		epsnamespace = deep_get(item, DictPath("metadata#namespace"))
		epsname = deep_get(item, DictPath("metadata#name"))
		tmp.append((epsnamespace, epsname))
	return tmp

# pylint: disable-next=unused-argument
def get_events(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Dict]:
	"""
	Get a list of events

		Parameters:
			kh (KubernetesHelper): A reference to a KubernetesHelper object
			obj (dict): The object to get data from
			kwargs (dict): Unused
		Returns:
			list[dict]: A list of events
	"""

	event_list = []

	kind = deep_get(obj, DictPath("kind"))
	api_version = deep_get(obj, DictPath("apiVersion"), "")
	name = deep_get(obj, DictPath("metadata#name"))
	namespace = deep_get(obj, DictPath("metadata#namespace"), "")
	tmp = kh.get_events_by_kind_name_namespace(kh.kind_api_version_to_kind(kind, api_version), name, namespace)
	for event in tmp:
		event_list.append({
			"fields": event,
		})

	return event_list

# pylint: disable-next=unused-argument
def get_image_list(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Tuple[str, str]]:
	"""
	Get a list of container images

		Parameters:
			kh (KubernetesHelper): Unused
			obj (dict): The object to get data from
			kwargs (dict): Additional parameters
		Returns:
			list[dict]: A list of container images
	"""

	vlist = []
	path = deep_get(kwargs, DictPath("path"), "")

	for image in deep_get(obj, DictPath(path), []):
		name = ""
		for name in deep_get(image, DictPath("names"), []):
			# This is the preferred name
			if "@sha256:" not in name:
				break

		if len(name) == 0:
			continue
		size = disksize_to_human(deep_get(image, DictPath("sizeBytes"), "0"))
		vlist.append((name, size))
	return cast(List[Tuple[str, str]], natsorted(vlist))

# pylint: disable-next=unused-argument
def get_key_value(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Tuple[str, Any]]:
	"""
	Get a list of key/value data

		Parameters:
			kh (KubernetesHelper): Unused
			obj (dict): The object to get data from
			kwargs (dict): Additional parameters
		Returns:
			list[dict]: A list of key/value data
	"""

	vlist = []
	if "path" in kwargs:
		path = deep_get(kwargs, DictPath("path"), "")
		d = deep_get(obj, DictPath(path), {})

		for _key in d:
			_value = d[_key]
			if isinstance(_value, list):
				value = ",".join(_value)
			elif isinstance(_value, dict):
				value = ",".join(f"{key}:{val}" for (key, val) in _value.items())
			# We do not need to check for bool, since it is a subclass of int
			elif isinstance(_value, (int, float)):
				value = str(_value)
			elif isinstance(_value, str):
				value = _value
			else:
				raise TypeError(f"Unhandled type {type(_value)} for {_key}={value}")
			vlist.append((_key, value))
	return vlist

# pylint: disable-next=unused-argument
def get_list_as_list(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Any]:
	"""
	Get data in list format

		Parameters:
			kh (KubernetesHelper): Unused
			obj (dict): The object to get data from
			kwargs (dict): Additional parameters
		Returns:
			list[dict]: A list of data
	"""

	vlist: List[Any] = []
	if "path" in kwargs:
		raw_path = deep_get(kwargs, DictPath("path"))
		if isinstance(raw_path, str):
			raw_path = [raw_path]
		paths = []
		for path in raw_path:
			paths.append(DictPath(path))
		_regex = deep_get(kwargs, DictPath("regex"))
		if _regex is not None:
			compiled_regex = re.compile(_regex)
		for item in deep_get_with_fallback(obj, paths, []):
			if _regex is not None:
				tmp = compiled_regex.match(item)
				if tmp is not None:
					vlist.append(tmp.groups())
			else:
				vlist.append([item])
	elif "paths" in kwargs:
		# lists that run out of elements will return ""
		# strings will be treated as constants and thus returned for every row
		paths = deep_get(kwargs, DictPath("paths"), [])
		maxlen = 0
		for column in paths:
			tmp = deep_get(obj, DictPath(column))
			if isinstance(tmp, list):
				maxlen = max(len(tmp), maxlen)
		for i in range(0, maxlen):
			item = []
			for column in paths:
				tmp = deep_get(obj, DictPath(column))
				if isinstance(tmp, str):
					item.append(tmp)
				elif isinstance(tmp, list):
					if len(tmp) > i:
						item.append(tmp[i])
					else:
						item.append(" ")
			vlist.append(item)

	return vlist

# pylint: disable-next=unused-argument
def get_list_fields(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Any]:
	"""
	Get the specified fields from a dict list in list format

		Parameters:
			kh (KubernetesHelper): Unused
			obj (dict): The object to get data from
			kwargs (dict): Additional parameters
		Returns:
			list[dict]: A list of data
	"""

	vlist: List[Any] = []

	if "path" in kwargs and "fields" in kwargs:
		raw_path = deep_get(kwargs, DictPath("path"))
		if isinstance(raw_path, str):
			raw_path = [raw_path]
		paths = []
		for path in raw_path:
			paths.append(DictPath(path))
		fields = deep_get(kwargs, DictPath("fields"), [])
		pass_ref = deep_get(kwargs, DictPath("pass_ref"), False)
		override_types = deep_get(kwargs, DictPath("override_types"), [])
		for item in deep_get_with_fallback(obj, paths, []):
			tmp = []
			for i, field in enumerate(fields):
				default = ""
				if isinstance(field, dict):
					default = deep_get(field, DictPath("default"), "")
					field = deep_get(field, DictPath("name"))
				_value = deep_get(item, DictPath(field), default)
				if isinstance(_value, list) or (i < len(fields) and i < len(override_types) and override_types[i] == "list"):
					value = ", ".join(_value)
				elif isinstance(_value, dict) or (i < len(fields) and i < len(override_types) and override_types[i] == "dict"):
					value = ", ".join(f"{key}:{val}" for (key, val) in _value.items())
				# We do not need to check for bool, since it is a subclass of int
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

# pylint: disable-next=unused-argument
def get_package_version_list(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> Optional[List[Tuple[str, str]]]:
	name_path = deep_get(kwargs, DictPath("name_path"), "")
	hostname = deep_get(obj, DictPath(name_path))
	hostname = deep_get(kwargs, DictPath("name"), hostname)
	try:
		package_versions = get_package_versions(hostname)
	except ValueError:
		package_versions = None
	return package_versions

# pylint: disable-next=unused-argument
def get_pod_affinity(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Tuple[str, str, str, str, str]]:
	affinities: List[Tuple[str, str, str, str, str]] = []

	for affinity in deep_get(obj, DictPath("spec#affinity"), []):
		atype = affinity
		# Safe
		policy_regex = re.compile(r"^(ignored|preferred|required)DuringScheduling(Ignored|Preferred|Required)DuringExecution$")

		for policy in deep_get(obj, DictPath(f"spec#affinity#{atype}"), ""):
			tmp = policy_regex.match(policy)
			if tmp is None:
				scheduling = "Unknown"
				execution = "Unknown"
			else:
				scheduling = tmp[1].capitalize()
				execution = tmp[2]

			selectors = ""
			for item in deep_get(obj, DictPath(f"spec#affinity#{atype}#{policy}"), []):
				topology = ""
				if isinstance(item, dict):
					items = [item]
				elif isinstance(item, str):
					items = deep_get(obj, DictPath(f"spec#affinity#{atype}#{policy}#{item}"), [])

				for selector in items:
					weight = deep_get(selector, DictPath("weight"), "")
					if isinstance(weight, int):
						weight = f"/{weight}"
					topology = deep_get(selector, DictPath("topologyKey"), "")
					# We are combining a few different policies, so the expressions can be in various places; not simultaneously though
					selectors += make_set_expression(deep_get(selector, DictPath("labelSelector#matchExpressions"), {}))
					selectors += make_set_expression(deep_get(selector, DictPath("labelSelector#matchFields"), {}))
					selectors += make_set_expression(deep_get(selector, DictPath("preference#matchExpressions"), {}))
					selectors += make_set_expression(deep_get(selector, DictPath("preference#matchFields"), {}))
					selectors += make_set_expression(deep_get(selector, DictPath("matchExpressions"), {}))
					selectors += make_set_expression(deep_get(selector, DictPath("matchFields"), {}))
					affinities.append((atype, f"{scheduling}{weight}", execution, selectors, topology))

	return affinities

# pylint: disable-next=unused-argument
def get_prepopulated_list(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Dict]:
	items = deep_get(kwargs, DictPath("items"), [])

	vlist: List[Dict] = []

	for item in items:
		action = deep_get(item, DictPath("action"))
		action_call = deep_get(item, DictPath("action_call"))
		action_args = deep_get(item, DictPath("action_args"), {})
		kind = deep_get(action_args, DictPath("kind"))
		kind_path = deep_get(action_args, DictPath("kind_path"))
		kind = deep_get(obj, DictPath(kind_path), kind)
		api_family = deep_get(action_args, DictPath("api_family"), "")
		api_family_path = deep_get(action_args, DictPath("api_family_path"))
		api_family = deep_get(obj, DictPath(api_family_path), api_family)
		kind = deep_get(obj, DictPath(kind_path), kind)
		name_path = deep_get(action_args, DictPath("name_path"))
		name = deep_get(obj, DictPath(name_path))
		namespace_path = deep_get(action_args, DictPath("namespace_path"))
		namespace = deep_get(obj, DictPath(namespace_path), "")
		kind = kh.guess_kind((kind, api_family))
		columns = deep_get(item, DictPath("columns"), [])
		args = deep_get(action_args, DictPath("args"), {})

		vlist.append({
			"fields": columns,
			"ref": {
				"action": action,
				"action_call": action_call,
				"action_args": {
					"kind": kind,
					"name": name,
					"namespace": namespace,
					"args": args,
				},
			},
		})

	return vlist

# pylint: disable-next=unused-argument
def get_pod_tolerations(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Tuple[str, str, str, str, str]]:
	tolerations: List[Tuple[str, str, str, str, str]] = []

	for toleration in deep_get_with_fallback(obj, [DictPath("spec#tolerations"), DictPath("scheduling#tolerations")], []):
		effect = deep_get(toleration, DictPath("effect"), "All")
		key = deep_get(toleration, DictPath("key"), "All")
		operator = deep_get(toleration, DictPath("operator"), "Equal")

		# Eviction timeout
		toleration_seconds = deep_get(toleration, DictPath("tolerationSeconds"))
		if toleration_seconds is None:
			timeout = "Never"
		elif toleration_seconds <= 0:
			timeout = "Immediately"
		else:
			timeout = str(toleration_seconds)

		value = deep_get(toleration, DictPath("value"), "")
		tolerations.append((key, operator, value, effect, timeout))

	return tolerations

# pylint: disable-next=unused-argument
def get_resource_list(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Tuple[str, str, str]]:
	vlist: List[Tuple[str, str, str]] = []

	for res in deep_get(obj, DictPath("status#capacity"), {}):
		capacity = deep_get(obj, DictPath(f"status#capacity#{res}"), "")
		allocatable = deep_get(obj, DictPath(f"status#allocatable#{res}"), "")
		vlist.append((res, allocatable, capacity))
	return vlist

# pylint: disable-next=unused-argument
def get_resources(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Tuple[str, str, str]]:
	resources: List[Tuple[str, str, str]] = []

	for limit in list(deep_get(obj, DictPath("spec#resources#limits"), {})):
		if limit == "cpu":
			resources.append(("CPU", "Limit", deep_get(obj, DictPath("spec#resources#limits#cpu"))))
		elif limit == "memory":
			resources.append(("CPU", "Limit", deep_get(obj, DictPath("spec#resources#limits#memory"))))
		elif limit.startswith("hugepages-"):
			resources.append((f"H{limit[1:]}", "Limit", deep_get(obj, DictPath(f"spec#resources#limits#{limit}"))))

	for request in list(deep_get(obj, DictPath("spec#resources#requests"), {})):
		if request == "cpu":
			resources.append(("CPU", "Limit", deep_get(obj, DictPath("spec#resources#requests#cpu"))))
		elif request == "memory":
			resources.append(("CPU", "Limit", deep_get(obj, DictPath("spec#resources#requests#memory"))))
		elif request.startswith("hugepages-"):
			resources.append((f"H{request[1:]}", "Limit", deep_get(obj, DictPath(f"spec#resources#requests#{request}"))))

	return resources

# pylint: disable-next=unused-argument
def get_strings_from_string(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[List[str]]:
	vlist = []
	if "path" in kwargs:
		path = deep_get(kwargs, DictPath("path"))
		tmp = deep_get(obj, DictPath(path), [])
		if tmp is not None and len(tmp) > 0:
			for line in split_msg(tmp):
				vlist.append([line])
	return vlist

def get_endpoint_ips(subsets: List[Dict]) -> List[str]:
	endpoints = []
	notready = 0

	if subsets is None:
		return ["<none>"]

	for subset in subsets:
		# Keep track of whether we have not ready addresses
		if deep_get(subset, DictPath("notReadyAddresses")) is not None and len(deep_get(subset, DictPath("notReadyAddresses"))) > 0:
			notready += 1

		if deep_get(subset, DictPath("addresses")) is None:
			continue

		for address in deep_get(subset, DictPath("addresses"), []):
			endpoints.append(deep_get(address, DictPath("ip")))

	if len(endpoints) == 0:
		if notready > 0:
			return ["<not ready>"]
		return ["<none>"]

	return endpoints

# pylint: disable-next=unused-argument
def get_security_context(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Tuple[str, str]]:
	security_policies = []

	tmp = [
		("Run as User",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#runAsUser"),
			DictPath("spec#template#spec#securityContext#runAsUser")])),
		("Run as non-Root",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#runAsNonRoot"),
			DictPath("spec#template#spec#securityContext#runAsNonRoot")])),
		("Run as Group",
		deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#runAsGroup"),
			DictPath("spec#template#spec#securityContext#runAsGroup")])),
		("FS Group",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#fsGroup"),
			DictPath("spec#template#spec#securityContext#fsGroup")])),
		("FS Group-change Policy",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#fsGroupChangePolicy"),
			DictPath("spec#template#spec#securityContext#fsGroupChangePolicy")])),
		("Allow Privilege Escalation",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#allowPrivilegeEscalation"),
			DictPath("spec#template#spec#securityContext#allowPrivilegeEscalation")])),
		("Capabilities",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#capabilities"),
			DictPath("spec#template#spec#securityContext#capabilities")])),
		("Privileged",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#privileged"),
			DictPath("spec#template#spec#securityContext#privileged")])),
		("Proc Mount",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#procMount"),
			DictPath("spec#template#spec#securityContext#procMount")])),
		("Read-only Root Filesystem",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#readOnlyRootFilesystem"),
			DictPath("spec#template#spec#securityContext#readOnlyRootFilesystem")])),
		("SELinux Options",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#seLinuxOptions"),
			DictPath("spec#template#spec#securityContext#seLinuxOptions")])),
		("Seccomp Profile",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#seccompProfile"),
			DictPath("spec#template#spec#securityContext#seccompProfile")])),
		("Windows Options",
		 deep_get_with_fallback(obj, [
			DictPath("spec#securityContext#windowsOptions"),
			DictPath("spec#template#spec#securityContext#windowsOptions")])),
	]

	for policy in tmp:
		if policy[1] is not None:
			security_policies.append((policy[0], str(policy[1])))

	return security_policies

# pylint: disable-next=unused-argument
def get_svc_port_target_endpoints(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Tuple[str, str, str, str]]:
	svcname = deep_get(obj, DictPath("metadata#name"))
	svcnamespace = deep_get(obj, DictPath("metadata#namespace"))
	port_target_endpoints = []
	stype = deep_get(obj, DictPath("spec#type"))
	cluster_ip = deep_get(obj, DictPath("spec#clusterIP"))
	endpoints = []

	ref = kh.get_ref_by_kind_name_namespace(("Endpoints", ""), svcname, svcnamespace)
	endpoints = get_endpoint_ips(deep_get(ref, DictPath("subsets")))

	for port in deep_get(obj, DictPath("spec#ports"), []):
		name = deep_get(port, DictPath("name"), "")
		svcport = deep_get(port, DictPath("port"), "")
		protocol = deep_get(port, DictPath("protocol"), "")
		if stype in ("NodePort", "LoadBalancer"):
			node_port = deep_get(port, DictPath("nodePort"), "Auto Allocate")
		else:
			node_port = "N/A"
		if cluster_ip is not None:
			target_port = deep_get(port, DictPath("targetPort"), "")
		else:
			target_port = ""
		endpointstr = f":{target_port}, ".join(endpoints)
		if len(endpointstr) > 0:
			endpointstr += f":{target_port}"
		port_target_endpoints.append((f"{name}:{svcport}/{protocol}", f"{node_port}", f"{target_port}/{protocol}", endpointstr))

	if len(port_target_endpoints) == 0:
		port_target_endpoints = [("<none>", "", "", "")]

	return port_target_endpoints

def get_pv_type(obj: Dict) -> Optional[str]:
	for pv_type, _pv_data in KNOWN_PV_TYPES.items():
		if pv_type in deep_get(obj, DictPath("spec"), {}):
			return pv_type
	return None

# pylint: disable-next=unused-argument
def get_volume_properties(kh: kubernetes_helper.KubernetesHelper, obj: Dict, **kwargs: Dict) -> List[Tuple[str, str]]:
	volume_properties: List[Tuple[str, str]] = []

	# First find out what kind of volume we are dealing with
	pv_type = get_pv_type(obj)
	if pv_type is None:
		return volume_properties

	properties = deep_get(KNOWN_PV_TYPES, DictPath(f"{pv_type}#properties"), {})
	for key in properties:
		default = deep_get(properties, DictPath(f"{key}#default"), "")
		path = deep_get(properties, DictPath(f"{key}#path"), "")
		value = deep_get(obj, DictPath(f"spec#{pv_type}#{path}"), default)
		if isinstance(value, list):
			value = ",".join(value)
		elif isinstance(value, dict):
			value = ",".join(f"{key}:{val}" for (key, val) in value.items())
		# We do not need to check for bool, since it is a subclass of int
		elif isinstance(value, (int, float, str)):
			value = str(value)
		else:
			raise TypeError(f"Unhandled type {type(value)} for {key}={value}")
		volume_properties.append((key, value))

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
	"get_prepopulated_list": get_prepopulated_list,
	"get_resource_list": get_resource_list,
	"get_resources": get_resources,
	"get_strings_from_string": get_strings_from_string,
	"get_svc_port_target_endpoints": get_svc_port_target_endpoints,
	"get_volume_properties": get_volume_properties,
}
