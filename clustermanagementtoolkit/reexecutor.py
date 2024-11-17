#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
A wrapper for using for executing callables asynchronously
using the concurrent.futures ThreadPoolExecutor
"""

import concurrent.futures
from datetime import datetime
import sys
import threading
from typing import Any, Optional, Type
from collections.abc import Callable


class ReExecutor:
    """
    A wrapper class for concurrent futures.
    """
    def __init__(self, max_workers: Optional[int] = None) -> None:
        """
        Init method for the ReExecutor() class.

            Parameters:
                max_workers (int): The maximum number of worker threads to dimension
        """
        if max_workers is not None:
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        else:
            self.executor = concurrent.futures.ThreadPoolExecutor()
        self.futures: dict = {}
        self.lock = threading.Lock()

    def __trigger(self, key: str) -> None:
        """
        Internal method for (re-)triggering a callable.

            Parameter:
                key (str): The identifier for the callable to (re-)trigger
        """
        data = self.futures[key]
        data["triggered"] = True
        if data["future"] is not None:
            data["future"].cancel()
        data["future"] = self.executor.submit(data["function"], *data["args"], **data["kwargs"])
        self.futures[key] = data

    def trigger(self, key: str, interval: int,
                fn: Callable, /, *args: list[Any], **kwargs: Any) -> None:
        """
        Trigger a callable.

            Parameter:
                key (str): The identifier for the future to (re-)trigger
                interval (int): Interval between each retrigger, or -1 to only run once
                fn (callable): The callable to execute
                *args (list): Positional arguments to pass to fn
                **kwargs (dict): Keyword arguments to pass to fn
        """
        with self.lock:
            if key not in self.futures:
                data = {
                    "function": fn,
                    "args": args,
                    "kwargs": kwargs,
                    "last_update": datetime.now(),
                    "future": None,
                    "interval": interval,
                }
                self.futures[key] = data
            self.__trigger(key)

    def retrigger(self, key: str) -> None:
        """
        Retrigger a callable

            Parameter:
                key (str): The identifier for the callable to (re-)trigger
        """
        self.trigger(key, self.futures[key]["interval"],
                     self.futures[key]["function"],
                     self.futures[key]["args"], self.futures[key]["kwargs"])

    def update(self, key: str, **kwargs: Any) -> None:
        """
        Update one or several parameters for a callable;
        we currently only support updating keyword args.

            Parameters:
                key (str): The identifier for the callable to update parameters for
                kwargs (dict): The variables to update
        """
        with self.lock:
            if key in self.futures:
                for kwarg, value in kwargs.items():
                    self.futures[key]["kwargs"][kwarg] = value
                self.__trigger(key)

    def get_parameters(self, key: str) -> tuple[list[Any], dict[str, Any]]:
        """
        Get the parameters for a callable.

            Returns:
                ([args]): The arg list
                ({kwargs}): The kwargs dict
        """
        if key in self.futures:
            return self.futures[key]["args"], self.futures[key]["kwargs"]
        return [], {}

    def get(self, key: str) -> tuple[list[Type], list[Any]]:
        """
        Check if there's available data from a callable; if there is, return it.

            Parameters:
                key (str): The identifier for the callable to update parameters for
            Returns:
                ([Type], [Any]): (data, status) or ([], []) if no data is available
        """
        info = []
        status = []

        if key in self.futures:
            update_timeout = (datetime.now() - self.futures[key]["last_update"]).seconds
            interval = self.futures[key]["interval"]
            if self.futures[key]["triggered"] and self.futures[key]["future"].done():
                self.futures[key]["last_update"] = datetime.now()
                info, status = self.futures[key]["future"].result()
                self.futures[key]["triggered"] = False
                self.futures[key]["future"] = None
            elif interval == -1:
                pass
            elif not self.futures[key]["triggered"] and update_timeout > interval:
                self.retrigger(key)
        return info, status

    def delete(self, key: str) -> None:
        """
        Delete a callable.

            Parameters:
                key (str): The callable to delete
        """
        with self.lock:
            if key in self.futures:
                if self.futures[key]["future"] is not None:
                    self.futures[key]["future"].cancel()
                self.futures.pop(key)

    def flush(self) -> None:
        """
        Flush the list of callables.
        """
        for key in list(self.futures.keys()):
            self.delete(key)

    def shutdown(self) -> None:
        """
        Shutdown the executor.
        """
        self.flush()
        # If cancel_futures is supported we should use it
        if sys.version_info[0:2] >= (3, 9):
            self.executor.shutdown(wait=False, cancel_futures=True)
        else:
            self.executor.shutdown(wait=False)

    def __len__(self) -> int:
        """
        Returns the number of items in the executor pool.

            Returns:
                (int): The number of items in the executor pool
        """
        return len(self.futures)

    def __contains__(self, future: str) -> bool:
        """
        Check whether a resource is a part of the executor pool.

            Parameters:
                future (str): The resource to check for
            Returns:
                (bool): True if the resource is in the pool, False otherwise
        """
        return future in self.futures
