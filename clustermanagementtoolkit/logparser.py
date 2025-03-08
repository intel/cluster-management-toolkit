#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

# The parser takes one line of input at a time;
# for messages that need multi-line parsing you need to
# return remnants and if necessary tweak multiline_parser
#
# Log levels are the same as in syslog:
# EMERG        system is unusable <should be irrelevant>
# ALERT        action must be taken immediately
# CRIT        critical conditions
# ERR        error conditions
# WARNING    warning conditions
# NOTICE    normal, but significant, condition
# INFO        informational message
# DEBUG        debug-level message
#
# Return format is timestamp, facility, severity, message

"""
Log parsers for cmu

unit-tests:
    tests/logtests
"""

# pylint: disable=too-many-lines

import ast
from collections import namedtuple
from collections.abc import Callable, Sequence
from datetime import datetime
import difflib
# ujson is much faster than json,
# but it might not be available
try:
    import ujson as json
    json_is_ujson = True  # pylint: disable=invalid-name
    # The exception raised by ujson when parsing fails is different
    # from what json raises
    DecodeException = ValueError
except ModuleNotFoundError:
    import json  # type: ignore
    json_is_ujson = False  # pylint: disable=invalid-name
    DecodeException = json.decoder.JSONDecodeError  # type: ignore
from pathlib import Path
import re
import sys
from typing import Any, cast, Optional, Union
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

try:
    from natsort import natsorted
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import natsort; "
             "you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

try:
    import validators
except ModuleNotFoundError:
    print("ModuleNotFoundError: Could not import validators; "
          "you may need to (re-)run `cmt-install` or `pip3 install validators`; "
          "disabling IP-address validation.\n", file=sys.stderr)
    # pylint: disable-next=invalid-name
    validators = None

from clustermanagementtoolkit import cmtlog

from clustermanagementtoolkit.cmtpaths import HOMEDIR, SYSTEM_PARSERS_DIR, PARSER_DIR

from clustermanagementtoolkit.cmttypes import deep_get, deep_get_with_fallback, DictPath
from clustermanagementtoolkit.cmttypes import FilePath
from clustermanagementtoolkit.cmttypes import LogLevel
from clustermanagementtoolkit.cmttypes import loglevel_to_name, name_to_loglevel
from clustermanagementtoolkit.cmttypes import ProgrammingError

from clustermanagementtoolkit.cmtio_yaml import secure_read_yaml, secure_read_yaml_all

from clustermanagementtoolkit import cmtlib
from clustermanagementtoolkit.cmtlib import none_timestamp, strip_ansicodes

from clustermanagementtoolkit import formatters

from clustermanagementtoolkit.curses_helper import themearray_len, themearray_to_string
from clustermanagementtoolkit.curses_helper import ThemeAttr, ThemeRef, ThemeStr

from clustermanagementtoolkit.ansithemeprint import ANSIThemeStr


# pylint: disable-next=too-few-public-methods
class LogparserConfiguration:
    """
    Various configuration options used by the logparsers
    """
    # Keep or strip timestamps in structured logs
    pop_ts: bool = True
    # Keep or strip severity in structured logs
    pop_severity: bool = True
    # Keep or strip facility in structured logs
    pop_facility: bool = True
    # msg="foo" or msg=foo => foo
    msg_extract: bool = True
    # If msg_extract is False,
    # this decides whether or not to put msg="foo" first or not
    # this also affects err="foo" and error="foo"
    msg_first: bool = True
    # if msg_extract is True,
    # this decides whether msg="foo\nbar" should be converted to:
    # foo
    # bar
    # Currently this only work with JSON & key_value on a subset of keys
    # and does not affect "err=" and "error="
    expand_newlines: bool = True
    # Should "* " be replaced with real bullets?
    msg_realbullets: bool = True
    # Should override severity rules be applied?
    override_severity: bool = True
    # collector=foo => • foo
    bullet_collectors: bool = True
    # if msg_extract is True,
    # this decides whether should be converted to:
    # msg="Starting foo" version="(version=.*)" => Starting foo (version=.*)
    merge_starting_version: bool = True
    # Replace tabs within values
    expand_tabs: bool = True
    using_bundles: bool = False


if json_is_ujson:
    def json_dumps(obj: dict[str, Any]) -> str:
        """
        Dump JSON object to text format; ujson version.

            Parameters:
                obj (dict): The JSON object to dump
            Returns:
                str: The serialized JSON object
        """
        indent = 2
        return json.dumps(obj, indent=indent, escape_forward_slashes=False)
else:
    def json_dumps(obj: dict[str, Any]) -> str:
        """
        Dump JSON object to text format; json version.

            Parameters:
                obj (dict): The JSON object to dump
            Returns:
                str: The serialized JSON object
        """
        indent = 2
        return json.dumps(obj, indent=indent)


def month_to_numerical(month: str) -> str:
    """
    Convert a 3-letter month string to a numerical month string.

        Parameters:
            month (str): The month string
        Returns:
            (str): The numerical value for the month
    """
    months = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
    return f"{months.index(month.lower()[0:3]):02}"


# Mainly used by glog
def letter_to_severity(letter: str, **kwargs: Any) -> LogLevel:
    """
    Convert a 1-letter severity string to a LogLevel.

        Parameters:
            letter (str): A 1-letter severity string
            **kwargs (dict[str, Any]): Keyword arguments
                default (LogLevel): The loglevel to return if the input is invalid
        Returns:
            (LogLevel): The corresponding LogLevel
    """
    default: LogLevel = deep_get(kwargs, DictPath("default"), LogLevel.DEFAULT)
    severities = {
        "F": LogLevel.EMERG,
        "E": LogLevel.ERR,
        "W": LogLevel.WARNING,
        "N": LogLevel.NOTICE,
        "C": LogLevel.NOTICE,  # Used by jupyter for the login token
        "I": LogLevel.INFO,
        "D": LogLevel.DEBUG,
    }
    return severities.get(letter, default)


# Used by Kiali and kubeshark
def str_3letter_to_severity(string: str, **kwargs: Any) -> LogLevel:
    """
    Convert a 3-letter severity string to a LogLevel.

        Parameters:
            letter (str): A 3-letter severity string
            **kwargs (dict[str, Any]): Keyword arguments
                default (LogLevel): The loglevel to return if the input is invalid
        Returns:
            (LogLevel): The corresponding LogLevel
    """
    default: LogLevel = deep_get(kwargs, DictPath("default"), LogLevel.DEFAULT)
    severities = {
        "ERR": LogLevel.ERR,
        "WRN": LogLevel.WARNING,
        "INF": LogLevel.INFO,
        "DBG": LogLevel.DEBUG,
        "TRC": LogLevel.DEBUG,  # Most likely TRACE; no reason for different loglevel
    }
    return severities.get(string.upper(), default)


def str_4letter_to_severity(string: str, **kwargs: Any) -> LogLevel:
    """
    Convert a 4-letter severity string to a LogLevel.

        Parameters:
            letter (str): A 4-letter severity string
            **kwargs (dict[str, Any]): Keyword arguments
                default (LogLevel): The loglevel to return if the input is invalid
        Returns:
            (LogLevel): The corresponding LogLevel
    """
    default: LogLevel = deep_get(kwargs, DictPath("default"), LogLevel.DEFAULT)
    severities = {
        "CRIT": LogLevel.CRIT,
        "FATA": LogLevel.CRIT,
        "ERRO": LogLevel.ERR,
        "WARN": LogLevel.WARNING,
        "NOTI": LogLevel.NOTICE,
        "SUCC": LogLevel.NOTICE,  # From KubeRay
        "INFO": LogLevel.INFO,
        "DEBU": LogLevel.DEBUG,
    }
    return severities.get(string.upper(), default)


def str_to_severity(string: str, **kwargs: Any) -> LogLevel:
    """
    Convert a severity string to a LogLevel.

        Parameters:
            letter (str): A severity string
            **kwargs (dict[str, Any]): Keyword arguments
                default (LogLevel): The loglevel to return if the input is invalid
        Returns:
            (LogLevel): The corresponding LogLevel
    """
    default: LogLevel = deep_get(kwargs, DictPath("default"), LogLevel.DEFAULT)
    severities = {
        "fatal": LogLevel.CRIT,
        "error": LogLevel.ERR,
        "eror": LogLevel.ERR,
        "warning": LogLevel.WARNING,
        "warn": LogLevel.WARNING,
        "notice": LogLevel.NOTICE,
        "noti": LogLevel.NOTICE,
        "info": LogLevel.INFO,
        "debug": LogLevel.DEBUG,
        "debu": LogLevel.DEBUG,
    }
    # Special case for severity found in trust-manager
    if string.lower().startswith("debug+"):
        tmp = re.match(r"debug\+(\d+)$", string, re.IGNORECASE)
        if tmp is not None:
            return LogLevel.DEBUG
    return severities.get(string.lower(), default)


def lvl_to_letter_severity(lvl: LogLevel) -> str:
    """
    Convert a LogLevel to a 1-letter severity string.

        Parameters:
            lvl (LogLevel): A LogLevel
        Returns:
            (str): The corresponding severity string
    """
    severities = {
        LogLevel.CRIT: "C",
        LogLevel.ERR: "E",
        LogLevel.WARNING: "W",
        LogLevel.NOTICE: "N",
        LogLevel.INFO: "I",
        LogLevel.DEBUG: "D",
    }
    return severities.get(lvl, "!ERROR IN LOGPARSER!")


def lvl_to_4letter_severity(lvl: LogLevel) -> str:
    """
    Convert a LogLevel to a 4-letter severity string.

        Parameters:
            lvl (LogLevel): A LogLevel
        Returns:
            (str): The corresponding severity string
    """
    severities = {
        LogLevel.CRIT: "CRIT",
        LogLevel.ERR: "ERRO",
        LogLevel.WARNING: "WARN",
        LogLevel.NOTICE: "NOTI",
        LogLevel.INFO: "INFO",
        LogLevel.DEBUG: "DEBU",
    }
    return severities.get(lvl, "!ERROR IN LOGPARSER!")


def lvl_to_word_severity(lvl: LogLevel) -> str:
    """
    Convert a LogLevel to a severity string.

        Parameters:
            lvl (LogLevel): A LogLevel
        Returns:
            (str): The corresponding severity string
    """
    severities = {
        LogLevel.CRIT: "CRITICAL",
        LogLevel.ERR: "ERROR",
        LogLevel.WARNING: "WARNING",
        LogLevel.NOTICE: "NOTICE",
        LogLevel.INFO: "INFO",
        LogLevel.DEBUG: "DEBUG",
    }
    return severities.get(lvl, "!ERROR IN LOGPARSER!")


def split_bracketed_severity(message: str, **kwargs: Any) -> tuple[str, LogLevel]:
    """
    Remove a bracketed severity prefix from a string.

        Parameters:
            message: A string to strip a severity prefix from
            **kwargs (dict[str, Any]): Keyword arguments
                options:
                    default: The default severity to use if no LogLevel prefix can be found
        Returns:
            (str, LogLevel):
                (str): The input string with the severity prefix removed
                (LogLevel): The extracted LogLevel
    """
    default: LogLevel = deep_get(kwargs, DictPath("options#default"), LogLevel.DEFAULT)

    severities = {
        "[fatal]": LogLevel.CRIT,
        # This is for ingress-nginx; while alert is higher than crit in syslog terms,
        # ingress-nginx doesn't seem to use it that way.
        "[alert]": LogLevel.ERR,
        "[error]": LogLevel.ERR,
        "[err]": LogLevel.ERR,
        "[warning]": LogLevel.WARNING,
        "[warn]": LogLevel.WARNING,
        "[notice]": LogLevel.NOTICE,
        "[info]": LogLevel.INFO,
        "[system]": LogLevel.INFO,  # MySQL seems to have its own loglevels
        "[note]": LogLevel.INFO,    # none of which makes every much sense
        "[debug]": LogLevel.DEBUG,
    }

    tmp = re.match(r"^(\[[A-Za-z]+?\]) ?(.*)", message)
    if tmp is not None:
        if (severity := severities.get(tmp[1].lower())) is not None:
            message = tmp[2]
        else:
            severity = default
    else:
        severity = default

    return message, severity


def split_colon_severity(message: str, **kwargs: Any) -> tuple[str, LogLevel]:
    """
    Remove a colon severity prefix from a string.

        Parameters:
            message (str): A string to strip a severity prefix from
            **kwargs (dict[str, Any]): Keyword arguments
                default: The default severity to use if no LogLevel prefix can be found
        Returns:
            (str, LogLevel):
                (str): The input string with the severity prefix removed
                (LogLevel): The extracted LogLevel
    """
    default: LogLevel = deep_get(kwargs, DictPath("default"), LogLevel.INFO)
    severities = {
        "CRITICAL:": LogLevel.CRIT,
        "ERROR:": LogLevel.ERR,
        "WARNING:": LogLevel.WARNING,
        "NOTICE:": LogLevel.NOTICE,
        "NOTE:": LogLevel.NOTICE,
        "INFO:": LogLevel.INFO,
        "DEBUG:": LogLevel.DEBUG,
    }

    if (tmp := re.match(r"^([A-Za-z]+?:) ?(.*)", message)) is not None:
        if (severity := severities.get(tmp[1].upper())) is not None:
            message = tmp[2]
        else:
            severity = default
    else:
        severity = default
    return message, severity


def is_timestamp(message: str) -> bool:
    """
    Tries to check whether the field is a timestamp.

        Parameters:
            message (str): The string to check
        Returns:
            (bool): True if the string is a timestamp, False if not
    """
    tmp = re.match(r"^\d\.\d+e\+09", message)
    if tmp is not None:
        return True

    tmp = re.match(r"^\d{4}[/-]\d\d[/-]\d\d"
                   r"[ T]"
                   r"\d\d[\.:]\d\d[\.:]\d\d"
                   r"([\.,]\d{9} [+-]\d\d[:\.]\d\d|"
                   r"[\.,]\d{8} [+-]\d\d[:\.]\d\d|"
                   r"[\.,]\d{6} [+-]\d\d[:\.]\d\d|"
                   r"[\.,]\d{3} [+-]\d\d[:\.]\d\d|"
                   r"[\.,]\d{9}Z?|"
                   r"[\.,]\d{8}Z?|"
                   r"[\.,]\d{6}Z?|"
                   r"[\.,]\d{3}Z?|"
                   r"Z?)$", message)

    if tmp is not None:
        return True
    return False


# pylint: disable-next=too-many-statements
def split_iso_timestamp(message: str, timestamp: datetime) -> tuple[str, datetime]:
    """
    Split a message into timestamp and remaining message.

        Parameters:
            message (str): The message to strip the timestamp from
            timestamp (datetime): The datetime to return if the message doesn't have a timestamp
        Returns:
            (str, datetime): Return the remainder of the message and the datetime
    """
    old_timestamp = timestamp
    tmp_timestamp = ""

    # This while loop is merely to allow for breaking out anywhere
    while True:
        # 2020-02-07T13:12:24.224Z (Z = UTC)
        tmp = re.match(r"^(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d\.\d+)Z ?(.*)", message)
        if tmp is not None:
            ymd = tmp[1]
            hmsms = tmp[2][0:len("HH:MM:SS.sss")]
            tmp_timestamp = f"{ymd} {hmsms}+0000"
            message = tmp[3]
            break

        # 2020-02-13T12:06:18.011345 [+-]00:00 (+timezone)
        # 2020-09-23T17:12:32.183967091[+-]03:00
        # 2024-11-02 23:20:35.121725861 +0000
        tmp = re.match(r"^(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d\.\d+) ?([\+-])(\d\d):?(\d\d) ?(.*)",
                       message)
        if tmp is not None:
            ymd = tmp[1]
            hmsms = tmp[2][0:len("HH:MM:SS.sss")]
            tzsign = tmp[3]
            tzhour = tmp[4]
            tzmin = tmp[5]
            tmp_timestamp = f"{ymd} {hmsms}{tzsign}{tzhour}{tzmin}"
            message = tmp[6]
            break

        # 2020-02-13 12:06:18[+-]00:00 (+timezone)
        # [2020-02-13 12:06:18 [+-]00:00] (+timezone)
        # 2020-02-13T12:06:18[+-]0000 (+timezone)
        tmp = re.match(r"^\[?(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d) ?([\+-])(\d\d):?(\d\d)\]? ?(.*)",
                       message)
        if tmp is not None:
            ymd = tmp[1]
            hms = tmp[2]
            tzsign = tmp[3]
            tzhour = tmp[4]
            tzmin = tmp[5]
            tmp_timestamp = f"{ymd} {hms}.000{tzsign}{tzhour}{tzmin}"
            message = tmp[6]
            break

        # 2020-02-20 13:47:41.008416 (assume UTC)
        # 2020-02-20 13:47:41.008416: (assume UTC)
        # 2020/02/20 13:47:41.008416 (assume UTC)
        # 2020-02-20 13:47:41.008416Z (Z = UTC)
        tmp = re.match(r"^(\d{4})[-/](\d\d)[-/](\d\d) (\d\d:\d\d:\d\d\.\d+)[Z:]? ?(.*)", message)
        if tmp is not None:
            year = tmp[1]
            month = tmp[2]
            day = tmp[3]
            hmsms = tmp[4][0:len("HH:MM:SS.sss")]
            tmp_timestamp = f"{year}-{month}-{day} {hmsms}+0000"
            message = tmp[5]
            break

        # [2021-12-18T20:15:36Z]
        # 2021-12-18T20:15:36Z
        tmp = re.match(r"^\[?(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d)Z\]? ?(.*)", message)
        if tmp is not None:
            ymd = tmp[1]
            hms = tmp[2]
            tmp_timestamp = f"{ymd} {hms}.000+0000"
            message = tmp[3]
            break

        # 2020-02-20 13:47:41 (assume UTC)
        # 2020/02/20 13:47:41 (assume UTC)
        tmp = re.match(r"^(\d{4})[-/](\d\d)[-/](\d\d) (\d\d:\d\d:\d\d) ?(.*)", message)
        if tmp is not None:
            year = tmp[1]
            month = tmp[2]
            day = tmp[3]
            hms = tmp[4]
            tmp_timestamp = f"{year}-{month}-{day} {hms}.000+0000"
            message = tmp[5]
            break

        # 2020-02-07 13:12:24.224
        # 2020-02-07 13:12:24,224
        # [2020-02-07 13:12:24.224]
        # [2020-02-07 13:12:24,224]
        tmp = re.match(r"^\[?(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d)(,|\.)(\d+)\]? ?(.*)", message)
        if tmp is not None:
            ymd = tmp[1]
            hms = tmp[2]
            # This just matches the separator; we don't use it
            # _sep = tmp[3]
            ms = tmp[4]
            tmp_timestamp = f"{ymd} {hms}.{ms}+0000"
            message = tmp[5]
            break

        break

    if old_timestamp == none_timestamp() and tmp_timestamp:
        timestamp = datetime.strptime(tmp_timestamp, "%Y-%m-%d %H:%M:%S.%f%z")

    # message + (timestamp|none_timestamp()) is passed in,
    # so it is safe just to return it too.
    return message, timestamp


def strip_iso_timestamp(message: str) -> str:
    """
    Given a string with a timestamp, return that string without the timestamp.

        Parameters:
            message (str): The message to strip
        Returns:
            (str): The stripped message
    """
    message, _timestamp = split_iso_timestamp(message, none_timestamp())
    return message


