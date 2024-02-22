#! /usr/bin/env python3
# Requires: python3 (>= 3.8)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Kubernetes helpers used by CMT
"""

# pylint: disable=line-too-long

import base64
import copy
import hashlib
# ujson is much faster than json,
# but it might not be available
try:
	import ujson as json
	# The exception raised by ujson when parsing fails is different
	# from what json raises
	DecodeException = ValueError
except ModuleNotFoundError:  # pragma: no cover
	import json  # type: ignore
	DecodeException = json.decoder.JSONDecodeError  # type: ignore
import re
import ssl
import sys
import tempfile
import threading
from typing import Any, AnyStr, cast, Dict, List, Optional, Sequence, Tuple, Union
try:
	import yaml
except ModuleNotFoundError:  # pragma: no cover
	sys.exit("ModuleNotFoundError: Could not import yaml; you may need to (re-)run `cmt-install` or `pip3 install PyYAML`; aborting.")

from cryptography import x509
from cryptography.hazmat.primitives import serialization

try:
	import urllib3
except ModuleNotFoundError:  # pragma: no cover
	sys.exit("ModuleNotFoundError: Could not import urllib3; you may need to (re-)run `cmt-install` or `pip3 install urllib3`; aborting.")

from cmtpaths import KUBE_CONFIG_FILE, KUBE_CREDENTIALS_FILE
import cmtlib
from cmtlib import datetime_to_timestamp, get_since, timestamp_to_datetime, versiontuple
#from cmtlog import debuglog
#from cmttypes import LogLevel
from cmttypes import deep_get, deep_get_with_fallback, DictPath, FilePath, FilePathAuditError, ProgrammingError, SecurityChecks, SecurityPolicy, StatusGroup
from cmtio import execute_command_with_response, secure_which
from cmtio import secure_read
from cmtio_yaml import secure_read_yaml, secure_write_yaml

#from ansithemeprint import ANSIThemeString

# Acceptable ciphers
CIPHERS = [
	# TLS v1.3
	"TLS_AES_256_GCM_SHA384",
	"TLS_AES_128_GCM_SHA256",
	"TLS_CHACHA20_POLY1305_SHA256",
	# TLS v1.2
	"ECDHE-RSA-AES256-GCM-SHA384",
	"ECDHE-ECDSA-AES256-GCM-SHA384",
	"ECDHE-RSA-AES128-GCM-SHA256",
	"ECDHE-ECDSA-AES128-GCM-SHA256",
]

renew_lock = threading.Lock()

# A list of all K8s resources we have some knowledge about
kubernetes_resources: Dict[Tuple[str, str], Any] = {
	# core API
	# ComponentStatus is deprecated
	("ComponentStatus", ""): {
		"api_paths": ["api/v1/"],
		"api": "componentstatuses",
	},
	("ConfigMap", ""): {
		"api_paths": ["api/v1/"],
		"api": "configmaps",
	},
	("Endpoints", ""): {
		"api_paths": ["api/v1/"],
		"api": "endpoints",
	},
	("Event", ""): {
		"api_paths": ["api/v1/"],
		"api": "events",
	},
	("LimitRange", ""): {
		"api_paths": ["api/v1/"],
		"api": "limitranges",
	},
	("Namespace", ""): {
		"api_paths": ["api/v1/"],
		"api": "namespaces",
		"namespaced": False,
	},
	("Node", ""): {
		"api_paths": ["api/v1/"],
		"api": "nodes",
		"namespaced": False,
	},
	("PersistentVolume", ""): {
		"api_paths": ["api/v1/"],
		"api": "persistentvolumes",
		"namespaced": False,
	},
	("PersistentVolumeClaim", ""): {
		"api_paths": ["api/v1/"],
		"api": "persistentvolumeclaims",
	},
	("Pod", ""): {
		"api_paths": ["api/v1/"],
		"api": "pods",
	},
	("PodTemplate", ""): {
		"api_paths": ["api/v1/"],
		"api": "podtemplates",
	},
	("ReplicationController", ""): {
		"api_paths": ["api/v1/"],
		"api": "replicationcontrollers",
	},
	("ResourceQuota", ""): {
		"api_paths": ["api/v1/"],
		"api": "resourcequotas",
	},
	("Secret", ""): {
		"api_paths": ["api/v1/"],
		"api": "secrets",
	},
	("Service", ""): {
		"api_paths": ["api/v1/"],
		"api": "services",
	},
	("ServiceAccount", ""): {
		"api_paths": ["api/v1/"],
		"api": "serviceaccounts",
	},
	# admissionregistration.k8s.io
	("MutatingWebhookConfiguration", "admissionregistration.k8s.io"): {
		"api_paths": ["apis/admissionregistration.k8s.io/v1/", "apis/admissionregistration.k8s.io/v1beta1/"],
		"api": "mutatingwebhookconfigurations",
		"namespaced": False,
	},
	("ValidatingAdmissionPolicy", "admissionregistration.k8s.io"): {
		"api_paths": ["apis/admissionregistration.k8s.io/v1alpha1/"],
		"api": "validatingadmissionpolicies",
		"namespaced": False,
	},
	("ValidatingAdmissionPolicyBinding", "admissionregistration.k8s.io"): {
		"api_paths": ["apis/admissionregistration.k8s.io/v1alpha1/"],
		"api": "validatingadmissionpolicybindings",
		"namespaced": False,
	},
	("ValidatingWebhookConfiguration", "admissionregistration.k8s.io"): {
		"api_paths": ["apis/admissionregistration.k8s.io/v1/", "apis/admissionregistration.k8s.io/v1beta1/"],
		"api": "validatingwebhookconfigurations",
		"namespaced": False,
	},
	# apiextensions.k8s.io
	("CustomResourceDefinition", "apiextensions.k8s.io"): {
		"api_paths": ["apis/apiextensions.k8s.io/v1/", "apis/apiextensions.k8s.io/v1beta1/"],
		"api": "customresourcedefinitions",
		"namespaced": False,
	},
	# apiregistration.k8s.io
	("APIService", "apiregistration.k8s.io"): {
		"api_paths": ["apis/apiregistration.k8s.io/v1/"],
		"api": "apiservices",
		"namespaced": False,
	},
	# app.k8s.io
	("Application", "app.k8s.io"): {
		"api_paths": ["apis/app.k8s.io/v1beta1/"],
		"api": "applications",
	},
	# apps
	("ControllerRevision", "apps"): {
		"api_paths": ["apis/apps/v1/"],
		"api": "controllerrevisions",
	},
	("DaemonSet", "apps"): {
		"api_paths": ["apis/apps/v1/"],
		"api": "daemonsets",
	},
	("Deployment", "apps"): {
		"api_paths": ["apis/apps/v1/"],
		"api": "deployments",
	},
	("ReplicaSet", "apps"): {
		"api_paths": ["apis/apps/v1/"],
		"api": "replicasets",
	},
	("StatefulSet", "apps"): {
		"api_paths": ["apis/apps/v1/"],
		"api": "statefulsets",
	},
	# autoscaling
	("HorizontalPodAutoscaler", "autoscaling"): {
		"api_paths": ["apis/autoscaling/v2/", "apis/autoscaling/v2beta2/", "apis/autoscaling/v1/"],
		"api": "horizontalpodautoscalers",
	},
	# autoscaling.k8s.io
	("VerticalPodAutoscaler", "autoscaling.k8s.io"): {
		"api_paths": ["apis/autoscaling.k8s.io/v1/"],
		"api": "verticalpodautoscalers",
	},
	("VerticalPodAutoscalerCheckpoint", "autoscaling.k8s.io"): {
		"api_paths": ["apis/autoscaling.k8s.io/v1/"],
		"api": "verticalpodautoscalercheckpoints",
	},
	# batch
	("CronJob", "batch"): {
		"api_paths": ["apis/batch/v1/", "apis/batch/v1beta1/"],
		"api": "cronjobs",
	},
	("Job", "batch"): {
		"api_paths": ["apis/batch/v1/", "apis/batch/v1beta1/"],
		"api": "jobs",
	},
	# certificates.k8s.io
	("CertificateSigningRequest", "certificates.k8s.io"): {
		"api_paths": ["apis/certificates.k8s.io/v1/"],
		"api": "certificatesigningrequests",
		"namespaced": False,
	},
	("ClusterTrustBundle", "certificates.k8s.io"): {
		"api_paths": ["apis/certificates.k8s.io/v1alpha1/"],
		"api": "clustertrustbundles",
		"namespaced": False,
	},
	# coordination.k8s.io
	("Lease", "coordination.k8s.io"): {
		"api_paths": ["apis/coordination.k8s.io/v1/"],
		"api": "leases",
	},
	# discovery.k8s.io
	("EndpointSlice", "discovery.k8s.io"): {
		"api_paths": ["apis/discovery.k8s.io/v1/", "apis/discovery.k8s.io/v1beta1/"],
		"api": "endpointslices",
	},
	# events.k8s.io
	("Event", "events.k8s.io"): {
		"api_paths": ["apis/events.k8s.io/v1/"],
		"api": "events",
	},
	# flowcontrol.apiserver.k8s.io
	("FlowSchema", "flowcontrol.apiserver.k8s.io"): {
		"api_paths": ["apis/flowcontrol.apiserver.k8s.io/v1/", "apis/flowcontrol.apiserver.k8s.io/v1beta3/", "apis/flowcontrol.apiserver.k8s.io/v1beta2/", "apis/flowcontrol.apiserver.k8s.io/v1beta1/"],
		"api": "flowschemas",
		"namespaced": False,
	},
	("PriorityLevelConfiguration", "flowcontrol.apiserver.k8s.io"): {
		"api_paths": ["apis/flowcontrol.apiserver.k8s.io/v1/", "apis/flowcontrol.apiserver.k8s.io/v1beta3/", "apis/flowcontrol.apiserver.k8s.io/v1beta2/", "apis/flowcontrol.apiserver.k8s.io/v1beta1/"],
		"api": "prioritylevelconfigurations",
		"namespaced": False,
	},
	# internal.apiserver.k8s.io
	("StorageVersion", "internal.apiserver.k8s.io"): {
		"api_paths": ["apis/internal.apiserver.k8s.io/v1alpha1/"],
		"api": "storageversions",
		"namespaced": False,
	},
	# metacontroller.k8s.io
	("CompositeController", "metacontroller.k8s.io"): {
		"api_paths": ["apis/metacontroller.k8s.io/v1alpha1/"],
		"api": "compositecontrollers",
		"namespaced": False,
	},
	("ControllerRevision", "metacontroller.k8s.io"): {
		# => "apps" ?
		"api_paths": ["apis/metacontroller.k8s.io/v1alpha1/"],
		"api": "controllerrevisions",
	},
	("DecoratorController", "metacontroller.k8s.io"): {
		"api_paths": ["apis/metacontroller.k8s.io/v1alpha1/"],
		"api": "decoratorcontrollers",
		"namespaced": False,
	},
	# metrics.k8s.io
	("NodeMetrics", "metrics.k8s.io"): {
		"api_paths": ["apis/metrics.k8s.io/v1beta1/"],
		"api": "nodes",
		"namespaced": False,
	},
	("PodMetrics", "metrics.k8s.io"): {
		"api_paths": ["apis/metrics.k8s.io/v1beta1/"],
		"api": "pods",
	},
	# networking.k8s.io
	("ClusterCIDR", "networking.k8s.io"): {
		"api_paths": ["apis/networking.k8s.io/v1alpha1/"],
		"api": "clustercidrs",
		"namespaced": False,
	},
	("IPAddress", "networking.k8s.io"): {
		"api_paths": ["apis/networking.k8s.io/v1alpha1/"],
		"api": "ipaddresses",
		"namespaced": False,
	},
	("Ingress", "networking.k8s.io"): {
		"api_paths": ["apis/networking.k8s.io/v1/", "apis/networking.k8s.io/v1beta1/"],
		"api": "ingresses",
	},
	("IngressClass", "networking.k8s.io"): {
		"api_paths": ["apis/networking.k8s.io/v1/", "apis/networking.k8s.io/v1beta1/"],
		"api": "ingressclasses",
		"namespaced": False,
	},
	("NetworkPolicy", "networking.k8s.io"): {
		"api_paths": ["apis/networking.k8s.io/v1/", "apis/networking.k8s.io/v1beta1/"],
		"api": "networkpolicies",
	},
	("ServiceCIDR", "networking.k8s.io"): {
		"api_paths": ["apis/networking.k8s.io/v1alpha1/"],
		"api": "servicecidrs",
		"namespaced": False,
	},
	# node.k8s.io
	("RuntimeClass", "node.k8s.io"): {
		"api_paths": ["apis/node.k8s.io/v1/", "apis/node.k8s.io/v1beta1/"],
		"api": "runtimeclasses",
		"namespaced": False,
	},
	# policy
	("PodDisruptionBudget", "policy"): {
		"api_paths": ["apis/policy/v1/", "apis/policy/v1beta1/"],
		"api": "poddisruptionbudgets",
	},
	("PodSecurityPolicy", "policy"): {
		"api_paths": ["apis/policy/v1beta1/"],
		"api": "podsecuritypolicies",
		"namespaced": False,
		"deprecated": "v1.21",
		"unavailable": "v1.25",
	},
	# rbac.authorization.k8s.io
	("ClusterRole", "rbac.authorization.k8s.io"): {
		"api_paths": ["apis/rbac.authorization.k8s.io/v1/"],
		"api": "clusterroles",
		"namespaced": False,
	},
	("ClusterRoleBinding", "rbac.authorization.k8s.io"): {
		"api_paths": ["apis/rbac.authorization.k8s.io/v1/"],
		"api": "clusterrolebindings",
		"namespaced": False,
	},
	("Role", "rbac.authorization.k8s.io"): {
		"api_paths": ["apis/rbac.authorization.k8s.io/v1/"],
		"api": "roles",
	},
	("RoleBinding", "rbac.authorization.k8s.io"): {
		"api_paths": ["apis/rbac.authorization.k8s.io/v1/"],
		"api": "rolebindings",
	},
	# scheduling.k8s.io
	("PriorityClass", "scheduling.k8s.io"): {
		"api_paths": ["apis/scheduling.k8s.io/v1/"],
		"api": "priorityclasses",
		"namespaced": False,
	},
	# scheduling.sigs.k8s.io
	("ElasticQuota", "scheduling.sigs.k8s.io"): {
		"api_paths": ["apis/scheduling.sigs.k8s.io/v1alpha1/"],
		"api": "elasticquotas",
	},
	("PodGroup", "scheduling.sigs.k8s.io"): {
		"api_paths": ["apis/scheduling.sigs.k8s.io/v1alpha1/"],
		"api": "podgroups",
	},
	# snapshot.storage.k8s.io
	("VolumeSnapshot", "snapshot.storage.k8s.io"): {
		"api_paths": ["apis/snapshot.storage.k8s.io/v1/", "apis/snapshot.storage.k8s.io/v1beta1/"],
		"api": "volumesnapshots",
	},
	("VolumeSnapshotClass", "snapshot.storage.k8s.io"): {
		"api_paths": ["apis/snapshot.storage.k8s.io/v1/", "apis/snapshot.storage.k8s.io/v1beta1/"],
		"api": "volumesnapshotclasses",
		"namespaced": False,
	},
	("VolumeSnapshotContent", "snapshot.storage.k8s.io"): {
		"api_paths": ["apis/snapshot.storage.k8s.io/v1/", "apis/snapshot.storage.k8s.io/v1beta1/"],
		"api": "volumesnapshotcontents",
		"namespaced": False,
	},
	# storage.k8s.io
	("CSIDriver", "storage.k8s.io"): {
		"api_paths": ["apis/storage.k8s.io/v1/"],
		"api": "csidrivers",
		"namespaced": False,
	},
	("CSINode", "storage.k8s.io"): {
		"api_paths": ["apis/storage.k8s.io/v1/"],
		"api": "csinodes",
		"namespaced": False,
	},
	("CSIStorageCapacity", "storage.k8s.io"): {
		"api_paths": ["apis/storage.k8s.io/v1/", "apis/storage.k8s.io/v1beta1/"],
		"api": "csistoragecapacities",
	},
	("StorageClass", "storage.k8s.io"): {
		"api_paths": ["apis/storage.k8s.io/v1/"],
		"api": "storageclasses",
		"namespaced": False,
	},
	("VolumeAttachment", "storage.k8s.io"): {
		"api_paths": ["apis/storage.k8s.io/v1/"],
		"api": "volumeattachments",
		"namespaced": False,
	},
	("VolumeAttributesClass", "storage.k8s.io"): {
		"api_paths": ["apis/storage.k8s.io/v1alpha1/"],
		"api": "volumeattributesclasses",
		"namespaced": False,
	},

	# aadpodidentity.k8s.io
	("AzureIdentity", "aadpodidentity.k8s.io"): {
		"api_paths": ["apis/aadpodidentity.k8s.io/v1/"],
		"api": "azureidentities",
	},
	("AzureIdentityBinding", "aadpodidentity.k8s.io"): {
		"api_paths": ["apis/aadpodidentity.k8s.io/v1/"],
		"api": "azureidentitybindings",
	},
	("AzurePodIdentityException", "aadpodidentity.k8s.io"): {
		"api_paths": ["apis/aadpodidentity.k8s.io/v1/"],
		"api": "azurepodidentityexceptions",
	},
	# access.smi-spec.io
	("TrafficTarget", "access.smi-spec.io"): {
		"api_paths": ["apis/access.smi-spec.io/v1alpha2/"],
		"api": "traffictargets",
	},
	# acme.cert-manager.io <= split from: cert-manager.io
	("Challenge", "acme.cert-manager.io"): {
		"api_paths": ["apis/acme.cert-manager.io/v1/", "apis/acme.cert-manager.k8s.io/v1alpha2/", "certmanager.k8s.io/v1alpha1/"],
		"api": "challenges",
	},
	("Order", "acme.cert-manager.io"): {
		"api_paths": ["apis/acme.cert-manager.io/v1/", "apis/acme.cert-manager.k8s.io/v1alpha2/", "certmanager.k8s.io/v1alpha1/"],
		"api": "orders",
	},
	# addons.cluster.x-k8s.io
	("ClusterResourceSetBinding", "addons.cluster.x-k8s.io"): {
		"api_paths": ["apis/addons.cluster.x-k8s.io/v1beta1/"],
		"api": "clusterresourcesetbindings",
	},
	("ClusterResourceSet", "addons.cluster.x-k8s.io"): {
		"api_paths": ["apis/addons.cluster.x-k8s.io/v1beta1/"],
		"api": "clusterresourcesets",
	},
	# apiserver.openshift.io
	("APIRequestCount", "apiserver.openshift.io"): {
		"api_paths": ["apis/apiserver.openshift.io/v1/"],
		"api": "apirequestcounts",
		"namespaced": False,
	},
	# apps.kruise.io
	("AdvancedCronJob", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "advancedcronjobs",
	},
	("BroadcastJob", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "broadcastjobs",
	},
	("CloneSet", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "clonesets",
	},
	("ContainerRecreateRequest", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "containerrecreaterequests",
	},
	("DaemonSet", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "daemonsets",
	},
	("ImagePullJob", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "imagepulljobs",
	},
	("NodeImage", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "nodeimages",
		"namespaced": False,
	},
	("NodePodProbe", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "nodepodprobes",
		"namespaced": False,
	},
	("PersistentPodState", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "persistentpodstates",
	},
	("PodProbeMarker", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "podprobemarkers",
	},
	("ResourceDistribution", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "resourcedistributions",
		"namespaced": False,
	},
	("SidecarSet", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "sidecarsets",
		"namespaced": False,
	},
	("StatefulSet", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1beta1/"],
		"api": "statefulsets",
	},
	("UnitedDeployment", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "uniteddeployments",
	},
	("WorkloadSpread", "apps.kruise.io"): {
		"api_paths": ["apis/apps.kruise.io/v1alpha1/"],
		"api": "workloadspreads",
	},
	# apps.openshift.io
	("DeploymentConfig", "apps.openshift.io"): {
		"api_paths": ["apis/apps.openshift.io/v1/"],
		"api": "deploymentconfigs",
	},
	# argoproj.io
	("Application", "argoproj.io"): {
		"api_paths": ["apis/argoproj.io/v1alpha1/"],
		"api": "applications",
	},
	("ApplicationSet", "argoproj.io"): {
		"api_paths": ["apis/argoproj.io/v1alpha1/"],
		"api": "applicationsets",
	},
	("AppProject", "argoproj.io"): {
		"api_paths": ["apis/argoproj.io/v1alpha1/"],
		"api": "appprojects",
	},
	("ClusterWorkflowTemplate", "argoproj.io"): {
		"api_paths": ["apis/argoproj.io/v1alpha1/"],
		"api": "clusterworkflowtemplates",
	},
	("CronWorkflow", "argoproj.io"): {
		"api_paths": ["apis/argoproj.io/v1alpha1/"],
		"api": "cronworkflows",
	},
	("WorkflowEventBinding", "argoproj.io"): {
		"api_paths": ["apis/argoproj.io/v1alpha1/"],
		"api": "workfloweventbindings",
	},
	("Workflow", "argoproj.io"): {
		"api_paths": ["apis/argoproj.io/v1alpha1/"],
		"api": "workflows",
	},
	("WorkflowTemplate", "argoproj.io"): {
		"api_paths": ["apis/argoproj.io/v1alpha1/"],
		"api": "workflowtemplates",
	},
	# aquasecurity.github.io
	("CISKubeBenchReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "ciskubebenchreports",
		"namespaced": False,
	},
	("ClusterComplianceReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "clustercompliancereports",
		"namespaced": False,
	},
	("ClusterConfigAuditReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "clusterconfigauditreports",
		"namespaced": False,
	},
	("ClusterInfraAssessmentReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "clusterinfraassessmentreports",
		"namespaced": False,
	},
	("ClusterRbacAssessmentReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "clusterrbacassessmentreports",
		"namespaced": False,
	},
	("ClusterSbomReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "clustersbomreports",
		"namespaced": False,
	},
	("ClusterVulnerabilityReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "clustervulnerabilityreports",
		"namespaced": False,
	},
	("ConfigAuditReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "configauditreports",
	},
	("ExposedSecretReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "exposedsecretreports",
	},
	("InfraAssessmentReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "infraassessmentreports",
	},
	("KubeHunterReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "kubehunterreports",
		"namespaced": False,
	},
	("RbacAssessmentReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "rbacassessmentreports",
	},
	("SbomReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "sbomreports",
	},
	("VulnerabilityReport", "aquasecurity.github.io"): {
		"api_paths": ["apis/aquasecurity.github.io/v1alpha1/"],
		"api": "vulnerabilityreports",
	},
	# auth.kio.kasten.io
	("K10ClusterRoleBinding", "auth.kio.kasten.io"): {
		"api_paths": ["apis/auth.kio.kasten.io/v1alpha1/"],
		"api": "k10clusterrolebindings",
	},
	("K10ClusterRole", "auth.kio.kasten.io"): {
		"api_paths": ["apis/auth.kio.kasten.io/v1alpha1/"],
		"api": "k10clusterroles",
	},
	# authorization.openshift.io
	("ClusterRole", "authorization.openshift.io"): {
		"api_paths": ["apis/authorization.openshift.io/v1/"],
		"api": "clusterroles",
		"namespaced": False,
	},
	("ClusterRoleBinding", "authorization.openshift.io"): {
		"api_paths": ["apis/authorization.openshift.io/v1/"],
		"api": "clusterrolebindings",
		"namespaced": False,
	},
	("Role", "authorization.openshift.io"): {
		"api_paths": ["apis/authorization.openshift.io/v1/"],
		"api": "roles",
	},
	("RoleBinding", "authorization.openshift.io"): {
		"api_paths": ["apis/authorization.openshift.io/v1/"],
		"api": "rolebindings",
	},
	("RoleBindingRestriction", "authorization.openshift.io"): {
		"api_paths": ["apis/authorization.openshift.io/v1/"],
		"api": "rolebindingrestrictions",
	},
	# autoscaling.openshift.io
	("ClusterAutoscaler", "autoscaling.openshift.io"): {
		"api_paths": ["apis/autoscaling.openshift.io/v1/"],
		"api": "clusterautoscalers",
		"namespaced": False,
	},
	("MachineAutoscaler", "autoscaling.openshift.io"): {
		"api_paths": ["apis/autoscaling.openshift.io/v1beta1/"],
		"api": "machineautoscalers",
	},
	# autoscaling.internal.knative.dev
	("Metric", "autoscaling.internal.knative.dev"): {
		"api_paths": ["apis/autoscaling.internal.knative.dev/v1alpha1/"],
		"api": "metrics",
	},
	("PodAutoscaler", "autoscaling.internal.knative.dev"): {
		"api_paths": ["apis/autoscaling.internal.knative.dev/v1alpha1/"],
		"api": "podautoscalers",
	},
	# batch.volcano.sh
	("Job", "batch.volcano.sh"): {
		"api_paths": ["apis/batch.volcano.sh/v1alpha1/"],
		"api": "jobs",
	},
	# bmc.tinkerbell.org
	("Job", "bmc.tinkerbell.org"): {
		"api_paths": ["apis/bmc.tinkerbell.org/v1alpha1/"],
		"api": "jobs",
	},
	("Machine", "bmc.tinkerbell.org"): {
		"api_paths": ["apis/bmc.tinkerbell.org/v1alpha1/"],
		"api": "machines",
	},
	("Task", "bmc.tinkerbell.org"): {
		"api_paths": ["apis/bmc.tinkerbell.org/v1alpha1/"],
		"api": "tasks",
	},
	# bootstrap.cluster.x-k8s.io
	("EKSConfig", "bootstrap.cluster.x-k8s.io"): {
		"api_paths": ["apis/bootstrap.cluster.x-k8s.io/v1beta2/"],
		"api": "eksconfigs",
	},
	("EKSConfigTemplate", "bootstrap.cluster.x-k8s.io"): {
		"api_paths": ["apis/bootstrap.cluster.x-k8s.io/v1beta2/"],
		"api": "eksconfigtemplates",
	},
	("KubeadmConfig", "bootstrap.cluster.x-k8s.io"): {
		"api_paths": ["apis/bootstrap.cluster.x-k8s.io/v1beta1/"],
		"api": "kubeadmconfigs",
	},
	("KubeadmConfigTemplate", "bootstrap.cluster.x-k8s.io"): {
		"api_paths": ["apis/bootstrap.cluster.x-k8s.io/v1beta1/"],
		"api": "kubeadmconfigtemplates",
	},
	# bus.volcano.sh
	("Command", "bus.volcano.sh"): {
		"api_paths": ["apis/bus.volcano.sh/v1alpha1/"],
		"api": "commands",
	},
	# build.openshift.io
	("BuildConfig", "build.openshift.io"): {
		"api_paths": ["apis/build.openshift.io/v1/"],
		"api": "buildconfigs",
	},
	("Build", "build.openshift.io"): {
		"api_paths": ["apis/build.openshift.io/v1/"],
		"api": "builds",
	},
	# caching.internal.knative.dev
	("Image", "caching.internal.knative.dev"): {
		"api_paths": ["apis/caching.internal.knative.dev/v1alpha1/"],
		"api": "images",
	},
	# cassandra.datastax.com
	("CassandraDatacenter", "cassandra.datastax.com"): {
		"api_paths": ["apis/cassandra.datastax.com/v1beta1/"],
		"api": "cassandradatacenters",
	},
	# cassandra.k8ssandra.io
	("CassandraBackup", "cassandra.k8ssandra.io"): {
		"api_paths": ["apis/cassandra.k8ssandra.io/v1alpha1/"],
		"api": "cassandrabackups",
	},
	("CassandraRestore", "cassandra.k8ssandra.io"): {
		"api_paths": ["apis/cassandra.k8ssandra.io/v1alpha1/"],
		"api": "cassandrarestores",
	},
	# catalogd.operatorframework.io
	("BundleMetadata", "catalogd.operatorframework.io"): {
		"api_paths": ["apis/catalogd.operatorframework.io/v1alpha1/"],
		"api": "bundlemetadata",
		"namespaced": False,
	},
	("CatalogMetadata", "catalogd.operatorframework.io"): {
		"api_paths": ["apis/catalogd.operatorframework.io/v1alpha1/"],
		"api": "catalogmetadata",
		"namespaced": False,
	},
	("Catalog", "catalogd.operatorframework.io"): {
		"api_paths": ["apis/catalogd.operatorframework.io/v1alpha1/"],
		"api": "catalogs",
		"namespaced": False,
	},
	("Package", "catalogd.operatorframework.io"): {
		"api_paths": ["apis/catalogd.operatorframework.io/v1alpha1/"],
		"api": "packages",
		"namespaced": False,
	},
	# cdi.kubevirt.io
	("CDI", "cdi.kubevirt.io"): {
		"api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
		"api": "cdis",
		"namespaced": False,
	},
	("DataVolume", "cdi.kubevirt.io"): {
		"api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
		"api": "datavolumes",
	},
	("CDIConfig", "cdi.kubevirt.io"): {
		"api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
		"api": "cdiconfigs",
		"namespaced": False,
	},
	("StorageProfile", "cdi.kubevirt.io"): {
		"api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
		"api": "storageprofiles",
		"namespaced": False,
	},
	("DataSource", "cdi.kubevirt.io"): {
		"api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
		"api": "datasources",
	},
	("DataImportCron", "cdi.kubevirt.io"): {
		"api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
		"api": "dataimportcrons",
	},
	("ObjectTransfer", "cdi.kubevirt.io"): {
		"api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
		"api": "objecttransfers",
		"namespaced": False,
	},
	# cert-manager.io <= rename from: certmanager.k8s.io
	("Certificate", "cert-manager.io"): {
		"api_paths": ["apis/cert-manager.io/v1/", "apis/cert-manager.io/v1alpha2/", "apis/certmanager.k8s.io/v1alpha1/"],
		"api": "certificates",
	},
	("CertificateRequest", "cert-manager.io"): {
		"api_paths": ["apis/cert-manager.io/v1/", "apis/cert-manager.io/v1alpha2/", "apis/certmanager.k8s.io/v1alpha1/"],
		"api": "certificaterequests",
	},
	("ClusterIssuer", "cert-manager.io"): {
		"api_paths": ["apis/cert-manager.io/v1/", "apis/cert-manager.io/v1alpha2/", "apis/certmanager.k8s.io/v1alpha1/"],
		"api": "clusterissuers",
		"namespaced": False,
	},
	("Issuer", "cert-manager.io"): {
		"api_paths": ["apis/cert-manager.io/v1/", "apis/cert-manager.io/v1alpha2/", "apis/certmanager.k8s.io/v1alpha1/"],
		"api": "issuers",
	},
	# cilium.io
	("CiliumCIDRGroup", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2alpha1/"],
		"api": "ciliumcidrgroups",
		"namespaced": False,
	},
	("CiliumClusterwideNetworkPolicy", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2/"],
		"api": "ciliumclusterwidenetworkpolicies",
		"namespaced": False,
	},
	("CiliumEndpoint", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2/"],
		"api": "ciliumendpoints",
	},
	("CiliumExternalWorkload", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2/"],
		"api": "ciliumexternalworkloads",
		"namespaced": False,
	},
	("CiliumIdentity", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2/"],
		"api": "ciliumidentities",
		"namespaced": False,
	},
	("CiliumL2AnnouncementPolicy", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2alpha1/"],
		"api": "ciliuml2announcementpolicies",
		"namespaced": False,
	},
	("CiliumLoadBalancerIPPool", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2alpha1/"],
		"api": "ciliumloadbalancerippools",
		"namespaced": False,
	},
	("CiliumLocalRedirectPolicy", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2/"],
		"api": "ciliumlocalredirectpolicies",
	},
	("CiliumNetworkPolicy", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2/"],
		"api": "ciliumnetworkpolicies",
	},
	("CiliumNode", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2/"],
		"api": "ciliumnodes",
		"namespaced": False,
	},
	("CiliumNodeConfig", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2alpha1/"],
		"api": "ciliumnodeconfigs",
	},
	("CiliumPodIPPool", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v2alpha1/"],
		"api": "ciliumpodippools",
		"namespaced": False,
	},
	("TracingPolicy", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v1alpha1/"],
		"api": "tracingpolicies",
		"namespaced": False,
	},
	("TracingPolicyNamespaced", "cilium.io"): {
		"api_paths": ["apis/cilium.io/v1alpha1/"],
		"api": "tracingpoliciesnamespaced",
	},
	# cis.cattle.io
	("ClusterScanBenchmark", "cis.cattle.io"): {
		"api_paths": ["apis/cis.cattle.io/v1/"],
		"api": "clusterscanbenchmarks",
		"namespaced": False,
	},
	("ClusterScanProfile", "cis.cattle.io"): {
		"api_paths": ["apis/cis.cattle.io/v1/"],
		"api": "clusterscanprofiles",
		"namespaced": False,
	},
	("ClusterScanReport", "cis.cattle.io"): {
		"api_paths": ["apis/cis.cattle.io/v1/"],
		"api": "clusterscanreports",
		"namespaced": False,
	},
	("ClusterScan", "cis.cattle.io"): {
		"api_paths": ["apis/cis.cattle.io/v1/"],
		"api": "clusterscans",
		"namespaced": False,
	},
	# clone.kubevirt.io
	("VirtualMachineClone", "clone.kubevirt.io"): {
		"api_paths": ["apis/clone.kubevirt.io/v1alpha1/"],
		"api": "virtualmachineclones",
	},
	# cloudcredential.openshift.io
	("CredentialsRequest", "cloudcredential.openshift.io"): {
		"api_paths": ["apis/cloudcredential.openshift.io/v1/"],
		"api": "credentialsrequests",
	},
	# cluster.loft.sh
	("ClusterQuota", "cluster.loft.sh"): {
		"api_paths": ["apis/cluster.loft.sh/v1/"],
		"api": "clusterquotas",
		"namespaced": False,
	},
	("HelmRelease", "cluster.loft.sh"): {
		"api_paths": ["apis/cluster.loft.sh/v1/"],
		"api": "helmreleases",
	},
	("LocalClusterAccess", "cluster.loft.sh"): {
		"api_paths": ["apis/cluster.loft.sh/v1/"],
		"api": "localclusteraccesses",
		"namespaced": False,
	},
	("SleepModeConfig", "cluster.loft.sh"): {
		"api_paths": ["apis/cluster.loft.sh/v1/"],
		"api": "sleepmodeconfigs",
	},
	("Space", "cluster.loft.sh"): {
		"api_paths": ["apis/cluster.loft.sh/v1/"],
		"api": "spaces",
		"namespaced": False,
	},
	("VirtualCluster", "cluster.loft.sh"): {
		"api_paths": ["apis/cluster.loft.sh/v1/"],
		"api": "virtualclusters",
	},
	# cluster.x-k8s.io
	("ClusterClass", "cluster.x-k8s.io"): {
		"api_paths": ["apis/cluster.x-k8s.io/v1beta1/"],
		"api": "clusterclasses",
	},
	("Cluster", "cluster.x-k8s.io"): {
		"api_paths": ["apis/cluster.x-k8s.io/v1beta1/"],
		"api": "clusters",
	},
	("MachineDeployment", "cluster.x-k8s.io"): {
		"api_paths": ["apis/cluster.x-k8s.io/v1beta1/"],
		"api": "machinedeployments",
	},
	("MachineHealthCheck", "cluster.x-k8s.io"): {
		"api_paths": ["apis/cluster.x-k8s.io/v1beta1/"],
		"api": "machinehealthchecks",
	},
	("MachinePool", "cluster.x-k8s.io"): {
		"api_paths": ["apis/cluster.x-k8s.io/v1beta1/"],
		"api": "machinepools",
	},
	("Machine", "cluster.x-k8s.io"): {
		"api_paths": ["apis/cluster.x-k8s.io/v1beta1/"],
		"api": "machines",
	},
	("MachineSet", "cluster.x-k8s.io"): {
		"api_paths": ["apis/cluster.x-k8s.io/v1beta1/"],
		"api": "machinesets",
	},
	# clusterctl.cluster.x-k8s.io
	("Provider", "clusterctl.cluster.x-k8s.io"): {
		"api_paths": ["apis/clusterctl.cluster.x-k8s.io/v1alpha3/"],
		"api": "providers",
	},
	# config.gatekeeper.sh
	("Config", "config.gatekeeper.sh"): {
		"api_paths": ["apis/config.gatekeeper.sh/v1alpha1/"],
		"api": "configs",
	},
	# config.kio.kasten.io
	("Policy", "config.kio.kasten.io"): {
		"api_paths": ["apis/config.kio.kasten.io/v1alpha1/"],
		"api": "policies",
	},
	("Profile", "config.kio.kasten.io"): {
		"api_paths": ["apis/config.kio.kasten.io/v1alpha1/"],
		"api": "profiles",
	},
	# config.kiosk.sh
	("AccountQuota", "config.kiosk.sh"): {
		"api_paths": ["apis/config.kiosk.sh/v1alpha1/"],
		"api": "accountquotas",
		"namespaced": False,
	},
	("Account", "config.kiosk.sh"): {
		"api_paths": ["apis/config.kiosk.sh/v1alpha1/"],
		"api": "accounts",
		"namespaced": False,
	},
	("TemplateInstance", "config.kiosk.sh"): {
		"api_paths": ["apis/config.kiosk.sh/v1alpha1/"],
		"api": "templateinstances",
	},
	("Template", "config.kiosk.sh"): {
		"api_paths": ["apis/config.kiosk.sh/v1alpha1/"],
		"api": "templates",
		"namespaced": False,
	},
	# config.openshift.io
	("APIServer", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "apiservers",
		"namespaced": False,
	},
	("Authentication", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "authentications",
		"namespaced": False,
	},
	("Backup", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1alpha1/"],
		"api": "backups",
		"namespaced": False,
	},
	("Build", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "builds",
		"namespaced": False,
	},
	("ClusterOperator", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "clusteroperators",
		"namespaced": False,
	},
	("ClusterVersion", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "clusterversions",
		"namespaced": False,
	},
	("Console", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "consoles",
		"namespaced": False,
	},
	("DNS", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "dnses",
		"namespaced": False,
	},
	("FeatureGate", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "featuregates",
		"namespaced": False,
	},
	("HelmChartRepository", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1beta1/"],
		"api": "helmchartrepositories",
		"namespaced": False,
	},
	("Image", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "images",
		"namespaced": False,
	},
	("ImageContentPolicy", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "imagecontentpolicies",
		"namespaced": False,
	},
	("ImageDigestMirrorSet", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "imagedigestmirrorsets",
		"namespaced": False,
	},
	("ImageTagMirrorSet", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "imagetagmirrorsets",
		"namespaced": False,
	},
	("Infrastructure", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "infrastructures",
		"namespaced": False,
	},
	("Ingress", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "ingresses",
		"namespaced": False,
	},
	("InsightsDataGather", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1alpha1/"],
		"api": "insightsdatagathers",
		"namespaced": False,
	},
	("Network", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "networks",
		"namespaced": False,
	},
	("Node", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "nodes",
		"namespaced": False,
	},
	("OAuth", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "oauths",
		"namespaced": False,
	},
	("OperatorHub", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "operatorhubs",
		"namespaced": False,
	},
	("Project", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "projects",
		"namespaced": False,
	},
	("Proxy", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "proxies",
		"namespaced": False,
	},
	("Scheduler", "config.openshift.io"): {
		"api_paths": ["apis/config.openshift.io/v1/"],
		"api": "schedulers",
		"namespaced": False,
	},
	# console.openshift.io
	("ConsoleCLIDownload", "console.openshift.io"): {
		"api_paths": ["apis/console.openshift.io/v1/"],
		"api": "consoleclidownloads",
		"namespaced": False,
	},
	("ConsoleExternalLogLink", "console.openshift.io"): {
		"api_paths": ["apis/console.openshift.io/v1/"],
		"api": "consoleexternalloglinks",
		"namespaced": False,
	},
	("ConsoleLink", "console.openshift.io"): {
		"api_paths": ["apis/console.openshift.io/v1/"],
		"api": "consolelinks",
		"namespaced": False,
	},
	("ConsoleNotification", "console.openshift.io"): {
		"api_paths": ["apis/console.openshift.io/v1/"],
		"api": "consolenotifications",
		"namespaced": False,
	},
	("ConsolePlugin", "console.openshift.io"): {
		"api_paths": ["apis/console.openshift.io/v1alpha1/"],
		"api": "consoleplugins",
		"namespaced": False,
	},
	("ConsoleQuickStart", "console.openshift.io"): {
		"api_paths": ["apis/console.openshift.io/v1/"],
		"api": "consolequickstarts",
		"namespaced": False,
	},
	("ConsoleSample", "console.openshift.io"): {
		"api_paths": ["apis/console.openshift.io/v1/"],
		"api": "consolesamples",
		"namespaced": False,
	},
	("ConsoleYAMLSample", "console.openshift.io"): {
		"api_paths": ["apis/console.openshift.io/v1/"],
		"api": "consoleyamlsamples",
		"namespaced": False,
	},
	# controlplane.antrea.io
	("AddressGroup", "controlplane.antrea.io"): {
		"api_paths": ["apis/controlplane.antrea.io/v1beta2/"],
		"api": "addressgroups",
		"namespaced": False,
	},
	("AppliedToGroup", "controlplane.antrea.io"): {
		"api_paths": ["apis/controlplane.antrea.io/v1beta2/"],
		"api": "appliedtogroups",
		"namespaced": False,
	},
	("EgressGroup", "controlplane.antrea.io"): {
		"api_paths": ["apis/controlplane.antrea.io/v1beta2/"],
		"api": "egressgroups",
		"namespaced": False,
	},
	("NetworkPolicy", "controlplane.antrea.io"): {
		"api_paths": ["apis/controlplane.antrea.io/v1beta2/"],
		"api": "networkpolicies",
		"namespaced": False,
	},
	# controlplane.cluster.x-k8s.io
	("AWSManagedControlPlane", "controlplane.cluster.x-k8s.io"): {
		"api_paths": ["apis/controlplane.cluster.x-k8s.io/v1beta2/"],
		"api": "awsmanagedcontrolplanes",
	},
	("KubeadmControlPlane", "controlplane.cluster.x-k8s.io"): {
		"api_paths": ["apis/controlplane.cluster.x-k8s.io/v1beta1/"],
		"api": "kubeadmcontrolplanes",
	},
	("KubeadmControlPlaneTemplate", "controlplane.cluster.x-k8s.io"): {
		"api_paths": ["apis/controlplane.cluster.x-k8s.io/v1beta1/"],
		"api": "kubeadmcontrolplanetemplates",
	},
	# controlplane.operator.openshift.io
	("PodNetworkConnectivityCheck", "controlplane.operator.openshift.io"): {
		"api_paths": ["apis/controlplane.operator.openshift.io/v1alpha1/"],
		"api": "podnetworkconnectivitychecks",
	},
	# core.rukpak.io
	("BundleDeployment", "core.rukpak.io"): {
		"api_paths": ["apis/core.rukpak.io/v1alpha1/"],
		"api": "bundledeployments",
		"namespaced": False,
	},
	("Bundle", "core.rukpak.io"): {
		"api_paths": ["apis/core.rukpak.io/v1alpha1/"],
		"api": "bundles",
		"namespaced": False,
	},
	# criresmgr.intel.com
	("Adjustment", "criresmgr.intel.com"): {
		"api_paths": ["apis/criresmgr.intel.com/v1alpha1/"],
		"api": "adjustments",
	},
	# cr.kanister.io
	("ActionSet", "cr.kanister.io"): {
		"api_paths": ["apis/cr.kanister.io/v1alpha1/"],
		"api": "actionsets",
	},
	("Blueprint", "cr.kanister.io"): {
		"api_paths": ["apis/cr.kanister.io/v1alpha1/"],
		"api": "blueprints",
	},
	("Profile", "cr.kanister.io"): {
		"api_paths": ["apis/cr.kanister.io/v1alpha1/"],
		"api": "profiles",
	},
	# crd.antrea.io
	("AntreaAgentInfo", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1beta1/"],
		"api": "antreaagentinfos",
		"namespaced": False,
	},
	("AntreaControllerInfo", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1beta1/"],
		"api": "antreacontrollerinfos",
		"namespaced": False,
	},
	("ClusterGroup", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha3/", "apis/crd.antrea.io/v1alpha2/"],
		"api": "clustergroups",
		"namespaced": False,
	},
	("ClusterNetworkPolicy", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha1/"],
		"api": "clusternetworkpolicies",
		"namespaced": False,
	},
	("Egress", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha2/"],
		"api": "egresses",
		"namespaced": False,
	},
	("ExternalEntity", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha2/"],
		"api": "externalentities",
	},
	("ExternalIPPool", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha2/"],
		"api": "externalippools",
		"namespaced": False,
	},
	("ExternalNode", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha1/"],
		"api": "externalnodes",
	},
	("Group", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha3/"],
		"api": "groups",
	},
	("IPPool", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha2/"],
		"api": "ippools",
		"namespaced": False,
	},
	("NetworkPolicy", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha1/"],
		"api": "networkpolicies",
	},
	("SupportBundleCollection", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha1/"],
		"api": "supportbundlecollections",
		"namespaced": False,
	},
	("Tier", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha1/"],
		"api": "tiers",
		"namespaced": False,
	},
	("Traceflow", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha1/"],
		"api": "traceflows",
		"namespaced": False,
	},
	("TrafficControl", "crd.antrea.io"): {
		"api_paths": ["apis/crd.antrea.io/v1alpha2/"],
		"api": "trafficcontrols",
		"namespaced": False,
	},
	# crd.projectcalico.org
	("BGPConfiguration", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "bgpconfigurations",
		"namespaced": False,
	},
	("BGPFilter", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v3/"],
		"api": "bgpfilters",
		"namespaced": False,
	},
	("BGPPeer", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "bgppeers",
		"namespaced": False,
	},
	("BlockAffinity", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "blockaffinities",
		"namespaced": False,
	},
	("CalicoNodeStatus", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "caliconodestatuses",
		"namespaced": False,
	},
	("ClusterInformation", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "clusterinformations",
		"namespaced": False,
	},
	("FelixConfiguration", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "felixconfigurations",
		"namespaced": False,
	},
	("GlobalNetworkPolicy", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "globalnetworkpolicies",
		"namespaced": False,
	},
	("GlobalNetworkSet", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "globalnetworksets",
		"namespaced": False,
	},
	("HostEndpoint", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "hostendpoints",
		"namespaced": False,
	},
	("IPAMBlock", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "ipamblocks",
		"namespaced": False,
	},
	("IPAMConfig", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "ipamconfigs",
		"namespaced": False,
	},
	("IPAMHandle", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "ipamhandles",
		"namespaced": False,
	},
	("IPPool", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "ippools",
		"namespaced": False,
	},
	("IPReservation", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "ipreservations",
		"namespaced": False,
	},
	("KubeControllersConfiguration", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "kubecontrollersconfigurations",
		"namespaced": False,
	},
	("NetworkPolicy", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "networkpolicies",
	},
	("NetworkSet", "crd.projectcalico.org"): {
		"api_paths": ["apis/crd.projectcalico.org/v1/"],
		"api": "networksets",
	},
	# dapr.io
	("Component", "dapr.io"): {
		"api_paths": ["apis/dapr.io/v1alpha1/"],
		"api": "components",
	},
	("Configuration", "dapr.io"): {
		"api_paths": ["apis/dapr.io/v1alpha1/"],
		"api": "configurations",
	},
	("Resiliency", "dapr.io"): {
		"api_paths": ["apis/dapr.io/v1alpha1/"],
		"api": "resiliencies",
	},
	("Subscription", "dapr.io"): {
		"api_paths": ["apis/dapr.io/v2alpha1/"],
		"api": "subscriptions",
	},
	# deviceplugin.intel.com
	("DlbDevicePlugin", "deviceplugin.intel.com"): {
		"api_paths": ["apis/deviceplugin.intel.com/v1/"],
		"api": "dlbdeviceplugins",
		"namespaced": False,
	},
	("DsaDevicePlugin", "deviceplugin.intel.com"): {
		"api_paths": ["apis/deviceplugin.intel.com/v1/"],
		"api": "dsadeviceplugins",
		"namespaced": False,
	},
	("FpgaDevicePlugin", "deviceplugin.intel.com"): {
		"api_paths": ["apis/deviceplugin.intel.com/v1/"],
		"api": "fpgadeviceplugins",
		"namespaced": False,
	},
	("GpuDevicePlugin", "deviceplugin.intel.com"): {
		"api_paths": ["apis/deviceplugin.intel.com/v1/"],
		"api": "gpudeviceplugins",
		"namespaced": False,
	},
	("IaaDevicePlugin", "deviceplugin.intel.com"): {
		"api_paths": ["apis/deviceplugin.intel.com/v1/"],
		"api": "iaadeviceplugins",
		"namespaced": False,
	},
	("QatDevicePlugin", "deviceplugin.intel.com"): {
		"api_paths": ["apis/deviceplugin.intel.com/v1/"],
		"api": "qatdeviceplugins",
		"namespaced": False,
	},
	("SgxDevicePlugin", "deviceplugin.intel.com"): {
		"api_paths": ["apis/deviceplugin.intel.com/v1/"],
		"api": "sgxdeviceplugins",
		"namespaced": False,
	},
	# dex.coreos.com
	("AuthCode", "dex.coreos.com"): {
		"api_paths": ["apis/dex.coreos.com/v1/"],
		"api": "authcodes",
	},
	("AuthRequest", "dex.coreos.com"): {
		"api_paths": ["apis/dex.coreos.com/v1/"],
		"api": "authrequests",
	},
	("Connector", "dex.coreos.com"): {
		"api_paths": ["apis/dex.coreos.com/v1/"],
		"api": "connectors",
	},
	("OAuth2Client", "dex.coreos.com"): {
		"api_paths": ["apis/dex.coreos.com/v1/"],
		"api": "oauth2clients",
	},
	("OfflineSessions", "dex.coreos.com"): {
		"api_paths": ["apis/dex.coreos.com/v1/"],
		"api": "offlinesessionses",
	},
	("Password", "dex.coreos.com"): {
		"api_paths": ["apis/dex.coreos.com/v1/"],
		"api": "passwords",
	},
	("RefreshToken", "dex.coreos.com"): {
		"api_paths": ["apis/dex.coreos.com/v1/"],
		"api": "refreshtokens",
	},
	("SigningKey", "dex.coreos.com"): {
		"api_paths": ["apis/dex.coreos.com/v1/"],
		"api": "signingkeies",
	},
	# dist.kio.kasten.io
	("Bootstrap", "dist.kio.kasten.io"): {
		"api_paths": ["apis/dist.kio.kasten.io/v1alpha1/"],
		"api": "bootstraps",
	},
	("Cluster", "dist.kio.kasten.io"): {
		"api_paths": ["apis/dist.kio.kasten.io/v1alpha1/"],
		"api": "clusters",
	},
	("Distribution", "dist.kio.kasten.io"): {
		"api_paths": ["apis/dist.kio.kasten.io/v1alpha1/"],
		"api": "distributions",
	},
	# etcd.database.coreos.com
	("EtcdCluster", "etcd.database.coreos.com"): {
		"api_paths": ["apis/etcd.database.coreos.com/v1beta2/"],
		"api": "etcdclusters",
	},
	# expansion.gatekeeper.sh
	("ExpansionTemplate", "expansion.gatekeeper.sh"): {
		"api_paths": ["apis/expansion.gatekeeper.sh/v1alpha1/"],
		"api": "expansiontemplate",
		"namespaced": False,
	},
	# export.kubevirt.io
	("VirtualMachineExport", "export.kubevirt.io"): {
		"api_paths": ["apis/export.kubevirt.io/v1alpha1/"],
		"api": "virtualmachineexports",
	},
	# extensions.istio.io
	("WasmPlugin", "extensions.istio.io"): {
		"api_paths": ["apis/install.istio.io/v1alpha1/"],
		"api": "wasmplugins",
	},
	# externaldata.gatekeeper.sh
	("Provider", "externaldata.gatekeeper.sh"): {
		"api_paths": ["apis/externaldata.gatekeeper.sh/v1beta1/"],
		"api": "providers",
		"namespaced": False,
	},
	# eventing.knative.dev
	("Broker", "eventing.knative.dev"): {
		"api_paths": ["apis/eventing.knative.dev/v1/", "apis/eventing.knative.dev/v1beta1/"],
		"api": "brokers",
	},
	("EventType", "eventing.knative.dev"): {
		"api_paths": ["apis/eventing.knative.dev/v1/", "apis/eventing.knative.dev/v1beta1/"],
		"api": "eventtypes",
	},
	("Trigger", "eventing.knative.dev"): {
		"api_paths": ["apis/eventing.knative.dev/v1/", "apis/eventing.knative.dev/v1beta1/"],
		"api": "triggers",
	},
	# flavor.kubevirt.io
	("VirtualMachineClusterFlavor", "flavor.kubevirt.io"): {
		"api_paths": ["apis/flavor.kubevirt.io/v1alpha1/"],
		"api": "virtualmachineclusterflavors",
		"namespaced": False,
	},
	("VirtualMachineFlavor", "flavor.kubevirt.io"): {
		"api_paths": ["apis/flavor.kubevirt.io/v1alpha1/"],
		"api": "virtualmachineflavors",
	},
	# flows.knative.dev
	("Parallel", "flows.knative.dev"): {
		"api_paths": ["apis/flows.knative.dev/v1/"],
		"api": "parallels",
	},
	("Sequence", "flows.knative.dev"): {
		"api_paths": ["apis/flows.knative.dev/v1/"],
		"api": "sequences",
	},
	# forecastle.stakater.com
	("ForecastleApp", "forecastle.stakater.com"): {
		"api_paths": ["apis/forecastle.stakater.com/v1alpha1/"],
		"api": "forecastleapps",
	},
	# fpga.intel.com
	("AcceleratorFunction", "fpga.intel.com"): {
		"api_paths": ["apis/fpga.intel.com/v2/"],
		"api": "acceleratorfunctions",
	},
	("FpgaRegion", "fpga.intel.com"): {
		"api_paths": ["apis/fpga.intel.com/v2/"],
		"api": "fpgaregions",
	},
	# gateway.networking.k8s.io
	("ReferenceGrant", "gateway.networking.k8s.io"): {
		"api_paths": ["apis/gateway.networking.k8s.io/v1alpha2/"],
		"api": "referencegrants",
	},
	("GatewayClass", "gateway.networking.k8s.io"): {
		"api_paths": ["apis/gateway.networking.k8s.io/v1beta1/"],
		"api": "gatewayclasses",
		"namespaced": False,
	},
	("Gateway", "gateway.networking.k8s.io"): {
		"api_paths": ["apis/gateway.networking.k8s.io/v1beta1/"],
		"api": "gateways",
	},
	("HTTPRoute", "gateway.networking.k8s.io"): {
		"api_paths": ["apis/gateway.networking.k8s.io/v1beta1/"],
		"api": "httproutes",
	},
	# gpu.resource.intel.com
	("DeviceClassParameters", "gpu.resource.intel.com"): {
		"api_paths": ["apis/gpu.resource.intel.com/v1alpha2/"],
		"api": "deviceclassparameters",
		"namespaced": False,
	},
	("GpuAllocationState", "gpu.resource.intel.com"): {
		"api_paths": ["apis/gpu.resource.intel.com/v1alpha2/"],
		"api": "gpuallocationstates",
	},
	("GpuClaimParameters", "gpu.resource.intel.com"): {
		"api_paths": ["apis/gpu.resource.intel.com/v1alpha2/"],
		"api": "gpuclaimparameters",
	},
	("GpuClassParameters", "gpu.resource.intel.com"): {
		"api_paths": ["apis/gpu.resource.intel.com/v1alpha2/"],
		"api": "gpuclassparameters",
		"namespaced": False,
	},
	# grafana.integreatly.org
	("GrafanaDashboard", "grafana.integreatly.org"): {
		"api_paths": ["apis/grafana.integreatly.org/v1beta1/"],
		"api": "grafanadashboards",
	},
	("GrafanaDatasource", "grafana.integreatly.org"): {
		"api_paths": ["apis/grafana.integreatly.org/v1beta1/"],
		"api": "grafanadatasources",
	},
	("GrafanaFolder", "grafana.integreatly.org"): {
		"api_paths": ["apis/grafana.integreatly.org/v1beta1/"],
		"api": "grafanafolders",
	},
	("Grafana", "grafana.integreatly.org"): {
		"api_paths": ["apis/grafana.integreatly.org/v1beta1/"],
		"api": "grafanas",
	},
	# helm.cattle.io
	("HelmChartConfig", "helm.cattle.io"): {
		"api_paths": ["apis/helm.cattle.io/v1/"],
		"api": "helmchartconfigs",
	},
	("HelmChart", "helm.cattle.io"): {
		"api_paths": ["apis/helm.cattle.io/v1/"],
		"api": "helmcharts",
	},
	# helm.openshift.io
	("HelmChartRepository", "helm.openshift.io"): {
		"api_paths": ["apis/helm.openshift.io/v1beta1/"],
		"api": "helmchartrepositories",
		"namespaced": False,
	},
	("ProjectHelmChartRepository", "helm.openshift.io"): {
		"api_paths": ["apis/helm.openshift.io/v1beta1/"],
		"api": "projecthelmchartrepositories",
	},
	# image.openshift.io
	("Image", "image.openshift.io"): {
		"api_paths": ["apis/image.openshift.io/v1/"],
		"api": "images",
		"namespaced": False,
	},
	("ImageStream", "image.openshift.io"): {
		"api_paths": ["apis/image.openshift.io/v1/"],
		"api": "imagestreams",
	},
	("ImageStreamTag", "image.openshift.io"): {
		"api_paths": ["apis/image.openshift.io/v1/"],
		"api": "imagestreamtags",
	},
	("ImageTag", "image.openshift.io"): {
		"api_paths": ["apis/image.openshift.io/v1/"],
		"api": "imagetags",
	},
	# imageregistry.operator.openshift.io
	("Config", "imageregistry.operator.openshift.io"): {
		"api_paths": ["apis/imageregistry.operator.openshift.io/v1/"],
		"api": "configs",
		"namespaced": False,
	},
	("ImagePruner", "imageregistry.operator.openshift.io"): {
		"api_paths": ["apis/imageregistry.operator.openshift.io/v1/"],
		"api": "imagepruners",
		"namespaced": False,
	},
	# infrastructure.cluster.x-k8s.io
	("AWSClusterControllerIdentity", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "awsclustercontrolleridentities",
		"namespaced": False,
	},
	("AWSClusterRoleIdentity", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "awsclusterroleidentities",
		"namespaced": False,
	},
	("AWSCluster", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "awsclusters",
	},
	("AWSClusterStaticIdentity", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "awsclusterstaticidentities",
		"namespaced": False,
	},
	("AWSClusterTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "awsclustertemplates",
	},
	("AWSFargateProfile", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "awsfargateprofiles",
	},
	("AWSMachinePool", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "awsmachinepools",
	},
	("AWSMachine", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "awsmachines",
	},
	("AWSMachineTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "awsmachinetemplates",
	},
	("AWSManagedCluster", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "awsmanagedclusters",
	},
	("AWSManagedMachinePool", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "awsmanagedmachinepools",
	},
	("AzureClusterIdentity", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "azureclusteridentities",
	},
	("AzureCluster", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "azureclusters",
	},
	("AzureClusterTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "azureclustertemplates",
	},
	("AzureMachinePoolMachine", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "azuremachinepoolmachines",
	},
	("AzureMachinePool", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "azuremachinepools",
	},
	("AzureMachine", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "azuremachines",
	},
	("AzureMachineTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "azuremachinetemplates",
	},
	("AzureManagedCluster", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "azuremanagedclusters",
	},
	("AzureManagedControlPlane", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "azuremanagedcontrolplanes",
	},
	("AzureManagedMachinePool", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "azuremanagedmachinepools",
	},
	("GCPCluster", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "gcpclusters",
	},
	("GCPClusterTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "gcpclustertemplates",
	},
	("GCPMachine", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "gcpmachines",
	},
	("GCPMachineTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "gcpmachinetemplates",
	},
	("GCPManagedCluster", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "gcpmanagedclusters",
	},
	("GCPManagedControlPlane", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "gcpmanagedcontrolplanes",
	},
	("GCPManagedMachinePool", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "gcpmanagedmachinepools",
	},
	("IBMPowerVSCluster", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "ibmpowervsclusters",
	},
	("IBMPowerVSClusterTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "ibmpowervsclustertemplates",
	},
	("IBMPowerVSImage", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "ibmpowervsimages",
	},
	("IBMPowerVSMachine", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "ibmpowervsmachines",
	},
	("IBMPowerVSMachineTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "ibmpowervsmachinetemplates",
	},
	("IBMVPCCluster", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "ibmvpcclusters",
	},
	("IBMVPCMachine", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "ibmvpcmachines",
	},
	("IBMVPCMachineTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta2/"],
		"api": "ibmvpcmachinetemplates",
	},
	("Metal3Remediation", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "metal3remediations",
	},
	("Metal3RemediationTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1beta1/"],
		"api": "metal3remediationtemplates",
	},
	("OpenStackCluster", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1alpha4/"],
		"api": "openstackclusters",
	},
	("OpenStackClusterTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1alpha4/"],
		"api": "openstackclustertemplates",
	},
	("OpenStackMachine", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1alpha4/"],
		"api": "openstackmachines",
	},
	("OpenStackMachineTemplate", "infrastructure.cluster.x-k8s.io"): {
		"api_paths": ["apis/infrastructure.cluster.x-k8s.io/v1alpha4/"],
		"api": "openstackmachinetemplates",
	},
	# ingress.operator.openshift.io
	("DNSRecord", "ingress.operator.openshift.io"): {
		"api_paths": ["apis/ingress.operator.openshift.io/v1/"],
		"api": "dnsrecords",
	},
	# insights.openshift.io
	("DataGather", "insights.openshift.io"): {
		"api_paths": ["apis/insights.openshift.io/v1alpha1/"],
		"api": "datagathers",
		"namespaced": False,
	},
	# installer.kubesphere.io/v1alpha1
	("ClusterConfiguration", "installer.kubesphere.io"): {
		"api_paths": ["apis/installer.kubesphere.io/v1alpha1/"],
		"api": "clusterconfigurations",
	},
	# install.istio.io
	("IstioOperator", "install.istio.io"): {
		"api_paths": ["apis/install.istio.io/v1alpha1/"],
		"api": "istiooperators",
	},
	# instancetype.kubevirt.io
	("VirtualMachineClusterInstancetype", "instancetype.kubevirt.io"): {
		"api_paths": ["apis/instancetype.kubevirt.io/v1alpha2/"],
		"api": "virtualmachineclusterinstancetypes",
		"namespaced": False,
	},
	("VirtualMachineClusterPreference", "instancetype.kubevirt.io"): {
		"api_paths": ["apis/instancetype.kubevirt.io/v1alpha2/"],
		"api": "virtualmachineclusterpreferences",
		"namespaced": False,
	},
	("VirtualMachineInstancetype", "instancetype.kubevirt.io"): {
		"api_paths": ["apis/instancetype.kubevirt.io/v1alpha2/"],
		"api": "virtualmachineinstancetypes",
	},
	("VirtualMachinePreference", "instancetype.kubevirt.io"): {
		"api_paths": ["apis/instancetype.kubevirt.io/v1alpha2/"],
		"api": "virtualmachinepreferences",
	},
	# ipam.cluster.x-k8s.io
	("IPAddressClaim", "ipam.cluster.x-k8s.io"): {
		"api_paths": ["apis/ipam.cluster.x-k8s.io/v1alpha1/"],
		"api": "ipaddressclaims",
	},
	("IPAddress", "ipam.cluster.x-k8s.io"): {
		"api_paths": ["apis/ipam.cluster.x-k8s.io/v1alpha1/"],
		"api": "ipaddresses",
	},
	# jaegertracing.io
	("Jaeger", "jaegertracing.io"): {
		"api_paths": ["apis/jaegertracing.io/v1/"],
		"api": "jaegers",
	},
	# k3s.cattle.io
	("Addon", "k3s.cattle.io"): {
		"api_paths": ["apis/k3s.cattle.io/v1/"],
		"api": "addons",
	},
	# k8s.cni.cncf.io
	("NetworkAttachmentDefinition", "k8s.cni.cncf.io"): {
		"api_paths": ["apis/k8s.cni.cncf.io/v1/"],
		"api": "network-attachment-definitions",
	},
	# k8s.otterize.com
	("ClientIntents", "k8s.otterize.com"): {
		"api_paths": ["apis/k8s.otterize.com/v1alpha2/"],
		"api": "clientintents",
	},
	("KafkaServerConfig", "k8s.otterize.com"): {
		"api_paths": ["apis/k8s.otterize.com/v1alpha2/"],
		"api": "kafkaserverconfigs",
	},
	# kamaji.clastix.io
	("DataStore", "kamaji.clastix.io"): {
		"api_paths": ["apis/kamaji.clastix.io/v1alpha1/"],
		"api": "datastores",
		"namespaced": False,
	},
	("TenantControlPlane", "kamaji.clastix.io"): {
		"api_paths": ["apis/kamaji.clastix.io/v1alpha1/"],
		"api": "tenantcontrolplanes",
	},
	# keda.sh
	("ClusterTriggerAuthentication", "keda.sh"): {
		"api_paths": ["apis/keda.sh/v1alpha1/"],
		"api": "clustertriggerauthentications",
	},
	("ScaledJob", "keda.sh"): {
		"api_paths": ["apis/keda.sh/v1alpha1/"],
		"api": "scaledjobs",
	},
	("ScaledObject", "keda.sh"): {
		"api_paths": ["apis/keda.sh/v1alpha1/"],
		"api": "scaledobjects",
	},
	("TriggerAuthentication", "keda.sh"): {
		"api_paths": ["apis/keda.sh/v1alpha1/"],
		"api": "triggerauthentications",
	},
	# kepler.system.sustainable.computing.io
	("Kepler", "kepler.system.sustainable.computing.io"): {
		"api_paths": ["apis/kepler.system.sustainable.computing.io/v1alpha1/"],
		"api": "keplers",
		"namespaced": False,
	},
	# kilo.squat.ai
	("Peer", "kilo.squat.ai"): {
		"api_paths": ["apis/kilo.squat.ai/v1alpha1/"],
		"api": "peers",
		"namespaced": False,
	},
	# kubeapps.com
	("AppRepository", "kubeapps.com"): {
		"api_paths": ["apis/kubeapps.com/v1alpha1/"],
		"api": "apprepositories",
	},
	# kubeflow.org
	("Experiment", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1beta1/"],
		"api": "experiments",
	},
	("MPIJob", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1alpha2/", "apis/kubeflow.org/v1/"],
		"api": "mpijobs",
	},
	("MXJob", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1/"],
		"api": "mxjobs",
	},
	("Notebook", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1/"],
		"api": "notebooks",
	},
	("PaddleJob", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1/"],
		"api": "paddlejobs",
	},
	("PodDefault", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1alpha1/"],
		"api": "poddefaults",
	},
	("Profile", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1beta1/", "apis/kubeflow.org/v1/"],
		"api": "profiles",
		"namespaced": False,
	},
	("PyTorchJob", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1/"],
		"api": "pytorchjobs",
	},
	("ScheduledWorkflow", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1beta1/"],
		"api": "scheduledworkflow",
	},
	("Suggestion", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1alpha3/", "apis/kubeflow.org/v1beta1/"],
		"api": "suggestions",
	},
	("TFJob", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1/"],
		"api": "tfjobs",
	},
	("Trial", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1alpha3/", "apis/kubeflow.org/v1beta1/"],
		"api": "trials",
	},
	("Viewer", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1alpha1/", "apis/kubeflow.org/v1beta1/"],
		"api": "viewers",
	},
	# kubeovn.io
	("HtbQos", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "htbqoses",
		"namespaced": False,
	},
	("IP", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "ips",
		"namespaced": False,
	},
	("IPPool", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "ippools",
		"namespaced": False,
	},
	("IptablesDnatRule", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "iptables-dnat-rules",
		"namespaced": False,
	},
	("IptablesEIP", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "iptables-eips",
		"namespaced": False,
	},
	("IptablesFIPRule", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "iptables-fip-rules",
		"namespaced": False,
	},
	("IptablesSnatRule", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "iptables-snat-rules",
		"namespaced": False,
	},
	("OvnDnatRule", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "ovn-dnat-rules",
		"namespaced": False,
	},
	("OvnEip", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "ovn-eips",
		"namespaced": False,
	},
	("OvnFip", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "ovn-fips",
		"namespaced": False,
	},
	("OvnSnatRule", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "ovn-snat-rules",
		"namespaced": False,
	},
	("ProviderNetwork", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "provider-networks",
		"namespaced": False,
	},
	("QoSPolicy", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "qos-policies",
		"namespaced": False,
	},
	("SecurityGroup", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "security-groups",
		"namespaced": False,
	},
	("Subnet", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "subnets",
		"namespaced": False,
	},
	("SwitchLBRule", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "switch-lb-rules",
		"namespaced": False,
	},
	("Vip", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "vips",
		"namespaced": False,
	},
	("Vlan", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "vlans",
		"namespaced": False,
	},
	("Vpc", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "vpcs",
		"namespaced": False,
	},
	("VpcDns", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "vpc-dnses",
		"namespaced": False,
	},
	("VpcNatGateway", "kubeovn.io"): {
		"api_paths": ["apis/kubeovn.io/v1/"],
		"api": "vpc-nat-gateways",
		"namespaced": False,
	},
	# kubevirt.io
	("KubeVirt", "kubevirt.io"): {
		"api_paths": ["apis/kubevirt.io/v1/"],
		"api": "kubevirts",
	},
	("VirtualMachineInstanceMigration", "kubevirt.io"): {
		"api_paths": ["apis/kubevirt.io/v1/"],
		"api": "virtualmachineinstancemigrations",
	},
	("VirtualMachineInstancePreset", "kubevirt.io"): {
		"api_paths": ["apis/kubevirt.io/v1/"],
		"api": "virtualmachineinstancepresets",
		"deprecated": "kubevirt/v1",
		"unavailable": "kubevirt/v2",
	},
	("VirtualMachineInstanceReplicaSet", "kubevirt.io"): {
		"api_paths": ["apis/kubevirt.io/v1/"],
		"api": "virtualmachineinstancereplicasets",
	},
	("VirtualMachineInstance", "kubevirt.io"): {
		"api_paths": ["apis/kubevirt.io/v1/"],
		"api": "virtualmachineinstances",
	},
	("VirtualMachine", "kubevirt.io"): {
		"api_paths": ["apis/kubevirt.io/v1/"],
		"api": "virtualmachines",
	},
	# kueue.x-k8s.io
	("ClusterQueue", "kueue.x-k8s.io"): {
		"api_paths": ["apis/kueue.x-k8s.io/v1beta1/"],
		"api": "clusterqueues",
		"namespaced": False,
	},
	("ResourceFlavor", "kueue.x-k8s.io"): {
		"api_paths": ["apis/kueue.x-k8s.io/v1beta1/"],
		"api": "resourceflavors",
		"namespaced": False,
	},
	("LocalQueue", "kueue.x-k8s.io"): {
		"api_paths": ["apis/kueue.x-k8s.io/v1beta1/"],
		"api": "localqueues",
	},
	("Workload", "kueue.x-k8s.io"): {
		"api_paths": ["apis/kueue.x-k8s.io/v1beta1/"],
		"api": "workloads",
	},
	# kuik.enix.io
	("CachedImage", "kuik.enix.io"): {
		"api_paths": ["apis/kuik.enix.io/v1alpha1/"],
		"api": "cachedimages",
		"namespaced": False,
	},
	# kyverno.io
	("AdmissionReport", "kyverno.io"): {
		"api_paths": ["apis/kyverno.io/v1alpha2/"],
		"api": "admissionreports",
	},
	("BackgroundScanReport", "kyverno.io"): {
		"api_paths": ["apis/kyverno.io/v1alpha2/"],
		"api": "backgroundscanreports",
	},
	("CleanupPolicy", "kyverno.io"): {
		"api_paths": ["apis/kyverno.io/v2alpha1/"],
		"api": "cleanuppolicies",
	},
	("ClusterAdmissionReport", "kyverno.io"): {
		"api_paths": ["apis/kyverno.io/v1alpha2/"],
		"api": "clusteradmissionreports",
		"namespaced": False,
	},
	("ClusterBackgroundScanReport", "kyverno.io"): {
		"api_paths": ["apis/kyverno.io/v1alpha2/"],
		"api": "clusterbackgroundscanreports",
		"namespaced": False,
	},
	("ClusterCleanupPolicy", "kyverno.io"): {
		"api_paths": ["apis/kyverno.io/v2alpha1/"],
		"api": "clustercleanuppolicies",
		"namespaced": False,
	},
	("ClusterPolicy", "kyverno.io"): {
		"api_paths": ["apis/kyverno.io/v1/"],
		"api": "clusterpolicies",
		"namespaced": False,
	},
	("GenerateRequest", "kyverno.io"): {
		"api_paths": ["apis/kyverno.io/v1/"],
		"api": "generaterequests",
	},
	("Policy", "kyverno.io"): {
		"api_paths": ["apis/kyverno.io/v1/"],
		"api": "policies",
	},
	("PolicyException", "kyverno.io"): {
		"api_paths": ["apis/kyverno.io/v2alpha1/"],
		"api": "policyexceptions",
	},
	("UpdateRequest", "kyverno.io"): {
		"api_paths": ["apis/kyverno.io/v1beta1/"],
		"api": "updaterequests",
	},
	# linkerd.io
	("ServiceProfile", "linkerd.io"): {
		"api_paths": ["apis/linkerd.io/v1alpha2/"],
		"api": "serviceprofiles",
	},
	# logging-extensions.banzaicloud.io
	("EventTailer", "logging-extensions.banzaicloud.io"): {
		"api_paths": ["apis/logging-extensions.banzaicloud.io/v1alpha1/"],
		"api": "eventtailers",
		"namespaced": False,
	},
	("HostTailer", "logging-extensions.banzaicloud.io"): {
		"api_paths": ["apis/logging-extensions.banzaicloud.io/v1alpha1/"],
		"api": "hosttailers",
	},
	# logging.banzaicloud.io
	("ClusterFlow", "logging.banzaicloud.io"): {
		"api_paths": ["apis/logging.banzaicloud.io/v1beta1/"],
		"api": "clusterflows",
	},
	("ClusterOutput", "logging.banzaicloud.io"): {
		"api_paths": ["apis/logging.banzaicloud.io/v1beta1/"],
		"api": "clusteroutputs",
	},
	("Flow", "logging.banzaicloud.io"): {
		"api_paths": ["apis/logging.banzaicloud.io/v1beta1/"],
		"api": "flows",
	},
	("Logging", "logging.banzaicloud.io"): {
		"api_paths": ["apis/logging.banzaicloud.io/v1beta1/"],
		"api": "loggings",
		"namespaced": False,
	},
	("Output", "logging.banzaicloud.io"): {
		"api_paths": ["apis/logging.banzaicloud.io/v1beta1/"],
		"api": "outputs",
	},
	# machine.openshift.io
	("ControlPlaneMachineSet", "machine.openshift.io"): {
		"api_paths": ["apis/machine.openshift.io/v1/"],
		"api": "controlplanemachinesets",
	},
	("MachineHealthCheck", "machine.openshift.io"): {
		"api_paths": ["apis/machine.openshift.io/v1beta1/"],
		"api": "machinehealthchecks",
	},
	("Machine", "machine.openshift.io"): {
		"api_paths": ["apis/machine.openshift.io/v1beta1/"],
		"api": "machines",
	},
	("MachineSet", "machine.openshift.io"): {
		"api_paths": ["apis/machine.openshift.io/v1beta1/"],
		"api": "machinesets",
	},
	# machineconfiguration.openshift.io
	("ContainerRuntimeConfig", "machineconfiguration.openshift.io"): {
		"api_paths": ["apis/machineconfiguration.openshift.io/v1/"],
		"api": "containerruntimeconfigs",
		"namespaced": False,
	},
	("ControllerConfig", "machineconfiguration.openshift.io"): {
		"api_paths": ["apis/machineconfiguration.openshift.io/v1/"],
		"api": "controllerconfigs",
		"namespaced": False,
	},
	("KubeletConfig", "machineconfiguration.openshift.io"): {
		"api_paths": ["apis/machineconfiguration.openshift.io/v1/"],
		"api": "kubeletconfigs",
		"namespaced": False,
	},
	("MachineConfigPool", "machineconfiguration.openshift.io"): {
		"api_paths": ["apis/machineconfiguration.openshift.io/v1/"],
		"api": "machineconfigpools",
		"namespaced": False,
	},
	("MachineConfig", "machineconfiguration.openshift.io"): {
		"api_paths": ["apis/machineconfiguration.openshift.io/v1/"],
		"api": "machineconfigs",
		"namespaced": False,
	},
	# machinelearning.seldon.io
	("SeldonDeployment", "machinelearning.seldon.io"): {
		"api_paths": ["apis/machinelearning.seldon.io/v1/", "apis/machinelearning.seldon.io/v1alpha3/", "apis/machinelearning.seldon.io/v1alpha2/"],
		"api": "seldondeployments",
	},
	# management.loft.sh
	("Announcement", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "announcements",
		"namespaced": False,
	},
	("App", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "apps",
		"namespaced": False,
	},
	("ClusterAccess", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "clusteraccesses",
		"namespaced": False,
	},
	("ClusterRoleTemplate", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "clusterroletemplates",
		"namespaced": False,
	},
	("Cluster", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "clusters",
		"namespaced": False,
	},
	("Event", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "events",
		"namespaced": False,
	},
	("Feature", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "features",
		"namespaced": False,
	},
	("PolicyViolation", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "policyviolations",
		"namespaced": False,
	},
	("Project", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "projects",
		"namespaced": False,
	},
	("ProjectSecret", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "projectsecrets",
	},
	("SharedSecret", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "sharedsecrets",
	},
	("SpaceConstraint", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "spaceconstraints",
		"namespaced": False,
	},
	("SpaceInstance", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "spaceinstances",
	},
	("SpaceTemplate", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "spacetemplates",
		"namespaced": False,
	},
	("Task", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "tasks",
		"namespaced": False,
	},
	("Team", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "teams",
		"namespaced": False,
	},
	("User", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "users",
		"namespaced": False,
	},
	("VirtualClusterInstance", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "virtualclusterinstances",
	},
	("VirtualClusterTemplate", "management.loft.sh"): {
		"api_paths": ["apis/management.loft.sh/v1/"],
		"api": "virtualclustertemplates",
		"namespaced": False,
	},
	# messaging.knative.dev
	("Channel", "messaging.knative.dev"): {
		"api_paths": ["apis/messaging.knative.dev/v1/"],
		"api": "channels",
	},
	("InMemoryChannel", "messaging.knative.dev"): {
		"api_paths": ["apis/messaging.knative.dev/v1/"],
		"api": "inmemorychannels",
	},
	("Subscription", "messaging.knative.dev"): {
		"api_paths": ["apis/messaging.knative.dev/v1/"],
		"api": "subscriptions",
	},
	# metal3.io
	("BareMetalHost", "metal3.io"): {
		"api_paths": ["apis/metal3.io/v1alpha1/"],
		"api": "baremetalhosts",
	},
	("BMCEventSubscription", "metal3.io"): {
		"api_paths": ["apis/metal3.io/v1alpha1/"],
		"api": "bmceventsubscriptions",
	},
	("FirmwareSchema", "metal3.io"): {
		"api_paths": ["apis/metal3.io/v1alpha1/"],
		"api": "firmwareschemas",
	},
	("HostFirmwareSettings", "metal3.io"): {
		"api_paths": ["apis/metal3.io/v1alpha1/"],
		"api": "hostfirmwaresettings",
	},
	("PreprovisioningImage", "metal3.io"): {
		"api_paths": ["apis/metal3.io/v1alpha1/"],
		"api": "preprovisioningimages",
	},
	("Provisioning", "metal3.io"): {
		"api_paths": ["apis/metal3.io/v1alpha1/"],
		"api": "provisionings",
		"namespaced": False,
	},
	# migration.k8s.io
	("StorageState", "migration.k8s.io"): {
		"api_paths": ["apis/migration.k8s.io/v1alpha1/"],
		"api": "storagestates",
		"namespaced": False,
	},
	("StorageVersionMigration", "migration.k8s.io"): {
		"api_paths": ["apis/migration.k8s.io/v1alpha1/"],
		"api": "storageversionmigrations",
		"namespaced": False,
	},
	# migrations.kubevirt.io
	("MigrationPolicy", "migrations.kubevirt.io"): {
		"api_paths": ["apis/migrations.kubevirt.io/v1alpha1/"],
		"api": "migrationpolicies",
		"namespaced": False,
	},
	# monitoring.coreos.com
	("Alertmanager", "monitoring.coreos.com"): {
		"api_paths": ["apis/monitoring.coreos.com/v1/"],
		"api": "alertmanagers",
	},
	("AlertmanagerConfig", "monitoring.coreos.com"): {
		"api_paths": ["apis/monitoring.coreos.com/v1alpha1/"],
		"api": "alertmanagerconfigs",
	},
	("PodMonitor", "monitoring.coreos.com"): {
		"api_paths": ["apis/monitoring.coreos.com/v1/"],
		"api": "podmonitors",
	},
	("Probe", "monitoring.coreos.com"): {
		"api_paths": ["apis/monitoring.coreos.com/v1/"],
		"api": "probes",
	},
	("Prometheus", "monitoring.coreos.com"): {
		"api_paths": ["apis/monitoring.coreos.com/v1/"],
		"api": "prometheuses",
	},
	("PrometheusAgent", "monitoring.coreos.com"): {
		"api_paths": ["apis/monitoring.coreos.com/v1alpha1/"],
		"api": "prometheusagents",
	},
	("PrometheusRule", "monitoring.coreos.com"): {
		"api_paths": ["apis/monitoring.coreos.com/v1/"],
		"api": "prometheusrules",
	},
	("ScrapeConfig", "monitoring.coreos.com"): {
		"api_paths": ["apis/monitoring.coreos.com/v1alpha1/"],
		"api": "scrapeconfigs",
	},
	("ServiceMonitor", "monitoring.coreos.com"): {
		"api_paths": ["apis/monitoring.coreos.com/v1/"],
		"api": "servicemonitors",
	},
	("ThanosRuler", "monitoring.coreos.com"): {
		"api_paths": ["apis/monitoring.coreos.com/v1/"],
		"api": "thanosrulers",
	},
	# mutations.gatekeeper.sh
	("ModifySet", "mutations.gatekeeper.sh"): {
		"api_paths": ["apis/mutations.gatekeeper.sh/v1/"],
		"api": "modifyset",
		"namespaced": False,
	},
	("Assign", "mutations.gatekeeper.sh"): {
		"api_paths": ["apis/mutations.gatekeeper.sh/v1/"],
		"api": "assign",
		"namespaced": False,
	},
	("AssignMetadata", "mutations.gatekeeper.sh"): {
		"api_paths": ["apis/mutations.gatekeeper.sh/v1/"],
		"api": "assignmetadata",
		"namespaced": False,
	},
	("AssignImage", "mutations.gatekeeper.sh"): {
		"api_paths": ["apis/mutations.gatekeeper.sh/v1alpha1/"],
		"api": "assignimage",
		"namespaced": False,
	},
	# monitoring.openshift.io
	("AlertingRule", "monitoring.openshift.io"): {
		"api_paths": ["apis/monitoring.openshift.io/v1/"],
		"api": "alertingrules",
	},
	("AlertRelabelConfig", "monitoring.openshift.io"): {
		"api_paths": ["apis/monitoring.openshift.io/v1/"],
		"api": "alertrelabelconfigs",
	},
	# network.openshift.io
	("ClusterNetwork", "network.openshift.io"): {
		"api_paths": ["apis/network.openshift.io/v1/"],
		"api": "clusternetworks",
		"namespaced": False,
	},
	("EgressNetworkPolicy", "network.openshift.io"): {
		"api_paths": ["apis/network.openshift.io/v1/"],
		"api": "egressnetworkpolicies",
	},
	("HostSubnet", "network.openshift.io"): {
		"api_paths": ["apis/network.openshift.io/v1/"],
		"api": "hostsubnets",
		"namespaced": False,
	},
	("NetNamespace", "network.openshift.io"): {
		"api_paths": ["apis/network.openshift.io/v1/"],
		"api": "netnamespaces",
		"namespaced": False,
	},
	# network.operator.openshift.io
	("EgressRouter", "network.operator.openshift.io"): {
		"api_paths": ["apis/network.operator.openshift.io/v1/"],
		"api": "egressrouters",
	},
	("OperatorPKI", "network.operator.openshift.io"): {
		"api_paths": ["apis/network.operator.openshift.io/v1/"],
		"api": "operatorpkis",
	},
	# networking.internal.knative.dev
	("Certificate", "networking.internal.knative.dev"): {
		"api_paths": ["apis/networking.internal.knative.dev/v1alpha1/"],
		"api": "certificates",
	},
	("ClusterDomainClaim", "networking.internal.knative.dev"): {
		"api_paths": ["apis/networking.internal.knative.dev/v1alpha1/"],
		"api": "clusterdomainclaims",
		"namespaced": False,
	},
	("Ingress", "networking.internal.knative.dev"): {
		"api_paths": ["apis/networking.internal.knative.dev/v1alpha1/"],
		"api": "ingresses",
	},
	("ServerlessService", "networking.internal.knative.dev"): {
		"api_paths": ["apis/networking.internal.knative.dev/v1alpha1/"],
		"api": "serverlessservices",
	},
	# networking.istio.io
	("DestinationRule", "networking.istio.io"): {
		"api_paths": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
		"api": "destinationrules",
	},
	("EnvoyFilter", "networking.istio.io"): {
		"api_paths": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
		"api": "envoyfilters",
	},
	("Gateway", "networking.istio.io"): {
		"api_paths": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
		"api": "gateways",
	},
	("ProxyConfig", "networking.istio.io"): {
		"api_paths": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
		"api": "proxyconfigs",
	},
	("ServiceEntry", "networking.istio.io"): {
		"api_paths": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
		"api": "serviceentries",
	},
	("Sidecar", "networking.istio.io"): {
		"api_paths": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
		"api": "sidecars",
	},
	("VirtualService", "networking.istio.io"): {
		"api_paths": ["apis/networking.istio.io/v1beta1/", "apis/networking.istio.io/v1alpha3/"],
		"api": "virtualservices",
	},
	("WorkloadEntry", "networking.istio.io"): {
		"api_paths": ["apis/networking.istio.io/v1beta1/"],
		"api": "workloadentries",
	},
	("WorkloadGroup", "networking.istio.io"): {
		"api_paths": ["apis/networking.istio.io/v1alpha3/"],
		"api": "workloadgroups",
	},
	# nfd.k8s-sigs.io
	("NodeFeature", "nfd.k8s-sigs.io"): {
		"api_paths": ["apis/nfd.k8s-sigs.io/v1alpha1/"],
		"api": "nodefeatures",
	},
	("NodeFeatureRule", "nfd.k8s-sigs.io"): {
		"api_paths": ["apis/nfd.k8s-sigs.io/v1alpha1/"],
		"api": "nodefeaturerules",
		"namespaced": False,
	},
	# nodeinfo.volcano.sh
	("Numatopology", "nodeinfo.volcano.sh"): {
		"api_paths": ["apis/nodeinfo.volcano.sh/v1alpha1/"],
		"api": "numatopologies",
	},
	# nvidia.com
	("ClusterPolicy", "nvidia.com"): {
		"api_paths": ["apis/nvidia.com/v1/"],
		"api": "clusterpolicies",
		"namespaced": False,
	},
	# oauth.openshift.io
	("OAuthAccessToken", "oauth.openshift.io"): {
		"api_paths": ["apis/oauth.openshift.io/v1/"],
		"api": "oauthaccesstokens",
		"namespaced": False,
	},
	("OAuthAuthorizeToken", "oauth.openshift.io"): {
		"api_paths": ["apis/oauth.openshift.io/v1/"],
		"api": "oauthauthorizetokens",
		"namespaced": False,
	},
	("OAuthClientAuthorization", "oauth.openshift.io"): {
		"api_paths": ["apis/oauth.openshift.io/v1/"],
		"api": "oauthclientauthorizations",
		"namespaced": False,
	},
	("OAuthClient", "oauth.openshift.io"): {
		"api_paths": ["apis/oauth.openshift.io/v1/"],
		"api": "oauthclients",
		"namespaced": False,
	},
	("UserOAuthAccessToken", "oauth.openshift.io"): {
		"api_paths": ["apis/oauth.openshift.io/v1/"],
		"api": "useroauthaccesstokens",
		"namespaced": False,
	},
	# opentelemetry.io
	("OpenTelemetryCollector", "opentelemetry.io"): {
		"api_paths": ["apis/opentelemetry.io/v1alpha1/"],
		"api": "opentelemetrycollectors",
	},
	# operator.cluster.x-k8s.io
	("BootstrapProvider", "operator.cluster.x-k8s.io"): {
		"api_paths": ["apis/operator.cluster.x-k8s.io/v1alpha1/"],
		"api": "bootstrapproviders",
	},
	("ControlPlaneProvider", "operator.cluster.x-k8s.io"): {
		"api_paths": ["apis/operator.cluster.x-k8s.io/v1alpha1/"],
		"api": "controlplaneproviders",
	},
	("CoreProvider", "operator.cluster.x-k8s.io"): {
		"api_paths": ["apis/operator.cluster.x-k8s.io/v1alpha1/"],
		"api": "coreproviders",
	},
	("InfrastructureProvider", "operator.cluster.x-k8s.io"): {
		"api_paths": ["apis/operator.cluster.x-k8s.io/v1alpha1/"],
		"api": "infrastructureproviders",
	},
	# operator.openshift.io
	("Authentication", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "authentications",
		"namespaced": False,
	},
	("CloudCredential", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "cloudcredentials",
		"namespaced": False,
	},
	("ClusterCSIDriver", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "clustercsidrivers",
		"namespaced": False,
	},
	("Config", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "configs",
		"namespaced": False,
	},
	("Console", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "consoles",
		"namespaced": False,
	},
	("CSISnapshotController", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "csisnapshotcontrollers",
		"namespaced": False,
	},
	("DNS", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "dnses",
		"namespaced": False,
	},
	("Etcd", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "etcds",
		"namespaced": False,
	},
	("EtcdBackup", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1alpha1/"],
		"api": "etcdbackups",
		"namespaced": False,
	},
	("ImageContentSourcePolicy", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1alpha1/"],
		"api": "imagecontentsourcepolicies",
		"namespaced": False,
	},
	("IngressController", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "ingresscontrollers",
	},
	("KubeAPIServer", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "kubeapiservers",
		"namespaced": False,
	},
	("KubeControllerManager", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "kubecontrollermanagers",
		"namespaced": False,
	},
	("KubeScheduler", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "kubeschedulers",
		"namespaced": False,
	},
	("KubeStorageVersionMigrator", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "kubestorageversionmigrators",
		"namespaced": False,
	},
	("Network", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "networks",
		"namespaced": False,
	},
	("OLM", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1alpha1/"],
		"api": "olms",
		"namespaced": False,
	},
	("OpenShiftAPIServer", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "openshiftapiservers",
		"namespaced": False,
	},
	("OpenShiftControllerManager", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "openshiftcontrollermanagers",
		"namespaced": False,
	},
	("ServiceCA", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "servicecas",
		"namespaced": False,
	},
	("Storage", "operator.openshift.io"): {
		"api_paths": ["apis/operator.openshift.io/v1/"],
		"api": "storages",
		"namespaced": False,
	},
	# operator.knative.dev
	("KnativeEventing", "operator.knative.dev"): {
		"api_paths": ["apis/operator.knative.dev/v1beta1/"],
		"api": "knativeeventings",
	},
	("KnativeServing", "operator.knative.dev"): {
		"api_paths": ["apis/operator.knative.dev/v1beta1/"],
		"api": "knativeservings",
	},
	# operator.tigera.io
	("APIServer", "operator.tigera.io"): {
		"api_paths": ["apis/operator.tigera.io/v1/"],
		"api": "apiservers",
		"namespaced": False,
	},
	("ImageSet", "operator.tigera.io"): {
		"api_paths": ["apis/operator.tigera.io/v1/"],
		"api": "imagesets",
		"namespaced": False,
	},
	("Installation", "operator.tigera.io"): {
		"api_paths": ["apis/operator.tigera.io/v1/"],
		"api": "installations",
		"namespaced": False,
	},
	("TigeraStatus", "operator.tigera.io"): {
		"api_paths": ["apis/operator.tigera.io/v1/"],
		"api": "tigerastatuses",
		"namespaced": False,
	},
	# operators.coreos.com
	("CatalogSource", "operators.coreos.com"): {
		"api_paths": ["apis/operators.coreos.com/v1alpha1/"],
		"api": "catalogsources",
	},
	("ClusterServiceVersion", "operators.coreos.com"): {
		"api_paths": ["apis/operators.coreos.com/v1alpha1/"],
		"api": "clusterserviceversions",
	},
	("InstallPlan", "operators.coreos.com"): {
		"api_paths": ["apis/operators.coreos.com/v1alpha1/"],
		"api": "installplans",
	},
	("OLMConfig", "operators.coreos.com"): {
		"api_paths": ["apis/operators.coreos.com/v1/"],
		"api": "olmconfigs",
		"namespaced": False,
	},
	("OperatorCondition", "operators.coreos.com"): {
		"api_paths": ["apis/operators.coreos.com/v2/"],
		"api": "operatorconditions",
	},
	("OperatorGroup", "operators.coreos.com"): {
		"api_paths": ["apis/operators.coreos.com/v1/"],
		"api": "operatorgroups",
	},
	("Operator", "operators.coreos.com"): {
		"api_paths": ["apis/operators.coreos.com/v1/"],
		"api": "operators",
		"namespaced": False,
	},
	("Subscription", "operators.coreos.com"): {
		"api_paths": ["apis/operators.coreos.com/v1alpha1/"],
		"api": "subscriptions",
	},
	# operators.operatorframework.io
	("Operator", "operators.operatorframework.io"): {
		"api_paths": ["apis/operators.operatorframework.io/v1alpha1/"],
		"api": "operators",
		"namespaced": False,
	},
	# packages.operators.coreos.com
	("PackageManifest", "packages.operators.coreos.com"): {
		"api_paths": ["apis/packages.operators.coreos.com/v1/"],
		"api": "packagemanifests",
	},
	# performance.openshift.io
	("PerformanceProfile", "performance.openshift.io"): {
		"api_paths": ["apis/performance.openshift.io/v2/"],
		"api": "performanceprofiles",
		"namespaced": False,
	},
	# platform.openshift.io
	("PlatformOperator", "platform.openshift.io"): {
		"api_paths": ["apis/platform.openshift.io/v1alpha1/"],
		"api": "platformoperators",
		"namespaced": False,
	},
	# policy.kruise.io
	("PodUnavailableBudget", "policy.kruise.io"): {
		"api_paths": ["apis/policy.kruise.io/v1alpha1/"],
		"api": "podunavailablebudgets",
	},
	# policy.linkerd.io
	("AuthorizationPolicy", "policy.linkerd.io"): {
		"api_paths": ["apis/policy.linkerd.io/v1alpha1/"],
		"api": "authorizationpolicies",
	},
	("HTTPRoute", "policy.linkerd.io"): {
		"api_paths": ["apis/policy.linkerd.io/v1alpha1/"],
		"api": "httproutes",
	},
	("MeshTLSAuthentication", "policy.linkerd.io"): {
		"api_paths": ["apis/policy.linkerd.io/v1alpha1/"],
		"api": "meshtlsauthentications",
	},
	("NetworkAuthentication", "policy.linkerd.io"): {
		"api_paths": ["apis/policy.linkerd.io/v1alpha1/"],
		"api": "networkauthentications",
	},
	("ServerAuthorization", "policy.linkerd.io"): {
		"api_paths": ["apis/policy.linkerd.io/v1beta1/"],
		"api": "serverauthorizations",
	},
	("Server", "policy.linkerd.io"): {
		"api_paths": ["apis/policy.linkerd.io/v1beta1/"],
		"api": "servers",
	},
	# pool.kubevirt.io
	("VirtualMachinePool", "pool.kubevirt.io"): {
		"api_paths": ["apis/kubevirt.io/v1alpha1/"],
		"api": "virtualmachinepools",
	},
	# pmem-csi.intel.com
	("PmemCSIDeployment", "pmem-csi.intel.com"): {
		"api_paths": ["apis/pmem-csi.intel.com/v1beta1/"],
		"api": "pmemcsideployments",
	},
	# projectcalico.org
	("Profile", "projectcalico.org"): {
		"api_paths": ["apis/projectcalico.org/v3/"],
		"api": "profiles",
		"namespaced": False,
	},
	# project.openshift.io
	("ProjectRequest", "project.openshift.io"): {
		"api_paths": ["apis/project.openshift.io/v1/"],
		"api": "projectrequests",
		"namespaced": False,
	},
	("Project", "project.openshift.io"): {
		"api_paths": ["apis/project.openshift.io/v1/"],
		"api": "projects",
		"namespaced": False,
	},
	# quota.openshift.io
	("AppliedClusterResourceQuota", "quota.openshift.io"): {
		"api_paths": ["apis/quota.openshift.io/v1/"],
		"api": "appliedclusterresourcequotas",
	},
	("ClusterResourceQuota", "quota.openshift.io"): {
		"api_paths": ["apis/quota.openshift.io/v1/"],
		"api": "clusterresourcequotas",
		"namespaced": False,
	},
	# ray.io
	("RayCluster", "ray.io"): {
		"api_paths": ["apis/ray.io/v1alpha1/"],
		"api": "rayclusters",
	},
	("RayJob", "ray.io"): {
		"api_paths": ["apis/ray.io/v1alpha1/"],
		"api": "rayjobs",
	},
	("RayService", "ray.io"): {
		"api_paths": ["apis/ray.io/v1alpha1/"],
		"api": "rayservices",
	},
	# reaper.cassandra-reaper.io
	("Reaper", "reaper.cassandra-reaper.io"): {
		"api_paths": ["apis/reaper.cassandra-reaper.io/v1alpha1/"],
		"api": "reapers",
	},
	# reporting.kio.kasten.io
	("Report", "reporting.kio.kasten.io"): {
		"api_paths": ["apis/reporting.kio.kasten.io/v1alpha1/"],
		"api": "reports",
	},
	# resolution.tekton.dev
	("ResolutionRequest", "resolution.tekton.dev"): {
		"api_paths": ["apis/resolution.tekton.dev/v1beta1/"],
		"api": "resolutionrequests",
	},
	# resource.k8s.io
	("PodScheduling", "resource.k8s.io"): {
		# => PodSchedulingContext
		"api_paths": ["apis/resource.k8s.io/v1alpha1/"],
		"api": "podschedulings",
	},
	("PodSchedulingContext", "resource.k8s.io"): {
		"api_paths": ["apis/resource.k8s.io/v1alpha2/"],
		"api": "podschedulingcontexts",
	},
	("ResourceClaim", "resource.k8s.io"): {
		"api_paths": ["apis/resource.k8s.io/v1alpha2/", "apis/resource.k8s.io/v1alpha1/"],
		"api": "resourceclaims",
	},
	("ResourceClaimTemplate", "resource.k8s.io"): {
		"api_paths": ["apis/resource.k8s.io/v1alpha2/", "apis/resource.k8s.io/v1alpha1/"],
		"api": "resourceclaimtemplates",
	},
	("ResourceClass", "resource.k8s.io"): {
		"api_paths": ["apis/resource.k8s.io/v1alpha2/", "apis/resource.k8s.io/v1alpha1/"],
		"api": "resourceclasses",
		"namespaced": False,
	},
	# route.openshift.io
	("Route", "route.openshift.io"): {
		"api_paths": ["apis/route.openshift.io/v1/"],
		"api": "routes",
	},
	# runtime.cluster.x-k8s.io
	("ExtensionConfig", "runtime.cluster.x-k8s.io"): {
		"api_paths": ["apis/runtime.cluster.x-k8s.io/v1alpha1/"],
		"api": "extensionconfigs",
		"namespaced": False,
	},
	# samples.operator.openshift.io
	("Config", "samples.operator.openshift.io"): {
		"api_paths": ["apis/samples.operator.openshift.io/v1/"],
		"api": "configs",
	},
	# scheduling.volcano.sh
	("PodGroup", "scheduling.volcano.sh"): {
		"api_paths": ["apis/scheduling.volcano.sh/v1beta1/"],
		"api": "podgroups",
	},
	("Queue", "scheduling.volcano.sh"): {
		"api_paths": ["apis/scheduling.volcano.sh/v1beta1/"],
		"api": "queues",
		"namespaced": False,
	},
	# security.istio.io
	("AuthorizationPolicy", "security.istio.io"): {
		"api_paths": ["apis/security.istio.io/v1beta1/"],
		"api": "authorizationpolicies",
	},
	("PeerAuthentication", "security.istio.io"): {
		"api_paths": ["apis/security.istio.io/v1beta1/"],
		"api": "peerauthentications",
	},
	("RequestAuthentication", "security.istio.io"): {
		"api_paths": ["apis/security.istio.io/v1beta1/"],
		"api": "requestauthentications",
	},
	# security.internal.openshift.io
	("RangeAllocation", "security.internal.openshift.io"): {
		"api_paths": ["apis/security.internal.openshift.io/v1/"],
		"api": "rangeallocations",
		"namespaced": False,
	},
	# security.openshift.io
	("RangeAllocation", "security.openshift.io"): {
		"api_paths": ["apis/security.openshift.io/v1/"],
		"api": "rangeallocations",
		"namespaced": False,
	},
	("SecurityContextConstraints", "security.openshift.io"): {
		"api_paths": ["apis/security.openshift.io/v1/"],
		"api": "securitycontextconstraints",
		"namespaced": False,
	},
	# servicecertsigner.config.openshift.io
	("ServiceCertSignerOperatorConfig", "servicecertsigner.config.openshift.io"): {
		"api_paths": ["apis/servicecertsigner.config.openshift.io/v1alpha1/"],
		"api": "servicecertsigneroperatorconfigs",
		"namespaced": False,
	},
	# serving.knative.dev
	("Configuration", "serving.knative.dev"): {
		"api_paths": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/", "apis/serving.knative.dev/v1alpha2/", "apis/serving.knative.dev/v1alpha1/"],
		"api": "configurations",
	},
	("DomainMapping", "serving.knative.dev"): {
		"api_paths": ["apis/serving.knative.dev/v1alpha1/"],
		"api": "domainmappings",
	},
	("Revision", "serving.knative.dev"): {
		"api_paths": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/", "apis/serving.knative.dev/v1alpha2/", "apis/serving.knative.dev/v1alpha1/"],
		"api": "revisions",
	},
	("Route", "serving.knative.dev"): {
		"api_paths": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/", "apis/serving.knative.dev/v1alpha2/", "apis/serving.knative.dev/v1alpha1/"],
		"api": "routes",
	},
	("Service", "serving.knative.dev"): {
		"api_paths": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/", "apis/serving.knative.dev/v1alpha2/", "apis/serving.knative.dev/v1alpha1/"],
		"api": "services",
	},
	# serving.kubeflow.org
	("InferenceService", "serving.kubeflow.org"): {
		"api_paths": ["apis/serving.kubeflow.org/v1alpha2/", "apis/serving.kubeflow.org/v1beta1/"],
		"api": "inferenceservices",
	},
	("TrainedModel", "serving.kubeflow.org"): {
		"api_paths": ["apis/serving.kubeflow.org/v1alpha2/"],
		"api": "trainedmodels",
	},
	# snapshot.kubevirt.io
	("VirtualMachineRestore", "snapshot.kubevirt.io"): {
		"api_paths": ["apis/snapshot.kubevirt.io/v1alpha1/"],
		"api": "virtualmachinerestores",
	},
	("VirtualMachineSnapshotContent", "snapshot.kubevirt.io"): {
		"api_paths": ["apis/snapshot.kubevirt.io/v1alpha1/"],
		"api": "virtualmachinesnapshotcontents",
	},
	("VirtualMachineSnapshot", "snapshot.kubevirt.io"): {
		"api_paths": ["apis/snapshot.kubevirt.io/v1alpha1/"],
		"api": "virtualmachinesnapshots",
	},
	# sources.knative.dev
	("ApiServerSource", "sources.knative.dev"): {
		"api_paths": ["apis/sources.knative.dev/v1/", "apis/sources.knative.dev/v1beta1/"],
		"api": "apiserversources",
	},
	("ContainerSource", "sources.knative.dev"): {
		"api_paths": ["apis/sources.knative.dev/v1/", "apis/sources.knative.dev/v1beta1/"],
		"api": "containersources",
	},
	("PingSource", "sources.knative.dev"): {
		"api_paths": ["apis/sources.knative.dev/v1/", "apis/sources.knative.dev/v1beta1/"],
		"api": "pingsources",
	},
	("SinkBinding", "sources.knative.dev"): {
		"api_paths": ["apis/sources.knative.dev/v1/", "apis/sources.knative.dev/v1beta1/"],
		"api": "sinkbindings",
	},
	# specs.smi-spec.io
	("HTTPRouteGroup", "specs.smi-spec.io"): {
		"api_paths": ["apis/specs.smi-spec.io/v1alpha4/", "apis/specs.smi-spec.io/v1alpha3/", "apis/specs.smi-spec.io/v1alpha3/"],
		"api": "httproutegroups",
	},
	("TCPRoute", "specs.smi-spec.io"): {
		"api_paths": ["apis/specs.smi-spec.io/v1alpha4/", "apis/specs.smi-spec.io/v1alpha3/"],
		"api": "tcproutes",
	},
	("UDPRoute", "specs.smi-spec.io"): {
		"api_paths": ["apis/specs.smi-spec.io/v1alpha4/"],
		"api": "tcproutes",
	},
	# split.smi-spec.io
	("TrafficSplit", "split.smi-spec.io"): {
		"api_paths": ["apis/split.smi-spec.io/v1alpha4/", "apis/split.smi-spec.io/v1alpha3/", "apis/split.smi-spec.io/v1alpha2/", "apis/split.smi-spec.io/v1alpha1/"],
		"api": "trafficsplits",
	},
	# stats.antrea.io
	("AntreaClusterNetworkPolicyStats", "stats.antrea.io"): {
		"api_paths": ["apis/stats.antrea.io/v1alpha1/"],
		"api": "antreaclusternetworkpolicystats",
		"namespaced": False,
	},
	("AntreaNetworkPolicyStats", "stats.antrea.io"): {
		"api_paths": ["apis/stats.antrea.io/v1alpha1/"],
		"api": "antreanetworkpolicystats",
	},
	("NetworkPolicyStats", "stats.antrea.io"): {
		"api_paths": ["apis/stats.antrea.io/v1alpha1/"],
		"api": "networkpolicystats",
	},
	# status.gatekeeper.sh
	("MutatorPodStatus", "status.gatekeeper.sh"): {
		"api_paths": ["apis/status.gatekeeper.sh/v1beta1/"],
		"api": "mutatorpodstatuses",
	},
	("ConstraintTemplatePodStatus", "status.gatekeeper.sh"): {
		"api_paths": ["apis/status.gatekeeper.sh/v1beta1/"],
		"api": "constrainttemplatepodstatuses",
	},
	("ExpansionTemplatePodStatus", "status.gatekeeper.sh"): {
		"api_paths": ["apis/status.gatekeeper.sh/v1beta1/"],
		"api": "expansiontemplatepodstatuses",
	},
	("ConstraintPodStatus", "status.gatekeeper.sh"): {
		"api_paths": ["apis/status.gatekeeper.sh/v1beta1/"],
		"api": "constraintpodstatuses",
	},
	# storage.loft.sh
	("AccessKey", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "accesskeys",
		"namespaced": False,
	},
	("App", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "apps",
		"namespaced": False,
	},
	("ClusterAccess", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "clusteraccesses",
		"namespaced": False,
	},
	("ClusterQuota", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "clusterquotas",
		"namespaced": False,
	},
	("ClusterRoleTemplate", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "clusterroletemplates",
		"namespaced": False,
	},
	("Cluster", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "clusters",
		"namespaced": False,
	},
	("LocalClusterAccess", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "localclusteraccesses",
		"namespaced": False,
	},
	("LocalTeam", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "localteams",
		"namespaced": False,
	},
	("LocalUser", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "localusers",
		"namespaced": False,
	},
	("Project", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "projects",
		"namespaced": False,
	},
	("SharedSecret", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "sharedsecrets",
	},
	("SpaceConstraint", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "spaceconstraints",
		"namespaced": False,
	},
	("SpaceInstance", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "spaceinstances",
	},
	("SpaceTemplate", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "spacetemplates",
		"namespaced": False,
	},
	("Task", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "tasks",
		"namespaced": False,
	},
	("Team", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "teams",
		"namespaced": False,
	},
	("User", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "users",
		"namespaced": False,
	},
	("VirtualClusterInstance", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "virtualclusterinstances",
	},
	("VirtualCluster", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "virtualclusters",
	},
	("VirtualClusterTemplate", "storage.loft.sh"): {
		"api_paths": ["apis/storage.loft.sh/v1/"],
		"api": "virtualclustertemplates",
		"namespaced": False,
	},
	# system.antrea.io
	("ControllerInfo", "system.antrea.io"): {
		"api_paths": ["apis/system.antrea.io/v1beta1/"],
		"api": "controllerinfos",
		"namespaced": False,
	},
	# tekton.dev
	("ClusterTask", "tekton.dev"): {
		"api_paths": ["apis/tekton.dev/v1beta1/"],
		"api": "clustertasks",
		"namespaced": False,
	},
	("CustomRun", "tekton.dev"): {
		"api_paths": ["apis/tekton.dev/v1beta1/"],
		"api": "customruns",
	},
	("PipelineResource", "tekton.dev"): {
		"api_paths": ["apis/tekton.dev/v1alpha1/"],
		"api": "pipelineresources",
	},
	("PipelineRun", "tekton.dev"): {
		"api_paths": ["apis/tekton.dev/v1beta1/"],
		"api": "pipelineruns",
	},
	("Pipeline", "tekton.dev"): {
		"api_paths": ["apis/tekton.dev/v1beta1/"],
		"api": "pipelines",
	},
	("Run", "tekton.dev"): {
		"api_paths": ["apis/tekton.dev/v1alpha1/"],
		"api": "runs",
	},
	("TaskRun", "tekton.dev"): {
		"api_paths": ["apis/tekton.dev/v1beta1/"],
		"api": "taskruns",
	},
	("Task", "tekton.dev"): {
		"api_paths": ["apis/tekton.dev/v1beta1/"],
		"api": "tasks",
	},
	("VerificationPolicy", "tekton.dev"): {
		"api_paths": ["apis/tekton.dev/v1alpha1/"],
		"api": "verificationpolicies",
	},
	# telemetry.intel.com
	("TASPolicy", "telemetry.intel.com"): {
		"api_paths": ["apis/telemetry.intel.com/v1alpha1/"],
		"api": "taspolicies",
	},
	# telemetry.istio.io
	("Telemetry", "telemetry.istio.io"): {
		"api_paths": ["apis/telemetry.istio.io/v1alpha1/"],
		"api": "telemetries",
	},
	# template.openshift.io
	("BrokerTemplateInstance", "template.openshift.io"): {
		"api_paths": ["apis/template.openshift.io/v1/"],
		"api": "brokertemplateinstances",
		"namespaced": False,
	},
	("TemplateInstance", "template.openshift.io"): {
		"api_paths": ["apis/template.openshift.io/v1/"],
		"api": "templateinstances",
	},
	("Template", "template.openshift.io"): {
		"api_paths": ["apis/template.openshift.io/v1/"],
		"api": "templates",
	},
	# templates.gatekeeper.sh
	("ConstraintTemplate", "templates.gatekeeper.sh"): {
		"api_paths": ["apis/templates.gatekeeper.sh/v1/"],
		"api": "constrainttemplates",
		"namespaced": False,
	},
	# tenancy.kiosk.sh
	("Account", "tenancy.kiosk.sh"): {
		"api_paths": ["apis/tenancy.kiosk.sh/v1alpha1/"],
		"api": "accounts",
		"namespaced": False,
	},
	("Space", "tenancy.kiosk.sh"): {
		"api_paths": ["apis/tenancy.kiosk.sh/v1alpha1/"],
		"api": "spaces",
		"namespaced": False,
	},
	# tensorboard.kubeflow.org
	("Tensorboard", "tensorboard.kubeflow.org"): {
		"api_paths": ["apis/tensorboard.kubeflow.org/v1alpha1/"],
		"api": "tensorboards",
	},
	# tinkerbell.org
	("Hardware", "tinkerbell.org"): {
		"api_paths": ["apis/tinkerbell.org/v1alpha1/"],
		"api": "hardware",
	},
	("Template", "tinkerbell.org"): {
		"api_paths": ["apis/tinkerbell.org/v1alpha1/"],
		"api": "templates",
	},
	("WorkflowData", "tinkerbell.org"): {
		"api_paths": ["apis/tinkerbell.org/v1alpha1/"],
		"api": "workflowdata",
	},
	("Workflow", "tinkerbell.org"): {
		"api_paths": ["apis/tinkerbell.org/v1alpha1/"],
		"api": "workflows",
	},
	# topology.node.k8s.io
	("NodeResourceTopology", "topology.node.k8s.io"): {
		"api_paths": ["apis/topology.node.k8s.io/v1alpha1/"],
		"api": "noderesourcetopologies",
	},
	# traefik.containo.us
	("IngressRoute", "traefik.containo.us"): {
		"api_paths": ["apis/traefik.containo.us/v1alpha1/"],
		"api": "ingressroutes",
	},
	("IngressRouteTCP", "traefik.containo.us"): {
		"api_paths": ["apis/traefik.containo.us/v1alpha1/"],
		"api": "ingressroutetcps",
	},
	("IngressRouteUDP", "traefik.containo.us"): {
		"api_paths": ["apis/traefik.containo.us/v1alpha1/"],
		"api": "ingressrouteudps",
	},
	("Middleware", "traefik.containo.us"): {
		"api_paths": ["apis/traefik.containo.us/v1alpha1/"],
		"api": "middlewares",
	},
	("MiddlewareTCP", "traefik.containo.us"): {
		"api_paths": ["apis/traefik.containo.us/v1alpha1/"],
		"api": "middlewaretcps",
	},
	("ServersTransport", "traefik.containo.us"): {
		"api_paths": ["apis/traefik.containo.us/v1alpha1/"],
		"api": "serverstransports",
	},
	("TLSOption", "traefik.containo.us"): {
		"api_paths": ["apis/traefik.containo.us/v1alpha1/"],
		"api": "tlsoptions",
	},
	("TLSStore", "traefik.containo.us"): {
		"api_paths": ["apis/traefik.containo.us/v1alpha1/"],
		"api": "tlsstores",
	},
	("TraefikService", "traefik.containo.us"): {
		"api_paths": ["apis/traefik.containo.us/v1alpha1/"],
		"api": "traefikservices",
	},
	# triggers.tekton.dev
	("ClusterInterceptor", "triggers.tekton.dev"): {
		"api_paths": ["apis/triggers.tekton.dev/v1alpha1/"],
		"api": "clusterinterceptors",
		"namespaced": False,
	},
	("ClusterTriggerBinding", "triggers.tekton.dev"): {
		"api_paths": ["apis/triggers.tekton.dev/v1beta1/"],
		"api": "clustertriggerbindings",
		"namespaced": False,
	},
	("EventListener", "triggers.tekton.dev"): {
		"api_paths": ["apis/triggers.tekton.dev/v1beta1/"],
		"api": "eventlisteners",
	},
	("Interceptor", "triggers.tekton.dev"): {
		"api_paths": ["apis/triggers.tekton.dev/v1alpha1/"],
		"api": "interceptors",
	},
	("TriggerBinding", "triggers.tekton.dev"): {
		"api_paths": ["apis/triggers.tekton.dev/v1beta1/"],
		"api": "triggerbindings",
	},
	("Trigger", "triggers.tekton.dev"): {
		"api_paths": ["apis/triggers.tekton.dev/v1beta1/"],
		"api": "triggers",
	},
	("TriggerTemplate", "triggers.tekton.dev"): {
		"api_paths": ["apis/triggers.tekton.dev/v1beta1/"],
		"api": "triggertemplates",
	},
	# tuned.openshift.io
	("Profile", "tuned.openshift.io"): {
		"api_paths": ["apis/tuned.openshift.io/v1/"],
		"api": "profiles",
	},
	("Tuned", "tuned.openshift.io"): {
		"api_paths": ["apis/tuned.openshift.io/v1/"],
		"api": "tuneds",
	},
	# upgrade.cattle.io
	("Plan", "upgrade.cattle.io"): {
		"api_paths": ["apis/upgrade.cattle.io/v1/"],
		"api": "plans",
	},
	# user.openshift.io
	("Group", "user.openshift.io"): {
		"api_paths": ["apis/user.openshift.io/v1/"],
		"api": "groups",
		"namespaced": False,
	},
	("Identity", "user.openshift.io"): {
		"api_paths": ["apis/user.openshift.io/v1/"],
		"api": "identities",
		"namespaced": False,
	},
	("User", "user.openshift.io"): {
		"api_paths": ["apis/user.openshift.io/v1/"],
		"api": "users",
		"namespaced": False,
	},
	#("UserIdentityMapping", "user.openshift.io"): {
	#	"api_paths": ["apis/user.openshift.io/v1/"],
	#	"api": "useridentitymappings",
	#	"namespaced": False,
	#},
	# velero.io
	("BackupRepository", "velero.io"): {
		"api_paths": ["apis/velero.io/v1/"],
		"api": "backuprepositories",
	},
	("Backup", "velero.io"): {
		"api_paths": ["apis/velero.io/v1/"],
		"api": "backups",
	},
	("BackupStorageLocation", "velero.io"): {
		"api_paths": ["apis/velero.io/v1/"],
		"api": "backupstoragelocations",
	},
	("DeleteBackupRequest", "velero.io"): {
		"api_paths": ["apis/velero.io/v1/"],
		"api": "deletebackuprequests",
	},
	("DownloadRequest", "velero.io"): {
		"api_paths": ["apis/velero.io/v1/"],
		"api": "downloadrequests",
	},
	("PodVolumeBackup", "velero.io"): {
		"api_paths": ["apis/velero.io/v1/"],
		"api": "podvolumebackups",
	},
	("PodVolumeRestore", "velero.io"): {
		"api_paths": ["apis/velero.io/v1/"],
		"api": "podvolumerestores",
	},
	("Restore", "velero.io"): {
		"api_paths": ["apis/velero.io/v1/"],
		"api": "restores",
	},
	("Schedule", "velero.io"): {
		"api_paths": ["apis/velero.io/v1/"],
		"api": "schedules",
	},
	("ServerStatusRequest", "velero.io"): {
		"api_paths": ["apis/velero.io/v1/"],
		"api": "serverstatusrequests",
	},
	("VolumeSnapshotLocation", "velero.io"): {
		"api_paths": ["apis/velero.io/v1/"],
		"api": "volumesnapshotlocations",
	},
	# virt.virtink.smartx.com
	("VirtualMachine", "virt.virtink.smartx.com"): {
		"api_paths": ["apis/virt.virtink.smartx.com/v1alpha1/"],
		"api": "virtualmachines",
	},
	("VirtualMachineMigration", "virt.virtink.smartx.com"): {
		"api_paths": ["apis/virt.virtink.smartx.com/v1alpha1/"],
		"api": "virtualmachinemigrations",
	},
	# webconsole.openshift.io
	("OpenShiftWebConsoleConfig", "webconsole.openshift.io"): {
		"api_paths": ["apis/webconsole.openshift.io/v1/"],
		"api": "openshiftwebconsoleconfigs",
		"namespaced": False,
	},
	# wgpolicyk8s.io
	("ClusterPolicyReport", "wgpolicyk8s.io"): {
		"api_paths": ["apis/wgpolicyk8s.io/v1alpha2/"],
		"api": "clusterpolicyreports",
		"namespaced": False,
	},
	("PolicyReport", "wgpolicyk8s.io"): {
		"api_paths": ["apis/wgpolicyk8s.io/v1alpha2/"],
		"api": "policyreports",
	},
	# whereabouts.cni.cncf.io
	("IPPool", "whereabouts.cni.cncf.io"): {
		"api_paths": ["apis/whereabouts.cni.cncf.io/v1alpha1/"],
		"api": "ippools",
	},
	("OverlappingRangeIPReservation", "whereabouts.cni.cncf.io"): {
		"api_paths": ["apis/whereabouts.cni.cncf.io/v1alpha1/"],
		"api": "overlappingrangeipreservations",
	},
	# xgboostjob.kubeflow.org
	("XGBoostJob", "kubeflow.org"): {
		"api_paths": ["apis/kubeflow.org/v1/"],
		"api": "xgboostjobs",
	},
}

class KubernetesResourceCache:
	"""
	A class for caching Kubernetes resources
	"""

	updated = False
	resource_cache: Dict = None

	def __init__(self) -> None:
		"""
		Initialize the resource cache
		"""
		self.resource_cache = {}

	def update_resource(self, kind: Tuple[str, str], resource: Dict) -> None:
		"""
		Add or update the cache entry for a resource

			Parameters:
				kind ((str, str)): The kind tuple for the resource
				resource (dict): The resource data
		"""
		if kind not in self.resource_cache:
			self.resource_cache[kind] = {
				"resource_version": None,
				"resources": {},
			}

		if len(uid := deep_get(resource, DictPath("metadata#uid"), "")) == 0:
			raise ProgrammingError("KubernetesResourceCache.update_resource(): "
					       "Attempt to add a resource with empty or None uid was made")
		resource_version = deep_get(resource, DictPath("metadata#resourceVersion"))
		if resource_version is None:
			raise ProgrammingError("KubernetesResourceCache.update_resource(): "
					       "Attempt to add a resource with empty or None resourceVersion was made")
		if resource_version == "":
			resource_version = "0"
		if uid not in self.resource_cache[kind]:
			self.resource_cache[kind]["resource_version"] = int(resource_version)
			self.resource_cache[kind]["resources"][uid] = copy.deepcopy(resource)
			self.updated = True
		elif deep_get(self.resource_cache[kind], DictPath("uid#metadata#resourceVersion"), "0") < int(resource_version):
			# Only update if the new version has a resource version strictly higher than the old version
			self.resource_cache[kind]["resource_version"] = int(resource_version)
			self.resource_cache[kind].pop(uid, None)
			self.resource_cache[kind]["resources"][uid] = copy.deepcopy(resource)
			self.updated = True

	def update_resources(self, kind: Tuple[str, str], resources: List[Dict]) -> None:
		"""
		Add or update the cache entries for a resource kind

			Parameters:
				kind ((str, str)): The kind tuple for the resources
				resources (dict): The resource data
		"""
		if resources is None or len(resources) == 0:
			raise ProgrammingError("KubernetesResourceCache.update_resources(): "
					       "resources is empty or None")

		for resource in resources:
			self.update_resource(kind, resource = resource)

	def get_resources(self, kind: Tuple[str, str]) -> Tuple[List[Dict], str]:
		"""
		Return a list with all resources of the specified kind

			Parameters:
				kind ((str, str)): The kind tuple for the resources
			Returns:
				([dict]): The list of cached resources of the specified kind
		"""
		if kind not in self.resource_cache:
			return None
		return [resource for uid, resource in deep_get(self.resource_cache[kind], DictPath("resources"), {}).items()]

	def index(self) -> List[str]:
		"""
		Return a list of all cached kinds

			Returns:
				([(str, str]): A list of kind tuples of all cached kinds
		"""
		if self.resource_cache is None:
			return []
		return list(self.resource_cache.keys())

	def __len__(self) -> int:
		"""
		Return the number of cached kinds

			Returns:
				(int): The number of cached kinds
		"""

		if self.resource_cache is None:
			return 0
		return len(self.resource_cache)


	def len(self, kind: Tuple[str, str]) -> int:
		"""
		Return the number of resources of the specified kind

			Parameters:
				kind ((str, str)): The kind tuple for the resources
			Returns:
				(int): The number of cached resources of the specified kind
		"""
		if self.resource_cache is None or kind not in self.resource_cache:
			return 0

		return len(deep_get(self.resource_cache[kind], DictPath("resources"), {}))

class PoolManagerContext:
	"""
	A class for wrapping PoolManager/ProxyManager
	"""

	# pylint: disable-next=too-many-arguments
	def __init__(self,
		     cert_file: Optional[str] = None, key_file: Optional[str] = None, ca_certs_file: Optional[str] = None,
		     token: Optional[str] = None, insecuretlsskipverify: bool = False) -> None:
		self.pool_manager = None
		self.cert_file = cert_file
		self.key_file = key_file
		self.ca_certs_file = ca_certs_file
		self.token = token
		self.insecuretlsskipverify = insecuretlsskipverify

	def __enter__(self) -> Union[urllib3.ProxyManager, urllib3.PoolManager]:
		# Only permit a limited set of acceptable ciphers
		ssl_context = urllib3.util.ssl_.create_urllib3_context(ciphers = ":".join(CIPHERS))
		# Disable anything older than TLSv1.2
		ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
		# This isn't ideal; we might need different cluster proxies for different clusters
		pool_manager_proxy = deep_get(cmtlib.cmtconfig, DictPath("Network#cluster_https_proxy"), "")

		if self.cert_file is not None:
			if not self.insecuretlsskipverify:
				pool_manager_args = {
					"cert_reqs": "CERT_REQUIRED",
					"ca_certs": self.ca_certs_file,
					"cert_file": self.cert_file,
					"key_file": self.key_file,
					"ssl_context": ssl_context,
				}
			else:
				pool_manager_args = {
					"cert_reqs": "CERT_NONE",
					"ca_certs": None,
					"cert_file": self.cert_file,
					"key_file": self.key_file,
				}
		elif self.token is not None:
			if not self.insecuretlsskipverify:
				pool_manager_args = {
					"cert_reqs": "CERT_REQUIRED",
					"ca_certs": self.ca_certs_file,
					"ssl_context": ssl_context,
				}
			else:
				pool_manager_args = {
					"cert_reqs": "CERT_NONE",
					"ca_certs": None,
				}

		if len(pool_manager_proxy) > 0:
			self.pool_manager = urllib3.ProxyManager(pool_manager_proxy, **pool_manager_args)
		else:
			self.pool_manager = urllib3.PoolManager(**pool_manager_args)

		return self.pool_manager

	def __exit__(self, *args: List, **kwargs: Any) -> None:
		if self.pool_manager is not None:
			self.pool_manager.clear()
		self.pool_manager = None

def kind_tuple_to_name(kind: Tuple[str, str]) -> str:
	"""
	Given a kind tuple, return a string representation

		Parameters:
			kind ((kind, api_group)): The kind tuple
				kind (str): The kind
				api_group (str): The API-group
		Returns:
			name (str): The string representation of kind + API-group
	"""

	name = ""

	if kind in kubernetes_resources:
		api = deep_get(kubernetes_resources[kind], DictPath("api"), "")
		name = f"{api}.{kind[1]}"
		name = name.rstrip(".")
	return name

def guess_kind(kind: Union[str, Tuple[str, str]]) -> Tuple[str, str]:
	"""
	Given a Kind without API-group, or (API-name, API-group)
	return the (Kind, API-group) tuple

		Parameters:
			kind (str):
				kind (str): The Kubernetes kind
			kind ((str, str)):
				kind (str): The API-name
				api_group (str): The API-group
		Returns:
			kind (kind, api_group):
				kind (str): The Kubernetes kind
				api_group (str): The API-group
		Raises:
			NameError: No matching API could be found
			TypeError: kind is not a str or (str, str) tuple
	"""

	if not isinstance(kind, (str, tuple)):
		raise TypeError("kind must be str or (str, str)")
	if isinstance(kind, tuple) and not (len(kind) == 2 and isinstance(kind[0], str) and isinstance(kind[1], str)):
		raise TypeError("kind must be str or (str, str)")

	if isinstance(kind, str):
		if "." in kind:
			kind = tuple(kind.split(".", maxsplit = 1))
		else:
			kind = (kind, "")

	# If we already have a tuple, do not guess
	if kind in kubernetes_resources:
		return kind

	if kind[0].startswith("__"):
		return kind

	guess = None

	# If we have a tuple that didn't match we can try matching it against the api + api_group instead.
	# To do that we need to scan.
	for resource_kind, resource_data in kubernetes_resources.items():
		api_name = deep_get(resource_data, DictPath("api"))
		resource_name = resource_kind[0].lower()
		resource_family = resource_kind[1].lower()
		kind_name = kind[0].lower()
		kind_family = kind[1].lower()
		if resource_name == kind_name and resource_family == kind_family:
			return resource_kind
		if (api_name, resource_family) == kind:
			return resource_kind
		if resource_name == kind_name and kind_family == "":
			# Special-case the built-in APIs
			if resource_family in ("admissionregistration.k8s.io",
					       "apiextensions.k8s.io",
					       "apps",
					       "autoscaling",
					       "batch",
					       "certificates.k8s.io",
					       "coordination.k8s.io",
					       "discovery.k8s.io",
					       "events.k8s.io",
					       "flowcontrol.apiserver.k8s.io",
					       "internal.apiserver.k8s.io",
					       "metacontroller.k8s.io"):
				return resource_kind

			if guess is None:
				guess = resource_kind
			else:
				guess = None
				break

	if guess is not None:
		return guess

	raise NameError(f"Could not guess kubernetes resource for kind: {kind}")

def update_api_status(kind: Tuple[str, str], listview: bool = False, infoview: bool = False, local: bool = False) -> None:
	"""
	Update kubernetes_resources for a kind to indicate whether or not there are list and infoviews for them

		Parameters:
			kind ((kind, api_group)): The kind tuple
			listview (bool): Does this kind have a list view
			infoview (bool): Does this kind have an info view
			local (bool): The view is a local addition
		Raises:
			TypeError: kind is not a (str, str) tuple
	"""

	if not isinstance(kind, tuple) or isinstance(kind, tuple) and not (len(kind) == 2 and isinstance(kind[0], str) and isinstance(kind[1], str)):
		raise TypeError("kind must be (str, str)")
	if not ((listview is None or isinstance(listview, bool)) and (infoview is None or isinstance(infoview, bool)) and (local is None or isinstance(local, bool))):
		raise TypeError("listview, infoview, and local must be either None or bool")

	# There are other kind of views than just Kubernetes APIs; just ignore them
	if kind not in kubernetes_resources:
		return
	kubernetes_resources[kind]["list"] = listview
	kubernetes_resources[kind]["info"] = infoview
	kubernetes_resources[kind]["local"] = local

def kubectl_get_version() -> Tuple[Optional[int], Optional[int], str, Optional[int], Optional[int], str]:
	"""
	Get kubectl & API-server version

		Returns:
			(kubectl_major_version, kubectl_minor_version, kubectl_git_version, server_major_version, server_minor_version, server_git_version):
				kubectl_major_version (int): Major client version
				kubectl_minor_version (int): Minor client version
				kubectl_git_version (str): Client GIT version
				server_major_version (int): Major API-server version
				server_minor_version (int): Minor API-server version
				server_git_version (str): API-server GIT version
	"""
	# Check kubectl version
	try:
		kubectl_path = secure_which(FilePath("/usr/bin/kubectl"), fallback_allowlist = ["/etc/alternatives"], security_policy = SecurityPolicy.ALLOWLIST_RELAXED)
	except FileNotFoundError:  # pragma: no cover
		return -1, -1, "", -1, -1, ""

	args = [kubectl_path, "version", "-oyaml"]

	try:
		response = execute_command_with_response(args)
		version_data = yaml.safe_load(response)
	except yaml.scanner.ScannerError:  # pragma: no cover
		return -1, -1, "", -1, -1, ""

	kubectl_version = deep_get(version_data, DictPath("clientVersion"))
	server_version = deep_get(version_data, DictPath("serverVersion"))
	if kubectl_version is not None:
		kubectl_major_version = int("".join(filter(str.isdigit, deep_get(kubectl_version, DictPath("major")))))
		kubectl_minor_version = int("".join(filter(str.isdigit, deep_get(kubectl_version, DictPath("minor")))))
		kubectl_git_version = str(deep_get(kubectl_version, DictPath("gitVersion")))
	else:  # pragma: no cover
		kubectl_major_version = None
		kubectl_minor_version = None
		kubectl_git_version = "<unavailable>"
	if server_version is not None:
		server_major_version = int("".join(filter(str.isdigit, deep_get(server_version, DictPath("major")))))
		server_minor_version = int("".join(filter(str.isdigit, deep_get(server_version, DictPath("minor")))))
		server_git_version = str(deep_get(server_version, DictPath("gitVersion")))
	else:  # pragma: no cover
		server_major_version = None
		server_minor_version = None
		server_git_version = "<unavailable>"

	return kubectl_major_version, kubectl_minor_version, kubectl_git_version, server_major_version, server_minor_version, server_git_version

def get_node_status(node: Dict) -> Tuple[str, StatusGroup, List[Tuple[str, str]], List[Dict]]:
	"""
	Given a node dict, extract the node status

		Parameters:
			node (dict): A dict with node information
		Returns:
			(status, status_group, taints, full_taints):
				status (str): A string representation of the node status
				status_group (StatusGroup): An enum representation of the node status
				taints (list[(str, str)]): A list of curated taints in tuple format
				full_taints (list[dict]): The full list of taints in dict format
	"""

	status = "Unknown"
	status_group = StatusGroup.UNKNOWN
	taints = []
	full_taints = deep_get(node, DictPath("spec#taints"), [])

	for condition in deep_get(node, DictPath("status#conditions"), []):
		if deep_get(condition, DictPath("type")) == "Ready":
			condition_status = deep_get(condition, DictPath("status"))
			if condition_status == "True":
				status = "Ready"
				status_group = StatusGroup.OK
			elif condition_status == "Unknown":
				status = "Unreachable"
				status_group = StatusGroup.NOT_OK
			else:
				status = "NotReady"
				status_group = StatusGroup.NOT_OK

	for nodetaint in deep_get(node, DictPath("spec#taints"), []):
		key = deep_get(nodetaint, DictPath("key"))
		if key == "node-role.kubernetes.io/master":
			key = "node-role.kubernetes.io/control-plane"
		effect = deep_get(nodetaint, DictPath("effect"))

		# Control Plane having scheduling disabled
		# is expected behaviour and does not need
		# any form of highlighting
		if deep_get(nodetaint, DictPath("effect")) == "NoSchedule":
			if key == "node-role.kubernetes.io/control-plane":
				taints.append(("control-plane", effect))
				continue

			if key.startswith("node.kubernetes.io/"):
				key = key[len("node.kubernetes.io/"):]

			taints.append((key, effect))

			# If status is already "worse" than OK,
			# we do not override it.
			# Scheduling being disabled is not an error,
			# but it is worth highlighting
			if status_group == StatusGroup.OK:
				status_group = StatusGroup.ADMIN
		else:
			if key.startswith("node.kubernetes.io/"):
				key = key[len("node.kubernetes.io/"):]

			taints.append((key, effect))

	return status, status_group, taints, full_taints

def make_selector(selector_dict: Dict) -> str:
	"""
	Given a selector dict entry, create a selector list

		Parameters:
			selector_dict (dict): The dict with selectors
		Returns:
			selector_str (str): The selector string
	"""

	selectors = []

	if selector_dict is not None:
		for key, value in selector_dict.items():
			selectors.append(f"{key}={value}")

	return ",".join(selectors)

def get_image_version(image: str, default: str = "<undefined>") -> str:
	"""
	Given the version of a container image, return its version

		Parameters:
			image (str): The name of the image
			default (str): The string to return if extracting the image version fails
		Returns:
			image_version (str): The extracted image version
	"""

	image_version = image.split("@")[0]
	image_version = image_version.split("/")[-1]
	image_version = image_version.split(":")[-1]

	# If we did not manage to do any splitting it means there was not a version; return default instead
	if image_version == image:
		image_version = default
	return image_version

def list_contexts(config_path: Optional[FilePath] = None) -> List[Tuple[bool, str, str, str, str, str]]:
	"""
	Given the path to a kubeconfig file, returns the available contexts

		Parameters:
			config_path (FilePath): The path to the kubeconfig file
		Returns:
			contexts (list[(current, name, cluster, authinfo, namespace)]):
				current (bool): Is this the current context?
				name (str): The name of the context
				cluster (str): The name of the cluster
				authinfo (str): The name of the user
				namespace (str): The name of the namespace
				server (str): The API-server of the cluster
	"""

	contexts = []

	if config_path is None:
		# Read kubeconfig
		config_path = KUBE_CONFIG_FILE

	try:
		kubeconfig = secure_read_yaml(FilePath(str(config_path)))
	except FilePathAuditError as e:
		if "SecurityStatus.PARENT_DOES_NOT_EXIST" in str(e):
			return []
	except FileNotFoundError:
		# We can handle FileNotFoundError and PARENT_DOES_NOT_EXIST;
		# other exceptions might be security related, so we let them raise
		return []
	except yaml.parser.ParserError as e:
		e.args += (f"{config_path} is not valid YAML; aborting.",)
		raise

	current_context = deep_get(kubeconfig, DictPath("current-context"), "")

	for context in deep_get(kubeconfig, DictPath("contexts"), []):
		name = deep_get(context, DictPath("name"))
		# In this case the parentheses really help legibility
		# pylint: disable-next=superfluous-parens
		current = (name == current_context)
		namespace = deep_get(context, DictPath("namespace"), "default")
		authinfo = deep_get(context, DictPath("context#user"))
		cluster = deep_get(context, DictPath("context#cluster"))
		server = ""
		for cluster_data in deep_get(kubeconfig, DictPath("clusters"), []):
			if cluster == deep_get(cluster_data, DictPath("name")):
				server = deep_get(cluster_data, DictPath("cluster#server"))
		contexts.append((current, name, cluster, authinfo, namespace, server))
	return contexts

# pylint: disable-next=too-many-return-statements
def set_context(config_path: Optional[FilePath] = None, name: Optional[str] = None) -> Optional[str]:
	"""
	Change context

		Parameters:
			config_path (FilePath): The path to the kubeconfig file
			name (str): The context to change to
		Returns:
			context (str): The name of the new current-context, or None on failure
	"""

	# We need a context name
	if name is None or len(name) == 0:
		return None

	if config_path is None:
		# Read kubeconfig
		config_path = KUBE_CONFIG_FILE

	config_path = FilePath(str(config_path))

	# We are semi-OK with the file not existing
	checks = [
		SecurityChecks.PARENT_RESOLVES_TO_SELF,
		SecurityChecks.OWNER_IN_ALLOWLIST,
		SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
		SecurityChecks.CAN_READ_IF_EXISTS,
		SecurityChecks.PERMISSIONS,
		SecurityChecks.PARENT_PERMISSIONS,
		SecurityChecks.IS_FILE,
	]

	try:
		kubeconfig = secure_read_yaml(config_path, checks = checks)
	except FileNotFoundError:
		return None
	except FilePathAuditError as e:
		if "SecurityStatus.PARENT_DOES_NOT_EXIST" in str(e):
			return None
		if "SecurityStatus.PERMISSIONS" in str(e):
			return None
		raise

	new_context = None

	# Find out whether the new context exists
	for context in deep_get(kubeconfig, DictPath("contexts"), []):
		if deep_get(context, DictPath("name"), "") == name:
			new_context = name
			break

	if new_context is not None:
		kubeconfig["current-context"] = new_context
		secure_write_yaml(config_path, kubeconfig, permissions = 0o600, sort_keys = False)

	return new_context

# pylint: disable-next=too-many-instance-attributes,too-many-public-methods
class KubernetesHelper:
	"""
	A class used for interacting with a Kubernetes cluster
	"""

	# XXX: There doesn't seem to be any better type-hint for NamedTemporaryFile for the time being.
	tmp_ca_certs_file: Any = None
	tmp_cert_file: Any = None
	tmp_key_file: Any = None

	ca_certs_file: Optional[str] = None
	cert_file: Optional[str] = None
	key_file: Optional[str] = None
	token: Optional[str] = None

	pool_manager_args: Dict = {}
	pool_manager_proxy = ""

	programname = ""
	programversion = ""

	cluster_unreachable: bool = True
	cluster_name: str = ""
	coontext_name: str = ""
	config_path: Optional[FilePath] = None

	control_plane_ip: Optional[str] = None
	control_plane_port: Optional[str] = None
	control_plane_path: Optional[str] = None

	def list_contexts(self, config_path: Optional[FilePath] = None) -> List[Tuple[bool, str, str, str, str, str]]:
		"""
		Given the path to a kubeconfig file, returns the available contexts

			Parameters:
				config_path (FilePath): The path to the kubeconfig file
			Returns:
				contexts (list[(current, name, cluster, authinfo, namespace)]):
					current (bool): Is this the current context?
					name (str): The name of the context
					cluster (str): The name of the cluster
					authinfo (str): The name of the user
					namespace (str): The name of the namespace
					server (str): The API-server of the cluster
		"""

		# If config_path is passed as a parameter, use it,
		# else use the path used when initialising the class
		if config_path is None:
			config_path = self.config_path
		# This should never be needed, but just in case
		elif config_path is None:
			config_path = KUBE_CONFIG_FILE

		return list_contexts(config_path)

	def list_clusters(self, config_path: Optional[FilePath] = None) -> List[Tuple[str, str]]:
		"""
		Returns a list of (cluster, context)
		with only one context per cluster, priority given to contexts with admin in the username

			Parameters:
				config_path (FilePath): The path to the kubeconfig file
			Returns:
				clusters (list[(cluster, context)]):
					cluster (str): The name of the cluster
					context (str): The name of the context
		"""

		# If config_path is passed as a parameter, use it,
		# else use the path used when initialising the class
		if config_path is None:
			config_path = self.config_path
		# This should never be needed, but just in case
		elif config_path is None:
			config_path = KUBE_CONFIG_FILE

		contexts = self.list_contexts(config_path = config_path)
		__clusters: Dict = {}
		clusters = []

		for context in contexts:
			name = context[1]
			cluster = context[2]
			authinfo = context[3]

			# Add the first context we find for a cluster
			if cluster not in __clusters:
				__clusters[cluster] = {
					"context": name,
					"authinfo": authinfo,
				}
			else:
				# Only override that entry if we find an admin
				if "admin" in authinfo and "admin" not in __clusters[cluster]["authinfo"]:
					__clusters[cluster]["context"] = name
					__clusters[cluster]["authinfo"] = authinfo

		# If we find a context where the authinfo mentions admin, pick that one,
		# otherwise just find the first context for each cluster
		for cluster, data in __clusters.items():
			clusters.append((cluster, data["context"]))

		return clusters

	def renew_token(self, cluster_name: str, context_name: str) -> None:
		"""
		Renew the authentication token, if applicable

			Parameters:
				cluster_name (str): The name of the cluster
				context_name (str): The name of the context
		"""

		# If the current cluster_name + context_name
		# has a matching entry in credentials we (attempt to) authenticate here

		try:
			credentials = secure_read_yaml(FilePath(str(KUBE_CREDENTIALS_FILE)))
		except FilePathAuditError as e:
			if "SecurityStatus.PARENT_DOES_NOT_EXIST" in str(e) or "SecurityStatus.DOES_NOT_EXIST" in str(e):
				return
			raise
		except FileNotFoundError:
			# We can handle FileNotFoundError and PARENT_DOES_NOT_EXIST;
			# other exceptions might be security related, so we let them raise
			return
		except yaml.parser.ParserError as e:
			e.args += (f"{KUBE_CREDENTIALS_FILE} is not valid YAML; aborting.",)
			raise

		# We got ourselves a credentials file;
		# is there a password for the current cluster + context?
		name = deep_get(credentials, DictPath(f"clusters#{cluster_name}#contexts#{context_name}#name"), None)
		password = deep_get(credentials, DictPath(f"clusters#{cluster_name}#contexts#{context_name}#password"), None)

		if name is None or password is None:
			return

		# This only applies for CRC
		if "crc" in cluster_name:
			url = "https://oauth-openshift.apps-crc.testing/oauth/authorize?response_type=token&client_id=openshift-challenging-client"
			auth = f"{name}:{password}".encode("ascii")

			header_params = {
				"X-CSRF-Token": "xxx",
				"Authorization": f"Basic {base64.b64encode(auth).decode('ascii')}",
				# "Accept": "application/json",
				# "Content-Type": "application/json",
				"User-Agent": f"{self.programname} v{self.programversion}",
			}

			connect_timeout: float = 3.0

			try:
				with PoolManagerContext(cert_file = self.cert_file, key_file = self.key_file, ca_certs_file = self.ca_certs_file, token = self.token, insecuretlsskipverify = self.insecuretlsskipverify) as pool_manager:
					result = pool_manager.request("GET", url, headers = header_params, timeout = urllib3.Timeout(connect = connect_timeout), redirect = False)  # type: ignore
					status = result.status
			except urllib3.exceptions.MaxRetryError as e:
				# No route to host does not have a HTTP response; make one up...
				# 503 is Service Unavailable; this is generally temporary, but to distinguish it from a real 503
				# we prefix it...
				if "CERTIFICATE_VERIFY_FAILED" in str(e):
					# Client Handshake Failed (Cloudflare)
					status = 525
				else:
					status = 42503
			except urllib3.exceptions.ConnectTimeoutError:
				# Connection timed out; the API-server might not be available, suffer from too high load, or similar
				# 504 is Gateway Timeout; using 42504 to indicate connection timeout thus seems reasonable
				status = 42504

			if status == 302:
				location = result.headers.get("Location", "")
				tmp = re.match(r".*implicit#access_token=([^&]+)", location)
				if tmp is not None:
					self.token = tmp[1]

	# pylint: disable-next=too-many-return-statements
	def set_context(self, config_path: Optional[FilePath] = None, name: Optional[str] = None, unchanged_is_success: bool = False) -> bool:
		"""
		Change context

			Parameters:
				config_path (FilePath): The path to the kubeconfig file
				name (str): The context to change to
				unchanged_is_success (bool): True to return success if the context didn't change, False otherwise
			Returns:
				status (bool): True on success, False on failure
		"""

		context_name = ""
		cluster_name = ""
		user_name = ""
		namespace_name = ""  # pylint: disable=unused-variable

		# If config_path is passed as a parameter, use it,
		# else use the path used when initialising the class
		if config_path is None:
			config_path = self.config_path
		# This should never be needed, but just in case
		elif config_path is None:
			config_path = KUBE_CONFIG_FILE

		config_path = FilePath(str(config_path))

		# We are semi-OK with the file not existing
		checks = [
			SecurityChecks.PARENT_RESOLVES_TO_SELF,
			SecurityChecks.OWNER_IN_ALLOWLIST,
			SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
			SecurityChecks.CAN_READ_IF_EXISTS,
			SecurityChecks.PERMISSIONS,
			SecurityChecks.PARENT_PERMISSIONS,
			SecurityChecks.IS_FILE,
		]

		try:
			kubeconfig = secure_read_yaml(config_path, checks = checks)
		except FileNotFoundError:
			return False
		except FilePathAuditError as e:
			if "SecurityStatus.PARENT_DOES_NOT_EXIST" in str(e):
				return False
			if "SecurityStatus.PERMISSIONS" in str(e):
				return False
			raise

		current_context = deep_get(kubeconfig, DictPath("current-context"), "")

		unchanged = True
		# If we did not get a context name we try current-context
		if name is None or len(name) == 0:
			unchanged = False
			name = current_context
		name = str(name)

		for context in deep_get(kubeconfig, DictPath("contexts"), []):
			# If we still do not have a context name,
			# pick the first match
			if len(name) == 0 or deep_get(context, DictPath("name")) == name:
				context_name = deep_get(context, DictPath("name"))
				user_name = deep_get(context, DictPath("context#user"), "")
				cluster_name = deep_get(context, DictPath("context#cluster"), "")
				namespace_name = deep_get(context, DictPath("context#namespace"), "")
				break

		if unchanged and current_context == context_name:
			return unchanged_is_success

		control_plane_ip = None
		control_plane_port = None
		control_plane_path = None
		self.insecuretlsskipverify = False
		ca_certs = None

		# OK, we have a user and a cluster to look for
		host_port_path_regex = re.compile(r"^https?://(.*):(\d+)(.*)")

		for cluster in deep_get(kubeconfig, DictPath("clusters"), []):
			if deep_get(cluster, DictPath("name")) != cluster_name:
				continue

			tmp = host_port_path_regex.match(cluster["cluster"]["server"])
			if tmp is not None:
				control_plane_ip = tmp[1]
				control_plane_port = tmp[2]
				control_plane_path = tmp[3]

			self.insecuretlsskipverify = deep_get(cluster, DictPath("cluster#insecure-skip-tls-verify"), False)
			if self.insecuretlsskipverify:
				break

			# ca_certs
			ccac = deep_get(cluster, DictPath("cluster#certificate-authority-data"))
			# ca_certs file
			ccac_file = deep_get(cluster, DictPath("cluster#certificate-authority"))


			if ccac is not None:
				try:
					ca_certs = base64.b64decode(ccac).decode("utf-8")
				except UnicodeDecodeError as e:
					e.args += (f"failed to decode certificate-authority-data: {e}",)
					raise
				break
			if ccac_file is not None:
				ca_certs = cast(str, secure_read(ccac_file))

		if control_plane_ip is None or control_plane_port is None:
			return False

		# OK, we have a cluster, try to find a user

		cert = None
		key = None
		self.token = None

		for _userindex, user in enumerate(deep_get(kubeconfig, DictPath("users"), [])):
			if deep_get(user, DictPath("name")) == user_name:
				if len(deep_get(user, DictPath("user"), {})) == 0:
					# We didn't get any user data at all;
					# we might still be able to use a token
					# if this is CRC
					if "crc" in cluster_name:
						self.token = ""
					break
				# cert
				ccd = deep_get(user, DictPath("user#client-certificate-data"))
				# cert file
				ccd_file = deep_get(user, DictPath("user#client-certificate"))

				if ccd is not None:
					try:
						cert = base64.b64decode(ccd).decode("utf-8")
					except UnicodeDecodeError as e:
						e.args += (f"failed to decode client-certificate-data: {e}",)
						raise
				elif ccd_file is not None:
					cert = cast(str, secure_read(ccd_file))


				# key
				ckd = deep_get(user, DictPath("user#client-key-data"))
				# key file
				ckd_file = deep_get(user, DictPath("user#client-key"))

				if ckd is not None:
					try:
						key = base64.b64decode(ckd).decode("utf-8")
					except UnicodeDecodeError as e:
						e.args += (f"failed to decode client-key-data: {e}",)
						raise
				elif ckd_file is not None:
					key = cast(str, secure_read(ckd_file))

				self.token = deep_get(user, DictPath("user#token"))
				break

		# We do not have the cert or token needed to access the server
		if self.token is None and (cert is None or key is None):
			return False

		# We cannot authenticate the server correctly
		if ca_certs is None and not self.insecuretlsskipverify:
			return False

		# OK, we've got the cluster IP and port,
		# as well as the certs we need; time to switch context

		# If we are switching contexts we might have open files
		self.__close_certs()

		self.control_plane_ip = control_plane_ip
		self.control_plane_port = control_plane_port
		self.control_plane_path = control_plane_path
		if key is not None:
			key = str(key)

		if not self.insecuretlsskipverify:
			ca_certs = str(ca_certs)
			self.tmp_ca_certs_file = tempfile.NamedTemporaryFile()  # pylint: disable=consider-using-with
			self.ca_certs_file = self.tmp_ca_certs_file.name
			self.tmp_ca_certs_file.write(ca_certs.encode("utf-8"))
			self.tmp_ca_certs_file.flush()
		else:
			urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

		# If we have a cert we also have a key, but check anyway, to make mypy happy
		if cert is not None and key is not None:
			self.tmp_cert_file = tempfile.NamedTemporaryFile()  # pylint: disable=consider-using-with
			self.tmp_key_file = tempfile.NamedTemporaryFile()  # pylint: disable=consider-using-with
			self.cert_file = self.tmp_cert_file.name
			self.key_file = self.tmp_key_file.name

			self.tmp_cert_file.write(cert.encode("utf-8"))
			self.tmp_cert_file.flush()

			self.tmp_key_file.write(key.encode("utf-8"))
			self.tmp_key_file.flush()

		self.cluster_unreachable = False
		self.cluster_name = cluster_name
		self.context_name = context_name

		# If we are switching contexts, update the config file
		if context_name != current_context:
			kubeconfig["current-context"] = context_name

		secure_write_yaml(config_path, kubeconfig, permissions = 0o600, sort_keys = False)

		return True

	def get_pod_network_cidr(self) -> Optional[str]:
		"""
		Returns the Pod network CIDR for the cluster

			Returns:
				pod_network_cidr (str): The Pod network CIDR
		"""

		# First try to get the CIDR from kubeadm-config, if it exists
		ref = self.get_ref_by_kind_name_namespace(("ConfigMap", ""), name = "kubeadm-config", namespace = "kube-system")
		if ref is not None:
			data = deep_get(ref, DictPath("data#ClusterConfiguration"), {})
			try:
				d = yaml.safe_load(data)
				return deep_get(d, DictPath("networking#podSubnet"))
			except yaml.scanner.ScannerError:
				pass
		nodes, status = self.get_list_by_kind_namespace(("Node", ""), "", label_selector = "node-role.kubernetes.io/control-plane")
		if nodes is None or len(nodes) == 0 or status != 200:
			nodes, status = self.get_list_by_kind_namespace(("Node", ""), "", label_selector = "node-role.kubernetes.io/master")
		if nodes is None or len(nodes) == 0 or status != 200:
			return None
		return deep_get(nodes[0], DictPath("spec#podCIDR"))

	# CNI detection helpers
	def __identify_cni(self, cni_name: str, controller_kind: Tuple[str, str], controller_selector: str, container_name: str) -> List[Tuple[str, str, Tuple[str, StatusGroup, str]]]:
		cni: List[Tuple[str, str, Tuple[str, StatusGroup, str]]] = []

		# Is there a controller matching the kind we are looking for?
		vlist, _status = self.get_list_by_kind_namespace(controller_kind, "", field_selector = controller_selector)

		if vlist is None or len(vlist) == 0 or _status != 200:
			return cni

		pod_matches = 0
		cni_version = None
		cni_status = ("<unknown>", StatusGroup.UNKNOWN, "Could not get status")

		# 2. Are there > 0 pods matching the label selector?
		for obj in vlist:
			if controller_kind == ("Deployment", "apps"):
				cni_status = ("Unavailable", StatusGroup.NOT_OK, "")
				for condition in deep_get(obj, DictPath("status#conditions")):
					ctype = deep_get(condition, DictPath("type"))
					if ctype == "Available":
						cni_status = (ctype, StatusGroup.OK, "")
						break
			elif controller_kind == ("DaemonSet", "apps"):
				if deep_get(obj, DictPath("status#numberUnavailable"), 0) > deep_get(obj, DictPath("status#maxUnavailable"), 0):
					cni_status = ("Unavailable", StatusGroup.NOT_OK, "numberUnavailable > maxUnavailable")
				else:
					cni_status = ("Available", StatusGroup.OK, "")

			vlist2, _status = self.get_list_by_kind_namespace(("Pod", ""), "", label_selector = make_selector(deep_get(obj, DictPath("spec#selector#matchLabels"))))

			if vlist2 is not None and len(vlist2) > 0:
				for obj2 in vlist2:
					# Try to get the version
					for container in deep_get(obj2, DictPath("status#containerStatuses"), []):
						if deep_get(container, DictPath("name"), "") == container_name:
							image_version = get_image_version(deep_get(container, DictPath("image"), ""))

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

	def identify_cni(self) -> List[Tuple[str, str, Tuple[str, StatusGroup, str]]]:
		"""
		Attempt to identify what CNI the cluster is using; if there are multiple possible matches all are returned

			Returns:
				cni (list[(name, version, (status, status_group, reason)])): A list of possible CNI candidates
					name (str): The CNI name
					version (str): The version of the CNI
					status: A string representation of the CNI status
					status_group (StatusGroup): An enum representation of the CNI status
					reason (str): The reason for the status, if known
		"""

		cni: List[Tuple[str, str, Tuple[str, StatusGroup, str]]] = []

		# We have to do some sleuthing here
		# Antrea:
		cni += self.__identify_cni("antrea", ("DaemonSet", "apps"), "metadata.name=antrea-agent", "antrea-agent")
		# Canal:
		cni += self.__identify_cni("canal", ("DaemonSet", "apps"), "metadata.name=canal", "calico-node")
		cni += self.__identify_cni("canal", ("DaemonSet", "apps"), "metadata.name=rke2-canal", "calico-node")
		# Calico:
		# Since canal is a combination of Calico and Flannel we need to skip Calico if Canal is detected
		if "canal" not in (cni_name for cni_name, cni_version, cni_status in cni):
			cni += self.__identify_cni("calico", ("Deployment", "apps"), "metadata.name=calico-kube-controllers", "calico-kube-controllers")
		# Cilium:
		cni += self.__identify_cni("cilium", ("Deployment", "apps"), "metadata.name=cilium-operator", "cilium-operator")
		# Flannel:
		cni += self.__identify_cni("flannel", ("DaemonSet", "apps"), "metadata.name=kube-flannel-ds", "kube-flannel")
		cni += self.__identify_cni("flannel", ("DaemonSet", "apps"), "metadata.name=kube-flannel", "kube-flannel")
		# Kilo:
		cni += self.__identify_cni("kilo", ("DaemonSet", "apps"), "metadata.name=kilo", "kilo")
		# Kindnet:
		cni += self.__identify_cni("kindnet", ("DaemonSet", "apps"), "metadata.name=kindnet", "kindnet-cni")
		# Kube-OVN:
		cni += self.__identify_cni("kube-ovn", ("DaemonSet", "apps"), "metadata.name=kube-ovn-cni", "cni-server")
		# OpenShift-SDN:
		cni += self.__identify_cni("sdn", ("DaemonSet", "apps"), "metadata.name=sdn", "sdn")
		# Kube-router:
		cni += self.__identify_cni("kube-router", ("DaemonSet", "apps"), "metadata.name=kube-router", "kube-router")
		# Weave:
		cni += self.__identify_cni("weave", ("DaemonSet", "apps"), "metadata.name=weave-net", "weave")

		return cni

	def get_node_roles(self, node: Dict) -> List[str]:
		"""
		Get a list of the roles that the node belongs to

			Parameters:
				node (dict): The node object
			Returns:
				roles (list[str]): THe roles that the node belongs to
		"""

		roles: List[str] = []

		node_role_regex = re.compile(r"^node-role\.kubernetes\.io/(.*)")

		for label in deep_get(node, DictPath("metadata#labels"), {}).items():
			tmp = node_role_regex.match(label[0])

			if tmp is None:
				continue

			role = tmp[1]

			if role not in roles:
				roles.append(role)

		return roles

	def __close_certs(self) -> None:
		if self.tmp_ca_certs_file is not None:
			self.tmp_ca_certs_file.close()
		if self.tmp_cert_file is not None:
			self.tmp_cert_file.close()
		if self.tmp_key_file is not None:
			self.tmp_key_file.close()

	def __init__(self, programname: str, programversion: str, config_path: Optional[FilePath] = None) -> None:
		self.programname = programname
		self.programversion = programversion
		self.cluster_unreachable = True
		self.context_name = ""
		self.cluster_name = ""

		if config_path is None:
			self.config_path = KUBE_CONFIG_FILE
		else:
			self.config_path = config_path

		self.set_context(config_path = config_path)

	def __del__(self) -> None:
		self.__close_certs()
		self.context_name = ""
		self.cluster_name = ""
		self.config_path = None

	def is_cluster_reachable(self) -> bool:
		"""
		Checks if the cluster is reachable

			Returns:
				is_reachable (bool): True if cluster is reachable, False if the cluster is unreachable
		"""

		return not self.cluster_unreachable

	def get_control_plane_address(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
		"""
		Returns the IP-address and port of the control plane

			Returns:
				(control_plane_ip, control_plane_port, control_plane_path): The IP-address, port, and path of the control plane
					control_plane_ip (str): An IP-address
					control_plane_port (str): A port
					control_plane_path (str): A path (can be the empty string)
		"""

		return self.control_plane_ip, self.control_plane_port, self.control_plane_path

	def get_join_token(self) -> str:
		"""
		Returns the cluster join token

			Returns:
				join_token (str): The cluster join token
		"""

		join_token = ""

		vlist, _status = self.get_list_by_kind_namespace(("Secret", ""), "kube-system")

		if vlist is None or len(vlist) == 0 or _status != 200:
			return join_token

		age = -1

		# Find the newest bootstrap token
		for secret in vlist:
			name = deep_get(secret, DictPath("metadata#name"))
			if name.startswith("bootstrap-token-"):
				timestamp = timestamp_to_datetime(deep_get(secret, DictPath("metadata#creationTimestamp")))
				newage = get_since(timestamp)
				if age == -1 or newage < age:
					try:
						tmp1 = base64.b64decode(deep_get(secret, DictPath("data#token-id"), "")).decode("utf-8")
					except UnicodeDecodeError:
						tmp2 = deep_get(secret, DictPath("data#token-id"), "")

					try:
						tmp2 = base64.b64decode(deep_get(secret, DictPath("data#token-secret"), "")).decode("utf-8")
					except UnicodeDecodeError:
						tmp2 = deep_get(secret, DictPath("data#token-secret"), "")

					if tmp1 != "" and tmp2 != "":
						join_token = f"{tmp1}.{tmp2}"
						age = newage

		return join_token

	def get_ca_cert_hash(self) -> str:
		"""
		Returns the CA certificate hash

			Returns:
				ca_cert_hash (str): The CA certificate hash
		"""

		ca_cert_hash = ""

		vlist, _status = self.get_list_by_kind_namespace(("Secret", ""), "kube-system")

		if vlist is None or len(vlist) == 0 or _status != 200:
			return ca_cert_hash

		age = -1
		ca_cert = ""

		# Find the newest certificate-controller-token
		for secret in vlist:
			if deep_get(secret, DictPath("metadata#name")).startswith("certificate-controller-token-"):
				timestamp = timestamp_to_datetime(deep_get(secret, DictPath("metadata#creationTimestamp")))
				newage = get_since(timestamp)
				if age == -1 or newage < age:
					try:
						tmp1 = base64.b64decode(deep_get(secret, DictPath("data#ca.crt"), "")).decode("utf-8")
					except UnicodeDecodeError:
						tmp1 = deep_get(secret, DictPath("data#ca.crt"), "")

					if tmp1 != "":
						ca_cert = tmp1
						age = newage

		if ca_cert == "":
			ref = self.get_ref_by_kind_name_namespace(("ConfigMap", ""), "kube-root-ca.crt", "kube-public")
			ca_cert = deep_get(ref, DictPath("data#ca.crt"), "")

		# we have the CA cert; now to extract the public key and hash it
		if len(ca_cert) > 0:
			try:
				x509obj = x509.load_pem_x509_certificate(ca_cert.encode("utf-8"))
			except TypeError as e:
				if "load_pem_x509_certificate() missing 1 required positional argument: 'backend'" in str(e):
					# This is to handle systems that doesn't have the latest version of cryptography
					# pylint: disable-next=import-outside-toplevel,no-name-in-module
					from cryptography.hazmat.primitives import default_backend  # type: ignore
					x509obj = x509.load_pem_x509_certificate(ca_cert.encode("utf-8"), backend = default_backend)
				else:
					raise
			pubkeyder = x509obj.public_key().public_bytes(encoding = serialization.Encoding.DER, format = serialization.PublicFormat.SubjectPublicKeyInfo)
			ca_cert_hash = hashlib.sha256(pubkeyder).hexdigest()

		return ca_cert_hash

	def is_kind_namespaced(self, kind: Tuple[str, str]) -> bool:
		"""
		Is this kind namespaced?

			Parameters:
				kind ((str, str)): A (kind, api_group) tuple
			Returns:
				is_namespaced (bool): True if namespaced, False if not
		"""

		if kind not in kubernetes_resources:
			raise ValueError(f"Kind {kind} not known; this is likely a programming error (possibly a typo)")
		return deep_get(kubernetes_resources[kind], DictPath("namespaced"), True)

	def kind_api_version_to_kind(self, kind: str, api_version: str) -> Tuple[str, str]:
		"""
		Given a Kubernetes API as (kind, api_version) return (kind, api_group)

			Parameters:
				kind (str): A Kubernetes kind
				api_version (str): A kubernetes API-version
			Returns:
				((kind, api_group)): A (kind, api_group) tuple
		"""

		# The API-group is anything before /, or the empty string if there's no "/"
		if api_version is not None and "/" in api_version:
			tmp = re.match(r"^(.*)/.*", api_version)
			if tmp is None:
				raise ValueError(f"Could not extract API-group from {api_version}",)
			api_group = tmp[1]
		else:
			api_group = ""
		return kind, api_group

	def get_latest_api(self, kind: Tuple[str, str]) -> str:
		"""
		Given a Kubernetes API as (kind, api_group), returns the latest API-version

			Parameters:
				kind ((str, str)): A (kind, api_group) tuple
			Returns:
				latest_api (str): The latest API-version
		"""

		if kind not in kubernetes_resources:
			raise ValueError(f"Could not determine latest API; kind {kind} not found in kubernetes_resources")

		latest_api = deep_get(kubernetes_resources[kind], DictPath("api_paths"))[0]
		if latest_api.startswith("api/"):
			latest_api = latest_api[len("api/"):]
		elif latest_api.startswith("apis/"):
			latest_api = latest_api[len("apis/"):]
		if latest_api.endswith("/"):
			latest_api = latest_api[:-len("/")]
		return latest_api

	# pylint: disable=too-many-return-statements
	def get_api_resources(self) -> Tuple[int, List[Tuple]]:
		"""
		Return information about all API-resources available in the cluster

			Returns:
				((status, api_resources)):
					status (int): The HTTP response
					api_resources ([dict]): Information about all available API-resources
		"""

		# If the list is not empty, but the cluster is unreachable, return it unchanged
		if self.cluster_unreachable:
			return 42503, []

		api_resources: List[Tuple] = []
		core_apis = {}

		# First get all core APIs
		method = "GET"
		url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/api/v1"
		with PoolManagerContext(cert_file = self.cert_file, key_file = self.key_file, ca_certs_file = self.ca_certs_file, token = self.token, insecuretlsskipverify = self.insecuretlsskipverify) as pool_manager:
			raw_data, _message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = method, url = url)

			if status == 200 and raw_data is not None:
				# Success
				try:
					core_apis = json.loads(raw_data)
				except DecodeException:
					# We got a response, but the data is malformed
					return 42422, []
			else:
				# Something went wrong
				self.cluster_unreachable = True
				return status, []

			group_version = deep_get(core_apis, DictPath("groupVersion"), "")

			for api in deep_get(core_apis, DictPath("resources"), []):
				name = deep_get(api, DictPath("name"), "")
				shortnames = deep_get(api, DictPath("shortNames"), [])
				api_version = group_version
				namespaced = deep_get(api, DictPath("namespaced"), False)
				kind = deep_get(api, DictPath("kind"), "")
				verbs = deep_get(api, DictPath("verbs"), [])
				if len(verbs) == 0:
					continue
				api_resources.append((name, shortnames, api_version, namespaced, kind, verbs))

			# Now fetch non-core APIs
			non_core_apis = {}
			non_core_api_dict = {}

			# Attempt aggregated discovery; we need custom header_params to do this.
			# Fallback to the old method if aggregate discovery isn't supported.
			header_params = {
				"Accept": "application/json;g=apidiscovery.k8s.io;v=v2beta1;as=APIGroupDiscoveryList,application/json",
				"Content-Type": "application/json",
				"User-Agent": f"{self.programname} v{self.programversion}",
			}
			aggregated_data = {}

			url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/apis"
			with PoolManagerContext(cert_file = self.cert_file, key_file = self.key_file, ca_certs_file = self.ca_certs_file, token = self.token, insecuretlsskipverify = self.insecuretlsskipverify) as pool_manager:
				raw_data, _message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = method, url = url, header_params = header_params)

				if status == 200 and raw_data is not None:
					# Success
					try:
						aggregated_data = json.loads(raw_data)
					except DecodeException:
						# We got a response, but the data is malformed
						pass
				else:
					# No non-core APIs found; this is a bit worrying, but OK...
					pass

				# We successfully got aggregated data
				if deep_get(aggregated_data, DictPath("kind"), "") == "APIGroupDiscoveryList":
					for api_group in deep_get(aggregated_data, DictPath("items"), []):
						api_group_name = deep_get(api_group, DictPath("metadata#name"), "")
						versions = deep_get(api_group, DictPath("versions"), [])

						# Now we need to check what kinds this api_group supports
						# and using what version
						for version in versions:
							_version = deep_get(version, DictPath("version"))
							if _version is None:
								# This should not happen, but ignore it
								continue
							resources = deep_get(api_group, DictPath("resources"), [])
							for resource in deep_get(version, DictPath("resources"), []):
								name = deep_get(resource, DictPath("resource"), [])
								shortnames = deep_get(resource, DictPath("shortNames"), [])
								api_version = "/".join([api_group_name, _version])
								namespaced = deep_get(resource, DictPath("scope"), "") == "Namespaced"
								kind = deep_get(resource, DictPath("responseKind#kind"), "")
								verbs = deep_get(resource, DictPath("verbs"), [])
								kind_tuple = (kind, api_version.split("/", maxsplit = 1)[0])
								# Let's hope we get them in the right order...
								if kind_tuple in non_core_api_dict:
									continue
								non_core_api_dict[kind_tuple] = (name, shortnames, api_version, namespaced, kind, verbs)
					api_resources += list(non_core_api_dict.values())

					return status, api_resources

				# Nope, this is only non-core APIs
				non_core_apis = aggregated_data

				for api_group in deep_get(non_core_apis, DictPath("groups"), []):
					name = deep_get(api_group, DictPath("name"), "")
					versions = deep_get(api_group, DictPath("versions"), [])

					# Now we need to check what kinds this api_group supports
					# and using what version
					for version in versions:
						group_version = deep_get(version, DictPath("groupVersion"))
						if group_version is None:
							# This should not happen, but ignore it
							continue
						url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/apis/{group_version}"
						raw_data, _message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = method, url = url)

						if status != 200 or raw_data is None:
							# Could not get API info; this is worrying, but ignore it
							continue
						try:
							data = json.loads(raw_data)
						except DecodeException:
							# We got a response, but the data is malformed
							continue

						resources = deep_get(data, DictPath("resources"), [])
						for resource in resources:
							kind = deep_get(resource, DictPath("kind"), "")
							if len(kind) == 0:
								continue

							name = deep_get(resource, DictPath("name"), "")
							shortnames = deep_get(resource, DictPath("shortNames"), [])
							api_version = group_version
							namespaced = deep_get(resource, DictPath("namespaced"), False)
							kind = deep_get(resource, DictPath("kind"), "")
							verbs = deep_get(resource, DictPath("verbs"), [])
							if len(verbs) == 0:
								continue
							kind_tuple = (kind, api_version.split("/")[0])
							# Let's hope we get them in the right order...
							if kind_tuple in non_core_api_dict:
								continue
							non_core_api_dict[kind_tuple] = (name, shortnames, api_version, namespaced, kind, verbs)
				api_resources += list(non_core_api_dict.values())

		return status, api_resources

	# TODO: This should ideally be modified to use get_api_resources()
	def get_available_kinds(self, force_refresh: bool = False) -> Tuple[Dict, int, bool]:
		"""
		Return a dict of Kinds known by both kubernetes_helper and the API-server

			Parameters:
				force_refresh (bool): Flush the list (if existing) and create a new one
			Returns:
				((kubernetes_resources, status, modified)):
					kubernetes_resources (dict): A list of all Kinds known
					by kubernetes_helper, with their support level (list, info) set
					status (int): The HTTP response
					modified (bool): True if the list was updated, False otherwise

		"""

		modified = False

		# If the list is not empty, but the cluster is unreachable, return it unchanged
		if self.cluster_unreachable:
			return kubernetes_resources, 42503, modified

		# It is fairly easy to check if the API-list is "fresh"; just check whether Pod is available
		if not force_refresh and deep_get(kubernetes_resources[("Pod", "")], DictPath("available"), False):
			return kubernetes_resources, 200, modified

		method = "GET"

		# First get all core APIs
		core_apis = {}

		url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/api/v1"
		with PoolManagerContext(cert_file = self.cert_file, key_file = self.key_file, ca_certs_file = self.ca_certs_file, token = self.token, insecuretlsskipverify = self.insecuretlsskipverify) as pool_manager:
			raw_data, _message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = method, url = url)

			if status == 200 and raw_data is not None:
				# Success
				try:
					core_apis = json.loads(raw_data)
				except DecodeException:
					# We got a response, but the data is malformed
					return kubernetes_resources, 42422, False
			else:
				self.cluster_unreachable = True
				# We could not get the core APIs; there is no use continuing
				modified = True
				return kubernetes_resources, status, modified

			# Flush the entire API list
			for _resource_kind, resource_data in kubernetes_resources.items():
				resource_data["available"] = False

			for api in deep_get(core_apis, DictPath("resources"), []):
				if "list" not in deep_get(api, DictPath("verbs"), []):
					# Ignore non-list APIs
					continue
				name = deep_get(api, DictPath("name"), "")
				kind = deep_get(api, DictPath("kind"), "")
				if (kind, "") in kubernetes_resources:
					kubernetes_resources[(kind, "")]["available"] = True

			# Attempt aggregated discovery; we need custom header_params to do this.
			# Fallback to the old method if aggregate discovery isn't supported.
			header_params = {
				"Accept": "application/json;g=apidiscovery.k8s.io;v=v2beta1;as=APIGroupDiscoveryList,application/json",
				"Content-Type": "application/json",
				"User-Agent": f"{self.programname} v{self.programversion}",
			}
			aggregated_data = {}

			url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/apis"
			raw_data, _message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = method, url = url, header_params = header_params)
			if status == 200 and raw_data is not None:
				# Success
				try:
					aggregated_data = json.loads(raw_data)
				except DecodeException:
					# We got a response, but the data is malformed
					return kubernetes_resources, 42422, False

			# These are all API-groups we know of
			_api_groups = set(api_group for kind, api_group in kubernetes_resources)

			# We successfully got aggregated data
			if deep_get(aggregated_data, DictPath("kind"), "") == "APIGroupDiscoveryList":
				for api_group in deep_get(aggregated_data, DictPath("items"), []):
					name = deep_get(api_group, DictPath("metadata#name"), "")
					known_api_group = name in _api_groups
					if not known_api_group:
						continue

					versions = deep_get(api_group, DictPath("versions"), [])

					# Now we need to check what kinds this api_group supports
					# and using what version
					for version in versions:
						_version = deep_get(version, DictPath("version"))
						if _version is None:
							# This should not happen, but ignore it
							continue
						resources = deep_get(version, DictPath("resources"), [])
						for resource in resources:
							if "list" not in deep_get(resource, DictPath("verbs"), []):
								continue
							kind = deep_get(resource, DictPath("responseKind#kind"), "")
							if len(kind) == 0:
								continue
							if (kind, name) in kubernetes_resources and \
									f"apis/{name}/{_version}/" in kubernetes_resources[(kind, name)].get("api_paths", ""):
								kubernetes_resources[(kind, name)]["available"] = True
								continue
				modified = True
				return kubernetes_resources, status, modified

			# Nope, this is only non-core APIs
			non_core_apis = aggregated_data

			for api_group in deep_get(non_core_apis, DictPath("groups"), []):
				name = deep_get(api_group, DictPath("name"), "")
				known_api_group = name in _api_groups
				if not known_api_group:
					continue

				versions = deep_get(api_group, DictPath("versions"), [])

				# Now we need to check what kinds this api_group supports
				# and using what version
				for version in versions:
					_version = deep_get(version, DictPath("groupVersion"))
					if _version is None:
						# This should not happen, but ignore it
						continue
					url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/apis/{_version}"
					raw_data, _message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = method, url = url)

					if status != 200 or raw_data is None:
						# Could not get API info; this is worrying, but ignore it
						continue
					try:
						data = json.loads(raw_data)
					except DecodeException:
						# We got a response, but the data is malformed
						continue

					for resource in deep_get(data, DictPath("resources"), []):
						if "list" not in deep_get(resource, DictPath("verbs"), []):
							continue
						kind = deep_get(resource, DictPath("kind"), "")
						if len(kind) == 0:
							continue
						if (kind, name) in kubernetes_resources and f"apis/{_version}/" in kubernetes_resources[(kind, name)].get("api_paths", ""):
							if (kind, name) in kubernetes_resources:
								kubernetes_resources[(kind, name)]["available"] = True
							continue

		modified = True
		return kubernetes_resources, status, modified

	def is_kind_available(self, kind: Tuple[str, str]) -> bool:
		"""
		Checks whether a kind tuple is available or not

			Parameters:
				kind ((str, str)): The kind tuple
			Returns:
				(bool): True if the kind is available, False if not
		"""
		try:
			available = deep_get(kubernetes_resources[kind], DictPath("available"), False)
		except NameError:
			available = False
		return available

	def get_list_of_namespaced_resources(self) -> List[Tuple[str, str]]:
		"""
		Returns a list of all namespaced resources that are available in the cluster

			Returns:
				vlist (List[(kind, api_group)]): A list of namespaced kinds
		"""

		vlist = []

		for resource_kind, resource_data in kubernetes_resources.items():
			if deep_get(resource_data, DictPath("namespaced"), True) \
			   and deep_get(resource_data, DictPath("available"), True):
				vlist.append(resource_kind)
		return vlist

	# pylint: disable-next=too-many-arguments
	def __rest_helper_generic_json(self, *, pool_manager: Tuple[urllib3.PoolManager, urllib3.ProxyManager], method: Optional[str] = None,
				       url: Optional[str] = None, header_params: Optional[Dict] = None,
				       query_params: Optional[Sequence[Optional[Tuple[str, Any]]]] = None, body: Optional[bytes] = None,
				       retries: int = 3, connect_timeout: float = 3.0) -> Tuple[Union[AnyStr, None], str, int]:

		if pool_manager is None:
			raise ProgrammingError("__rest_helper_generic_json() should never be called without a pool_manager")

		if query_params is None:
			query_params = []

		if self.cluster_unreachable:
			message = "Cluster Unreachable"
			return None, "", 42503

		if header_params is None:
			header_params = {
				"Accept": "application/json",
				"Content-Type": "application/json",
				"User-Agent": f"{self.programname} v{self.programversion}",
			}

		if self.token is not None:
			header_params["Authorization"] = f"Bearer {self.token}"

		if method is None:
			raise ValueError("REST API called without method; this is a programming error!")

		if url is None:
			raise ValueError("REST API called without URL; this is a programming error!")

		if retries == 0:
			_retries = False
		else:
			_retries = urllib3.Retry(retries)  # type: ignore

		data = None
		message = ""

		reauth_retry = 1

		while reauth_retry > 0:
			try:
				if body is not None:
					result = pool_manager.request(method, url, headers = header_params, body = body, timeout = urllib3.Timeout(connect = connect_timeout), retries = _retries)  # type: ignore
				else:
					result = pool_manager.request(method, url, headers = header_params, fields = query_params, timeout = urllib3.Timeout(connect = connect_timeout), retries = _retries)  # type: ignore
				status = result.status
			except urllib3.exceptions.MaxRetryError as e:
				# No route to host does not have a HTTP response; make one up...
				# 503 is Service Unavailable; this is generally temporary, but to distinguish it from a real 503
				# we prefix it...
				if "CERTIFICATE_VERIFY_FAILED" in str(e):
					# Client Handshake Failed (Cloudflare)
					status = 525
					if "certificate verify failed" in str(e):
						tmp = re.match(r".*SSL: CERTIFICATE_VERIFY_FAILED.*certificate verify failed: (.*) \(_ssl.*", str(e))
						if tmp is not None:
							message = f"; {tmp[1]}"
				else:
					status = 42503
			except urllib3.exceptions.ConnectTimeoutError:
				# Connection timed out; the API-server might not be available, suffer from too high load, or similar
				# 504 is Gateway Timeout; using 42504 to indicate connection timeout thus seems reasonable
				status = 42504

			# We don't want to try to renew the token multiple times
			if reauth_retry == 42:
				break

			if status in (401, 403):
				# Unauthorized:
				# Try to renew the token then retry
				if self.token is not None:
					with renew_lock:
						self.renew_token(self.cluster_name, self.context_name)
					header_params["Authorization"] = f"Bearer {self.token}"
				reauth_retry = 42
			else:
				reauth_retry = 0

		if status == 200:
			# YAY, things went fine!
			data = result.data
		elif status == 201:
			# Created
			# (Assuming we tried to create something this means success
			data = result.data
		elif status == 202:
			# Accepted
			# (Operation queued for batch processing; no further status available; returned when deleting things with a finalizer)
			pass
		elif status == 204:
			# No Content
			pass
		elif status == 400:
			# Bad request
			# The feature might be disabled, or the pod is waiting to start/terminated
			try:
				d = json.loads(result.data)
				message = "400: Bad Request; " + deep_get(d, DictPath("message"), "")
			except DecodeException:
				# We got a response, but the data is malformed
				message = "400: Bad Request [return data invalid]"
		elif status == 401:
			# Unauthorized:
			message = f"401: Unauthorized; method: {method}, URL: {url}, header_params: {header_params}"
		elif status == 403:
			# Forbidden: request denied
			message = f"403: Forbidden; method: {method}, URL: {url}, header_params: {header_params}"
		elif status == 404:
			# page not found (API not available or possibly programming error)
			message = f"404: Not Found; method: {method}, URL: {url}, header_params: {header_params}"
		elif status == 405:
			# Method not allowed
			raise TypeError(f"405: Method Not Allowed; this is probably a programming error; method: {method}, URL: {url}; header_params: {header_params}")
		elif status == 406:
			# Not Acceptable
			raise TypeError(f"406: Not Acceptable; this is probably a programming error; method: {method}, URL: {url}; header_params: {header_params}")
		elif status == 410:
			# Gone
			# Most likely a update events were requested (using resourceVersion), but it has been too long since the previous request;
			# caller should retry without &resourceVersion=xxxxx
			pass
		elif status == 415:
			# Unsupported Media Type
			# The server refused to accept the request because the payload was in an unsupported format; check Content-Type, Content-Encoding, and the data itself.
			raise TypeError(f"415: Unsupported Media Type; this is probably a programming error; method: {method}, URL: {url}; header_params: {header_params}")
		elif status == 422:
			# Unprocessable entity
			# The content and syntax is correct, but the request cannot be processed
			msg = result.data.decode("utf-8", errors = "replace")
			message = f"422: Unprocessable Entity; method: {method}, URL: {url}; header_params: {header_params}; message: {msg}"
		elif status == 500:
			# Internal Server Error
			msg = result.data.decode("utf-8", errors = "replace")
			message = f"500: Internal Server Error; method: {method}, URL: {url}; header_params: {header_params}; message: {msg}"
		elif status == 502:
			# Bad Gateway
			# Either a malfunctioning or a malicious proxy
			message = "502: Bad Gateway"
		elif status == 503:
			# Service Unavailable
			# This might be a CRD that has failed to deploy properly
			message = f"503: Service Unavailable; method: {method}, URL: {url}; header_params: {header_params}"
		elif status == 504:
			# Gateway Timeout
			# A request was made for an unrecognised resourceVersion, and timed out waiting for it to become available
			message = f"504: Gateway Timeout; method: {method}, URL: {url}; header_params: {header_params}"
		elif status == 525:
			# SSL Handshake Failed (Cloudflare)
			message = f"525: Client Handshake Failed{message}"
		elif status == 42503:
			message = f"No route to host; method: {method}, URL: {url}; header_params: {header_params}"
		else:
			#debuglog.add([
			#		[ANSIThemeString("__rest_helper_generic_json():", "emphasis")],
			#		[ANSIThemeString(f"Unhandled error: {result.status}", "error")],
			#		[ANSIThemeString("method: ", "emphasis"),
			#		 ANSIThemeString(f"{method}", "argument")],
			#		[ANSIThemeString("URL: ", "emphasis"),
			#		 ANSIThemeString(f"{url}", "argument")],
			#		[ANSIThemeString("header_params: ", "emphasis"),
			#		 ANSIThemeString(f"{header_params}", "argument")],
			#       ], severity = LogLevel.ERR)
			sys.exit(f"__rest_helper_generic_json():\nUnhandled error: {result.status}\nmethod: {method}\nURL: {url}\nheader_params: {header_params}")

		return data, message, status

	def __rest_helper_post(self, kind: Tuple[str, str], *, name: str = "", namespace: str = "", body: Optional[bytes] = None) -> Tuple[str, int]:
		method = "POST"

		if body is None or len(body) == 0:
			raise ValueError("__rest_helper_post called with empty body; this is most likely a programming error")

		header_params = {
			"Content-Type": "application/json",
			"User-Agent": f"{self.programname} v{self.programversion}",
		}

		namespace_part = ""
		if namespace is not None and namespace != "":
			namespace_part = f"namespaces/{namespace}/"

		if kind is None:
			raise ValueError("__rest_helper_post called with kind None; this is most likely a programming error")

		kind = guess_kind(kind)

		if kind in kubernetes_resources:
			api_paths = deep_get(kubernetes_resources[kind], DictPath("api_paths"))
			api = deep_get(kubernetes_resources[kind], DictPath("api"))
			namespaced = deep_get(kubernetes_resources[kind], DictPath("namespaced"), True)
		else:
			raise ValueError(f"kind unknown: {kind}")

		fullitem = f"{kind[0]}.{kind[1]} {name}"
		if namespaced:
			fullitem = f"{fullitem} (namespace: {namespace})"

		name = f"/{name}"

		if not namespaced:
			namespace_part = ""

		status = 42503

		# Try the newest API first and iterate backwards
		with PoolManagerContext(cert_file = self.cert_file, key_file = self.key_file, ca_certs_file = self.ca_certs_file, token = self.token, insecuretlsskipverify = self.insecuretlsskipverify) as pool_manager:
			for api_path in api_paths:
				url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/{api_path}{namespace_part}{api}{name}"
				_data, message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = method, url = url, header_params = header_params, body = body)
				if status in (200, 201, 204, 42503):
					break

		return message, status

	# pylint: disable-next=too-many-arguments
	def __rest_helper_patch(self, kind: Tuple[str, str], *, name: str, namespace: str = "", strategic_merge: bool = True, subresource: str = "", body: Optional[bytes] = None) -> Tuple[str, int]:
		method = "PATCH"

		header_params = {
			"User-Agent": f"{self.programname} v{self.programversion}",
		}

		if strategic_merge:
			header_params["Content-Type"] = "application/strategic-merge-patch+json"
		else:
			header_params["Content-Type"] = "application/merge-patch+json"

		if body is None or len(body) == 0:
			raise ValueError("__rest_helper_patch called with empty body; this is most likely a programming error")

		namespace_part = ""
		if namespace is not None and namespace != "":
			namespace_part = f"namespaces/{namespace}/"

		subresource_part = ""
		if subresource is not None and subresource != "":
			subresource_part = f"/{subresource}"

		if kind is None:
			raise ValueError("__rest_helper_patch called with kind None; this is most likely a programming error")

		kind = guess_kind(kind)

		if kind in kubernetes_resources:
			api_paths = deep_get(kubernetes_resources[kind], DictPath("api_paths"))
			api = deep_get(kubernetes_resources[kind], DictPath("api"))
			namespaced = deep_get(kubernetes_resources[kind], DictPath("namespaced"), True)
		else:
			raise ValueError(f"kind unknown: {kind}")

		fullitem = f"{kind[0]}.{kind[1]} {name}"
		if namespaced:
			fullitem = f"{fullitem} (namespace: {namespace})"

		name = f"/{name}"

		if not namespaced:
			namespace_part = ""

		message = ""
		status = 42503

		# Try the newest API first and iterate backwards
		with PoolManagerContext(cert_file = self.cert_file, key_file = self.key_file, ca_certs_file = self.ca_certs_file, token = self.token, insecuretlsskipverify = self.insecuretlsskipverify) as pool_manager:
			for api_path in api_paths:
				url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/{api_path}{namespace_part}{api}{name}{subresource_part}"
				_data, message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = method, url = url, header_params = header_params, body = body)
				if status in (200, 204, 42503):
					break

		return message, status

	def __rest_helper_delete(self, kind: Tuple[str, str], *, name: str, namespace: str = "", query_params: Optional[Sequence[Optional[Tuple[str, Any]]]] = None) -> Tuple[str, int]:
		method = "DELETE"

		if query_params is None:
			query_params = []

		namespace_part = ""
		if namespace is not None and namespace != "":
			namespace_part = f"namespaces/{namespace}/"

		if kind is None:
			raise ValueError("__rest_helper_delete called with kind None; this is most likely a programming error")

		kind = guess_kind(kind)

		if kind in kubernetes_resources:
			api_paths = deep_get(kubernetes_resources[kind], DictPath("api_paths"))
			api = deep_get(kubernetes_resources[kind], DictPath("api"))
			namespaced = deep_get(kubernetes_resources[kind], DictPath("namespaced"), True)
		else:
			raise ValueError(f"kind unknown: {kind}")

		fullitem = f"{kind[0]}.{kind[1]} {name}"
		if namespaced:
			fullitem = f"{fullitem} (namespace: {namespace})"

		name = f"/{name}"

		if not namespaced:
			namespace_part = ""

		status = 42503

		# Try the newest API first and iterate backwards
		with PoolManagerContext(cert_file = self.cert_file, key_file = self.key_file, ca_certs_file = self.ca_certs_file, token = self.token, insecuretlsskipverify = self.insecuretlsskipverify) as pool_manager:
			for api_path in api_paths:
				url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/{api_path}{namespace_part}{api}{name}"
				_data, message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = method, url = url, query_params = query_params)
				if status in (200, 202, 204, 42503):
					break

		return message, status

	# On failure this function should always return [] for list requests, and None for other requests;
	# this way lists the result can be handled unconditionally in for loops

	# pylint: disable-next=too-many-arguments
	def __rest_helper_get(self, *, kind: Optional[Tuple[str, str]] = None, raw_path: Optional[str] = None, name: str = "", namespace: str = "",
			      label_selector: str = "", field_selector: str = "") -> Tuple[Union[Optional[Dict], List[Optional[Dict]]], int]:
		if kind is None and raw_path is None:
			raise ValueError("__rest_helper_get API called with kind None and raw_path None; this is most likely a programming error")

		if self.cluster_unreachable:
			# Our arbitrary return value for Cluster Unreachable
			status = 42503

			# If name is not set this is a list request, so return an empty list instead of None
			if name == "" and not raw_path:
				return [], status
			return None, status

		query_params: List[Optional[Tuple[str, Any]]] = []
		if field_selector != "":
			query_params.append(("fieldSelector", field_selector))
		if label_selector != "":
			query_params.append(("labelSelector", label_selector))

		method = "GET"

		namespace_part = ""
		if namespace is not None and namespace != "":
			namespace_part = f"namespaces/{namespace}/"

		if raw_path is None:
			kind = guess_kind(cast(Tuple[str, str], kind))
			if kind in kubernetes_resources:
				api_paths = deep_get(kubernetes_resources[kind], DictPath("api_paths"))
				api = deep_get(kubernetes_resources[kind], DictPath("api"))
				namespaced = deep_get(kubernetes_resources[kind], DictPath("namespaced"), True)
			else:
				raise ValueError(f"kind unknown: {kind}; this is most likely a programming error")
		else:
			api_paths = [raw_path]
			api = ""
			namespaced = False

		if name != "":
			name = f"/{name}"

		if not namespaced:
			namespace_part = ""

		status = 42503

		# Try the newest API first and iterate backwards
		with PoolManagerContext(cert_file = self.cert_file, key_file = self.key_file, ca_certs_file = self.ca_certs_file, token = self.token, insecuretlsskipverify = self.insecuretlsskipverify) as pool_manager:
			for api_path in api_paths:
				url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/{api_path}{namespace_part}{api}{name}"
				raw_data, _message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = method, url = url, query_params = query_params)

				# All fatal failures are handled in __rest_helper_generic
				if status == 200 and raw_data is not None:
					# Success
					try:
						d = json.loads(raw_data)
					except DecodeException:
						# We got a response, but the data is malformed; skip the entry
						continue

					# If name is set this is a read request, not a list request
					if raw_path or name != "":
						return d, status
					return deep_get(d, DictPath("items"), []), status

				if status in (204, 400, 403, 503):
					# We did not get any data, but we might not want to fail
					continue

				#if status == 404:
					# We did not get any data, but we might not want to fail

					# page not found (API not available or possibly programming error)
					# raise UnknownError(f"API not available; this is probably a programming error; URL {url}")

				#if status == 410:
					# XXX: Should be handled when we implement support for update events

					# Gone
					# We requested update events (using resourceVersion), but it has been too long since the previous request;
					# retry without &resourceVersion=xxxxx

		# If name is not set this is a list request, so return an empty list instead of None
		if name == "":
			return [], status

		return None, status

	def get_api_server_version(self) -> Tuple[int, int, str]:
		"""
		Get API-server version

			Returns:
				(server_major_version, server_minor_version, server_git_version):
					server_major_version (int): Major API-server version
					server_minor_version (int): Minor API-server version
					server_git_version (str): API-server GIT version
		"""

		ref, _status = self.__rest_helper_get(raw_path = "version")
		ref = cast(Dict, ref)
		server_major_version = deep_get(ref, DictPath("major"), "")
		server_minor_version = deep_get(ref, DictPath("minor"), "")
		server_git_version = deep_get(ref, DictPath("gitVersion"), "")
		if (tmp := re.match(r"^v?(\d+?)\.(\d+?)\.(\d+?)$", server_git_version)) is not None:
			server_git_version = f"{tmp[1]}.{tmp[2]}.{tmp[3]}"

		return server_major_version, server_minor_version, server_git_version

	def create_namespace(self, name: str) -> Tuple[str, int]:
		"""
		Create a new namespace

			Parameters:
				name (str): The name of the new namespace
			Returns:
				(message, status):
					message (str): The status message, if any
					status (int): The HTTP response
		"""

		kind = ("Namespace", "")

		if name is None or len(name) == 0:
			return "", 200

		data = {
			"kind": "Namespace",
			"apiVersion": "v1",
			"metadata": {
				"creationTimestamp": None,
				"name": name,
			},
			"spec": {},
			"status": {},
		}

		body = json.dumps(data).encode("utf-8")
		return self.__rest_helper_post(kind = kind, body = body)

	def taint_node(self, node: str, taints: List[Dict], new_taint: Tuple[str, Optional[str], Optional[str], Optional[str]], overwrite: bool = False) -> Tuple[str, int]:
		"""
		Apply a new taint, replace an existing taint, or remove a taint for a node

			Parameters:
				node (str): The node to taint
				taints (list[dict]): The current taints
				new_taint ((key, value, old_effect, new_effect): The modified or new taint
				overwrite (bool): If overwrite is set, modify the taint, otherwise return
			Returns:
				the return value from __rest_helper_patch
		"""

		kind = ("Node", "")
		if new_taint is None:
			return "", 304

		key, value, old_effect, new_effect = new_taint
		modified_taints = []
		modified = False

		for taint in taints:
			# If the taint is not the one to modify we keep it
			if deep_get(taint, DictPath("key")) != key:
				modified_taints.append(taint)
				continue

			_old_value = deep_get(taint, DictPath("value"))
			_old_effect = deep_get(taint, DictPath("effect"))

			# Do we want to *remove* the taint?
			if new_effect is None:
				# If old_effect is None we remove taints matching this key or key=value
				# If old_effect is not None we remove taints matching key=value:effect
				# value is None: remove all taints for key
				# value == value: remove the taint for this key=value
				if (old_effect is None or _old_effect == old_effect) and (value is None or _old_value == value):
					modified = True
					continue

			if _old_effect == new_effect:
				if not overwrite:
					# We already have the right taint,
					# and we do not want to overwrite it
					return "", 42304

				tmp = {
					"key": key,
					"effect": new_effect,
				}

				if value is not None:
					tmp["value"] = value
				modified_taints.append(tmp)
				modified = True
				continue

			# Same key, but different effect; we keep the taint
			modified_taints.append(taint)

		if not modified:
			if new_effect is None:
				return "", 304

			tmp = {
				"key": key,
				"effect": new_effect,
			}

			if value is not None:
				tmp["value"] = value
			modified_taints.append(tmp)

		data = {
			"spec": {
				"taints": modified_taints
			}
		}
		body = json.dumps(data).encode("utf-8")
		return self.__rest_helper_patch(kind = kind, name = node, body = body)

	def cordon_node(self, node: str) -> Tuple[str, int]:
		"""
		Cordon a Node

			Parameters:
				node (str): The node to cordon
			Returns:
				the return value from __rest_helper_patch
		"""

		kind = ("Node", "")
		data = {
			"spec": {
				"unschedulable": True
			}
		}
		body = json.dumps(data).encode("utf-8")
		return self.__rest_helper_patch(kind = kind, name = node, body = body)

	def uncordon_node(self, node: str) -> Tuple[str, int]:
		"""
		Uncordon a Node

			Parameters:
				node (str): The node to uncordon
			Returns:
a				the return value from __rest_helper_patch
		"""

		kind = ("Node", "")
		data = {
			"spec": {
				"unschedulable": None
			}
		}
		body = json.dumps(data).encode("utf-8")
		return self.__rest_helper_patch(kind, name = node, body = body)

	# pylint: disable-next=too-many-arguments
	def patch_obj_by_kind_name_namespace(self, kind: Tuple[str, str], name: str, namespace: str, patch: Dict, subresource: str = "", strategic_merge: bool = True) -> Tuple[str, int]:
		"""
		Patch an object

			Parameters:
				kind ((kind, api_group)): Kind of object to patch
				name (str): The name of the object
				namespace (str): The namespace of the object (or "")
				subresource (str): The subresource of the object (or "")
				strategic_merge (bool): True to use strategic merge
			Returns:
				the return value from __rest_helper_delete
		"""
		body = json.dumps(patch).encode("utf-8")
		return self.__rest_helper_patch(kind = kind, name = name, namespace = namespace, body = body, subresource = subresource, strategic_merge = strategic_merge)

	def delete_obj_by_kind_name_namespace(self, kind: Tuple[str, str], name: str, namespace: str, force: bool = False) -> Tuple[str, int]:
		"""
		Delete an object

			Parameters:
				kind ((kind, api_group)): Kind of object to delete
				name (str): The name of the object
				namespace (str): The namespace of the object (or "")
				force (bool): True = no grace period
			Returns:
				the return value from __rest_helper_delete
		"""

		query_params: List[Optional[Tuple[str, Any]]] = []

		if force:
			query_params.append(("gracePeriodSeconds", 0))

		return self.__rest_helper_delete(kind = kind, name = name, namespace = namespace, query_params = query_params)

	def get_metrics(self) -> Tuple[List[str], int]:
		"""
		Get cluster metrics

			Returns:
				(metrics, status):
					metrics (list[str]): The metrics
					status (int): The HTTP response
		"""

		msg: List[str] = []
		status = 42503

		if self.cluster_unreachable:
			return msg, status

		query_params: List[Optional[Tuple[str, Any]]] = []
		url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/metrics"
		with PoolManagerContext(cert_file = self.cert_file, key_file = self.key_file, ca_certs_file = self.ca_certs_file, token = self.token, insecuretlsskipverify = self.insecuretlsskipverify) as pool_manager:
			data, _message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = "GET", url = url, query_params = query_params)
			if status == 200 and data is not None:
				if isinstance(data, bytes):
					msg = data.decode("utf-8", errors = "replace").splitlines()
				elif isinstance(data, str):
					msg = data.splitlines()
			elif status == 204:
				# No Content; pretend that everything is fine
				msg = []
				status = 200
			else:
				msg = []
		return msg, status

	def get_list_by_kind_namespace(self, kind: Tuple[str, str], namespace: str, label_selector: str = "", field_selector: str = "") -> Tuple[Union[Optional[Dict], List[Optional[Dict]]], int]:
		"""
		Given kind, namespace and optionally label and/or field selectors, return all matching resources

			Parameters:
				kind (str, str): A kind, API-group tuple
				namespace (str): The namespace of the resource (empty if the resource is not namespaced)
				label_selector (str): A label selector
				label_selector (str): A field selector
			Returns:
				(objects, status):
					objects (list[dict]): A list of object dicts
					status (int): The HTTP response
		"""

		d, status = self.__rest_helper_get(kind = kind, namespace = namespace, label_selector = label_selector, field_selector = field_selector)
		d = cast(List[Optional[Dict]], d)
		return d, status

	def get_ref_by_kind_name_namespace(self, kind: Tuple[str, str], name: str, namespace: str) -> Dict:
		"""
		Given kind, name, namespace return a resource

			Parameters:
				kind (str, str): A kind, API-group tuple
				name (str): The name of the resource
				namespace (str): The namespace of the resource (empty if the resource is not namespaced)
			Returns:
				object (dict): An object dict
		"""

		ref, _status = self.__rest_helper_get(kind = kind, name = name, namespace = namespace)
		ref = cast(Dict, ref)
		return ref

	def read_namespaced_pod_log(self, name: str, namespace: str, container: Optional[str] = None, tail_lines: int = 0) -> Tuple[str, int]:
		"""
		Read a pod log

			Parameters:
				name (str): The name of the pod
				namespace (str): The namespace of the pod
				container (str): The name of the container
				tail_lines (int): The amount of lines to return (0 returns all)
			Returns:
				(msg, status):
					msg (str): A string with all log messages
					status (int): The HTTP response
		"""

		msg = ""
		status = 42503

		query_params: List[Optional[Tuple[str, Any]]] = []
		if container is not None:
			query_params.append(("container", container))
		if tail_lines is not None:
			query_params.append(("tailLines", tail_lines))
		query_params.append(("timestamps", True))

		method = "GET"
		url = f"https://{self.control_plane_ip}:{self.control_plane_port}{self.control_plane_path}/api/v1/namespaces/{namespace}/pods/{name}/log"
		with PoolManagerContext(cert_file = self.cert_file, key_file = self.key_file, ca_certs_file = self.ca_certs_file, token = self.token, insecuretlsskipverify = self.insecuretlsskipverify) as pool_manager:
			data, message, status = self.__rest_helper_generic_json(pool_manager = pool_manager, method = method, url = url, query_params = query_params)

			if status == 200 and data is not None:
				if isinstance(data, bytes):
					msg = data.decode("utf-8", errors = "replace")
				elif isinstance(data, str):
					msg = data
			elif status == 204:
				# No Content
				msg = "No Content"
			else:
				msg = message

		return msg, status

	# Namespace must be the namespace of the resource; the owner reference itself lacks namespace
	# since owners have to reside in the same namespace as their owned resources
	def get_ref_from_owr(self, owr: Dict, namespace: str) -> Dict:
		"""
		Given an Owner Reference (OWR), returns resource of the owner

			Parameters:
				owr (dict): A reference to the owner of the resource
				namespace (str): The namespace of the resource
			Returns:
				object (dict): An object dict
		"""

		ref, _status = self.__rest_helper_get(kind = deep_get(owr, DictPath("kind")), name = deep_get(owr, DictPath("name")), namespace = namespace)
		ref = cast(dict, ref)
		return ref

	def get_events_by_kind_name_namespace(self, kind: Tuple[str, str], name: str, namespace: str) -> List[Tuple[str, str, str, str, str, str, str, str, str]]:
		"""
		Given kind, name, and namespace, returns all matching events

			Parameters:
				kind ((str, str)): A (kind, api_group) tuple
				name (str): The name of the resource
				namespace (str): The namespace of the resource
			Returns:
				events (list[(ev_namespace, ev_name, last_seen, status, reason, source, first_seen, count, message)]):
					ev_namespace (str): The namespace of the event
					ev_name (str): The name of the event
					last_seen (str): A string representation of the last seen datetime
					status (str): The event status
					reason (str): The reason for the event
					source (str): The source of the event
					first_seen (str): A string representation of the first seen datetime
					count (str): The number of times this event has been emitted
					message (str): A free-form explanation of the event
		"""

		events: List[Tuple[str, str, str, str, str, str, str, str, str]] = []
		vlist, _status = self.get_list_by_kind_namespace(("Event", "events.k8s.io"), "")
		if vlist is None or len(vlist) == 0 or _status != 200:
			return events

		for obj in vlist:
			obj = cast(Dict, obj)

			__involved_kind = deep_get_with_fallback(obj, [DictPath("regarding#kind"), DictPath("involvedObject#kind")])
			__involved_api_version = deep_get_with_fallback(obj, [DictPath("regarding#apiVersion"), DictPath("involvedObject#apiVersion")])
			involved_kind = self.kind_api_version_to_kind(__involved_kind, __involved_api_version)
			involved_name = deep_get_with_fallback(obj, [DictPath("regarding#name"), DictPath("involvedObject#name")])
			ev_name = deep_get(obj, DictPath("metadata#name"))
			ev_namespace = deep_get(obj, DictPath("metadata#namespace"), "")
			_last_seen = timestamp_to_datetime(deep_get_with_fallback(obj, [
				DictPath("series#lastObservedTime"),
				DictPath("deprecatedLastTimestamp"),
				DictPath("lastTimestamp"),
				DictPath("eventTime"),
				DictPath("deprecatedFirstTimestamp"),
				DictPath("firstTimestamp")]))
			last_seen = datetime_to_timestamp(_last_seen)
			status = deep_get(obj, DictPath("type"), "")
			reason = deep_get(obj, DictPath("reason"), "").replace("\\\"", "“").replace("\n", "\\n").rstrip()
			src_component = deep_get(obj, DictPath("reportingController"), "")
			if len(src_component) == 0:
				src_component = deep_get_with_fallback(obj, [DictPath("deprecatedSource#component"), DictPath("source#component")], "")
			src_host = deep_get(obj, DictPath("reportingInstance"), "")
			if len(src_host) == 0:
				src_host = deep_get_with_fallback(obj, [DictPath("deprecatedSource#host"), DictPath("source#host")], "")
			if len(src_component) == 0:
				source = src_host
			elif len(src_host) == 0:
				source = src_component
			else:
				source = f"{src_host}/{src_component}"
			_first_seen = timestamp_to_datetime(deep_get_with_fallback(obj, [DictPath("eventTime"), DictPath("deprecatedFirstTimestamp"), DictPath("firstTimestamp")]))
			first_seen = datetime_to_timestamp(_first_seen)

			count: str = deep_get_with_fallback(obj, [DictPath("series#count"), DictPath("deprecatedCount"), DictPath("count")], "")
			if count is None:
				count = ""
			else:
				count = str(count)
			message: str = deep_get(obj, DictPath("message"), "").replace("\\\"", "“").replace("\n", "\\n").rstrip()
			if kind == involved_kind and name == involved_name and ev_namespace == namespace:
				event = (str(ev_namespace), str(ev_name), last_seen, status, str(reason), str(source), first_seen, count, message)
				events.append(event)
		return events
