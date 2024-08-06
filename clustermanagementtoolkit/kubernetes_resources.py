#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
List of Kubernetes resources known by CMT.
"""

# pylint: disable=too-many-lines

from typing import Dict, List, Tuple, Union

# A list of all K8s resources we have some knowledge about
kubernetes_resources: Dict[Tuple[str, str], Dict[str, Union[List[str], str, bool]]] = {
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
        "api_paths": ["apis/admissionregistration.k8s.io/v1/",
                      "apis/admissionregistration.k8s.io/v1beta1/"],
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
        "api_paths": ["apis/admissionregistration.k8s.io/v1/",
                      "apis/admissionregistration.k8s.io/v1beta1/"],
        "api": "validatingwebhookconfigurations",
        "namespaced": False,
    },
    # apiextensions.k8s.io
    ("CustomResourceDefinition", "apiextensions.k8s.io"): {
        "api_paths": ["apis/apiextensions.k8s.io/v1/",
                      "apis/apiextensions.k8s.io/v1beta1/"],
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
        "api_paths": ["apis/autoscaling/v2/",
                      "apis/autoscaling/v2beta2/",
                      "apis/autoscaling/v1/"],
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
        "api_paths": ["apis/discovery.k8s.io/v1/",
                      "apis/discovery.k8s.io/v1beta1/"],
        "api": "endpointslices",
    },
    # events.k8s.io
    ("Event", "events.k8s.io"): {
        "api_paths": ["apis/events.k8s.io/v1/"],
        "api": "events",
    },
    # flowcontrol.apiserver.k8s.io
    ("FlowSchema", "flowcontrol.apiserver.k8s.io"): {
        "api_paths": ["apis/flowcontrol.apiserver.k8s.io/v1/",
                      "apis/flowcontrol.apiserver.k8s.io/v1beta3/",
                      "apis/flowcontrol.apiserver.k8s.io/v1beta2/",
                      "apis/flowcontrol.apiserver.k8s.io/v1beta1/"],
        "api": "flowschemas",
        "namespaced": False,
    },
    ("PriorityLevelConfiguration", "flowcontrol.apiserver.k8s.io"): {
        "api_paths": ["apis/flowcontrol.apiserver.k8s.io/v1/",
                      "apis/flowcontrol.apiserver.k8s.io/v1beta3/",
                      "apis/flowcontrol.apiserver.k8s.io/v1beta2/",
                      "apis/flowcontrol.apiserver.k8s.io/v1beta1/"],
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
        "api_paths": ["apis/networking.k8s.io/v1/",
                      "apis/networking.k8s.io/v1beta1/"],
        "api": "ingresses",
    },
    ("IngressClass", "networking.k8s.io"): {
        "api_paths": ["apis/networking.k8s.io/v1/",
                      "apis/networking.k8s.io/v1beta1/"],
        "api": "ingressclasses",
        "namespaced": False,
    },
    ("NetworkPolicy", "networking.k8s.io"): {
        "api_paths": ["apis/networking.k8s.io/v1/",
                      "apis/networking.k8s.io/v1beta1/"],
        "api": "networkpolicies",
    },
    ("ServiceCIDR", "networking.k8s.io"): {
        "api_paths": ["apis/networking.k8s.io/v1alpha1/"],
        "api": "servicecidrs",
        "namespaced": False,
    },
    # node.k8s.io
    ("RuntimeClass", "node.k8s.io"): {
        "api_paths": ["apis/node.k8s.io/v1/",
                      "apis/node.k8s.io/v1beta1/"],
        "api": "runtimeclasses",
        "namespaced": False,
    },
    # policy
    ("PodDisruptionBudget", "policy"): {
        "api_paths": ["apis/policy/v1/",
                      "apis/policy/v1beta1/"],
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
        "api_paths": ["apis/snapshot.storage.k8s.io/v1/",
                      "apis/snapshot.storage.k8s.io/v1beta1/"],
        "api": "volumesnapshots",
    },
    ("VolumeSnapshotClass", "snapshot.storage.k8s.io"): {
        "api_paths": ["apis/snapshot.storage.k8s.io/v1/",
                      "apis/snapshot.storage.k8s.io/v1beta1/"],
        "api": "volumesnapshotclasses",
        "namespaced": False,
    },
    ("VolumeSnapshotContent", "snapshot.storage.k8s.io"): {
        "api_paths": ["apis/snapshot.storage.k8s.io/v1/",
                      "apis/snapshot.storage.k8s.io/v1beta1/"],
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
        "api_paths": ["apis/storage.k8s.io/v1/",
                      "apis/storage.k8s.io/v1beta1/"],
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
        "api_paths": ["apis/acme.cert-manager.io/v1/",
                      "apis/acme.cert-manager.k8s.io/v1alpha2/",
                      "certmanager.k8s.io/v1alpha1/"],
        "api": "challenges",
    },
    ("Order", "acme.cert-manager.io"): {
        "api_paths": ["apis/acme.cert-manager.io/v1/",
                      "apis/acme.cert-manager.k8s.io/v1alpha2/",
                      "certmanager.k8s.io/v1alpha1/"],
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
    ("CDIConfig", "cdi.kubevirt.io"): {
        "api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
        "api": "cdiconfigs",
        "namespaced": False,
    },
    ("DataImportCron", "cdi.kubevirt.io"): {
        "api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
        "api": "dataimportcrons",
    },
    ("DataSource", "cdi.kubevirt.io"): {
        "api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
        "api": "datasources",
    },
    ("DataVolume", "cdi.kubevirt.io"): {
        "api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
        "api": "datavolumes",
    },
    ("ObjectTransfer", "cdi.kubevirt.io"): {
        "api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
        "api": "objecttransfers",
        "namespaced": False,
    },
    ("StorageProfile", "cdi.kubevirt.io"): {
        "api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
        "api": "storageprofiles",
        "namespaced": False,
    },
    ("VolumeCloneSource", "cdi.kubevirt.io"): {
        "api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
        "api": "volumeclonesources",
    },
    ("VolumeImportSource", "cdi.kubevirt.io"): {
        "api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
        "api": "volumeimportsources",
    },
    ("VolumeUploadSource", "cdi.kubevirt.io"): {
        "api_paths": ["apis/cdi.kubevirt.io/v1beta1/"],
        "api": "volumeuploadsources",
    },
    # cert-manager.io <= rename from: certmanager.k8s.io
    ("Certificate", "cert-manager.io"): {
        "api_paths": ["apis/cert-manager.io/v1/",
                      "apis/cert-manager.io/v1alpha2/",
                      "apis/certmanager.k8s.io/v1alpha1/"],
        "api": "certificates",
    },
    ("CertificateRequest", "cert-manager.io"): {
        "api_paths": ["apis/cert-manager.io/v1/",
                      "apis/cert-manager.io/v1alpha2/",
                      "apis/certmanager.k8s.io/v1alpha1/"],
        "api": "certificaterequests",
    },
    ("ClusterIssuer", "cert-manager.io"): {
        "api_paths": ["apis/cert-manager.io/v1/",
                      "apis/cert-manager.io/v1alpha2/",
                      "apis/certmanager.k8s.io/v1alpha1/"],
        "api": "clusterissuers",
        "namespaced": False,
    },
    ("Issuer", "cert-manager.io"): {
        "api_paths": ["apis/cert-manager.io/v1/",
                      "apis/cert-manager.io/v1alpha2/",
                      "apis/certmanager.k8s.io/v1alpha1/"],
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
    ("ClusterImagePolicy", "config.openshift.io"): {
        "api_paths": ["apis/config.openshift.io/v1alpha1/"],
        "api": "clusterimagepolicies",
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
    ("SupportBundleCollection", "controlplane.antrea.io"): {
        "api_paths": ["apis/controlplane.antrea.io/v1beta2/"],
        "api": "supportbundlecollections",
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
    ("BGPPolicy", "crd.antrea.io"): {
        "api_paths": ["apis/crd.antrea.io/v1alpha1/"],
        "api": "bgppolicies",
        "namespaced": False,
    },
    ("ClusterGroup", "crd.antrea.io"): {
        "api_paths": ["apis/crd.antrea.io/v1alpha3/",
                      "apis/crd.antrea.io/v1alpha2/"],
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
    ("NodeLatencyMonitor", "crd.antrea.io"): {
        "api_paths": ["apis/crd.antrea.io/v1alpha1/"],
        "api": "nodelatencymonitors",
        "namespaced": False,
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
    # hco.kubevirt.io
    ("HyperConverged", "hco.kubevirt.io"): {
        "api_paths": ["apis/hco.kubevirt.io/v1beta1/"],
        "api": "hyperconvergeds",
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
    # helm.toolkit.fluxcd.io
    ("HelmRelease", "helm.toolkit.fluxcd.io"): {
        "api_paths": ["apis/helm.toolkit.fluxcd.io/v2beta2/"],
        "api": "helmreleases",
    },
    # hostpathprovisioner.kubevirt.io
    ("HostPathProvisioner", "hostpathprovisioner.kubevirt.io"): {
        "api_paths": ["apis/hostpathprovisioner.kubevirt.io/v1beta1/"],
        "api": "hostpathprovisioners",
        "namespaced": False,
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
    # k8s.ovn.org
    ("AdminPolicyBasedExternalRoute", "k8s.ovn.org"): {
        "api_paths": ["apis/k8s.ovn.org/v1/"],
        "api": "adminpolicybasedexternalroutes",
        "namespaced": False,
    },
    ("EgressFirewall", "k8s.ovn.org"): {
        "api_paths": ["apis/k8s.ovn.org/v1/"],
        "api": "egressfirewalls",
    },
    ("EgressIP", "k8s.ovn.org"): {
        "api_paths": ["apis/k8s.ovn.org/v1/"],
        "api": "egressips",
        "namespaced": False,
    },
    ("EgressQoS", "k8s.ovn.org"): {
        "api_paths": ["apis/k8s.ovn.org/v1/"],
        "api": "egressqoses",
    },
    ("EgressService", "k8s.ovn.org"): {
        "api_paths": ["apis/k8s.ovn.org/v1/"],
        "api": "egressservices",
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
    # kmm.sigs.x-k8s.io
    ("Module", "kmm.sigs.x-k8s.io"): {
        "api_paths": ["apis/kmm.sigs.x-k8s.io/v1beta1/"],
        "api": "modules",
    },
    ("NodeModulesConfig", "kmm.sigs.x-k8s.io"): {
        "api_paths": ["apis/kmm.sigs.x-k8s.io/v1beta1/"],
        "api": "nodemodulesconfigs",
        "namespaced": False,
    },
    ("PreflightValidation", "kmm.sigs.x-k8s.io"): {
        "api_paths": ["apis/kmm.sigs.x-k8s.io/v1beta1/"],
        "api": "preflightvalidations",
        "namespaced": False,
    },
    ("PreflightValidationOCP", "kmm.sigs.x-k8s.io"): {
        "api_paths": ["apis/kmm.sigs.x-k8s.io/v1beta1/"],
        "api": "preflightvalidationsocp",
        "namespaced": False,
    },
    # kubeapps.com
    ("AppRepository", "kubeapps.com"): {
        "api_paths": ["apis/kubeapps.com/v1alpha1/"],
        "api": "apprepositories",
    },
    # kubefledged.io
    ("ImageCache", "kubefledged.io"): {
        "api_paths": ["apis/kubefledged.io/v1alpha2/"],
        "api": "imagecaches",
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
    # kustomize.toolkit.fluxcd.io
    ("Kustomization", "kustomize.toolkit.fluxcd.io"): {
        "api_paths": ["apis/kustomize.toolkit.fluxcd.io/v1/"],
        "api": "kustomizations",
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
    # lvm.topolvm.io
    ("LVMCluster", "lvm.topolvm.io"): {
        "api_paths": ["apis/lvm.topolvm.io/v1alpha1/"],
        "api": "lvmclusters",
    },
    ("LVMVolumeGroupNodeStatus", "lvm.topolvm.io"): {
        "api_paths": ["apis/lvm.topolvm.io/v1alpha1/"],
        "api": "lvmvolumegroupnodestatuses",
    },
    ("LVMVolumeGroup", "lvm.topolvm.io"): {
        "api_paths": ["apis/lvm.topolvm.io/v1alpha1/"],
        "api": "lvmvolumegroups",
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
    ("MachineConfigNode", "machineconfiguration.openshift.io"): {
        "api_paths": ["apis/machineconfiguration.openshift.io/v1alpha1/"],
        "api": "machineconfignodes",
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
    ("MachineOSBuild", "machineconfiguration.openshift.io"): {
        "api_paths": ["apis/machineconfiguration.openshift.io/v1alpha1/"],
        "api": "machineosbuilds",
        "namespaced": False,
    },
    ("MachineOSConfig", "machineconfiguration.openshift.io"): {
        "api_paths": ["apis/machineconfiguration.openshift.io/v1alpha1/"],
        "api": "machineosconfigs",
        "namespaced": False,
    },
    ("PinnedImageSet", "machineconfiguration.openshift.io"): {
        "api_paths": ["apis/machineconfiguration.openshift.io/v1alpha1/"],
        "api": "pinnedimagesets",
        "namespaced": False,
    },
    # machinelearning.seldon.io
    ("SeldonDeployment", "machinelearning.seldon.io"): {
        "api_paths": ["apis/machinelearning.seldon.io/v1/",
                      "apis/machinelearning.seldon.io/v1alpha3/",
                      "apis/machinelearning.seldon.io/v1alpha2/"],
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
    ("HardwareData", "metal3.io"): {
        "api_paths": ["apis/metal3.io/v1alpha1/"],
        "api": "hardwaredata",
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
    # mtq.kubevirt.io
    ("MTQ", "mtq.kubevirt.io"): {
        "api_paths": ["apis/mtq.kubevirt.io/v1alpha1/"],
        "api": "mtqs",
        "namespaced": False,
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
    # networkaddonsoperator.network.kubevirt.io
    ("NetworkAddonsConfig", "networkaddonsoperator.network.kubevirt.io"): {
        "api_paths": ["apis/networkaddonsoperator.network.kubevirt.io/v1/"],
        "api": "networkaddonsconfigs",
        "namespaced": False,
    },
    # network.openshift.io
    ("ClusterNetwork", "network.openshift.io"): {
        "api_paths": ["apis/network.openshift.io/v1/"],
        "api": "clusternetworks",
        "namespaced": False,
    },
    ("DNSNameResolver", "network.openshift.io"): {
        "api_paths": ["apis/network.openshift.io/v1alpha1/"],
        "api": "dnsnameresolvers",
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
    # nfd.openshift.io
    ("NodeFeatureDiscovery", "nfd.openshift.io"): {
        "api_paths": ["apis/nfd.openshift.io/v1/"],
        "api": "nodefeaturediscoveries",
    },
    ("NodeFeatureRule", "nfd.openshift.io"): {
        "api_paths": ["apis/nfd.openshift.io/v1alpha1/"],
        "api": "nodefeaturerules",
    },
    # nodeinfo.volcano.sh
    ("Numatopology", "nodeinfo.volcano.sh"): {
        "api_paths": ["apis/nodeinfo.volcano.sh/v1alpha1/"],
        "api": "numatopologies",
    },
    # notification.toolkit.fluxcd.io
    ("Receiver", "notification.toolkit.fluxcd.io"): {
        "api_paths": ["apis/notification.toolkit.fluxcd.io/v1/"],
        "api": "receivers",
    },
    ("Alert", "notification.toolkit.fluxcd.io"): {
        "api_paths": ["apis/notification.toolkit.fluxcd.io/v1beta3/"],
        "api": "alerts",
    },
    ("Provider", "notification.toolkit.fluxcd.io"): {
        "api_paths": ["apis/notification.toolkit.fluxcd.io/v1beta3/"],
        "api": "providers",
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
    # olm.operatorframework.io
    ("ClusterExtension", "olm.operatorframework.io"): {
        "api_paths": ["apis/olm.operatorframework.io/v1alpha1/"],
        "api": "clusterextensions",
        "namespaced": False,
    },
    ("Extension", "olm.operatorframework.io"): {
        "api_paths": ["apis/olm.operatorframework.io/v1alpha1/"],
        "api": "extensions",
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
    ("InsightsOperator", "operator.openshift.io"): {
        "api_paths": ["apis/operator.openshift.io/v1/"],
        "api": "insightsoperators",
        "namespaced": False,
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
    ("MachineConfiguration", "operator.openshift.io"): {
        "api_paths": ["apis/operator.openshift.io/v1/"],
        "api": "machineconfigurations",
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
    # policy.networking.k8s.io
    ("AdminNetworkPolicy", "policy.networking.k8s.io"): {
        "api_paths": ["apis/policy.networking.k8s.io/v1alpha1/"],
        "api": "adminnetworkpolicies",
        "namespaced": False,
    },
    ("BaselineAdminNetworkPolicy", "policy.networking.k8s.io"): {
        "api_paths": ["apis/policy.networking.k8s.io/v1alpha1/"],
        "api": "baselineadminnetworkpolicies",
        "namespaced": False,
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
    ("ResourceClaimParameters", "resource.k8s.io"): {
        "api_paths": ["apis/resource.k8s.io/v1alpha2/"],
        "api": "resourceclaimparameters",
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
    ("ResourceClassParameters", "resource.k8s.io"): {
        "api_paths": ["apis/resource.k8s.io/v1alpha2/"],
        "api": "resourceclassparameters",
    },
    ("ResourceSlice", "resource.k8s.io"): {
        "api_paths": ["apis/resource.k8s.io/v1alpha2/"],
        "api": "resourceslices",
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
        "api_paths": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/"],
        "api": "configurations",
    },
    ("DomainMapping", "serving.knative.dev"): {
        "api_paths": ["apis/serving.knative.dev/v1alpha1/"],
        "api": "domainmappings",
    },
    ("Revision", "serving.knative.dev"): {
        "api_paths": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/"],
        "api": "revisions",
    },
    ("Route", "serving.knative.dev"): {
        "api_paths": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/"],
        "api": "routes",
    },
    ("Service", "serving.knative.dev"): {
        "api_paths": ["apis/serving.knative.dev/v1/", "apis/serving.knative.dev/v1beta1/"],
        "api": "services",
    },
    # serving.kubeflow.org
    ("InferenceService", "serving.kubeflow.org"): {
        "api_paths": ["apis/serving.kubeflow.org/v1alpha2/",
                      "apis/serving.kubeflow.org/v1beta1/"],
        "api": "inferenceservices",
    },
    ("TrainedModel", "serving.kubeflow.org"): {
        "api_paths": ["apis/serving.kubeflow.org/v1alpha2/"],
        "api": "trainedmodels",
    },
    # sharedresource.openshift.io
    ("SharedConfigMap", "sharedresource.openshift.io"): {
        "api_paths": ["apis/sharedresource.openshift.io/v1alpha1/"],
        "api": "sharedconfigmaps",
        "namespaced": False,
    },
    ("SharedSecret", "sharedresource.openshift.io"): {
        "api_paths": ["apis/sharedresource.openshift.io/v1alpha1/"],
        "api": "sharedsecrets",
        "namespaced": False,
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
    # source.toolkit.fluxcd.io
    ("GitRepository", "source.toolkit.fluxcd.io"): {
        "api_paths": ["apis/source.toolkit.fluxcd.io/v1/"],
        "api": "gitrepositories",
    },
    ("Bucket", "source.toolkit.fluxcd.io"): {
        "api_paths": ["apis/source.toolkit.fluxcd.io/v1beta2/"],
        "api": "buckets",
    },
    ("HelmChart", "source.toolkit.fluxcd.io"): {
        "api_paths": ["apis/source.toolkit.fluxcd.io/v1beta2/"],
        "api": "helmcharts",
    },
    ("HelmRepository", "source.toolkit.fluxcd.io"): {
        "api_paths": ["apis/source.toolkit.fluxcd.io/v1beta2/"],
        "api": "helmrepositories",
    },
    ("OCIRepository", "source.toolkit.fluxcd.io"): {
        "api_paths": ["apis/source.toolkit.fluxcd.io/v1beta2/"],
        "api": "ocirepositories",
    },
    # specs.smi-spec.io
    ("HTTPRouteGroup", "specs.smi-spec.io"): {
        "api_paths": ["apis/specs.smi-spec.io/v1alpha4/",
                      "apis/specs.smi-spec.io/v1alpha3/",
                      "apis/specs.smi-spec.io/v1alpha3/"],
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
        "api_paths": ["apis/split.smi-spec.io/v1alpha4/",
                      "apis/split.smi-spec.io/v1alpha3/",
                      "apis/split.smi-spec.io/v1alpha2/",
                      "apis/split.smi-spec.io/v1alpha1/"],
        "api": "trafficsplits",
    },
    # ssp.kubevirt.io
    ("SSP", "ssp.kubevirt.io"): {
        "api_paths": ["apis/ssp.kubevirt.io/v1beta2/"],
        "api": "ssps",
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
    ("MulticastGroup", "stats.antrea.io"): {
        "api_paths": ["apis/stats.antrea.io/v1alpha1/"],
        "api": "multicastgroups",
        "namespaced": False,
    },
    ("NetworkPolicyStats", "stats.antrea.io"): {
        "api_paths": ["apis/stats.antrea.io/v1alpha1/"],
        "api": "networkpolicystats",
    },
    ("NodeLatencyStats", "stats.antrea.io"): {
        "api_paths": ["apis/stats.antrea.io/v1alpha1/"],
        "api": "nodelatencystats",
        "namespaced": False,
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
    # topolvm.io
    ("LogicalVolume", "topolvm.io"): {
        "api_paths": ["apis/topolvm.io/v1/"],
        "api": "logicalvolumes",
        "namespaced": False,
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
    # trust.cert-manager.io
    ("Bundle", "trust.cert-manager.io"): {
        "api_paths": ["apis/trust.cert-manager.io/v1alpha1/"],
        "api": "bundles",
        "namespaced": False,
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
    #   ("UserIdentityMapping", "user.openshift.io"): {
    #       "api_paths": ["apis/user.openshift.io/v1/"],
    #       "api": "useridentitymappings",
    #       "namespaced": False,
    #   },
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
    ("DataDownload", "velero.io"): {
        "api_paths": ["apis/velero.io/v2alpha1/"],
        "api": "datadownloads",
    },
    ("DataUpload", "velero.io"): {
        "api_paths": ["apis/velero.io/v2alpha1/"],
        "api": "datauploads",
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

kubernetes_resource_types: Dict[Tuple[str, str], str] = {
    ("AntreaAgentInfo", "crd.antrea.io"): "[antrea_agent_info]",
    ("AntreaControllerInfo", "crd.antrea.io"): "[antrea_controller_info]",
    ("CiliumEndpoint", "cilium.io"): "[cilium_endpoint]",
    ("ConfigAuditReport", "aquasecurity.github.io"): "[report]",
    ("ConfigMap", ""): "[configmap]",
    ("Container", ""): "[container]",
    ("Controller", ""): "[controller]",
    ("ControllerRevision", "apps"): "[controller_revision]",
    ("CronJob", "batch"): "[job_controller]",
    ("DaemonSet", "apps"): "[controller]",
    ("Deployment", "apps"): "[controller]",
    ("Endpoints", ""): "[endpoints]",
    ("EndpointSlice", "discovery.k8s.io"): "[endpoint_slice]",
    ("EphemeralContainer", ""): "[ephemeral_container]",
    ("ExposedSecretReport", "aquasecurity.github.io"): "[report]",
    ("Event", ""): "[event]",
    ("Event", "events.k8s.io"): "[event]",
    ("HorizontalPodAutoscaler", "autoscaling"): "[pod_autoscaler]",
    ("InfraAssessmentReport", "aquasecurity.github.io"): "[report]",
    ("Ingress", "networking.k8s.io"): "[ingress]",
    ("InitContainer", ""): "[init_container]",
    ("Job", "batch"): "[controller]",
    ("Lease", "coordination.k8s.io"): "[lease]",
    ("LimitRange", ""): "[limit]",
    ("MutatingWebhookConfiguration",
     "admissionregistration.k8s.io"): "[webhook_configuration]",
    ("Node", ""): "[node]",
    ("PersistentVolume", ""): "[volume]",
    ("PersistentVolumeClaim", ""): "[volume_claim]",
    ("Pod", ""): "[pod]",
    ("PodDisruptionBudget", "policy"): "[pod_disruption_budget]",
    ("PodMetrics", "metrics.k8s.io"): "[pod_metrics]",
    ("PriorityClass", "scheduling.k8s.io"): "[priority_class]",
    ("ReplicaSet", "apps"): "[controller]",
    ("ReplicationController", ""): "[controller]",
    ("ResourceClaim", "resource.k8s.io"): "[resource_claim]",
    ("Role", "rbac.authorization.k8s.io"): "[role]",
    ("RoleBinding", "rbac.authorization.k8s.io"): "[role_binding]",
    ("RuntimeClass", "node.k8s.io"): "[runtime_class]",
    ("SbomReport", "aquasecurity.github.io"): "[report]",
    ("Scheduler", ""): "[scheduler]",
    ("Secret", ""): "[secret]",
    ("Service", ""): "[service]",
    ("ServiceAccount", ""): "[service_account]",
    ("ServiceEntry", ""): "[service_entry]",
    ("StatefulSet", "apps"): "[controller]",
    ("TASPolicy", "telemetry.intel.com"): "[scheduling_policy]",
    ("TFJob", "kubeflow.org"): "[controller]",
    ("ValidatingWebhookConfiguration",
     "admissionregistration.k8s.io"): "[webhook_configuration]",
    ("VulnerabilityReport", "aquasecurity.github.io"): "[report]",
    ("Workflow", "argoproj.io"): "[controller]",
}
