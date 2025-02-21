#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Structured log module for CMT.
"""

import logging
import logging.handlers
from typing import Any, cast, Union
from collections.abc import Callable

from clustermanagementtoolkit import cmtpaths

from clustermanagementtoolkit.cmttypes import deep_get, DictPath

from clustermanagementtoolkit.ansithemeprint import ANSIThemeStr


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


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger that generates log messages as YAML-list entries.

        Parameters:
            name (str): The name of the module that the logger is to be used in
        Returns:
            (logging.Logger): A logger configured to generate YAML-list entries
    """
    formatter = \
        logging.Formatter('- {'
                          '"timestamp": %(asctime)s, "severity": "%(levelname)s", '
                          '"facility": "%(name)s", "message": "%(message)s", '
                          '"file": "%(filename)s", "function": "%(funcName)s", '
                          '"lineno": "%(lineno)s", "ppid": "%(process)s", %(messages)s'
                          '}')
    handler = \
        logging.handlers.RotatingFileHandler(cmtpaths.CMT_LOGS_DIR.joinpath(f"{name}.log.yaml"),
                                             backupCount=100)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.addHandler(handler)
    return logger


def log(logger: Callable, **kwargs: Any) -> None:
    """
    Log a message.

        Parameters:
            logger (Logger.severity()): The logger to use
            msg (str): An unformatted log message
            messages ([str|[ANSIThemeStr]]): A list of unformatted strings or formatted strings
    """
    msg = deep_get(kwargs, DictPath("msg"), "")
    messages = deep_get(kwargs, DictPath("messages"), [])

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
    logger(msg, extra={"messages": messages_joined})
