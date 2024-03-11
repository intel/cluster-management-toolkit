#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Helper for installing and upgrading CNI
"""

from typing import Any, Dict

from cmtio import check_path, execute_command, join_securitystatus_set
from cmttypes import FilePath, FilePathAuditError, SecurityStatus
from networkio import get_github_version


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
    violations = check_path(cni_path)
    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=cni_path)

    # Ideally we should patch this using a round-trip capable YAML parser,
    # such as ruamel
    sedstr = fr's#cidr: 192.168.0.0/16$#cidr: {pod_network_cidr}#'
    args = ["/usr/bin/sed", "-i", "-e", sedstr, cni_path]
    return execute_command(args)


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
    violations = check_path(cni_path)
    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=cni_path)

    # Ideally we should patch this using a round-trip capable YAML parser,
    # such as ruamel
    # This seems like the obvious thing to patch
    sedstr = fr's#^\(.*"\)Network": "10.244.0.0/16"\(,.*\)$#\1Network": "{pod_network_cidr}"\2#'
    args = ["/usr/bin/sed", "-i", "-e", sedstr, cni_path]
    if not (retval := execute_command(args)):
        return retval
    # According to the canal documentation this should be patched too;
    # let's patch both just in case
    sedstr = r's,# - name: CALICO_IPV4POOL_CIDR$,- name: CALICO_IPV4POOL_CIDR,'
    args = ["/usr/bin/sed", "-i", "-e", sedstr, cni_path]
    if not (retval := execute_command(args)):
        return retval
    sedstr = fr's,  value: "192.168.0.0/16"$,#   value: "{pod_network_cidr}",'
    args = ["/usr/bin/sed", "-i", "-e", sedstr, cni_path]
    return execute_command(args)


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
    violations = check_path(cni_path)
    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=cni_path)

    # Ideally we should patch this using a round-trip capable YAML parser,
    # such as ruamel
    sedstr = fr's#^\(.*"\)Network": "10.244.0.0/16",$#\1Network": "{pod_network_cidr}",#'
    args = ["/usr/bin/sed", "-i", "-e", sedstr, cni_path]
    return execute_command(args)


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
    violations = check_path(cni_path)
    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=cni_path)

    # Ideally we should patch this using a round-trip capable YAML parser,
    # such as ruamel
    sedstr_remove_existing = r'/^                - name: IPALLOC_RANGE$/,+1d'
    args = ["/usr/bin/sed", "-i", "-e", sedstr_remove_existing, cni_path]
    if not (retval := execute_command(args)):
        return retval

    sedstr_add_new = fr's#^\(.*\)\(- name: INIT_CONTAINER\)$#\1- name: " \
                     f"IPALLOC_RANGE\n\1  value: {pod_network_cidr}\n\1\2#'
    args = ["/usr/bin/sed", "-i", "-e", sedstr_add_new, cni_path]
    return execute_command(args)


cni_data: Dict[str, Any] = {
    "antrea": {
        "CNI": {
            "candidate_version_function": get_github_version,
            "candidate_version_url":
                "https://api.github.com/repos/antrea-io/antrea/releases/latest",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
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
                "https://api.github.com/repos/projectcalico/calico/releases/latest",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
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
                "https://api.github.com/repos/projectcalico/calico/releases/latest",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
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
                "https://api.github.com/repos/projectcalico/calico/releases/latest",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
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
            "version_regex": r"^cilium image \(running\): (v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "candidate_version_command": ["cilium", "--context", "<<<context>>>", "version"],
            "candidate_version_regex": r"^cilium image \(default\): (v)(\d+)(\.)(\d+)(\.)(\d+)$",
            "upgrade": ["cilium", "--context", "<<<context>>>", "upgrade"],
            "install": ["cilium", "--context", "<<<context>>>", "install"],
            "uninstall": ["cilium", "--context", "<<<context>>>", "uninstall"],
        }
    },
    "flannel": {
        "CNI": {
            "candidate_version_function": get_github_version,
            "candidate_version_url":
                "https://api.github.com/repos/flannel-io/flannel/releases/latest",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
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
                "https://api.github.com/repos/cloudnativelabs/kube-router/releases/latest",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
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
                "https://api.github.com/repos/weaveworks/weave/releases/latest",
            "candidate_version_regex": r"(v)(\d+)(\.)(\d+)(\.)(\d+)$",
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