# 2020-02-20 13:47:01.531 GMT
def strip_iso_timestamp_with_tz(message: str) -> str:
    """
    Given a string with a timestamp and timezone, return that string without the timestamp.

        Parameters:
            message (str): The message to strip
        Returns:
            (str): The stripped message
    """
    tmp = re.match(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d [A-Z]{3}(\s+?|$)(.*)", message)
    if tmp is not None:
        message = tmp[2]
    return message


# pylint: disable-next=too-many-locals,too-many-branches
def iptables(message: str,
             remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]], **kwargs: Any) \
        -> tuple[list[Union[ThemeRef, ThemeStr]], LogLevel, str,
                 list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Format output from iptables-save.

        Parameters:
            message (str): The message part of the msg to format
            remnants (list[(themearray, severity)]): The remnants part of the msg to format
            **kwargs (dict[str, Any]): Keyword arguments
                severity (LogLevel): The log severity
                facility (str): The log facility
                fold_msg (bool): Should the message be expanded or folded?
                options (dict): Additional, rule specific, options
        Returns:
            (ThemeArray, LogLevel, str, [(ThemeArray, LogLevel)]):
                (ThemeArray): The formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.DEFAULT)
    facility: str = deep_get(kwargs, DictPath("facility"), "")
    fold_msg: bool = deep_get(kwargs, DictPath("fold_msg"), True)

    new_message: list[Union[ThemeRef, ThemeStr]] = []
    new_remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

    old_messages: list[str] = []
    if fold_msg and "\\n" in message:
        old_messages = message.split("\\n")
    else:
        old_messages.append(message)

        for themearray, _loglevel in remnants:
            old_messages.append(themearray_to_string(themearray))

    variable_regex = re.compile(r"^[A-Z][A-Z0-9_]*=.*")
    for i, items in enumerate(old_messages):
        tmp_message: list[Union[ThemeRef, ThemeStr]] = []
        for j, item in enumerate(items.split(" ")):
            # Variables consume the entire line
            if variable_regex.match(items) is not None:
                tmp_message.append(ThemeStr(items,
                                   ThemeAttr("types", "iptables_variable")))
                break

            if not j:
                if item.startswith(("/usr/sbin/iptables", "/sbin/iptables")):
                    tmp_message.append(ThemeStr(item,
                                       ThemeAttr("types", "iptables_programname")))
                elif item.startswith("*"):
                    tmp_message.append(ThemeStr(item,
                                       ThemeAttr("types", "iptables_table")))
                elif item.startswith(":"):
                    tmp_message.append(ThemeStr(item,
                                       ThemeAttr("types", "iptables_chain")))
                elif item.startswith("COMMIT"):
                    tmp_message.append(ThemeStr(item,
                                       ThemeAttr("types", "iptables_command")))
                elif item.startswith("-"):
                    tmp_message.append(ThemeStr(item,
                                       ThemeAttr("types", "iptables_option")))
                elif item.startswith("#"):
                    tmp_message.append(ThemeStr(items[j:],
                                       ThemeAttr("types", "iptables_comment")))
                    break
            elif item.startswith("-"):
                tmp_message.append(ThemeStr(f" {item}",
                                   ThemeAttr("types", "iptables_option")))
            elif item.startswith("#"):
                tmp_message.append(ThemeStr(" ",
                                   ThemeAttr("types", "iptables_comment")))
                tmp_message.append(ThemeStr(" ".join(item[j:]),
                                   ThemeAttr("types", "iptables_comment")))
                break
            else:
                tmp_message.append(ThemeStr(f" {item}",
                                   ThemeAttr("types", "iptables_argument")))

        if not i:
            new_message = tmp_message
        else:
            new_remnants.append((tmp_message, severity))

    if fold_msg and "\\n" in message:
        for remnant, _severity in new_remnants:
            new_message.append(ThemeRef("separators", "newline"))
            new_message += remnant

        new_remnants = []
    return new_message, severity, facility, new_remnants


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def http(message: str,
         **kwargs: Any) -> tuple[Sequence[Union[ThemeRef, ThemeStr]], LogLevel, str]:
    """
    Format various http log style messages.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments
                severity (LogLevel): The log severity
                facility (str): The log facility
                options (dict): Additional, rule specific, options
        Returns:
            (ThemeArray, LogLevel, str):
                (ThemeArray): The formatted string
                (LogLevel): The new loglevel
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    facility: str = deep_get(kwargs, DictPath("facility"), "")
    options: dict = deep_get(kwargs, DictPath("options"), {})

    reformat_timestamps = deep_get(options, DictPath("reformat_timestamps"), False)

    ipaddress = ""

    # If the message starts with a timestamp without a leading IP-address, skip this
    if not message.startswith("["):
        # First try to check if it's an IP-address
        tmp = re.match(r"^([a-f0-9:][a-f0-9:.]+[a-f0-9])( - - .*)", message)
        if tmp is not None:
            # Just pass-through if validators isn't installed;
            # this might lead to false positives, but it's better than
            # not working at all
            if validators is None or validators.ipv4(tmp[1]) or validators.ipv6(tmp[1]):
                ipaddress = tmp[1]
                message = tmp[2]

    # Short format
    if ipaddress:
        tmp = re.match(r"( - - )"                  # separator1
                       r"(\[)"                     # separator2
                       r"(\d\d)"                   # day
                       r"/"
                       r"([A-Z][a-z][a-z])"        # _month
                       r"/"
                       r"(\d{4})"                  # year
                       r" "
                       r"(\d\d:\d\d:\d\d)"         # hms
                       r"(\])"                     # separator3
                       r"(\s\")"                   # separator4
                       r"([A-Z]*?\s)"              # verb
                       r"(\S*?)"                   # address3
                       r"(\s\S*?)"                 # protocol
                       r"(\"\s)"                   # separator5
                       r"(\d+?)"                   # statuscode
                       r"(\s+[\d-]+?$)", message)  # separator6

        if tmp is not None:
            address1 = ipaddress
            separator1 = tmp[1]
            separator2 = tmp[2]
            day = tmp[3]
            _month = tmp[4]
            month = month_to_numerical(_month)
            year = tmp[5]
            hms = tmp[6]
            if reformat_timestamps:
                ts = f"{year}-{month}-{day} {hms}"
            else:
                ts = f"{day}/{_month}/{year}:{hms}"
            separator3 = tmp[7]
            separator4 = tmp[8]
            verb = tmp[9]
            address3 = tmp[10]
            protocol = tmp[11]
            separator5 = tmp[12]
            statuscode = tmp[13]
            _statuscode = int(statuscode)
            if 100 <= _statuscode < 300:
                severity = LogLevel.NOTICE
            elif 300 <= _statuscode < 400:
                severity = LogLevel.WARNING
            else:
                severity = LogLevel.ERR
            separator6 = tmp[14]
            new_message: Sequence[Union[ThemeRef, ThemeStr]] = [
                ThemeStr(address1, ThemeAttr("logview", "hostname")),
                ThemeStr(separator1, ThemeAttr("logview", "severity_info")),
                ThemeStr(f"{separator2}{ts}{separator3}", ThemeAttr("logview", "timestamp")),
                ThemeStr(separator4, ThemeAttr("logview", "severity_info")),
                ThemeStr(verb, ThemeAttr("logview", "protocol")),
                ThemeStr(address3, ThemeAttr("logview", "url")),
                ThemeStr(protocol, ThemeAttr("logview", "protocol")),
                ThemeStr(separator5, ThemeAttr("logview", "severity_info")),
                ThemeStr(statuscode,
                         ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")),
                ThemeStr(separator6, ThemeAttr("logview", "severity_info")),
            ]

            return new_message, severity, facility

    if ipaddress:
        tmp = re.match(r"( - - )"
                       r"(\[)"
                       r"(\d\d)"
                       r"/"
                       r"([A-Z][a-z][a-z])"
                       r"/"
                       r"(\d{4})"
                       r":"
                       r"(\d\d:\d\d:\d\d)"
                       r"(\s\+\d{4}|\s-\d{4})"
                       r"(\])"
                       r"(\s\")"
                       r"([A-Z]*?\s)"
                       r"(\S*?)"
                       r"(\s\S*?)"
                       r"(\"\s)"
                       r"(\d+?)"
                       r"(\s+\d+?\s\")"
                       r"([^\"]*)"
                       r"(\")"
                       r"(\s|$)"
                       r"(\"|.*$)"
                       r"([^\"]*|$)"
                       r"(\"|$)"
                       r"(\s.*$|$)", message)

        if tmp is not None:
            address1 = ipaddress
            separator1 = tmp[1]
            separator2 = tmp[2]
            day = tmp[3]
            _month = tmp[4]
            month = month_to_numerical(_month)
            year = tmp[5]
            hms = tmp[6]
            tz = tmp[7]
            if reformat_timestamps:
                ts = f"{year}-{month}-{day} {hms}{tz}"
            else:
                ts = f"{day}/{_month}/{year}:{hms}{tz}"
            separator3 = tmp[8]
            separator4 = tmp[9]
            verb = tmp[10]
            address3 = tmp[11]
            protocol = tmp[12]
            separator5 = tmp[13]
            statuscode = tmp[14]
            _statuscode = int(statuscode)
            if 100 <= _statuscode < 300:
                severity = LogLevel.NOTICE
            elif 300 <= _statuscode < 400:
                severity = LogLevel.WARNING
            else:
                severity = LogLevel.ERR
            separator6 = tmp[15]
            address4 = tmp[16]
            separator7 = tmp[17] + tmp[18] + tmp[19]
            address5 = tmp[20]
            separator8 = tmp[21]
            remainder = tmp[22]

            severity_name = f"severity_{loglevel_to_name(severity).lower()}"
            new_message = [
                ThemeStr(address1, ThemeAttr("logview", "hostname")),
                ThemeStr(separator1, ThemeAttr("logview", "severity_info")),
                ThemeStr(f"{separator2}{ts}{separator3}", ThemeAttr("logview", "timestamp")),
                ThemeStr(separator4, ThemeAttr("logview", "severity_info")),
                ThemeStr(verb, ThemeAttr("logview", "protocol")),
                ThemeStr(address3, ThemeAttr("logview", "url")),
                ThemeStr(protocol, ThemeAttr("logview", "protocol")),
                ThemeStr(separator5, ThemeAttr("logview", "severity_info")),
                ThemeStr(statuscode, ThemeAttr("logview", severity_name)),
                ThemeStr(separator6, ThemeAttr("logview", "severity_info")),
                ThemeStr(address4, ThemeAttr("logview", "url")),
                ThemeStr(separator7, ThemeAttr("logview", "severity_info")),
            ]
            if address5 is not None:
                new_message.append(ThemeStr(address5, ThemeAttr("logview", "url")))
                new_message.append(ThemeStr(separator8, ThemeAttr("logview", "severity_info")))
            if remainder is not None:
                new_message.append(ThemeStr(remainder, ThemeAttr("types", "generic")))

            return new_message, severity, facility

    # Alternate formats
    tmp = re.match(r"^\|\s+"
                   r"(\d{3})"         # statuscode
                   r"\s+\|\s+"
                   r"([0-9.]+)"       # duration
                   r"([^ ]*)"         # unit
                   r"\s+\|\s+"
                   r"([^:^\s]*)"      # hostname
                   r":(\d+?)"         # port
                   r"\s+\|\s+"
                   r"([A-Z]+)"        # verb
                   r"\s+"
                   r"(.*)", message)  # url

    if tmp is not None:
        statuscode = tmp[1]
        _statuscode = int(statuscode)
        if 100 <= _statuscode < 300:
            severity = LogLevel.NOTICE
        elif 300 <= _statuscode < 400:
            severity = LogLevel.WARNING
        else:
            severity = LogLevel.ERR
        duration = tmp[2]
        unit = tmp[3]
        hostname = tmp[4]
        port = tmp[5]
        verb = tmp[6]
        url = tmp[7]
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        new_message = [
            ThemeStr("| ", ThemeAttr("logview", "severity_info")),
            ThemeStr(statuscode, ThemeAttr("logview", severity_name)),
            ThemeStr(" | ", ThemeAttr("logview", "severity_info")),
            ThemeStr(duration, ThemeAttr("logview", "severity_info")),
            ThemeStr(unit, ThemeAttr("types", "unit")),
            ThemeStr(" | ", ThemeAttr("logview", "severity_info")),
            ThemeStr(hostname, ThemeAttr("logview", "hostname")),
            ThemeRef("separators", "port"),
            ThemeStr(port, ThemeAttr("types", "port")),
            ThemeStr(" | ", ThemeAttr("logview", "severity_info")),
            ThemeStr(verb, ThemeAttr("logview", "protocol")),
            ThemeStr(" ", ThemeAttr("logview", "severity_info")),
            ThemeStr(url, ThemeAttr("logview", "url")),
        ]
        return new_message, severity, facility

    tmp = re.match(r"^\["
                   r"(\d{4}-\d\d-\d\d)"
                   r"T"
                   r"(\d\d:\d\d:\d\d\.\d\d\d)Z"
                   r"\] \""
                   r"([A-Z]+)"
                   r"\s"
                   r"([^\s]+)"
                   r"\s"
                   r"([^\"]+)"
                   r"\" "
                   r"([\d]+)"
                   r" ([^\s]+)"
                   r" ([^\s]+)"
                   r" ([^\s]+)"
                   r" ([^\s]+)"
                   r" ([^\s]+) "
                   r"\"([^\"]+)\" "
                   r"\"([^\"]+)\" "
                   r"\"([^\"]+)\" "
                   r"\"([^\"]+)\" "
                   r"\"([^\"]+)\"", message)

    if tmp is not None:
        date = tmp[1]
        hmsms = tmp[2]

        if reformat_timestamps:
            ts = f"{date} {hmsms} +0000"
        else:
            ts = f"{date}T{hmsms}Z"

        verb = tmp[3]
        address1 = tmp[4]
        protocol = tmp[5]
        statuscode = tmp[6]
        _statuscode = int(statuscode)
        if 100 <= _statuscode < 300:
            severity = LogLevel.NOTICE
        elif 300 <= _statuscode < 400:
            severity = LogLevel.WARNING
        else:
            severity = LogLevel.ERR
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"

        number0 = tmp[7]
        number1 = tmp[8]
        number2 = tmp[9]
        number3 = tmp[10]
        number4 = tmp[11]
        client = tmp[12]
        str0 = tmp[13]
        str1 = tmp[14]
        str2 = tmp[15]
        str3 = tmp[16]

        new_message = [
            ThemeStr(f"[{ts}] ", ThemeAttr("logview", "timestamp")),
            ThemeStr("\"", ThemeAttr("logview", "severity_info")),
            ThemeStr(f"{verb} ", ThemeAttr("logview", "protocol")),
            ThemeStr(address1, ThemeAttr("logview", "url")),
            ThemeStr(f" {protocol}", ThemeAttr("logview", "protocol")),
            ThemeStr("\" ", ThemeAttr("logview", "severity_info")),
            ThemeStr(statuscode, ThemeAttr("logview", severity_name)),
            ThemeStr(f" {number0}", ThemeAttr("logview", "severity_info")),
            ThemeStr(f" {number1}", ThemeAttr("logview", "severity_info")),
            ThemeStr(f" {number2}", ThemeAttr("logview", "severity_info")),
            ThemeStr(f" {number3}", ThemeAttr("logview", "severity_info")),
            ThemeStr(f" {number4} \"", ThemeAttr("logview", "severity_info")),
            ThemeStr(f"{client}", ThemeAttr("logview", "url")),
            ThemeStr("\" \"", ThemeAttr("logview", "severity_info")),
            ThemeStr(str0, ThemeAttr("logview", "url")),
            ThemeStr("\" \"", ThemeAttr("logview", "severity_info")),
            ThemeStr(str1, ThemeAttr("logview", "url")),
            ThemeStr("\" \"", ThemeAttr("logview", "severity_info")),
            ThemeStr(str2, ThemeAttr("logview", "url")),
            ThemeStr("\" \"", ThemeAttr("logview", "severity_info")),
            ThemeStr(str3, ThemeAttr("logview", "url")),
            ThemeStr("\"", ThemeAttr("logview", "severity_info")),
        ]
        return new_message, severity, facility

    if severity is None:
        severity = LogLevel.INFO
    severity_name = f"severity_{loglevel_to_name(severity).lower()}"
    return [ThemeStr(f"{ipaddress}", ThemeAttr("logview", "hostname")),
            ThemeStr(f"{message}", ThemeAttr("logview", severity_name))], severity, facility


def split_glog(message: str, **kwargs: Any) \
    -> tuple[str, LogLevel, str,
             list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]], bool]:
    """
    Extract messages in glog format.

        Parameters:
            message (str): The message to reformat
            **kwargs (dict[str, Any]): Keyword arguments
                severity (LogLevel): The current loglevel
                facility (str): The current facility
        Returns:
            (message, severity, facility, remnants, matched)
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.DEFAULT)
    facility: str = deep_get(kwargs, DictPath("facility"), "")

    matched: bool = False
    loggingerror = None
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

    # Workaround a bug in use of glog; to make the logged message useful
    # we separate it from the warning about glog use; this way we can get the proper severity
    if message.startswith("ERROR: logging before flag.Parse: "):
        loggingerror = "ERROR: logging before flag.Parse"
        message = message.removeprefix("ERROR: logging before flag.Parse: ")

    tmp = re.match(r"^([A-Z]\d{4} \d\d:\d\d:\d\d\.\d)\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{9}Z (.*)",
                   message)
    if tmp is not None:
        message = f"{tmp[1]}{tmp[2]}"

    tmp = re.match(r"^([A-Z])\d\d\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s(.+?:\d+)\](.*)", message)
    if tmp is not None:
        severity = letter_to_severity(tmp[1])

        # We do not use PID, but it is here just to document the meaning of the field
        # _pid = tmp[2]

        facility = f"{(tmp[3])}"
        message = f"{(tmp[4])}"
        # The first character is always whitespace unless this is an empty line
        if message:
            message = message[1:]
        matched = True
    else:
        if severity is None:
            severity = LogLevel.INFO

    # If we have a logging error we return that as message and the rest as remnants
    if loggingerror is not None:
        severity = LogLevel.ERR
        remnants.insert(0,
                        ([ThemeStr(message,
                                   ThemeAttr("logview",
                                             f"severity_{loglevel_to_name(severity).lower()}"))],
                         severity))
        message = loggingerror

    return message, severity, facility, remnants, matched


