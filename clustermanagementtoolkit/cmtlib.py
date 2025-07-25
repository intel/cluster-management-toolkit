#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Helpers used by various components of CMT.
"""

# pylint: disable=too-many-lines

import base64
import binascii
from datetime import datetime, timezone, timedelta, date
import errno
from pathlib import Path, PurePath
import re
import sys
from typing import Any, cast, Optional, Union
from collections.abc import Generator

from clustermanagementtoolkit.ansithemeprint import ANSIThemeStr, ansithemeprint

from clustermanagementtoolkit import cmtlog

from clustermanagementtoolkit.cmttypes import deep_get, deep_get_with_fallback, DictPath
from clustermanagementtoolkit.cmttypes import SecurityChecks, SecurityPolicy, SecurityStatus
from clustermanagementtoolkit.cmttypes import FilePath, ProgrammingError, LogLevel

from clustermanagementtoolkit import cmtpaths

from clustermanagementtoolkit import cmtio


cmtconfig: dict[str, Any] = {}


def decode_value(value: Union[str, bytes]) -> tuple[str, Union[str, bytes]]:
    """
    Given a value attempt to decode it from base64.

        Parameters:
            value (str|bytes): The value to decode
        Returns:
            (str, str|bytes):
                (str): The identified type
                (str|bytes): The decoded value
    """
    # Is this base64?
    try:
        decoded = base64.b64decode(value)
        vtype = "base64"
    except binascii.Error:
        vtype = "string"

    if vtype == "base64":
        try:
            tmp = decoded.decode("utf-8")
            if "\n" in tmp:
                vtype = "base64-utf-8"
            else:
                vtype = "string"
                value = tmp
        except UnicodeDecodeError:
            vtype = "base64-binary"

            try:
                if len(decoded) >= 2 and decoded[0:2] == [0x1f, 0x8b]:
                    vtype = "gzip"
                    value = decoded
                elif len(decoded) >= 6 and decoded[0:6] == [0xfd, 0x37, 0x7a, 0x58, 0x5a, 0x0]:
                    vtype = "xz"
                    value = decoded
                elif len(decoded) >= 3 and decoded[0:3] == [0x42, 0x5a, 0x68]:
                    vtype = "bz2"
                    value = decoded
                elif len(decoded) >= 3 and decoded[0:3] == [0x51, 0x46, 0x49]:
                    vtype = "qcow"
                    value = decoded
            except binascii.Error:
                pass
    return vtype, value


def substitute_string(string: str, substitutions: dict) -> str:
    """
    Substitutes substrings in a string.

        Parameters:
            string (str): The string to perform substitutions on
            substitutions (dict): A dict where key is the substring to match against,
                                  and value is the replacement for that substring
        Returns:
            (str): The string with substitutions performed
    """
    for key, value in substitutions.items():
        if string is None or value is None:
            continue
        string = string.replace(key, value)
    return string


def substitute_list(strlist: list[str], substitutions: dict) -> list[str]:
    """
    Substitutes substrings in all strings in a list.

        Parameters:
            string ([str]): A list with the strings to perform substitutions on
            substitutions (dict): A dict where key is the substring to match against,
                                  and value is the replacement for that substring
        Returns:
            ([str]): The list of strings with substitutions performed
    """
    if strlist is not None:
        for key, value in substitutions.items():
            strlist = [s.replace(key, value)
                       if (s is not None and value is not None)
                       else s for s in strlist]
    return strlist


def lstrip_count(string: str, prefix: str) -> tuple[str, int]:
    """
    Given a string remove prefix
    and return the stripped string and the count of stripped characters.

        Parameters:
            string (str): The string to strip
            prefix (str): The prefix to strip
        Returns:
            ((str, int)): The stripped string and the count of stripped characters
    """
    stripped = string.lstrip(prefix)
    return stripped, len(string) - len(stripped)


def rstrip_count(string: str, suffix: str) -> tuple[str, int]:
    """
    Given a string remove suffix and return the stripped string
    and the count of stripped characters.

        Parameters:
            string (str): The string to strip
            suffix (str): The suffix to strip
        Returns:
            ((str, int)): The stripped string and the count of stripped characters
    """

    stripped = string.rstrip(suffix)
    return stripped, len(string) - len(stripped)


def chunk_list(items: list[Any], chunksize: int) -> Generator[list, None, None]:
    """
    Split a list into sublists, each up to chunksize elements long.

        Parameters:
            items ([Any]): The list to split
            chunksize (int): The chunksize
        Returns:
            ([Any]): A generator for the chunked list
        Raises:
            TypeError: items is not a list or chunksize is not an integer
            ValueError: chunksize is < 1
    """
    if not isinstance(items, list):
        raise TypeError("items must be a list")
    if not isinstance(chunksize, int):
        raise TypeError("chunksize must by an integer > 0")
    if chunksize < 1:
        raise ValueError(f"Invalid chunksize {chunksize}; chunksize must be > 0")
    for i in range(0, len(items), chunksize):
        yield items[i:i + chunksize]


def clamp(value: Union[int, float],
          minval: Union[int, float], maxval: Union[int, float]) -> Union[int, float]:
    """
    Clamp value inside the range minval, maxval.

        Parameters:
            value (int | float): The value to clamp
            minval (int | float): The minimum allowed value
            maxval (int | float): The maximum allowed value
        Returns:
            (int | float): The clamped value
    """
    if not isinstance(value, (int, float)):
        raise TypeError("value must be an integer or float")
    if not isinstance(minval, (int, float)) or not isinstance(maxval, (int, float)):
        raise TypeError("maxval and minval must be integers or floats")
    if minval > maxval:
        raise ValueError(f"maxval ({maxval}) must be >= minval ({minval})")
    return min(maxval, max(minval, value))


def none_timestamp() -> datetime:
    """
    Return the timestamp used to represent None.

        Returns:
            timestamp (datetime): A "None" timestamp
    """
    return (datetime.combine(date.min, datetime.min.time()) + timedelta(days=1)).astimezone()


def normalise_cpu_usage_to_millicores(cpu_usage: str) -> float:
    """
    Given CPU usage information, convert it to CPU usage in millicores.

        Parameters:
            cpu_usage(union(int, str)): The CPU usage
        Returns:
            (float): CPU usage in millicores
    """
    cpu_usage_millicores: float = 0

    if not isinstance(cpu_usage, str):
        raise TypeError("cpu_usage must be a str")

    if cpu_usage.isnumeric():
        cpu_usage_millicores = int(cpu_usage) * 1000 ** 1
    elif cpu_usage.endswith("k"):
        cpu_usage_millicores = int(cpu_usage[0:-1]) * 1000 ** 1
    elif cpu_usage.endswith("m"):
        cpu_usage_millicores = int(cpu_usage[0:-1])
    elif cpu_usage.endswith("u"):
        cpu_usage_millicores = int(cpu_usage[0:-1]) / 1000 ** 1
    elif cpu_usage.endswith("n"):
        cpu_usage_millicores = int(cpu_usage[0:-1]) / 1000 ** 2
    else:
        raise ValueError(f"Unknown unit for CPU usage in {cpu_usage}")
    return cpu_usage_millicores


def normalise_mem_to_bytes(mem_usage: str) -> int:
    """
    Given a memory usage string, normalise it to bytes.

        Parameters:
            mem_usage (str): The amount of memory used
        Returns:
            (int): The amount of memory used in bytes
    """
    mem = 0

    unit_lookup = {
        "Ki": 1024 ** 1,
        "Mi": 1024 ** 2,
        "Gi": 1024 ** 3,
        "Ti": 1024 ** 4,
        "Pi": 1024 ** 5,
        "Ei": 1024 ** 6,
        "Zi": 1024 ** 7,
        "Yi": 1024 ** 8,
    }

    if not isinstance(mem_usage, (int, str)):
        raise TypeError("mem_usage must be an integer-string (optionally with a valid unit) or int")

    if isinstance(mem_usage, int) or isinstance(mem_usage, str) and mem_usage.isnumeric():
        mem = int(mem_usage)
    else:
        for key, value in unit_lookup.items():
            if mem_usage.endswith(key):
                mem = int(mem_usage[0:-len(key)]) * value
                break
        else:
            raise ValueError(f"Unknown unit for memory usage in {mem_usage}")

    return mem


def normalise_mem_bytes_to_str(mem_usage_bytes: int, fmt: str = "float") -> str:
    """
    Given memory usage in bytes, convert it to a normalised string.

        Parameters:
            mem_usage_bytes (int): The memory size in bytes
            fmt (str): Format as float or integer
        Returns:
            (str): The human readable mem usage with size suffix
        Raises:
            TypeError: size is not an integer
            ValueError: size is not >= 0
    """
    suffix = ""
    mem_usage: float = 0

    suffixes = (
        "",    # 1024 ** 1
        "Ki",  # 1024 ** 2
        "Mi",  # 1024 ** 3
        "Gi",  # 1024 ** 4
        "Ti",  # 1024 ** 5
        "Pi",  # 1024 ** 6
        "Ei",  # 1024 ** 7
        "Zi",  # 1024 ** 8
        "Yi",  # 1024 ** 9
    )

    if not isinstance(mem_usage_bytes, int):
        raise TypeError("mem_usage_bytes must be an int")

    mem_usage = float(mem_usage_bytes)

    if mem_usage < 0:
        raise ValueError("mem_usage_bytes must be >= 0")

    for i, suffix in enumerate(suffixes):
        if mem_usage < 1024 or i >= len(suffixes) - 1:
            break
        mem_usage /= 1024 ** 1

    if fmt == "int":
        return f"{int(mem_usage)}{suffix}B"
    return f"{mem_usage:0.1f}{suffix}B"


def disksize_to_human(size: int) -> str:
    """
    Given a disksize in bytes, convert it to a more readable format with size suffix.

        Parameters:
            size (int): The disksize in bytes
        Returns:
            (str): The human readable disksize with size suffix
        Raises:
            TypeError: size is not an integer
            ValueError: size is not >= 0
    """
    tmp = normalise_mem_bytes_to_str(size, fmt="int")
    if tmp[:-1].isnumeric():
        tmp = f"{tmp[:-1]} bytes"
    return tmp


def split_msg(rawmsg: str) -> list[str]:
    """
    Split a string into a list of strings, strip NUL-bytes, and convert newlines.

        Parameters:
            rawmsg (str): The string to split
        Returns:
            ([str]): A list of split strings
    """
    if not isinstance(rawmsg, str):
        raise TypeError(f"rawmsg is type {type(rawmsg)}, expected str")
    # We only want "\n" to represent newlines
    tmp = rawmsg.replace("\r\n", "\n")
    # We also replace all \x00 with <NUL>
    tmp = tmp.replace("\x00", "<NUL>")
    # We also replace non-breaking space with space
    tmp = tmp.replace("\xa0", " ")
    # And remove almost all control characters
    tmp = re.sub(r"[\x00-\x08\x0b-\x1a\x1c-\x1f\x7f-\x9f]", "\uFFFD", tmp)

    return list(map(str.rstrip, tmp.splitlines()))


def strip_ansicodes(message: str) -> str:
    """
    Strip all ANSI-formatting from a string.

        Parameters:
            message (str): The string to strip
        Returns:
            (str): The stripped string
        Raises:
            TypeError: The input was not a string
    """
    if not isinstance(message, str):
        raise TypeError(f"message is type {type(message)}, expected str")

    message = message.replace("\\x1b", "\x1b").replace("\\u001b", "\x1b")
    tmp = re.findall(r"("
                     r"\x1b\[\d+m|"
                     r"\x1b\[\d+;\d+m|"
                     r"\x1b\[\d+;\d+;\d+m|"
                     r".*?)", message)
    message = "".join(item for item in tmp if not item.startswith("\x1b"))

    return message


# pylint: disable-next=too-many-branches
def read_cmtconfig() -> dict:
    """
    Read cmt.yaml and cmt.yaml.d/*.yaml and update the global cmtconfig dict.

        Returns:
            (dict): A reference to the global cmtconfig dict
    """
    try:
        # This is for the benefit of avoiding dependency cycles
        # pylint: disable-next=import-outside-toplevel
        from natsort import natsorted
    except ModuleNotFoundError:  # pragma: no cover
        sys.exit("ModuleNotFoundError: Could not import natsort; "
                 "you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

    global cmtconfig  # pylint: disable=global-statement
    # Start with an empty base configuration
    cmtconfig = {}

    # This is to allow use of ansithemeprint from cmt-install.
    # pylint: disable-next=import-outside-toplevel
    from clustermanagementtoolkit.cmtio_yaml import secure_read_yaml

    if Path(cmtpaths.SYSTEM_CMT_CONFIG_FILE).is_file():
        # Read the base configuration file from /etc (if available)
        tmp_cmtconfig = secure_read_yaml(cmtpaths.SYSTEM_CMT_CONFIG_FILE)
        if tmp_cmtconfig is not None:
            cmtconfig = dict(tmp_cmtconfig)
    elif Path(cmtpaths.CMT_CONFIG_FILE).is_file():
        # Read the base configuration file from /home/.cmt (if available)
        tmp_cmtconfig = secure_read_yaml(cmtpaths.CMT_CONFIG_FILE)
        if tmp_cmtconfig is not None:
            cmtconfig = dict(tmp_cmtconfig)

    # Now read /etc/cmt.yaml.d/*
    system_config_dir = Path(cmtpaths.SYSTEM_CMT_CONFIG_FILE_DIR)
    if system_config_dir.is_dir():
        for path in natsorted(system_config_dir.iterdir()):
            path = str(path)
            filename = PurePath(path).name

            # Skip tempfiles and only read entries that end with .y{,a}ml
            if filename.startswith(("~", ".")) or not filename.endswith((".yaml", ".yml")):
                continue

            # Read the conflet files
            morecmtconfig = secure_read_yaml(FilePath(path))

            # Handle config files without any values defined
            if morecmtconfig is not None:
                cmtconfig = {**cmtconfig, **dict(morecmtconfig)}

    # Finally {HOMEDIR}/cmt.yaml.d/*
    config_dir = Path(cmtpaths.CMT_CONFIG_FILE_DIR)
    if config_dir.is_dir():
        for path in natsorted(Path(cmtpaths.CMT_CONFIG_FILE_DIR).iterdir()):
            path = cast(str, path)
            filename = PurePath(str(path)).name

            # Skip tempfiles and only read entries that end with .y{,a}ml
            if filename.startswith(("~", ".")) or not filename.endswith((".yaml", ".yml")):
                continue

            # Read the conflet files
            morecmtconfig = secure_read_yaml(FilePath(path))

            # Handle config files without any values defined
            if morecmtconfig is not None:
                cmtconfig = {**cmtconfig, **dict(morecmtconfig)}

    return cmtconfig


# Helper functions
def versiontuple(ver: str) -> tuple[str, ...]:
    """
    Split a version string into a tuple.

        Parameters:
            ver (str): The version string to split
        Returns:
            ((str, ...)): A variable-length tuple with one string per version component
        Raises:
            TypeError: The input was not a string
    """
    filled = []

    if not isinstance(ver, str):
        raise TypeError(f"ver is type {type(ver)}, expected str")

    for point in ver.split("."):
        filled.append(point.zfill(8))
    return tuple(filled)


def age_to_seconds(age: str) -> int:
    """
    Given a time in X1dX2hX3mX4s, convert it to seconds.

        Parameters:
            age (str): A string in age format
        Returns:
            seconds (int): The number of seconds
        Raises:
            TypeError: The input was not a string
            ValueError: The input could not be parsed as an age string
    """
    seconds: int = 0

    if not isinstance(age, str):
        raise TypeError(f"age {age} is type {type(age)}, expected str")

    if not age:
        return -1
    tmp = re.match(r"^(\d+d)?(\d+h)?(\d+m)?(\d+s)?", age)
    if tmp is not None and tmp.span() != (0, 0):
        d = 0 if tmp[1] is None else int(tmp[1][:-1])
        h = 0 if tmp[2] is None else int(tmp[2][:-1])
        m = 0 if tmp[3] is None else int(tmp[3][:-1])
        s = 0 if tmp[4] is None else int(tmp[4][:-1])
        seconds = d * 24 * 60 * 60 + h * 60 * 60 + m * 60 + s
    else:
        raise ValueError(f"age regex did not match; age: {age}")

    return seconds


def seconds_to_age(seconds: int, negative_is_skew: bool = False) -> str:
    """
    Given a time in seconds, convert it to X1dX2hX3mX4s.

        Parameters:
            seconds (int): The number of seconds
            negative_is_skew (bool): Should a negative timestamp
                                     return a clock skew warning (default: -age)
        Returns:
            (str): The age string
        Raises:
            TypeError: The input was not an integer
    """
    if isinstance(seconds, str) and seconds == "":
        return ""

    if not isinstance(seconds, int):
        raise TypeError(f"age {seconds} is type {type(seconds)}, expected int")

    age = ""
    fields = 0

    if seconds < -1:
        sign = "-"
    else:
        sign = ""

    if seconds < -1 and negative_is_skew:
        return "<clock skew detected>"

    seconds = abs(seconds)

    if seconds == 0:
        return "<unset>"
    if seconds >= 24 * 60 * 60:
        days = seconds // (24 * 60 * 60)
        seconds -= days * 24 * 60 * 60
        age += f"{days}d"
        if days >= 7:
            return f"{sign}{age}"
        fields += 1
    if seconds >= 60 * 60:
        hours = seconds // (60 * 60)
        seconds -= hours * 60 * 60
        age += f"{hours}h"
        if hours >= 12:
            return f"{sign}{age}"
        fields += 1
    if seconds >= 60 and fields < 2:
        minutes = seconds // 60
        seconds -= minutes * 60
        age += f"{minutes}m"
        fields += 1
    if seconds > 0 and fields < 2:
        age += f"{seconds}s"

    return f"{sign}{age}"


def get_since(timestamp: Optional[Union[int, datetime]]) -> int:
    """
    Given either a datetime, or an integer, returns how old that
    timestamp is in seconds.

        Parameters:
            timestamp ([int | datetime]): A time in the past
        Returns:
            (int): The number of seconds, 0 if timestamp is None,
                   or -1 if the none_timestamp() was provided
    """
    if timestamp is None:
        return 0

    if not isinstance(timestamp, (int, datetime)):
        raise TypeError(f"timestamp is type {type(timestamp)}, expected int or datetime")

    if timestamp == -1 or timestamp == none_timestamp():
        since = -1
    # If the timestamp is an integer we assume it to already be in seconds
    elif isinstance(timestamp, int):
        since = timestamp
    else:
        timediff = datetime.now(timezone.utc) - timestamp
        since = timediff.days * 24 * 60 * 60 + timediff.seconds

    return since


# Will take datetime and convert it to a timestamp
def datetime_to_timestamp(timestamp: datetime) -> str:
    """
    Given a timestamp in datetime format,
    convert it to a string.

        Parameters:
            timestamp (datetime): The timestamp in datetime
        Returns:
            (str): The timestamp in string format
    """
    if not (timestamp is None or isinstance(timestamp, (date, datetime))):
        msg = [
            [("datetime_to_timestamp()", "emphasis"),
             (" initialised with invalid argument(s):", "error")],
            [("timestamp = ", "default"),
             (f"{timestamp}", "argument"),
             (" (type: ", "default"),
             (f"{type(timestamp)}", "argument"),
             (", expected: ", "default"),
             (f"{datetime}", "argument"),
             (")", "default")],
        ]

        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

        raise ProgrammingError(unformatted_msg,
                               severity=LogLevel.ERR,
                               formatted_msg=formatted_msg)

    if timestamp is None or timestamp == none_timestamp():
        string = ""
    elif timestamp == datetime.fromtimestamp(0).astimezone():
        # Replace epoch with an empty string
        # with the same length as a timestamp
        string = "".ljust(len(str(datetime.fromtimestamp(0).astimezone())))
    elif isinstance(timestamp, datetime):
        string = f"{timestamp.astimezone():%Y-%m-%d %H:%M:%S}"
    else:
        string = f"{timestamp:%Y-%m-%d}"
    return string


def reformat_timestamp(timestamp: str) -> str:
    """
    Takes a timestamp in various formats and formats it the proper(tm) way; ISO-8601.

        Parameters:
            timestamp (str): A timestamp str
        Returns:
            (str): A timestamp str in YYYY-MM-DD HH:MM:SS format
    """
    if timestamp is not None:
        for fmt in ("%Y-%m-%d %H:%M:%S.%f%z",
                    "%Y-%m-%d %H:%M:%S%z",
                    "%Y-%m-%dT%H:%M:%S.%f%z",
                    "%Y-%m-%dT%H:%M:%S%z"):

            try:
                return f"{datetime.strptime(timestamp, fmt).astimezone():%Y-%m-%d %H:%M:%S}"
            except ValueError:
                pass

    raise ValueError(f"Could not parse timestamp: {timestamp}")


# Will take a timestamp and convert it to datetime
def timestamp_to_datetime(timestamp: str, default: datetime = none_timestamp()) -> datetime:
    """
    Takes a timestamp and converts it to datetime.

        Parameters:
            timestamp (str): The timestamp string to convert
            default (datetime): The value to return if timestamp is None, 0, "", or "None"
        Returns:
            (int|datetime): -1 if the timestamp was -1, datetime otherwise
    """
    rtimestamp = timestamp

    if timestamp is None \
            or isinstance(timestamp, int) and timestamp == 0 \
            or isinstance(timestamp, str) and timestamp in ("", "None"):
        return default

    if timestamp == -1:
        return none_timestamp()

    # Just in case the timestamp isn't a string already
    timestamp = str(timestamp)

    # Timestamps that end with Z are already in UTC; strip that
    if timestamp.endswith("Z"):
        timestamp = timestamp[:-1]

    # Timestamps that have both a numerical timezone offset and a timezone name do not make sense
    tmp = re.match(r"^(.+ [+-]\d{4}) [A-Z]{3}$", timestamp)
    if tmp is not None:
        timestamp = f"{tmp[1]}"

    # Some timestamps are weird
    tmp = re.match(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{6})\d* ([+-]\d{4})$", timestamp)
    if tmp is not None:
        timestamp = f"{tmp[1]}{tmp[2]}"

    tmp = re.match(r"^(.+?) ?([+-]\d{4})$", timestamp)
    if tmp is not None:
        timestamp = f"{tmp[1]}{tmp[2]}"
    else:
        # If the timestamp has too many, or too few, decimals (should be 6), adjust it
        tmp = re.match(r"^(\d{4}-\d\d-\d\d.\d\d:\d\d:\d\d\.)(\d+)", timestamp)
        if tmp is not None:
            if len(tmp[2]) != 6:
                timestamp = f"{tmp[1]}{tmp[2]:06.6}"
        # For timestamp without timezone add one; all timestamps are assumed to be UTC
        timestamp += "+0000"

    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%d %H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S%z"):
        try:
            return datetime.strptime(timestamp, fmt)
        except ValueError:
            pass

    errmsg = [
        [("Could not parse timestamp: ", "default"),
         (f"{rtimestamp}", "argument"),
         ("; defaulting to ", "default"),
         (f"{none_timestamp()}", "argument"),
         (".", "default")],
    ]

    unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(errmsg)
    cmtlog.log(LogLevel.ERR, msg=unformatted_msg, messages=formatted_msg)

    return none_timestamp()


# pylint: disable-next=too-many-branches,too-many-statements
def make_set_expression_list(expression_list: list[dict],
                             key: str = "", toleration: bool = False) -> list[tuple[str, str, str]]:
    """
    Create a list of set expressions (key, operator, values).

        Parameters:
            expression_list ([dict]): A list of dicts to extract extract the data from
            key (str):
            toleration (bool): Is this a match expression or a toleration?
        Returns:
            ([(key, operator, values)]): A set expression list
    """
    expressions = []

    if expression_list is not None:
        if not isinstance(expression_list, list):
            raise TypeError("expression_list must be a list")
        for expression in expression_list:
            operator = deep_get_with_fallback(expression,
                                              [DictPath("operator"), DictPath("op")], "")
            requires_values = None
            if not isinstance(operator, str):
                raise TypeError("operator must be a str")
            if operator == "In":
                new_operator = "In "
                requires_values = "1+"
            elif operator == "NotIn":
                new_operator = "Not In "
                requires_values = "1+"
            elif operator == "Equals":
                new_operator = "= "
                requires_values = "1+"
            elif operator == "Exists":
                new_operator = "Exists"
                requires_values = "0"
            elif operator == "DoesNotExist":
                new_operator = "Does Not Exist"
                requires_values = "0"
            elif operator == "Gt":
                new_operator = "> "
                requires_values = "1"
            elif operator == "Lt":
                new_operator = "< "
                requires_values = "1"
            else:
                raise ValueError(f"Unknown operator '{operator}'")
            key = deep_get_with_fallback(expression, [DictPath("key"), DictPath("scopeName")], key)
            if not isinstance(key, str):
                raise TypeError("key must be a str")

            tmp = deep_get_with_fallback(expression, [DictPath("values"), DictPath("value")], [])
            if not isinstance(tmp, list):
                raise TypeError("values must be a list")

            if requires_values == "0" and tmp and len(max(tmp, key=len)):
                # Exists and DoesNotExist do no accept values;
                # for the sake of convenience we still accept empty values
                raise ValueError(f"operator {operator} does not accept values; values {tmp}")
            if requires_values == "1" and len(tmp) != 1:
                raise ValueError(f"operator {operator} requires exactly 1 value; values {tmp}")
            if requires_values == "1+" and len(tmp) < 1:
                raise ValueError(f"operator {operator} requires at least 1 value; values {tmp}")
            values = ",".join(tmp)
            if requires_values != "0" and operator not in ("Gt", "Lt"):
                values = f"[{values}]"

            if toleration:
                effect = deep_get(expression, DictPath("effect"), "All")
                expressions.append((str(key), str(new_operator), values, effect))
            else:
                expressions.append((str(key), str(new_operator), values))
    return expressions


def make_set_expression(expression_list: list[dict]) -> str:
    """
    Join set expressions data into one single string.

        Parameters:
            expression_list (dict): The dict to extract the data from
        Returns:
            (str): The set expressions joined into one string
    """
    vlist = make_set_expression_list(expression_list)
    xlist = []
    for key, operator, values in vlist:
        xlist.append(f"{key} {operator}{values}")
    return ", ".join(xlist)


def make_label_selector(selector_dict: dict) -> str:
    """
    Given a label selector dict entry, create a selector list string.

        Parameters:
            selector_dict (dict): The dict with selectors
        Returns:
            selector_str (str): The selector string
    """
    selectors = []

    if selector_dict is not None:
        for key, value in selector_dict.items():
            selectors.append(f"{key}={value}")

    return ",".join(selectors)


def get_package_versions(hostname: str) -> list[tuple[str, str]]:
    """
    Returns a list of predefined packages for a host.

        Parameters:
            hostname (str): The host to get package versions for
        Returns:
            ([(str, str)]): The list of package versions
    """
    # pylint: disable-next=import-outside-toplevel
    from clustermanagementtoolkit.ansible_helper import ansible_run_playbook_on_selection
    # pylint: disable-next=import-outside-toplevel
    from clustermanagementtoolkit.ansible_helper import get_playbook_path

    if not isinstance(hostname, str):
        raise TypeError(f"hostname {hostname} is type: {type(hostname)}, expected str")

    get_versions_path = get_playbook_path(FilePath("get_versions.yaml"))
    retval, ansible_results = ansible_run_playbook_on_selection(get_versions_path,
                                                                selection=[hostname])

    if not ansible_results:
        raise ValueError(f"Error: Failed to get package versions from {hostname} "
                         f"(retval: {retval}); aborting.")

    tmp = []

    for result in deep_get(ansible_results, DictPath(hostname), []):
        if deep_get(result, DictPath("task"), "") == "Package versions":
            tmp = deep_get(result, DictPath("msg_lines"), [])
            break

    if not tmp:
        raise ValueError(f"Error: Received empty version data from {hostname} "
                         f"(retval: {retval}); aborting.")

    package_versions = []
    package_version_regex = re.compile(r"^(.*?): (.*)")

    for line in tmp:
        tmp2 = package_version_regex.match(line)
        if tmp2 is None:
            continue
        package = tmp2[1]
        version = tmp2[2]
        package_versions.append((package, version))

    return package_versions


def __extract_version(line: str) -> str:
    """
    Extract a version from an apt-cache madison entry.

        Parameters:
            line (str): A package info line from apt-cache madison
        Returns:
            (str): A version number
    """
    if not isinstance(line, str):
        raise TypeError(f"{line} is type: {type}; expected str")

    tmp = line.split("|")
    if len(tmp) != 3:
        raise ValueError("Failed to extract a version; "
                         "this is (most likely) a programming error.")
    return tmp[1].strip()


# pylint: disable-next=too-many-locals,too-many-branches
def check_versions_apt(packages: list[str]) -> list[tuple[str, str, str, list[str]]]:
    """
    Given a list of packages, return installed, candidate, and all available versions.

        Parameters:
            packages ([str]): A list of packages to get versions for
        Returns:
            ([(str, str, str, [str])]): A list of package versions
    """
    try:
        # This is for the benefit of avoiding dependency cycles
        # pylint: disable-next=import-outside-toplevel
        from natsort import natsorted
    except ModuleNotFoundError:  # pragma: no cover
        sys.exit("ModuleNotFoundError: Could not import natsort; "
                 "you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

    versions = []

    if not isinstance(packages, (list, tuple)):
        raise TypeError(f"packages must be a list or tuple, got {type(packages)}")

    apt_cache_path = cmtio.secure_which(FilePath("apt-cache"),
                                        fallback_allowlist=["/bin", "/usr/bin"],
                                        security_policy=SecurityPolicy.ALLOWLIST_STRICT)
    args = [apt_cache_path, "policy"] + packages
    response = cmtio.execute_command_with_response(args)
    split_response = response.splitlines()
    installed_regex = re.compile(r"^\s*Installed: (.*)")
    candidate_regex = re.compile(r"^\s*Candidate: (.*)")
    for line in split_response:
        if line.endswith(":"):
            package = line[:-1]
        elif line.startswith("  Installed: "):
            tmp = installed_regex.match(line)
            if tmp is not None:
                if tmp[1] == "(none)":
                    installed_version = "<none>"
                else:
                    installed_version = tmp[1]
            else:
                installed_version = "<none>"
        elif line.startswith("  Candidate: "):
            tmp = candidate_regex.match(line)
            if tmp is not None and tmp[1] != installed_version:
                if tmp[1] == "(none)":
                    if installed_version == "<none>":
                        continue
                    candidate_version = "<none>"
                else:
                    candidate_version = tmp[1]
            else:
                candidate_version = ""
            # We have the current and candidate version now;
            # get all the other versions of the same package
            apt_cache_path = cmtio.secure_which(FilePath("apt-cache"),
                                                fallback_allowlist=["/bin", "/usr/bin"],
                                                security_policy=SecurityPolicy.ALLOWLIST_STRICT)
            _args = [apt_cache_path, "madison", package]
            _response = cmtio.execute_command_with_response(_args)
            _split_response = _response.splitlines()
            all_versions = []
            for version in _split_response:
                if version.endswith(" Packages"):
                    all_versions.append(__extract_version(version))
            natsorted_versions = []
            for natsorted_version in natsorted(all_versions, reverse=True):
                natsorted_versions.append(str(natsorted_version))
            versions.append((package, installed_version, candidate_version, natsorted_versions))

    return versions


def check_versions_yum(packages: list[str]) -> list[tuple[str, str, str, list[str]]]:
    """
    Given a list of packages, return installed, candidate, and all available versions.

        Parameters:
            packages ([str]): A list of packages to get versions for
        Returns:
            ([(str, str, str, [str])]): A list of package versions
    """
    versions = []
    versions_dict: dict[str, dict] = {}

    yum_path = cmtio.secure_which(FilePath("/usr/bin/yum"), fallback_allowlist=["/usr/bin"],
                                  security_policy=SecurityPolicy.ALLOWLIST_RELAXED)
    args = [yum_path, "-y", "-q", "list", "--showduplicates"] + packages
    response = cmtio.execute_command_with_response(args)
    split_response = response.splitlines()

    package_version = re.compile(r"^([^.]+)[^\s]+[\s]+([^\s]+).*")

    section = ""

    for line in split_response:
        if line.lower() == "installed packages":
            section = "installed"
            continue
        if line.lower() == "available packages":
            section = "available"
            continue
        tmp = package_version.match(line)
        if tmp is not None:
            package = tmp[1]
            version = tmp[2]

            if package not in versions_dict:
                versions_dict[package] = {
                    "installed": "<none>",
                    "candidate": "<none>",
                    "available": [],
                }

            if section == "installed":
                versions_dict[package]["installed"] = version
            elif section == "available":
                versions_dict[package]["available"].append(version)

    # Now summarise
    for package, data in versions_dict.items():
        candidate = "<none>"
        if data["available"]:
            candidate = data["available"][-1]
            if data["installed"] == candidate:
                candidate = ""
        versions.append((package, data["installed"],
                         candidate, list(reversed(data["available"]))))

    return versions


# pylint: disable-next=too-many-locals
def check_versions_zypper(packages: list[str]) -> list[tuple[str, str, str, list[str]]]:
    """
    Given a list of packages, return installed, candidate, and all available versions.

        Parameters:
            packages ([str]): A list of packages to get versions for
        Returns:
            ([(str, str, str, [str])]): A list of package versions
    """
    versions = []
    versions_dict: dict[str, dict] = {}

    zypper_path = cmtio.secure_which(FilePath("/usr/bin/zypper"), fallback_allowlist=["/usr/bin"],
                                     security_policy=SecurityPolicy.ALLOWLIST_RELAXED)
    args = [zypper_path, "search", "-s", "-x"] + packages
    response = cmtio.execute_command_with_response(args)
    split_response = response.splitlines()

    # il | kubernetes1.28-kubeadm | package | 1.28.3-150400.5.1 | x86_64 | kubic
    # i | kubernetes1.28-kubeadm | package | 1.28.3-150400.5.1 | x86_64 | kubic
    package_version = re.compile(r"^(.).? \| (\S+) +\| package +\| (\S+) +\|.*")

    for line in split_response:
        if (tmp := package_version.match(line)):
            if tmp is not None:
                package = tmp[2]
                version = tmp[3]

                if package not in versions_dict:
                    versions_dict[package] = {
                        "installed": "<none>",
                        "candidate": "<none>",
                        "available": [],
                    }

                if tmp[1] == "i":
                    versions_dict[package]["installed"] = version
                versions_dict[package]["available"].append(version)

    # Now summarise
    for package, data in versions_dict.items():
        installed = data["installed"]
        available = data["available"]
        if available:
            candidate = available[0]
        if candidate == installed:
            candidate = ""
        versions.append((package, data["installed"],
                         candidate, list(reversed(data["available"]))))

    return versions


def identify_distro(**kwargs: Any) -> str:
    """
    Identify what distro (Debian, Red Hat, SUSE, etc.) is in use.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (str): The identified distro; empty if no distro could be identified
    """
    exit_on_failure = deep_get(kwargs, DictPath("exit_on_failure"), True)
    error_on_failure = deep_get(kwargs, DictPath("error_on_failure"), True)

    # Find out what distro this is run on
    try:
        distro_path = cmtio.secure_which(FilePath("/etc/os-release"),
                                         fallback_allowlist=["/usr/lib", "/lib"],
                                         security_policy=SecurityPolicy.ALLOWLIST_STRICT,
                                         executable=False)
    except FileNotFoundError:  # pragma: no cover
        ansithemeprint([ANSIThemeStr("Error:", "error"),
                        ANSIThemeStr(" Cannot find an “", "default"),
                        ANSIThemeStr("os-release", "path"),
                        ANSIThemeStr("“ file to determine OS distribution; aborting.",
                                     "default")], stderr=True)
        sys.exit(errno.ENOENT)

    distro = None

    distro_id_like = ""
    distro_id = ""

    with open(distro_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            key, value = line.split("=")
            value = value.strip("\"'")
            if key == "ID_LIKE":
                distro_id_like = value
                # If there's an ID_LIKE in the file we're done
                break
            if key == "ID":
                distro_id = value
                # But if we've only found an ID we cannot be sure
                # that there won't be an ID_LIKE later on

    if distro_id_like:
        distro = distro_id_like
    else:
        distro = distro_id

    if distro is None or not distro:
        if error_on_failure:
            ansithemeprint([ANSIThemeStr("Error:", "error"),
                            ANSIThemeStr(" Cannot read ID / ID_LIKE from “", "default"),
                            ANSIThemeStr("os-release", "path"),
                            ANSIThemeStr("“ file to determine OS distribution",
                                         "default")], stderr=True)
        if exit_on_failure:  # pragma: no cover
            sys.exit(errno.ENOENT)
        return ""

    if distro == "suse opensuse":
        distro = "suse"

    return distro


def get_latest_upstream_version(component: str) -> str:
    """
    Fetch the upstream version for Kubernetes.

        Parameters:
            component (str): The component to return the latest version for
            **kwargs (dict[str, Any]): Keyword arguments [unused]
        Returns:
            (str): The latest upstream Kubernetes version;
                   or an empty string if the version could not be determined
    """
    if not component:
        return ""

    # This is to allow use of ansithemeprint from cmt-install.
    # pylint: disable-next=import-outside-toplevel
    from clustermanagementtoolkit.cmtio_yaml import secure_read_yaml

    # We are OK with the file not existing
    security_checks = [
        SecurityChecks.PARENT_RESOLVES_TO_SELF,
        SecurityChecks.OWNER_IN_ALLOWLIST,
        SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
        SecurityChecks.PERMISSIONS,
        SecurityChecks.PARENT_PERMISSIONS,
        SecurityChecks.IS_FILE,
    ]

    try:
        candidate_versions = \
            dict(secure_read_yaml(cmtpaths.VERSION_CANDIDATES_FILE, checks=security_checks))
    except (FileNotFoundError, TypeError):
        candidate_versions = {}

    return deep_get(candidate_versions, DictPath(f"{component}#release"), "")


# The following paths are necessary:
# ${HOMEDIR}
# └── .cmt (main directory for CMT)
#     ├── ansible (Ansible files)
#     │   └── log (Ansible logs)
#     ├── cmt.yaml.d (configlets)
#     ├── deployments (generic workloads)
#     ├── hooks (installation hooks)
#     │   └── pre-prepare.d (hooks run before the prepare step)
#     │   ├── post-prepare.d (hooks run after the prepare step)
#     │   ├── pre-setup.d (hooks run before the setup step)
#     │   ├── post-setup.d (hooks run after the setup step)
#     │   ├── pre-upgrade.d (hooks run before the upgrade step)
#     │   ├── post-upgrade.d (hooks run after the upgrade step)
#     │   ├── pre-teardown.d (hooks run before the teardown step)
#     │   ├── post-teardown.d (hooks run after the teardown step)
#     │   ├── pre-purge.d (hooks run before the purge step)
#     │   └── post-purge.d (hooks run after the purge step)
#     ├── logs (debug logs)
#     ├── parsers (parser files; symlink if cmt-install, dir when system path)
#     ├── playbooks (Ansible playbooks; symlink if cmt-install, dir when system path)
#     ├── sources (data sources; symlink if cmt-install, dir when system path)
#     ├── themes (theme files; symlink if cmt-install, dir when system path)
#     ├── version-cache (version data cache)
#     └── views (view files; symlink if cmt-install, dir when system path)
#
required_dir_paths: list[tuple[FilePath, int]] = [
    (cmtpaths.CMTDIR, 0o755),
    (cmtpaths.ANSIBLE_DIR, 0o755),
    (cmtpaths.ANSIBLE_LOG_DIR, 0o700),
    (cmtpaths.CMT_CONFIG_FILE_DIR, 0o755),
    (cmtpaths.DEPLOYMENT_DIR, 0o700),
    (cmtpaths.CMT_HOOKS_DIR, 0o755),
    (cmtpaths.CMT_PRE_PREPARE_DIR, 0o755),
    (cmtpaths.CMT_POST_PREPARE_DIR, 0o755),
    (cmtpaths.CMT_PRE_SETUP_DIR, 0o755),
    (cmtpaths.CMT_POST_SETUP_DIR, 0o755),
    (cmtpaths.CMT_PRE_UPGRADE_DIR, 0o755),
    (cmtpaths.CMT_POST_UPGRADE_DIR, 0o755),
    (cmtpaths.CMT_POST_TEARDOWN_DIR, 0o755),
    (cmtpaths.CMT_POST_TEARDOWN_DIR, 0o755),
    (cmtpaths.CMT_PRE_PURGE_DIR, 0o755),
    (cmtpaths.CMT_POST_PURGE_DIR, 0o755),
    (cmtpaths.CMT_LOGS_DIR, 0o700),
    (cmtpaths.VERSION_CACHE_DIR, 0o700),
]

required_dir_or_symlink_paths: list[tuple[FilePath, int]] = [
    (cmtpaths.ANSIBLE_PLAYBOOK_DIR, 0o755),
    (cmtpaths.PARSER_DIR, 0o755),
    (cmtpaths.SOFTWARE_SOURCES_DIR, 0o755),
    (cmtpaths.THEME_DIR, 0o755),
    (cmtpaths.VIEW_DIR, 0o755),
]


def setup_paths() -> list[SecurityStatus]:
    """
    Create all directories & files that need to be present
    for CMT to work properly; this should've been handled by .cmt-install
    if we're running directly from git + ${HOMEDIR}/bin.

    If /usr/share/cluster-management-toolkit doesn't exist we assume local installation;
    this heuristic may need revisiting later on.

        Returns:
            ([SecurityStatus]): SecurityStatus.OK on success,
                                a list of SecurityStatus violations on failure
    """
    system_path_installation = True

    if not Path(cmtpaths.SYSTEM_DATA_DIR).is_dir():
        system_path_installation = False

    for path, permissions in required_dir_paths:
        if not Path(path).is_dir():
            if not system_path_installation:
                sys.exit(f"The directory {path} is missing; "
                         "you may need to (re-)run `cmt-install`; aborting.")
            result = cmtio.secure_mkdir(directory=path, permissions=permissions, exist_ok=False)
            if result != [SecurityStatus.OK]:
                return result

    for path, permissions in required_dir_or_symlink_paths:
        if not Path(path).is_dir():
            if not system_path_installation:
                if not Path(path).is_symlink():
                    sys.exit(f"The symlink {path} is missing; "
                             "you may need to (re-)run `cmt-install`; aborting.")
            result = cmtio.secure_mkdir(directory=path, permissions=permissions, exist_ok=False)
            if result != [SecurityStatus.OK]:
                return result
    return [SecurityStatus.OK]


# pylint: disable=too-many-arguments,too-many-positional-arguments
def check_allowlist(allowlist: dict, allowlist_name: str, value: Optional[Any],
                    default: Optional[Any] = None, exit_on_fail: bool = True,
                    allow_none: bool = False) -> Optional[Any]:
    """
    Check whether the provided value is in the allowlist,
    and either return a default, or exit if it's not in the allowlist.

        Parameters:
            allowlist (Dict): A list of allowed values and the corresponding return value
            allowlist_name (str): The name of the allow list (used for exit message)
            value (Any): A value that can be used as a dict key
            default (Any): The value to return if the value isn't in the allow list
            exit_on_fail (bool): Exit on failure
            allow_none (bool): Allow None as value
        Returns:
            (Any): An acceptable value
    """
    if value is None and allow_none:
        return None
    if value not in allowlist.keys() and exit_on_fail:
        allowed_values = ""
        if allowlist.keys():
            allowed_values = "\n- " + "\n- ".join(allowlist.keys())
        sys.exit(f"“{value}“ is not in “{allowlist_name}“; "
                 f"allowed values:{allowed_values}\nAborting.")
    return allowlist.get(value, default)
