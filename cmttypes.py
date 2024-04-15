#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.8)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
This file contains custom types used to define types used by CMT.
"""

# pylint: disable=too-many-lines

from datetime import datetime
from enum import auto, Enum, IntEnum
from functools import reduce
import os
from pathlib import Path, PurePath
import sys
import traceback
from typing import Any, Dict, List, NewType, Optional, Tuple, Union

DictPath = NewType("DictPath", str)


class FilePath(str):
    """
    A wrapper used for paths, to ensure correct types.
    """

    def __init__(self, path: Union["FilePath", str, Path, PurePath]) -> None:
        self.path = str(path)

    def basename(self) -> str:
        """
        Returns the filename part of the FilePath.

            Returns:
                (str): The filename path of the FilePath.
        """
        return os.path.basename(self.path)

    def dirname(self) -> "FilePath":
        """
        Returns the dirname part of the FilePath.

            Returns:
                (FilePath): The dirname path of the FilePath.
        """
        return FilePath(os.path.dirname(self.path))

    def joinpath(self, *paths: Any) -> "FilePath":
        """
        Perform a path join on a FilePath
        with either a PurePath, a str, a FilePath,
        a list of strings, or a tuple of strings.

            Parameters:
                paths (str|FilePath|PurePath|List|Tuple): The path(s) to append
            Returns:
                (FilePath): The new FilePath
            Raises:
                TypeError: paths was an unsupported type
        """
        # PurePath will raise TypeError if an element
        # in the list/tuple isn't a string
        return FilePath(PurePath(self.path).joinpath(*paths))


def reformat_msg(msg: List[List[Tuple[str, str]]]) -> str:
    """
    Given a structured error message return a plaintext representation.

        Parameters:
            msg ([[(str, str)]]): A structured message for format
        Returns:
            (str): The plaintext representation
    """
    joined_strings = []

    for line in msg:
        joined_string = ""
        for string, _fmt in line:
            joined_string += string
        joined_strings.append(joined_string)
    return "\n".join(joined_strings)


# Keep this first so we can use it in the exceptions
def deep_get(dictionary: Optional[Dict], path: DictPath, default: Any = None) -> Any:
    """
    Given a dictionary and a path into that dictionary, get the value.

        Parameters:
            dictionary (dict): The dict to get the value from
            path (DictPath): A dict path
            default (Any): The value to return if the dictionary, path, or result is None
        Returns:
            (Any): The value from the path
    """
    if dictionary is None:
        return default
    if path is None or not path:
        return default
    result = reduce(lambda d,
                    key: d.get(key, default) if isinstance(d, dict) else default,
                    path.split("#"), dictionary)
    if result is None:
        result = default
    return result


# pylint: disable-next=too-many-instance-attributes
class UnknownError(Exception):
    """
    Exception raised when an error occurs that we have no further information about
    Note: severity and formatted_msg use Any as type to avoid recursive imports,
    but they are typically LogLevel and List[ANSIThemeStr], respectively.

    Optional arguments are normally deduced; overriding them is only necessary in special cases.

        Attributes:
            message (str): Additional information about the error
            severity (any): The severity
            facility (str): A facility
            formatted_msg (any); A formatted version of the message
            timestamp (datetime): A timestamp (optional)
            file (str): The file the error occurred in (optional)
            function (str): The function the error occurred in (optional)
            lineno (str): The line the error occurred on (optional)
            ppid (str): The parent pid of the process (optional)
    """
    traceback: Optional[str] = None

    def __init__(self, message: str, **kwargs: Any) -> None:
        severity: Optional[Any] = deep_get(kwargs, DictPath("severity"))
        facility: Optional[str] = deep_get(kwargs, DictPath("facility"))
        formatted_msg: Optional[Any] = deep_get(kwargs, DictPath("formatted_msg"))
        timestamp: Optional[datetime] = deep_get(kwargs, DictPath("timestamp"))
        file: Optional[str] = deep_get(kwargs, DictPath("file"))
        function: Optional[str] = deep_get(kwargs, DictPath("function"))
        lineno: Optional[int] = deep_get(kwargs, DictPath("lineno"))
        ppid: Optional[int] = deep_get(kwargs, DictPath("ppid"))

        try:
            # This is to get the necessary stack info
            raise UserWarning
        except UserWarning:
            frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
            self.file = str(frame.f_code.co_filename)  # type: ignore
            self.function = str(frame.f_code.co_name)  # type: ignore
            self.lineno = int(frame.f_lineno)  # type: ignore

        self.exception = __class__.__name__  # type: ignore
        self.message = message
        self.severity = severity
        self.facility = facility
        self.formatted_msg = formatted_msg
        if timestamp is None:
            self.timestamp = datetime.now()
        else:
            self.timestamp = timestamp
        if file is not None:
            self.file = file
        if function is not None:
            self.function = function
        if lineno is not None:
            self.lineno = lineno
        if ppid is not None:
            self.ppid = ppid
        else:
            self.ppid = os.getppid()
        self.traceback = "".join(traceback.format_stack())

        super().__init__(message)

    def __str__(self) -> str:
        """
        Return a string representation of the exception.

            Returns:
                (str): The string representation of the exception
        """
        if not self.message:
            message = "No further details were provided"
        else:
            message = self.message

        return message

    def exception_dict(self) -> Dict:
        """
        Return a dictionary containing structured information about the exception.

            Returns:
                (dict): A dictionary with structured information
        """
        return {
            "exception": self.exception,
            "message": self.message,
            "severity": self.severity,
            "facility": self.facility,
            "formatted_msg": self.formatted_msg,
            "timestamp": self.timestamp,
            "file": self.file,
            "function": self.function,
            "lineno": self.lineno,
            "ppid": self.ppid,
            "traceback": self.traceback,
        }


# pylint: disable-next=too-many-instance-attributes
class ArgumentValidationError(Exception):
    """
    Exception raised when argument validation fails.
    Note: severity use Any as type to avoid recursive imports,
    but it is typically LogLevel.

    Optional arguments are normally deduced; overriding them is only necessary in special cases.

        Attributes:
            message (str): Additional information about the error
            subexception (Exception): Related standard exception
            severity (any): The severity
            facility (str): A facility
            formatted_msg ([[(str, str)]]); A formatted version of the message
            timestamp (datetime): A timestamp (optional)
            file (str): The file the error occurred in (optional)
            function (str): The function the error occurred in (optional)
            lineno (str): The line the error occurred on (optional)
            ppid (str): The parent pid of the process (optional)
    """
    traceback: Optional[str] = None

    def __init__(self, **kwargs: Any) -> None:
        message: Optional[str] = deep_get(kwargs, DictPath("message"))
        subexception: Optional[Exception] = deep_get(kwargs, DictPath("subexception"))
        severity: Optional[Any] = deep_get(kwargs, DictPath("severity"))
        facility: Optional[str] = deep_get(kwargs, DictPath("facility"))
        formatted_msg: Optional[List[List[Tuple[str, str]]]] = deep_get(kwargs,
                                                                        DictPath("formatted_msg"))
        timestamp: Optional[datetime] = deep_get(kwargs, DictPath("timestamp"))
        file: Optional[str] = deep_get(kwargs, DictPath("file"))
        function: Optional[str] = deep_get(kwargs, DictPath("function"))
        lineno: Optional[int] = deep_get(kwargs, DictPath("lineno"))
        ppid: Optional[int] = deep_get(kwargs, DictPath("ppid"))
        try:
            # This is to get the necessary stack info
            raise UserWarning
        except UserWarning:
            frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
            self.file = str(frame.f_code.co_filename)  # type: ignore
            self.function = str(frame.f_code.co_name)  # type: ignore
            self.lineno = int(frame.f_lineno)  # type: ignore

        if message is None and formatted_msg is not None and formatted_msg:
            message = reformat_msg(formatted_msg)

        self.exception = __class__.__name__  # type: ignore
        self.subexception = subexception
        self.message = message
        self.severity = severity
        self.facility = facility
        self.formatted_msg = formatted_msg
        if timestamp is None:
            self.timestamp = datetime.now()
        else:
            self.timestamp = timestamp
        if file is not None:
            self.file = file
        if function is not None:
            self.function = function
        if lineno is not None:
            self.lineno = lineno
        if ppid is not None:
            self.ppid = ppid
        else:
            self.ppid = os.getppid()
        self.traceback = "".join(traceback.format_stack())

        super().__init__(message)

    def __str__(self) -> str:
        """
        Return a string representation of the exception.

            Returns:
                (str): The string representation of the exception
        """
        if self.subexception is None:
            message = ""
        else:
            message = f"({self.subexception}): "

        if not self.message:
            message += "No further details were provided"
        else:
            message += f"{self.message}"

        return message

    def exception_dict(self) -> Dict:
        """
        Return a dictionary containing structured information about the exception.

            Returns:
                (dict): A dictionary with structured information
        """
        return {
            "exception": self.exception,
            "subexception": self.subexception,
            "message": self.message,
            "severity": self.severity,
            "facility": self.facility,
            "formatted_msg": self.formatted_msg,
            "timestamp": self.timestamp,
            "file": self.file,
            "function": self.function,
            "lineno": self.lineno,
            "ppid": self.ppid,
            "traceback": self.traceback,
        }


# pylint: disable-next=too-many-instance-attributes
class ProgrammingError(Exception):
    """
    Exception raised when a condition occured that is most likely caused by a programming error
    Note: severity and formatted_msg use Any as type to avoid recursive imports,
    but they are typically LogLevel and List[ANSIThemeStr], respectively.

    Optional arguments are normally deduced; overriding them is only necessary in special cases.

        Attributes:
            message (str): Additional information about the error
            subexception (Exception): Related standard exception
            severity (any): The severity
            facility (str): A facility
            formatted_msg (any); A formatted version of the message
            timestamp (datetime): A timestamp (optional)
            file (str): The file the error occurred in (optional)
            function (str): The function the error occurred in (optional)
            lineno (str): The line the error occurred on (optional)
            ppid (str): The parent pid of the process (optional)
    """
    traceback: Optional[str] = None

    def __init__(self, message: str, **kwargs: Any) -> None:
        subexception: Optional[Exception] = deep_get(kwargs, DictPath("subexception"))
        severity: Optional[Any] = deep_get(kwargs, DictPath("severity"))
        facility: Optional[str] = deep_get(kwargs, DictPath("facility"))
        formatted_msg: Optional[Any] = deep_get(kwargs, DictPath("formatted_msg"))
        timestamp: Optional[datetime] = deep_get(kwargs, DictPath("timestamp"))
        file: Optional[str] = deep_get(kwargs, DictPath("file"))
        function: Optional[str] = deep_get(kwargs, DictPath("function"))
        lineno: Optional[int] = deep_get(kwargs, DictPath("lineno"))
        ppid: Optional[int] = deep_get(kwargs, DictPath("ppid"))
        try:
            # This is to get the necessary stack info
            raise UserWarning
        except UserWarning:
            frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
            self.file = str(frame.f_code.co_filename)  # type: ignore
            self.function = str(frame.f_code.co_name)  # type: ignore
            self.lineno = int(frame.f_lineno)  # type: ignore

        self.exception = __class__.__name__  # type: ignore
        self.subexception = subexception
        self.message = message
        self.severity = severity
        self.facility = facility
        self.formatted_msg = formatted_msg
        if timestamp is None:
            self.timestamp = datetime.now()
        else:
            self.timestamp = timestamp
        if file is not None:
            self.file = file
        if function is not None:
            self.function = function
        if lineno is not None:
            self.lineno = lineno
        if ppid is not None:
            self.ppid = ppid
        else:
            self.ppid = os.getppid()
        self.traceback = "".join(traceback.format_stack())

        super().__init__(message)

    def __str__(self) -> str:
        """
        Return a string representation of the exception.

            Returns:
                (str): The string representation of the exception
        """
        if self.subexception is None:
            message = ""
        else:
            message = f"({self.subexception}): "

        if not self.message:
            message += "No further details were provided"
        else:
            message += f"{self.message}"

        return message

    def exception_dict(self) -> Dict:
        """
        Return a dictionary containing structured information about the exception.

            Returns:
                (dict): A dictionary with structured information
        """
        return {
            "exception": self.exception,
            "subexception": self.subexception,
            "message": self.message,
            "severity": self.severity,
            "facility": self.facility,
            "formatted_msg": self.formatted_msg,
            "timestamp": self.timestamp,
            "file": self.file,
            "function": self.function,
            "lineno": self.lineno,
            "ppid": self.ppid,
            "traceback": self.traceback,
        }


# pylint: disable-next=too-many-instance-attributes
class FilePathAuditError(Exception):
    """
    Exception raised when a security check fails on a FilePath
    Note: severity and formatted_msg use Any as type to avoid recursive imports,
    but they are typically LogLevel and List[ANSIThemeStr], respectively.

    Optional arguments are normally deduced; overriding them is only necessary in special cases.

        Attributes:
            message (str): Additional information about the error
            path (FilePath): The path being audited
            severity (any): The severity
            facility (str): A facility
            formatted_msg (any); A formatted version of the message
            timestamp (datetime): A timestamp (optional)
            file (str): The file the error occurred in (optional)
            function (str): The function the error occurred in (optional)
            lineno (str): The line the error occurred on (optional)
            ppid (str): The parent pid of the process (optional)
    """
    traceback: Optional[str] = None

    def __init__(self, message: str, **kwargs: Any) -> None:
        path: Optional[FilePath] = deep_get(kwargs, DictPath("path"))
        severity: Optional[Any] = deep_get(kwargs, DictPath("severity"))
        facility: Optional[str] = deep_get(kwargs, DictPath("facility"))
        formatted_msg: Optional[Any] = deep_get(kwargs, DictPath("formatted_msg"))
        timestamp: Optional[datetime] = deep_get(kwargs, DictPath("timestamp"))
        file: Optional[str] = deep_get(kwargs, DictPath("file"))
        function: Optional[str] = deep_get(kwargs, DictPath("function"))
        lineno: Optional[int] = deep_get(kwargs, DictPath("lineno"))
        ppid: Optional[int] = deep_get(kwargs, DictPath("ppid"))
        try:
            # This is to get the necessary stack info
            raise UserWarning
        except UserWarning:
            frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
            self.file = str(frame.f_code.co_filename)  # type: ignore
            self.function = str(frame.f_code.co_name)  # type: ignore
            self.lineno = int(frame.f_lineno)  # type: ignore

        self.exception = __class__.__name__  # type: ignore
        self.message = message
        self.path = path
        self.severity = severity
        self.facility = facility
        self.formatted_msg = formatted_msg
        if timestamp is None:
            self.timestamp = datetime.now()
        else:
            self.timestamp = timestamp
        if file is not None:
            self.file = file
        if function is not None:
            self.function = function
        if lineno is not None:
            self.lineno = lineno
        if ppid is not None:
            self.ppid = ppid
        else:
            self.ppid = os.getppid()
        self.traceback = "".join(traceback.format_stack())

        super().__init__(message)

    def __str__(self) -> str:
        """
        Return a string representation of the exception.

            Returns:
                (str): The string representation of the exception
        """
        if self.path is None:
            path = "<omitted>"
        else:
            path = self.path
        if not self.message:
            message = "No further details were provided"
        else:
            message = self.message

        msg = f"Security policy violation for path {path}.  {message}"

        return msg

    def exception_dict(self) -> Dict:
        """
        Return a dictionary containing structured information about the exception.

            Returns:
                (dict): A dictionary with structured information
        """
        return {
            "exception": self.exception,
            "message": self.message,
            "path": self.path,
            "severity": self.severity,
            "facility": self.facility,
            "formatted_msg": self.formatted_msg,
            "timestamp": self.timestamp,
            "file": self.file,
            "function": self.function,
            "lineno": self.lineno,
            "ppid": self.ppid,
            "traceback": self.traceback,
        }


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def validate_args(kwargs_spec: Dict[str, Any], kwargs: Any) -> None:
    """
    Validates that the kwargs against the requirements in kwargs_spec.

        Parameters:
            kwargs_spec ([dict]): The expected properties for kwargs
            kwargs ([{str, Any}]): The kwargs to validate
        Raises:
            ArgumentValidationError (with subexception)
    """
    results: Dict = {}
    msg: List[List[Tuple[str, str]]] = []
    function = "<unknown>"  # This is just to make pylint happy

    try:
        # This is to get the necessary stack info
        raise UserWarning
    except UserWarning:
        frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
        function = str(frame.f_code.co_name)  # type: ignore

    anyof = deep_get(kwargs_spec, DictPath("__anyof"), ())
    allof = deep_get(kwargs_spec, DictPath("__allof"), ())
    if not (isinstance(anyof, tuple) and isinstance(allof, tuple)
            and isinstance(kwargs_spec, dict) and isinstance(kwargs, dict)):
        msg = [
            [("validate_arguments()", "emphasis"),
             (" called with invalid argument(s):", "error")],
            [("    __anyof", "argument"), (" is ", "default"), (f"{type(anyof)}", "argument"),
             (" expected ", "default"), (f"{repr(tuple)}", "emphasis")],
            [("    __allof", "argument"), (" is ", "default"), (f"{type(allof)}", "argument"),
             (" expected ", "default"), (f"{repr(tuple)}", "emphasis")],
            [("    kwargs_spec", "argument"), (" is ", "default"),
             (f"{type(kwargs_spec)}", "argument"),
             (" expected ", "default"), (f"{repr(dict)}", "emphasis")],
            [("    kwargs", "argument"), (" is ", "default"), (f"{type(kwargs)}", "argument"),
             (" expected ", "default"), (f"{repr(dict)}", "emphasis")],
        ]

        raise ArgumentValidationError(subexception=TypeError, formatted_msg=msg)

    for key, data in kwargs_spec.items():
        if key.startswith("__"):
            continue
        expected_types = deep_get(data, DictPath("types"))
        none_acceptable = deep_get(data, DictPath("none"), False)
        # -1 (no min/max length); min_len == max_len for exact length

        min_max = deep_get(data, DictPath("range"))
        kwarg = deep_get(kwargs, DictPath(key))
        # pylint: disable-next=too-many-boolean-expressions
        if (expected_types is None or not isinstance(expected_types, tuple)
            or not isinstance(none_acceptable, bool)
            or (min_max is not None
                and (not isinstance(min_max, tuple) or len(min_max) != 2
                     or not (min_max[0] is None or isinstance(min_max[0], (int, float)))
                     or not (min_max[1] is None or isinstance(min_max[1], (int, float)))))):
            msg = [
                [("validate_arguments()", "emphasis"),
                 (" called with invalid argument(s):", "error")],
                [("    types", "argument"),
                 (" is ", "default"),
                 (f"{type(expected_types)}", "argument"),
                 (" expected ", "default"),
                 (f"{repr(tuple)}", "emphasis")],
                [("    none", "argument"),
                 (" is ", "default"),
                 (f"{type(none_acceptable)}", "argument"),
                 (" expected ", "default"),
                 (f"{repr(bool)}", "emphasis")],
                [("    range", "argument"),
                 (" is ", "default"),
                 (f"{type(min_max)}", "argument"),
                 (" expected ", "default"),
                 ("((int|float, int|float))", "emphasis")],
            ]

            raise ArgumentValidationError(subexception=TypeError, formatted_msg=msg)

        if kwarg is None and not none_acceptable:
            if len(expected_types) == 1:
                results[key] = {
                    "subexception": TypeError,
                    "msg": [(f"    {key}", "argument"),
                            (" is ", "default"),
                            ("None", "emphasis"),
                            (" expected ", "default"),
                            (f"{expected_types}", "emphasis")],
                    "missing": True,
                }
            else:
                results[key] = {
                    "subexception": TypeError,
                    "msg": [(f"    {key}", "argument"),
                            (" is ", "default"),
                            ("None", "emphasis"),
                            (" expected one of ", "default"),
                            (f"{expected_types}", "emphasis")],
                    "missing": True,
                }
            # If kwarg is None there's nothing else we can check
            continue

        if not isinstance(kwarg, expected_types):
            if len(expected_types) == 1:
                results[key] = {
                    "subexception": TypeError,
                    "msg": [(f"    {key}", "argument"),
                            (" is ", "default"),
                            (f"{type(kwarg)}", "emphasis"),
                            (" expected ", "default"),
                            (f"{expected_types}", "emphasis")],
                }
            else:
                results[key] = {
                    "subexception": TypeError,
                    "msg": [(f"    {key}", "argument"), (" is ", "default"),
                            (f"{type(kwarg)}", "emphasis"), (" expected one of ", "default"),
                            (f"{expected_types}", "emphasis")],
                }
            continue

        if min_max is not None:
            minval, maxval = min_max
            if minval is None:
                minval_cmp = -sys.maxsize
                minval_str = ""
            else:
                minval_cmp = minval
                minval_str = str(minval)
            if maxval is None:
                maxval_cmp = sys.maxsize
                maxval_str = ""
            else:
                maxval_cmp = maxval
                maxval_str = str(maxval)

            if isinstance(kwarg, (int, float)):
                if not minval_cmp <= kwarg <= maxval_cmp:
                    results[key] = {
                        "subexception": ValueError,
                        "msg": [(f"    {key}", "argument"),
                                ("=", "default"),
                                (f"{kwarg}", "emphasis"),
                                (", valid range is [", "default"),
                                (f"{minval_str}", "numerical"),
                                (", ", "default"),
                                (f"{maxval_str}", "numerical"),
                                ("]", "default")],
                    }
                    continue
            else:
                if not minval_cmp <= len(kwarg) <= maxval_cmp:
                    results[key] = {
                        "subexception": ValueError,
                        "msg": [("    len(", "default"), (f"{key}", "argument"), (")=", "default"),
                                (f"{len(kwarg)}", "emphasis"), (", valid range is [", "default"),
                                (f"{minval_str}", "numerical"), (", ", "default"),
                                (f"{maxval_str}", "numerical"), ("]", "default")],
                    }
                    continue
        results[key] = {}

    # Check if we got all the arguments we asked for
    missing: List[str] = []
    anyexists: bool = False

    for key in anyof:
        if key in kwargs:
            anyexists = True
            break
    if anyof and not anyexists:
        msg = [
            [(f"{function}()", "emphasis"), (" called with invalid argument(s):", "error")],
            [("    At least one of the following arguments must be present:", "default")],
        ]
        for key in anyof:
            msg.append([(f"{key}", "argument")])
        subexception = ValueError

    for key in allof:
        if key not in kwargs:
            missing += key
    if missing:
        msg = [
            [(f"{function}()", "emphasis"), (" called with invalid argument(s):", "error")],
            [("    The following arguments are missing but must be present:", "default")],
        ]
        for key in missing:
            msg.append([(f"{key}", "argument")])
        subexception = ValueError

    if not msg:
        # Check whether arguments were OK
        for key, result in results.items():
            # No complaints
            if not result:
                continue
            submsg = deep_get(result, DictPath("msg"))
            subexception = deep_get(result, DictPath("subexception"), TypeError)
            if not msg:
                msg = [
                    [(f"{function}()", "emphasis"),
                     (" called with invalid argument(s):", "error")],
                ]
            msg.append(submsg)

    if msg:
        raise ArgumentValidationError(subexception=subexception, formatted_msg=msg)


class HostNameStatus(Enum):
    """
    Return values from validate_hostname().
    """
    OK = auto()
    DNS_SUBDOMAIN_EMPTY = auto()
    DNS_SUBDOMAIN_TOO_LONG = auto()
    DNS_SUBDOMAIN_WRONG_CASE = auto()
    DNS_SUBDOMAIN_INVALID_FORMAT = auto()
    DNS_LABEL_STARTS_WITH_IDNA = auto()
    DNS_LABEL_INVALID_FORMAT = auto()
    DNS_LABEL_TOO_LONG = auto()
    DNS_LABEL_PUNYCODE_TOO_LONG = auto()
    DNS_LABEL_INVALID_CHARACTERS = auto()
    DNS_TLD_INVALID = auto()


class SecurityStatus(IntEnum):
    """
    Return values from check_path().
    """
    OK = auto()
    # Critical
    PERMISSIONS = auto()
    PARENT_PERMISSIONS = auto()
    OWNER_NOT_IN_ALLOWLIST = auto()
    PARENT_OWNER_NOT_IN_ALLOWLIST = auto()
    PATH_NOT_RESOLVING_TO_SELF = auto()
    PARENT_PATH_NOT_RESOLVING_TO_SELF = auto()
    # Error
    DOES_NOT_EXIST = auto()
    PARENT_DOES_NOT_EXIST = auto()
    IS_NOT_FILE = auto()
    IS_NOT_DIR = auto()
    IS_NOT_SYMLINK = auto()
    IS_EXECUTABLE = auto()
    IS_NOT_EXECUTABLE = auto()
    PARENT_IS_NOT_DIR = auto()
    DIR_NOT_EMPTY = auto()
    EXISTS = auto()


class SecurityChecks(Enum):
    """
    Checks that can be performed by check_path().
    """
    PARENT_RESOLVES_TO_SELF = auto()
    RESOLVES_TO_SELF = auto()
    OWNER_IN_ALLOWLIST = auto()
    PARENT_OWNER_IN_ALLOWLIST = auto()
    PERMISSIONS = auto()
    PARENT_PERMISSIONS = auto()
    CAN_READ_IF_EXISTS = auto()
    EXISTS = auto()
    IS_FILE = auto()
    IS_DIR = auto()
    IS_SYMLINK = auto()
    IS_EXECUTABLE = auto()
    IS_NOT_EXECUTABLE = auto()


class SecurityPolicy(Enum):
    """
    Security policies used by CMT.
    """
    # Only allows exact matches
    STRICT = auto()
    # Only allows exact matches from any path in the allowlist
    ALLOWLIST_STRICT = auto()
    # Allows exact matches from any path in the allowlist,
    # but path elements can be symlinks
    ALLOWLIST_RELAXED = auto()


class LogLevel(IntEnum):
    """
    Loglevels used by CMT.
    """
    EMERG = 0
    ALERT = 1
    CRIT = 2
    ERR = 3
    WARNING = 4
    NOTICE = 5
    INFO = 6
    DEBUG = 7
    DIFFPLUS = 8
    DIFFMINUS = 9
    DIFFSAME = 10
    ALL = 255


loglevel_mappings = {
    LogLevel.EMERG: "Emergency",
    LogLevel.ALERT: "Alert",
    LogLevel.CRIT: "Critical",
    LogLevel.ERR: "Error",
    LogLevel.WARNING: "Warning",
    LogLevel.NOTICE: "Notice",
    LogLevel.INFO: "Info",
    LogLevel.DEBUG: "Debug",
    LogLevel.DIFFPLUS: "Diffplus",
    LogLevel.DIFFMINUS: "Diffminus",
    LogLevel.DIFFSAME: "Diffsame",
    LogLevel.ALL: "Debug",
}


def loglevel_to_name(loglevel: LogLevel) -> str:
    """
    Given a numerical loglevel, return its severity string.

        Parameters:
            loglevel (int): The corresponding numerical loglevel
        Returns:
            (str): A severity string
    """
    return loglevel_mappings[max(LogLevel.EMERG, min(LogLevel.DIFFSAME, loglevel))]


class Retval(Enum):
    """
    Return values from the UI functions.
    """
    NOMATCH = 0     # No keypress matched/processed; further checks needed (if any)
    MATCH = 1       # keypress matched/processed; no further action
    RETURNONE = 2   # keypress matched/processed; return up one level
    RETURNFULL = 3  # keypress matched/processed, callback called; return up entire callstack
    RETURNDONE = 4  # We've done our Return One


class StatusGroup(IntEnum):
    """
    Status groups used by CMT.
    """
    NEUTRAL = 8
    DONE = 7
    OK = 6
    PENDING = 5
    WARNING = 4
    ADMIN = 3
    NOT_OK = 2
    UNKNOWN = 1
    CRIT = 0


stgroup_mapping = {
    StatusGroup.CRIT: "status_critical",
    StatusGroup.UNKNOWN: "status_unknown",
    StatusGroup.NOT_OK: "status_not_ok",
    StatusGroup.ADMIN: "status_admin",
    StatusGroup.WARNING: "status_warning",
    StatusGroup.OK: "status_ok",
    StatusGroup.PENDING: "status_pending",
    StatusGroup.DONE: "status_done",
}


def deep_set(dictionary: Dict, path: DictPath, value: Any, create_path: bool = False) -> None:
    """
    Given a dictionary, a path into that dictionary, and a value, set the path to that value.

        Parameters:
            dictionary (dict): The dict to set the value in
            path (DictPath): A dict path
            value (any): The value to set
            create_path (bool): If True the path will be created if it does not exist
    """
    if dictionary is None or path is None or not path:
        raise ValueError(f"deep_set: dictionary {dictionary} or path {path} invalid/unset")

    ref = dictionary
    pathsplit = path.split("#")

    for i, pathsegment in enumerate(pathsplit):  # pragma: no branch
        # Note that we're (potentially) updating ref every iteration
        if ref is None or not isinstance(ref, dict):
            raise ValueError(f"Path {path} does not exist in dictionary {dictionary} "
                             f"or is the wrong type {type(ref)}")

        if pathsegment not in ref or ref[pathsegment] is None:
            if create_path:
                ref[pathsegment] = {}

        if i == len(pathsplit) - 1:
            ref[pathsegment] = value
            break

        ref = deep_get(ref, DictPath(pathsegment))


def __deep_get_recursive(dictionary: Dict,
                         path_fragments: List[str],
                         result: Union[List, None] = None) -> Optional[List[Any]]:
    if result is None:
        result = []

    for i, path_fragment in enumerate(path_fragments):  # pragma: no branch
        tmp = deep_get(dictionary, DictPath(path_fragment))
        if i + 1 == len(path_fragments):
            if tmp is None:
                return result
            return tmp

        if isinstance(tmp, dict):
            return __deep_get_recursive(tmp, path_fragments[i + 1:len(path_fragments)], result)
        if isinstance(tmp, list):  # pragma: no branch
            result = []
            for tmp2 in tmp:
                result.append(__deep_get_recursive(tmp2,
                                                   path_fragments[i + 1:len(path_fragments)],
                                                   result))

    return result


def deep_get_list(dictionary: Dict,
                  paths: List[DictPath],
                  default: Optional[List[Any]] = None,
                  fallback_on_empty: bool = False) -> Optional[List[Any]]:
    """
    Given a dictionary and a list of paths into that dictionary, get all values.

        Parameters:
            dictionary (dict): The dict to get the values from
            path ([DictPath]): A list of dict paths
            default ([Any]): The value to return if the dictionary, paths, or results are None
            fallback_on_empty (bool): Should "" be treated as None?
        Returns:
            ([Any]): The values from the paths
    """
    if dictionary is None or paths is None:
        return default

    result = None
    for path in paths:
        if path is None:
            continue
        result = __deep_get_recursive(dictionary, path.split("#"))

        if (result is not None and not
                (type(result) in (list, str, dict) and not result and fallback_on_empty)):
            break
    if result is None or type(result) in (list, str, dict) and not result and fallback_on_empty:
        result = default
    return result


def deep_get_with_fallback(obj: Dict,
                           paths: List[DictPath],
                           default: Optional[Any] = None, fallback_on_empty: bool = False) -> Any:
    """
    Given a dictionary and a list of paths into that dictionary,
    get the value from the first path that has a value.

        Parameters:
            dictionary (dict): The dict to get the value from
            paths ([DictPath]): A list of dict paths
            default (any): The value to return if the dictionary, path or result is None
            fallback_on_empty (bool): Should "" be treated as None?
        Returns:
            (Any): The value from the path(s)
    """
    if paths is None:
        return default

    result = None
    for path in paths:
        result = deep_get(obj, path)
        if (result is not None and not
                (type(result) in (list, str, dict) and not result and fallback_on_empty)):
            break
    if result is None or type(result) in (list, str, dict) and not result and fallback_on_empty:
        result = default
    return result


def deep_get_str_tuple_paths(obj: Dict,
                             paths: List[Union[str, List[DictPath]]],
                             default: str = "", fallback_on_empty: bool = False) -> str:
    """
    Given a dictionary and a list of strings or paths into that dictionary,
    get the value from each path and joined them together with the verbatim strings,
    with special consideration taken for apiFamily/apiVersion (remove the version).

        Parameters:
            dictionary (dict): The dict to get the value from
            paths ([DictPath]): A list of dict paths or verbatim strings
            default (any): The value to return if the dictionary, path or result is None
            fallback_on_empty (bool): Should "" be treated as None?
        Returns:
            (str): The joined string
    """
    string = ""
    prev: Union[List, str] = ""

    for fragment in paths:
        # This isn't a path, it's a verbatim string
        if isinstance(fragment, str):
            string += fragment
        elif isinstance(fragment, list):
            tmp_string = deep_get_with_fallback(obj, fragment, "")
            if fragment in (["apiFamily"], ["apiVersion"]) and prev == ["kind"]:
                if "/" in tmp_string:
                    string += "." + tmp_string.split("/", maxsplit=1)[0]
            else:
                string += tmp_string
        else:
            raise TypeError("deep_get_str_tuple_paths() called with invalid path segment: "
                            f"{fragment}")
        prev = fragment
    if fallback_on_empty and not string:
        string = default
    return string