# pylint: disable-next=too-many-locals
def tab_separated(message: str, **kwargs: Any) \
    -> tuple[str, LogLevel, str,
             list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Extract messages of the format datetime\tSEVERITY\t[facility\t]message[\tjson].

        Parameters:
            message (str): The message to reformat
            **kwargs (dict[str, Any]): Keyword arguments
                severity (LogLevel): The current loglevel
                facility (str): The current facility
                fold_msg (bool): Should the message be expanded or folded?
                options (dict): Additional, rule specific, options
        Returns:
            (message, severity, facility, remnants)
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    facility: str = deep_get(kwargs, DictPath("facility"), "")
    fold_msg: bool = deep_get(kwargs, DictPath("fold_msg"), True)
    options: dict = deep_get(kwargs, DictPath("options"), {})

    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

    messages: list[str] = deep_get(options, DictPath("messages"), ["msg", "message"])
    errors: list[str] = deep_get(options, DictPath("errors"), ["err", "error"])
    versions: list[str] = deep_get(options, DictPath("versions"), [])

    fields = message.split("\t")

    # If the first field is not a timestamp
    # we cannot trust the rest of the message to be what we hope for.
    if not is_timestamp(fields[0]) or len(fields) < 3:
        return message, severity, facility, remnants

    severity = str_to_severity(fields[1], default=severity)
    message_index = 2
    if fields[2][0].islower():
        facility = fields[2]
        message_index += 1

    message = fields[message_index]
    remnants_index = message_index + 1

    override_formatting: dict[str, Any] = {}
    for _msg in versions:
        override_formatting[f"\"{_msg}\""] = {
            "key": ThemeAttr("types", "yaml_key"),
            "value": ThemeAttr("logview", "severity_notice")
        }
    for _msg in messages:
        override_formatting[f"\"{_msg}\""] = {
            "key": ThemeAttr("types", "yaml_key"),
            "value": ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")
        }
    for _err in errors:
        override_formatting[f"\"{_err}\""] = {
            "key": ThemeAttr("types", "yaml_key_error"),
            "value": ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"),
        }

    if not fold_msg and remnants_index < len(fields) \
            and fields[remnants_index].startswith("{") and fields[remnants_index].endswith("}"):
        try:
            d = json.loads(fields[remnants_index])
            json_strs = json_dumps(d)
            for remnant in formatters.format_yaml(json_strs,
                                                  override_formatting=override_formatting):
                remnants.append((remnant, severity))
        except DecodeException:
            message = " ".join(fields[message_index:])
    else:
        message = " ".join(fields[message_index:])

    return message, severity, facility, remnants


def __split_severity_facility_style(message: str, **kwargs: Any) -> tuple[str, LogLevel, str]:
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    facility: str = deep_get(kwargs, DictPath("facility"), "")
    tmp = re.match(r"^\s*([A-Z]+)\s+([a-zA-Z-\.]+)\s+(.*)", message)
    if tmp is not None:
        severity = str_to_severity(tmp[1], default=severity)
        facility = tmp[2]
        message = tmp[3]
    return message, severity, facility


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def split_json_style(message: str, **kwargs: Any) \
    -> tuple[Union[str, Sequence[Union[ThemeRef, ThemeStr]]], LogLevel, str,
             list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Split JSON style messages.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments
                severity (LogLevel): The log severity
                facility (str): The log facility
                fold_msg (bool): [unused]
                options (dict): Additional, rule specific, options
        Returns:
            (str|ThemeArray, LogLevel, str, [(ThemeArray, LogLevel)]):
                (str|ThemeArray): The untouched or formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    facility: str = deep_get(kwargs, DictPath("facility"), "")
    fold_msg: bool = deep_get(kwargs, DictPath("fold_msg"), True)
    options: dict = deep_get(kwargs, DictPath("options"), {})
    logentry: dict = {}

    messages: list[DictPath] = deep_get(options, DictPath("messages"), ["msg", "message"])
    errors: list[DictPath] = deep_get(options, DictPath("errors"), ["err", "error"])
    error_tags = deep_get(options, DictPath("error_tags"), {})
    timestamps: list[DictPath] = deep_get(options, DictPath("timestamps"),
                                          ["ts", "time", "timestamp"])
    severities: list[DictPath] = deep_get(options, DictPath("severities"), ["level"])
    severity_overrides = deep_get(options, DictPath("msg#severity#overrides"), [])
    facilities: list[DictPath] = deep_get(options,
                                          DictPath("facilities"), ["logger", "caller", "filename"])
    versions: list[DictPath] = deep_get(options, DictPath("versions"), [])

    message = message.replace("\x00", "")

    try:
        logentry = json.loads(message)
    except DecodeException:
        pass

    # Unfold Python dicts
    if logentry is None:
        d = None
        try:
            d = ast.literal_eval(message)
        except (ValueError, TypeError, SyntaxError, RecursionError):
            pass

        if d is not None:
            try:
                logentry = json_dumps(d)
            except ValueError:
                pass

    # pylint: disable-next=too-many-nested-blocks
    if logentry is not None and isinstance(logentry, dict):
        # If msg_first we reorder the dict
        if LogparserConfiguration.msg_first:
            _d = {}
            for key in messages + errors:
                value = logentry.get(key, None)
                if value is not None:
                    _d[key] = value
            for key in logentry:
                if key not in messages + errors:
                    value = logentry.get(key, "")
                    if value is not None:
                        _d[key] = value
            logentry = _d

        msg = deep_get_with_fallback(logentry, messages, "")
        level = deep_get_with_fallback(logentry, severities, None)
        if LogparserConfiguration.pop_severity:
            for _sev in severities:
                logentry.pop(_sev, None)
        if LogparserConfiguration.pop_ts:
            for _ts in timestamps:
                logentry.pop(_ts, None)

        if facility == "":
            for _fac in facilities:
                if isinstance(_fac, str):
                    facility = deep_get(logentry, DictPath(_fac), "")
                    break

                if not isinstance(_fac, dict):
                    continue

                _facilities = deep_get(_fac, DictPath("keys"), [])
                _separators = deep_get(_fac, DictPath("separators"), [])
                for i, _fac in enumerate(_facilities):
                    # This is to allow prefixes/suffixes.
                    if _fac != "":
                        if _fac not in logentry:
                            break
                        facility += str(deep_get(logentry, DictPath(_fac), ""))
                    if i < len(_separators):
                        facility += _separators[i]

        if LogparserConfiguration.pop_facility:
            for _fac in facilities:
                if isinstance(_fac, str):
                    logentry.pop(_fac, None)
                if not isinstance(_fac, dict):
                    continue
                # This is a list, since the order of the facilities matter when outputting
                # it does not matter when popping though
                for __fac in deep_get(_fac, DictPath("keys"), []):
                    if __fac == "":
                        continue

                    logentry.pop(__fac, None)

        if level is not None:
            severity = str_to_severity(level)

        # If the message is folded, append the rest
        if fold_msg:
            if severity is not None:
                msgseverity = severity
            else:
                msgseverity = LogLevel.INFO
            # Append all remaining fields to message
            if msg == "":
                message = str(logentry)
            else:
                if LogparserConfiguration.msg_extract:
                    # pop the first matching _msg
                    for _msg in messages:
                        if _msg in logentry:
                            logentry.pop(_msg, None)
                            break
                    if logentry:
                        message = f"{msg} {logentry}"
                    else:
                        message = msg
                else:
                    message = str(logentry)
        # else return an expanded representation
        else:
            if severity is not None and severity == LogLevel.DEBUG:
                structseverity: LogLevel = severity
            else:
                structseverity = LogLevel.INFO

            if "err" not in logentry and "error" not in logentry:
                if severity is not None:
                    msgseverity = severity
                else:
                    msgseverity = LogLevel.INFO
            else:
                msgseverity = structseverity
            if severity is not None:
                errorseverity = severity
            else:
                errorseverity = LogLevel.ERR

            if LogparserConfiguration.msg_extract:
                message = msg
                # Pop the first matching _msg
                for _msg in messages:
                    if _msg in logentry:
                        logentry.pop(_msg, None)
                        break
            else:
                message = ""

            override_formatting: dict[str, Any] = {}
            formatted_message = None
            remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

            if logentry:
                tagseverity = None
                if structseverity == LogLevel.DEBUG:
                    override_formatting = {"__all": ThemeAttr("logview", "severity_debug")}
                else:
                    for _msg in versions:
                        override_formatting[f"\"{_msg}\""] = {
                            "key": ThemeAttr("types", "yaml_key"),
                            "value": ThemeAttr("logview", "severity_notice")
                        }
                    msg_severity_name = f"severity_{loglevel_to_name(msgseverity).lower()}"
                    error_severity_name = f"severity_{loglevel_to_name(errorseverity).lower()}"
                    for _msg in messages:
                        override_formatting[f"\"{_msg}\""] = {
                            "key": ThemeAttr("types", "yaml_key"),
                            "value": ThemeAttr("logview", msg_severity_name)
                        }
                    for _err in errors:
                        override_formatting[f"\"{_err}\""] = {
                            "key": ThemeAttr("types", "yaml_key_error"),
                            "value": ThemeAttr("logview", error_severity_name),
                        }
                    for tag, tag_values in error_tags.items():
                        for tag_key, tag_severity in tag_values.items():
                            if tag_key in deep_get(logentry, DictPath(tag), []):
                                tagseverity = str_to_severity(tag_severity, default=msgseverity)
                                break
                        if tagseverity is not None:
                            break
                if tagseverity is not None:
                    tag_severity_name = f"severity_{loglevel_to_name(tagseverity).lower()}"
                    override_formatting[f"\"{_msg}\""] = {
                        "key": ThemeAttr("types", "yaml_key"),
                        "value": ThemeAttr("logview", tag_severity_name)
                    }
                    severity = tagseverity

                dump = json_dumps(logentry)

                expand_newline_fields: tuple = ()
                if LogparserConfiguration.expand_newlines:
                    expand_newline_fields = (
                        "config",
                        "errorVerbose",
                        "stacktrace",
                        "status.message")

                tmp = formatters.format_yaml([dump],
                                             override_formatting=override_formatting,
                                             expand_newline_fields=expand_newline_fields,
                                             value_expand_tabs=LogparserConfiguration.expand_tabs)

                if severity is None:
                    if structseverity is not None:
                        severity = structseverity
                    else:
                        severity = LogLevel.INFO
                if not message:
                    formatted_message = tmp[0]
                    tmp.pop(0)
                    msgseverity = structseverity
                for line in tmp:
                    remnants.append((line, severity))

            if formatted_message is not None:
                return formatted_message, severity, facility, remnants

            if isinstance(message, str):
                _message, severity = \
                    custom_override_severity(message, severity,
                                             overrides={
                                                 "options": {
                                                     "overrides": severity_overrides,
                                                 }})
            return message, severity, facility, remnants

    return message, severity, facility, []


def merge_message(message: Union[str, list[Union[ThemeRef, ThemeStr]]], **kwargs: Any) \
        -> tuple[str, list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Given message + remnants, merge the message into the remnants and return an empty message.

        Parameters:
            message (str|themearray): The string to merge into remnants
            **kwargs (dict[str, Any]): Keyword arguments
                remnants (list[(themearray, LogLevel)]): The list of remnants
                severity (LogLevel): The severity for message
        Returns:
            (message, remnants):
                message (str): The newly emptied message
                remnants (list[(themearray, LogLevel)]): Remnants with message preprended
    """
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = \
        deep_get(kwargs, DictPath("remnants"))
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)

    # This is a ThemeArray
    if isinstance(message, list):
        if remnants is not None:
            remnants = [(message, severity)] + remnants
        else:
            remnants = message
    else:
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        if remnants is not None:
            remnants.insert(0,
                            ([ThemeStr(message, ThemeAttr("logview", severity_name))], severity))
        else:
            remnants = [([ThemeStr(message, ThemeAttr("logview", severity_name))], severity)]
    message = ""

    return message, remnants


# pylint: disable-next=too-many-locals
def split_json_style_raw(message: str, **kwargs: Any) \
        -> tuple[str, LogLevel, str, list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Split JSON style messages.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments
                severity (LogLevel): The log severity
                facility (str): The log facility
                fold_msg (bool): [unused]
                options (dict): Additional, rule specific, options
        Returns:
            (str|ThemeArray, LogLevel, str, [(ThemeArray, LogLevel)]):
                (str|ThemeArray): The untouched or formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    facility: str = deep_get(kwargs, DictPath("facility"), "")
    fold_msg: bool = deep_get(kwargs, DictPath("fold_msg"), True)
    options: dict = deep_get(kwargs, DictPath("options"), {})
    merge_msg: bool = deep_get(kwargs, DictPath("merge_msg"), False)

    # This warning seems incorrect
    # pylint: disable-next=global-variable-not-assigned
    global LogparserConfiguration

    tmp_msg_first = LogparserConfiguration.msg_first
    tmp_msg_extract = LogparserConfiguration.msg_extract
    tmp_pop_severity = LogparserConfiguration.pop_severity
    tmp_pop_ts = LogparserConfiguration.pop_ts
    tmp_pop_facility = LogparserConfiguration.pop_facility

    LogparserConfiguration.msg_first = False
    LogparserConfiguration.msg_extract = False
    LogparserConfiguration.pop_severity = False
    LogparserConfiguration.pop_ts = False
    LogparserConfiguration.pop_facility = False

    _message, _severity, _facility, _remnants = \
        split_json_style(message=message, severity=severity,
                         facility=facility, fold_msg=fold_msg, options=options)

    LogparserConfiguration.msg_first = tmp_msg_first
    LogparserConfiguration.msg_extract = tmp_msg_extract
    LogparserConfiguration.pop_severity = tmp_pop_severity
    LogparserConfiguration.pop_ts = tmp_pop_ts
    LogparserConfiguration.pop_facility = tmp_pop_facility

    if merge_msg:
        message, remnants = merge_message(message, remnants=_remnants, severity=severity)
    else:
        remnants = _remnants

    if severity is None:
        severity = _severity
    if facility == "":
        facility = _facility

    return message, severity, facility, remnants


# pylint: disable-next=too-many-locals,too-many-branches
def json_event(message: str,
               **kwargs: Any) -> tuple[Union[str, list[Union[ThemeRef, ThemeStr]]],
                                       LogLevel, str,
                                       list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Given a string, extract any events in JSON format.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments
                severity (LogLevel): The log severity
                facility (str): The log facility
                fold_msg (bool): Should the message be expanded or folded?
                options (dict): Additional, rule specific, options
        Returns:
            (ThemeArray, LogLevel, str, [(ThemeArray, LogLevel)]):
                (ThemeArray): The formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    facility: str = deep_get(kwargs, DictPath("facility"), "")
    fold_msg: bool = deep_get(kwargs, DictPath("fold_msg"), True)
    options: dict = deep_get(kwargs, DictPath("options"), {})

    new_message: Union[str, list[Union[ThemeRef, ThemeStr]]] = []
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []
    tmp = message.split(" ", 2)

    if not message.startswith("EVENT ") or len(tmp) < 3:
        return message, severity, facility, remnants

    event = tmp[1]

    if event in ("AddPod", "DeletePod", "AddNamespace", "AddNetworkPolicy", "DeleteNamespace") \
            or (event in ("UpdatePod", "UpdateNamespace") and "} {" not in tmp[2]):
        msg = tmp[2]
        _message, _severity, _facility, remnants = \
            split_json_style_raw(message=msg, severity=severity, facility=facility,
                                 fold_msg=fold_msg, options=options, merge_msg=True)
        new_message = [ThemeStr(f"{tmp[0]} {event}", ThemeAttr("logview", "severity_info"))]
        if event in ("UpdatePod", "UpdateNamespace"):
            severity_name = f"severity_{loglevel_to_name(severity).lower()}"
            new_message = [ThemeStr(f"{tmp[0]} {event}", ThemeAttr("logview", severity_name)),
                           ThemeStr(" [No changes]", ThemeAttr("logview", "unchanged"))]
    elif event in ("UpdatePod", "UpdateNamespace"):
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        tmp2 = re.match(r"^({.*})\s*({.*})", tmp[2])
        if tmp2 is not None:
            try:
                old = json.loads(tmp2[1])
            except DecodeException:
                new_message = \
                    [ThemeStr(f"{tmp[1]} {event}", ThemeAttr("logview", severity_name)),
                     ThemeStr(" [error: could not parse json]",
                              ThemeAttr("logview", "severity_error"))]
                remnants = [([ThemeStr(tmp[2], ThemeAttr("logview", severity_name))], severity)]
                return new_message, severity, facility, remnants

            old_str = json_dumps(old)
            try:
                new = json.loads(tmp2[2])
            except DecodeException:
                new_message = [ThemeStr(f"{tmp[0]} {event}",
                                        ThemeAttr("logview", severity_name)),
                               ThemeStr(" [error: could not parse json]",
                                        ThemeAttr("logview", "severity_error"))]
                remnants = [([ThemeStr(tmp[2], ThemeAttr("logview", severity_name))], severity)]
                return new_message, severity, facility, remnants
            new_str = json_dumps(new)

            y = 0
            for el in difflib.unified_diff(old_str.split("\n"), new_str.split("\n"),
                                           n=sys.maxsize, lineterm=""):
                y += 1
                if y < 4:
                    continue
                if el.startswith("+"):
                    remnants.append(([ThemeStr(el, ThemeAttr("logview", "severity_diffplus"))],
                                     LogLevel.DIFFPLUS))
                elif el.startswith("-"):
                    remnants.append(([ThemeStr(el, ThemeAttr("logview", "severity_diffminus"))],
                                     LogLevel.DIFFMINUS))
                else:
                    remnants.append(([ThemeStr(el, ThemeAttr("logview", "severity_diffsame"))],
                                     LogLevel.DIFFSAME))
            new_message = [ThemeStr(f"{tmp[0]} {event}", ThemeAttr("logview", severity_name)),
                           ThemeStr(" [State modified]", ThemeAttr("logview", "modified"))]
    else:
        errmsg = [
            [("Unknown EVENT type: ", "default"),
             (f"{event}", "argument")],
        ]
        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(errmsg)
        cmtlog.log(LogLevel.ERR, msg=unformatted_msg, messages=formatted_msg)
        return message, severity, facility, remnants

    return new_message, severity, facility, remnants


def split_angle_bracketed_facility(message: str, facility: str = "") -> tuple[str, str]:
    """
    Split a message in "<facility> message" format into message, facility.

        Parameters:
            message (str): The message part of the msg to format
            facility (str): The current facility (typically empty)
        Returns:
            (str, str):
                (str): The message part
                (str): The facility
    """
    tmp = re.match(r"^<(.+?)>\s?(.*)", message)
    if tmp is not None:
        facility = tmp[1]
        message = tmp[2]
    return message, facility


def split_colon_facility(message: str, facility: str = "") -> tuple[str, str]:
    """
    Split a message in "facility: message" format into message, facility.

        Parameters:
            message (str): The message part of the msg to format
            facility (str): The current facility (typically empty)
        Returns:
            (str, str):
                (str): The message part
                (str): The facility
    """
    tmp = re.match(r"^(\S+?):\s?(.*)", message)
    if tmp is not None:
        facility = tmp[1]
        message = tmp[2]
    return message, facility


def split_bracketed_timestamp_severity_facility(message: str,
                                                **kwargs: Any) -> tuple[str, LogLevel, str]:
    """
    Split a message in "[timestamp severity facility] message" format into message, facility.

        Parameters:
            message (str): The message part of the msg to format
            **kwargs (dict[str, Any]): Keyword arguments
                default: The default severity to return if the message coouldn't be split
        Returns:
            (str, LogLeve, str):
                (str): The message part
                (LogLevel): The extracted LogLevel
                (str): The facility
    """
    severity: LogLevel = deep_get(kwargs, DictPath("default"), LogLevel.INFO)
    facility: str = ""

    tmp = re.match(r"^\[([^ ]+) ([^ ]+) (.+?)\]: (.+)", message)

    if tmp is not None:
        severity = str_to_severity(tmp[2])
        facility = tmp[3]
        message = tmp[4]

    return message, severity, facility


# pylint: disable-next=too-many-branches,too-many-locals
def custom_override_severity(message: Union[str, list],
                             severity: LogLevel,
                             **kwargs: Any) -> tuple[Union[str, list], LogLevel]:
    """
    Override the message severity if the message matches the provided ruleset.

        Parameters:
            message (str|ThemeArray): The string to override severity for
            severity (LogLevel): The log severity
            **kwargs (dict[str, Any]): Keyword arguments
                overrides ([dict]): The override rules
        Returns:
            (str|ThemeArray, LogLevel):
    """
    overrides: list[dict] = deep_get(kwargs, DictPath("options#overrides"), [])

    if not LogparserConfiguration.override_severity:
        return message, severity

    if isinstance(message, list):
        tmp_message = themearray_to_string(message)
    else:
        tmp_message = message
    override_message = message

    for override in overrides:
        override_type = deep_get(override, DictPath("matchtype"), "")
        override_pattern = deep_get(override, DictPath("matchkey"), "")
        override_loglevel = name_to_loglevel(deep_get(override, DictPath("loglevel"), ""))

        if override_type == "startswith":
            if not tmp_message.startswith(override_pattern):
                continue
        elif override_type == "endswith":
            if not tmp_message.endswith(override_pattern):
                continue
        elif override_type == "contains":
            if override_pattern not in tmp_message:
                continue
        elif override_type == "regex":
            tmp = override_pattern.match(tmp_message)
            if tmp is None:
                continue
        else:
            msg = [
                [("Unknown override_type “", "error"),
                 (f"{override_type}", "argument"),
                 ("“", "error")]
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR, formatted_msg=formatted_msg)

        severity = override_loglevel

        if isinstance(message, list):
            override_message = []
            severity_name = f"severity_{loglevel_to_name(override_loglevel).lower()}"
            for substring in message:
                override_message.append(ThemeStr(substring.string,
                                                 ThemeAttr("logview", severity_name)))
        break

    return override_message, severity


# pylint: disable-next=too-many-branches
def expand_event_objectmeta(message: str, severity: LogLevel, **kwargs: Any) \
        -> tuple[LogLevel,
                 Union[str, list[Union[ThemeRef, ThemeStr]]],
                 list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Given a log message, expand and format objectmeta event messages.

        Parameters:
            message (str): The log message
            severity (LogLevel): Current loglevel; will be overriden if new severity is higher
            **kwargs (dict[str, Any]): Keyword arguments
                remnants ([(ThemeArray, LogLevel)]): Remnants for messages split into multiple lines
        Returns:
            (LogLevel, str|ThemeArray, [(ThemeArray, LogLevel)]):
                (LogLevel): The new loglevel
                (str|ThemeArray): The processed message
                ([(ThemeArray, LogLevel)]): The formatted remnants
    """
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]],
                         LogLevel]] = deep_get(kwargs, DictPath("remnants"), [])

    raw_message = message
    curlydepth = 0

    # This just makes sure that the indentation matches up
    for i in range(0, len(raw_message)):
        if message[i] == "{":
            curlydepth += 1
        elif message[i] == "}":
            curlydepth -= 1
            if curlydepth < 0:
                # Abort parsing; assume that this message is either malformed
                # or that the parser is flawed
                return severity, message, remnants

    new_message: Union[str, list[Union[ThemeRef, ThemeStr]]] = []
    remnants = []
    indent = 2
    depth = 0
    escaped = False
    tmp = ""

    for i, raw_msg in enumerate(raw_message):
        if raw_msg == "\"" and not escaped:
            pass
        elif raw_msg == "\\":
            escaped = not escaped
        elif raw_msg in ("{", ",", "}"):
            if raw_msg != "}":
                tmp += raw_msg
            else:
                if tmp == "":
                    tmp += raw_msg
                    depth -= 1
                    if i < len(raw_msg) - 1:
                        continue

            # OK, this is not an escaped curly brace or comma,
            # so it is time to flush the buffer
            if not new_message:
                if ":" in tmp:
                    key, value = tmp.split(":", 1)
                    new_message = [ThemeStr("".ljust(indent * depth) + key,
                                            ThemeAttr("types", "yaml_key")),
                                   ThemeRef("separators", "yaml_key_separator"),
                                   ThemeStr(f"{value}", ThemeAttr("types", "yaml_value"))]
                else:
                    new_message = [ThemeStr("".ljust(indent * depth) + tmp,
                                            ThemeAttr("types", "yaml_value"))]
            else:
                if ":" in tmp:
                    key, value = tmp.split(":", 1)
                    remnants.append(([ThemeStr("".ljust(indent * depth) + key,
                                               ThemeAttr("types", "yaml_key")),
                                      ThemeRef("separators", "yaml_key_separator"),
                                      ThemeStr(f"{value}",
                                               ThemeAttr("types", "yaml_value"))], severity))
                else:
                    remnants.append(([ThemeStr("".ljust(indent * depth) + tmp,
                                               ThemeAttr("types", "yaml_value"))], severity))
            tmp = ""
            if raw_msg == "{":
                depth += 1
            elif raw_msg == "}":
                tmp += raw_msg
                depth -= 1
            continue
        tmp += raw_msg
    return severity, new_message, remnants


