#! /usr/bin/env python3
import re
import sys

# Helper functions
def join_tuple_list(items, _tuple = "", item_prefix = None, item_suffix = None, separator = None):
	_list = []
	first = True

	for item in items:
		if first == False and separator is not None:
			_list.append(separator)
		if item_prefix is not None:
			_list.append(item_prefix)
		if type(item) == tuple:
			_list.append(item)
		else:
			_list.append((item, _tuple))
		if item_suffix is not None:
			_list.append(item_suffix)
		first = False
	return _list

def age_to_seconds(age):
	seconds = 0

	tmp = re.match("^(\d+d)?(\d+h)?(\d+m)?(\d+s)?", age)
	if tmp is not None:
		if len(tmp[0]) == 0:
			seconds = -1
		else:
			d = 0 if tmp[1] is None else int(tmp[1][:-1])
			h = 0 if tmp[2] is None else int(tmp[2][:-1])
			m = 0 if tmp[3] is None else int(tmp[3][:-1])
			s = 0 if tmp[4] is None else int(tmp[4][:-1])
			seconds = d * 24 * 60 * 60 + h * 60 * 60 + m * 60 + s
	else:
		raise Exception(f"age regex did not match; age: {age}")

	return seconds

def seconds_to_age(seconds):
	age = ""
	fields = 0

	if seconds == 0:
		return "<unset>"
	if seconds >= 24 * 60 * 60:
		days = seconds // (24 * 60 * 60)
		seconds -= days * 24 * 60 * 60
		age += f"{days}d"
		if days >= 7:
			return age
		fields += 1
	if seconds >= 60 * 60:
		hours = seconds // (60 * 60)
		seconds -= hours * 60 * 60
		age += f"{hours}h"
		if hours >= 12:
			return age
		fields += 1
	if seconds >= 60 and fields < 2:
		minutes = seconds // 60
		seconds -= minutes * 60
		age += f"{minutes}m"
		fields += 1
	if seconds > 0 and fields < 2:
		age += f"{seconds}s"

	return age
