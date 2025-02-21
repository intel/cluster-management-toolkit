#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
YAML I/O helpers
"""

import io
import sys
from typing import Any, Optional, Union
from collections.abc import Generator
try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import yaml; "
             "you may need to (re-)run `cmt-install` or `pip3 install PyYAML`; aborting.")
try:
    import ruyaml
    ryaml = ruyaml.YAML()
    sryaml = ruyaml.YAML(typ="safe")
except ModuleNotFoundError:  # pragma: no cover
    try:
        import ruamel.yaml as ruyaml  # type: ignore
        ryaml = ruyaml.YAML()
        sryaml = ruyaml.YAML(typ="safe")
    except ModuleNotFoundError:  # pragma: no cover
        sys.exit("ModuleNotFoundError: Could not import ruyaml/ruamel.yaml; "
                 "you may need to (re-)run `cmt-install` or `pip3 install ruyaml/ruamel.yaml`; "
                 "aborting.")

from clustermanagementtoolkit import cmtio

from clustermanagementtoolkit.cmttypes import deep_get, DictPath, FilePath, SecurityChecks


# pylint: disable=unused-argument
def __representer_none(self: Any, data: None) -> Any:
    return self.represent_scalar("tag:yaml.org,2002:null", "null")  # pragma: nocover


def ruyaml_dump_to_string(obj: Any, **kwargs: Any) -> str:
    """
    Dump a dict to a YAML-string

        Parameters:
            obj (dict|[dict]): The dict to dump
            **kwargs (dict[str, Any]): Keyword arguments
                replace_empty (bool): True strips empty strings
                replace_empty_dict (bool): True strips empty dicts
                replace_null (bool): True strips null
    """
    replace_null: bool = deep_get(kwargs, DictPath("replace_null"), False)
    replace_empty: bool = deep_get(kwargs, DictPath("replace_empty"), False)
    replace_empty_dict: bool = deep_get(kwargs, DictPath("replace_empty_dict"), False)
    ryaml.default_flow_style = deep_get(kwargs, DictPath("default_flow_style"), False)
    ryaml.representer.add_representer(type(None), __representer_none)
    f = io.StringIO()

    if isinstance(obj, (dict, ruyaml.comments.CommentedMap, ruyaml.comments.CommentedSeq)):
        ryaml.dump(obj, f)
    else:
        for d in obj:
            f.write("---\n")
            ryaml.dump(d, f)
    string = f.getvalue()
    f.close()
    if replace_empty:
        string = string.replace(r"''", "")
    if replace_empty_dict:
        string = string.replace(r"{}", "")
    if replace_null:
        string = string.replace(r"null", "")
    return string


def secure_write_yaml(path: FilePath,
                      data: Union[dict, list[dict],
                                  ruyaml.comments.CommentedMap, ruyaml.comments.CommentedSeq],
                      **kwargs: Any) -> None:
    """
    Dump a dict to a file in YAML-format in a safe manner

        Parameters:
            path (FilePath): The path to write to
            data (dict|[dict]): The dict to dump
            **kwargs (dict[str, Any]): Keyword arguments
                permissions (int): File permissions (None uses system defaults)
                replace_empty (bool): True strips empty strings
                replace_empty_dict (bool): True strips empty dicts
                replace_null (bool): True strips null
                write_mode (str): [w, a, x] Write, Append, Exclusive Write
                temporary (bool): Is the file a tempfile?
                                  If so we need to disable the check for parent permissions
        Raises:
            cmttypes.FilePathAuditError
    """
    permissions: Optional[int] = deep_get(kwargs, DictPath("permissions"))
    replace_empty: bool = deep_get(kwargs, DictPath("replace_empty"), False)
    replace_empty_dict: bool = deep_get(kwargs, DictPath("replace_empty_dict"), False)
    replace_null: bool = deep_get(kwargs, DictPath("replace_null"), False)
    write_mode: str = deep_get(kwargs, DictPath("write_mode"), "w")
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    if write_mode not in ("a", "w", "x"):
        raise ValueError(f"Invalid write mode “{write_mode}“; "
                         "permitted modes: “a“ (append), “w“ (write) and “x“ (exclusive write)")

    yaml_str = ruyaml_dump_to_string(data, default_flow_style=False,
                                     replace_null=replace_null,
                                     replace_empty=replace_empty,
                                     replace_empty_dict=replace_empty_dict)
    cmtio.secure_write_string(path, yaml_str, permissions=permissions,
                              write_mode=write_mode, temporary=temporary)


def secure_read_yaml(path: FilePath, **kwargs: Any) -> Union[dict,
                                                             ruyaml.comments.CommentedMap,
                                                             ruyaml.comments.CommentedSeq]:
    """
    Read data in YAML-format from a file in a safe manner

        Parameters:
            path (FilePath): The path to read from
            **kwargs (dict[str, Any]): Keyword arguments
                checks ([SecurityChecks]): A list of checks that should be performed
                directory_is_symlink (bool): The dir that the path points to is a symlink
                temporary (bool): Is the file a tempfile?
                                  If so we need to disable the check for parent permissions
                asynchronous (bool): The data should be read asynchronous; use PyYAML
        Returns:
            yaml_data
                (dict|ruyaml.comments.CommentedMap|ruyaml.comments.CommentedSeq): The read YAML-data
        Raises:
            ruyaml.composer.ComposerError
            ruyaml.scanner.ScannerError
            FileNotFoundError
            cmttypes.FilePathAuditError
    """
    checks: Optional[list[SecurityChecks]] = deep_get(kwargs, DictPath("checks"), None)
    directory_is_symlink: bool = deep_get(kwargs, DictPath("directory_is_symlink"), False)
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)
    asynchronous: bool = deep_get(kwargs, DictPath("asynchronous"), False)

    string = cmtio.secure_read_string(path, checks=checks,
                                      directory_is_symlink=directory_is_symlink,
                                      temporary=temporary)
    if asynchronous:
        return yaml.safe_load(string)

    # First parse the data with safe parser; this will throw an exception if there are issues
    _d2 = sryaml.load(string)

    # If nothing went wrong, we import the round-trip formatted data
    tmp = ryaml.load(string)
    return tmp


def secure_read_yaml_all(path: FilePath, **kwargs: Any) -> Generator:
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
            Generator: An iterator of data
        Raises:
            FileNotFoundError
            cmttypes.FilePathAuditError
            ruyaml.composer.ComposerError
            ruyaml.scanner.ScannerError
    """
    checks: Optional[list[SecurityChecks]] = deep_get(kwargs, DictPath("checks"), None)
    directory_is_symlink: bool = deep_get(kwargs, DictPath("directory_is_symlink"), False)
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    string = cmtio.secure_read_string(path, checks=checks,
                                      directory_is_symlink=directory_is_symlink,
                                      temporary=temporary)
    return ryaml.load_all(string)
