#! /usr/bin/env python3
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Get data for fields in a list; typically used to populate _extra_data
"""

import copy
from typing import Any, Callable, Dict, List

from cmttypes import deep_get, DictPath, ProgrammingError


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
    "fieldgetter_api_server_version": fieldgetter_api_server_version,
}
