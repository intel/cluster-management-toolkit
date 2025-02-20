#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Helpers for preparing/installing/tearing down/purging a cluster.
"""

import errno
import re
import sys
from typing import Any, cast, Optional

from clustermanagementtoolkit.ansible_helper import ansible_print_action_summary
from clustermanagementtoolkit.ansible_helper import populate_playbooks_from_filenames
from clustermanagementtoolkit.ansible_helper import ansible_run_playbook_on_selection
from clustermanagementtoolkit.ansible_helper import ansible_print_play_results
from clustermanagementtoolkit.ansible_helper import ansible_add_hosts, get_playbook_path

from clustermanagementtoolkit.ansithemeprint import ANSIThemeStr, ansithemeprint

from clustermanagementtoolkit.cmtlib import get_latest_upstream_version

from clustermanagementtoolkit.cmtpaths import ANSIBLE_INVENTORY

from clustermanagementtoolkit.cmttypes import deep_get, DictPath, FilePath

from clustermanagementtoolkit.networkio import get_github_version, scan_and_add_ssh_keys

from clustermanagementtoolkit import kubernetes_helper

cri_data: dict[str, dict[str, str]] = {
    "containerd": {
        "socket": "unix:///run/containerd/containerd.sock",
    },
    "cri-o": {
        "socket": "unix:///run/crio/crio.sock",
    },
}

prepare_playbooks: list[FilePath] = [
    FilePath("prepare_passwordless_ansible.yaml"),
    FilePath("prepare_node.yaml"),
]

setup_playbooks: list[FilePath] = [
    FilePath("add_kubernetes_repo.yaml"),
    FilePath("kubeadm_setup_node.yaml"),
]

join_playbooks: list[FilePath] = [
    FilePath("kubeadm_join_node.yaml"),
]

# For now we require the host to have the requisite packages to create VMs installed already,
# and for the ansible user to be a member of libvirt and kvm.
vm_create_template_playbooks: list[FilePath] = [
    FilePath("vm_template_create.yaml"),
    FilePath("vm_template_instantiate.yaml"),
]

# Commit template changes to the backing image.
vm_commit_template_playbooks: list[FilePath] = [
    FilePath("vm_template_commit.yaml"),
]

# For now we require the host to have the requisite packages to create VMs installed already,
# and for the ansible user to be a member of libvirt and kvm.
vm_create_playbooks: list[FilePath] = [
    FilePath("vm_create.yaml"),
    FilePath("vm_instantiate.yaml"),
]

# While destroy might sound extremely destructive, the VM-image remains untouched.
# destroy refers to the virtual machine, which we don't want running, since we will need
# use it as base image for new images.
vm_destroy_template_playbooks: list[FilePath] = [
    FilePath("vm_destroy.yaml"),
]


def get_crio_version(kubernetes_version: tuple[int, int]) -> Optional[tuple[str, str]]:
    """
    Given a Kubernetes version, return the matching cri-o version.

        Parameters:
            kubernetes_version ((int, int)): A version tuple (major, minor)
        Returns:
            (str, str): The cri-o version (major, minor)
    """
    # cri-o is built/distributed using OBS, hence we need to know the major.minor version
    # Apparently cri-o tries to keep more or less in lock-step with Kubernetes, so don't jump ahead,
    # and if Kubernetes gets ahead, use whatever is the most recent version of cri-o
    requested_major, requested_minor = kubernetes_version

    if (tmp := get_github_version("https://api.github.com/repos/cri-o/cri-o/releases",
                                  r"^v(\d+)\.(\d+)\.\d+$")) is None:
        return None

    version_tmp, _release_date, _body = tmp
    if requested_major < int(version_tmp[0]) \
            or requested_major == int(version_tmp[0]) and requested_minor < int(version_tmp[1]):
        crio_major_version = str(requested_major)
        crio_minor_version = str(requested_minor)
    else:
        crio_major_version = version_tmp[0]
        crio_minor_version = version_tmp[1]

    return crio_major_version, crio_minor_version


def get_control_planes(**kwargs: Any) -> list[tuple[str, list[str]]]:
    """
    Get the list of control planes.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
        Returns:
            [(str, [str])]: The list of control planes
                (str): The name of the control plane
                ([str]): A list of IP-addresses for the control plane
    """
    kh: kubernetes_helper.KubernetesHelper = deep_get(kwargs, DictPath("kubernetes_helper"))

    controlplanes = []

    vlist, status = kh.get_list_by_kind_namespace(("Node", ""), "")
    if status != 200:
        ansithemeprint([ANSIThemeStr("Error", "error"),
                        ANSIThemeStr(": API-server returned ", "default"),
                        ANSIThemeStr(f"{status}", "errorvalue"),
                        ANSIThemeStr("; aborting.", "default")], stderr=True)
        sys.exit(errno.EINVAL)
    if vlist is None:
        ansithemeprint([ANSIThemeStr("Error", "error"),
                        ANSIThemeStr(": API-server did not return any data", "default")],
                       stderr=True)
        sys.exit(errno.EINVAL)

    for node in vlist:
        name: str = deep_get(node, DictPath("metadata#name"))
        node_roles: list[str] = kubernetes_helper.get_node_roles(cast(dict, node))
        if "control-plane" in node_roles or "master" in node_roles:
            ipaddresses = []
            for address in deep_get(node, DictPath("status#addresses")):
                if deep_get(address, DictPath("type"), "") == "InternalIP":
                    ipaddresses.append(deep_get(address, DictPath("address")))
            controlplanes.append((name, ipaddresses))

    return controlplanes


# pylint: disable-next=too-many-locals
def get_api_server_package_version(**kwargs: Any) -> tuple[str, str, str]:
    """
    Get the package version for kubeadm/rke2 from the API-server.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                k8s_distro (str): The Kubernetes distribution
        Returns:
            ((str, str, str)): The package version for kubeadm/rke2
    """
    kh: kubernetes_helper.KubernetesHelper = deep_get(kwargs, DictPath("kubernetes_helper"))
    k8s_distro: str = deep_get(kwargs, DictPath("k8s_distro"), "kubeadm")

    control_plane_ip, _control_plane_port, _control_plane_path = kh.get_control_plane_address()
    if control_plane_ip is None:
        ansithemeprint([ANSIThemeStr("Error", "error"),
                        ANSIThemeStr(": Failed to get control plane IP; "
                                     "aborting.", "default")], stderr=True)
        sys.exit(errno.EBADMSG)

    # If this is a kubeadm cluster we need the package version for kubeadm;
    # if it's an RKE2 cluster we try to deduce the channel from the control plane
    # Kubernetes version
    if k8s_distro == "kubeadm":
        get_version_playbook_path = get_playbook_path(FilePath("get_versions.yaml"))
        retval, ansible_results = \
            ansible_run_playbook_on_selection(get_version_playbook_path,
                                              selection=[control_plane_ip], quiet=False)
        if not ansible_results:
            ansithemeprint([ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(": Failed to get package versions from control plane "
                                         f"at {control_plane_ip} (retval: {retval}); aborting.",
                                         "default")], stderr=True)
            sys.exit(errno.ENOENT)

        tmp = []

        for result in deep_get(ansible_results, DictPath(control_plane_ip), []):
            if deep_get(result, DictPath("task"), "") == "Package versions":
                tmp = deep_get(result, DictPath("msg_lines"), [])
                break

        if not tmp:
            ansithemeprint([ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(": Failed to get package versions from control plane "
                                         f"at {control_plane_ip} (playbook returned no valid "
                                         "data); aborting.", "default")], stderr=True)
            sys.exit(errno.EBADMSG)

        version = ""
        kubeadm_version_regex = re.compile(r"^(.*?): (.*)")

        for line in tmp:
            match_tmp = kubeadm_version_regex.match(line)
            if match_tmp is None:
                continue
            if match_tmp[1] == "kubeadm":
                version = match_tmp[2]
                break

        if not version:
            ansithemeprint([ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(": Failed to get ", "default"),
                            ANSIThemeStr("kubeadm", "programname"),
                            ANSIThemeStr(" package version from control plane at "
                                         f"{control_plane_ip}; aborting.", "default")], stderr=True)
            sys.exit(errno.ENOENT)

        # First remove the distro revision
        major_minor_patchrev, _pkgrev = version.split("-")
        # Now split the version tuple
        version_major, version_minor, _rest = major_minor_patchrev.split(".")
    elif k8s_distro == "rke2":
        vlist = get_control_planes()
        first_control_plane = vlist[0][0]
        node_data = kh.get_ref_by_kind_name_namespace(("Node", ""), first_control_plane, "")
        kubelet_version = deep_get(node_data, DictPath("status#nodeInfo#kubeletVersion"), "")
        match_tmp = re.match(r"^(v\d+)\.(\d+).*", kubelet_version)
        if match_tmp is None:
            ansithemeprint([ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(": Failed to get kubelet version from control plane; "
                                         "aborting.", "default")], stderr=True)
            sys.exit(errno.EBADMSG)
        version = f"{match_tmp[1]}.{match_tmp[2]}"
        version_major = match_tmp[1][1:]
        version_minor = match_tmp[2]
    return version, version_major, version_minor


def run_playbook(playbookpath: FilePath, hosts: list[str], extra_values: Optional[dict] = None,
                 quiet: bool = False, verbose: bool = False) -> tuple[int, dict]:
    """
    Run an Ansible playbook.

        Parameters:
            playbookpath (FilePath): A path to the playbook to run
            hosts ([str]): A list of hosts to run the playbook on
            extra_values (dict): A dict of values to set before running the playbook
            quiet (bool): Should the results of the run be printed? [unused]
            verbose (bool): If the results are printed, should skipped tasks be printed too?
        Returns:
            (int): The return value from ansible_run_playbook_on_selection()
            (dict): A dict with the results from the run
    """
    # The first patch revision that isn't available from the new repositories is 1.24.0,
    # but anything older than 1.28.0 is signed with a key that has expired, so only
    # include 1.28.0 and newer; the old repository is no longer usable.
    if (kubernetes_upstream_version := get_latest_upstream_version("kubernetes")) is None:
        ansithemeprint([ANSIThemeStr("Error", "error"),
                        ANSIThemeStr(": Could not get the latest upstream Kubernetes version; ",
                                     "default"),
                        ANSIThemeStr("this is either a network error or a bug; aborting.",
                                     "default")], stderr=True)
        sys.exit(errno.ENOENT)

    # Split the version tuple
    _upstream_major, upstream_minor, _rest = kubernetes_upstream_version.split(".")
    minor_versions = []
    for minor_version in range(28, int(upstream_minor) + 1):
        minor_versions.append(f"{minor_version}")

    values = {
        "minor_versions": minor_versions,
    }
    if extra_values:
        merged_values = {**values, **extra_values}
    else:
        merged_values = {**values}

    retval, ansible_results = \
        ansible_run_playbook_on_selection(playbookpath, selection=hosts,
                                          values=merged_values, quiet=False)
    if retval == -errno.ENOENT and not ansible_results:
        ansithemeprint([ANSIThemeStr("Error", "error"),
                        ANSIThemeStr(": ", "default"),
                        ANSIThemeStr(f"{ANSIBLE_INVENTORY}", "path"),
                        ANSIThemeStr(" is either empty or missing; aborting.", "default")],
                       stderr=True)
        sys.exit(errno.ENOENT)

    if not quiet:
        ansible_print_play_results(retval, ansible_results, verbose=verbose)
        print()

    return retval, ansible_results


def run_playbooks(playbooks: list[tuple[list[ANSIThemeStr], FilePath]], **kwargs: Any) -> int:
    """
    Run a set of Ansible playbooks.

        Parameters:
            playbooks ([([ANSIThemeStr], FilePath)]): A list of playbooks
            **kwargs (dict[str, Any]): Keyword arguments
                hosts (str): The hosts to run the playbooks on
                extra_values (dict): Variables to set before running the playbooks
                verbose (bool): If the results are printed, should skipped tasks be printed too?
        Returns:
            (int): 0 on success, non-zero on failure
    """
    hosts: Optional[list[str]] = deep_get(kwargs, DictPath("hosts"))
    extra_values: Optional[dict] = deep_get(kwargs, DictPath("extra_values"))
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)

    if not playbooks or hosts is None:
        return 0

    for string, playbookpath in playbooks:
        ansithemeprint(string)
        retval, _ansible_results = \
            run_playbook(playbookpath, hosts=hosts,
                         extra_values=extra_values, verbose=verbose)

        # We do not want to continue executing playbooks if the first one failed
        if retval != 0:
            break

    return retval


def prepare_nodes(hosts: list[str], **kwargs: Any) -> int:
    """
    Given a list of hostnames prepare them for use as cluster nodes.

        Parameters:
            hosts ([str]): A list of hosts to prepare as nodes
            **kwargs (dict[str, Any]): Keyword arguments
                extra_values (dict): Extra valeus to pass to Ansible
                verbose (bool): If the results are printed, should skipped tasks be printed too?
        Returns:
            (int): 0 on success, non-zero on failure
    """
    extra_values: dict = deep_get(kwargs, DictPath("extra_values"), {})
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)

    playbooks = populate_playbooks_from_filenames(prepare_playbooks)
    ansible_print_action_summary(playbooks)
    print()

    # Create inventory entries for the hosts; existing entries are silently ignored
    ansible_add_hosts(inventory=ANSIBLE_INVENTORY, hosts=hosts, skip_all=False)

    # Add the SSH keys for the new hosts
    scan_and_add_ssh_keys(hosts)

    # Now prepare the hosts
    return run_playbooks(playbooks=playbooks, hosts=hosts,
                         extra_values=extra_values, verbose=verbose)


def setup_nodes(hosts: list[str], **kwargs: Any) -> int:
    """
    Given a list of hostnames do every bit of setup except joining the nodes to the cluster.

        Parameters:
            hosts ([str]): A list of hosts to setup as nodes
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                k8s_distro (str): The Kubernetes distribution
                extra_values (dict): Extra valeus to pass to Ansible
                verbose (bool): If the results are printed, should skipped tasks be printed too?
        Returns:
            (int): 0 on success, non-zero on failure
    """
    kh: kubernetes_helper.KubernetesHelper = deep_get(kwargs, DictPath("kubernetes_helper"))
    k8s_distro: str = deep_get(kwargs, DictPath("k8s_distro"), "kubeadm")
    extra_values: dict = deep_get(kwargs, DictPath("extra_values"), {})
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)
    cri: str = deep_get(kwargs, DictPath("cri"))

    # Add the CRI to the setup playbooks for the control plane;
    # the list is short enough that doing prepend isn't a performance issue.
    setup_playbooks_with_cri = []
    if cri == "containerd":
        setup_playbooks_with_cri += [FilePath("setup_containerd.yaml")]
    elif cri == "cri-o":
        setup_playbooks_with_cri += [FilePath("setup_cri-o.yaml")]
    setup_playbooks_with_cri += setup_playbooks

    playbooks = populate_playbooks_from_filenames(setup_playbooks_with_cri)
    ansible_print_action_summary(playbooks)
    print()

    version, _version_major, _version_minor = \
        get_api_server_package_version(kubernetes_helper=kh, k8s_distro=k8s_distro)

    extra_values = {
        **extra_values,
        "control_plane_k8s_version": version,
    }

    # Now setup the hosts
    return run_playbooks(playbooks=playbooks, hosts=hosts,
                         extra_values=extra_values, verbose=verbose)


# pylint: disable-next=too-many-locals
def join_nodes(hosts: list[str], **kwargs: Any) -> int:
    """
    Given a list of hostnames join them as worker nodes to the cluster.

        earameters:
            hosts ([str]): A list of hosts to join to the cluster
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                k8s_distro (str): The Kubernetes distribution
                extra_values (dict): Extra valeus to pass to Ansible
                verbose (bool): If the results are printed, should skipped tasks be printed too?
        Returns:
            (int): 0 on success, non-zero on failure
    """
    kh: kubernetes_helper.KubernetesHelper = deep_get(kwargs, DictPath("kubernetes_helper"))
    k8s_distro: str = deep_get(kwargs, DictPath("k8s_distro"), "kubeadm")
    cri: str = deep_get(kwargs, DictPath("cri"))
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)
    extra_values: dict = deep_get(kwargs, DictPath("extra_values"), {})

    cri_socket: str = deep_get(cri_data[cri], DictPath("socket"))

    join_token = None
    ca_cert_hash = None

    version, version_major, version_minor = \
        get_api_server_package_version(kubernetes_helper=kh, k8s_distro=k8s_distro)
    if k8s_distro == "kubeadm":
        join_token = kh.get_join_token()
        ca_cert_hash = kh.get_ca_cert_hash()

    control_plane_ip, control_plane_port, control_plane_path = kh.get_control_plane_address()
    if control_plane_ip is None:
        ansithemeprint([ANSIThemeStr("\nAborting", "error"),
                        ANSIThemeStr(": Could not get the IP-address for the control plane.",
                                     "default")], stderr=True)
        sys.exit(errno.ENOENT)

    playbooks = populate_playbooks_from_filenames(join_playbooks)
    ansible_print_action_summary(playbooks)
    print()

    # Currently we only support kubeadm
    if k8s_distro == "kubeadm":
        if int(version_minor) < 31:
            join_configuration_api_version = "kubeadm.k8s.io/v1beta3"
        else:
            join_configuration_api_version = "kubeadm.k8s.io/v1beta4"

        extra_values = {
            **extra_values,
            "control_plane_ip": control_plane_ip,
            "control_plane_port": control_plane_port,
            "control_plane_path": control_plane_path,
            "join_token": join_token,
            "ca_cert_hash": ca_cert_hash,
            "configuration_path": "templates/config/nodeconfig.yaml.j2",
            "control_plane_k8s_version": version,
            "cri_socket": cri_socket,
            "kubernetes_major_minor_version": f"{version_major}.{version_minor}",
            "join_configuration_api_version": join_configuration_api_version,
        }

    # Now join the hosts
    return run_playbooks(playbooks=playbooks, hosts=hosts,
                         extra_values=extra_values, verbose=verbose)


def prepare_vm_template(vmhost: str, hosts: list[tuple[str, str, str]], **kwargs: Any) -> int:
    """
    Create a template VM image to use when instantiating virtualised nodes.

        Parameters:
            vmhost (str): The name of the host that runs the VMs
            hosts ([(str, str, str)]): The hostname, IP-address, and MAC-address of the template VM
            **kwargs (dict[str, Any]): Keyword arguments
                os_image (FilePath): The local path to the OS image to use
                template_name (str): The name of the template image
                template_balloon_size (str): The ballooned size of the template image
                extra_values (dict): Extra valeus to pass to Ansible
                verbose (bool): If the results are printed, should skipped tasks be printed too?
        Returns:
            (int): 0 on success, non-zero on failure
    """
    kh: kubernetes_helper.KubernetesHelper = deep_get(kwargs, DictPath("kubernetes_helper"))
    os_image: FilePath = deep_get(kwargs, DictPath("os_image"))
    os_variant: str = deep_get(kwargs, DictPath("os_variant"))
    template_name: str = deep_get(kwargs, DictPath("template_name"))
    template_balloon_size: str = deep_get(kwargs, DictPath("template_balloon_size"))
    extra_values: dict[str, Any] = deep_get(kwargs, DictPath("extra_values"), {})
    cri: str = deep_get(kwargs, DictPath("cri"))
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)

    playbooks = populate_playbooks_from_filenames(vm_create_template_playbooks)
    ansible_print_action_summary(playbooks)
    print()

    extra_values = {
        **extra_values,
        "base_image": os_image,
        "base_image_name": os_image.basename(),
        "os_variant": os_variant,
        "template_name": template_name,
        "template_balloon_size": template_balloon_size,
        "instances": hosts,
    }

    # Now prepare the VM-template
    retval = run_playbooks(playbooks=playbooks, hosts=[vmhost],
                           extra_values=extra_values, verbose=verbose)

    hostnames = [hostname for hostname, _ipaddress, _macaddress in hosts]

    if not retval:
        # We've got a running VM to turn into a template;
        # we need to set it up as a Kubernetes node now.
        # Every single step except adding it to the cluster.
        retval = setup_nodes(hostnames, kubernetes_helper=kh, extra_values=extra_values, cri=cri)

    if not retval:
        # The template image is prepared and all necessary packages
        # and configuration should be installed on it. At this point we need to shut down the VM.
        playbooks = populate_playbooks_from_filenames(vm_destroy_template_playbooks)
        ansible_print_action_summary(playbooks)
        print()
        retval = run_playbooks(playbooks=playbooks, hosts=[vmhost],
                               extra_values=extra_values, verbose=verbose)

    if not retval:
        # The template image is no longer running as a VM.
        # Time to commit the changes to the backing mimage.
        playbooks = populate_playbooks_from_filenames(vm_commit_template_playbooks)
        ansible_print_action_summary(playbooks)
        print()
        retval = run_playbooks(playbooks=playbooks, hosts=[vmhost],
                               extra_values=extra_values, verbose=verbose)

    return retval


def create_vm_hosts(vmhost: str, hosts: list[tuple[str, str, str]], **kwargs: Any) -> int:
    """
    Create VM hosts.

        Parameters:
            vmhost (str): The name of the host that runs the VMs
            hosts ([(str, str, str)]): The hostname, IP-address, and MAC-address of the hosts
            **kwargs (dict[str, Any]): Keyword arguments
                os_image (FilePath): The local path to the OS image to use
                os_variant (str): The OS variant for the OS image
                template_name (str): The name of the template image
                extra_values (dict): Extra valeus to pass to Ansible
                verbose (bool): If the results are printed, should skipped tasks be printed too?
        Returns:
            (int): 0 on success, non-zero on failure
    """
    os_image: FilePath = deep_get(kwargs, DictPath("os_image"))
    os_variant: str = deep_get(kwargs, DictPath("os_variant"))
    extra_values: dict = deep_get(kwargs, DictPath("extra_values"), {})
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)

    playbooks = populate_playbooks_from_filenames(vm_create_playbooks)
    ansible_print_action_summary(playbooks)
    print()

    extra_values = {
        **extra_values,
        "base_image_name": os_image.basename(),
        "os_variant": os_variant,
        "instances": hosts,
    }

    # Now prepare the VM-template
    retval = run_playbooks(playbooks=playbooks, hosts=[vmhost],
                           extra_values=extra_values, verbose=verbose)

    # OK, we now have VMs running that can be joined as nodes. Our job here is done.
    return retval
