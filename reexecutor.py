#! /usr/bin/env python3
# Requires: python3 (>= 3.8)

"""
A wrapper for using futures
"""

import concurrent.futures
from datetime import datetime
import threading
from typing import Any, Callable, List, Optional, Tuple, Type

class ReExecutor:
	def __init__(self, max_workers: Optional[int] = None) -> None:
		if max_workers is not None:
			self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = max_workers)
		else:
			self.executor = concurrent.futures.ThreadPoolExecutor()
		self.futures = {}
		self.lock = threading.Lock()

	def __trigger(self, key: str) -> None:
		data = self.futures[key]
		data["triggered"] = True
		data["future"] = self.executor.submit(data["function"], *data["args"], **data["kwargs"])
		self.futures[key] = data

	def trigger(self, key: str, interval: int, fn: Callable, /, *args, **kwargs) -> None:
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
		self.trigger(key, self.futures[key]["interval"], self.futures[key]["function"], self.futures[key]["args"], self.futures[key]["kwargs"])

	def get(self, key: str) -> Tuple[List[Type], List[Any]]:
		info = []
		status = []

		if key in self.futures:
			if self.futures[key]["triggered"] and self.futures[key]["future"].done():
				self.futures[key]["last_update"] = datetime.now()
				info, status = self.futures[key]["future"].result()
				self.futures[key]["triggered"] = False
				self.futures[key]["future"] = None
			elif not self.futures[key]["triggered"] and (datetime.now() - self.futures[key]["last_update"]).seconds > self.futures[key]["interval"]:
				self.retrigger(key)
		return info, status

	def delete(self, key: str) -> None:
		"""
		Delete a future

			Parameters:
				key (str): The future to delete
		"""
		with self.lock:
			if key in self.futures:
				if self.futures[key]["future"] is not None:
					self.futures[key]["future"].cancel()
				self.futures.pop(key)

	def flush(self) -> None:
		for key in list(self.futures.keys()):
			self.delete(key)

	def shutdown(self) -> None:
		"""
		Shutdown the executor
		"""
		self.flush()
		# Maybe check for python version and use:
		# self.executor.shutdown(wait = False, cancel_futures = True)
		self.executor.shutdown(wait = False)
