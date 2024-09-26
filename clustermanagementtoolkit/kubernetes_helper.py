#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.8)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Kubernetes helpers used by CMT
"""

# pylint: disable=too-many-lines

import base64
import copy
from datetime import datetime
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
from pathlib import Path
import re
import ssl
import sys
import tempfile
import threading
from typing import Any, AnyStr, cast, Dict, List, Optional, Tuple, Union
try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import yaml; "
             "you may need to (re-)run `cmt-install` or `pip3 install PyYAML`; aborting.")

from cryptography import x509
from cryptography.hazmat.primitives import serialization

try:
    import urllib3  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import urllib3; "
             "you may need to (re-)run `cmt-install` or `pip3 install urllib3`; aborting.")

from clustermanagementtoolkit.cmtpaths import HOMEDIR, KUBE_CONFIG_FILE, KUBE_CREDENTIALS_FILE

from clustermanagementtoolkit import cmtlib

# from clustermanagementtoolkit.cmtlog import debuglog

# from clustermanagementtoolkit.cmttypes import LogLevel

from clustermanagementtoolkit.cmttypes import deep_get, deep_get_with_fallback, DictPath
from clustermanagementtoolkit.cmttypes import FilePath, FilePathAuditError, ProgrammingError
from clustermanagementtoolkit.cmttypes import SecurityChecks, SecurityPolicy, StatusGroup

from clustermanagementtoolkit.cmtio import execute_command_with_response, secure_which
from clustermanagementtoolkit.cmtio import secure_read

from clustermanagementtoolkit.cmtio_yaml import secure_read_yaml, secure_write_yaml

from clustermanagementtoolkit.kubernetes_resources import kubernetes_resources
from clustermanagementtoolkit.kubernetes_resources import kubernetes_resource_types

# Acceptable ciphers
CIPHERS = [
    # TLS v1.3
    "TLS_AES_256_GCM_SHA384",
    # TLS v1.2
    "ECDHE-RSA-AES256-GCM-SHA384",
    "ECDHE-ECDSA-AES256-GCM-SHA384",
]

renew_lock = threading.Lock()


def get_pod_restarts_total(pod: Dict[str, Any]) -> Tuple[int, Union[int, datetime]]:
    """
    Given a Pod object, return the total number of restarts for all containers
    as well as the timestamp of the latest restart

        Parameters:
            pod (dict): The pod to return information about
        Returns:
            (int, int|datetime):
                (int): The number of restarts
                (int|datetime): The timestamp for the last restart
                        or -1 if number of restarts = 0
    """
    restarts = 0
    restarted_at: Union[int, datetime] = -1

    # for status in deep_get(pod, DictPath("status#initContainerStatuses"), []) \
    #               + deep_get(pod, DictPath("status#containerStatuses"), []):
    for status in deep_get(pod, DictPath("status#containerStatuses"), []):
        restart_count = deep_get(status, DictPath("restartCount"), 0)
        restarts += restart_count
        if restart_count:
            restart_ts = deep_get_with_fallback(status,
                                                [DictPath("state#running#startedAt"),
                                                 DictPath("lastState#terminated#finishedAt")])
            started_at = cmtlib.timestamp_to_datetime(restart_ts)
            if started_at is not None \
                    and (restarted_at == -1 or cast(datetime, restarted_at) < started_at):
                restarted_at = started_at

    if not restarts:
        restarted_at = -1
    return restarts, restarted_at


def get_containers(containers: List[Dict[str, Any]],
                   container_statuses: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """
    Given a list of containers and a list of container statuses,
    create a joined list with both pieces of information

        Parameters:
            containers ([dict]): The list of container info
            container_statuses ([dict]): The list of container statuses
        Returns:
            ([(str, str)]): The list of container info
    """
    container_dict = {}
    container_list = []

    for container in containers:
        container_name = deep_get(container, DictPath("name"))
        container_image = deep_get(container, DictPath("image"))
        image_version = get_image_version(container_image)
        container_dict[container_name] = image_version

    for container in container_statuses:
        container_name = deep_get(container, DictPath("name"))
        container_image = deep_get(container, DictPath("image"))
        if container_dict[container_name] == "<undefined>":
            image_version = get_image_version(container_image, "<undefined>")
            container_list.append((container_name, image_version))
        else:
            container_list.append((container_name, container_dict[container_name]))

    return container_list


def get_controller_from_owner_references(owner_references: List[Dict]) \
        -> Tuple[Tuple[str, str], str]:
    """
    Given an owner reference list, extract the controller (if any)

        Parameters:
            owner_references ([dict]): The list of owner references
        Returns:
            (((str, str), str)): A tuple made up of:
                ((str, str)): The controller kind
                (str): The controller name
    """
    controller = (("", ""), "")
    if owner_references is not None:
        api_group_regex = re.compile(r"^(.*)/.*")

        for owr in owner_references:
            if deep_get(owr, DictPath("controller"), False):
                api_version = deep_get(owr, DictPath("apiVersion"), "")
                tmp = api_group_regex.match(api_version)
                if tmp is not None:
                    api_group = tmp[1]
                else:
                    api_group = ""
                kind = (deep_get(owr, DictPath("kind")), api_group)
                controller = (kind, deep_get(owr, DictPath("name"), ""))

    return controller


def get_node_roles(node: Dict) -> List[str]:
    """
    Get a list of the roles that the node belongs to

        Parameters:
            node (dict): The node object
        Returns:
            ([str]): THe roles that the node belongs to
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


# We could probably merge this into kubernetes_resources?
def resource_kind_to_rtype(resource: Tuple[str, str]) -> str:
    """
    Given a kind return a resource type (basically a summary of what type is).

        Parameters:
            resource ((str, str)): The resource
        Returns:
            (str): A Resource type
    """
    return kubernetes_resource_types.get(resource, "[unknown]")


class KubernetesResourceCache:
    """
    A class for caching Kubernetes resources
    """
    updated = False

    def __init__(self) -> None:
        """
        Initialize the resource cache
        """
        self.resource_cache: Dict = {}

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

        # Some resources lack a UID (notably metrics);
        # let's not cache those.
        if not (uid := deep_get(resource, DictPath("metadata#uid"), "")):
            return

        resource_version = deep_get(resource, DictPath("metadata#resourceVersion"))
        if resource_version is None:
            raise ProgrammingError("KubernetesResourceCache.update_resource(): "
                                   "Attempt to add a resource with empty or None "
                                   "resourceVersion was made")
        if not resource_version:
            resource_version = "0"
        if uid not in self.resource_cache[kind]:
            self.resource_cache[kind]["resource_version"] = int(resource_version)
            self.resource_cache[kind]["resources"][uid] = copy.deepcopy(resource)
            self.updated = True
        elif deep_get(self.resource_cache[kind],
                      DictPath("uid#metadata#resourceVersion"), "0") < int(resource_version):
            # Only update if the new version has a resource version
            # strictly higher than the old version
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
        if resources is None or not resources:
            raise ProgrammingError("KubernetesResourceCache.update_resources(): "
                                   "resources is empty or None")

        for resource in resources:
            self.update_resource(kind, resource=resource)

    def get_resources(self, kind: Tuple[str, str], namespace: str = "",
                      label_selector: str = "", field_selector: str = "") -> List[Dict[str, Any]]:
        """
        Return a list with all resources of the specified kind

            Parameters:
                kind ((str, str)): The kind tuple for the resources
                namespace (str): The namespace of the resource (None to return all namespaces)
                label_selector (str): A label selector
                field_selector (str): A field selector
            Returns:
                ([dict]): The list of cached resources of the specified kind
        """
        if kind not in self.resource_cache:
            return []

        if namespace is not None and namespace or label_selector or field_selector:
            vlist = []
            field_selector_dict = {}
            for selector in field_selector.split(","):
                if not selector:
                    continue
                key, value = selector.split("=")
                key = key.replace(".", "#")
                field_selector_dict[key] = value
            label_selector_dict = {}
            for selector in label_selector.split(","):
                if not selector:
                    continue
                key, value = selector.split("=")
                key = key.replace(".", "#")
                label_selector_dict[f"metadata#labels#{key}"] = value

            for uid, resource in deep_get(self.resource_cache[kind],
                                          DictPath("resources"), {}).items():
                if deep_get(resource, DictPath("metadata#namespace"), "") != namespace:
                    continue
                for key, value in field_selector_dict.items():
                    if deep_get(resource, DictPath(key), "") != value:
                        continue
                for key, value in label_selector_dict.items():
                    if deep_get(resource, DictPath(key), "") != value:
                        continue
                vlist.append(resource)
            return vlist
        return [resource for uid, resource in deep_get(self.resource_cache[kind],
                                                       DictPath("resources"), {}).items()]

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
    def __init__(self, cert_file: Optional[str] = None, key_file: Optional[str] = None,
                 ca_certs_file: Optional[str] = None, token: Optional[str] = None,
                 insecuretlsskipverify: bool = False) -> None:
        self.pool_manager = None
        self.cert_file = cert_file
        self.key_file = key_file
        self.ca_certs_file = ca_certs_file
        self.token = token
        self.insecuretlsskipverify = insecuretlsskipverify

    def __enter__(self) -> Union[urllib3.ProxyManager, urllib3.PoolManager]:
        # Only permit a limited set of acceptable ciphers
        ssl_context = urllib3.util.ssl_.create_urllib3_context(ciphers=":".join(CIPHERS))
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

        if pool_manager_proxy:
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
            (str): The string representation of kind + API-group
    """
    name = ""

    if kind in kubernetes_resources:
        api = deep_get(kubernetes_resources[kind], DictPath("api"), "")
        name = f"{api}.{kind[1]}"
        name = name.rstrip(".")
    return name


# pylint: disable-next=too-many-branches
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
            (str, str):
                (str): The Kubernetes kind
                (str): The API-group
        Raises:
            NameError: No matching API could be found
            TypeError: kind is not a str or (str, str) tuple
    """
    if not isinstance(kind, (str, tuple)):
        raise TypeError(f"kind must be str or (str, str); got {repr(kind)}")
    if isinstance(kind, tuple) \
            and not (len(kind) == 2 and isinstance(kind[0], str) and isinstance(kind[1], str)):
        raise TypeError(f"kind must be str or (str, str); got {repr(kind)}")

    if isinstance(kind, str):
        if "." in kind:
            kind = cast(tuple, tuple(kind.split(".", maxsplit=1)))
        else:
            kind = (kind, "")

    # If we already have a tuple, do not guess
    if kind in kubernetes_resources:
        return cast(tuple, kind)

    if kind[0].startswith("__"):
        return cast(tuple, kind)

    guess = None

    # If we have a tuple that didn't match we can try
    # matching it against the api + api_group instead.
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


