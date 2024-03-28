#! /usr/bin/env python3
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Get data for fields in a list; typically used to populate _extra_data
"""

import about
import copy
from typing import Any, Callable, Dict, List

from cmttypes import deep_get, DictPath, ProgrammingError


def fieldgetter_cmt_version(**kwargs: Any) -> List[Any]:
    """
    A fieldgetter that provides the version
    of the Cluster Version Toolkit

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                fields ([int]): The indexes of the CMT version fields to return
        Returns:
            [str]: The list of cmt versions
    """
    fields: List[Any] = deep_get(kwargs, DictPath("fields"), [])
    versions = [
        about.PROGRAM_SUITE_VERSION,
        about.UI_PROGRAM_VERSION,
        about.TOOL_PROGRAM_VERSION,
        about.ADMIN_PROGRAM_VERSION,
        about.INVENTORY_PROGRAM_VERSION,
        about.INSTALL_PROGRAM_VERSION,
    ]
    version_strings = []
    for field in fields:
        if field < len(versions):
            version_strings.append(versions[field])
    return version_strings


def fieldgetter_api_server_version(**kwargs: Any) -> List[Any]:
    """
    A fieldgetter that provides the version
    of the Kubernetes API-server

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                fields ([int]): The indexes of the API-server version fields to return
        Returns:
            [str]: The list of API-server version fields
    """
    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("fieldgetter_api_server_version() called without kubernetes_helper")
    fields: List[Any] = deep_get(kwargs, DictPath("fields"), [])

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
fieldgetter_allowlist: Dict[str, Callable] = {
    "fieldgetter_cmt_version": fieldgetter_cmt_version,
    "fieldgetter_api_server_version": fieldgetter_api_server_version,
}
