import base64
from functools import reduce
import hashlib
# ujson is much faster than json,
# but it might not be available
try:
	import ujson as json
except:
	import json
from pathlib import Path
import re
import sys
import tempfile
import yaml

try:
	import urllib3
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-urllib3")

try:
	import OpenSSL
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-openssl")

from iktlib import deep_get, stgroup, versiontuple, timestamp_to_datetime, get_since

class KubernetesHelper:
	tmp_ca_certs_file = None
	tmp_cert_file = None
	tmp_key_file = None
	programname = ""
	programversion = ""

	def validate_name(self, rtype, name):
		invalid = False
		tmp = None

		if name is None:
			return False

		if rtype in ["dns-subdomain", "dns-label"]:
			if rtype == "dns-label":
				maxlen = 63
				if "." in name:
					invalid = True
			else:
				maxlen = 253

			# A dns-subdomain can be at most 253 characters long
			# and cannot start or end with "-"; it must be made up
			# of valid dns-labels; each of which are separated by "."
			# and have to meet the same standards as a dns-label
			labels = name.lower().split(".")

			for label in labels:
				if len(label) > 63:
					invalid = True
					break

				tmp = re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", label)
				if tmp is None:
					break
		elif rtype in ["path-segment"]:
			# XXX: Are there any other requirements? maxlen or similar?
			if name in [".", ".."] or "/" in name or "%" in name:
				invalid = True
			tmp = ""
			import os
			maxlen = os.pathconf("/", "PC_NAME_MAX")
		elif rtype in ["port-name"]:
			# Any name containing adjacent "-" is invalid
			if "--" in name:
				invalid = True
			# As is any port-name that doesn't contain any character in [a-z]
			if re.match(r".*[a-z].*", name.lower()) is None:
				invalid = True
			# A portname can be at most 15 characters long
			# and cannot start or end with "-"
			tmp = re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", name.lower())
			maxlen = 15

		return invalid == False and tmp is not None and len(name) <= maxlen

	# Returns a list of (current [current-context], name [context], cluster, authinfo [user], namespace)
	def list_contexts(self, config_path = None):
		contexts = []

		# If config_path == None we use ${HOME}/.kube/config
		if config_path == None:
			# Read kubeconfig
			config_path = str(Path.home()) + "/.kube/config"

		try:
			with open(config_path, "r") as f:
				kubeconfig = yaml.safe_load(f)
		except FileNotFoundError:
			return []

		current_context = deep_get(kubeconfig, "current-context", "")

		for context in deep_get(kubeconfig, "contexts", []):
			name = deep_get(context, "name")
			current = (name == current_context)
			namespace = deep_get(context, "namespace", "default")
			authinfo = deep_get(context, "context#user")
			cluster = deep_get(context, "context#cluster")
			contexts.append((current, name, cluster, authinfo, namespace))
		return contexts

	# Returns a list of (cluster, context),
	# with only one context per cluster (priority given to contexts with admin in the username)
	def list_clusters(self, config_path = None):
		contexts = self.list_contexts(config_path = config_path)
		__clusters = {}
		clusters = []

		for context in contexts:
			name = context[1]
			cluster = context[2]

			if cluster not in __clusters:
				__clusters[cluster] = {
					"contexts": [],
				}
			__clusters[cluster]["contexts"].append(name)

		# If we find a context that mentions admin, pick that one,
		# otherwise just find the first context for each cluster
		for cluster in __clusters:
			for context in __clusters[cluster]["contexts"]:
				# We don't want to risk matches where the *cluster* is named admin
				tmp = re.match(r"admin.*@", context)
				if tmp is not None:
					clusters.append((cluster, context))
					continue
			# Nope, no context mentions admin
			clusters.append((cluster, __clusters[cluster]["contexts"][0]))
		return clusters

	# Returns False if the context wasn't changed (for whatever reason)
	def set_context(self, config_path = None, name = None):
		context_name = ""
		cluster_name = ""
		user_name = ""
		namespace_name = ""

		# If config_path == None we use ${HOME}/.kube/config
		if config_path == None:
			# Read kubeconfig
			config_path = str(Path.home()) + "/.kube/config"

		try:
			with open(config_path, "r") as f:
				kubeconfig = yaml.safe_load(f)
		except FileNotFoundError:
			return False

		current_context = deep_get(kubeconfig, "current-context", "")

		unchanged = True
		# If we didn't get a context name we try current-context
		if name is None or len(name) == 0:
			unchanged = False
			name = current_context

		for context in deep_get(kubeconfig, "contexts", []):
			# If we still don't have a context name,
			# pick the first match
			if len(name) == 0 or deep_get(context, "name") == name:
				context_name = deep_get(context, "name")
				user_name = deep_get(context, "context#user", "")
				cluster_name = deep_get(context, "context#cluster", "")
				namespace_name = deep_get(context, "context#namespace", "")
				break

		if unchanged == True and current_context == context_name:
			return False

		control_plane_ip = None
		control_plane_port = None
		insecuretlsskipverify = False
		ca_certs = None

		# OK, we have a user and a cluster to look for

		for cluster in deep_get(kubeconfig, "clusters", []):
			if deep_get(cluster, "name") != cluster_name:
				continue

			tmp = re.match(r"https?://(.*):(\d+)", cluster["cluster"]["server"])
			if tmp is not None:
				control_plane_ip = tmp[1]
				control_plane_port = tmp[2]

			insecuretlsskipverify = deep_get(cluster, "cluster#insecure-skip-tls-verify", False)
			if insecuretlsskipverify == True:
				break

			# ca_certs
			ccac = deep_get(cluster, "cluster#certificate-authority-data")
			try:
				ca_certs = base64.b64decode(ccac).decode("utf-8")
			except UnicodeDecodeError as e:
				raise Exception("failed to decode certificate-authority-data: {e}")
			break

		if control_plane_ip is None or control_plane_port is None:
			return False

		# OK, we have a cluster, try to find a user

		cert = None
		key = None
		self.token = None

		for user in deep_get(kubeconfig, "users", []):
			if deep_get(user, "name") == user_name:
				# cert
				ccd = deep_get(user, "user#client-certificate-data")
				if ccd is not None:
					try:
						cert = base64.b64decode(ccd).decode("utf-8")
					except UnicodeDecodeError as e:
						raise Exception(f"failed to decode client-certificate-data: {e}")

				# key
				ckd = deep_get(user, "user#client-key-data")
				if ckd is not None:
					try:
						key = base64.b64decode(ckd).decode("utf-8")
					except UnicodeDecodeError as e:
						raise Exception(f"failed to decode client-key-data: {e}")

				self.token = deep_get(user, "user#token")
				break

		# We don't have the cert or token needed to access the server
		if self.token is None and (cert is None or key is None):
			return False

		# We cannot authenticate the server correctly
		if ca_certs is None and insecuretlsskipverify == False:
			return False

		# OK, we've got the cluster IP and port,
		# as well as the certs we need; time to switch context

		# If we're switching contexts we might have open files
		self.__close_certs()

		self.control_plane_ip = control_plane_ip
		self.control_plane_port = control_plane_port

		if insecuretlsskipverify == False:
			self.tmp_ca_certs_file = tempfile.NamedTemporaryFile()
			self.tmp_ca_certs_file.write(ca_certs.encode("utf-8"))
			self.tmp_ca_certs_file.flush()
		else:
			urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

		# If we have a cert we also have a key
		if cert is not None:
			self.tmp_cert_file = tempfile.NamedTemporaryFile()
			self.tmp_key_file = tempfile.NamedTemporaryFile()

			self.tmp_cert_file.write(cert.encode("utf-8"))
			self.tmp_cert_file.flush()

			self.tmp_key_file.write(key.encode("utf-8"))
			self.tmp_key_file.flush()

			if insecuretlsskipverify == False:
				self.pool_manager = urllib3.PoolManager(
					cert_reqs = "CERT_REQUIRED",
					ca_certs = self.tmp_ca_certs_file.name,
					cert_file = self.tmp_cert_file.name,
					key_file = self.tmp_key_file.name)
			else:
				self.pool_manager = urllib3.PoolManager(
					cert_reqs = "CERT_NONE",
					ca_certs = None,
					cert_file = self.tmp_cert_file.name,
					key_file = self.tmp_key_file.name)
		elif self.token is not None:
			if insecuretlsskipverify == False:
				self.pool_manager = urllib3.PoolManager(
					cert_reqs = "CERT_REQUIRED",
					ca_certs = self.tmp_ca_certs_file.name)
			else:
				self.pool_manager = urllib3.PoolManager(
					cert_reqs = "CERT_NONE",
					ca_certs = None)

		self.cluster_unreachable = False
		self.context_name = context_name

		# If we're switching contexts, update the config file
		if context_name != current_context:
			kubeconfig["current-context"] = context_name

		yaml_str = yaml.safe_dump(kubeconfig, default_flow_style = False)

		with open(config_path, "w") as f:
			f.write(yaml_str)

		return True

	def make_selector(self, selector_dict):
		selectors = []

		if selector_dict is not None:
			for key, value in selector_dict.items():
				selectors.append(f"{key}={value}")

		return ",".join(selectors)

	def get_image_version(self, image, default = "<undefined>"):
		tmp = re.match(r"^.*:(.*)", image)
		if tmp is not None:
			image_version = f"{tmp[1]}"
		else:
			image_version = default
		return image_version

	# CNI detection helpers
	def __identify_cni(self, cni_name, controller_kind, controller_selector, container_name):
		cni = []

		# Is there a controller matching the kind we're looking for?
		vlist, status = self.get_list_by_kind_namespace(controller_kind, "", field_selector = controller_selector)

		if len(vlist) == 0:
			return cni

		cni_matches = 0
		pod_matches = 0
		cni_version = None
		cni_status = ("<unknown>", stgroup.UNKNOWN, "Could not get status")

		# 2. Are there > 0 pods matching the label selector?
		for obj in vlist:
			if controller_kind == ("Deployment", "apps"):
				cni_status = ("Unavailable", stgroup.NOT_OK)
				for condition in deep_get(obj, "status#conditions"):
					ctype = deep_get(condition, "type")
					if ctype == "Available":
						cni_status = (ctype, stgroup.OK)
						break
			elif controller_kind == ("DaemonSet", "apps"):
				if deep_get(obj, "status#numberUnavailable", 0) > deep_get(obj, "status#maxUnavailable", 0):
					cni_status = ("Unavailable", stgroup.NOT_OK, "numberUnavailable > maxUnavailable")
				else:
					cni_status = ("Available", stgroup.OK, "")

			vlist2, status = self.get_list_by_kind_namespace(("Pod", ""), "", label_selector = self.make_selector(deep_get(obj, "spec#selector#matchLabels")))

			if vlist2 is not None and len(vlist2) > 0:
				for obj2 in vlist2:
					# Try to get the version
					for container in deep_get(obj2, "status#containerStatuses", []):
						if deep_get(container, "name", "") == container_name:
							image_version = self.get_image_version(deep_get(container, "image", ""))

							if image_version != "<undefined>":
								if cni_version is None:
									cni_version = image_version
									pod_matches += 1
								elif versiontuple(image_version) > versiontuple(cni_version):
									cni_version = image_version
									pod_matches += 1
								elif image_version != cni_version:
									cni_version = image_version
									pod_matches += 1

		if cni_version is None:
			cni_version = "<unknown>"

		if pod_matches == 0:
			cni.append((cni_name, "<incomplete>", cni_status))
		elif pod_matches == 1:
			cni.append((cni_name, f"{cni_version}", cni_status))
		else:
			cni.append((cni_name, f"{cni_version}*", cni_status))

		return cni

	def identify_cni(self):
		cni = []

		# We're gonna have to do some sleuthing here
		# Antrea:
		cni += self.__identify_cni("antrea", ("DaemonSet", "apps"), "metadata.name=antrea-agent", "antrea-agent")
		# Canal:
		cni += self.__identify_cni("canal", ("DaemonSet", "apps"), "metadata.name=canal", "calico-node")
		# Calico:
		# Since canal is a combination of Calico and Flannel we need to skip Calico if Canal is detected
		if "canal" not in [cni_name for cni_name, cni_version, cni_status in cni]:
			cni += self.__identify_cni("calico", ("Deployment", "apps"), "metadata.name=calico-kube-controllers", "calico-kube-controllers")
		# Cilium:
		cni += self.__identify_cni("cilium", ("Deployment", "apps"), "metadata.name=cilium-operator", "cilium-operator")
		# Flannel:
		cni += self.__identify_cni("flannel", ("DaemonSet", "apps"), "metadata.name=kube-flannel-ds", "kube-flannel")
		# Kilo:
		cni += self.__identify_cni("kilo", ("DaemonSet", "apps"), "metadata.name=kilo", "kilo")
		# Kube-router:
		cni += self.__identify_cni("kube-router", ("DaemonSet", "apps"), "metadata.name=kube-router", "kube-router")
		# Weave:
		cni += self.__identify_cni("weave", ("DaemonSet", "apps"), "metadata.name=weave-net", "weave")

		return cni

	def get_node_roles(self, node):
		roles = []

		for label in deep_get(node, "metadata#labels", {}).items():
			tmp = re.match(r"^node-role\.kubernetes\.io/(.*)", label[0])

			if tmp is None:
				continue

			role = tmp[1]

			if role == "master":
				role = "control-plane"

			if role not in roles:
				roles.append(role)

		return roles

	def __close_certs(self):
		if self.tmp_ca_certs_file is not None:
			self.tmp_ca_certs_file.close()
		if self.tmp_cert_file is not None:
			self.tmp_cert_file.close()
		if self.tmp_key_file is not None:
			self.tmp_key_file.close()

	def __init__(self, programname, programversion, config_path = None):
		self.programname = programname
		self.programversion = programversion
		self.cluster_unreachable = True
		self.context_name = ""

		self.set_context(config_path = config_path)

	def __del__(self):
		self.__close_certs()
		self.context_name = ""

	def is_cluster_reachable(self):
		return self.cluster_unreachable == False

	def get_control_plane_address(self, cluster = ""):
		return self.control_plane_ip, self.control_plane_port

	def get_join_token(self):
		join_token = ""

		vlist, status = self.get_list_by_kind_namespace(("Secret", ""), "kube-system")

		if len(vlist) == 0:
			return join_token

		age = -1

		# Find the newest bootstrap token
		for secret in vlist:
			name = deep_get(secret, "metadata#name")
			if name.startswith("bootstrap-token-"):
				timestamp = timestamp_to_datetime(deep_get(secret, "metadata#creationTimestamp"))
				newage = get_since(timestamp)
				if age == -1 or newage < age:
					try:
						tmp1 = base64.b64decode(deep_get(secret, "data#token-id", "")).decode("utf-8")
					except UnicodeDecodeError as e:
						tmp1 = secret.data.get("data#token-id", "")

					try:
						tmp2 = base64.b64decode(deep_get(secret, "data#token-secret", "")).decode("utf-8")
					except UnicodeDecodeError as e:
						tmp2 = deep_get(secret, "data#token-secret", "")

					if tmp1 != "" and tmp2 != "":
						join_token = f"{tmp1}.{tmp2}"
						age = newage

		return join_token

	def get_ca_cert_hash(self):
		ca_cert_hash = ""

		vlist, status = self.get_list_by_kind_namespace(("Secret", ""), "kube-system")

		if len(vlist) == 0:
			return ca_cert_hash

		age = -1
		ca_cert = ""

		# Find the newest certificate-controller-token
		for secret in vlist:
			if deep_get(secret, "metadata#name").startswith("certificate-controller-token-"):
				timestamp = timestamp_to_datetime(deep_get(secret, "metadata#creationTimestamp"))
				newage = get_since(timestamp)
				if age == -1 or newage < age:
					try:
						tmp1 = base64.b64decode(deep_get(secret, "data#ca.crt", "")).decode("utf-8")
					except UnicodeDecodeError as e:
						tmp1 = deep_get(secret, "data#ca.crt", "")

					if tmp1 != "":
						ca_cert = tmp1
						age = newage

		# we have the CA cert; now to extract the public key and hash it
		if ca_cert != "":
			x509obj = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, ca_cert)
			pubkey = x509obj.get_pubkey()
			pubkeyasn1 = OpenSSL.crypto.dump_publickey(OpenSSL.crypto.FILETYPE_ASN1, pubkey)
			ca_cert_hash = hashlib.sha256(pubkeyasn1).hexdigest()

		return ca_cert_hash


	# A list of all K8s resources we have some knowledge about
	kubernetes_resources = {
		# core API
		# ComponentStatus is deprecated
		("ComponentStatus", ""): {
			"api_family": ["api/v1/"],
			"api": "componentstatuses",
		},
		("ConfigMap", ""): {
			"api_family": ["api/v1/"],
			"api": "configmaps",
		},
		("Endpoints", ""): {
			"api_family": ["api/v1/"],
			"api": "endpoints",
		},
		("Event", ""): {
			"api_family": ["/apis/events.k8s.io/v1/", "api/v1/"],
			"api": "events",
		},
		("LimitRange", ""): {
			"api_family": ["api/v1/"],
			"api": "limitranges",
		},
		("Namespace", ""): {
			"api_family": ["api/v1/"],
			"api": "namespaces",
			"namespaced": False,
		},
		("Node", ""): {
			"api_family": ["api/v1/"],
			"api": "nodes",
			"namespaced": False,
		},
		("PersistentVolume", ""): {
			"api_family": ["api/v1/"],
			"api": "persistentvolumes",
			"namespaced": False,
		},
		("PersistentVolumeClaim", ""): {
			"api_family": ["api/v1/"],
			"api": "persistentvolumeclaims",
		},
		("Pod", ""): {
			"api_family": ["api/v1/"],
			"api": "pods",
		},
		("PodTemplate", ""): {
			"api_family": ["api/v1/"],
			"api": "podtemplates",
		},
		("ReplicationController", ""): {
			"api_family": ["api/v1/"],
			"api": "replicationcontrollers",
		},
		("ResourceQuota", ""): {
			"api_family": ["api/v1/"],
			"api": "resourcequotas",
		},
		("Secret", ""): {
			"api_family": ["api/v1/"],
			"api": "secrets",
		},
		("Service", ""): {
			"api_family": ["api/v1/"],
			"api": "services",
		},
		("ServiceAccount", ""): {
			"api_family": ["api/v1/"],
			"api": "serviceaccounts",
		},
		# admissionregistration.k8s.io
		("MutatingWebhookConfiguration", "admissionregistration.k8s.io"): {
			"api_family": ["apis/admissionregistration.k8s.io/v1/", "apis/admissionregistration.k8s.io/v1beta1/"],
			"api": "mutatingwebhookconfigurations",
			"namespaced": False,
		},
		("ValidatingWebhookConfiguration", "admissionregistration.k8s.io"): {
			"api_family": ["apis/admissionregistration.k8s.io/v1/", "apis/admissionregistration.k8s.io/v1beta1/"],
			"api": "validatingwebhookconfigurations",
			"namespaced": False,
		},
		# apiextensions.k8s.io
		("CustomResourceDefinition", "apiextensions.k8s.io"): {
			"api_family": ["apis/apiextensions.k8s.io/v1/", "apis/apiextensions.k8s.io/v1beta1/"],
			"api": "customresourcedefinitions",
			"namespaced": False,
		},
		# apiregistration.k8s.io
		("APIService", "apiregistration.k8s.io"): {
			"api_family": ["apis/apiregistration.k8s.io/v1/"],
			"api": "apiservices",
			"namespaced": False,
		},
		# app.k8s.io
		("Application", "app.k8s.io"): {
			"api_family": ["apis/app.k8s.io/v1beta1/"],
			"api": "applications",
		},
		# apps
		("ControllerRevision", "apps"): {
			"api_family": ["apis/apps/v1/"],
			"api": "controllerrevisions",
		},
		("DaemonSet", "apps"): {
			"api_family": ["apis/apps/v1/"],
			"api": "daemonsets",
		},
		("Deployment", "apps"): {
			"api_family": ["apis/apps/v1/"],
			"api": "deployments",
		},
		("ReplicaSet", "apps"): {
			"api_family": ["apis/apps/v1/"],
			"api": "replicasets",
		},
		("StatefulSet", "apps"): {
			"api_family": ["apis/apps/v1/"],
			"api": "statefulsets",
		},
		# autoscaling
		("HorizontalPodAutoscaler", "autoscaling"): {
			"api_family": ["apis/autoscaling/v2/", "apis/autoscaling/v2beta2/", "apis/autoscaling/v1/"],
			"api": "horizontalpodautoscalers",
		},
		# batch
		("CronJob", "batch"): {
			"api_family": ["apis/batch/v1/", "apis/batch/v1beta1/"],
			"api": "cronjobs",
		},
		("Job", "batch"): {
			"api_family": ["apis/batch/v1/", "apis/batch/v1beta1/"],
			"api": "jobs",
		},
		# certificates.k8s.io
		("CertificateSigningRequest", "certificates.k8s.io"): {
			"api_family": ["apis/certificates.k8s.io/v1/"],
			"api": "certificatesigningrequests",
			"namespaced": False,
		},
		# coordination.k8s.io
		("Lease", "coordination.k8s.io"): {
			"api_family": ["apis/coordination.k8s.io/v1/"],
			"api": "leases",
		},
		# discovery.k8s.io
		("EndpointSlice", "discovery.k8s.io"): {
			"api_family": ["apis/discovery.k8s.io/v1/", "apis/discovery.k8s.io/v1beta1/"],
			"api": "endpointslices",
		},
		# flowcontrol.apiserver.k8s.io
		("FlowSchema", "flowcontrol.apiserver.k8s.io"): {
			"api_family": ["apis/flowcontrol.apiserver.k8s.io/v1beta2/", "apis/flowcontrol.apiserver.k8s.io/v1beta1/"],
			"api": "flowschemas",
			"namespaced": False,
		},
		("PriorityLevelConfiguration", "flowcontrol.apiserver.k8s.io"): {
			"api_family": ["apis/flowcontrol.apiserver.k8s.io/v1beta2/", "apis/flowcontrol.apiserver.k8s.io/v1beta1/"],
			"api": "prioritylevelconfigurations",
			"namespaced": False,
		},
		# metacontroller.k8s.io
		("CompositeController", "metacontroller.k8s.io"): {
			"api_family": ["apis/metacontroller.k8s.io/v1alpha1/"],
			"api": "compositecontrollers",
			"namespaced": False,
		},
		("ControllerRevision", "metacontroller.k8s.io"): {
			# => "apps" ?
			"api_family": ["apis/metacontroller.k8s.io/v1alpha1/"],
			"api": "controllerrevisions",
		},
		("DecoratorController", "metacontroller.k8s.io"): {
			"api_family": ["apis/metacontroller.k8s.io/v1alpha1/"],
			"api": "decoratorcontrollers",
			"namespaced": False,
		},
		# networking.k8s.io
		("Ingress", "networking.k8s.io"): {
			"api_family": ["apis/networking.k8s.io/v1/", "apis/networking.k8s.io/v1beta1/"],
			"api": "ingresses",
		},
		("IngressClass", "networking.k8s.io"): {
			"api_family": ["apis/networking.k8s.io/v1/", "apis/networking.k8s.io/v1beta1/"],
			"api": "ingressesclasses",
			"namespaced": False,
		},
		("NetworkPolicy", "networking.k8s.io"): {
			"api_family": ["apis/networking.k8s.io/v1/", "apis/networking.k8s.io/v1beta1/"],
			"api": "networkpolicies",
		},
		# node.k8s.io
		("RuntimeClass", "node.k8s.io"): {
			"api_family": ["apis/node.k8s.io/v1/", "apis/node.k8s.io/v1beta1/"],
			"api": "runtimeclasses",
			"namespaced": False,
		},
		# policy
		("PodDisruptionBudget", "policy"): {
			"api_family": ["apis/policy/v1/", "apis/policy/v1beta1/"],
			"api": "poddisruptionbudgets",
		},
		("PodSecurityPolicy", "policy"): {
			"api_family": ["apis/policy/v1beta1/"],
			"api": "podsecuritypolicies",
			"namespaced": False,
			"deprecated": "v1.21",
			"unavailable": "v1.25",
		},
		# rbac.authorization.k8s.io
		("ClusterRole", "rbac.authorization.k8s.io"): {
			"api_family": ["apis/rbac.authorization.k8s.io/v1/"],
			"api": "clusterroles",
			"namespaced": False,
		},
		("ClusterRoleBinding", "rbac.authorization.k8s.io"): {
			"api_family": ["apis/rbac.authorization.k8s.io/v1/"],
			"api": "clusterrolebindings",
			"namespaced": False,
		},
		("Role", "rbac.authorization.k8s.io"): {
			"api_family": ["apis/rbac.authorization.k8s.io/v1/"],
			"api": "roles",
		},
		("RoleBinding", "rbac.authorization.k8s.io"): {
			"api_family": ["apis/rbac.authorization.k8s.io/v1/"],
			"api": "rolebindings",
		},
		# scheduling.k8s.io
		("PriorityClass", "scheduling.k8s.io"): {
			"api_family": ["apis/scheduling.k8s.io/v1/"],
			"api": "priorityclasses",
			"namespaced": False,
		},
		# snapshot.storage.k8s.io
		("VolumeSnapshot", "snapshot.storage.k8s.io"): {
			"api_family": ["apis/snapshot.storage.k8s.io/v1beta1/"],
			"api": "volumesnapshots",
		},
		("VolumeSnapshotClass", "snapshot.storage.k8s.io"): {
			"api_family": ["apis/snapshot.storage.k8s.io/v1beta1/"],
			"api": "volumesnapshotclasses",
			"namespaced": False,
		},
		("VolumeSnapshotContent", "snapshot.storage.k8s.io"): {
			"api_family": ["apis/snapshot.storage.k8s.io/v1beta1/"],
			"api": "volumesnapshotcontent",
			"namespaced": False,
		},
		# storage.k8s.io
		("CSIDriver", "storage.k8s.io"): {
			"api_family": ["apis/storage.k8s.io/v1/"],
			"api": "csidrivers",
			"namespaced": False,
		},
		("CSINode", "storage.k8s.io"): {
			"api_family": ["apis/storage.k8s.io/v1/"],
			"api": "csinodes",
			"namespaced": False,
		},
		("CSIStorageCapacity", "storage.k8s.io"): {
			"api_family": ["apis/storage.k8s.io/v1beta1/"],
			"api": "csistoragecapacities",
		},
		("StorageClass", "storage.k8s.io"): {
			"api_family": ["apis/storage.k8s.io/v1/"],
			"api": "storageclasses",
			"namespaced": False,
		},
		("VolumeAttachment", "storage.k8s.io"): {
			"api_family": ["apis/storage.k8s.io/v1/"],
			"api": "volumeattachments",
			"namespaced": False,
		},

		# access.smi-spec.io
		("TrafficTarget", "access.smi-spec.io"): {
			"api_family": ["apis/access.smi-spec.io/v1alpha2/"],
			"api": "traffictargets",
		},
		# acme.cert-manager.io <= split from: cert-manager.io
		("Challenge", "acme.cert-manager.io"): {
			"api_family": ["apis/acme.cert-manager.io/v1/", "apis/acme.cert-manager.k8s.io/v1alpha2/", "certmanager.k8s.io/v1alpha1/"],
			"api": "challenges",
		},
		("Order", "acme.cert-manager.io"): {
			"api_family": ["apis/acme.cert-manager.io/v1/", "apis/acme.cert-manager.k8s.io/v1alpha2/", "certmanager.k8s.io/v1alpha1/"],
			"api": "orders",
		},
		# apps.openshift.io
		("DeploymentConfig", "apps.openshift.io"): {
			"api_family": ["apis/apps.openshift.io/v1/"],
			"api": "deploymentconfigs",
			"aliases": ["dc"],
		},
		# argoproj.io
		("ClusterWorkflowTemplate", "argoproj.io"): {
			"api_family": ["apis/argoproj.io/v1alpha1/"],
			"api": "clusterworkflowtemplates",
		},
		("CronWorkflow", "argoproj.io"): {
			"api_family": ["apis/argoproj.io/v1alpha1/"],
			"api": "cronworkflows",
		},
		("WorkflowEventBinding", "argoproj.io"): {
			"api_family": ["apis/argoproj.io/v1alpha1/"],
			"api": "workfloweventbindings",
		},
		("Workflow", "argoproj.io"): {
			"api_family": ["apis/argoproj.io/v1alpha1/"],
			"api": "workflows",
		},
		("WorkflowTemplate", "argoproj.io"): {
			"api_family": ["apis/argoproj.io/v1alpha1/"],
			"api": "workflowtemplates",
		},
		# aquasecurity.github.io
		("CISKubeBenchReport", "aquasecurity.github.io"): {
			"api_family": ["apis/aquasecurity.github.io/v1alpha1/"],
			"api": "ciskubebenchreports",
			"namespaced": False,
		},
		("ConfigAuditReport", "aquasecurity.github.io"): {
			"api_family": ["apis/aquasecurity.github.io/v1alpha1/"],
			"api": "configauditreports",
		},
		("KubeHunterReport", "aquasecurity.github.io"): {
			"api_family": ["apis/aquasecurity.github.io/v1alpha1/"],
			"api": "kubehunterreports",
			"namespaced": False,
		},
		("VulnerabilityReport", "aquasecurity.github.io"): {
			"api_family": ["apis/aquasecurity.github.io/v1alpha1/"],
			"api": "vulnerabilityreports",
		},
		# auth.kio.kasten.io
		("K10ClusterRoleBinding", "auth.kio.kasten.io"): {
			"api_family": ["apis/auth.kio.kasten.io/v1alpha1/"],
			"api": "k10clusterrolebindings",
		},
		("K10ClusterRole", "auth.kio.kasten.io"): {
			"api_family": ["apis/auth.kio.kasten.io/v1alpha1/"],
			"api": "k10clusterroles",
		},
		# authorization.openshift.io
		("RoleBindingRestriction", "authorization.openshift.io"): {
			"api_family": ["apis/authorization.openshift.io/v1/"],
			"api": "rolebindingrestrictions",
		},
		# autoscaling.openshift.io
		("ClusterAutoscaler", "autoscaling.openshift.io"): {
			"api_family": ["apis/autoscaling.openshift.io/v1/"],
			"api": "clusterautoscalers",
			"namespaced": False,
			"aliases": ["ca"],
		},
		("MachineAutoscaler", "autoscaling.openshift.io"): {
			"api_family": ["apis/autoscaling.openshift.io/v1beta1/"],
			"api": "machineautoscalers",
			"aliases": ["ma"],
		},
		# autoscaling.internal.knative.dev
		("Metric", "autoscaling.internal.knative.dev"): {
			"api_family": ["apis/autoscaling.internal.knative.dev/v1alpha1/"],
			"api": "metrics",
		},
		("PodAutoscaler", "autoscaling.internal.knative.dev"): {
			"api_family": ["apis/autoscaling.internal.knative.dev/v1alpha1/"],
			"api": "podautoscalers",
		},
		# batch.volcano.sh
		("Job", "batch.volcano.sh"): {
			"api_family": ["apis/batch.volcano.sh/v1alpha1/"],
			"api": "jobs",
		},
		# bus.volcano.sh
		("Command", "bus.volcano.sh"): {
			"api_family": ["apis/bus.volcano.sh/v1alpha1/"],
			"api": "commands",
		},
		# build.openshift.io
		("BuildConfig", "build.openshift.io"): {
			"api_family": ["apis/build.openshift.io/v1/"],
			"api": "buildconfigs",
			"aliases": ["bc"],
		},
		("Build", "build.openshift.io"): {
			"api_family": ["apis/build.openshift.io/v1/"],
			"api": "builds",
		},
		# caching.internal.knative.dev
		("Image", "caching.internal.knative.dev"): {
			"api_family": ["apis/caching.internal.knative.dev/v1alpha1/"],
			"api": "images",
		},
		# cassandra.datastax.com
		("CassandraDatacenter", "cassandra.datastax.com"): {
			"api_family": ["apis/cassandra.datastax.com/v1beta1/"],
			"api": "cassandradatacenters",
			"aliases": ["cassandradatacenter", "cassdcs", "cassdc"],
		},
		# cassandra.k8ssandra.io
		("CassandraBackup", "cassandra.k8ssandra.io"): {
			"api_family": ["apis/cassandra.k8ssandra.io/v1alpha1/"],
			"api": "cassandrabackups",
			"aliases": ["cassandrabackup"],
		},
		("CassandraRestore", "cassandra.k8ssandra.io"): {
			"api_family": ["apis/cassandra.k8ssandra.io/v1alpha1/"],
			"api": "cassandrarestores",
			"aliases": ["cassandrarestore"],
		},
		# cert-manager.io <= rename from: certmanager.k8s.io
		("Certificate", "cert-manager.io"): {
			"api_family": ["apis/cert-manager.io/v1/", "apis/cert-manager.io/v1alpha2/", "apis/certmanager.k8s.io/v1alpha1/"],
			"api": "certificates",
		},
		("CertificateRequest", "cert-manager.io"): {
			"api_family": ["apis/cert-manager.io/v1/", "apis/cert-manager.io/v1alpha2/", "apis/certmanager.k8s.io/v1alpha1/"],
			"api": "certificaterequests",
		},
		("ClusterIssuer", "cert-manager.io"): {
			"api_family": ["apis/cert-manager.io/v1/", "apis/cert-manager.io/v1alpha2/", "apis/certmanager.k8s.io/v1alpha1/"],
			"api": "clusterissuers",
			"namespaced": False,
		},
		("Issuer", "cert-manager.io"): {
			"api_family": ["apis/cert-manager.io/v1/", "apis/cert-manager.io/v1alpha2/", "apis/certmanager.k8s.io/v1alpha1/"],
			"api": "issuers",
		},
		# cilium.io
		("CiliumClusterwideNetworkPolicy", "cilium.io"): {
			"api_family": ["apis/cilium.io/v2/"],
			"api": "ciliumclusterwidenetworkpolicies",
			"aliases": ["ccnp"],
			"namespaced": False,
		},
		("CiliumEndpoint", "cilium.io"): {
			"api_family": ["apis/cilium.io/v2/"],
			"api": "ciliumendpoints",
			"aliases": ["ciliumep", "cep"],
		},
		("CiliumExternalWorkload", "cilium.io"): {
			"api_family": ["apis/cilium.io/v2/"],
			"api": "ciliumexternalworkloads",
			"aliases": ["cew"],
			"namespaced": False,
		},
		("CiliumIdentity", "cilium.io"): {
			"api_family": ["apis/cilium.io/v2/"],
			"api": "ciliumidentities",
			"aliases": ["ciliumid"],
			"namespaced": False,
		},
		("CiliumLocalRedirectPolicy", "cilium.io"): {
			"api_family": ["apis/cilium.io/v2/"],
			"api": "ciliumlocalredirectpolicies",
			"aliases": ["clrp"],
		},
		("CiliumNetworkPolicy", "cilium.io"): {
			"api_family": ["apis/cilium.io/v2/"],
			"api": "ciliumnetworkpolicies",
			"aliases": ["ciliumnp", "cnp"],
		},
		("CiliumNode", "cilium.io"): {
			"api_family": ["apis/cilium.io/v2/"],
			"api": "ciliumnodes",
			"aliases": ["ciliumn", "cn"],
			"namespaced": False,
		},
		# config.kio.kasten.io
		("Policy", "config.kio.kasten.io"): {
			"api_family": ["apis/config.kio.kasten.io/v1alpha1/"],
			"api": "policies",
		},
		("Profile", "config.kio.kasten.io"): {
			"api_family": ["apis/config.kio.kasten.io/v1alpha1/"],
			"api": "profiles",
		},
		# config.openshift.io
		("APIServer", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "apiservers",
			"namespaced": False,
		},
		("Authentication", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "authentications",
			"namespaced": False,
		},
		("Build", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "builds",
			"namespaced": False,
		},
		("ClusterOperator", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "clusteroperators",
			"namespaced": False,
		},
		("ClusterVersion", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "clusterversions",
			"namespaced": False,
		},
		("Console", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "consoles",
			"namespaced": False,
		},
		("DNS", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "dnses",
			"namespaced": False,
		},
		("FeatureGate", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "featuregates",
			"namespaced": False,
		},
		("HelmChartRepository", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1beta1/"],
			"api": "helmchartrepositories",
			"namespaced": False,
		},
		("Image", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "images",
			"namespaced": False,
		},
		("Infrastructure", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "infrastructures",
			"namespaced": False,
		},
		("Ingress", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "ingresses",
			"namespaced": False,
		},
		("Network", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "networks",
			"namespaced": False,
		},
		("OAuth", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "oauths",
			"namespaced": False,
		},
		("OperatorHub", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "operatorhub",
			"namespaced": False,
		},
		("Project", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "projects",
			"namespaced": False,
		},
		("Proxy", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "proxies",
			"namespaced": False,
		},
		("Scheduler", "config.openshift.io"): {
			"api_family": ["apis/config.openshift.io/v1/"],
			"api": "schedulers",
			"namespaced": False,
		},
		# controlplane.antrea.io
		("AddressGroup", "controlplane.antrea.io"): {
			"api_family": ["apis/controlplane.antrea.io/v1beta2/"],
			"api": "addressgroups",
			"aliases": ["addressgroup"],
			"namespaced": False,
		},
		("AppliedToGroup", "controlplane.antrea.io"): {
			"api_family": ["apis/controlplane.antrea.io/v1beta2/"],
			"api": "appliedtogroups",
			"aliases": ["appliedtogroup"],
			"namespaced": False,
		},
		("EgressGroup", "controlplane.antrea.io"): {
			"api_family": ["apis/controlplane.antrea.io/v1beta2/"],
			"api": "egressgroups",
			"aliases": ["egressgroup"],
			"namespaced": False,
		},
		("NetworkPolicy", "controlplane.antrea.io"): {
			"api_family": ["apis/controlplane.antrea.io/v1beta2/"],
			"api": "networkpolicies",
			"aliases": ["networkpolicy"],
			"namespaced": False,
		},
		# cr.kanister.io
		("ActionSet", "cr.kanister.io"): {
			"api_family": ["apis/cr.kanister.io/v1alpha1/"],
			"api": "actionsets",
		},
		("Blueprint", "cr.kanister.io"): {
			"api_family": ["apis/cr.kanister.io/v1alpha1/"],
			"api": "blueprints",
		},
		("Profile", "cr.kanister.io"): {
			"api_family": ["apis/cr.kanister.io/v1alpha1/"],
			"api": "profiles",
		},
		# crd.antrea.io
		("AntreaAgentInfo", "crd.antrea.io"): {
			"api_family": ["apis/crd.antrea.io/v1beta1/"],
			"api": "antreaagentinfos",
			"aliases": ["antreaagentinfo", "aai"],
			"namespaced": False,
		},
		("AntreaControllerInfo", "crd.antrea.io"): {
			"api_family": ["apis/crd.antrea.io/v1beta1/"],
			"api": "antreacontrollerinfos",
			"aliases": ["antreacontrollerinfo", "aci"],
			"namespaced": False,
		},
		("ClusterGroup", "crd.antrea.io"): {
			"api_family": ["apis/crd.antrea.io/v1alpha3/", "apis/crd.antrea.io/v1alpha2/"],
			"api": "clustergroups",
			"aliases": ["clustergroup", "cg"],
			"namespaced": False,
		},
		("ClusterNetworkPolicy", "crd.antrea.io"): {
			"api_family": ["apis/crd.antrea.io/v1alpha1/"],
			"api": "clusternetworkpolicies",
			"aliases": ["clusternetpolicy"],
			"namespaced": False,
		},
		("Egress", "crd.antrea.io"): {
			"api_family": ["apis/crd.antrea.io/v1alpha2/"],
			"api": "egresses",
			"aliases": ["egress", "eg"],
			"namespaced": False,
		},
		("ExternalEntity", "crd.antrea.io"): {
			"api_family": ["apis/crd.antrea.io/v1alpha2/"],
			"api": "externalentities",
			"aliases": ["externalentity", "ee"],
		},
		("ExternalIPPool", "crd.antrea.io"): {
			"api_family": ["apis/crd.antrea.io/v1alpha2/"],
			"api": "externalippools",
			"aliases": ["externalippool", "eip"],
			"namespaced": False,
		},
		("IPPool", "crd.antrea.io"): {
			"api_family": ["apis/crd.antrea.io/v1alpha2/"],
			"api": "ippools",
			"aliases": ["ippool", "ipp"],
			"namespaced": False,
		},
		("NetworkPolicy", "crd.antrea.io"): {
			"api_family": ["apis/crd.antrea.io/v1alpha1/"],
			"api": "networkpolicies",
			"aliases": ["networkpolicy", "anp"],
		},
		("Tier", "crd.antrea.io"): {
			"api_family": ["apis/crd.antrea.io/v1alpha1/"],
			"api": "tiers",
			"aliases": ["tier", "tr"],
			"namespaced": False,
		},
		("TraceFlow", "crd.antrea.io"): {
			"api_family": ["apis/crd.antrea.io/v1alpha1/"],
			"api": "traceflows",
			"aliases": ["traceflow", "tf"],
			"namespaced": False,
		},
		# crd.projectcalico.org
		("BGPConfiguration", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "bgpconfigurations",
			"namespaced": False,
		},
		("BGPPeer", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "bgppeers",
			"namespaced": False,
		},
		("BlockAffinity", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "blockaffinities",
			"namespaced": False,
		},
		("CalicoNodeStatus", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "caliconodestatuses",
			"namespaced": False,
		},
		("ClusterInformation", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "clusterinformations",
			"namespaced": False,
		},
		("FelixConfiguration", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "felixconfigurations",
			"namespaced": False,
		},
		("GlobalNetworkPolicy", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "globalnetworkpolicies",
			"namespaced": False,
		},
		("GlobalNetworkSet", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "globalnetworksets",
			"namespaced": False,
		},
		("HostEndpoint", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "hostendpoints",
			"namespaced": False,
		},
		("IPAMBlock", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "ipamblocks",
			"namespaced": False,
		},
		("IPAMConfig", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "ipamconfigs",
			"namespaced": False,
		},
		("IPAMHandle", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "ipamhandles",
			"namespaced": False,
		},
		("IPPool", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "ippools",
			"namespaced": False,
		},
		("IPReservation", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "ipreservations",
			"namespaced": False,
		},
		("KubeControllersConfiguration", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "kubecontrollersconfigurations",
			"namespaced": False,
		},
		("NetworkPolicy", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "networkpolicies",
		},
		("NetworkSet", "crd.projectcalico.org"): {
			"api_family": ["apis/crd.projectcalico.org/v1/"],
			"api": "networksets",
		},
		# deviceplugin.intel.com
		("DsaDevicePlugin", "deviceplugin.intel.com"): {
			"api_family": ["apis/deviceplugin.intel.com/v1/"],
			"api": "dsadeviceplugins",
			"namespaced": False,
		},
		("FpgaDevicePlugin", "deviceplugin.intel.com"): {
			"api_family": ["apis/deviceplugin.intel.com/v1/"],
			"api": "fpgadeviceplugins",
			"namespaced": False,
		},
		("GpuDevicePlugin", "deviceplugin.intel.com"): {
			"api_family": ["apis/deviceplugin.intel.com/v1/"],
			"api": "gpudeviceplugins",
			"namespaced": False,
		},
		("QatDevicePlugin", "deviceplugin.intel.com"): {
			"api_family": ["apis/deviceplugin.intel.com/v1/"],
			"api": "qatdeviceplugins",
			"namespaced": False,
		},
		("SgxDevicePlugin", "deviceplugin.intel.com"): {
			"api_family": ["apis/deviceplugin.intel.com/v1/"],
			"api": "sgxdeviceplugins",
			"namespaced": False,
		},
		# dex.coreos.com
		("AuthCode", "dex.coreos.com"): {
			"api_family": ["apis/dex.coreos.com/v1/"],
			"api": "authcodes",
		},
		("AuthRequest", "dex.coreos.com"): {
			"api_family": ["apis/dex.coreos.com/v1/"],
			"api": "authrequests",
		},
		("Connector", "dex.coreos.com"): {
			"api_family": ["apis/dex.coreos.com/v1/"],
			"api": "connectors",
		},
		("OAuth2Client", "dex.coreos.com"): {
			"api_family": ["apis/dex.coreos.com/v1/"],
			"api": "oauth2clients",
		},
		("OfflineSessions", "dex.coreos.com"): {
			"api_family": ["apis/dex.coreos.com/v1/"],
			"api": "offlinesessionses",
		},
		("Password", "dex.coreos.com"): {
			"api_family": ["apis/dex.coreos.com/v1/"],
			"api": "passwords",
		},
		("RefreshToken", "dex.coreos.com"): {
			"api_family": ["apis/dex.coreos.com/v1/"],
			"api": "refreshtokens",
		},
		("SigningKey", "dex.coreos.com"): {
			"api_family": ["apis/dex.coreos.com/v1/"],
			"api": "signingkeies",
		},
		# dist.kio.kasten.io
		("Bootstrap", "dist.kio.kasten.io"): {
			"api_family": ["apis/dist.kio.kasten.io/v1alpha1/"],
			"api": "bootstraps",
		},
		("Cluster", "dist.kio.kasten.io"): {
			"api_family": ["apis/dist.kio.kasten.io/v1alpha1/"],
			"api": "clusters",
		},
		("Distribution", "dist.kio.kasten.io"): {
			"api_family": ["apis/dist.kio.kasten.io/v1alpha1/"],
			"api": "distributions",
		},
		# etcd.database.coreos.com
		("EtcdCluster", "etcd.database.coreos.com"): {
			"api_family": ["apis/etcd.database.coreos.com/v1beta2/"],
			"api": "etcdclusters",
		},
		# eventing.knative.dev
		("Broker", "eventing.knative.dev"): {
			"api_family": ["apis/eventing.knative.dev/v1/", "apis/eventing.knative.dev/v1beta1/"],
			"api": "brokers",
		},
		("EventType", "eventing.knative.dev"): {
			"api_family": ["apis/eventing.knative.dev/v1/", "apis/eventing.knative.dev/v1beta1/"],
			"api": "eventtypes",
		},
		("Trigger", "eventing.knative.dev"): {
			"api_family": ["apis/eventing.knative.dev/v1/", "apis/eventing.knative.dev/v1beta1/"],
			"api": "triggers",
		},
		# flows.knative.dev
		("Parallel", "flow.knative.dev"): {
			"api_family": ["apis/flows.knative.dev/v1/"],
			"api": "parallels",
		},
		("Sequence", "flow.knative.dev"): {
			"api_family": ["apis/flows.knative.dev/v1/"],
			"api": "sequences",
		},
		# fpga.intel.com
		("AcceleratorFunction", "fpga.intel.com"): {
			"api_family": ["apis/fpga.intel.com/v2/"],
			"api": "acceleratorfunctions",
			"aliases": ["af"],
		},
		("FpgaRegion", "fpga.intel.com"): {
			"api_family": ["apis/fpga.intel.com/v2/"],
			"api": "fpgaregions",
			"aliases": ["fpga"],
		},
		# helm.cattle.io
		("HelmChartConfig", "helm.cattle.io"): {
			"api_family": ["apis/helm.cattle.io/v1/"],
			"api": "helmchartconfigs",
		},
		("HelmChart", "helm.cattle.io"): {
			"api_family": ["apis/helm.cattle.io/v1/"],
			"api": "helmcharts",
		},
		# image.openshift.io
		("Image", "image.openshift.io"): {
			"api_family": ["apis/image.openshift.io/v1/"],
			"api": "images",
			"namespaced": False,
		},
		("ImageStream", "image.openshift.io"): {
			"api_family": ["apis/image.openshift.io/v1/"],
			"api": "imagestreams",
			"aliases": ["is"],
		},
		("ImageStreamTag", "image.openshift.io"): {
			"api_family": ["apis/image.openshift.io/v1/"],
			"api": "imagestreamtags",
			"aliases": ["istag"],
		},
		# install.istio.io
		("IstioOperator", "install.istio.io"): {
			"api_family": ["apis/install.istio.io/v1alpha1/"],
			"api": "istiooperators",
			"aliases": ["iop", "io"],
		},
		# integreatly.org
		("Grafana", "integreatly.org"): {
			"api_family": ["apis/integreatly.org/v1alpha1/"],
			"api": "grafanas",
		},
		("GrafanaDashboard", "integreatly.org"): {
			"api_family": ["apis/integreatly.org/v1alpha1/"],
			"api": "grafanadashboards",
		},
		("GrafanaDataSource", "integreatly.org"): {
			"api_family": ["apis/integreatly.org/v1alpha1/"],
			"api": "grafanadatasources",
		},
		# jaegertracing.io
		("Jaeger", "jaegertracing.io"): {
			"api_family": ["apis/jaegertracing.io/v1/"],
			"api": "jaegers",
		},
		# k3s.cattle.io
		("Addon", "k3s.cattle.io"): {
			"api_family": ["apis/k3s.cattle.io/v1/"],
			"api": "addons",
		},
		# keda.sh
		("ClusterTriggerAuthentication", "keda.sh"): {
			"api_family": ["apis/keda.sh/v1alpha1/"],
			"api": "clustertriggerauthentications",
			"aliases": ["cta", "clustertriggerauth"],
		},
		("ScaledJob", "keda.sh"): {
			"api_family": ["apis/keda.sh/v1alpha1/"],
			"api": "scaledjobs",
			"aliases": ["sj"],
		},
		("ScaledObject", "keda.sh"): {
			"api_family": ["apis/keda.sh/v1alpha1/"],
			"api": "scaledobjects",
			"aliases": ["so"],
		},
		("TriggerAuthentication", "keda.sh"): {
			"api_family": ["apis/keda.sh/v1alpha1/"],
			"api": "triggerauthentications",
			"aliases": ["ta", "triggerauth"],
		},
		# kilo.squat.ai
		("Peer", "kilo.squat.ai"): {
			"api_family": ["apis/kilo.squat.ai/v1alpha1/"],
			"api": "peers",
			"namespaced": False,
		},
		# kubeapps.com
		("AppRepository", "kubeapps.com"): {
			"api_family": ["apis/kubeapps.com/v1alpha1/"],
			"api": "apprepositories",
			"aliases": ["apprepos"],
		},
		# kubeflow.org
		("Experiment", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1beta1/"],
			"api": "experiments",
		},
		("MPIJob", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1alpha2/", "apis/kubeflow.org/v1/"],
			"api": "mpijobs",
		},
		("MXJob", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1/"],
			"api": "mxjobs",
		},
		("Notebook", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1/"],
			"api": "notebooks",
		},
		("PodDefault", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1alpha1/"],
			"api": "poddefaults",
		},
		("Profile", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1beta1/", "apis/kubeflow.org/v1/"],
			"api": "profiles",
			"namespaced": False,
		},
		("PyTorchJob", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1/"],
			"api": "pytorchjobs",
		},
		("ScheduledWorkflow", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1beta1/"],
			"api": "scheduledworkflow",
		},
		("Suggestion", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1alpha3/", "apis/kubeflow.org/v1beta1/"],
			"api": "suggestions",
		},
		("TFJob", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1/"],
			"api": "tfjobs",
		},
		("Trial", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1alpha3/", "apis/kubeflow.org/v1beta1/"],
			"api": "trials",
		},
		("Viewer", "kubeflow.org"): {
			"api_family": ["apis/kubeflow.org/v1alpha1/", "apis/kubeflow.org/v1beta1/"],
			"api": "viewers",
		},
		# kubevirt.io
		("KubeVirt", "kubevirt.io"): {
			"api_family": ["apis/kubevirt.io/v1/"],
			"api": "kubevirts",
			"aliases": ["kvs", "kv"],
		},
		("VirtualMachineInstanceMigration", "kubevirt.io"): {
			"api_family": ["apis/kubevirt.io/v1alpha3/"],
			"api": "virtualmachineinstancemigrations",
		},
		("VirtualMachineInstancePreset", "kubevirt.io"): {
			"api_family": ["apis/kubevirt.io/v1alpha3/"],
			"api": "virtualmachineinstancepresets",
		},
		("VirtualMachineInstanceReplicaSet", "kubevirt.io"): {
			"api_family": ["apis/kubevirt.io/v1alpha3/"],
			"api": "virtualmachineinstancereplicasets",
		},
		("VirtualMachineInstance", "kubevirt.io"): {
			"api_family": ["apis/kubevirt.io/v1alpha3/"],
			"api": "virtualmachineinstances",
		},
		("VirtualMachine", "kubevirt.io"): {
			"api_family": ["apis/kubevirt.io/v1alpha3/"],
			"api": "virtualmachines",
		},
		# linkerd.io
		("ServiceProfile", "linkerd.io"): {
			"api_family": ["apis/linkerd.io/v1alpha2/"],
			"api": "serviceprofiles",
		},
		# machinelearning.seldon.io
		("SeldonDeployment", "machinelearning.seldon.io"): {
			"api_family": ["apis/machinelearning.seldon.io/v1/", "apis/machinelearning.seldon.io/v1alpha3/", "apis/machinelearning.seldon.io/v1alpha2/"],
			"api": "seldondeployments",
		},
		# messaging.knative.dev
		("Channel", "messaging.knative.dev"): {
			"api_family": ["apis/messaging.knative.dev/v1/"],
			"api": "channels",
		},
		("InMemoryChannel", "messaging.knative.dev"): {
			"api_family": ["apis/messaging.knative.dev/v1/"],
			"api": "inmemorychannels",
		},
		("Subscription", "messaging.knative.dev"): {
			"api_family": ["apis/messaging.knative.dev/v1/"],
			"api": "subscriptions",
		},
		# metrics.k8s.io
		("NodeMetrics", "metrics.k8s.io"): {
			"api_family": ["apis/metrics.k8s.io/v1beta1/"],
			"api": "nodes",
			"namespaced": False,
		},
		("PodMetrics", "metrics.k8s.io"): {
			"api_family": ["apis/metrics.k8s.io/v1beta1/"],
			"api": "pods",
		},
		# monitoring.coreos.com
		("Alertmanager", "monitoring.coreos.com"): {
			"api_family": ["apis/monitoring.coreos.com/v1/"],
			"api": "alertmanagers",
		},
		("PodMonitor", "monitoring.coreos.com"): {
			"api_family": ["apis/monitoring.coreos.com/v1/"],
			"api": "podmonitors",
		},
		("Probe", "monitoring.coreos.com"): {
			"api_family": ["apis/monitoring.coreos.com/v1/"],
			"api": "probes",
		},
		("Prometheus", "monitoring.coreos.com"): {
			"api_family": ["apis/monitoring.coreos.com/v1/"],
			"api": "prometheuses",
		},
		("PrometheusRule", "monitoring.coreos.com"): {
			"api_family": ["apis/monitoring.coreos.com/v1/"],
			"api": "prometheusrules",
		},
		("ServiceMonitor", "monitoring.coreos.com"): {
			"api_family": ["apis/monitoring.coreos.com/v1/"],
			"api": "servicemonitors",
		},
		("ThanosRuler", "monitoring.coreos.com"): {
			"api_family": ["apis/monitoring.coreos.com/v1/"],
			"api": "thanosrulers",
		},
		# network.openshift.io
		("ClusterNetwork", "network.openshift.io"): {
			"api_family": ["apis/network.openshift.io/v1/"],
			"api": "clusternetworks",
			"aliases": ["clusternets"],
			"namespaced": False,
		},
		("EgressNetworkPolicy", "network.openshift.io"): {
			"api_family": ["apis/network.openshift.io/v1/"],
			"api": "egressnetworkpolicies",
			"aliases": ["egressnetpols", "egressnetpol"],
		},
		("HostSubnet", "network.openshift.io"): {
			"api_family": ["apis/network.openshift.io/v1/"],
			"api": "hostsubnets",
			"namespaced": False,
		},
		("NetNamespace", "network.openshift.io"): {
			"api_family": ["apis/network.openshift.io/v1/"],
			"api": "netnamespaces",
			"namespaced": False,
		},
		# networking.antrea.tanzu.vmware.com
		("AddressGroup", "networking.antrea.tanzu.vmware.com"): {
			"api_family": ["apis/networking.antrea.tanzu.vmware.com/v1beta1/"],
			"api": "addressgroups",
			"aliases": ["addressgroup"],
			"namespaced": False,
		},
		("AppliedToGroup", "networking.antrea.tanzu.vmware.com"): {
			"api_family": ["apis/networking.antrea.tanzu.vmware.com/v1beta1/"],
			"api": "appliedtogroups",
			"aliases": ["appliedtogroup"],
			"namespaced": False,
		},
		("NetworkPolicy", "networking.antrea.tanzu.vmware.com"): {
			"api_family": ["apis/networking.antrea.tanzu.vmware.com/v1beta1/"],
			"api": "networkpolicies",
			"aliases": ["networkpolicy", "netpols", "netpol"],
			"namespaced": False,
		},
		# networking.internal.knative.dev
		("Certificate", "networking.internal.knative.dev"): {
			"api_family": ["apis/networking.internal.knative.dev/v1alpha1/"],
			"api": "certificates",
		},
		("Ingress", "networking.internal.knative.dev"): {
			"api_family": ["apis/networking.internal.knative.dev/v1alpha1/"],
			"api": "certificates",
		},
		("ServerlessService", "networking.internal.knative.dev"): {
			"api_family": ["apis/networking.internal.knative.dev/v1alpha1/"],
			"api": "serverlessservices",
		},
		# networking.istio.io
		("DestinationRule", "networking.istio.io"): {
			"api_family": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
			"api": "destinationrules",
			"aliases": ["dr"],
		},
		("EnvoyFilter", "networking.istio.io"): {
			"api_family": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
			"api": "envoyfilters",
		},
		("Gateway", "networking.istio.io"): {
			"api_family": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
			"api": "gateways",
			"aliases": ["gw"],
		},
		("ServiceEntry", "networking.istio.io"): {
			"api_family": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
			"api": "serviceentries",
			"aliases": ["se"],
		},
		("Sidecar", "networking.istio.io"): {
			"api_family": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
			"api": "sidecars",
		},
		("VirtualService", "networking.istio.io"): {
			"api_family": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
			"api": "virtualservices",
			"aliases": ["vs"],
		},
		("WorkloadEntry", "networking.istio.io"): {
			"api_family": ["apis/networking.istio.io/v1beta1/"],
			"api": "workloadentries",
			"aliases": ["we"],
		},
		("WorkloadGroup", "networking.istio.io"): {
			"api_family": ["apis/networking.istio.io/v1alpha3/"],
			"api": "workloadgroups",
			"aliases": ["wg"],
		},
		# nodeinfo.volcano.sh
		("Numatopology", "nodeinfo.volcano.sh"): {
			"api_family": ["apis/nodeinfo.volcano.sh/v1alpha1/"],
			"api": "numatopologies",
		},
		# nvidia.com
		("ClusterPolicy", "nvidia.com"): {
			"api_family": ["apis/nvidia.com/v1/"],
			"api": "clusterpolicies",
			"namespaced": False,
		},
		# oauth.openshift.io
		("OAuthAccessToken", "oauth.openshift.io"): {
			"api_family": ["apis/oauth.openshift.io/v1/"],
			"api": "oauthaccesstokens",
			"namespaced": False,
		},
		("OAuthAuthorizeToken", "oauth.openshift.io"): {
			"api_family": ["apis/oauth.openshift.io/v1/"],
			"api": "oauthauthorizetokens",
			"namespaced": False,
		},
		("OAuthClientAuthorization", "oauth.openshift.io"): {
			"api_family": ["apis/oauth.openshift.io/v1/"],
			"api": "oauthclientauthorizations",
			"namespaced": False,
		},
		("OAuthClient", "oauth.openshift.io"): {
			"api_family": ["apis/oauth.openshift.io/v1/"],
			"api": "oauthclients",
			"namespaced": False,
		},
		# opentelemetry.io
		("OpenTelemetryCollector", "opentelemetry.io"): {
			"api_family": ["apis/opentelemetry.io/v1alpha1/"],
			"api": "opentelemetrycollectors",
		},
		# operators.coreos.com
		("CatalogSource", "operators.coreos.com"): {
			"api_family": ["apis/operators.coreos.com/v1alpha1/"],
			"api": "catalogsources",
			"aliases": ["catalogsource", "catsrcs", "catsrc"],
		},
		("ClusterServiceVersion", "operators.coreos.com"): {
			"api_family": ["apis/operators.coreos.com/v1alpha1/"],
			"api": "clusterserviceversions",
			"aliases": ["clusterserviceversion", "csvs", "csv"],
		},
		("InstallPlan", "operators.coreos.com"): {
			"api_family": ["apis/operators.coreos.com/v1alpha1/"],
			"api": "installplans",
			"aliases": ["installplan", "ip"],
		},
		("OperatorGroup", "operators.coreos.com"): {
			"api_family": ["apis/operators.coreos.com/v1/"],
			"api": "operatorgroups",
			"aliases": ["operatorgroup", "og"],
		},
		("Operator", "operators.coreos.com"): {
			"api_family": ["apis/operators.coreos.com/v1/"],
			"api": "operators",
			"aliases": ["operator"],
			"namespaced": False,
		},
		("Subscription", "operators.coreos.com"): {
			"api_family": ["apis/operators.coreos.com/v1alpha1/"],
			"api": "subscriptions",
			"aliases": ["subscription", "subs", "sub"],
		},
		# ops.antrea.tanzu.vmware.com
		("Traceflow", "ops.antrea.tanzu.vmware.com"): {
			"api_family": ["apis/ops.antrea.tanzu.vmware.com/v1alpha1/"],
			"api": "traceflows",
			"aliases": ["traceflow", "tf"],
			"namespaced": False,
		},
		# packages.operators.coreos.com
		("PackageManifest", "packages.operators.coreos.com"): {
			"api_family": ["apis/packages.operators.coreos.com/v1/"],
			"api": "packagemanifests",
			"aliases": ["pkgmanifests"],
		},
		# policy.linkerd.io
		("ServerAuthorization", "policy.linkerd.io"): {
			"api_family": ["apis/policy.linkerd.io/v1beta1/"],
			"api": "serverauthorizations",
			"aliases": ["saz"],
		},
		("Server", "policy.linkerd.io"): {
			"api_family": ["apis/policy.linkerd.io/v1beta1/"],
			"api": "servers",
			"aliases": ["srv"],
		},
		# project.openshift.io
		("ProjectRequest", "project.openshift.io"): {
			"api_family": ["apis/project.openshift.io/v1/"],
			"api": "projectrequests",
			"aliases": ["projectreqs"],
			"namespaced": False,
		},
		("Project", "project.openshift.io"): {
			"api_family": ["apis/project.openshift.io/v1/"],
			"api": "projects",
			"namespaced": False,
		},
		# quota.openshift.io
		("AppliedClusterResourceQuota", "quota.openshift.io"): {
			"api_family": ["apis/quota.openshift.io/v1/"],
			"api": "appliedclusterresourcequota",
			"aliases": ["projectreqs"],
		},
		("ClusterResourceQuota", "quota.openshift.io"): {
			"api_family": ["apis/quota.openshift.io/v1/"],
			"api": "clusterresourcequota",
			"aliases": ["clusterquota"],
			"namespaced": False,
		},
		# reaper.cassandra-reaper.io
		("Reaper", "reaper.cassandra-reaper.io"): {
			"api_family": ["apis/reaper.cassandra-reaper.io/v1alpha1/"],
			"api": "reapers",
			"aliases": ["reaper"],
		},
		# reporting.kio.kasten.io
		("Report", "reporting.kio.kasten.io"): {
			"api_family": ["apis/reporting.kio.kasten.io/v1alpha1/"],
			"api": "reports",
		},
		# route.openshift.io
		("Route", "route.openshift.io"): {
			"api_family": ["apis/route.openshift.io/v1/"],
			"api": "routes",
		},
		# security.istio.io
		("AuthorizationPolicy", "security.istio.io"): {
			"api_family": ["apis/security.istio.io/v1beta1/"],
			"api": "authorizationpolicies",
		},
		("PeerAuthentication", "security.istio.io"): {
			"api_family": ["apis/security.istio.io/v1beta1/"],
			"api": "peerauthentications",
			"aliases": ["pa"],
		},
		("RequestAuthentication", "security.istio.io"): {
			"api_family": ["apis/security.istio.io/v1beta1/"],
			"api": "requestauthentications",
			"aliases": ["ra"],
		},
		# security.openshift.io
		("RangeAllocation", "security.openshift.io"): {
			"api_family": ["apis/security.openshift.io/v1/"],
			"api": "rangeallocations",
			"aliases": ["scc"],
			"namespaced": False,
		},
		("SecurityContextConstraint", "security.openshift.io"): {
			"api_family": ["apis/security.openshift.io/v1/"],
			"api": "securitycontextconstraints",
			"aliases": ["scc"],
			"namespaced": False,
		},
		# servicecertsigner.config.openshift.io
		("ServiceCertSignerOperatorConfig", "servicecertsigner.config.openshift.io"): {
			"api_family": ["apis/servicecertsigner.config.openshift.io/v1alpha1/"],
			"api": "servicecertsigneroperatorconfigs",
			"namespaced": False,
		},
		# serving.knative.dev
		("Configuration", "serving.knative.dev"): {
			"api_family": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/", "apis/serving.knative.dev/v1alpha2/", "apis/serving.knative.dev/v1alpha1/"],
			"api": "configations",
		},
		("Revision", "serving.knative.dev"): {
			"api_family": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/", "apis/serving.knative.dev/v1alpha2/", "apis/serving.knative.dev/v1alpha1/"],
			"api": "revisions",
		},
		("Route", "serving.knative.dev"): {
			"api_family": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/", "apis/serving.knative.dev/v1alpha2/", "apis/serving.knative.dev/v1alpha1/"],
			"api": "routes",
		},
		("Service", "serving.knative.dev"): {
			"api_family": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/", "apis/serving.knative.dev/v1alpha2/", "apis/serving.knative.dev/v1alpha1/"],
			"api": "services",
		},
		# serving.kubeflow.org
		("InferenceService", "serving.kubeflow.org"): {
			"api_family": ["apis/serving.kubeflow.org/v1alpha2/", "apis/serving.kubeflow.org/v1beta1/"],
			"api": "inferenceservices",
		},
		("TrainedModel", "serving.kubeflow.org"): {
			"api_family": ["apis/serving.kubeflow.org/v1alpha2/"],
			"api": "trainedmodels",
		},
		# snapshot.kubevirt.io
		("VirtualMachineRestore", "snapshot.kubevirt.io"): {
			"api_family": ["apis/snapshot.kubevirt.io/v1alpha1/"],
			"api": "virtualmachinerestores",
		},
		("VirtualMachineSnapshotContent", "snapshot.kubevirt.io"): {
			"api_family": ["apis/snapshot.kubevirt.io/v1alpha1/"],
			"api": "virtualmachinesnapshotcontents",
		},
		("VirtualMachineSnapshot", "snapshot.kubevirt.io"): {
			"api_family": ["apis/snapshot.kubevirt.io/v1alpha1/"],
			"api": "virtualmachinesnapshots",
		},
		# sources.knative.dev
		("ApiServerSource", "sources.knative.dev"): {
			"api_family": ["apis/sources.knative.dev/v1beta1/"],
			"api": "apiserversources",
		},
		("ContainerSource", "sources.knative.dev"): {
			"api_family": ["apis/sources.knative.dev/v1beta1/"],
			"api": "containersources",
		},
		("PingSource", "sources.knative.dev"): {
			"api_family": ["apis/sources.knative.dev/v1beta1/"],
			"api": "pingsources",
		},
		("SinkBinding", "sources.knative.dev"): {
			"api_family": ["apis/sources.knative.dev/v1beta1/"],
			"api": "sinkbindings",
		},
		# specs.smi-spec.io
		("HTTPRouteGroup", "specs.smi-spec.io"): {
			"api_family": ["apis/specs.smi-spec.io/v1alpha4/", "apis/specs.smi-spec.io/v1alpha3/", "apis/specs.smi-spec.io/v1alpha3/"],
			"api": "httproutegroups",
		},
		("TCPRoute", "specs.smi-spec.io"): {
			"api_family": ["apis/specs.smi-spec.io/v1alpha4/", "apis/specs.smi-spec.io/v1alpha3/"],
			"api": "tcproutes",
		},
		("UDPRoute", "specs.smi-spec.io"): {
			"api_family": ["apis/specs.smi-spec.io/v1alpha4/"],
			"api": "tcproutes",
		},
		# split.smi-spec.io
		("TrafficSplit", "split.smi-spec.io"): {
			"api_family": ["apis/split.smi-spec.io/v1alpha4/", "apis/split.smi-spec.io/v1alpha3/", "apis/split.smi-spec.io/v1alpha2/", "apis/split.smi-spec.io/v1alpha1/"],
			"api": "trafficsplits",
		},
		# stats.antrea.io
		("AntreaClusterNetworkPolicyStats", "stats.antrea.io"): {
			"api_family": ["apis/stats.antrea.io/v1alpha1/"],
			"api": "antreaclusternetworkpolicystats",
			"aliases": ["antreaclusternetpolstats"],
			"namespaced": False,
		},
		("AntreaNetworkPolicyStats", "stats.antrea.io"): {
			"api_family": ["apis/stats.antrea.io/v1alpha1/"],
			"api": "antreanetworkpolicystats",
			"aliases": ["antreanetpolstats"],
		},
		("NetworkPolicyStats", "stats.antrea.io"): {
			"api_family": ["apis/stats.antrea.io/v1alpha1/"],
			"api": "networkpolicystats",
			"aliases": ["netpolstats"],
		},
		# system.antrea.io
		("ControllerInfo", "system.antrea.io"): {
			"api_family": ["apis/system.antrea.io/v1beta1/"],
			"api": "controllerinfos",
			"aliases": ["controllerinfo"],
			"namespaced": False,
		},
		# telemetry.intel.com
		("TASPolicy", "telemetry.intel.com"): {
			"api_family": ["apis/telemetry.intel.com/v1alpha1/"],
			"api": "taspolicies",
		},
		# telemetry.istio.io
		("Telemetry", "telemetry.intel.com"): {
			"api_family": ["apis/telemetry.istio.io/v1alpha1/"],
			"api": "telemetries",
			"aliases": ["telemetry"],
		},
		# template.openshift.io
		("BrokerTemplateInstance", "servicecertsigner.config.openshift.io"): {
			"api_family": ["apis/template.openshift.io/v1/"],
			"api": "brokertemplateinstances",
			"namespaced": False,
		},
		("TemplateInstance", "servicecertsigner.config.openshift.io"): {
			"api_family": ["apis/template.openshift.io/v1/"],
			"api": "templateinstances",
		},
		("Template", "servicecertsigner.config.openshift.io"): {
			"api_family": ["apis/template.openshift.io/v1/"],
			"api": "templates",
		},
		# tensorboard.kubeflow.org
		("Tensorboard", "tensorboard.kubeflow.org"): {
			"api_family": ["apis/tensorboard.kubeflow.org/v1alpha1/"],
			"api": "tensorboards",
		},
		# traefik.containo.us
		("IngressRoute", "traefik.containo.us"): {
			"api_family": ["apis/traefik.containo.us/v1alpha1/"],
			"api": "ingressroutes",
		},
		("IngressRouteTCP", "traefik.containo.us"): {
			"api_family": ["apis/traefik.containo.us/v1alpha1/"],
			"api": "ingressroutetcps",
		},
		("IngressRouteUDP", "traefik.containo.us"): {
			"api_family": ["apis/traefik.containo.us/v1alpha1/"],
			"api": "ingressrouteudps",
		},
		("Middleware", "traefik.containo.us"): {
			"api_family": ["apis/traefik.containo.us/v1alpha1/"],
			"api": "middlewares",
		},
		("MiddlewareTCP", "traefik.containo.us"): {
			"api_family": ["apis/traefik.containo.us/v1alpha1/"],
			"api": "middlewaretcps",
		},
		("ServersTransport", "traefik.containo.us"): {
			"api_family": ["apis/traefik.containo.us/v1alpha1/"],
			"api": "serverstransports",
		},
		("TLSOption", "traefik.containo.us"): {
			"api_family": ["apis/traefik.containo.us/v1alpha1/"],
			"api": "tlsoptions",
		},
		("TLSStore", "traefik.containo.us"): {
			"api_family": ["apis/traefik.containo.us/v1alpha1/"],
			"api": "tlsstores",
		},
		("TraefikService", "traefik.containo.us"): {
			"api_family": ["apis/traefik.containo.us/v1alpha1/"],
			"api": "traefikservices",
		},
		# tuned.openshift.io
		("Profile", "tuned.openshift.io"): {
			"api_family": ["apis/tuned.openshift.io/v1/"],
			"api": "profiles",
		},
		("Tuned", "tuned.openshift.io"): {
			"api_family": ["apis/tuned.openshift.io/v1/"],
			"api": "tuneds",
		},
		# user.openshift.io
		("Group", "user.openshift.io"): {
			"api_family": ["apis/user.openshift.io/v1/"],
			"api": "groups",
			"namespaced": False,
		},
		("Identity", "user.openshift.io"): {
			"api_family": ["apis/user.openshift.io/v1/"],
			"api": "identities",
			"namespaced": False,
		},
		("User", "user.openshift.io"): {
			"api_family": ["apis/user.openshift.io/v1/"],
			"api": "users",
			"namespaced": False,
		},
		#("UserIdentityMapping", "user.openshift.io"): {
		#	"api_family": ["apis/user.openshift.io/v1/"],
		#	"api": "useridentitymappings",
		#	"namespaced": False,
		#},
		# scheduling.volcano.sh
		("PodGroup", "scheduling.volcano.sh"): {
			"api_family": ["apis/scheduling.volcano.sh/v1beta1/"],
			"api": "podgroups",
		},
		("Queue", "scheduling.volcano.sh"): {
			"api_family": ["apis/scheduling.volcano.sh/v1beta1/"],
			"api": "queues",
			"namespaced": False,
		},
		# webconsole.openshift.io
		("OpenShiftWebConsoleConfig", "webconsole.openshift.io"): {
			"api_family": ["apis/webconsole.openshift.io/v1/"],
			"api": "openshiftwebconsoleconfigs",
			"namespaced": False,
		},
		# xgboostjob.kubeflow.org
		("XGBoostJob", "xgboostjob.kubeflow.org"): {
			"api_family": ["apis/xgboostjob.kubeflow.org/v1/"],
			"api": "xgboostjobs",
		},
	}

	def kind_api_version_to_kind(self, kind, api_version):
		# The API group is anything before /, or the empty string if there's no "/"
		if api_version is not None and "/" in api_version:
			tmp = re.match(r"(.*)/.*", api_version)
			if tmp is None:
				raise Exception(f"Could not extract API group from {api_version}")
			api_group = tmp[1]
		else:
			api_group = ""
		return kind, api_group

	def get_latest_api(self, kind):
		if kind not in self.kubernetes_resources:
			raise Exception(f"Could not determine latest API; kind {kind} not found in kubernetes_resources")

		latest_api = deep_get(self.kubernetes_resources[kind], "api_family")[0]
		if latest_api.startswith("api/"):
			latest_api = latest_api[len("api/"):]
		elif latest_api.startswith("apis/"):
			latest_api = latest_api[len("apis/"):]
		if latest_api.endswith("/"):
			latest_api = latest_api[:-len("/")]
		return latest_api

	# In cases where we get a kind that doesn't include the API group
	# (such as from owner references), we have to guess
	def guess_kind(self, kind):
		# If we already have a tuple, don't guess
		if type(kind) == tuple:
			if kind in self.kubernetes_resources:
				return kind

			# We have a tuple, but it didn't have an entry in kubernetes_resources;
			# it might be api + api_family instead though, but for that we need to scan
			for _kind in self.kubernetes_resources:
				if deep_get(self.kubernetes_resources[_kind], "api") == kind[0] and _kind[1] == kind[1]:
					return _kind

		# APIs are grouped in two: Kubernetes "native",
		# and everything else, with native entries first.
		# Thus we can iterate over the dict and stop as soon
		# as we get a match.
		for _kind, _api_group in self.kubernetes_resources:
			if kind == _kind:
				return _kind, _api_group

		raise Exception(f"Couldn't guess kubernetes resource for kind: {kind}")

	def get_available_api_families(self):
		if self.cluster_unreachable == True:
			return [], 42503

		available_apis = set()

		# First get all core APIs
		core_apis = {}

		method = "GET"
		url = f"https://{self.control_plane_ip}:{self.control_plane_port}/api/v1"
		data, message, status = self.__rest_helper_generic_json(method = method, url = url)

		if status == 200:
			core_apis = json.loads(data)
		else:
			# We couldn't get the core APIs; there's no use continuing
			return [], status

		for api in deep_get(core_apis, "resources", []):
			if "list" not in deep_get(api, "verbs", []):
				# Ignore non-list APIs
				continue
			name = deep_get(api, "name", "")
			kind = deep_get(api, "kind", "")
			if (kind, "") in self.kubernetes_resources:
				available_apis.add((kind, ""))

		# Now fetch non-core APIs
		non_core_apis = {}

		url = f"https://{self.control_plane_ip}:{self.control_plane_port}/apis"
		data, message, status = self.__rest_helper_generic_json(method = method, url = url)

		if status == 200:
			non_core_apis = json.loads(data)
		else:
			# No non-core APIs found; this is a bit worrying, but OK...
			pass

		# These are all API groups we know of
		_api_groups = set(api_group for kind, api_group in self.kubernetes_resources)

		# Now create a cross-section between known APIs and available APIs
		api_groups = set()

		for api_group in deep_get(non_core_apis, "groups", []):
			name = deep_get(api_group, "name", "")
			known_api_group = name in _api_groups
			if known_api_group == False:
				continue

			versions = deep_get(api_group, "versions", [])

			# Now we need to check what kinds this api_group supports
			# and using what version
			for version in versions:
				_version = deep_get(version, "groupVersion")
				if _version is None:
					# This shouldn't happen, but ignore it
					continue
				url = f"https://{self.control_plane_ip}:{self.control_plane_port}/apis/{_version}"
				data, message, status = self.__rest_helper_generic_json(method = method, url = url)

				if status != 200:
					# Could not get API info; this is worrying, but ignore it
					continue
				data = json.loads(data)
				match = False
				for resource in deep_get(data, "resources", []):
					if "list" not in deep_get(resource, "verbs", []):
						continue
					kind = deep_get(resource, "kind", "")
					if len(kind) == 0:
						continue
					if (kind, name) in self.kubernetes_resources and f"apis/{_version}/" in self.kubernetes_resources[(kind, name)].get("api_family", ""):
						# We're special casing this since the core API is deprecated and handled transparently
						if (kind, name) == ("Event", "events.k8s.io"):
							continue
						available_apis.add((kind, name))
						continue

		# Now post-process
		return list(available_apis), status

	def get_list_of_namespaced_resources(self):
		vlist = []

		for resource in self.kubernetes_resources:
			if deep_get(self.kubernetes_resources[resource], "namespaced", True) == True:
				vlist.append(resource)
		return vlist

	def __rest_helper_generic_json(self, method = None, url = None, query_params = []):
		data = None
		message = ""

		if self.cluster_unreachable == True:
			status = 42503
			message = "Cluster Unreachable"
			return data, message, status

		header_params = {
			"Accept": "application/json",
			"Content-Type": "application/json",
			"User-Agent": f"{self.programname} v{self.programversion}",
		}

		if self.token is not None:
			header_params["Authorization"] = f"Bearer {self.token}"

		if method is None:
			raise Exception("REST API called without method; this is a programming error!")

		if url is None:
			raise Exception("REST API called without URL; this is a programming error!")

		try:
			result = self.pool_manager.request(method, url, headers = header_params, fields = query_params)
			status = result.status
		except urllib3.exceptions.MaxRetryError as e:
			# No route to host doesn't have a HTTP response; make one up...
			# 503 is Service Unavailable; this is generally temporary, but to distinguish it from a real 503
			# we prefix it...
			status = 42503

		if status == 200:
			# YAY, things went fine!
			retval = True
			d = result.data
			data = d
		elif status == 204:
			# No Content
			pass
		elif status == 400:
			d = json.loads(result.data)
			# Bad request; is the feature disabled? If so we ignore the failure
			message = deep_get(d, "message", "")
			tmp = re.match(r"feature.*disabled", message)
			if tmp is None:
				raise Exception(f"400: Bad Request; method {method} URL {url} header_params: {header_params}; result.data: {result.data}")
		elif status == 401:
			# Unauthorized
			message = f"401: Unauthorized; method {method} URL {url} header_params: {header_params}"
		elif status == 403:
			# Forbidden: request denied
			message = f"403: Forbidden; method {method} URL {url} header_params: {header_params}"
		elif status == 404:
			# page not found (API not available or possibly programming error)
			message = f"404: Not Found; method {method} URL {url} header_params: {header_params}"
		elif status == 405:
			# Method not allowed
			raise Exception(f"405: Method Not Allowed; this is probably a programming error; method: {method} URL {url}; header_params: {header_params}")
		elif status == 406:
			# Not Acceptable
			raise Exception(f"406: Not Acceptable; this is probably a programming error; method: {method} URL {url}; header_params: {header_params}")
		elif status == 410:
			# Gone
			# Most likely a update events were requested (using resourceVersion), but it's been too long since the previous request;
			# caller should retry without &resourceVersion=xxxxx
			pass
		elif status == 500:
			# Internal Server Error
			d = eval(result.data.decode("utf-8"))
			msg = deep_get(d, "message")
			message = f"500: Internal Server Error; method: {method} URL {url}; header_params: {header_params}; message: {msg}"
		elif status == 503:
			# Service Unavailable
			# This is might be a CRD that has failed to deploy properly
			message = f"503: Service Unavailable; method: {method} URL {url}; header_params: {header_params}"
		elif status == 504:
			# Gateway Timeout
			# A request was made for an unrecognised resourceVersion, and timed out waiting for it to become available
			message = f"504: Gateway Timeout; method: {method} URL {url}; header_params: {header_params}"
		elif status == 42503:
			message = f"No route to host; method: {method} URL {url}; header_params: {header_params}"
		else:
			raise Exception(f"Unhandled error: {result.status}; method {method} URL {url}; header_params: {header_params}")

		return data, message, status

	def __rest_helper_delete(self, kind, name, namespace = "", query_params = []):
		method = "DELETE"

		namespace_part = ""
		if namespace is not None and namespace != "":
			namespace_part = f"namespaces/{namespace}/"

		if kind is None:
			raise Exception("__rest_helper_delete called with kind None")

		kind = self.guess_kind(kind)

		if kind in self.kubernetes_resources:
			api_family = deep_get(self.kubernetes_resources[kind], "api_family")
			api = deep_get(self.kubernetes_resources[kind], "api")
			namespaced = deep_get(self.kubernetes_resources[kind], "namespaced", True)
		else:
			raise Exception(f"kind unknown: {kind}")

		fullitem = f"{kind[0]}.{kind[1]} {name}"
		if namespaced == True:
			fullitem = f"{fullitem} (namespace: {namespace})"

		name = f"/{name}"

		if namespaced == False:
			namespace_part = ""

		status = None

		retval = False

		# Try the newest API first and iterate backwards
		for i in range(0, len(api_family)):
			url = f"https://{self.control_plane_ip}:{self.control_plane_port}/{api_family[i]}{namespace_part}{api}{name}"
			data, message, status = self.__rest_helper_generic_json(method = method, url = url, query_params = query_params)
			if status in [200, 204, 42503]:
				break

		return message, status

	def __rest_helper_generic_protobuf(self, method = None, url = None, query_params = []):
		header_params["Accept"] = "application/vnd.kubernetes.protobuf"
		if self.token is not None:
			header_params["Authorization"] = f"Bearer {self.token}"
		# Do we support this version of Kubernetes protobuf?
		expected_signature = b"k8s\x00"
		if result.data[0:4] != expected_signature:
			sys.exit(f"protobuf format not supported")
		sys.exit(f"Protobuf support not implemented yet;\n{result.data}")

	# On failure this function should always return [] for list requests, and None for other requests;
	# this way lists the result can be handled unconditionally in for loops
	def __rest_helper_get(self, kind, name = "", namespace = "", label_selector = "", field_selector = ""):
		vlist = None
		use_protobuf = False

		if kind is None:
			raise Exception("__rest_helper_get API called with kind None")

		if self.cluster_unreachable == True:
			# Our arbitrary return value for Cluster Unreachable
			status = 42503

			# If name is not set this is a list request, so return an empty list instead of None
			if name == "":
				vlist = []
			return vlist, status

		query_params = []
		if field_selector != "":
			query_params.append(("fieldSelector", field_selector))
		if label_selector != "":
			query_params.append(("labelSelector", label_selector))

		method = "GET"

		namespace_part = ""
		if namespace is not None and namespace != "":
			namespace_part = f"namespaces/{namespace}/"

		kind = self.guess_kind(kind)

		if kind in self.kubernetes_resources:
			api_family = deep_get(self.kubernetes_resources[kind], "api_family")
			api = deep_get(self.kubernetes_resources[kind], "api")
			namespaced = deep_get(self.kubernetes_resources[kind], "namespaced", True)
		else:
			raise Exception(f"kind unknown: {kind}")

		if name != "":
			name = f"/{name}"

		if namespaced == False:
			namespace_part = ""

		status = None

		# Try the newest API first and iterate backwards
		for i in range(0, len(api_family)):
			url = f"https://{self.control_plane_ip}:{self.control_plane_port}/{api_family[i]}{namespace_part}{api}{name}"
			if use_protobuf == True:
				data, message, status = self.__rest_helper_generic_protobuf(method = method, url = url, query_params = query_params)
			else:
				data, message, status = self.__rest_helper_generic_json(method = method, url = url, query_params = query_params)

			# All fatal failures are handled in __rest_helper_generic
			if status == 200:
				# Success
				if use_protobuf == True:
					# Do we support this version of Kubernetes protobuf?
					expected_signature = b"k8s\x00"
					if data[0:4] != expected_signature:
						sys.exit(f"protobuf format not supported")
					sys.exit(f"Protobuf support not implemented yet;\n{result.data}")
				else:
					d = json.loads(data)

				# If name is set this is a read request, not a list request
				if name != "":
					vlist = d
				else:
					vlist = d["items"]
				break
			elif status in [204, 400, 403, 503]:
				# We didn't get any data, but we might not want to fail
				continue
			elif status == 404:
				# We didn't get any data, but we might not want to fail

				# page not found (API not available or possibly programming error)
				# raise Exception(f"API not available; this is probably a programming error; URL {url}")

				# Is this the oldest API family we support? If not, we continue,
				# otherwise we give up and return an empty list
				if i < len(api_family) - 1:
					continue
			#elif status == 410:
				# XXX: Should be handled when we implement support for update events

				# Gone
				# We requested update events (using resourceVersion), but it's been too long since the previous request;
				# retry without &resourceVersion=xxxxx

		# If name is not set this is a list request, so return an empty list instead of None
		if name == "" and vlist is None:
			vlist = []

		return vlist, status

	def delete_obj_by_kind_name_namespace(self, kind, name, namespace, force = False):
		query_params = []

		if force == True:
			query_params.append(("gracePeriodSeconds", 0))

		return self.__rest_helper_delete(kind, name, namespace, query_params = query_params)

	def get_metrics(self):
		if self.cluster_unreachable == True:
			return [], 42503

		query_params = []
		url = f"https://{self.control_plane_ip}:{self.control_plane_port}/metrics"
		data, message, status = self.__rest_helper_generic_json(method = "GET", url = url, query_params = query_params)
		if status == 200:
			msg = data.decode("utf-8").splitlines()
		elif status == 204:
			# No Content; pretend that everything is fine
			msg = []
			status = 200
		else:
			msg = []
		return msg, status

	def get_list_by_kind_namespace(self, kind, namespace, label_selector = "", field_selector = ""):
		return self.__rest_helper_get(kind, "", namespace, label_selector, field_selector)

	def get_ref_by_kind_name_namespace(self, kind, name, namespace):
		ref, status = self.__rest_helper_get(kind, name, namespace, "", "")
		return ref

	def read_namespaced_pod_log(self, name, namespace, container = None, tail_lines = 0):
		query_params = []
		if container is not None:
			query_params.append(("container", container))
		if tail_lines is not None:
			query_params.append(("tailLines", tail_lines))
		query_params.append(("timestamps", True))

		method = "GET"
		url = f"https://{self.control_plane_ip}:{self.control_plane_port}/api/v1/namespaces/{namespace}/pods/{name}/log"
		data, message, status = self.__rest_helper_generic_json(method = method, url = url, query_params = query_params)

		if status == 200:
			msg = data.decode("utf-8")
		elif status == 204:
			# No Content
			msg = "No Content"
		else:
			msg = message

		return msg, status

	# Namespace must be the namespace of the resource; the owner reference itself lacks namespace
	# since owners have to reside in the same namespace as their owned resources
	def get_ref_from_owr(self, owr, namespace):
		ref, status = self.__rest_helper_get(deep_get(owr, "kind"), deep_get(owr, "name"), namespace)
		return ref