# pylint: disable-next=too-many-locals,too-many-branches
def expand_event(message: str, severity: LogLevel, **kwargs: Any) \
        -> tuple[LogLevel, str, list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Given a log message, expand and format event messages.

        Parameters:
            message (str): The log message
            severity (LogLevel): Current loglevel; will be overriden if new severity is higher
            **kwargs (dict[str, Any]): Keyword arguments
                remnants ([(ThemeArray, LogLevel)]): Remnants for messages split into multiple lines
                fold_msg (bool): Should lines be unfolded where possible?
        Returns:
            (LogLevel, str, [(ThemeArray, LogLevel)]):
                (LogLevel): The new loglevel
                (str): The processed message
                ([(ThemeArray, LogLevel)]): The formatted remnants
    """
    remnants: Optional[list[tuple[list[Union[ThemeRef, ThemeStr]],
                                  LogLevel]]] = deep_get(kwargs, DictPath("remnants"))
    fold_msg: bool = deep_get(kwargs, DictPath("fold_msg"), True)

    if fold_msg or (remnants is not None and remnants):
        return severity, message, remnants

    raw_message = message
    parendepth = 0
    curlydepth = 0
    eventstart = 0
    eventend = 0
    refstart = 0
    refend = 0

    for i in range(0, len(raw_message)):
        if message[i] == "(":
            parendepth += 1
            if eventstart is None:
                eventstart = i + 1
        elif message[i] == "{":
            curlydepth += 1
            if refstart is None:
                refstart = i + 1
        elif message[i] == "}":
            curlydepth -= 1
            if curlydepth < 0:
                # Abort parsing; assume that this message is either malformed
                # or that the parser is flawed
                return message, remnants
            refend = i
        elif message[i] == ")":
            parendepth -= 1
            if not parendepth:
                if curlydepth:
                    # Abort parsing; assume that this message is either malformed
                    # or that the parser is flawed
                    return message, remnants

                eventend = i
                break

    remnants = []
    message = raw_message[0:eventstart]
    indent = 2
    # Try to extract an embedded severity; use it if higher than severity
    tmp = re.match(r"^.*type: '([A-Z][a-z]+)' reason:", raw_message)
    if tmp is not None:
        _severity = severity
        if tmp[1] == "Normal":
            _severity = LogLevel.INFO
        elif tmp[1] == "Warning":
            _severity = LogLevel.WARNING
        severity = min(severity, _severity)
    remnants.append(([ThemeStr(" ".ljust(indent) + raw_message[eventstart:refstart],
                               ThemeAttr("types", "yaml_reference"))], severity))
    for _key_value in raw_message[refstart:refend].split(", "):
        key, value = _key_value.split(":", 1)
        remnants.append(([ThemeStr(" ".ljust(indent * 2) + key, ThemeAttr("types", "yaml_key")),
                          ThemeRef("separators", "yaml_key_separator"),
                          ThemeStr(f" {value}", ThemeAttr("types", "yaml_value"))], severity))
    remnants.append(([ThemeStr(" ".ljust(indent * 1) + raw_message[refend:eventend],
                               ThemeAttr("types", "yaml_reference"))], severity))
    severity_name = f"severity_{loglevel_to_name(severity).lower()}"
    remnants.append(([ThemeStr(raw_message[eventend:eventend + 3],
                               ThemeAttr("logview", severity_name)),
                      ThemeStr(raw_message[eventend + 3:len(raw_message)],
                               ThemeAttr("logview", severity_name))], severity))

    return severity, message, remnants


def format_key_value(key: str, value: str,
                     severity: LogLevel, **kwargs: Any) -> list[Union[ThemeRef, ThemeStr]]:
    """
    Given a key, value, and severity, return a formatted ThemeArray.

        Parameters:
            key (str): The key to format
            value (str): The value to format
            severity (LogLevel): The LogLevel to use when forcing severity
            **kwargs (dict[str, Any]): Keyword arguments
                force_severity (bool): Override default formatting; use severity instead
                error_keys ((str, ...)): A tuple of keys that should be formatted as errors
                allow_bare_keys (bool): Should keys without a value be accepted?
        Returns:
            (ThemeArray): The formatted message
    """
    force_severity = deep_get(kwargs, DictPath("force_severity"), False)
    error_keys = deep_get(kwargs, DictPath("error_keys"), ("error", "err"))
    severity_name = f"severity_{loglevel_to_name(severity).lower()}"
    tmp: list[Union[ThemeRef, ThemeStr]]

    separator = [ThemeRef("separators", "keyvalue_log")]
    if key in error_keys:
        tmp = [ThemeStr(f"{key}", ThemeAttr("types", "key_error"))] \
            + separator \
            + [ThemeStr(f"{value}", ThemeAttr("logview", severity_name))]
    elif force_severity:
        tmp = [ThemeStr(f"{key}", ThemeAttr("types", "key"))] \
            + separator \
            + [ThemeStr(f"{value}", ThemeAttr("logview", severity_name))]
    else:
        tmp = [ThemeStr(f"{key}", ThemeAttr("types", "key"))]
        if value is not None:
            tmp += separator \
                + [ThemeStr(f"{value}", ThemeAttr("types", "value"))]
    return tmp


def sysctl(message: str, **kwargs: Any) -> tuple[str, LogLevel, str,
                                                 list[tuple[list[Union[ThemeRef, ThemeStr]],
                                                            LogLevel]]]:
    """
    Format output from sysctl.

        Parameters:
            message (str): The string to format
            **kwargs (dict[str, Any]): Keyword arguments
                severity (LogLevel): The log severity
                facility (str): The log facility
        Returns:
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    facility: str = deep_get(kwargs, DictPath("facility"), "")

    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []
    new_message: list[Union[ThemeRef, ThemeStr]] = []

    kv = message.split(" = ")
    if len(kv) == 2:
        key, value = kv
        keyparts = key.split(".")
        for i, part in enumerate(keyparts):
            new_message.append(ThemeStr(part, ThemeAttr("types", "key")))
            if i < len(keyparts) - 1:
                new_message.append(ThemeRef("separators", "sysctl_key_components"))
        new_message.append(ThemeRef("separators", "sysctl_keyvalue"))
        new_message.append(ThemeStr(value, ThemeAttr("types", "value")))
    return facility, severity, new_message, remnants


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def key_value(message: str, **kwargs: Any) -> tuple[str, LogLevel, str,
                                                    list[tuple[list[Union[ThemeRef, ThemeStr]],
                                                               LogLevel]]]:
    """
    Format a key=value message.

        Parameters:
            message (str): The string to format
            **kwargs (dict[str, Any]): Keyword arguments
                severity (LogLevel): The log severity
                facility (str): The log facility
                fold_msg (bool): Should the message be expanded or folded?
                options (dict): Additional, rule specific, options
        Returns:
            (str|ThemeArray, LogLevel, str, [(ThemeArray, LogLevel)]):
                (str|ThemeArray): The untouched or formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    facility: str = deep_get(kwargs, DictPath("facility"), "")
    fold_msg: bool = deep_get(kwargs, DictPath("fold_msg"), True)
    options: dict = deep_get(kwargs, DictPath("options"), {})

    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

    messages = deep_get(options, DictPath("messages"), ["msg"])
    errors = deep_get(options, DictPath("errors"), ["err", "error"])
    timestamps = deep_get(options, DictPath("timestamps"), ["t", "ts", "time"])
    severities = deep_get(options, DictPath("severities"), ["level", "lvl"])
    severity_overrides = deep_get(options, DictPath("severity#overrides"), [])
    facilities = deep_get(options, DictPath("facilities"),
                          ["source", "subsys", "caller", "logger", "Topic"])
    versions = deep_get(options, DictPath("versions"), [])
    allow_bare_keys: bool = deep_get(options, DictPath("allow_bare_keys"), False)
    substitute_bullets_: bool = deep_get(options, DictPath("substitute_bullets"), True)
    collector_bullets: bool = deep_get(options, DictPath("collector_bullets"), False)
    is_event: bool = deep_get(options, DictPath("is_event"), False)

    # Split all key=value pairs. Make sure not to process "=="
    key_value_regex = re.compile(r"^(.*?[^=])=($|[^=].*$)")
    tmp = re.findall(r"(?:\".*?\"|\S)+", message.replace("\\\"", "<<<quote>>>"))
    # pylint: disable-next=too-many-nested-blocks
    if tmp is not None:
        # First go through the list of matches and check that there are at least one
        # key=value pair; we do not allow *only* bare keys. While it could theoretically
        # occur, it leaves too much room for false positives.
        if not any("=" in item for item in tmp):
            # Give up; this line cannot be parsed as a set of key=value
            return facility, severity, message, remnants

        d: dict = {}
        for item in tmp:
            tmp2 = key_value_regex.match(item)
            if tmp2 is None:
                if allow_bare_keys and not item.endswith(":"):
                    if item not in d:
                        d[item] = None
                else:
                    # Give up; this line cannot be parsed as a set of key=value
                    return facility, severity, message, remnants
            else:
                key = tmp2[1]
                value = tmp2[2].replace("<<<quote>>>", "\\\"")
                if key not in d:
                    d[key] = value
                else:
                    # Give up; this line cannot be parsed as a set of key=value
                    break
            # XXX: Instead of just giving up we should probably do something with the leftovers...

        if LogparserConfiguration.pop_ts:
            for _ts in timestamps:
                d.pop(_ts, None)
        level = deep_get_with_fallback(d, severities)
        if LogparserConfiguration.pop_severity:
            for _sev in severities:
                d.pop(_sev, None)
        if level is not None:
            severity = str_to_severity(level, default=severity)

        msg = deep_get_with_fallback(d, messages, "")
        if msg.startswith("\"") and msg.endswith("\""):
            msg = msg[1:-1]
        version = deep_get_with_fallback(d, versions, "").strip("\"")

        if facility == "":
            for _fac in facilities:
                if isinstance(_fac, str):
                    facility = deep_get(d, DictPath(_fac), "")
                    break

                if isinstance(_fac, dict):
                    _facilities = deep_get(_fac, DictPath("keys"), [])
                    _separators = deep_get(_fac, DictPath("separators"), [])
                    for i, _fac in enumerate(_facilities):
                        # This is to allow prefixes/suffixes
                        if _fac != "":
                            if _fac not in d:
                                break
                            facility += str(deep_get(d, DictPath(_fac), ""))
                        if i < len(_separators):
                            facility += _separators[i]
        if LogparserConfiguration.pop_facility:
            for _fac in facilities:
                if isinstance(_fac, str):
                    d.pop(_fac, None)
                elif isinstance(_fac, dict):
                    # This is a list, since the order of the facilities matter when outputting
                    # it does not matter when popping though
                    for __fac in deep_get(_fac, DictPath("keys"), []):
                        if __fac == "":
                            continue

                        d.pop(__fac)

        # pylint: disable-next=too-many-boolean-expressions
        if not fold_msg \
                and len(d) == 2 \
                and LogparserConfiguration.merge_starting_version \
                and "msg" in d \
                and msg.startswith("Starting") \
                and "version" in d \
                and version.startswith("(version="):
            message, severity = \
                custom_override_severity(msg, severity,
                                         overrides={
                                             "options": {
                                                 "overrides": severity_overrides,
                                             }})
            message = f"{msg} {version}"
        elif "err" in d \
                and ("errors occurred:" in d["err"] or "error occurred:" in d["err"]) \
                and not fold_msg:
            err = d["err"]
            if err.startswith("\"") and err.endswith("\""):
                err = err[1:-1]
            message = f"{msg}"
            tmp = re.match(r"^(\d+ errors? occurred:)(.*)", err)
            if tmp is not None:
                severity_name = f"severity_{loglevel_to_name(severity).lower()}"
                remnants.append(([ThemeStr(tmp[1], ThemeAttr("logview", severity_name))],
                                 severity))
                s = tmp[2].replace("\\t", "").split("\\n")
                for line in s:
                    if line:
                        # Real bullets look so much nicer
                        if line.startswith("* ") \
                                and substitute_bullets_ \
                                and LogparserConfiguration.msg_realbullets:
                            remnants.append(([ThemeRef("separators", "logbullet"),
                                              ThemeStr(f"{line[2:]}",
                                                       ThemeAttr("logview", severity_name))],
                                             severity))
                        else:
                            remnants.append(([ThemeStr(f"{line}",
                                                       ThemeAttr("logview", severity_name))],
                                             severity))
        else:
            tmp = []
            # If we are extracting msg we always want msg first
            if LogparserConfiguration.msg_extract and not fold_msg and msg:
                tmp.append(msg)
                # Pop the first matching _msg
                for _msg in messages:
                    if _msg in d:
                        d.pop(_msg, "")
                        break
                for key in errors:
                    if (value := d.pop(key, "")):
                        tmp.append(format_key_value(key, value, severity, error_keys=errors))
            else:
                if LogparserConfiguration.msg_first:
                    if fold_msg:
                        for key in messages + errors:
                            value = d.pop(key, "")
                            if value:
                                if LogparserConfiguration.msg_extract and key in messages:
                                    # We already have the message extracted
                                    tmp.append(msg)
                                else:
                                    tmp.append(f"{key}={value}")
                    else:
                        if (msg := deep_get_with_fallback(d, messages, "")):
                            force_severity = False
                            if not any(key in errors for key in d):
                                force_severity = True
                            tmp.append(format_key_value("msg", msg, severity,
                                       force_severity=force_severity))
                        # Pop the first matching _msg
                        for _msg in messages:
                            if _msg in d:
                                d.pop(_msg, "")
                                break
                        for key in errors:
                            if (value := d.pop(key, "")):
                                tmp.append(format_key_value(key, value, severity))

            for d_key, d_value in d.items():
                if not fold_msg:
                    if d_key == "collector" \
                            and collector_bullets \
                            and LogparserConfiguration.bullet_collectors:
                        tmp.append(f"• {d_value}")
                    elif d_key in versions:
                        tmp.append(format_key_value(d_key, d_value,
                                                    LogLevel.NOTICE, force_severity=True))
                    else:
                        if is_event and d_key == "type":
                            severity_ = severity
                            if d_value.strip("\"") == "Normal":
                                severity_ = LogLevel.NOTICE
                            elif d_value.strip("\"") == "Warning":
                                severity_ = LogLevel.WARNING
                            tmp.append(format_key_value(d_key, d_value,
                                                        severity_, force_severity=True))
                            severity = min(severity, severity_)
                        elif is_event and d_key == "reason":
                            # A lot more reasons need to be added here
                            if d_value.strip("\"") in ("Completed",
                                                       "Created",
                                                       "Killing",
                                                       "LeaderElection",
                                                       "Pulled",
                                                       "Pulling",
                                                       "RegisteredNode",
                                                       "Resumed",
                                                       "Scheduled",
                                                       "ServiceNotReady",
                                                       "Started",
                                                       "Suspended",
                                                       "SuccessfulCreate",
                                                       "SuccessfulDelete",
                                                       "WaitForServeDeploymentReady"):
                                severity_ = LogLevel.NOTICE
                            elif d_value.strip("\"") in ("BackOff",
                                                         "FailedBinding",
                                                         "FailedScheduling",
                                                         "FailedToCreateEndpoint",
                                                         "ServiceUnhealthy"):
                                severity_ = LogLevel.WARNING
                            elif d_value.strip("\"") in ("BackoffLimitExceeded",):
                                severity_ = LogLevel.ERR
                            tmp.append(format_key_value(d_key, d_value, severity_,
                                                        force_severity=True))
                        else:
                            d_value, severity_ = \
                                custom_override_severity(d_value, severity,
                                                         overrides={
                                                             "options": {
                                                                 "overrides": severity_overrides,
                                                             }})
                            force_severity = severity_ != severity
                            tmp.append(format_key_value(d_key, d_value, severity_,
                                                        force_severity=force_severity,
                                                        allow_bare_keys=allow_bare_keys))
                else:
                    if d_value:
                        tmp.append(f"{d_key}={d_value}")
                    else:
                        tmp.append(f"{d_key}")

            if fold_msg:
                message = " ".join(tmp)
            else:
                if tmp:
                    message = tmp.pop(0)
                else:
                    message = ""
                if tmp:
                    remnants = (tmp, severity)

    if LogparserConfiguration.expand_newlines \
            and "\\n" in message \
            and isinstance(message, str) \
            and not fold_msg:
        lines = message.split("\\n")
        message = lines[0]
        _remnants = []
        if len(lines) > 1:
            severity_name = f"severity_{loglevel_to_name(severity).lower()}"
            for line in lines[1:]:
                _remnants.append(([ThemeStr(f"{line}", ThemeAttr("logview", severity_name))],
                                  severity))
            if isinstance(remnants, tuple):
                severity_name = f"severity_{loglevel_to_name(remnants[1]).lower()}"
                for remnant in remnants[0]:
                    _remnants.append((remnant, remnants[1]))
                remnants = _remnants
            elif isinstance(remnants, list):
                remnants = _remnants + remnants

    if facility.startswith("\"") and facility.endswith("\""):
        facility = facility[1:-1]
    return facility, severity, message, remnants


# pylint: disable-next=too-many-locals
def key_value_with_leading_message(message: str, **kwargs: Any) -> \
        tuple[str, LogLevel, str, list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Format a "message key=value" message.

        Parameters:
            message (str): The string to format
            **kwargs (dict[str, Any]): Keyword arguments
                severity (LogLevel): The log severity
                facility (str): The log facility
                fold_msg (bool): Should the message be expanded or folded?
                options (dict): Additional, rule specific, options
        Returns:
            (str|ThemeArray, LogLevel, str, [(ThemeArray, LogLevel)]):
                (str|ThemeArray): The untouched or formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    facility: str = deep_get(kwargs, DictPath("facility"), "")
    fold_msg: bool = deep_get(kwargs, DictPath("fold_msg"), True)
    options: dict = deep_get(kwargs, DictPath("options"), {})
    allow_bare_keys: bool = deep_get(options, DictPath("allow_bare_keys"), False)

    # This warning seems incorrect
    # pylint: disable-next=global-variable-not-assigned
    global LogparserConfiguration
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []
    is_event: bool = False

    if fold_msg:
        return facility, severity, message, remnants

    # Split into substrings based on spaces
    tmp = re.findall(r"(?:\".*?\"|\S)+", message.replace("\\\"", "<<<quote>>>"))
    if tmp is not None and tmp:
        # First go through the list of matches and check that there are at least one
        # key=value pair; we do not allow *only* bare keys. While it could theoretically
        # occur, it leaves too much room for false positives.
        if not any("=" in item for item in tmp):
            # Give up; this line cannot be parsed as a set of key=value
            return facility, severity, message, remnants

        if "=" in tmp[0]:
            # Try parsing this as regular key_value
            facility, severity, new_message, remnants = \
                key_value(message, fold_msg=fold_msg, severity=severity,
                          facility=facility, options=options)
            if not isinstance(new_message, str):
                new_message = themearray_to_string(new_message)
            return facility, severity, new_message, remnants

        for item in tmp[1:]:
            # we could not parse this as "msg key=value"; give up
            if "=" not in item and (item.endswith(":") or not allow_bare_keys):
                return facility, severity, message, remnants
        rest = message.removeprefix(tmp[0]).lstrip()
        new_message = tmp[0]
        tmp_msg_extract = LogparserConfiguration.msg_extract
        LogparserConfiguration.msg_extract = False

        if new_message.strip("\"") == "Event occurred":
            is_event = True
        if options is None:
            options = {}
        options["is_event"] = is_event

        facility, severity, first_message, tmp_new_remnants = \
            key_value(rest, fold_msg=fold_msg, severity=severity,
                      facility=facility, options=options)
        LogparserConfiguration.msg_extract = tmp_msg_extract
        if tmp_new_remnants is not None and tmp_new_remnants:
            new_remnants_strs, new_remnants_severity = tmp_new_remnants
            new_remnants = ([first_message] + new_remnants_strs, new_remnants_severity)
        else:
            if first_message:
                new_remnants = ([first_message], severity)
            else:
                new_remnants = None
        return facility, severity, new_message, new_remnants
    return facility, severity, message, remnants


# pylint: disable-next=unused-argument
def modinfo(message: str, **kwargs: Any) \
        -> tuple[str, LogLevel, Union[str, list[Union[ThemeRef, ThemeStr]]],
                 list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Format the output from the Linux modinfo command.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ((str, LogLevel, str, [(ThemeArray, LogLevel)]))):
                (str): The log facility
                (ThemeArray): The formatted string
                (LogLevel): The LogLevel of the message
                (str|ThemeArray): The unchanged message if nothing matched,
                                  or the formatted themearray
                ([(ThemeArray, LogLevel)]): [unused]
    """
    facility = ""
    severity = LogLevel.INFO
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

    tmp = re.match(r"^([a-z][\S]*?):(\s+)(.+)", message)
    if tmp is not None:
        key = tmp[1]
        whitespace = tmp[2]
        value = tmp[3]
        new_message: list[Union[ThemeRef, ThemeStr]] = [
            ThemeStr(key, ThemeAttr("types", "key")),
            ThemeRef("separators", "keyvalue"),
            ThemeStr(whitespace, ThemeAttr("types", "generic")),
            ThemeStr(value, ThemeAttr("types", "value")),
        ]
        return facility, severity, new_message, remnants
    return facility, severity, message, remnants


# pylint: disable-next=unused-argument
def bracketed_timestamp_severity(message: str, **kwargs: Any) \
        -> tuple[str, LogLevel, str, list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Split a message of the type [timestamp] [severity] message.

        Parameters:
            message (str): The log message
            **kwargs (dict[str, Any]): Keyword arguments
        Returns:
            (str, LogLevel, str, [(ThemeArray, LogLevel)]):
                (str): The extracted facility [unused]
                (str): The processed message
                remnants (list[(themearray, LogLevel)]): Remnants with message preprended [unused]
    """
    facility: str = ""
    severity: LogLevel = LogLevel.INFO
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

    # Some messages have double timestamps...
    message, _timestamp = split_iso_timestamp(message, none_timestamp())
    message, severity = split_bracketed_severity(message, default=LogLevel.WARNING)

    if message.startswith(("XPU Manager:", "Build:", "Level Zero:")):
        severity = LogLevel.NOTICE

    return facility, severity, message, remnants


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def directory(message: str,
              **kwargs: Any) -> tuple[str, LogLevel,
                                      Union[str, list[Union[ThemeRef, ThemeStr]]],
                                      list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Format the output from "ls -alF --color" command.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ((str, LogLevel, str|ThemeArray, [(ThemeArray, LogLevel)]))):
                (str): The log facility
                (LogLevel): The LogLevel of the message
                (str|ThemeArray): The unchanged message if nothing matched,
                                  or the formatted themearray
                ([(ThemeArray, LogLevel)]): [unused]
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    facility: str = deep_get(kwargs, DictPath("facility"), "")

    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

    tmp = re.match(r"^(total)\s+(\d+)$", message)
    if tmp is not None:
        return facility, severity, message, remnants

    tmp = re.match(r"^(.)"                  # etype
                   r"(.{9})"                # permissions
                   r"(\+|\s)"               # acl
                   r"(\s+)"                 # space1
                   r"(\d+)"                 # linkcount
                   r"(\s+)"                 # space2
                   r"([^\s]+)"              # owner
                   r"(\s+)"                 # space3
                   r"([^\s]+)"              # group
                   r"(\s+)"                 # space4
                   r"(\d+)"                 # size part1
                   r"(,\s+\d+|)"            # size part2
                   r"(\s+)"                 # space5
                   r"([^\s]+)"              # month
                   r"(\s+)"                 # space6
                   r"(\d+)"                 # day
                   r"(\s+)"                 # space7
                   r"([^\s]+)"              # yearortime
                   r"(\s+)"                 # space8
                   r"(.+?)"                 # name
                   r"(=|\||/|)$", message)  # suffix
    if tmp is None:
        # This is unlikely to be a directory match
        return facility, severity, message, remnants

    etype = tmp[1]
    permissions = tmp[2]
    acl = tmp[3]
    space1 = tmp[4]
    linkcount = tmp[5]
    space2 = tmp[6]
    owner = tmp[7]
    space3 = tmp[8]
    group = tmp[9]
    space4 = tmp[10]
    size = tmp[11] + tmp[12]
    space5 = tmp[13]
    month = tmp[14]
    space6 = tmp[15]
    day = tmp[16]
    space7 = tmp[17]
    yearortime = tmp[18]
    space8 = tmp[19]
    name = tmp[20]
    suffix = tmp[21]

    _message: list[Union[ThemeRef, ThemeStr]] = [
        ThemeStr(f"{etype}", ThemeAttr("types", "dir_type")),
        ThemeStr(f"{permissions}", ThemeAttr("types", "dir_permissions")),
        ThemeStr(f"{acl}", ThemeAttr("types", "dir_permissions")),
        ThemeStr(f"{space1}", ThemeAttr("types", "generic")),
        ThemeStr(f"{linkcount}", ThemeAttr("types", "dir_linkcount")),
        ThemeStr(f"{space2}", ThemeAttr("types", "generic")),
        ThemeStr(f"{owner}", ThemeAttr("types", "dir_owner")),
        ThemeStr(f"{space3}", ThemeAttr("types", "generic")),
        ThemeStr(f"{group}", ThemeAttr("types", "dir_group")),
        ThemeStr(f"{space4}", ThemeAttr("types", "generic")),
        ThemeStr(f"{size}", ThemeAttr("types", "dir_size")),
        ThemeStr(f"{space5}", ThemeAttr("types", "generic")),
        ThemeStr(f"{month}", ThemeAttr("types", "dir_date")),
        ThemeStr(f"{space6}", ThemeAttr("types", "generic")),
        ThemeStr(f"{day}", ThemeAttr("types", "dir_date")),
        ThemeStr(f"{space7}", ThemeAttr("types", "generic")),
        ThemeStr(f"{yearortime}", ThemeAttr("types", "dir_date")),
        ThemeStr(f"{space8}", ThemeAttr("types", "generic")),
    ]
    # regular file
    if etype == "-":
        _message += [
            ThemeStr(f"{name}", ThemeAttr("types", "dir_file"))
        ]
    # block device
    elif etype == "b":
        _message += [
            ThemeStr(f"{name}", ThemeAttr("types", "dir_dev"))
        ]
    # character device
    elif etype == "c":
        _message += [
            ThemeStr(f"{name}", ThemeAttr("types", "dir_dev"))
        ]
    # sticky bit has precedence over the regular directory type
    elif permissions.endswith("t"):
        _message += [
            ThemeStr(f"{name}", ThemeAttr("types", "dir_sticky"))
        ]
    # directory
    elif etype == "d":
        _message += [
            ThemeStr(f"{name}", ThemeAttr("types", "dir_dir"))
        ]
    # symbolic link
    elif etype == "l":
        tmp2 = re.match(r"^(.+?)( -> )(.+)", name)
        if tmp2 is None:
            _message += [
                ThemeStr(f"{name}", ThemeAttr("types", "dir_symlink_name"))
            ]
        else:
            _message += [
                ThemeStr(f"{tmp2[1]}", ThemeAttr("types", "dir_symlink_name")),
                ThemeStr(f"{tmp2[2]}", ThemeAttr("types", "dir_symlink_link"))
            ]
            # There is no suffix for devices or regular files,
            # but we can distinguish the two based on the file size;
            # the size for devices is not really a size per se,
            # but rather major, minor (a normal size never has a comma)
            if not suffix:
                if "," in size:
                    _message += [
                        ThemeStr(f"{tmp2[3]}", ThemeAttr("types", "dir_dev")),
                    ]
                else:
                    _message += [
                        ThemeStr(f"{tmp2[3]}", ThemeAttr("types", "dir_file")),
                    ]
            elif suffix == "|":
                _message += [
                    ThemeStr(f"{tmp2[3]}", ThemeAttr("types", "dir_pipe")),
                ]
            elif suffix == "=":
                _message += [
                    ThemeStr(f"{tmp2[3]}", ThemeAttr("types", "dir_socket")),
                ]
            elif suffix == "/":
                _message += [
                    ThemeStr(f"{tmp2[3]}", ThemeAttr("types", "dir_dir")),
                ]
            else:
                raise ValueError(f"Unhandled suffix {suffix} in line {message}")
    # pipe
    elif etype == "p":
        _message += [
            ThemeStr(f"{name}", ThemeAttr("types", "dir_pipe"))
        ]
    # socket
    elif etype == "s":
        _message += [
            ThemeStr(f"{name}", ThemeAttr("types", "dir_socket"))
        ]

    if suffix:
        _message += [
            ThemeStr(f"{suffix}", ThemeAttr("types", "dir_suffix"))
        ]

    return facility, severity, _message, remnants


# input: [     0.000384s]  INFO ThreadId(01) linkerd2_proxy::rt: Using single-threaded proxy runtime
# output:
#   severity: LogLevel.INFO
#   facility: ThreadId(01)
#   msg: [     0.000384s] linkerd2_proxy::rt: Using single-threaded proxy runtime
#   remnants: []
# pylint: disable-next=unused-argument
def seconds_severity_facility(message: str, **kwargs: Any) \
        -> tuple[str, LogLevel, Union[str, list[Union[ThemeRef, ThemeStr]]],
                 list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Convert messages in [seconds] SEVERITY facility message format.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ((str, LogLevel, str|ThemeArray, [(ThemeArray, LogLevel)]))):
                (str): The log facility
                (LogLevel): The LogLevel of the message
                (str|ThemeArray): The unchanged message if nothing matched,
                                  or the formatted themearray
                ([(ThemeArray, LogLevel)]): [unused]
    """
    facility: str = ""
    severity: LogLevel = LogLevel.INFO
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

    tmp = re.match(r"(\[\s*?\d+?\.\d+?s\])\s+([A-Z]+?)\s+(\S+?)\s(.*)", message)
    if tmp is not None:
        severity = str_to_severity(tmp[2], default=severity)
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        facility = tmp[3]
        new_message: list[Union[ThemeRef, ThemeStr]] = \
            [ThemeStr(f"{tmp[1]} ", ThemeAttr("logview", "timestamp")),
             ThemeStr(f"{tmp[4]}", ThemeAttr("logview", severity_name))]
        return facility, severity, new_message, remnants

    return facility, severity, message, remnants


def substitute_bullets(message: str, **kwargs: Any) -> str:
    """
    Replace a prefix (by default "* ") with actual bullet characters.

        Parameters:
            message (str): The message to process
            **kwargs (dict[str, Any]): Keyword arguments
                options (dict[str, Any]): options
                    prefix (str): The prefix to use to substitute for "proper" bullets
        Returns:
            message (str): The message with bullets substituted
    """
    options: dict = deep_get(kwargs, DictPath("options"), {})
    prefix: str = deep_get(options, DictPath("prefix"), "* ")

    if message.startswith(prefix) and LogparserConfiguration.msg_realbullets:
        # We do not want to replace all "*" in the message with bullet, just prefixes
        message = message[0:len(prefix)].replace("*", "•", 1) + message.removeprefix(prefix)
    return message


# pylint: disable-next=unused-argument
def python_traceback_scanner_nested_exception(message: str, **kwargs: Any) \
        -> tuple[tuple[str, Optional[Callable], dict],
                 tuple[datetime, str, LogLevel, list[Union[ThemeRef, ThemeStr]]]]:
    """
    Scanner for nested Python tracebacks.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (((str, Callable, dict),
              (datetime, str, LogLevel, [(ThemeArray, LogLevel)]))):
                ((str, Callable, dict)):
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                ((datetime, str, LogLevel, Callable, dict)):
                    (datetime): The timestamp
                    (str): The facility of the message
                    (LogLevel): The LogLevel of the message
                    ([(ThemeArray, LogLevel)]):
                        (ThemeArray): The formatted strings of the remnant
                        (LogLevel): The severity of the remnant
    """
    timestamp: datetime = none_timestamp()
    facility: str = ""
    severity: LogLevel = LogLevel.ERR
    message, _timestamp = split_iso_timestamp(message, none_timestamp())
    processor: tuple[str, Optional[Callable], dict] = \
        ("block", python_traceback_scanner_nested_exception, {})

    # Default case
    remnants: list[Union[ThemeRef, ThemeStr]] = [
        ThemeStr(message, ThemeAttr("logview", "severity_info"))
    ]

    tmp = re.match(r"^([A-Z])\d\d\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s(.+?:\d+)\] (.*)", message)
    if tmp is not None:
        message = tmp[4]
        remnants = [
            ThemeStr(message, ThemeAttr("logview", "severity_info"))
        ]

    if (tmp := re.match(r"^(\s+\+ )"
                        r"(Exception Group Traceback "
                        r"\(most recent call last\):)", message)) is not None:
        remnants = [
            ThemeStr(tmp[1], ThemeAttr("logview", "severity_info")),
            ThemeStr(tmp[2], ThemeAttr("logview", "severity_error")),
        ]
    elif (tmp := re.match(r"^(\s+\|\s+)(During handling of the above "
                          r"exception, another exception occurred:)",
                          message)) is not None:
        remnants = [
            ThemeStr(tmp[1], ThemeAttr("logview", "severity_info")),
            ThemeStr(tmp[2], ThemeAttr("logview", "severity_error")),
        ]
    elif (tmp := re.match(r"^(\s+\|\s+)(Traceback "
                          r"\(most recent call last\):)", message)) is not None:
        remnants = [
            ThemeStr(tmp[1], ThemeAttr("logview", "severity_info")),
            ThemeStr(tmp[2], ThemeAttr("logview", "severity_error")),
        ]
    elif (tmp := re.match(r"^(\s+\|\s+)(File \")(.+?)(\", line )"
                          r"(\d+)(, in )(.*)", message)) is not None:
        remnants = [
            ThemeStr(tmp[1], ThemeAttr("logview", "severity_info")),
            ThemeStr(tmp[2], ThemeAttr("types", "path")),
            ThemeStr(tmp[3], ThemeAttr("logview", "severity_info")),
            ThemeStr(tmp[4], ThemeAttr("types", "lineno")),
            ThemeStr(tmp[5], ThemeAttr("logview", "severity_info")),
            ThemeStr(tmp[6], ThemeAttr("types", "path")),
        ]
    elif re.match(r"^\s+\+-+$", message):
        remnants = [
            ThemeStr(message, ThemeAttr("logview", "severity_info")),
        ]
        processor = ("end_block", None, {})
    else:
        if (tmp := re.match(r"^(\s+\|\s+)"
                            r"(\S+?Error:|"
                            r"\S+?Exception:|"
                            r"ExceptionGroup:|"
                            r"GeneratorExit:|"
                            r"KeyboardInterrupt:|"
                            r"StopIteration:|"
                            r"StopAsyncIteration:|"
                            r"SystemExit:|"
                            r"socket.gaierror:"
                            r")( .*)", message)) is not None:
            remnants = [
                ThemeStr(tmp[1], ThemeAttr("logview", "severity_info")),
                ThemeStr(tmp[2], ThemeAttr("logview", "severity_error")),
                ThemeStr(tmp[3], ThemeAttr("logview", "severity_info")),
            ]

    return processor, (timestamp, facility, severity, remnants)


# pylint: disable-next=unused-argument
def python_traceback_scanner(message: str, **kwargs: Any) \
        -> tuple[tuple[str, Optional[Callable], dict],
                 tuple[datetime, str, LogLevel, list[Union[ThemeRef, ThemeStr]]]]:
    """
    Scanner for Python tracebacks.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (((str, Callable, dict),
              (datetime, str, LogLevel, [(ThemeArray, LogLevel)]))):
                ((str, Callable, dict)):
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                ((datetime, str, LogLevel, Callable, dict)):
                    (datetime): The timestamp
                    (str): The facility of the message
                    (LogLevel): The LogLevel of the message
                    ([(ThemeArray, LogLevel)]):
                        (ThemeArray): The formatted strings of the remnant
                        (LogLevel): The severity of the remnant
    """
    timestamp: datetime = none_timestamp()
    facility: str = ""
    severity: LogLevel = LogLevel.ERR
    message, _timestamp = split_iso_timestamp(message, none_timestamp())
    processor: tuple[str, Optional[Callable], dict] = ("block", python_traceback_scanner, {})

    # Default case
    remnants: list[Union[ThemeRef, ThemeStr]] = [
        ThemeStr(message, ThemeAttr("logview", "severity_info"))
    ]

    tmp = re.match(r"^([A-Z])\d\d\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s(.+?:\d+)\] (.*)", message)
    if tmp is not None:
        message = tmp[4]
        remnants = [
            ThemeStr(message, ThemeAttr("logview", "severity_info"))
        ]

    if (tmp := re.match(r"^(\s+File \")(.+?)(\", line )(\d+)(, in )(.*)", message)) is not None:
        remnants = [
            ThemeStr(tmp[1], ThemeAttr("logview", "severity_info")),
            ThemeStr(tmp[2], ThemeAttr("types", "path")),
            ThemeStr(tmp[3], ThemeAttr("logview", "severity_info")),
            ThemeStr(tmp[4], ThemeAttr("types", "lineno")),
            ThemeStr(tmp[5], ThemeAttr("logview", "severity_info")),
            ThemeStr(tmp[6], ThemeAttr("types", "path")),
        ]
    else:
        if (tmp := re.match(r"(^\S+?Error:|"
                            r"^\S+?Exception:|"
                            r"GeneratorExit:|"
                            r"KeyboardInterrupt:|"
                            r"StopIteration:|"
                            r"StopAsyncIteration:|"
                            r"SystemExit:|"
                            r"socket.gaierror:"
                            r")( .*)", message)) is not None:
            remnants = [
                ThemeStr(tmp[1], ThemeAttr("logview", "severity_error")),
                ThemeStr(tmp[2], ThemeAttr("logview", "severity_info")),
            ]
            # This doesn't handle the stack trace that may follow the traceback,
            # but we cannot support that unless we have a forward-looking scanner.
            if not tmp[2].startswith(" <") or tmp[2].endswith(">"):
                processor = ("end_block", None, {})
        elif message == ">":
            processor = ("end_block", None, {})
        elif message.lstrip() == message:
            processor = ("break", None, {})

    return processor, (timestamp, facility, severity, remnants)


# pylint: disable-next=unused-argument
def python_traceback(message: str, **kwargs: Any) \
        -> tuple[Union[str, tuple[str, Optional[Callable], dict]],
                 list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Parser for Python tracebacks.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ((str | (str, Callable, dict)), [(ThemeArray, LogLevel)]):
                ((str | (str, Callable, dict))):
                    (str): The unformatted message
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                (ThemeArray): The formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

    if message.startswith(("Traceback (most recent call last):",
                           "Exception in thread ")):
        remnants = [ThemeStr(message, ThemeAttr("logview", "severity_error"))]
        processor: tuple[str, Optional[Callable], dict] = \
            ("start_block", python_traceback_scanner, {})
        return processor, remnants

    if message == "During handling of the above exception, " \
                  "another exception occurred:":
        remnants = [ThemeStr(message, ThemeAttr("logview", "severity_error"))]
        processor = \
            ("start_block", python_traceback_scanner_nested_exception, {})
        return processor, remnants

    return message, remnants


# pylint: disable-next=too-many-locals,too-many-branches
def json_line_scanner(message: str, **kwargs: Any) \
        -> tuple[tuple[str, Optional[Callable], dict],
                 tuple[datetime, str, LogLevel,
                       Optional[list[tuple[list[Union[ThemeRef, ThemeStr]],
                                           LogLevel]]]]]:
    """
    Scanner for JSON.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments
        Returns:
            (((str, Callable, dict),
              (datetime, str, LogLevel, [(ThemeArray, LogLevel)]))):
                ((str, Callable, dict)):
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                ((datetime, str, LogLevel, Callable, dict)):
                    (datetime): The timestamp
                    (str): The facility of the message
                    (LogLevel): The LogLevel of the message
                    ([(ThemeArray, LogLevel)]):
                        (ThemeArray): The formatted strings of the remnant
                        (LogLevel): The severity of the remnant
    """
    options: dict = deep_get(kwargs, DictPath("options"), {})

    allow_empty_lines: bool = deep_get(options, DictPath("allow_empty_lines"), True)
    timestamp: datetime = none_timestamp()
    facility: str = ""
    severity: LogLevel = LogLevel.INFO
    message, _timestamp = split_iso_timestamp(message, none_timestamp())
    matched: bool = True

    # If no block end is defined we continue until EOF
    block_end = deep_get(options, DictPath("block_end"), [])

    # format_block_end = False
    # process_block_end = True

    for _be in block_end:
        matchtype = deep_get(_be, DictPath("matchtype"))
        matchkey = deep_get(_be, DictPath("matchkey"))
        # format_block_end = deep_get(_be, DictPath("format_block_end"), False)
        # process_block_end = deep_get(_be, DictPath("process_block_end"), True)
        if matchtype == "empty":
            if not message.strip():
                matched = False
        elif matchtype == "exact":
            if message == matchkey:
                matched = False
        elif matchtype == "startswith":
            if message.startswith(matchkey):
                matched = False
        elif matchtype == "regex":
            tmp = matchkey.match(message)
            if tmp is not None:
                matched = False

    if message == "}".rstrip() or not matched:
        remnants, _ = formatters.format_yaml_line(message, override_formatting={})
        processor: tuple[str, Optional[Callable], dict] = ("end_block", None, {})
    elif message.lstrip() != message or message == "{":
        remnants, _ = formatters.format_yaml_line(message, override_formatting={})
        processor = ("block", json_line_scanner, {})
    elif not message.strip() and allow_empty_lines:
        remnants, _ = formatters.format_yaml_line(message, override_formatting={})
        processor = ("block", json_line_scanner, {})
    else:
        remnants = None
        processor = ("break", None, {})

    return processor, (timestamp, facility, severity, remnants)


# pylint: disable-next=too-many-locals,too-many-branches
def json_line(message: str,
              **kwargs: Any) -> tuple[Union[str, tuple[str, Optional[Callable], dict]],
                                      list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Parser for JSON.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ((str | (str, Callable, dict)), [(ThemeArray, LogLevel)]):
                ((str | (str, Callable, dict))):
                    (str): The unformatted message
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                (ThemeArray): The formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    options: dict = deep_get(kwargs, DictPath("options"), {})

    if options is None:
        options = {}

    remnants: Union[str, list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]] = []
    matched = False

    block_start = deep_get(options, DictPath("block_start"), [{
        "matchtype": "exact",
        "matchkey": "{",
        "matchline": "any",
        "format_block_start": False,
    }])
    line = deep_get(options, DictPath("__line"), 0)

    for _bs in block_start:
        matchtype = _bs["matchtype"]
        matchkey = _bs["matchkey"]
        matchline = _bs["matchline"]
        format_block_start = deep_get(_bs, DictPath("format_block_start"), False)
        if matchline == "any" or matchline == "first" and not line:
            if matchtype == "exact":
                if message == matchkey:
                    matched = True
            elif matchtype == "startswith":
                if message.startswith(matchkey):
                    matched = True
            elif matchtype == "endswith":
                if message.endswith(matchkey):
                    matched = True
            elif matchtype == "regex":
                tmp = re.match(matchkey, message)
                if tmp is not None:
                    matched = True

    if matched:
        if format_block_start:
            remnants, _ = formatters.format_yaml_line(message, override_formatting={})
        else:
            severity_name = f"severity_{loglevel_to_name(severity).lower()}"
            remnants = [ThemeStr(message, ThemeAttr("logview", severity_name))]
        processor: tuple[str, Optional[Callable], dict] = \
            ("start_block", json_line_scanner, options)
        return processor, remnants

    return message, []


# pylint: disable-next=too-many-locals,too-many-branches
def yaml_line_scanner(message: str,
                      **kwargs: Any) -> tuple[tuple[str, Optional[Callable], dict],
                                              tuple[datetime, str, LogLevel,
                                                    list[tuple[list[Union[ThemeRef, ThemeStr]],
                                                               LogLevel]]]]:
    """
    Scanner for YAML.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (((str, Callable, dict),
              (datetime, str, LogLevel, [(ThemeArray, LogLevel)]))):
                ((str, Callable, dict)):
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                ((datetime, str, LogLevel, Callable, dict)):
                    (datetime): The timestamp
                    (str): The facility of the message
                    (LogLevel): The LogLevel of the message
                    ([(ThemeArray, LogLevel)]):
                        (ThemeArray): The formatted strings of the remnant
                        (LogLevel): The severity of the remnant
    """
    options: dict = deep_get(kwargs, DictPath("options"), {})

    timestamp: datetime = none_timestamp()
    facility: str = ""
    severity: LogLevel = LogLevel.INFO
    message, _timestamp = split_iso_timestamp(message, none_timestamp())
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []
    matched = True

    # If no block end is defined we continue until EOF
    block_end = deep_get(options, DictPath("block_end"), [])

    format_block_end = False
    process_block_end = True

    for _be in block_end:
        matchtype = deep_get(_be, DictPath("matchtype"))
        matchkey = deep_get(_be, DictPath("matchkey"))
        format_block_end = deep_get(_be, DictPath("format_block_end"), False)
        process_block_end = deep_get(_be, DictPath("process_block_end"), True)
        if matchtype == "empty":
            if not message.strip():
                matched = False
        elif matchtype == "exact":
            if message == matchkey:
                matched = False
        elif matchtype == "startswith":
            if message.startswith(matchkey):
                matched = False
        elif matchtype == "regex":
            tmp = matchkey.match(message)
            if tmp is not None:
                matched = False

    if matched:
        remnants, _ = formatters.format_yaml_line(message, override_formatting={})
        processor: tuple[str, Optional[Callable], dict] = ("block", yaml_line_scanner, options)
    else:
        if process_block_end:
            if format_block_end:
                remnants, _ = formatters.format_yaml_line(message, override_formatting={})
            else:
                severity_name = f"severity_{loglevel_to_name(severity).lower()}"
                remnants = [ThemeStr(message, ThemeAttr("logview", severity_name))]
            processor = ("end_block", None, {})
        else:
            processor = ("end_block_not_processed", None, {})

    return processor, (timestamp, facility, severity, remnants)


# pylint: disable-next=too-many-locals,too-many-branches
def yaml_line(message: str, **kwargs: Any) -> \
        tuple[Union[str, tuple[str, Optional[Callable], dict]],
              Union[str, list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]]:
    """
    Parser for YAML.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ((str | (str, Callable, dict)), [(ThemeArray, LogLevel)]):
                ((str | (str, Callable, dict))):
                    (str): The unformatted message
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                (ThemeArray): The formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    options: dict = deep_get(kwargs, DictPath("options"), {})

    if options is None:
        options = {}

    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []
    matched = False

    block_start = deep_get(options, DictPath("block_start"), [{
        "matchtype": "regex",
        "matchkey": re.compile(r"^\S+?: \S.*$|^\S+?:$"),
        "matchline": "any",
        "format_block_start": False,
    }])
    line = deep_get(options, DictPath("__line"), 0)
    if deep_get(options, DictPath("eof")) is None:
        options["eof"] = "end_block"

    for _bs in block_start:
        matchtype = _bs["matchtype"]
        matchkey = _bs["matchkey"]
        matchline = _bs["matchline"]
        format_block_start = deep_get(_bs, DictPath("format_block_start"), False)
        if matchline == "any" or matchline == "first" and not line:
            if matchtype == "exact":
                if message == matchkey:
                    matched = True
            elif matchtype == "startswith":
                if message.startswith(matchkey):
                    matched = True
            elif matchtype == "endswith":
                if message.endswith(matchkey):
                    matched = True
            elif matchtype == "regex":
                tmp = re.match(matchkey, message)
                if tmp is not None:
                    matched = True

    if matched:
        if format_block_start:
            remnants, _ = formatters.format_yaml_line(message, override_formatting={})
        else:
            severity_name = f"severity_{loglevel_to_name(severity).lower()}"
            remnants = [ThemeStr(message, ThemeAttr("logview", severity_name))]
        processor: tuple[str, Optional[Callable], dict] = \
            ("start_block", yaml_line_scanner, options)
        return processor, remnants

    return message, remnants


# pylint: disable-next=too-many-locals,too-many-branches
def diff_line_scanner(message: str,
                      **kwargs: Any) -> tuple[tuple[str, Optional[Callable], dict],
                                              tuple[datetime, str, LogLevel,
                                                    list[tuple[list[Union[ThemeRef, ThemeStr]],
                                                               LogLevel]]]]:
    """
    Scanner for unified diffs.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (((str, Callable, dict),
              (datetime, str, LogLevel, [(ThemeArray, LogLevel)]))):
                ((str, Callable, dict)):
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                ((datetime, str, LogLevel, Callable, dict)):
                    (datetime): The timestamp
                    (str): The facility of the message
                    (LogLevel): The LogLevel of the message
                    ([(ThemeArray, LogLevel)]):
                        (ThemeArray): The formatted strings of the remnant
                        (LogLevel): The severity of the remnant
    """
    options: dict = deep_get(kwargs, DictPath("options"), {})

    timestamp: datetime = none_timestamp()
    facility: str = ""
    severity: LogLevel = LogLevel.INFO
    message, _timestamp = split_iso_timestamp(message, none_timestamp())
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []
    matched = True

    # If no block end is defined we continue until EOF
    block_end = deep_get(options, DictPath("block_end"), [])

    format_block_end = False
    process_block_end = True

    for _be in block_end:
        matchtype = deep_get(_be, DictPath("matchtype"))
        matchkey = deep_get(_be, DictPath("matchkey"))
        format_block_end = deep_get(_be, DictPath("format_block_end"), False)
        process_block_end = deep_get(_be, DictPath("process_block_end"), True)
        if matchtype == "empty":
            if not message.strip():
                matched = False
        elif matchtype == "exact":
            if message == matchkey:
                matched = False
        elif matchtype == "startswith":
            if message.startswith(matchkey):
                matched = False
        elif matchtype == "regex":
            tmp = matchkey.match(message)
            if tmp is not None:
                matched = False

    if matched:
        remnants = formatters.format_diff_line(message,
                                               indent=deep_get(options, DictPath("indent"), ""),
                                               diffspace=deep_get(options,
                                                                  DictPath("diffspace"), ""))
        processor: tuple[str, Optional[Callable], dict] = ("block", diff_line_scanner, options)
    else:
        if process_block_end:
            if format_block_end:
                remnants = formatters.format_diff_line(message, override_formatting={})
            else:
                severity_name = f"severity_{loglevel_to_name(severity).lower()}"
                remnants = [ThemeStr(message, ThemeAttr("logview", severity_name))]
            processor = ("end_block", None, {})
        else:
            processor = ("end_block_not_processed", None, {})

    return processor, (timestamp, facility, severity, remnants)


# pylint: disable-next=too-many-locals,too-many-branches
def diff_line(message: str, **kwargs: Any) -> tuple[tuple[str, Optional[Callable], dict],
                                                    list[tuple[list[Union[ThemeRef, ThemeStr]],
                                                               LogLevel]]]:
    """
    Parser for unified diffs.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ((str | (str, Callable, dict)), [(ThemeArray, LogLevel)]):
                ((str | (str, Callable, dict))):
                    (str): The unformatted message
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                (ThemeArray): The formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    options: dict = deep_get(kwargs, DictPath("options"), {})

    if options is None:
        options = {}

    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []
    matched = False

    block_start = deep_get(options, DictPath("block_start"), [{
        "matchtype": "regex",
        "matchkey": re.compile(r"^\S+?: \S.*$|^\S+?:$"),
        "matchline": "any",
        "format_block_start": False,
    }])
    line = deep_get(options, DictPath("__line"), 0)
    if deep_get(options, DictPath("eof")) is None:
        options["eof"] = "end_block"

    for _bs in block_start:
        matchtype = _bs["matchtype"]
        matchkey = _bs["matchkey"]
        matchline = _bs["matchline"]
        format_block_start = deep_get(_bs, DictPath("format_block_start"), False)
        if matchline == "any" or matchline == "first" and not line:
            if matchtype == "exact":
                if message == matchkey:
                    matched = True
            elif matchtype == "startswith":
                if message.startswith(matchkey):
                    matched = True
            elif matchtype == "endswith":
                if message.endswith(matchkey):
                    matched = True
            elif matchtype == "regex":
                tmp = matchkey.match(message)
                if tmp is not None:
                    matched = True

    if matched:
        if format_block_start:
            remnants = formatters.format_diff_line(message,
                                                   indent=deep_get(options, DictPath("indent"), ""))
        else:
            severity_name = f"severity_{loglevel_to_name(severity).lower()}"
            remnants = [ThemeStr(message, ThemeAttr("logview", severity_name))]
        processor: tuple[str, Optional[Callable], dict] = \
            ("start_block", diff_line_scanner, options)
        return processor, remnants

    return message, remnants


# pylint: disable-next=too-many-locals,too-many-branches
def ansible_line_scanner(message: str,
                         **kwargs: Any) -> tuple[tuple[str, Optional[Callable], dict],
                                                 tuple[datetime, str, LogLevel,
                                                       list[tuple[list[Union[ThemeRef, ThemeStr]],
                                                                  LogLevel]]]]:
    """
    Scanner for Ansible results.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (((str, Callable, dict),
              (datetime, str, LogLevel, [(ThemeArray, LogLevel)]))):
                ((str, Callable, dict)):
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                ((datetime, str, LogLevel, Callable, dict)):
                    (datetime): The timestamp
                    (str): The facility of the message
                    (LogLevel): The LogLevel of the message
                    ([(ThemeArray, LogLevel)]):
                        (ThemeArray): The formatted strings of the remnant
                        (LogLevel): The severity of the remnant
    """
    options: dict = deep_get(kwargs, DictPath("options"), {})

    timestamp: datetime = none_timestamp()
    facility: str = ""
    severity: LogLevel = LogLevel.INFO
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []
    final_block: bool = deep_get(options, DictPath("final_block"), False)

    message = strip_iso_timestamp(message)

    if not message:
        options["override_formatting"] = {}

    # We're approaching the end
    if final_block and not message:
        processor: tuple[str, Optional[Callable], dict] = ("end_block", None, {})
    else:
        if "final_block" in options:
            tmp = re.match(r"^.+?:\sok=(\d+)\s+"
                           r"changed=(\d+)\s+"
                           r"unreachable=(\d+)\s+"
                           r"failed=(\d+)\s+"
                           r"skipped=(\d+)\s+"
                           r"rescued=(\d+)\s+"
                           r"ignored=(\d+)$", message)
            if tmp is not None:
                ok = int(tmp[1])
                changed = int(tmp[2])
                unreachable = int(tmp[3])
                failed = int(tmp[4])
                skipped = int(tmp[5])
                rescued = int(tmp[6])
                ignored = int(tmp[7])

                # These are sorted in order of severity; "highest" wins
                if ok:
                    options["override_formatting"] = {"__all": ThemeAttr("main", "status_ok")}
                if changed:
                    options["override_formatting"] = {"__all": ThemeAttr("logview", "modified")}
                if skipped:
                    options["override_formatting"] = {"__all": ThemeAttr("logview",
                                                                         "severity_debug")}
                if ignored or rescued:
                    options["override_formatting"] = {"__all": ThemeAttr("logview",
                                                                         "severity_warning")}
                if unreachable or failed:
                    options["override_formatting"] = {"__all": ThemeAttr("logview",
                                                                         "severity_error")}
                    options["override_formatting"] = {"__all": ThemeAttr("logview",
                                                                         "severity_error")}

        if message.startswith("skipping"):
            options["override_formatting"] = {"__all": ThemeAttr("logview", "severity_debug")}
        elif message.startswith("ok"):
            options["override_formatting"] = {"__all": ThemeAttr("main", "status_ok")}
        elif message.startswith("changed"):
            options["override_formatting"] = {"__all": ThemeAttr("logview", "modified")}
        elif message.startswith("fatal"):
            options["override_formatting"] = {"__all": ThemeAttr("logview", "severity_error")}
        override_formatting = deep_get(options, DictPath("override_formatting"))
        remnants = formatters.format_ansible_line(message, override_formatting=override_formatting)
        if message.startswith("PLAY RECAP"):
            options["final_block"] = True
            processor = ("final_block", ansible_line_scanner, options)
        else:
            processor = ("block", ansible_line_scanner, options)

    return processor, (timestamp, facility, severity, remnants)


def ansible_line(message: str,
                 **kwargs: Any) -> tuple[tuple[str, Optional[Callable], dict],
                                         list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    Parser for Ansible results.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ((str | (str, Callable, dict)), [(ThemeArray, LogLevel)]):
                ((str | (str, Callable, dict))):
                    (str): The unformatted message
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                (ThemeArray): The formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    options: dict = deep_get(kwargs, DictPath("options"), {})

    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

    if message.startswith("PLAY [") and message.endswith("***"):
        if severity is None:
            severity = LogLevel.INFO
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        remnants = [ThemeStr(message, ThemeAttr("logview", severity_name))]
        options["eof"] = "end_block"
        processor: tuple[str, Optional[Callable], dict] = \
            ("start_block", ansible_line_scanner, options)
        return processor, remnants

    return message, remnants


# pylint: disable-next=too-many-locals,too-many-branches
def custom_line_scanner(message: str, **kwargs: Any) \
        -> tuple[tuple[str, Optional[Callable], dict],
                 tuple[datetime, str, LogLevel, list[Union[ThemeRef, ThemeStr]]]]:
    """
    Scanner for custom block messages.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (((str, Callable, dict),
              (datetime, str, LogLevel, [(ThemeArray, LogLevel)]))):
                ((str, Callable, dict)):
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                ((datetime, str, LogLevel, Callable, dict)):
                    (datetime): The timestamp
                    (str): The facility of the message
                    (LogLevel): The LogLevel of the message
                    ([(ThemeArray, LogLevel)]):
                        (ThemeArray): The formatted strings of the remnant
                        (LogLevel): The severity of the remnant
    """
    options: dict = deep_get(kwargs, DictPath("options"), {})
    loglevel_name: str = deep_get(options, DictPath("loglevel"), "info")

    timestamp: datetime = none_timestamp()
    facility: str = ""
    severity: LogLevel = LogLevel.INFO
    message, _timestamp = split_iso_timestamp(message, none_timestamp())
    remnants: list[Union[ThemeRef, ThemeStr]] = []
    matched = True

    # If no block end is defined we continue until EOF
    block_end = deep_get(options, DictPath("block_end"), [])

    format_block_end = False
    process_block_end = True

    for _be in block_end:
        matchtype = deep_get(_be, DictPath("matchtype"))
        matchkey = deep_get(_be, DictPath("matchkey"))
        format_block_end = deep_get(_be, DictPath("format_block_end"), False)
        process_block_end = deep_get(_be, DictPath("process_block_end"), True)
        if matchtype == "empty":
            if not message.strip():
                matched = False
        elif matchtype == "exact":
            if message == matchkey:
                matched = False
        elif matchtype == "startswith":
            if message.startswith(matchkey):
                matched = False
        elif matchtype == "regex":
            tmp = matchkey.match(message)
            if tmp is not None:
                matched = False

    if matched:
        remnants = [ThemeStr(message, ThemeAttr("logview", f"severity_{loglevel_name}"))]
        processor: tuple[str, Optional[Callable], dict] = ("block", custom_line_scanner, options)
    else:
        if process_block_end:
            if format_block_end:
                remnants = [ThemeStr(message, ThemeAttr("logview", f"severity_{loglevel_name}"))]
            else:
                severity_name = f"severity_{loglevel_to_name(severity).lower()}"
                remnants = [ThemeStr(message, ThemeAttr("logview", severity_name))]
            processor = ("end_block", None, {})
        else:
            processor = ("end_block_not_processed", None, {})

    return processor, (timestamp, facility, severity, remnants)


# pylint: disable-next=too-many-locals,too-many-branches
def custom_line(message: str, **kwargs: Any) -> tuple[tuple[str, Optional[Callable], dict],
                                                      list[tuple[list[Union[ThemeRef, ThemeStr]],
                                                                 LogLevel]]]:
    """
    Parser for custom block messages.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            ((str | (str, Callable, dict)), [(ThemeArray, LogLevel)]):
                ((str | (str, Callable, dict))):
                    (str): The unformatted message
                    (str, Callable, dict):
                        (str): Command to the block parser
                        (Callable): The block parser to use
                        (dict): Arguments to the block parser
                (ThemeArray): The formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.INFO)
    options: dict = deep_get(kwargs, DictPath("options"), {})

    block_start: list[dict] = deep_get(options, DictPath("block_start"), [])
    loglevel_name: str = deep_get(options, DictPath("loglevel"), "info")

    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []
    matched = False

    line = deep_get(options, DictPath("__line"), 0)
    if deep_get(options, DictPath("eof")) is None:
        options["eof"] = "end_block"

    for _bs in block_start:
        matchtype = _bs["matchtype"]
        matchkey = _bs["matchkey"]
        matchline = _bs["matchline"]
        format_block_start = deep_get(_bs, DictPath("format_block_start"), False)
        if matchline == "any" or matchline == "first" and not line:
            if matchtype == "exact":
                if message == matchkey:
                    matched = True
            elif matchtype == "startswith":
                if message.startswith(matchkey):
                    matched = True
            elif matchtype == "endswith":
                if message.endswith(matchkey):
                    matched = True
            elif matchtype == "regex":
                tmp = matchkey.match(message)
                if tmp is not None:
                    matched = True

    if matched:
        if format_block_start:
            remnants = [ThemeStr(message, ThemeAttr("logview", f"severity_{loglevel_name}"))]
        else:
            severity_name = f"severity_{loglevel_to_name(severity).lower()}"
            remnants = [ThemeStr(message, ThemeAttr("logview", severity_name))]
        processor: tuple[str, Optional[Callable], dict] = \
            ("start_block", custom_line_scanner, options)
        return processor, remnants

    return message, remnants


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def custom_splitter(message: str, **kwargs: Any) -> \
        tuple[Union[str, list[Union[ThemeRef, ThemeStr]]], LogLevel, str]:
    """
    Custom splitter.

        Parameters:
            message (str): The message to format
            **kwargs (dict[str, Any]): Keyword arguments
                severity (LogLevel): The log severity
                facility (str): The log facility
                options (dict[str, Any]): splitter options
                    regex (re.Pattern[str]): A compiled regex
                    severity (dict[str, Any]): A dict of severity options
                        field (str): The index of the field to get the severity from
                        transform (str): The rule to use when transforming the severity value;
                                         valid options:
                                         letter, 3letter, 4letter, str, int
                        overrides (list): Special cases for overriding the severity
                    facility (dict[str, Any]): A dict of facility options
                        fields ([int]): A list of indexes for the fields containing the facility
                        separators ([str]): A list of separators to use when joining the facility
                    message (dict[str, Any]): A dict of message options
                        field (str): The index of the field to get the message from
        Returns:
            (str|ThemeArray, LogLevel, str, [(ThemeArray, LogLevel)]):
                (str|ThemeArray): The untouched or formatted message
                (LogLevel): The LogLevel of the message
                (str): The facility of the message
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    severity: LogLevel = deep_get(kwargs, DictPath("severity"), LogLevel.DEFAULT)
    facility: str = deep_get(kwargs, DictPath("facility"), "")
    options: dict = deep_get(kwargs, DictPath("options"), {})

    compiled_regex: re.Pattern[str] = deep_get(options, DictPath("regex"))
    severity_field = deep_get(options, DictPath("severity#field"))
    severity_transform = deep_get(options, DictPath("severity#transform"))
    severity_overrides = deep_get(options, DictPath("severity#overrides"), [])
    facility_fields = \
        deep_get_with_fallback(options, [DictPath("facility#fields"), DictPath("facility#field")])
    facility_separators = \
        deep_get_with_fallback(options, [DictPath("facility#separators"),
                                         DictPath("facility#separator")], "")
    message_field = deep_get(options, DictPath("message#field"))

    # This message is already formatted
    if isinstance(message, list):
        return message, severity, facility

    # The bare minimum for these rules is
    if compiled_regex is None or message_field is None:
        raise ValueError("parser rule is missing regex or message field")

    tmp = compiled_regex.match(message)

    if tmp is not None:
        group_count = len(tmp.groups())
        if message_field > group_count:
            sys.exit(f"The parser rule references a non-existing capture group {message_field} "
                     f"for message; the valid range is [1-{group_count}]")
        if severity_field is not None and severity_transform is not None:
            if severity_field > group_count:
                sys.exit("The parser rule references a non-existing capture group "
                         f"{severity_field} for severity; the valid range is [1-{group_count}]")
            if severity_transform == "letter":
                severity = letter_to_severity(tmp[severity_field], default=severity)
            elif severity_transform == "3letter":
                severity = str_3letter_to_severity(tmp[severity_field], default=severity)
            elif severity_transform == "4letter":
                severity = str_4letter_to_severity(tmp[severity_field], default=severity)
            elif severity_transform == "str":
                severity = str_to_severity(tmp[severity_field], default=severity)
            elif severity_transform == "int":
                severity = cast(LogLevel, int(tmp[severity_field]))
            else:
                sys.exit(f"Unknown severity transform rule {severity_transform}; aborting.")
            message, severity = \
                custom_override_severity(tmp[message_field], severity,
                                         overrides={
                                             "options": {
                                                 "overrides": severity_overrides,
                                             }})
        else:
            message = tmp[message_field]
        if facility_fields is not None and not facility:
            if isinstance(facility_fields, str):
                facility_fields = [facility_fields]
            if isinstance(facility_separators, str):
                facility_separators = [facility_separators]
            i = 0
            facility = ""
            for field in facility_fields:
                if field > group_count:
                    sys.exit(f"The parser rule references a non-existing capture group {field} "
                             f"for facility; the valid range is [1-{group_count}]")
                if i:
                    facility += facility_separators[min(i - 1, len(facility_separators) - 1)]
                if field != 0:
                    facility += tmp[field]
                i += 1

    return message, severity, facility


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def parsing_multiplexer(message: str, filters: list[Union[str, tuple]], **kwargs: Any) \
        -> tuple[str, LogLevel,
                 Union[list[Union[ThemeRef, ThemeStr]], tuple[str, Optional[Callable], dict]],
                 list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    The main loop for the parser; it will iterate loop through all rules specified for
    a particular log until a line has been fully processed.

        Parameters:
            message (str): The message to format
            filters ([str | (str, Any)]): The list of parser rules to apply (and options)
            **kwargs (dict[str, Any]): Keyword arguments
                fold_msg (bool): Should the message be expanded or folded?
                options (dict[str, Any]): Options to pass to the block parsers
        Returns:
            (str, LogLevel, [(ThemeArray, LogLevel)] | (str, Callable, dict[str, Any]),
             [([ThemeArray], LogLevel)]):
                (str): The log facility
                (LogLevel): The log severity
                (ThemeArray | (str, Callable, dict[str, Any])):
                    Either the formatted message or the block parser tuple
                ([(ThemeArray, LogLevel)]):
                    (ThemeArray): The formatted strings of the remnant
                    (LogLevel): The severity of the remnant
    """
    fold_msg: bool = deep_get(kwargs, DictPath("fold_msg"), True)
    options: dict = deep_get(kwargs, DictPath("options"), {})

    facility: str = ""
    severity: LogLevel = LogLevel.DEFAULT
    remnants: list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]] = []

    # pylint: disable-next=too-many-nested-blocks
    for _filter, filter_options in filters:
        try:
            filter_options = {**filter_options, **options}
        except TypeError:
            sys.exit(f"{_filter=}\n{filter_options=}")
        # These parsers CANNOT handle ThemeArrays
        if isinstance(message, str):
            # Multiparsers
            if _filter == "glog":
                message, severity, facility, remnants, _match = \
                    split_glog(message, severity=severity, facility=facility)
            elif _filter == "spaced_severity_facility":
                message, severity, facility = \
                    __split_severity_facility_style(message,
                                                    severity=severity, facility=facility)
            elif _filter == "directory":
                facility, severity, message, remnants = \
                    directory(message, fold_msg=fold_msg, severity=severity, facility=facility)
            elif _filter == "seconds_severity_facility":
                facility, severity, message, remnants = \
                    seconds_severity_facility(message, fold_msg=fold_msg)
            elif _filter == "expand_event":
                if message.startswith(("Event(v1.ObjectReference{")):
                    severity, message, remnants = \
                        expand_event(message, severity=severity,
                                     remnants=remnants, fold_msg=fold_msg)
                elif message.startswith(("&Event{ObjectMeta:")):
                    severity, message, remnants = \
                        expand_event_objectmeta(message, severity=severity,
                                                remnants=remnants, fold_msg=fold_msg)
            elif _filter == "modinfo":
                facility, severity, message, remnants = modinfo(message, fold_msg=fold_msg)
            elif _filter == "sysctl":
                facility, severity, message, remnants = \
                    sysctl(message, severity=severity, facility=facility, fold_msg=fold_msg)
            elif _filter == "bracketed_timestamp_severity_facility":
                message, severity, facility = \
                    split_bracketed_timestamp_severity_facility(message, default=filter_options)
            elif _filter == "custom_splitter":
                message, severity, facility = \
                    custom_splitter(message, severity=severity, facility=facility,
                                    fold_msg=fold_msg, options=filter_options)
            elif _filter == "http":
                message, severity, facility = \
                    http(message, severity=severity, facility=facility,
                         fold_msg=fold_msg, options=filter_options)
            elif _filter == "iptables":
                message, severity, facility, remnants = \
                    iptables(message, remnants, severity=severity,
                             facility=facility, fold_msg=fold_msg)
            elif _filter == "json" and isinstance(message, str):
                _message = message
                if message.startswith(("{\"", "{ \"")):
                    message, severity, facility, remnants = \
                        split_json_style(message, severity=severity, facility=facility,
                                         fold_msg=fold_msg, options=filter_options)
            elif _filter == "json_with_leading_message" and isinstance(message, str):
                parts = message.split("{", 1)
                if len(parts) == 2:
                    # No leading message
                    if not parts[0]:
                        message, severity, facility, remnants = \
                            split_json_style(message, severity=severity, facility=facility,
                                             fold_msg=fold_msg, options=filter_options)
                    elif parts[0].rstrip() != parts[0]:
                        parts[0] = parts[0].rstrip()
                        # It isn't leading message + JSON unless there's whitespace in-between
                        _message, severity, facility, remnants = \
                            split_json_style("{" + parts[1], severity=severity,
                                             facility=facility, fold_msg=fold_msg,
                                             options=filter_options)
                        if (_severity := severity) is None:
                            _severity = LogLevel.INFO
                        _message, remnants = \
                            merge_message(_message, remnants=remnants, severity=_severity)
                        severity_name = f"severity_{loglevel_to_name(_severity).lower()}"
                        message = [ThemeStr(parts[0], ThemeAttr("logview", severity_name))]
            elif _filter == "json_event":
                # We do not extract the facility/severity from folded messages,
                # so just skip if fold_msg == True.
                if message.startswith("EVENT ") and not fold_msg:
                    message, severity, facility, remnants = \
                        json_event(message, fold_msg=fold_msg, options=filter_options)
            elif _filter == "key_value":
                if "=" in message:
                    facility, severity, message, remnants = \
                        key_value(message, fold_msg=fold_msg, severity=severity,
                                  facility=facility, options=filter_options)
            elif _filter == "key_value_with_leading_message":
                if "=" in message:
                    facility, severity, message, remnants = \
                        key_value_with_leading_message(message, fold_msg=fold_msg,
                                                       severity=severity, facility=facility,
                                                       options=filter_options)
            # Timestamp formats
            elif _filter == "ts_8601":  # Anything that resembles ISO-8601 / RFC 3339
                message = strip_iso_timestamp(message)
            # Facility formats
            elif _filter == "colon_facility":
                message, facility = split_colon_facility(message, facility)
            elif _filter == "angle_bracketed_facility":
                message, facility = split_angle_bracketed_facility(message, facility)
            # Severity formats
            elif _filter == "colon_severity":
                message, severity = split_colon_severity(message, default=severity)
            elif _filter == "bracketed_severity":
                message, severity = split_bracketed_severity(message, default=filter_options)
            # Filters
            elif _filter == "substitute_bullets":
                message = substitute_bullets(message, options=filter_options)
            elif _filter == "strip_ansicodes":
                message = strip_ansicodes(message)
            # Block starters
            elif _filter == "python_traceback":
                message, remnants = python_traceback(message, fold_msg=fold_msg)
            # Block starters; these are treated as parser loop terminators if a match is found
            elif _filter == "json_line":
                message, remnants = \
                    json_line(message, fold_msg=fold_msg, severity=severity,
                              options=filter_options)
            elif _filter == "yaml_line":
                message, remnants = \
                    yaml_line(message, fold_msg=fold_msg, severity=severity,
                              options=filter_options)
            elif _filter == "diff_line":
                message, remnants = \
                    diff_line(message, fold_msg=fold_msg, severity=severity,
                              options=filter_options)
            elif _filter == "ansible_line":
                message, remnants = \
                    ansible_line(message, fold_msg=fold_msg, severity=severity,
                                 options=filter_options)
            elif _filter == "custom_line":
                message, remnants = \
                    custom_line(message, fold_msg=fold_msg, severity=severity,
                                options=filter_options)
            elif _filter == "tab_separated":
                message, severity, facility, remnants = \
                    tab_separated(message, severity=severity, facility=facility,
                                  fold_msg=fold_msg, options=filter_options)
        # These parsers CAN handle ThemeArrays
        # Severity formats
        if _filter == "override_severity":
            message, severity = custom_override_severity(message, severity, options=filter_options)

        if isinstance(message, tuple) and message[0] == "start_block":
            break

    if severity == LogLevel.DEFAULT:
        severity = LogLevel.INFO

    # As a step towards always using ThemeStr, convert all regular strings
    if isinstance(message, str):
        rmessage = [ThemeStr(message,
                             ThemeAttr("logview",
                                       f"severity_{loglevel_to_name(severity).lower()}"))]
    else:
        rmessage = message

    return facility, severity, rmessage, remnants


Parser = namedtuple("Parser", "name show_in_selector match rules")
parsers = []


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def init_parser_list() -> None:
    """
    Initialise the list of parsers.
    """
    # This pylint warning seems incorrect--does it not handle namedtuple.append()?
    # pylint: disable-next=global-variable-not-assigned
    global parsers

    # Get a full list of parsers from all parser directories
    # Start by adding files from the parsers directory

    parser_dirs = []
    parser_dirs += deep_get(cmtlib.cmtconfig, DictPath("Pod#local_parsers"), [])
    parser_dirs.append(PARSER_DIR)
    parser_dirs.append(SYSTEM_PARSERS_DIR)

    parser_files = []

    for parser_dir in parser_dirs:
        if parser_dir.startswith("{HOME}"):
            parser_dir = parser_dir.replace("{HOME}", HOMEDIR, 1)

        if not Path(parser_dir).is_dir():
            continue

        parser_dir = FilePath(parser_dir)

        if Path(parser_dir).joinpath("BUNDLE.yaml").is_file():
            path = FilePath(parser_dir).joinpath("BUNDLE.yaml")
            parser_files.append(path)
            continue

        for ppath in cast(list[Path], natsorted(Path(parser_dir).iterdir())):
            filename = ppath.name

            if filename.startswith(("~", ".")) or not filename.endswith((".yaml", ".yml")):
                continue

            parser_files.append(FilePath(ppath))

    # pylint: disable-next=too-many-nested-blocks
    for parser_file in parser_files:
        if parser_file.endswith("BUNDLE.yaml"):
            temp_dl = secure_read_yaml_all(parser_file, directory_is_symlink=True)
            try:
                dl = [list(d) for d in temp_dl]
            except (ruyaml.composer.ComposerError,
                    ruyaml.parser.ParserError,
                    ruyaml.scanner.ScannerError):
                sys.exit(f"{parser_file} is not valid YAML; aborting.")
            LogparserConfiguration.using_bundles = True
        else:
            try:
                d = list(secure_read_yaml(parser_file, directory_is_symlink=True))
            except (ruyaml.composer.ComposerError,
                    ruyaml.parser.ParserError,
                    ruyaml.scanner.ScannerError,
                    TypeError):
                sys.exit(f"{parser_file} is not valid YAML; aborting.")
            dl = [d]

        for parser_dict in dl:
            for parser in parser_dict:
                parser_name = parser.get("name", "")
                if not parser_name:
                    continue
                show_in_selector = parser.get("show_in_selector", False)
                matchrules = []
                for matchkey in parser.get("matchkeys"):
                    pod_name = matchkey.get("pod_name", "")
                    container_name = matchkey.get("container_name", "")
                    image_name = matchkey.get("image_name", "")
                    image_regex_raw = matchkey.get("image_regex", "")
                    if image_regex_raw:
                        image_regex = re.compile(image_regex_raw)
                    else:
                        image_regex = None
                    container_type = matchkey.get("container_type", "container")
                    # We need at least one way of matching
                    if not pod_name and not container_name and not image_name:
                        continue
                    matchrule = (pod_name, container_name, image_name, container_type, image_regex)
                    matchrules.append(matchrule)

                if not matchrules:
                    continue

                parser_rules = parser.get("parser_rules")
                if parser_rules is None or not parser_rules:
                    continue

                rules = []
                for rule in parser_rules:
                    rule_name = rule.get("name")
                    if rule_name in ("angle_bracketed_facility",
                                     "ansible_line",
                                     "bracketed_severity",
                                     "bracketed_timestamp_severity_facility",
                                     "colon_facility",
                                     "colon_severity",
                                     "custom_line",
                                     "custom_splitter",
                                     "diff_line",
                                     "directory",
                                     "expand_event",
                                     "glog",
                                     "http",
                                     "iptables",
                                     "json",
                                     "json_event",
                                     "json_line",
                                     "json_with_leading_message",
                                     "key_value",
                                     "key_value_with_leading_message",
                                     "modinfo",
                                     "python_traceback",
                                     "seconds_severity_facility",
                                     "spaced_severity_facility",
                                     "substitute_bullets",
                                     "strip_ansicodes",
                                     "sysctl",
                                     "tab_separated",
                                     "ts_8601",
                                     "yaml_line"):
                        options = {}
                        for key, value in deep_get(rule, DictPath("options"), {}).items():
                            if key in ("block_start", "block_end"):
                                tmp = []
                                for entry in value:
                                    if deep_get(entry, DictPath("matchtype"), "") == "regex":
                                        regex = deep_get(entry, DictPath("matchkey"), "")
                                        if regex is not None:
                                            compiled_regex = re.compile(regex)
                                            entry["matchkey"] = compiled_regex
                                    tmp.append(entry)
                            elif key == "regex":
                                regex = deep_get(rule, DictPath("options#regex"), "")
                                value = re.compile(regex)
                            elif key == "default_loglevel":
                                try:
                                    value = name_to_loglevel(value)
                                except ValueError:
                                    sys.exit(f"Parser {parser_file} contains an invalid loglevel "
                                             f"{value}; aborting.")
                            options[key] = value
                        rules.append((rule_name, options))
                    elif rule_name == "override_severity":
                        overrides = []
                        for override in deep_get(rule, DictPath("overrides"), []):
                            matchtype = deep_get(override, DictPath("matchtype"))
                            matchkey = deep_get(override, DictPath("matchkey"))
                            _loglevel = deep_get(override, DictPath("loglevel"))

                            if matchtype is None or matchkey is None or _loglevel is None:
                                raise ValueError("Incorrect override rule in Parser "
                                                 f"{parser_file}; every override must define "
                                                 "matchtype, matchkey, and loglevel")

                            if matchtype == "regex":
                                regex = deep_get(override, DictPath("matchkey"), "")
                                matchkey = re.compile(regex)
                            overrides.append({
                                "matchtype": matchtype,
                                "matchkey": matchkey,
                                "loglevel": _loglevel,
                            })
                        rules.append((rule_name, {"overrides": overrides}))
                    else:
                        sys.exit(f"Parser {parser_file} has an unknown rule-type "
                                 f"{rule}; aborting.")

                parsers.append(Parser(name=parser_name, show_in_selector=show_in_selector,
                                      match=matchrules, rules=rules))

    # Fallback entries
    parsers.append(Parser(name="basic_8601_raw", show_in_selector=True,
                          match=[("raw", "", "", "container", None)], rules=[]))
    # This should always be last
    parsers.append(Parser(name="basic_8601", show_in_selector=True,
                          match=[("raw", "", "", "container", None)], rules=[("ts_8601", {})]))


def get_parser_list() -> set[Parser]:
    """
    Return a set with the parsers that should be visible in the override menu.

        Returns:
            (set(Parser)): A set of parsers
    """
    parsers_ = set()
    for parser in parsers:
        if not parser.show_in_selector:
            continue
        parsers_.add(parser.name)

    return parsers_


# pylint: disable-next=too-many-locals
def logparser_initialised(**kwargs: Any) \
        -> tuple[datetime, str, LogLevel,
                 Union[list[Union[ThemeRef, ThemeStr]], tuple[str, Optional[Callable], dict]],
                 list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]]]:
    """
    This is used when the parser is already initialised.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                parser (Parser): The parser to use
                message (str): A line to parse
                fold_msg (bool): Should the message be folded (unmodified)
                                 or unfolded (expanded to multiple lines where possible)
                line (int): The line number
        Returns:
            (datetime, str, LogLevel, str, [(ThemeArray, LogLevel)]):
                (datetime): A timestamp
                (str): The log facility
                (LogLevel): Loglevel
                (rstr): An unformatted string
                ([(ThemeArray, LogLevel)]): Formatted remainders with severity
    """
    parser: Optional[Parser] = deep_get(kwargs, DictPath("parser"))
    message: str = deep_get(kwargs, DictPath("message"), "")
    fold_msg: bool = deep_get(kwargs, DictPath("fold_msg"), True)
    line: int = deep_get(kwargs, DictPath("line"), 0)
    # First extract the Kubernetes timestamp
    message, timestamp = split_iso_timestamp(message, none_timestamp())

    if parser is None:
        raise ValueError("logparser_initialised() called with parser == None")

    options = {
        "__line": line,
    }
    facility, severity, rmessage, remnants = \
        parsing_multiplexer(message, filters=parser.rules, fold_msg=fold_msg, options=options)

    max_untruncated_len = 16384
    if isinstance(rmessage, list) and themearray_len(rmessage) > max_untruncated_len - 1:
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        remnants = [([ThemeStr(message[0:max_untruncated_len - 1],
                               ThemeAttr("logview", severity_name))], severity)]
        severity = LogLevel.ERR
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        rmessage = [ThemeStr(f"Line too long ({len(message)} bytes); "
                             f"truncated to {max_untruncated_len} bytes "
                             "(Use line wrapping to see the entire message)",
                             ThemeAttr("logview", severity_name))]

    if rmessage is None:
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        rmessage = [ThemeStr(message, ThemeAttr("logview", severity_name))]
        errmsg = [
            [("Message ", "default"),
             (f"{message}", "argument"),
             ("not parsed; converting.", "default")],
        ]
        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(errmsg)
        cmtlog.log(LogLevel.NOTICE, msg=unformatted_msg, messages=formatted_msg)
    elif isinstance(rmessage, str):
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        rmessage = [ThemeStr(rmessage, ThemeAttr("logview", severity_name))]
        errmsg = [
            [("Unexpected format for message: ", "default"),
             (f"{rmessage}", "argument"),
             (" (expected one of [ThemeStr] or tuple(block); converting.", "default")],
        ]
        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(errmsg)
        cmtlog.log(LogLevel.WARNING, msg=unformatted_msg, messages=formatted_msg)
    if not (isinstance(rmessage, list) and len(rmessage) and isinstance(rmessage[0], ThemeStr)
            or isinstance(rmessage, tuple)):
        errmsg = [
            [("Unexpected format for rmessage: ", "default"),
             (f"{rmessage}", "argument"),
             (" (expected one of [ThemeStr] or tuple(block).", "default")],
        ]
        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(errmsg)
        cmtlog.log(LogLevel.WARNING, msg=unformatted_msg, messages=formatted_msg)

    return timestamp, facility, severity, rmessage, remnants


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def logparser(pod_name: str, container_name: str, image_name: str, message: str, **kwargs: Any) \
        -> tuple[datetime, str, LogLevel,
                 Union[list[Union[ThemeRef, ThemeStr]], tuple[str, Optional[Callable], dict]],
                 list[tuple[list[Union[ThemeRef, ThemeStr]], LogLevel]],
                 tuple[Optional[str], str], Parser]:
    """
    This (re-)initialises the parser; it will identify what parser rules to use
    helped by pod_name, container_name, and image_name;
    this allows for different containers in the same pod to use different parsers,
    and different versions of a pod to use different parsers

        Parameters:
            pod_name (str): The name of the pod
            container_name (str): The name of the container
            image_name (str): The name of the image
            message (str): A line to parse
            **kwargs (dict[str, Any]): Keyword arguments
                fold_msg (bool): Should the message be folded (unmodified)
                                 or unfolded (expanded to multiple lines where possible)
                override_parser (opaque): A reference to the parser rules
                                          to use instead of the autodetected parser
                container_type (str): container or init_container
                line (int): The line number
        Returns:
            (datetime, str, LogLevel,
             ThemeArray | (str, Callable, dict),
             [(ThemeArray, LogLevel)], (str, str), Parser):
                (datetime): A timestamp
                (str): The log facility
                (LogLevel): Loglevel
                (ThemeArray): A ThemeArray, or a scanner
                ([tuple[ThemeArray, LogLevel]]): Formatted remainders with severity
                ((str, str)):
                    (str): Subidentifiers to help explain
                           what rules in the parser file are used
                    (str): Name of the parser file used
                (Parser): A reference to the parser rules that are used
    """
    fold_msg: bool = deep_get(kwargs, DictPath("fold_msg"), True)
    override_parser: Optional[Parser] = deep_get(kwargs, DictPath("override_parser"))
    container_type: str = deep_get(kwargs, DictPath("container_type"), "container")
    line: int = deep_get(kwargs, DictPath("line"), 0)
    facility: str = ""

    # First extract the Kubernetes timestamp
    message, timestamp = split_iso_timestamp(message, none_timestamp())

    if not parsers:
        init_parser_list()

    rmessage = None

    if override_parser is not None:
        # Any other timestamps (as found in the logs) are ignored
        parser = None
        severity = LogLevel.INFO
        remnants = None
        for parser in parsers:
            if parser.name == override_parser:
                options = {
                    "__line": line,
                }
                facility, severity, rmessage, remnants = \
                    parsing_multiplexer(message, filters=parser.rules,
                                        fold_msg=fold_msg, options=options)
        # As a step towards always using ThemeStr, convert all regular strings
        if rmessage is None:
            severity_name = f"severity_{loglevel_to_name(severity).lower()}"
            rmessage = [ThemeStr(message, ThemeAttr("logview", severity_name))]
        elif isinstance(rmessage, str):
            severity_name = f"severity_{loglevel_to_name(severity).lower()}"
            rmessage = [ThemeStr(rmessage, ThemeAttr("logview", severity_name))]
        return (timestamp, facility, severity,
                rmessage, remnants, ("<override>", str(override_parser)), parser)

    image_name = image_name.removeprefix("docker-pullable://")

    for parser in parsers:
        uparser = None
        lparser = None

        for pod_prefix, container_prefix, image_prefix, \
                _container_type, image_regex in parser.match:
            _image_name = image_name
            if image_prefix.startswith("/"):
                tmp = image_name.split("/", 1)
                if len(tmp) == 2:
                    _image_name = f"/{tmp[1]}"

            if image_regex is None:
                regex_match = True
            else:
                tmp = image_regex.match(_image_name)
                regex_match = tmp is not None

            if pod_name.startswith(pod_prefix) \
                    and container_name.startswith(container_prefix) \
                    and _image_name.startswith(image_prefix) \
                    and container_type == _container_type and regex_match:
                uparser = parser.name
                options = {
                    "__line": line,
                }
                facility, severity, rmessage, remnants = \
                    parsing_multiplexer(message, filters=parser.rules,
                                        fold_msg=fold_msg, options=options)

                _lparser = []
                if pod_prefix:
                    _lparser.append(pod_prefix)
                if container_prefix:
                    _lparser.append(container_prefix)
                if image_prefix:
                    _lparser.append(image_prefix)
                lparser = "|".join(_lparser)
                break

        if lparser is not None:
            break

    if uparser is None and (lparser is None or not lparser):
        lparser = "<unknown format>"
        uparser = "basic_8601"
        parser = Parser(name="basic_8601", show_in_selector=True,
                        match=[("raw", "", "", "container", None)], rules=[("ts_8601", {})])
        facility, severity, rmessage, remnants = \
            parsing_multiplexer(message, filters=parser.rules, fold_msg=fold_msg, options={})

    severity_name = f"severity_{loglevel_to_name(severity).lower()}"
    if rmessage is None:
        rmessage = [ThemeStr(message, ThemeAttr("logview", severity_name))]

    max_untruncated_len = 16384
    if isinstance(rmessage, list) and themearray_len(rmessage) > max_untruncated_len - 1:
        remnants = [([ThemeStr(message[0:max_untruncated_len - 1],
                               ThemeAttr("logview", severity_name))], severity)]
        severity = LogLevel.ERR
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        rmessage = [ThemeStr(f"Line too long ({len(message)} bytes); "
                             f"truncated to {max_untruncated_len} bytes "
                             "(Use line wrapping to see the entire message)",
                             ThemeAttr("logview", severity_name))]

    if rmessage is None:
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        rmessage = [ThemeStr(message, ThemeAttr("logview", severity_name))]
        errmsg = [
            [("Message ", "default"),
             (f"{message}", "argument"),
             ("not parsed; converting.", "default")],
        ]
        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(errmsg)
        cmtlog.log(LogLevel.NOTICE, msg=unformatted_msg, messages=formatted_msg)
    elif isinstance(rmessage, str):
        severity_name = f"severity_{loglevel_to_name(severity).lower()}"
        rmessage = [ThemeStr(rmessage, ThemeAttr("logview", severity_name))]
        errmsg = [
            [("Unexpected format for message: ", "default"),
             (f"{rmessage}", "argument"),
             (" (expected one of [ThemeStr] or tuple(block); converting.", "default")],
        ]
        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(errmsg)
        cmtlog.log(LogLevel.WARNING, msg=unformatted_msg, messages=formatted_msg)
    if not (isinstance(rmessage, list) and len(rmessage) and isinstance(rmessage[0], ThemeStr)
            or isinstance(rmessage, tuple)):
        errmsg = [
            [("Unexpected format for rmessage: ", "default"),
             (f"{rmessage}", "argument"),
             (" (expected one of [ThemeStr] or tuple(block).", "default")],
        ]
        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(errmsg)
        cmtlog.log(LogLevel.WARNING, msg=unformatted_msg, messages=formatted_msg)

    return timestamp, facility, severity, rmessage, remnants, (lparser, uparser), parser