def update_api_status(kind: Tuple[str, str], listview: bool = False,
                      infoview: bool = False, local: bool = False) -> None:
    """
    Update kubernetes_resources for a kind to indicate
    whether or not there are list and infoviews for them

        Parameters:
            kind ((kind, api_group)): The kind tuple
            listview (bool): Does this kind have a list view
            infoview (bool): Does this kind have an info view
            local (bool): The view is a local addition
        Raises:
            TypeError: kind is not a (str, str) tuple
    """
    if not isinstance(kind, tuple) or isinstance(kind, tuple) \
            and not (len(kind) == 2 and isinstance(kind[0], str) and isinstance(kind[1], str)):
        raise TypeError("kind must be (str, str)")
    if not ((listview is None or isinstance(listview, bool))
            and (infoview is None or isinstance(infoview, bool))
            and (local is None or isinstance(local, bool))):
        raise TypeError("listview, infoview, and local must be either None or bool")

    # There are other kind of views than just Kubernetes APIs; just ignore them
    if kind not in kubernetes_resources:
        return
    kubernetes_resources[kind]["list"] = listview
    kubernetes_resources[kind]["info"] = infoview
    kubernetes_resources[kind]["local"] = local


def kubectl_get_version() -> Tuple[Optional[int], Optional[int], str,
                                   Optional[int], Optional[int], str]:
    """
    Get kubectl & API-server version

        Returns:
            (int, int, str, int, int, str):
                (int): Major client version
                (int): Minor client version
                (str): Client GIT version
                (int): Major API-server version
                (int): Minor API-server version
                (str): API-server GIT version
    """
    # Check kubectl version
    try:
        kubectl_path = secure_which(FilePath("/usr/bin/kubectl"),
                                    fallback_allowlist=["/etc/alternatives"],
                                    security_policy=SecurityPolicy.ALLOWLIST_RELAXED)
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
        kubectl_major_version = \
            int("".join(filter(str.isdigit, deep_get(kubectl_version, DictPath("major")))))
        kubectl_minor_version = \
            int("".join(filter(str.isdigit, deep_get(kubectl_version, DictPath("minor")))))
        kubectl_git_version = str(deep_get(kubectl_version, DictPath("gitVersion")))
    else:  # pragma: no cover
        kubectl_major_version = None
        kubectl_minor_version = None
        kubectl_git_version = "<unavailable>"
    if server_version is not None:
        server_major_version = \
            int("".join(filter(str.isdigit, deep_get(server_version, DictPath("major")))))
        server_minor_version = \
            int("".join(filter(str.isdigit, deep_get(server_version, DictPath("minor")))))
        server_git_version = str(deep_get(server_version, DictPath("gitVersion")))
    else:  # pragma: no cover
        server_major_version = None
        server_minor_version = None
        server_git_version = "<unavailable>"

    return kubectl_major_version, kubectl_minor_version, kubectl_git_version, \
        server_major_version, server_minor_version, server_git_version


# pylint: disable-next=too-many-branches
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

    # If we did not manage to do any splitting it means there was not a version;
    # return default instead
    if image_version == image:
        image_version = default
    return image_version


def list_contexts(config_path: Optional[FilePath] = None) \
        -> List[Tuple[bool, str, str, str, str, str]]:
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
        kubeconfig = secure_read_yaml(FilePath(config_path))
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
def set_context(config_path: Optional[FilePath] = None,
                name: Optional[str] = None) -> Optional[str]:
    """
    Change context

        Parameters:
            config_path (FilePath): The path to the kubeconfig file
            name (str): The context to change to
        Returns:
            context (str): The name of the new current-context, or None on failure
    """
    # We need a context name
    if name is None or not name:
        return None

    if config_path is None:
        # Read kubeconfig
        config_path = KUBE_CONFIG_FILE

    config_path = FilePath(config_path)

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
        kubeconfig = secure_read_yaml(config_path, checks=checks)
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
        secure_write_yaml(config_path, kubeconfig, permissions=0o600, sort_keys=False)

    return new_context


