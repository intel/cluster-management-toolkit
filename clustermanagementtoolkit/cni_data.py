#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Helper for installing and upgrading CNI
"""

from collections.abc import Callable, Generator
from typing import Any, TypedDict

from clustermanagementtoolkit.cmtio import check_path, join_securitystatus_set

from clustermanagementtoolkit.cmtio_yaml import secure_read_yaml, secure_read_yaml_all
from clustermanagementtoolkit.cmtio_yaml import secure_write_yaml

from clustermanagementtoolkit.cmttypes import deep_get, deep_set, DictPath
from clustermanagementtoolkit.cmttypes import FilePath, FilePathAuditError, SecurityStatus

from clustermanagementtoolkit.networkio import get_github_version


def __patch_cni_calico(cni_path: FilePath, pod_network_cidr: str) -> bool:
    """
    Patch the configuration for Calico

        Parameters:
            cni_path (FilePath): The path to the CNI configuration to patch
            pod_network_cidr (str): The CIDR for the pod network
        Returns:
            (bool): True on success, False on Failure
        Raises:
            FilePathAuditError
    """
    violations: list[SecurityStatus] = check_path(cni_path)
    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=cni_path)

    dl: Generator = secure_read_yaml_all(cni_path)
    dl_mod: list[Any] = []

    for d in dl:
        if deep_get(d, DictPath("kind"), "") == "Installation":
            for ippool in deep_get(d, DictPath("spec#calicoNetwork#ipPools"), []):
                if deep_get(ippool, DictPath("name"), "") == "default-ipv4-ippool":
                    deep_set(ippool, DictPath("cidr"), f"{pod_network_cidr}")
        dl_mod.append(d)
    secure_write_yaml(cni_path, dl_mod, sort_keys=False, permissions=0o644)
    return True


def __patch_cni_canal(cni_path: FilePath, pod_network_cidr: str) -> bool:
    """
    Patch the configuration for Canal

        Parameters:
            cni_path (FilePath): The path to the CNI configuration to patch
            pod_network_cidr (str): The CIDR for the pod network
        Returns:
            (bool): True on success, False on Failure
        Raises:
            FilePathAuditError
    """
    violations: list[SecurityStatus] = check_path(cni_path)
    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=cni_path)

    dl: Generator = secure_read_yaml_all(cni_path)
    dl_mod: list[Any] = []

    for d in dl:
        if deep_get(d, DictPath("kind"), "") == "ConfigMap" \
                and deep_get(d, DictPath("metadata#name"), "") == "canal-config":
            data = deep_get(d, DictPath("data#net-conf.json"), "")
            data = data.replace("10.244.0.0/16", pod_network_cidr)
            deep_set(d, DictPath("data#net-conf.json"), data)
        dl_mod.append(d)

    secure_write_yaml(cni_path, dl_mod, sort_keys=False, permissions=0o644)
    return True


def __patch_cni_flannel(cni_path: FilePath, pod_network_cidr: str) -> bool:
    """
    Patch the configuration for Flannel

        Parameters:
            cni_path (FilePath): The path to the CNI configuration to patch
            pod_network_cidr (str): The CIDR for the pod network
        Returns:
            (bool): True on success, False on Failure
        Raises:
            FilePathAuditError
    """
    violations: list[SecurityStatus] = check_path(cni_path)
    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=cni_path)

    dl: Generator = secure_read_yaml_all(cni_path)
    dl_mod: list[Any] = []

    for d in dl:
        if deep_get(d, DictPath("kind"), "") == "ConfigMap" \
                and deep_get(d, DictPath("metadata#name"), "") == "kube-flannel-cfg":
            data = deep_get(d, DictPath("data#net-conf.json"), "")
            data = data.replace("10.244.0.0/16", pod_network_cidr)
            deep_set(d, DictPath("data#net-conf.json"), data)
        dl_mod.append(d)

    secure_write_yaml(cni_path, dl_mod, sort_keys=False, permissions=0o644)
    return True


def __patch_cni_weave(cni_path: FilePath, pod_network_cidr: str) -> bool:
    """
    Patch the configuration for Weave

        Parameters:
            cni_path (FilePath): The path to the CNI configuration to patch
            pod_network_cidr (str): The CIDR for the pod network
        Returns:
            (bool): True on success, False on Failure
        Raises:
            FilePathAuditError
    """
    violations: list[SecurityStatus] = check_path(cni_path)
    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=cni_path)

    d: Any = secure_read_yaml(cni_path)

    # pylint: disable=too-many-nested-blocks
    for item in deep_get(d, DictPath("items"), []):
        if deep_get(item, DictPath("kind"), "") == "DaemonSet" \
                and deep_get(item, DictPath("metadata#name"), "") == "weave-net":
            for container in deep_get(item, DictPath("spec#template#spec#containers"), []):
                if deep_get(container, DictPath("name"), "") == "weave":
                    env = deep_get(container, DictPath("env"), [])
                    for var in env:
                        if deep_get(var, DictPath("name"), "") == "IPALLOC_RANGE":
                            deep_set(var, DictPath("value"), pod_network_cidr)
                            break
                    else:
                        # OK, there isn't any IPALLOC_RANGE entry; prepend it
                        env.insert(0,
                                   {
                                       "name": "IPALLOC_RANGE",
                                       "value": pod_network_cidr,
                                   })
    secure_write_yaml(cni_path, d, sort_keys=False, permissions=0o644)
    return True


class URLTypeOptional(TypedDict, total=False):
    """
    Optional parts of a URL dict.

        Parameters:
            checksum_url (str): The URL to fetch the checksum from
            checksum_type (str): The type of the checksum
            patch (Callable): A function to call to patch the downloaded file
    """
    checksum_url: str
    checksum_type: str
    patch: Callable


class URLType(URLTypeOptional):
    """
    A URL dict.

        Parameters:
            url (str): The URL to download
            filename (str): The filename of the downloaded file
    """
    url: str
    filename: str


class CNIDataTypeOptional(TypedDict, total=False):
    """
    CNI data.

        Parameters:
            candidate_version_command ([str]): A command that returns the candidate CNI version
            candidate_version_function (Callable): A function that returns the candidate CNI version
            candidate_version_url (str): A URL to retrieve the candidate CNI version from
            candidate_version_regex (str): A regex for use with candidate_version_function
            manual_candidate_version_regex (str): A regex to use with candidate_version_command
            version_command ([str]): A command that returns the current CNI version
            version_regex (str): A regex to use with version_command
            urls ([URLType]): A list of URLs to download
            upgrade ([str]): The command to use to upgrade the CNI
            install ([str]): The command to use to install the CNI
            uninstall ([str]): The command to use to uninstall the CNI
    """
    candidate_version_command: list[str]
    candidate_version_function: Callable
    candidate_version_url: str
    manual_candidate_version_regex: str
    version_command: list[str]
    version_regex: str
    urls: list[URLType]
    upgrade: list[str]
    install: list[str]
    uninstall: list[str]


class CNIDataType(CNIDataTypeOptional):
    """
    CNI data.

        Parameters:
            candidate_version_regex (str): A regex that extracts the candidate CNI version
    """
    candidate_version_regex: str


cni_data: dict[str, dict[str, CNIDataType]] = {
    "antrea": {
        "executable": {
            "candidate_version_function": get_github_version,
            "candidate_version_url":
                "https://api.github.com/repos/antrea-io/antrea/releases",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "manual_candidate_version_regex": r"^(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "version_command": ["antctl", "version"],
            "version_regex": r"^antctlVersion: v(\d+)(\.)(\d+)(\.)(\d+)$",
            "urls": [
                {
                    "url": "https://github.com/antrea-io/antrea/releases/"
                           "download/<<<version>>>/antctl-linux-x86_64",
                    "filename": "antctl",
                }
            ]
        },
        "CNI": {
            "candidate_version_function": get_github_version,
            "candidate_version_url":
                "https://api.github.com/repos/antrea-io/antrea/releases",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "manual_candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "urls": [
                {
                    "url": "https://raw.githubusercontent.com/"
                           "antrea-io/antrea/<<<version>>>/build/yamls/antrea.yml",
                    "filename": "antrea.yaml",
                }
            ]
        }
    },
    "calico": {
        "executable": {
            "candidate_version_function": get_github_version,
            "candidate_version_url":
                "https://api.github.com/repos/projectcalico/calico/releases",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "manual_candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "version_command": ["kubectl", "calico", "version"],
            "version_regex": r"^Client Version:\s+(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "urls": [
                {
                    "url": "https://github.com/projectcalico/"
                           "calico/releases/download/<<<version>>>/calicoctl-linux-<<<arch>>>",
                    "checksum_url": "https://github.com/projectcalico/"
                                    "calico/releases/download/<<<version>>>/SHA256SUMS",
                    "checksum_type": "sha256",
                    "filename": "kubectl-calico",
                }
            ]
        },
        "CNI": {
            "version_command": ["kubectl", "calico", "version"],
            "version_regex": r"^Cluster Version:\s*(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "candidate_version_function": get_github_version,
            "candidate_version_url":
                "https://api.github.com/repos/projectcalico/calico/releases",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "manual_candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "urls": [
                {
                    "url": "https://raw.githubusercontent.com/projectcalico/"
                           "calico/<<<version>>>/manifests/tigera-operator.yaml",
                    "filename": "tigera-operator-<<<version>>>.yaml",
                }, {
                    "url": "https://raw.githubusercontent.com/projectcalico/"
                           "calico/<<<version>>>/manifests/custom-resources.yaml",
                    "filename": "calico-custom-resources-<<<version>>>.yaml",
                    "patch": __patch_cni_calico,
                }
            ]
        }
    },
    "canal": {
        "CNI": {
            "candidate_version_function": get_github_version,
            "candidate_version_url":
                "https://api.github.com/repos/projectcalico/calico/releases",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "manual_candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "urls": [
                {
                    "url": "https://raw.githubusercontent.com/projectcalico/"
                           "calico/<<<version>>>/manifests/canal.yaml",
                    "filename": "canal.yaml",
                    "patch": __patch_cni_canal,
                }
            ]
        }
    },
    "cilium": {
        "executable": {
            "version_command": ["cilium", "--context", "<<<context>>>", "version"],
            "version_regex": r"^cilium-cli: (v)(\d+)(\.)(\d+)(\.)(\d+) .*$",
            "candidate_version_url":
                "https://raw.githubusercontent.com/cilium/cilium-cli/master/stable.txt",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "manual_candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "urls": [
                {
                    "url": "https://github.com/cilium/cilium-cli/releases/"
                           "download/<<<version>>>/cilium-linux-<<<arch>>>.tar.gz",
                    "checksum_url":
                        "https://github.com/cilium/cilium-cli/releases/"
                        "download/<<<version>>>/cilium-linux-<<<arch>>>.tar.gz.sha256sum",
                    "checksum_type": "sha256",
                    "filename": "cilium",
                }
            ],
        },
        "CNI": {
            "version_command": ["cilium", "--context", "<<<context>>>", "version"],
            "version_regex": r"^cilium image \(running\): (\d+)(\.)(\d+)(\.)(\d+)$",
            "candidate_version_command": ["cilium", "--context", "<<<context>>>", "version"],
            "candidate_version_regex": r"^cilium image \(stable\): v(\d+)(\.)(\d+)(\.)(\d+)$",
            "manual_candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "upgrade": ["cilium", "--context", "<<<context>>>", "upgrade",
                        "--reset-then-reuse-values"],
            "install": ["cilium", "--context", "<<<context>>>", "install"],
            "uninstall": ["cilium", "--context", "<<<context>>>", "uninstall"],
        }
    },
    "flannel": {
        "CNI": {
            "candidate_version_function": get_github_version,
            "candidate_version_url":
                "https://api.github.com/repos/flannel-io/flannel/releases",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "manual_candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "urls": [
                {
                    "url": "https://github.com/flannel-io/flannel/releases/"
                           "download/<<<version>>>/kube-flannel.yml",
                    "filename": "flannel.yaml",
                    "patch": __patch_cni_flannel,
                }
            ]
        }
    },
    "kube-router": {
        "CNI": {
            "candidate_version_function": get_github_version,
            "candidate_version_url":
                "https://api.github.com/repos/cloudnativelabs/kube-router/releases",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "manual_candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "urls": [
                {
                    "url": "https://raw.githubusercontent.com/cloudnativelabs/"
                           "kube-router/<<<version>>>/daemonset/kubeadm-kuberouter.yaml",
                    "filename": "kube-router.yaml",
                }
            ]
        }
    },
    "weave": {
        "CNI": {
            "candidate_version_function": get_github_version,
            "candidate_version_url":
                "https://api.github.com/repos/weaveworks/weave/releases",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "manual_candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "urls": [
                {
                    "url": "https://github.com/weaveworks/weave/releases/"
                           "download/<<<version>>>/weave-daemonset-k8s-1.11.yaml",
                    "filename": "weave.yaml",
                    "patch": __patch_cni_weave,
                }
            ]
        }
    },
}
