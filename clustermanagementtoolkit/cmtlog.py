#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Structured log module for CMT.
"""

from datetime import datetime
import logging
import logging.handlers
import os
import sys
from typing import Any, cast, Optional, Union
from collections.abc import Callable

from clustermanagementtoolkit import cmtpaths

from clustermanagementtoolkit.cmttypes import deep_get, DictPath, LogLevel

from clustermanagementtoolkit.ansithemeprint import ANSIThemeStr

logger: Optional[logging.Logger] = None


def log_array_to_string(msglist: list[Union[str, list[ANSIThemeStr]]]) -> str:
    """
    Convert a list of strings or a list of ANSIThemeArray to a text representation
    that can be written to a YAML-file.

        Parameters:
            msglist ([str|[ANSITHemeStr]): The list of messages
        Returns:
            (str): A string representation of the list of messages
    """
    if not msglist:
        return ""

    if isinstance(msglist[0], str):
        return f'"strarray": [{", ".join(cast(list[str], msglist))}]'

    loglines = []
    for line in msglist:
        logline = []
        for linesegment in line:
            linesegment = cast(ANSIThemeStr, linesegment)
            logline.append(f'{{"string": "{str(linesegment)}", '
                           f'"themeref": "{linesegment.themeref}"}}')
        loglines.append(f'[{", ".join(logline)}]')
    return f'"themearray": [{", ".join(loglines)}]'


def set_logger(name: str, loglevel: LogLevel) -> None:
    """
    Return a logger that generates log messages as YAML-list entries.

        Parameters:
            name (str): The name of the module that the logger is to be used in
            loglevel (LogLevel): Logging threshold
    """
    global logger  # pylint: disable=global-statement

    formatter = \
        logging.Formatter('- {'
                          '"timestamp": "%(timestamp)s", "severity": "%(levelname)s", '
                          '"facility": "%(name)s", "message": "%(message)s", '
                          '"file": "%(file)s", "function": "%(function)s", '
                          '"lineno": "%(lineno)s", "ppid": "%(process)s", %(messages)s'
                          '}')
    handler = \
        logging.handlers.RotatingFileHandler(cmtpaths.CMT_LOGS_DIR.joinpath(f"{name}.log.yaml"),
                                             maxBytes=1_000_000, backupCount=10)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.addHandler(handler)
    set_level(loglevel)


def __loglevel_to_logger(loglevel: LogLevel) -> Callable:
    if logger is None:
        raise ValueError("cmtlog.__loglevel_to_logger() "
                         "called without being initialized; aborting.")

    if loglevel == LogLevel.DEBUG:
        return logger.debug
    if loglevel == LogLevel.INFO:
        return logger.info
    if loglevel == LogLevel.WARNING:
        return logger.warning
    if loglevel == LogLevel.ERR:
        return logger.error
    if loglevel == LogLevel.CRIT:
        return logger.critical
    raise ValueError(f"Unsupported LogLevel: {repr(loglevel)}; "
                     "supported LogLevels: {DEBUG|INFO|WARNING|ERR|CRIT}.")


def log(loglevel: LogLevel, **kwargs: Any) -> None:
    """
    Log a message.

        Parameters:
            msg (str): An unformatted log message
            messages ([str|[ANSIThemeStr]]): A list of unformatted strings or formatted strings
    """
    msg = deep_get(kwargs, DictPath("msg"), "")
    messages = deep_get(kwargs, DictPath("messages"), [])

    if logger is None:
        # If an exception occurs before the logger has been initialised we do not want
        # the program to abort without a chance to raise an exception, so just return here.
        return

    if not messages and not msg:
        messages = ["Attempted to log without log message"]

    if not messages:
        messages = [msg]

    if not msg:
        if isinstance(messages[0], list):
            msg = messages[0][0]
        else:
            msg = messages[0]
    messages_joined = log_array_to_string(messages)
    timestamp = f"{datetime.now().astimezone():%Y-%m-%d %H:%M:%S%z}"
    try:
        # This is to get the necessary stack info
        raise UserWarning
    except UserWarning:
        frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
        file = str(frame.f_code.co_filename)  # type: ignore
        function = str(frame.f_code.co_name)  # type: ignore

    extra = {
        "messages": messages_joined,
        "timestamp": timestamp,
        "function": function,  # pylint: disable=used-before-assignment
        "file": f"{os.path.basename(file)}",  # pylint: disable=used-before-assignment
    }
    __loglevel_to_logger(loglevel)(msg, extra=extra)


def set_level(loglevel: LogLevel) -> None:
    """
    Set logging threshold.

        Parameters:
            loglevel (LogLevel): One of LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING,
                                 LogLevel.ERR, LogLevel.CRIT
    """
    if logger is None:
        raise TypeError("cmtlog.log() called without being initialized; aborting.")

    if loglevel == LogLevel.DEBUG:
        logger.setLevel(logging.DEBUG)
    elif loglevel == LogLevel.INFO:
        logger.setLevel(logging.INFO)
    elif loglevel == LogLevel.WARNING:
        logger.setLevel(logging.WARNING)
    elif loglevel == LogLevel.ERR:
        logger.setLevel(logging.ERROR)
    elif loglevel == LogLevel.CRIT:
        logger.setLevel(logging.CRITICAL)
    else:
        raise ValueError(f"cmtlog.set_level() called with invalid loglevel {loglevel}")
