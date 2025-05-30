#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Get data for fields in a list; typically used to populate _extra_data
"""

import copy
import re
from typing import Any, Optional
from collections.abc import Callable

from clustermanagementtoolkit.cmtio import execute_command_with_response, secure_which

from clustermanagementtoolkit.cmtpaths import HOMEDIR

from clustermanagementtoolkit.cmttypes import deep_get, DictPath, FilePath
from clustermanagementtoolkit.cmttypes import ProgrammingError, SecurityPolicy


def fieldgetter_executable_version(**kwargs: Any) -> list[Any]:
    """
    A fieldgetter that provides the version from an executable.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                executable (str): The executable to get the version for
                args ([str]): The arguments to pass to the executable
                version_regex (str): The regular expression to use to extract the version
        Returns:
            [str]: The version tuple
    """
    executable: FilePath = FilePath(deep_get(kwargs, DictPath("executable"), ""))
    args: list[str] = deep_get(kwargs, DictPath("args"), [])
    version_regex: str = deep_get(kwargs, DictPath("version_regex"), '')

    security_policy = SecurityPolicy.ALLOWLIST_RELAXED
    fallback_allowlist = ["/bin", "/sbin", "/usr/bin", "/usr/sbin",
                          "/usr/local/bin", "/usr/local/sbin", f"{HOMEDIR}/bin"]

    try:
        executable_path = secure_which(FilePath(executable), fallback_allowlist=fallback_allowlist,
                                       security_policy=security_policy)
    except FileNotFoundError:
        executable_path = None

    version = []

    if executable_path:
        result: Optional[str] = execute_command_with_response([executable_path] + args)
        if result:
            for line in result.splitlines():
                if (tmp := re.match(version_regex, line)) is not None:
                    for field in tmp.groups():
                        version.append(field)
    return ["".join(version)]


# pylint: disable-next=too-many-branches
def fieldgetter_crc_version(**kwargs: Any) -> list[Any]:
    """
    A fieldgetter that provides the version of Code Ready Containers (CRC).

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                fields ([int]): The indexes of the CRC version fields to return
        Returns:
            ([str]): The list of CRC version fields
    """
    fields: list[Any] = deep_get(kwargs, DictPath("fields"), [])
    security_policy = SecurityPolicy.ALLOWLIST_RELAXED
    fallback_allowlist = ["/bin", "/sbin", "/usr/bin", "/usr/sbin",
                          "/usr/local/bin", "/usr/local/sbin", f"{HOMEDIR}/bin"]

    versions = ["", "", "", ""]

    try:
        crc_path = secure_which(FilePath("/usr/bin/crc"), fallback_allowlist=fallback_allowlist,
                                security_policy=security_policy)
    except FileNotFoundError:
        crc_path = None

    if crc_path:
        args = ["status"]
        result: Optional[str] = execute_command_with_response([crc_path] + args)

        if result:
            for line in result.splitlines():
                if "Machine does not exist" in line:
                    result = None

        if result is not None:
            # OK, we hopefully have a CRC cluster setup; it might not be running, but that's OK,
            # we want the version information anyway.
            args = ["version"]
            result = execute_command_with_response([crc_path] + args)

        if result is not None:
            for line in result.splitlines():
                if line.startswith("CRC version: "):
                    versions[0] = line.removeprefix("CRC version: ")
                elif line.startswith("OpenShift version: "):
                    versions[1] = line.removeprefix("OpenShift version: ")
                elif line.startswith("MicroShift version: "):
                    versions[2] = line.removeprefix("MicroShift version: ")
                elif line.startswith("Podman version: "):
                    versions[3] = line.removeprefix("Podman version: ")

    version_strings = []
    for field in fields:
        if field < len(versions):
            version_strings.append(versions[field])
    return version_strings


def fieldgetter_api_server_version(**kwargs: Any) -> list[Any]:
    """
    A fieldgetter that provides the version of the Kubernetes API-server.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                fields ([int]): The indexes of the API-server version fields to return
        Returns:
            ([str]): The list of API-server version fields
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("fieldgetter_api_server_version() called without kubernetes_helper")
    fields: list[Any] = deep_get(kwargs, DictPath("fields"), [])

    field_list = []
    result = kh.get_api_server_version()
    if not fields:
        field_list = list(copy.deepcopy(result))
    else:
        for i, field in enumerate(result):
            if i in fields:
                field_list.append(field)
    return field_list


# Fieldgetters acceptable for direct use in view files
fieldgetter_allowlist: dict[str, Callable] = {
    "fieldgetter_api_server_version": fieldgetter_api_server_version,
    "fieldgetter_crc_version": fieldgetter_crc_version,
    "fieldgetter_executable_version": fieldgetter_executable_version,
}
