#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
YAML I/O helpers
"""

import sys
from typing import Any, Optional
from collections.abc import Iterator
try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import yaml; "
             "you may need to (re-)run `cmt-install` or `pip3 install PyYAML`; aborting.")

from clustermanagementtoolkit import cmtio

from clustermanagementtoolkit.cmttypes import deep_get, DictPath, FilePath, SecurityChecks


def secure_write_yaml(path: FilePath, data: dict | list[dict], **kwargs: Any) -> None:
    """
    Dump a dict to a file in YAML-format in a safe manner

        Parameters:
            path (FilePath): The path to write to
            data (dict): The dict to dump
            **kwargs (dict[str, Any]): Keyword arguments
                permissions (int): File permissions (None uses system defaults)
                replace_empty (bool): True strips empty strings
                replace_null (bool): True strips null
                write_mode (str): [w, a, x] Write, Append, Exclusive Write
                temporary (bool): Is the file a tempfile?
                                  If so we need to disable the check for parent permissions
        Raises:
            cmttypes.FilePathAuditError
    """
    permissions: Optional[int] = deep_get(kwargs, DictPath("permissions"))
    replace_empty: bool = deep_get(kwargs, DictPath("replace_empty"), False)
    replace_null: bool = deep_get(kwargs, DictPath("replace_null"), False)
    sort_keys: bool = deep_get(kwargs, DictPath("sort_keys"), True)
    write_mode: str = deep_get(kwargs, DictPath("write_mode"), "w")
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    if write_mode not in ("a", "w", "x"):
        raise ValueError(f"Invalid write mode “{write_mode}“; "
                         "permitted modes: “a“ (append), “w“ (write) and “x“ (exclusive write)")

    yaml_str = yaml.safe_dump(data, default_flow_style=False, sort_keys=sort_keys)
    if replace_empty:
        yaml_str = yaml_str.replace(r"''", "")
    if replace_null:
        yaml_str = yaml_str.replace(r"null", "")
    cmtio.secure_write_string(path, yaml_str, permissions=permissions,
                              write_mode=write_mode, temporary=temporary)


def secure_read_yaml(path: FilePath, **kwargs: Any) -> Any:
    """
    Read data in YAML-format from a file in a safe manner

        Parameters:
            path (FilePath): The path to read from
            **kwargs (dict[str, Any]): Keyword arguments
                checks ([SecurityChecks]): A list of checks that should be performed
                directory_is_symlink (bool): The dir that the path points to is a symlink
                temporary (bool): Is the file a tempfile?
                                  If so we need to disable the check for parent permissions
        Returns:
            yaml_data (any): The read YAML-data
        Raises:
            yaml.composer.ComposerError
            yaml.parser.ParserError
            FileNotFoundError
            cmttypes.FilePathAuditError
    """
    checks: Optional[list[SecurityChecks]] = deep_get(kwargs, DictPath("checks"), None)
    directory_is_symlink: bool = deep_get(kwargs, DictPath("directory_is_symlink"), False)
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    string = cmtio.secure_read_string(path, checks=checks,
                                      directory_is_symlink=directory_is_symlink,
                                      temporary=temporary)
    return yaml.safe_load(string)


def secure_read_yaml_all(path: FilePath, **kwargs: Any) -> Iterator[Any]:
    """
    Read all dicts in YAML-format from a file in a safe manner
    Note: since the return type from safe_load_all() is an iterator
    evaluation does not happen until iterating; this means that exceptions
    must be handled when iterating rather than when getting the return value

        Parameters:
            path (FilePath): The path to read from
            **kwargs (dict[str, Any]): Keyword arguments
                checks ([SecurityChecks]): A list of checks that should be performed
                directory_is_symlink (bool): The dir that the path points to is a symlink
                temporary (bool): Is the file a tempfile?
                                  If so we need to disable the check for parent permissions
        Returns:
            iterator[any]: An iterator of data
        Raises:
            FileNotFoundError
            cmttypes.FilePathAuditError
    """
    checks: Optional[list[SecurityChecks]] = deep_get(kwargs, DictPath("checks"), None)
    directory_is_symlink: bool = deep_get(kwargs, DictPath("directory_is_symlink"), False)
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    string = cmtio.secure_read_string(path, checks=checks,
                                      directory_is_symlink=directory_is_symlink,
                                      temporary=temporary)
    return yaml.safe_load_all(string)