# pylint: disable-next=too-many-instance-attributes,too-many-public-methods
class KubernetesHelper:
    """
    A class used for interacting with a Kubernetes cluster
    """

    # There doesn't seem to be any better type-hint than Any
    # for NamedTemporaryFile for the time being.
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

    def list_contexts(self, config_path: Optional[FilePath] = None) \
            -> List[Tuple[bool, str, str, str, str, str]]:
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

        contexts = self.list_contexts(config_path=config_path)
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

    # pylint: disable-next=too-many-locals
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
            credentials = secure_read_yaml(KUBE_CREDENTIALS_FILE)
        except FilePathAuditError as e:
            if "SecurityStatus.PARENT_DOES_NOT_EXIST" in str(e) \
                    or "SecurityStatus.DOES_NOT_EXIST" in str(e):
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
        name = deep_get(credentials,
                        DictPath(f"clusters#{cluster_name}#contexts#{context_name}#name"), None)
        password = deep_get(credentials,
                            DictPath(f"clusters#{cluster_name}#contexts#{context_name}#password"),
                            None)

        if name is None or password is None:
            return

        # This only applies for CRC
        if "crc" in cluster_name:
            url = "https://oauth-openshift.apps-crc.testing/oauth/" \
                  "authorize?response_type=token&client_id=openshift-challenging-client"
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
                with PoolManagerContext(cert_file=self.cert_file, key_file=self.key_file,
                                        ca_certs_file=self.ca_certs_file, token=self.token,
                                        insecuretlsskipverify=self.insecuretlsskipverify) \
                        as pool_manager:
                    result = pool_manager.request("GET", url, headers=header_params,
                                                  timeout=urllib3.Timeout(connect=connect_timeout),
                                                  redirect=False)  # type: ignore
                    status = result.status
            except urllib3.exceptions.MaxRetryError as e:
                # No route to host does not have a HTTP response; make one up...
                # 503 is Service Unavailable; this is generally temporary,
                # but to distinguish it from a real 503 we prefix it...
                if "CERTIFICATE_VERIFY_FAILED" in str(e):
                    # Client Handshake Failed (Cloudflare)
                    status = 525
                else:
                    status = 42503
            except urllib3.exceptions.ConnectTimeoutError:
                # Connection timed out; the API-server might not be available,
                # suffer from too high load, or similar
                # 504 is Gateway Timeout; using 42504 to indicate
                # connection timeout thus seems reasonable
                status = 42504

            if status == 302:
                location = result.headers.get("Location", "")
                tmp = re.match(r".*implicit#access_token=([^&]+)", location)
                if tmp is not None:
                    self.token = tmp[1]

    # pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
    def set_context(self, config_path: Optional[FilePath] = None,
                    name: Optional[str] = None, unchanged_is_success: bool = False) -> bool:
        """
        Change context

            Parameters:
                config_path (FilePath): The path to the kubeconfig file
                name (str): The context to change to
                unchanged_is_success (bool): True to return success if the context didn't change,
                                             False otherwise
            Returns:
                (bool): True on success, False on failure
        """
        context_name = ""
        cluster_name = ""
        user_name = ""
        # namespace_name = ""

        # If config_path is passed as a parameter, use it,
        # else use the path used when initialising the class
        if config_path is None:
            config_path = self.config_path
        # This should never be needed, but just in case
        elif config_path is None:
            config_path = KUBE_CONFIG_FILE

        config_path = FilePath(config_path)

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
            kubeconfig = secure_read_yaml(config_path, checks=checks)
        except FileNotFoundError:
            return False
        except FilePathAuditError as e:
            if "SecurityStatus.PARENT_DOES_NOT_EXIST" in str(e) \
               or "SecurityStatus.PERMISSIONS" in str(e):
                return False
            raise

        current_context = deep_get(kubeconfig, DictPath("current-context"), "")

        unchanged = True
        # If we did not get a context name we try current-context
        if name is None or not name:
            unchanged = False
            name = current_context
        name = str(name)

        for context in deep_get(kubeconfig, DictPath("contexts"), []):
            # If we still do not have a context name,
            # pick the first match
            if not name or deep_get(context, DictPath("name")) == name:
                context_name = deep_get(context, DictPath("name"))
                user_name = deep_get(context, DictPath("context#user"), "")
                cluster_name = deep_get(context, DictPath("context#cluster"), "")
                # namespace_name = deep_get(context, DictPath("context#namespace"), "")
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

            self.insecuretlsskipverify = \
                deep_get(cluster, DictPath("cluster#insecure-skip-tls-verify"), False)
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
                if not deep_get(user, DictPath("user"), {}):
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

        # We either do not have the cert or token needed to access the server
        # or we cannot authenticate the server correctly
        if self.token is None and (cert is None or key is None) \
           or ca_certs is None and not self.insecuretlsskipverify:
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
            # pylint: disable-next=consider-using-with
            self.tmp_ca_certs_file = tempfile.NamedTemporaryFile()
            self.ca_certs_file = self.tmp_ca_certs_file.name
            self.tmp_ca_certs_file.write(ca_certs.encode("utf-8"))
            self.tmp_ca_certs_file.flush()
        else:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # If we have a cert we also have a key, but check anyway, to make mypy happy
        if cert is not None and key is not None:
            # pylint: disable-next=consider-using-with
            self.tmp_cert_file = tempfile.NamedTemporaryFile()
            # pylint: disable-next=consider-using-with
            self.tmp_key_file = tempfile.NamedTemporaryFile()
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

        secure_write_yaml(config_path, kubeconfig, permissions=0o600, sort_keys=False)

        return True

    def get_pod_network_cidr(self) -> Optional[str]:
        """
        Returns the Pod network CIDR for the cluster

            Returns:
                pod_network_cidr (str): The Pod network CIDR
        """
        # First try to get the CIDR from kubeadm-config, if it exists
        ref = self.get_ref_by_kind_name_namespace(("ConfigMap", ""),
                                                  name="kubeadm-config", namespace="kube-system")
        if ref is not None:
            data = deep_get(ref, DictPath("data#ClusterConfiguration"), {})
            try:
                d = yaml.safe_load(data)
                return deep_get(d, DictPath("networking#podSubnet"))
            except yaml.scanner.ScannerError:
                pass
        nodes, status = \
            self.get_list_by_kind_namespace(("Node", ""), "",
                                            label_selector="node-role.kubernetes.io/control-plane")
        if nodes is None or not nodes or status != 200:
            nodes, status = \
                self.get_list_by_kind_namespace(("Node", ""), "",
                                                label_selector="node-role.kubernetes.io/master")
        if nodes is None or not nodes or status != 200:
            return None
        return deep_get(nodes[0], DictPath("spec#podCIDR"))

    # CNI detection helpers
    # pylint: disable-next=too-many-locals,too-many-branches
    def __identify_cni(self, cni_name: str, controller_kind: Tuple[str, str],
                       controller_selector: str,
                       container_name: str) -> List[Tuple[str, str, Tuple[str, StatusGroup, str]]]:
        cni: List[Tuple[str, str, Tuple[str, StatusGroup, str]]] = []

        # Is there a controller matching the kind we are looking for?
        vlist, _status = \
            self.get_list_by_kind_namespace(controller_kind, "",
                                            field_selector=controller_selector)

        if vlist is None or not vlist or _status != 200:
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
                num_unavailable = deep_get(obj, DictPath("status#numberUnavailable"), 0)
                max_unavailable = deep_get(obj, DictPath("status#maxUnavailable"), 0)
                if num_unavailable > max_unavailable:
                    cni_status = ("Unavailable", StatusGroup.NOT_OK,
                                  "numberUnavailable > maxUnavailable")
                else:
                    cni_status = ("Available", StatusGroup.OK, "")

            match_label_selector = \
                make_selector(deep_get(obj, DictPath("spec#selector#matchLabels")))
            vlist2, _status = \
                self.get_list_by_kind_namespace(("Pod", ""), "",
                                                label_selector=match_label_selector)

            if vlist is None or not vlist:
                continue

            for obj2 in vlist2:
                # Try to get the version
                for container in deep_get(obj2, DictPath("status#containerStatuses"), []):
                    if deep_get(container, DictPath("name"), "") != container_name:
                        continue
                    image_version = get_image_version(deep_get(container, DictPath("image"), ""))
                    if image_version == "<undefined>":
                        continue

                    image_version_tuple = cmtlib.versiontuple(image_version)
                    if cni_version is None:
                        cni_version = image_version
                        pod_matches += 1
                        continue
                    cni_version_tuple = cmtlib.versiontuple(cni_version)
                    if image_version_tuple > cni_version_tuple:
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
        Attempt to identify what CNI the cluster is using;
        if there are multiple possible matches all are returned

            Returns:
                ([(str, str, (str, StatusGroup, str)])): A list of possible CNI candidates
                    (str): The CNI name
                    (str): The version of the CNI
                    ((str, StatusGroup, str)):
                        (str): A string representation of the CNI status
                        (StatusGroup): An enum representation of the CNI status
                        (str): The reason for the status, if known
        """
        cni: List[Tuple[str, str, Tuple[str, StatusGroup, str]]] = []

        # We have to do some sleuthing here
        # Antrea:
        cni += self.__identify_cni("antrea", ("DaemonSet", "apps"),
                                   "metadata.name=antrea-agent", "antrea-agent")
        # Canal:
        cni += self.__identify_cni("canal", ("DaemonSet", "apps"),
                                   "metadata.name=canal", "calico-node")
        cni += self.__identify_cni("canal", ("DaemonSet", "apps"),
                                   "metadata.name=rke2-canal", "calico-node")
        # Calico:
        # Since canal is a combination of Calico and Flannel
        # we need to skip Calico if Canal is detected
        if "canal" not in (cni_name for cni_name, cni_version, cni_status in cni):
            cni += self.__identify_cni("calico", ("Deployment", "apps"),
                                       "metadata.name=calico-kube-controllers",
                                       "calico-kube-controllers")
        # Cilium:
        cni += self.__identify_cni("cilium", ("Deployment", "apps"),
                                   "metadata.name=cilium-operator", "cilium-operator")
        # Flannel:
        cni += self.__identify_cni("flannel", ("DaemonSet", "apps"),
                                   "metadata.name=kube-flannel-ds", "kube-flannel")
        cni += self.__identify_cni("flannel", ("DaemonSet", "apps"),
                                   "metadata.name=kube-flannel", "kube-flannel")
        # Kilo:
        cni += self.__identify_cni("kilo", ("DaemonSet", "apps"),
                                   "metadata.name=kilo", "kilo")
        # Kindnet:
        cni += self.__identify_cni("kindnet", ("DaemonSet", "apps"),
                                   "metadata.name=kindnet", "kindnet-cni")
        # Kube-OVN:
        cni += self.__identify_cni("kube-ovn", ("DaemonSet", "apps"),
                                   "metadata.name=kube-ovn-cni", "cni-server")
        # OVN-Kubernetes:
        cni += self.__identify_cni("ovn-kubernetes", ("DaemonSet", "apps"),
                                   "metadata.name=ovnkube-node", "ovn-controller")
        # OpenShift-SDN:
        cni += self.__identify_cni("sdn", ("DaemonSet", "apps"),
                                   "metadata.name=sdn", "sdn")
        # Kube-router:
        cni += self.__identify_cni("kube-router", ("DaemonSet", "apps"),
                                   "metadata.name=kube-router", "kube-router")
        # Weave:
        cni += self.__identify_cni("weave", ("DaemonSet", "apps"),
                                   "metadata.name=weave-net", "weave")

        return cni

    def __close_certs(self) -> None:
        if self.tmp_ca_certs_file is not None:
            self.tmp_ca_certs_file.close()
        if self.tmp_cert_file is not None:
            self.tmp_cert_file.close()
        if self.tmp_key_file is not None:
            self.tmp_key_file.close()

    def __init__(self, programname: str, programversion: str,
                 config_path: Optional[FilePath] = None) -> None:
        self.programname = programname
        self.programversion = programversion
        self.cluster_unreachable = True
        self.context_name = ""
        self.cluster_name = ""

        if config_path is None:
            self.config_path = KUBE_CONFIG_FILE
        else:
            self.config_path = config_path

        self.set_context(config_path=config_path)

    def __del__(self) -> None:
        self.__close_certs()
        self.context_name = ""
        self.cluster_name = ""
        self.config_path = None

    def is_cluster_reachable(self) -> bool:
        """
        Checks if the cluster is reachable

            Returns:
                (bool): True if cluster is reachable,
                        False if the cluster is unreachable
        """
        return not self.cluster_unreachable

    def get_control_plane_address(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Returns the IP-address and port of the control plane

            Returns:
                (str, str, str): The IP-address, port, and path of the control plane
                    (str): An IP-address
                    (str): A port
                    (str): A path (can be the empty string)
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

        if vlist is None or not vlist or _status != 200:
            return join_token

        age = -1

        # Find the newest bootstrap token
        for secret in vlist:
            name = deep_get(secret, DictPath("metadata#name"))
            if name.startswith("bootstrap-token-"):
                creation_ts = deep_get(secret, DictPath("metadata#creationTimestamp"))
                timestamp = cmtlib.timestamp_to_datetime(creation_ts)
                newage = cmtlib.get_since(timestamp)
                if age == -1 or newage < age:
                    try:
                        token_id = deep_get(secret, DictPath("data#token-id"), "")
                        tmp1 = base64.b64decode(token_id).decode("utf-8")
                    except UnicodeDecodeError:
                        tmp2 = deep_get(secret, DictPath("data#token-id"), "")

                    try:
                        token_secret = deep_get(secret, DictPath("data#token-secret"), "")
                        tmp2 = base64.b64decode(token_secret).decode("utf-8")
                    except UnicodeDecodeError:
                        tmp2 = deep_get(secret, DictPath("data#token-secret"), "")

                    if tmp1 != "" and tmp2 != "":
                        join_token = f"{tmp1}.{tmp2}"
                        age = newage

        return join_token

    # pylint: disable-next=too-many-locals
    def get_ca_cert_hash(self) -> str:
        """
        Returns the CA certificate hash

            Returns:
                ca_cert_hash (str): The CA certificate hash
        """
        ca_cert_hash = ""

        vlist, _status = self.get_list_by_kind_namespace(("Secret", ""), "kube-system")

        if vlist is None or not vlist or _status != 200:
            return ca_cert_hash

        age = -1
        ca_cert = ""

        # Find the newest certificate-controller-token
        for secret in vlist:
            secret_name = deep_get(secret, DictPath("metadata#name"), "")
            if secret_name.startswith("certificate-controller-token-"):
                creation_ts = deep_get(secret, DictPath("metadata#creationTimestamp"))
                timestamp = cmtlib.timestamp_to_datetime(creation_ts)
                newage = cmtlib.get_since(timestamp)
                if age == -1 or newage < age:
                    try:
                        undecoded_ca_cert = deep_get(secret, DictPath("data#ca.crt"), "")
                        tmp1 = base64.b64decode(undecoded_ca_cert).decode("utf-8")
                    except UnicodeDecodeError:
                        tmp1 = deep_get(secret, DictPath("data#ca.crt"), "")

                    if tmp1 != "":
                        ca_cert = tmp1
                        age = newage

        if ca_cert == "":
            ref = self.get_ref_by_kind_name_namespace(("ConfigMap", ""),
                                                      "kube-root-ca.crt", "kube-public")
            ca_cert = deep_get(ref, DictPath("data#ca.crt"), "")

        # we have the CA cert; now to extract the public key and hash it
        if ca_cert:
            try:
                x509obj = x509.load_pem_x509_certificate(ca_cert.encode("utf-8"))
            except TypeError as e:
                if "load_pem_x509_certificate() missing 1 required positional argument: " \
                   "'backend'" in str(e):
                    # This is to handle systems that doesn't have the latest version
                    # of cryptography.
                    # pylint: disable-next=import-outside-toplevel,no-name-in-module
                    from cryptography.hazmat.primitives import default_backend  # type: ignore
                    x509obj = x509.load_pem_x509_certificate(ca_cert.encode("utf-8"),
                                                             backend=default_backend)
                else:
                    raise
            pubkey_fmt = serialization.PublicFormat.SubjectPublicKeyInfo
            pubkeyder = x509obj.public_key().public_bytes(encoding=serialization.Encoding.DER,
                                                          format=pubkey_fmt)
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
            raise ValueError(f"Kind {kind} not known; "
                             "this is likely a programming error (possibly a typo)")
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
            raise ValueError(f"Could not determine latest API; "
                             f"kind {kind} not found in kubernetes_resources")

        latest_api = deep_get(kubernetes_resources[kind], DictPath("api_paths"))[0]
        if latest_api.startswith("api/"):
            latest_api = latest_api[len("api/"):]
        elif latest_api.startswith("apis/"):
            latest_api = latest_api[len("apis/"):]
        if latest_api.endswith("/"):
            latest_api = latest_api[:-len("/")]
        return latest_api

    # pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
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
        url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
              f"{self.control_plane_path}/api/v1"
        with PoolManagerContext(cert_file=self.cert_file, key_file=self.key_file,
                                ca_certs_file=self.ca_certs_file, token=self.token,
                                insecuretlsskipverify=self.insecuretlsskipverify) as pool_manager:
            raw_data, _message, status = \
                self.__rest_helper_generic_json(pool_manager=pool_manager, method=method, url=url)

            if status != 200 or raw_data is None:
                # Something went wrong
                self.cluster_unreachable = True
                return status, []

            # Success
            try:
                core_apis = json.loads(raw_data)
            except DecodeException:
                # We got a response, but the data is malformed
                return 42422, []

            group_version = deep_get(core_apis, DictPath("groupVersion"), "")

            for api in deep_get(core_apis, DictPath("resources"), []):
                name = deep_get(api, DictPath("name"), "")
                shortnames = deep_get(api, DictPath("shortNames"), [])
                api_version = group_version
                namespaced = deep_get(api, DictPath("namespaced"), False)
                kind = deep_get(api, DictPath("kind"), "")
                if not (verbs := deep_get(api, DictPath("verbs"), [])):
                    continue
                api_resources.append((name, shortnames, api_version, namespaced, kind, verbs))

            # Now fetch non-core APIs
            non_core_apis = {}
            non_core_api_dict = {}

            # Attempt aggregated discovery; we need custom header_params to do this.
            # Fallback to the old method if aggregate discovery isn't supported.
            header_params = {
                "Accept": "application/json;g=apidiscovery.k8s.io;v=v2beta1;"
                          "as=APIGroupDiscoveryList,application/json",
                "Content-Type": "application/json",
                "User-Agent": f"{self.programname} v{self.programversion}",
            }
            aggregated_data = {}

            url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
                  f"{self.control_plane_path}/apis"
            with PoolManagerContext(cert_file=self.cert_file, key_file=self.key_file,
                                    ca_certs_file=self.ca_certs_file, token=self.token,
                                    insecuretlsskipverify=self.insecuretlsskipverify) \
                    as pool_manager:
                raw_data, _message, status = \
                    self.__rest_helper_generic_json(pool_manager=pool_manager, method=method,
                                                    url=url, header_params=header_params)

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
                                namespaced = \
                                    deep_get(resource, DictPath("scope"), "") == "Namespaced"
                                kind = deep_get(resource, DictPath("responseKind#kind"), "")
                                verbs = deep_get(resource, DictPath("verbs"), [])
                                kind_tuple = (kind, api_version.split("/", maxsplit=1)[0])
                                # Let's hope we get them in the right order...
                                if kind_tuple in non_core_api_dict:
                                    continue
                                non_core_api_dict[kind_tuple] = \
                                    (name, shortnames, api_version, namespaced, kind, verbs)
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
                        url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
                              f"{self.control_plane_path}/apis/{group_version}"
                        raw_data, _message, status = \
                            self.__rest_helper_generic_json(pool_manager=pool_manager,
                                                            method=method, url=url)

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
                            if not (kind := deep_get(resource, DictPath("kind"), "")):
                                continue

                            name = deep_get(resource, DictPath("name"), "")
                            shortnames = deep_get(resource, DictPath("shortNames"), [])
                            api_version = group_version
                            namespaced = deep_get(resource, DictPath("namespaced"), False)
                            kind = deep_get(resource, DictPath("kind"), "")
                            if not (verbs := deep_get(resource, DictPath("verbs"), [])):
                                continue
                            kind_tuple = (kind, api_version.split("/")[0])
                            # Let's hope we get them in the right order...
                            if kind_tuple in non_core_api_dict:
                                continue
                            non_core_api_dict[kind_tuple] = (name, shortnames, api_version,
                                                             namespaced, kind, verbs)
                api_resources += list(non_core_api_dict.values())

        return status, api_resources

    # TODO: This should ideally be modified to use get_api_resources()
    # pylint: disable-next=too-many-locals,too-many-return-statements,too-many-branches,too-many-statements  # noqa: E501
    def get_available_kinds(self, force_refresh: bool = False) -> Tuple[Dict, int, bool]:
        """
        Return a dict of Kinds known by both kubernetes_helper and the API-server

            Parameters:
                force_refresh (bool): Flush the list (if existing) and create a new one
            Returns:
                ((dict, int, bool)):
                    (dict): A list of all Kinds known
                            by kubernetes_helper, with their support level (list, info) set
                    (int): The HTTP response
                    (bool): True if the list was updated, False otherwise
        """
        modified = False

        # If the list is not empty, but the cluster is unreachable, return it unchanged
        if self.cluster_unreachable:
            return kubernetes_resources, 42503, modified

        # It is fairly easy to check if the API-list is "fresh";
        # just check whether Pod is available
        if not force_refresh and deep_get(kubernetes_resources[("Pod", "")],
                                          DictPath("available"), False):
            return kubernetes_resources, 200, modified

        method = "GET"

        # First get all core APIs
        core_apis = {}

        url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
              f"{self.control_plane_path}/api/v1"
        with PoolManagerContext(cert_file=self.cert_file, key_file=self.key_file,
                                ca_certs_file=self.ca_certs_file, token=self.token,
                                insecuretlsskipverify=self.insecuretlsskipverify) as pool_manager:
            raw_data, _message, status = self.__rest_helper_generic_json(pool_manager=pool_manager,
                                                                         method=method, url=url)

            if status != 200 or raw_data is None:
                self.cluster_unreachable = True
                # We could not get the core APIs; there is no use continuing
                modified = True
                return kubernetes_resources, status, modified
            # Success
            try:
                core_apis = json.loads(raw_data)
            except DecodeException:
                # We got a response, but the data is malformed
                return kubernetes_resources, 42422, False

            # Flush the entire API list
            for _resource_kind, resource_data in kubernetes_resources.items():
                resource_data["available"] = False

            # When running in developer mode with testdata we allow reads from files,
            # and can thus get data without the Kubernetes API being available.
            if deep_get(cmtlib.cmtconfig, DictPath("Debug#developer_mode")) \
                    and deep_get(cmtlib.cmtconfig, DictPath("Debug#use_testdata")):
                for path in Path(f"{HOMEDIR}/testdata").iterdir():
                    if not path.name.endswith(".yaml"):
                        continue
                    tmp = path.name[:-len(".yaml")]
                    tmp_split = tmp.split(".", maxsplit=1)
                    if len(tmp_split) == 1:
                        kind = (tmp_split[0], "")
                    else:
                        kind = (tmp_split[0], tmp_split[1])
                    if kind in kubernetes_resources:
                        kubernetes_resources[kind]["available"] = True

            for api in deep_get(core_apis, DictPath("resources"), []):
                if "list" not in deep_get(api, DictPath("verbs"), []):
                    # Ignore non-list APIs
                    continue
                name = deep_get(api, DictPath("name"), "")
                kind_ = deep_get(api, DictPath("kind"), "")
                if (kind_, "") in kubernetes_resources:
                    kubernetes_resources[(kind_, "")]["available"] = True

            # Attempt aggregated discovery; we need custom header_params to do this.
            # Fallback to the old method if aggregate discovery isn't supported.
            header_params = {
                "Accept": "application/json;g=apidiscovery.k8s.io;"
                          "v=v2beta1;as=APIGroupDiscoveryList,application/json",
                "Content-Type": "application/json",
                "User-Agent": f"{self.programname} v{self.programversion}",
            }
            aggregated_data = {}

            url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
                  f"{self.control_plane_path}/apis"
            raw_data, _message, status = \
                self.__rest_helper_generic_json(pool_manager=pool_manager, method=method,
                                                url=url, header_params=header_params)
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
                        if (version_ := deep_get(version, DictPath("version"))) is None:
                            # This should not happen, but ignore it
                            continue
                        resources = deep_get(version, DictPath("resources"), [])
                        for resource in resources:
                            if "list" not in deep_get(resource, DictPath("verbs"), []):
                                continue
                            if not (kind_ := deep_get(resource, DictPath("responseKind#kind"), "")):
                                continue
                            if (kind_, name) in kubernetes_resources \
                                    and f"apis/{name}/{version_}/" in \
                                    cast(List[str],
                                         kubernetes_resources[(kind_, name)].get("api_paths", [])):
                                kubernetes_resources[(kind_, name)]["available"] = True
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
                    if (version_ := deep_get(version, DictPath("groupVersion"))) is None:
                        # This should not happen, but ignore it
                        continue
                    url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
                          f"{self.control_plane_path}/apis/{version_}"
                    raw_data, _message, status = \
                        self.__rest_helper_generic_json(pool_manager=pool_manager,
                                                        method=method, url=url)

                    if status != 200 or raw_data is None:
                        # Could not get API info; this is worrying, but ignore it
                        continue
                    try:
                        data = json.loads(raw_data)
                    except DecodeException:
                        # We got a response, but the data is malformed
                        continue

                    for resource in deep_get(data, DictPath("resources"), []):
                        if "list" not in deep_get(resource, DictPath("verbs"), []) \
                           or not (kind_ := deep_get(resource, DictPath("kind"), "")):
                            continue
                        if (kind_, name) in kubernetes_resources \
                                and f"apis/{version_}/" in \
                                cast(List[str],
                                     kubernetes_resources[(kind_, name)].get("api_paths", [])):
                            if (kind_, name) in kubernetes_resources:
                                kubernetes_resources[(kind_, name)]["available"] = True
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

    # pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
    def __rest_helper_generic_json(self, *,
                                   pool_manager: Union[urllib3.PoolManager, urllib3.ProxyManager],
                                   **kwargs: Any) -> Tuple[Union[AnyStr, None], str, int]:
        method: Optional[str] = deep_get(kwargs, DictPath("method"))
        url: Optional[str] = deep_get(kwargs, DictPath("url"))
        header_params: Optional[Dict] = deep_get(kwargs, DictPath("header_params"))
        query_params: Optional[List[Optional[Tuple[str, Any]]]] = \
            deep_get(kwargs, DictPath("query_params"))
        body: Optional[bytes] = deep_get(kwargs, DictPath("body"))
        retries: int = deep_get(kwargs, DictPath("retries"), 3)
        connect_timeout: float = deep_get(kwargs, DictPath("connect_timeout"), 3.0)

        if pool_manager is None:
            raise ProgrammingError("__rest_helper_generic_json() "
                                   "should never be called without a pool_manager")

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

        if not retries:
            _retries = False
        else:
            _retries = urllib3.Retry(retries)  # type: ignore

        data = None
        message = ""

        reauth_retry = 1

        while reauth_retry > 0:
            try:
                if body is not None:
                    result = pool_manager.request(method, url, headers=header_params, body=body,
                                                  timeout=urllib3.Timeout(connect=connect_timeout),
                                                  retries=_retries)  # type: ignore
                else:
                    result = pool_manager.request(method, url, headers=header_params,
                                                  fields=query_params,
                                                  timeout=urllib3.Timeout(connect=connect_timeout),
                                                  retries=_retries)  # type: ignore
                status = result.status
            except urllib3.exceptions.MaxRetryError as e:
                # No route to host does not have a HTTP response; make one up...
                # 503 is Service Unavailable; this is generally temporary,
                # but to distinguish it from a real 503 we prefix it...
                if "CERTIFICATE_VERIFY_FAILED" in str(e):
                    # Client Handshake Failed (Cloudflare)
                    status = 525
                    if "certificate verify failed" in str(e):
                        tmp = re.match(r".*SSL: CERTIFICATE_VERIFY_FAILED.*"
                                       r"certificate verify failed: (.*) \(_ssl.*", str(e))
                        if tmp is not None:
                            message = f"; {tmp[1]}"
                else:
                    status = 42503
            except urllib3.exceptions.ConnectTimeoutError:
                # Connection timed out; the API-server might not be available,
                # suffer from too high load, or similar 504 is Gateway Timeout;
                # using 42504 to indicate connection timeout thus seems reasonable
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
            # (Operation queued for batch processing; no further status available;
            #  returned when deleting things with a finalizer)
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
            message = f"401: Unauthorized; method: {method}, URL: {url}, " \
                      f"header_params: {header_params}"
        elif status == 403:
            # Forbidden: request denied
            message = f"403: Forbidden; method: {method}, URL: {url}, " \
                      f"header_params: {header_params}"
        elif status == 404:
            # page not found (API not available or possibly programming error)
            message = f"404: Not Found; method: {method}, URL: {url}, " \
                      f"header_params: {header_params}"
        elif status == 405:
            # Method not allowed
            raise TypeError(f"405: Method Not Allowed; this is probably a programming error; "
                            f"method: {method}, URL: {url}; header_params: {header_params}")
        elif status == 406:
            # Not Acceptable
            raise TypeError(f"406: Not Acceptable; this is probably a programming error; "
                            f"method: {method}, URL: {url}; header_params: {header_params}")
        elif status == 410:
            # Gone
            # Most likely a update events were requested (using resourceVersion),
            # but it has been too long since the previous request;
            # caller should retry without &resourceVersion=xxxxx
            pass
        elif status == 415:
            # Unsupported Media Type
            # The server refused to accept the request because the payload
            # was in an unsupported format;
            # check Content-Type, Content-Encoding, and the data itself.
            raise TypeError("415: Unsupported Media Type; this is probably a programming error; "
                            f"method: {method}, URL: {url}; header_params: {header_params}")
        elif status == 422:
            # Unprocessable entity
            # The content and syntax is correct, but the request cannot be processed
            msg = result.data.decode("utf-8", errors="replace")
            message = f"422: Unprocessable Entity; method: {method}, URL: {url}; " \
                      f"header_params: {header_params}; message: {msg}"
        elif status == 500:
            # Internal Server Error
            msg = result.data.decode("utf-8", errors="replace")
            message = f"500: Internal Server Error; method: {method}, URL: {url}; " \
                      f"header_params: {header_params}; message: {msg}"
        elif status == 502:
            # Bad Gateway
            # Either a malfunctioning or a malicious proxy
            message = "502: Bad Gateway"
        elif status == 503:
            # Service Unavailable
            # This might be a CRD that has failed to deploy properly
            message = f"503: Service Unavailable; method: {method}, URL: {url}; " \
                      f"header_params: {header_params}"
        elif status == 504:
            # Gateway Timeout
            # A request was made for an unrecognised resourceVersion,
            # and timed out waiting for it to become available
            message = f"504: Gateway Timeout; method: {method}, URL: {url}; " \
                      f"header_params: {header_params}"
        elif status == 525:
            # SSL Handshake Failed (Cloudflare)
            message = f"525: Client Handshake Failed{message}"
        elif status == 42503:
            message = f"No route to host; method: {method}, URL: {url}; " \
                      f"header_params: {header_params}"
        else:
            # debuglog.add([
            #        [ANSIThemeStr("__rest_helper_generic_json():", "emphasis")],
            #        [ANSIThemeStr(f"Unhandled error: {result.status}", "error")],
            #        [ANSIThemeStr("method: ", "emphasis"),
            #         ANSIThemeStr(f"{method}", "argument")],
            #        [ANSIThemeStr("URL: ", "emphasis"),
            #         ANSIThemeStr(f"{url}", "argument")],
            #        [ANSIThemeStr("header_params: ", "emphasis"),
            #         ANSIThemeStr(f"{header_params}", "argument")],
            #       ], severity=LogLevel.ERR)
            sys.exit(f"__rest_helper_generic_json():\nUnhandled error: {result.status}\n"
                     f"method: {method}\nURL: {url}\nheader_params: {header_params}")

        return data, message, status

    # pylint: disable-next=too-many-locals
    def __rest_helper_post(self, kind: Tuple[str, str], **kwargs: Any) -> Tuple[str, int]:
        name: str = deep_get(kwargs, DictPath("name"), "")
        namespace: str = deep_get(kwargs, DictPath("namespace"), "")
        body: Optional[bytes] = deep_get(kwargs, DictPath("body"))
        method = "POST"

        if body is None or not body:
            raise ValueError("__rest_helper_post called with empty body; "
                             "this is most likely a programming error")

        header_params = {
            "Content-Type": "application/json",
            "User-Agent": f"{self.programname} v{self.programversion}",
        }

        namespace_part = ""
        if namespace is not None and namespace != "":
            namespace_part = f"namespaces/{namespace}/"

        if kind is None:
            raise ValueError("__rest_helper_post called with kind None; "
                             "this is most likely a programming error")

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
        with PoolManagerContext(cert_file=self.cert_file, key_file=self.key_file,
                                ca_certs_file=self.ca_certs_file, token=self.token,
                                insecuretlsskipverify=self.insecuretlsskipverify) as pool_manager:
            for api_path in api_paths:
                url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
                      f"{self.control_plane_path}/{api_path}{namespace_part}{api}{name}"
                _data, message, status = \
                    self.__rest_helper_generic_json(pool_manager=pool_manager, method=method,
                                                    url=url, header_params=header_params,
                                                    body=body)
                if status in (200, 201, 204, 42503):
                    break

        return message, status

    # pylint: disable-next=too-many-locals
    def __rest_helper_patch(self, kind: Tuple[str, str], *, name: str,
                            **kwargs: Any) -> Tuple[str, int]:
        namespace: str = deep_get(kwargs, DictPath("namespace"), "")
        strategic_merge: bool = deep_get(kwargs, DictPath("strategic_merge"), True)
        subresource: str = deep_get(kwargs, DictPath("subresource"), "")
        body: Optional[bytes] = deep_get(kwargs, DictPath("body"), None)
        method = "PATCH"

        header_params = {
            "User-Agent": f"{self.programname} v{self.programversion}",
        }

        if strategic_merge:
            header_params["Content-Type"] = "application/strategic-merge-patch+json"
        else:
            header_params["Content-Type"] = "application/merge-patch+json"

        if body is None or not body:
            raise ValueError("__rest_helper_patch called with empty body; "
                             "this is most likely a programming error")

        namespace_part = ""
        if namespace is not None and namespace != "":
            namespace_part = f"namespaces/{namespace}/"

        subresource_part = ""
        if subresource is not None and subresource != "":
            subresource_part = f"/{subresource}"

        if kind is None:
            raise ValueError("__rest_helper_patch called with kind None; "
                             "this is most likely a programming error")

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
        with PoolManagerContext(cert_file=self.cert_file, key_file=self.key_file,
                                ca_certs_file=self.ca_certs_file, token=self.token,
                                insecuretlsskipverify=self.insecuretlsskipverify) as pool_manager:
            for api_path in api_paths:
                url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
                      f"{self.control_plane_path}/{api_path}{namespace_part}{api}" \
                      f"{name}{subresource_part}"
                _data, message, status = \
                    self.__rest_helper_generic_json(pool_manager=pool_manager, method=method,
                                                    url=url, header_params=header_params,
                                                    body=body)
                if status in (200, 204, 42503):
                    break

        return message, status

    # pylint: disable-next=too-many-locals
    def __rest_helper_delete(self, kind: Tuple[str, str], *,
                             name: str, **kwargs: Any) -> Tuple[str, int]:
        namespace: str = deep_get(kwargs, DictPath("namespace"), "")
        query_params: Optional[List[Optional[Tuple[str, Any]]]] = \
            deep_get(kwargs, DictPath("query_params"))
        method = "DELETE"

        if query_params is None:
            query_params = []

        namespace_part = ""
        if namespace is not None and namespace != "":
            namespace_part = f"namespaces/{namespace}/"

        if kind is None:
            raise ValueError("__rest_helper_delete called with kind None; "
                             "this is most likely a programming error")

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
        with PoolManagerContext(cert_file=self.cert_file, key_file=self.key_file,
                                ca_certs_file=self.ca_certs_file, token=self.token,
                                insecuretlsskipverify=self.insecuretlsskipverify) as pool_manager:
            for api_path in api_paths:
                url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
                      f"{self.control_plane_path}/{api_path}{namespace_part}{api}{name}"
                _data, message, status = \
                    self.__rest_helper_generic_json(pool_manager=pool_manager, method=method,
                                                    url=url, query_params=query_params)
                if status in (200, 202, 204, 42503):
                    break

        return message, status

    # On failure this function should always return [] for list requests,
    # and None for other requests; this way lists the result can be handled
    # unconditionally in for loops

    # pylint: disable-next=too-many-locals,too-many-branches
    def __rest_helper_get(self, **kwargs: Any) -> Tuple[Union[Optional[Dict], List[Optional[Dict]]],
                                                        int]:
        kind: Optional[Tuple[str, str]] = deep_get(kwargs, DictPath("kind"))
        raw_path: Optional[str] = deep_get(kwargs, DictPath("raw_path"))
        name: str = deep_get(kwargs, DictPath("name"), "")
        namespace: str = deep_get(kwargs, DictPath("namespace"), "")
        label_selector: str = deep_get(kwargs, DictPath("label_selector"), "")
        field_selector: str = deep_get(kwargs, DictPath("field_selector"), "")

        if kind is None and raw_path is None:
            raise ValueError("__rest_helper_get API called with kind None and raw_path None; "
                             "this is most likely a programming error")

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
        with PoolManagerContext(cert_file=self.cert_file, key_file=self.key_file,
                                ca_certs_file=self.ca_certs_file, token=self.token,
                                insecuretlsskipverify=self.insecuretlsskipverify) as pool_manager:
            for api_path in api_paths:
                url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
                      f"{self.control_plane_path}/{api_path}{namespace_part}{api}{name}"
                raw_data, _message, status = \
                    self.__rest_helper_generic_json(pool_manager=pool_manager, method=method,
                                                    url=url, query_params=query_params)

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

                # if status == 404:
                    # We did not get any data, but we might not want to fail

                    # page not found (API not available or possibly programming error)
                    # raise UnknownError(f"API not available; this is probably "
                    #                     "a programming error; URL {url}")

                # if status == 410:
                    # XXX: Should be handled when we implement support for update events

                    # Gone
                    # We requested update events (using resourceVersion),
                    # but it has been too long since the previous request;
                    # retry without &resourceVersion=xxxxx

        # If name is not set this is a list request, so return an empty list instead of None
        if name == "":
            return [], status

        return None, status

    def get_api_server_version(self) -> Tuple[int, int, str]:
        """
        Get API-server version

            Returns:
                (int, int, str):
                    (int): Major API-server version
                    (int): Minor API-server version
                    (str): API-server GIT version
        """
        ref, _status = self.__rest_helper_get(raw_path="version")
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

        if name is None or not name:
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
        return self.__rest_helper_post(kind=kind, body=body)

    # pylint: disable-next=too-many-locals
    def taint_node(self, node: str, taints: List[Dict],
                   new_taint: Tuple[str, Optional[str], Optional[str], Optional[str]],
                   overwrite: bool = False) -> Tuple[str, int]:
        """
        Apply a new taint, replace an existing taint, or remove a taint for a node

            Parameters:
                node (str): The node to taint
                taints (list[dict]): The current taints
                new_taint ((key, value, old_effect, new_effect): The modified or new taint
                overwrite (bool): If overwrite is set, modify the taint, otherwise return
            Returns:
                ((str, int)): The return value from __rest_helper_patch
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
                if (old_effect is None or _old_effect == old_effect) \
                        and (value is None or _old_value == value):
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
        return self.__rest_helper_patch(kind=kind, name=node, body=body)

    def cordon_node(self, node: str) -> Tuple[str, int]:
        """
        Cordon a Node

            Parameters:
                node (str): The node to cordon
            Returns:
                ((str, int)): the return value from __rest_helper_patch
        """
        kind = ("Node", "")
        data = {
            "spec": {
                "unschedulable": True
            }
        }
        body = json.dumps(data).encode("utf-8")
        return self.__rest_helper_patch(kind=kind, name=node, body=body)

    def uncordon_node(self, node: str) -> Tuple[str, int]:
        """
        Uncordon a Node

            Parameters:
                node (str): The node to uncordon
            Returns:
                ((str, int)): the return value from __rest_helper_patch
        """
        kind = ("Node", "")
        data = {
            "spec": {
                "unschedulable": None
            }
        }
        body = json.dumps(data).encode("utf-8")
        return self.__rest_helper_patch(kind, name=node, body=body)

    # pylint: disable-next=too-many-arguments
    def patch_obj_by_kind_name_namespace(self, kind: Tuple[str, str], name: str,
                                         namespace: str, patch: Dict, subresource: str = "",
                                         strategic_merge: bool = True) -> Tuple[str, int]:
        """
        Patch an object

            Parameters:
                kind ((kind, api_group)): Kind of object to patch
                name (str): The name of the object
                namespace (str): The namespace of the object (or "")
                subresource (str): The subresource of the object (or "")
                strategic_merge (bool): True to use strategic merge
            Returns:
                ((str, int)): the return value from __rest_helper_delete
        """
        body = json.dumps(patch).encode("utf-8")
        return self.__rest_helper_patch(kind=kind, name=name, namespace=namespace, body=body,
                                        subresource=subresource, strategic_merge=strategic_merge)

    def delete_obj_by_kind_name_namespace(self, kind: Tuple[str, str], name: str,
                                          namespace: str, force: bool = False) -> Tuple[str, int]:
        """
        Delete an object

            Parameters:
                kind ((kind, api_group)): Kind of object to delete
                name (str): The name of the object
                namespace (str): The namespace of the object (or "")
                force (bool): True = no grace period
            Returns:
                ((str, int)): the return value from __rest_helper_delete
        """
        query_params: List[Optional[Tuple[str, Any]]] = []

        if force:
            query_params.append(("gracePeriodSeconds", 0))

        return self.__rest_helper_delete(kind=kind, name=name,
                                         namespace=namespace, query_params=query_params)

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
        url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
              f"{self.control_plane_path}/metrics"
        with PoolManagerContext(cert_file=self.cert_file, key_file=self.key_file,
                                ca_certs_file=self.ca_certs_file, token=self.token,
                                insecuretlsskipverify=self.insecuretlsskipverify) as pool_manager:
            data, _message, status = self.__rest_helper_generic_json(pool_manager=pool_manager,
                                                                     method="GET", url=url,
                                                                     query_params=query_params)
            if status == 200 and data is not None:
                if isinstance(data, bytes):
                    msg = data.decode("utf-8", errors="replace").splitlines()
                elif isinstance(data, str):
                    msg = data.splitlines()
            elif status == 204:
                # No Content; pretend that everything is fine
                msg = []
                status = 200
            else:
                msg = []
        return msg, status

    def get_list_by_kind_namespace(self, kind: Tuple[str, str], namespace: str,
                                   **kwargs: Any) -> Tuple[List[Dict[str, Any]], int]:
        """
        Given kind, namespace and optionally label and/or field selectors,
        return all matching resources

            Parameters:
                kind (str, str): A kind, API-group tuple
                namespace (str): The namespace of the resource
                                 (empty if the resource is not namespaced)
                **kwargs (dict[str, Any]): Keyword arguments
                    label_selector (str): A label selector
                    field_selector (str): A field selector
                    resource_cache (KubernetesResourceCache): A KubernetesResourceCache
            Returns:
                ([dict], int):
                    ([dict]): A list of object dicts
                    (int): The HTTP response
        """
        label_selector: str = deep_get(kwargs, DictPath("label_selector"), "")
        field_selector: str = deep_get(kwargs, DictPath("field_selector"), "")
        resource_cache: Optional[KubernetesResourceCache] = deep_get(kwargs,
                                                                     DictPath("resource_cache"))

        vlist: List[Dict[str, Any]] = []

        if deep_get(cmtlib.cmtconfig, DictPath("Debug#developer_mode")) \
                and deep_get(cmtlib.cmtconfig, DictPath("Debug#use_testdata")):
            if resource_cache:
                if vlist := resource_cache.get_resources(kind, namespace=namespace,
                                                         label_selector=label_selector,
                                                         field_selector=field_selector):
                    return vlist, 200

            if not kind[1]:
                joined_kind = kind[0]
            else:
                joined_kind = ".".join(kind)
            testdata = f"{HOMEDIR}/testdata/{joined_kind}.yaml"
            if Path(testdata).is_file():
                d = secure_read_yaml(FilePath(testdata))
                if deep_get(d, DictPath("kind")) == "List":
                    vlist = deep_get(d, DictPath("items"), [])
                else:
                    if d:
                        vlist = list(d)
                if vlist is None:
                    d = []
                if vlist and resource_cache is not None:
                    resource_cache.update_resources(kind, vlist)
                    # This way we get the selectors handled
                    return resource_cache.get_resources(kind, namespace=namespace,
                                                        label_selector=label_selector,
                                                        field_selector=field_selector), 200
                return vlist, 200

        tmp, status = self.__rest_helper_get(kind=kind, namespace=namespace,
                                             label_selector=label_selector,
                                             field_selector=field_selector)
        vlist = cast(List[Dict[str, Any]], tmp)
        return vlist, status

    def get_ref_by_kind_name_namespace(self, kind: Tuple[str, str], name: str,
                                       namespace: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """
        Given kind, name, namespace return a resource

            Parameters:
                kind (str, str): A kind, API-group tuple
                name (str): The name of the resource
                namespace (str): The namespace of the resource
                                 (empty if the resource is not namespaced)
                **kwargs (dict[str, Any]): Keyword arguments
                    resource_cache (KubernetesResourceCache): A KubernetesResourceCache
            Returns:
                (dict): An object dict
        """
        resource_cache: Optional[KubernetesResourceCache] = deep_get(kwargs,
                                                                     DictPath("resource_cache"))

        if deep_get(cmtlib.cmtconfig, DictPath("Debug#developer_mode")) \
                and deep_get(cmtlib.cmtconfig, DictPath("Debug#use_testdata")):
            if not kind[1]:
                joined_kind = kind[0]
            else:
                joined_kind = ".".join(kind)
            testdata = f"{HOMEDIR}/testdata/{joined_kind}.yaml"
            if resource_cache:
                d = resource_cache.get_resources(kind, namespace=namespace)
            else:
                d = []
            if not d and Path(testdata).is_file():
                tmp = secure_read_yaml(FilePath(testdata))
                if deep_get(tmp, DictPath("kind")) == "List":
                    d = deep_get(tmp, DictPath("items"), [])
                else:
                    d = [tmp]
            if d is None:
                d = []
            for item in d:
                i_name = deep_get(item, DictPath("metadata#name"), "")
                i_namespace = deep_get(item, DictPath("metadata#namespace"))
                if i_name == name and (not namespace or i_namespace == namespace):
                    return item
            return None

        ref, _status = self.__rest_helper_get(kind=kind, name=name, namespace=namespace)
        ref = cast(Dict, ref)
        return ref

    def read_namespaced_pod_log(self, name: str, namespace: str,
                                container: Optional[str] = None,
                                tail_lines: int = 0) -> Tuple[str, int]:
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
        url = f"https://{self.control_plane_ip}:{self.control_plane_port}" \
              f"{self.control_plane_path}/api/v1/namespaces/{namespace}/pods/{name}/log"
        with PoolManagerContext(cert_file=self.cert_file, key_file=self.key_file,
                                ca_certs_file=self.ca_certs_file, token=self.token,
                                insecuretlsskipverify=self.insecuretlsskipverify) as pool_manager:
            data, message, status = self.__rest_helper_generic_json(pool_manager=pool_manager,
                                                                    method=method, url=url,
                                                                    query_params=query_params)

            if status == 200 and data is not None:
                if isinstance(data, bytes):
                    msg = data.decode("utf-8", errors="replace")
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
        ref, _status = self.__rest_helper_get(kind=deep_get(owr, DictPath("kind")),
                                              name=deep_get(owr, DictPath("name")),
                                              namespace=namespace)
        ref = cast(dict, ref)
        return ref

    # pylint: disable-next=too-many-locals
    def get_events_by_kind_name_namespace(self, kind: Tuple[str, str], name: str,
                                          namespace: str, **kwargs: Any) \
            -> List[Tuple[str, str, str, str, str, str, str, str, str]]:
        """
        Given kind, name, and namespace, returns all matching events

            Parameters:
                kind ((str, str)): A (kind, api_group) tuple
                name (str): The name of the resource
                namespace (str): The namespace of the resource
                **kwargs (dict[str, Any]): Keyword arguments
                    resource_cache (KubernetesResourceCache): A KubernetesResourceCache
            Returns:
                ([(str, str, str, str, str, str, str, str, str)]):
                    (str): The namespace of the event
                    (str): The name of the event
                    (str): A string representation of the last seen datetime
                    (str): The event status
                    (str): The reason for the event
                    (str): The source of the event
                    (str): A string representation of the first seen datetime
                    (str): The number of times this event has been emitted
                    (str): A free-form explanation of the event
        """
        resource_cache: Optional[KubernetesResourceCache] = \
            deep_get(kwargs, DictPath("resource_cache"))

        events: List[Tuple[str, str, str, str, str, str, str, str, str]] = []
        vlist, _status = self.get_list_by_kind_namespace(("Event", "events.k8s.io"), "",
                                                         resource_cache=resource_cache)
        if vlist is None or not vlist or _status != 200:
            return events

        for obj in vlist:
            obj = cast(Dict, obj)

            __involved_kind = deep_get_with_fallback(obj, [DictPath("regarding#kind"),
                                                           DictPath("involvedObject#kind")])
            __involved_api_version = \
                deep_get_with_fallback(obj, [DictPath("regarding#apiVersion"),
                                             DictPath("involvedObject#apiVersion")])
            involved_kind = self.kind_api_version_to_kind(__involved_kind, __involved_api_version)
            involved_name = deep_get_with_fallback(obj, [DictPath("regarding#name"),
                                                         DictPath("involvedObject#name")])
            ev_name = deep_get(obj, DictPath("metadata#name"))
            ev_namespace = deep_get(obj, DictPath("metadata#namespace"), "")
            _last_seen = cmtlib.timestamp_to_datetime(deep_get_with_fallback(obj, [
                DictPath("series#lastObservedTime"),
                DictPath("deprecatedLastTimestamp"),
                DictPath("lastTimestamp"),
                DictPath("eventTime"),
                DictPath("deprecatedFirstTimestamp"),
                DictPath("firstTimestamp")]))
            last_seen = cmtlib.datetime_to_timestamp(_last_seen)
            status = deep_get(obj, DictPath("type"), "")
            reason = deep_get(obj, DictPath("reason"), "")
            reason = reason.replace("\\\"", "“").replace("\n", "\\n").rstrip()
            if not (src_component := deep_get(obj, DictPath("reportingController"), "")):
                src_component = deep_get_with_fallback(obj, [DictPath("deprecatedSource#component"),
                                                             DictPath("source#component")], "")
            if not (src_host := deep_get(obj, DictPath("reportingInstance"), "")):
                src_host = deep_get_with_fallback(obj, [DictPath("deprecatedSource#host"),
                                                        DictPath("source#host")], "")
            if not src_component:
                source = src_host
            elif not src_host:
                source = src_component
            else:
                source = f"{src_host}/{src_component}"
            _first_seen = \
                cmtlib.timestamp_to_datetime(
                    deep_get_with_fallback(obj, [DictPath("eventTime"),
                                                 DictPath("deprecatedFirstTimestamp"),
                                                 DictPath("firstTimestamp")]))
            first_seen = cmtlib.datetime_to_timestamp(_first_seen)

            count: str = deep_get_with_fallback(obj, [DictPath("series#count"),
                                                      DictPath("deprecatedCount"),
                                                      DictPath("count")], "")
            if count is None:
                count = ""
            else:
                count = str(count)
            message: str = deep_get_with_fallback(obj, [DictPath("message"), DictPath("note")], "")
            message = message.replace("\\\"", "“").replace("\n", "\\n").rstrip()
            if kind == involved_kind and name == involved_name and ev_namespace == namespace:
                event = (str(ev_namespace),
                         str(ev_name), last_seen, status,
                         str(reason), str(source), first_seen, count, message)
                events.append(event)
        return events

    def check_for_feature_gates(self, **kwargs: Any) -> Dict[str, Dict[str, Any]]:
        """
        Upgrading typically isn't supported when feature gates are enabled;
        this provides a quick way to check whether there are feature gates enabled.
        Note that this isn't 100% proof; we won't be able to detect manually enabled
        feature gates.

            Parameters:
                **kwargs (dict[str, Any]): Keyword arguments
                    resource_cache (KubernetesResourceCache): A KubernetesResourceCache
            Returns:
                (Dict): A dict with that contains the set feature gates, if any
        """
        resource_cache: Optional[KubernetesResourceCache] = \
            deep_get(kwargs, DictPath("resource_cache"))

        # We can find out whether feature gates were enabled by checking the configuration
        # used when setting up the cluster.
        ref = self.get_ref_by_kind_name_namespace(("ConfigMap", ""),
                                                  "kube-proxy", "kube-system",
                                                  resource_cache=resource_cache)
        cm_str = deep_get(ref, DictPath("data#config.conf"), {})
        cm = yaml.safe_load(cm_str)
        kube_proxy_feature_gates = deep_get(cm, DictPath("featureGates"), {})

        ref = self.get_ref_by_kind_name_namespace(("ConfigMap", ""),
                                                  "kubeadm-config", "kube-system",
                                                  resource_cache=resource_cache)
        cm_str = deep_get(ref, DictPath("data#ClusterConfiguration"), {})
        cm = yaml.safe_load(cm_str)
        api_server_feature_gates = deep_get(cm, DictPath("apiServer#extraArgs#feature-gates"), {})
        scheduler_feature_gates = deep_get(cm, DictPath("scheduler#extraArgs#feature-gates"), {})

        ref = self.get_ref_by_kind_name_namespace(("ConfigMap", ""),
                                                  "kubelet-config", "kube-system",
                                                  resource_cache=resource_cache)
        cm_str = deep_get(ref, DictPath("data#kubelet"), {})
        cm = yaml.safe_load(cm_str)
        kubelet_feature_gates = deep_get(cm, DictPath("featureGates"), {})
        return {
            "kube_proxy_feature_gates": copy.deepcopy(kube_proxy_feature_gates),
            "api_server_feature_gates": copy.deepcopy(api_server_feature_gates),
            "scheduler_feature_gates": copy.deepcopy(scheduler_feature_gates),
            "kubelet_feature_gates": copy.deepcopy(kubelet_feature_gates),
        }
