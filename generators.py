#! /usr/bin/env python3
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
This generates and post-processes elements for various more complex types
"""

# pylint: disable=too-many-arguments

import copy
from datetime import datetime
from typing import Any, Callable, cast, Dict, List, Optional, Set, Tuple, Union
import yaml

from ansithemeprint import ANSIThemeString
from curses_helper import color_status_group, themearray_len, themearray_to_string, ThemeAttr, ThemeRef, ThemeString, get_theme_ref
import cmtlib
from cmtlib import datetime_to_timestamp, timestamp_to_datetime
from cmttypes import deep_get, deep_get_with_fallback, DictPath, StatusGroup, LogLevel, ProgrammingError
import datagetters

def format_special(string: str, selected: bool) -> Optional[Union[ThemeRef, ThemeString]]:
	"""
	Given a string, substitute any special strings with their formatted version

		Parameters:
			string (str): The string to format
			selected (bool): Is the string selected?
		Returns:
			union[ThemeRef, ThemeString]: The ThemeString
	"""
	formatted_string: Optional[Union[ThemeRef, ThemeString]] = None

	if string in ("<none>", "<unknown>"):
		fmt = ThemeAttr("types", "none")
		formatted_string = ThemeString(string, fmt, selected)
	elif string in ("<undefined>", "<unspecified>"):
		fmt = ThemeAttr("types", "undefined")
		formatted_string = ThemeString(string, fmt, selected)
	elif string in ("<empty>", "<unset>"):
		fmt = ThemeAttr("types", "unset")
		formatted_string = ThemeString(string, fmt, selected)
	elif string == "<not ready>":
		fmt = color_status_group(StatusGroup.NOT_OK)
		formatted_string = ThemeString(string, fmt, selected)

	return formatted_string

def format_list(items: Any,
		fieldlen: int,
		pad: int,
		ralign: bool,
		selected: bool,
		item_separator: Optional[ThemeRef] = None,
		field_separators: Optional[List[ThemeRef]] = None,
		field_colors: Optional[List[ThemeAttr]] = None,
		ellipsise: int = -1,
		ellipsis: Optional[ThemeRef] = None,
		field_prefixes: Optional[List[ThemeRef]] = None,
		field_suffixes: Optional[List[ThemeRef]] = None,
		mapping: Optional[Dict] = None) ->\
			List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []
	totallen = 0

	if item_separator is None:
		item_separator = ThemeRef("separators", "list", selected)

	if ellipsis is None:
		ellipsis = ThemeRef("separators", "ellipsis", selected)

	if field_separators is None:
		field_separators = [ThemeRef("separators", "field", selected)]

	if field_colors is None:
		field_colors = [ThemeAttr("types", "generic")]

	if not isinstance(field_separators, list):
		raise TypeError(f"field_separators should be a list of ThemeRef, not a single tuple; {field_separators}")

	if not isinstance(field_colors, list):
		raise TypeError(f"field_colors should be a list of ThemeAttr, not a single tuple; {field_colors}")

	if not isinstance(items, list):
		items = [items]

	if mapping is None:
		mapping = {}

	elcount = 0
	skip_separator = True

	for item in items:
		if len(array) > 0:
			item_sep = item_separator
			item_sep.selected = selected
			totallen += len(item_sep)
			array.append(item_sep)
			elcount += 1

		if elcount == ellipsise:
			ell = ellipsis
			ell.selected = selected
			totallen += len(ell)
			array.append(ellipsis)
			break

		# Treat all types as tuples no matter if they are; since tuples consist of 2+ elements we add None
		if not isinstance(item, tuple):
			item = (item, None)

		for i in range(0, len(item)):
			if item[i] is None:
				continue

			string = str(item[i])

			if len(string) == 0:
				continue

			if i > 0 and not skip_separator:
				field_sep = field_separators[min(i - 1, len(field_separators) - 1)]
				field_sep.selected = selected
				totallen += len(field_sep)
				array.append(field_sep)

			if (tmp := format_special(string, selected)) is not None:
				formatted_string = tmp
			else:
				default_field_color = cast(ThemeAttr, field_colors[min(i, len(field_colors) - 1)])
				formatted_string, __string = map_value(string, selected = selected, default_field_color = default_field_color, mapping = mapping)

			# OK, we know now that we will be appending the field, so do the prefix
			if field_prefixes is not None and i < len(field_prefixes):
				if isinstance(field_prefixes[i], tuple):
					totallen += len(field_prefixes[i])
					array.append(field_prefixes[i])
				else:
					for prefix in field_prefixes:
						pref = prefix
						pref.selected = selected
						totallen += len(pref)
						array.append(pref)
			array.append(formatted_string)
			totallen += len(string)
			# And now the suffix
			if field_suffixes is not None and i < len(field_suffixes):
				if isinstance(field_suffixes[i], tuple):
					totallen += len(field_suffixes[i])
					array.append(field_suffixes[i])
				else:
					for suffix in field_suffixes:
						suff = suffix
						suff.selected = selected
						totallen += len(suff)
						array.append(suff)
				# RequestPrincipals[*@example.com]
			skip_separator = False

	return align_and_pad(array, pad, fieldlen, totallen, ralign, selected)

# references is unused for now, but will eventually be used to compare against
# reference values (such as using other paths to get the range, instead of getting
# it static from formatting#mapping)
# pylint: disable=unused-argument
def map_value(value: Any,
	      references: Any = None,
	      selected: bool = False,
	      default_field_color: ThemeAttr = ThemeAttr("types", "generic"),
	      mapping: Optional[Dict] = None) ->\
			Tuple[Union[ThemeRef, ThemeString], str]:
	# If we lack a mapping, use the default color for this field
	if mapping is None or len(mapping) == 0:
		return ThemeString(value, default_field_color, selected), value

	substitutions = deep_get(mapping, DictPath("substitutions"), {})
	ranges = deep_get(mapping, DictPath("ranges"), [])
	match_case = deep_get(mapping, DictPath("match_case"), True)
	_mapping = deep_get(mapping, DictPath("mappings"), {})

	field_colors = None

	if value in substitutions:
		# We do not need to check for bool, since it is a subclass of int
		if isinstance(value, int):
			value = substitutions[f"__{str(value)}"]
		else:
			value = substitutions[value]

		# If the substitution is a dict it is either a ThemeRef to a separator or a string,
		# or a ThemeString
		if isinstance(value, dict):
			context: str = deep_get(value, DictPath("context"), "main")
			attr_ref: str = deep_get(value, DictPath("type"))
			string: str = deep_get(value, DictPath("string"))
			if string is None:
				themeref = ThemeRef(context, attr_ref, selected)
				return themeref, str(themeref)
			themestring = ThemeString(string, ThemeAttr(context, attr_ref))
			return themestring, str(themestring)
		if isinstance(value, ThemeRef):
			return value, str(value)

	# OK, so we want to output output_value, but compare using reference_value
	if isinstance(value, tuple) and len(ranges) > 0:
		output_value, reference_value = value
	else:
		output_value = value
		reference_value = value

	if isinstance(reference_value, (int, float)) and len(ranges) > 0:
		default_index = -1
		for i in range(0, len(ranges)):
			if deep_get(ranges[i], DictPath("default"), False):
				if default_index != -1:
					raise ValueError("Range cannot contain more than one default")
				default_index = i
				continue
			_min = deep_get(ranges[i], DictPath("min"))
			_max = deep_get(ranges[i], DictPath("max"))
			if (_min is None or reference_value >= _min) and (_max is None or reference_value < _max):
				field_colors = deep_get(ranges[i], DictPath("field_colors"))
				break
		if field_colors is None and default_index != -1:
			field_colors = deep_get(ranges[default_index], DictPath("field_colors"))
		string = str(output_value)
	elif isinstance(reference_value, (str, bool)) or len(ranges) == 0:
		string = str(output_value)
		_string = string
		if not match_case:
			matched = False
			if string in _mapping and string.lower() in _mapping and string != string.lower():
				raise ValueError("When using match_case == False the mapping cannot contain keys that only differ in case")
			for key in _mapping:
				if key.lower() == string.lower():
					_string = key
				matched = True
			if not matched and "__default" in _mapping:
				_string = "__default"
		elif _string not in _mapping and "__default" in _mapping:
			_string = "__default"
		field_colors = deep_get(_mapping, DictPath(f"{_string}#field_colors"))
	else:
		raise TypeError(f"Unknown type {type(value)} for mapping/range")

	if field_colors is not None:
		context = deep_get(field_colors[0], DictPath("context"), "main")
		attr_ref = deep_get(field_colors[0], DictPath("type"))
		fmt = ThemeAttr(context, attr_ref)
	else:
		fmt = ThemeAttr("types", "generic")
	return ThemeString(string, fmt, selected), string

def align_and_pad(array: List[Union[ThemeRef, ThemeString]],
		  pad: int,
		  fieldlen: int,
		  stringlen: int,
		  ralign: bool,
		  selected: bool) ->\
			List[Union[ThemeRef, ThemeString]]:
	tmp_array: List[Union[ThemeRef, ThemeString]] = []
	if ralign:
		tmp_array.append(ThemeString("".ljust(fieldlen - stringlen), ThemeAttr("types", "generic"), selected))
		tmp_array += array
	else:
		tmp_array += array
		tmp_array.append(ThemeString("".ljust(fieldlen - stringlen), ThemeAttr("types", "generic"), selected))
	if pad > 0:
		tmp_array.append(ThemeRef("separators", "pad", selected))
	return tmp_array

def format_numerical_with_units(string: str,
				ftype: str,
				selected: bool,
				non_units: Optional[Set] = None,
				separator_lookup: Optional[Dict] = None) ->\
					List[Union[ThemeRef, ThemeString]]:
	substring = ""
	array: List[Union[ThemeRef, ThemeString]] = []
	numeric = None
	# This is necessary to be able to use pop
	liststring = list(string)

	if separator_lookup is None:
		separator_lookup = {}

	if "default" not in separator_lookup:
		separator_lookup["default"] = ThemeAttr("types", "unit")

	if non_units is None:
		non_units = set("0123456789")
	else:
		non_units = set(non_units)

	while len(liststring) > 0:
		char = liststring.pop(0)
		if numeric is None:
			numeric = char in non_units
			substring += char
		elif numeric:
			# Do we need to flush?
			if not char in non_units:
				if selected is None:
					array.append(ThemeString(substring, ThemeAttr("types", ftype)))
				else:
					array.append(ThemeString(substring, ThemeAttr("types", ftype), selected))
				substring = ""
				numeric = False

			substring += char
		else:
			# Do we need to flush?
			if char in non_units:
				fmt = cast(ThemeAttr, deep_get_with_fallback(separator_lookup, [DictPath(substring), DictPath("default")]))
				if selected is None:
					array.append(ThemeString(substring, fmt))
				else:
					array.append(ThemeString(substring, fmt, selected))
				substring = ""
				numeric = True
			substring += char

		if len(liststring) == 0:
			if numeric:
				if selected is None:
					array.append(ThemeString(substring, ThemeAttr("types", ftype)))
				else:
					array.append(ThemeString(substring, ThemeAttr("types", ftype), selected))
			else:
				fmt = cast(ThemeAttr, deep_get_with_fallback(separator_lookup, [DictPath(substring), DictPath("default")]))
				if selected is None:
					array.append(ThemeString(substring, fmt))
				else:
					array.append(ThemeString(substring, fmt, selected))

	if len(array) == 0:
		array = [
			ThemeString("", ThemeAttr("types", "generic"), selected)
		]

	return array

def generator_age_raw(value: Union[int, str],
		      selected: bool) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []

	if value == -1:
		string = ""
	elif isinstance(value, str):
		string = value
	else:
		string = cmtlib.seconds_to_age(value, negative_is_skew = True)

	if (tmp := format_special(string, selected)) is not None:
		array = [tmp]
	elif string == "<clock skew detected>":
		fmt = ThemeAttr("main", "status_not_ok")
		array = [
			ThemeString(string, fmt, selected)
		]
	else:
		array = format_numerical_with_units(string, "age", selected)

	return array

# pylint: disable=unused-argument
def generator_age(obj: Dict,
		  field: str,
		  fieldlen: int,
		  pad: int,
		  ralign: bool,
		  selected: bool,
		  **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []

	value = getattr(obj, field)

	array = generator_age_raw(value, selected)

	return align_and_pad(array, pad, fieldlen, themearray_len(array), ralign, selected)

def generator_address(obj: Dict,
		      field: str,
		      fieldlen: int,
		      pad: int,
		      ralign: bool,
		      selected: bool,
		      **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	item_separator = deep_get(formatting, DictPath("item_separator"))

	items = getattr(obj, field, [])
	if items is None:
		items = []

	if isinstance(items, str) and items in ("<unset>", "<none>"):
		return format_list([items], fieldlen, pad, ralign, selected)

	if isinstance(items, (str, tuple)):
		items = [items]

	separator_lookup = {}

	separators = deep_get(formatting, DictPath("field_separators"))
	if len(separators) == 0:
		separators = [ThemeRef("separators", "ipv4address", selected), ThemeRef("separators", "ipv6address", selected), ThemeRef("separators", "ipmask", selected)]

	for separator in separators:
		string = str(separator)
		separator_lookup[string] = separator

	array: List[Union[ThemeRef, ThemeString]] = []

	subnet = False

	for item in items:
		_vlist = []
		tmp = ""
		for ch in item:
			if ch in separator_lookup:
				if len(tmp) > 0:
					if subnet:
						_vlist.append(ThemeString(tmp, ThemeAttr("types", "ipmask"), selected))
					else:
						_vlist.append(ThemeString(tmp, ThemeAttr("types", "address"), selected))
				_vlist.append(separator_lookup[ch])
				tmp = ""

				if ch == "/":
					subnet = True
			else:
				tmp += ch

		if len(tmp) > 0:
			if subnet:
				_vlist.append(ThemeString(tmp, ThemeAttr("types", "ipmask"), selected))
			else:
				_vlist.append(ThemeString(tmp, ThemeAttr("types", "address"), selected))
		if len(array) > 0:
			array.append(item_separator)
		array += _vlist

	return align_and_pad(array, pad, fieldlen, themearray_len(array), ralign, selected)

def generator_basic(obj: Dict,
		    field: str,
		    fieldlen: int,
		    pad: int,
		    ralign: bool,
		    selected: bool,
		    **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []
	value = getattr(obj, field)
	string = str(value)
	field_colors = deep_get(formatting, DictPath("field_colors"), [ThemeAttr("types", "generic")])

	if string == "None":
		string = "<none>"

	if string in ("<none>", "<unknown>"):
		fmt = ThemeAttr("types", "none")
	elif string == "<default>":
		fmt = ThemeAttr("types", "default")
	elif string in ("<undefined>", "<unspecified>"):
		fmt = ThemeAttr("types", "undefined")
	elif string in ("<empty>", "<unset>"):
		fmt = ThemeAttr("types", "unset")
	else:
		context, attr_ref = field_colors[0]
		fmt = ThemeAttr(context, attr_ref)

	array = [
		ThemeString(string, fmt, selected)
	]

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

# pylint: disable=unused-argument
def generator_hex(obj: Dict,
		  field: str,
		  fieldlen: int,
		  pad: int,
		  ralign: bool,
		  selected: bool,
		  **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []
	value = getattr(obj, field)
	string = str(value)

	array = format_numerical_with_units(string, "field", selected, non_units = set("0123456789abcdefABCDEF"))

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

def generator_list(obj: Dict,
		   field: str,
		   fieldlen: int,
		   pad: int,
		   ralign: bool,
		   selected: bool,
		   **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	items = getattr(obj, field)

	item_separator = deep_get(formatting, DictPath("item_separator"))
	if item_separator is None:
		item_separator = ThemeRef("separators", "list", selected)

	field_separators = deep_get(formatting, DictPath("field_separators"))
	if field_separators is None:
		field_separators = [ThemeRef("separators", "field", selected)]

	field_colors = deep_get(formatting, DictPath("field_colors"))
	if field_colors is None:
		field_colors = [ThemeAttr("types", "field")]

	ellipsise = deep_get(formatting, DictPath("ellipsise"), -1)

	ellipsis = deep_get(formatting, DictPath("ellipsis"))
	if ellipsis is None:
		ellipsis = ThemeRef("separators", "ellipsis", selected)

	field_prefixes = deep_get(formatting, DictPath("field_prefixes"))
	field_suffixes = deep_get(formatting, DictPath("field_suffixes"))

	mapping = deep_get(formatting, DictPath("mapping"), {})

	return format_list(items, fieldlen, pad, ralign, selected,
			   item_separator = item_separator,
			   field_separators = field_separators,
			   field_colors = field_colors,
			   ellipsise = ellipsise,
			   ellipsis = ellipsis,
			   field_prefixes = field_prefixes,
			   field_suffixes = field_suffixes,
			   mapping = mapping)

def generator_list_with_status(obj: Dict,
			       field: str,
			       fieldlen: int,
			       pad: int,
			       ralign: bool,
			       selected: bool,
			       **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	items = getattr(obj, field)
	if isinstance(items, tuple):
		items = [items]

	item_separator = deep_get(formatting, DictPath("item_separator"))
	if item_separator is None:
		item_separator = ThemeRef("separators", "list", selected)

	field_separators = deep_get(formatting, DictPath("field_separators"))
	if field_separators is None:
		field_separators = [ThemeRef("separators", "field", selected)]

	ellipsise = deep_get(formatting, DictPath("ellipsise"), -1)

	ellipsis = deep_get(formatting, DictPath("ellipsis"))
	if ellipsis is None:
		ellipsis = ThemeRef("separators", "ellipsis", selected)

	field_prefixes = deep_get(formatting, DictPath("field_prefixes"))
	field_suffixes = deep_get(formatting, DictPath("field_prefixes"))

	# XXX: Well, this works:ish, but it is ugly beyond belief
	#      it would be solved so much better with a mapping that uses a secondary value
	newitems = []
	field_colors = [
		ThemeAttr("main", "status_done"),
		ThemeAttr("main", "status_ok"),
		ThemeAttr("main", "status_pending"),
		ThemeAttr("main", "status_warning"),
		ThemeAttr("main", "status_admin"),
		ThemeAttr("main", "status_not_ok"),
		ThemeAttr("main", "status_unknown"),
		ThemeAttr("main", "status_critical"),
		ThemeAttr("types", "generic")]
	field_separators = [ThemeRef("separators", "no_pad", selected)]

	for item, status in items:
		if status == StatusGroup.DONE:
			newitems.append((item))
		if status == StatusGroup.OK:
			newitems.append(("", item))
		elif status == StatusGroup.PENDING:
			newitems.append(("", "", item))
		elif status == StatusGroup.WARNING:
			newitems.append(("", "", "", item))
		elif status == StatusGroup.ADMIN:
			newitems.append(("", "", "", "", item))
		elif status == StatusGroup.NOT_OK:
			newitems.append(("", "", "", "", "", item))
		elif status == StatusGroup.UNKNOWN:
			newitems.append(("", "", "", "", "", "", item))
		elif status == StatusGroup.CRIT:
			newitems.append(("", "", "", "", "", "", "", item))
		elif status == StatusGroup.NEUTRAL:
			newitems.append(("", "", "", "", "", "", "", "", item))
		else:
			newitems.append(("", "", "", "", "", "", "", "", item))

	return format_list(newitems, fieldlen, pad, ralign, selected,
			   item_separator = item_separator,
			   field_separators = field_separators,
			   field_colors = field_colors,
			   ellipsise = ellipsise,
			   ellipsis = ellipsis,
			   field_prefixes = field_prefixes,
			   field_suffixes = field_suffixes)

# pylint: disable=unused-argument
def generator_mem(obj: Dict,
		  field: str,
		  fieldlen: int,
		  pad: int,
		  ralign: bool,
		  selected: bool,
		  **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []
	free, total = getattr(obj, field)

	if free is None and total is None:
		return generator_basic(obj, field, fieldlen, pad, ralign, selected)

	used = f"{100 - (100 * int(free) / int(total)):0.1f}"

	if float(used) < 80.0:
		fmt = ThemeAttr("types", "watermark_low")
	elif float(used) < 90.0:
		fmt = ThemeAttr("types", "watermark_medium")
	else:
		fmt = ThemeAttr("types", "watermark_high")

	total = f"{int(total) / (1024 * 1024):0.1f}"
	unit = "GiB"

	array = [
		ThemeString(used, fmt, selected),
		ThemeRef("separators", "percentage", selected),
		ThemeString(" ", fmt, selected),
		ThemeRef("separators", "fraction", selected),
		ThemeString(" ", fmt, selected),
		ThemeString(total, ThemeAttr("types", "numerical"), selected),
		ThemeString(unit, ThemeAttr("types", "unit"), selected),
	]
	stringlen = themearray_len(array)

	return align_and_pad(array, pad, fieldlen, stringlen, ralign, selected)

# pylint: disable=unused-argument
def generator_mem_single(obj: Dict,
			 field: str,
			 fieldlen: int,
			 pad: int,
			 ralign: bool,
			 selected: bool,
			 **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []
	value = getattr(obj, field)
	string = str(value)

	array = format_numerical_with_units(string, "numerical", selected)

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

# pylint: disable=unused-argument
def generator_numerical(obj: Dict,
			field: str,
			fieldlen: int,
			pad: int,
			ralign: bool,
			selected: bool,
			**formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []

	value = getattr(obj, field)

	if value == -1:
		string = ""
	else:
		string = str(value)

	fmt = ThemeAttr("types", "numerical")

	array = [
		ThemeString(string, fmt, selected)
	]

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

def generator_numerical_with_units(obj: Dict,
				   field: str,
				   fieldlen: int,
				   pad: int,
				   ralign: bool,
				   selected: bool,
			           **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []

	value = getattr(obj, field)

	if value in ("<none>", "<unset>", "<unknown>"):
		fmt = ThemeAttr("types", "none")
		array = [ThemeString(value, fmt, selected)]
		return align_and_pad(array, pad, fieldlen, len(value), ralign, selected)

	if value == -1 and not deep_get(formatting, DictPath("allow_signed")):
		string = ""
	else:
		string = str(value)

	array = format_numerical_with_units(string, "numerical", selected)

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

def generator_status(obj: Dict,
		     field: str,
		     fieldlen: int,
		     pad: int,
		     ralign: bool,
		     selected: bool,
		     **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []

	status = getattr(obj, field)
	status_group = getattr(obj, "status_group")
	fmt = color_status_group(status_group)

	array = [
		ThemeString(status, fmt, selected)
	]
	stringlen = len(status)

	return align_and_pad(array, pad, fieldlen, stringlen, ralign, selected)

def generator_timestamp(obj: Dict,
			field: str,
			fieldlen: int,
			pad: int,
			ralign: bool,
			selected: bool,
			**formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []

	value = getattr(obj, field)

	if isinstance(value, str):
		if (tmp := format_special(value, selected)) is not None:
			array = [tmp]
			string = value

	if len(array) == 0:
		string = datetime_to_timestamp(value)
		if value is None:
			array = [
				ThemeString(string, ThemeAttr("types", "generic"), selected)
			]
		elif value == datetime.fromtimestamp(0).astimezone():
			array = [
				ThemeString(string, ThemeAttr("types", "generic"), selected)
			]
		else:
			array = format_numerical_with_units(string, "timestamp", selected)

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

def generator_timestamp_with_age(obj: Dict,
				 field: str,
				 fieldlen: int,
				 pad: int,
				 ralign: bool,
				 selected: bool,
				 **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []
	values = getattr(obj, field)

	if len(values) > 2 and len(deep_get(formatting, DictPath("field_colors"), [])) < 2:
		raise ValueError("Received more than 2 fields for timestamp_with_age but no formatting to specify what the values signify")

	if len(values) == 2:
		if values[0] is None:
			array = [
				ThemeString("<none>", ThemeAttr("types", "none"), selected)
			]
		else:
			timestamp_string = datetime_to_timestamp(values[0])
			array = format_numerical_with_units(timestamp_string, "timestamp", selected)
			array += [
				ThemeString(" (", ThemeAttr("types", "generic"), selected)
			]
			array += generator_age_raw(values[1], selected)
			array += [
				ThemeString(")", ThemeAttr("types", "generic"), selected)
			]
	else:
		array = []

		for i in range(0, len(values)):
			# If there's no formatting for this field we assume that
			# it is a generic string
			if len(deep_get(formatting, DictPath("field_colors"), [])) <= i:
				fmt = ThemeAttr("types", "generic")
				array += [ThemeString(values[i], fmt, selected)]
			elif formatting["field_colors"][i] == ThemeAttr("types", "timestamp"):
				if values[i] is None:
					array += [
						ThemeString("<unset>", ThemeAttr("types", "none"), selected)
					]
					break

				timestamp = timestamp_to_datetime(values[i])
				timestamp_string = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
				array += format_numerical_with_units(timestamp_string, "timestamp", selected)
			elif formatting["field_colors"][i] == ThemeAttr("types", "age"):
				array += generator_age_raw(values[i], selected)
			else:
				array += [
					ThemeString(values[i], formatting["field_colors"][i], selected)
				]

	return align_and_pad(array, pad, fieldlen, themearray_len(array), ralign, selected)

def generator_value_mapper(obj: Dict,
			   field: "str",
			   fieldlen: int,
			   pad: int,
			   ralign: bool,
			   selected: bool,
			   **formatting: Dict) -> List[Union[ThemeRef, ThemeString]]:
	array: List[Union[ThemeRef, ThemeString]] = []
	value = getattr(obj, field)

	default_field_color = cast(ThemeAttr, deep_get(formatting, DictPath("field_colors"), [("types", "generic")])[0])

	formatted_string, string = map_value(value, selected = selected,default_field_color = default_field_color,
					     mapping = deep_get(formatting, DictPath("mapping"), {}))
	array = [
		formatted_string
	]
	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

def processor_timestamp(obj: Dict, field: str) -> str:
	value = getattr(obj, field)

	if value is None:
		return ""

	if isinstance(value, str):
		return value

	string = value.astimezone().strftime("%Y-%m-%d %H:%M:%S")
	return string

def processor_timestamp_with_age(obj: Dict, field: str, formatting: Dict) -> str:
	values = getattr(obj, field)

	if len(values) > 2 and len(deep_get(formatting, DictPath("field_colors"), [])) < 2:
		raise ValueError("Received more than 2 fields for timestamp_with_age but no formatting to specify what the values signify")

	if len(values) == 2:
		if values[0] is None:
			array: List[Union[ThemeRef, ThemeString]] = [
				ThemeString("<none>", ThemeAttr("types", "none"))
			]
		else:
			timestamp_string = datetime_to_timestamp(values[0])
			array = format_numerical_with_units(timestamp_string, "timestamp", False)
			array += [
				ThemeString(" (", ThemeAttr("types", "generic"))
			]
			array += generator_age_raw(values[1], False)
			array += [
				ThemeString(")", ThemeAttr("types", "generic"))
			]
	else:
		array = []

		for i in range(0, len(values)):
			# If there is no formatting for this field we assume that
			# it is a generic string
			if len(deep_get(formatting, DictPath("field_colors"), [])) <= i:
				fmt = ThemeAttr("types", "generic")
				array += [
					ThemeString(values[i], fmt)
				]
			elif formatting["field_colors"][i] == ThemeAttr("types", "timestamp"):
				if values[i] is None:
					array += [
						ThemeString("<none>", ThemeAttr("types", "none"))
					]
				else:
					# timestamp_string = datetime_to_timestamp(values[0])
					array += format_numerical_with_units(values[i], "timestamp", False)
			elif formatting["field_colors"][i] == ThemeAttr("types", "age"):
				array += generator_age_raw(values[i], False)
			else:
				array += [
					ThemeString(values[i], formatting["field_colors"][i])
				]

	return themearray_to_string(array)

# For the list processor to work we need to know the length of all the separators
# pylint: disable-next=too-many-arguments
def processor_list(obj: Dict, field: str, item_separator: ThemeRef, field_separators: List[Union[ThemeRef, ThemeString]],
		   ellipsise: bool, ellipsis: ThemeRef,
		   field_prefixes: List[Union[Tuple[str, str], ThemeString, List[Union[Tuple[str, str], ThemeString]]]],
		   field_suffixes: List[Union[Tuple[str, str], ThemeString, List[Union[Tuple[str, str], ThemeString]]]]) -> str:
	items = getattr(obj, field)

	strings: List[str] = []

	elcount = 0
	skip_separator = True

	if isinstance(items, tuple):
		items = [items]

	for item in items:
		if elcount == ellipsise:
			strings.append(themearray_to_string([ellipsis]))
			break

		if not isinstance(item, tuple):
			item = (item, None)

		# Join all elements of the field into one string
		string = ""

		for i in range(0, len(item)):
			if item[i] is None:
				continue

			tmp = str(item[i])

			if len(tmp) == 0:
				continue

			if i > 0 and not skip_separator:
				string += themearray_to_string([field_separators[min(i - 1, len(field_separators) - 1)]])

			if field_prefixes is not None and i < len(field_prefixes):
				if isinstance(field_prefixes[i], tuple):
					string += themearray_to_string(cast(List[Union[ThemeRef, ThemeString]], [field_prefixes[i]]))
				else:
					for item_ in cast(List[Union[ThemeRef, ThemeString]], field_prefixes[i]):
						string += themearray_to_string(cast(List[Union[ThemeRef, ThemeString]], [item_]))
			string += tmp
			if field_suffixes is not None and i < len(field_suffixes):
				if isinstance(field_suffixes[i], tuple):
					string += themearray_to_string(cast(List[Union[ThemeRef, ThemeString]], [field_suffixes[i]]))
				else:
					for item_ in cast(List[Union[ThemeRef, ThemeString]], field_suffixes[i]):
						string += themearray_to_string(cast(List[Union[ThemeRef, ThemeString]], [item_]))
			skip_separator = False

		strings.append(string)
		elcount += 1

	vstring = themearray_to_string([item_separator]).join(strings)

	return vstring

# For the list processor to work we need to know the length of all the separators
# pylint: disable-next=too-many-arguments

def processor_list_with_status(obj: Dict, field: str, item_separator: ThemeRef, field_separators: List[Union[ThemeRef, ThemeString]],
			       ellipsise: bool, ellipsis: ThemeRef, field_prefixes: List[ThemeString], field_suffixes: List[ThemeString]) -> str:
	items = getattr(obj, field)

	strings = []

	elcount = 0
	skip_separator = True

	newitems = []
	for item in items:
		newitems.append(item[0])

	for item in newitems:
		if elcount == ellipsise:
			strings.append(themearray_to_string([ellipsis]))
			break

		if not isinstance(item, tuple):
			item = (item, None)

		# Join all elements of the field into one string
		string = ""

		for i in range(0, len(item)):
			if item[i] is None:
				continue

			tmp = str(item[i])

			if len(tmp) == 0:
				continue

			if i > 0 and not skip_separator:
				string += themearray_to_string([field_separators[min(i - 1, len(field_separators) - 1)]])

			if field_prefixes is not None and i < len(field_prefixes):
				string += themearray_to_string([field_prefixes[i]])
			string += tmp
			if field_suffixes is not None and i < len(field_suffixes):
				string += themearray_to_string([field_suffixes[i]])
			skip_separator = False

		strings.append(string)
		elcount += 1

	vstring = themearray_to_string([item_separator]).join(strings)

	return vstring

def processor_age(obj: Dict, field: str) -> str:
	seconds = getattr(obj, field)
	return cmtlib.seconds_to_age(seconds, negative_is_skew = True)

def processor_mem(obj: Dict, field: str) -> str:
	free, total = getattr(obj, field)

	string = f"{100 - (100 * int(free)) / int(total):0.1f}"
	string += str(ThemeRef("separators", "percentage"))
	string += " "
	string += str(ThemeRef("separators", "fraction"))
	string += " "
	string += f"{int(total) / (1024 * 1024):0.1f}"
	string += "GiB"

	return string

default_processor: Dict[Callable, Callable] = {
	generator_age: processor_age,
	generator_list: processor_list,
	generator_list_with_status: processor_list_with_status,
	generator_mem: processor_mem,
	generator_timestamp: processor_timestamp,
}

# The return type of the formatting will be the same
# as the type of the default, so default == None is a programming error
def get_formatting(field: Dict[str, Any], formatting: str, default: Dict[str, Any]) -> Union[List[Union[ThemeAttr, ThemeString, ThemeRef]], int, ThemeRef]:
	result: List[Union[ThemeAttr, ThemeString, ThemeRef]] = []
	items: Union[Dict, List[Dict]] = deep_get(field, DictPath(f"formatting#{formatting}"))

	if items is None:
		return deep_get(default, DictPath(f"{formatting}"))

	if not isinstance(items, (dict, list)):
		raise TypeError(f"Formatting must be either list[union[dict, ThemeAttr, ThemeRef, ThemeString]] or list[list[dict]]; is type: {type(items)}")

	if default is None:
		raise ValueError(f"default cannot be None for field {field}, formatting {formatting}; this is a programming error")

	if len(items) < 1:
		raise ValueError(f"field {field}, formatting {formatting}: format list item is empty; this is likely an error in the view file")

	if formatting in ("item_separator", "field_separators", "ellipsis", "field_prefixes", "field_suffixes"):
		default_context = "separators"
	elif formatting == "field_colors":
		default_context = "types"

	if isinstance(items, dict):
		context = deep_get(items, DictPath("context"), default_context)
		key = deep_get(items, DictPath("type"))
		return ThemeRef(context, key)

	for item in items:
		# field_prefixes/suffixes can be either list[Union[ThemeRef, ThemeString]] or Union[ThemeRef, ThemeString]; in the latter case turn it into a list
		if isinstance(item, (ThemeAttr, ThemeRef, ThemeString)):
			result.append(item)
		elif isinstance(item, dict):
			context = deep_get(item, DictPath("context"), default_context)
			key = deep_get(item, DictPath("type"))
			if formatting in ("field_separators", "field_prefixes", "field_suffixes"):
				result.append(ThemeRef(context, key))
			elif formatting == "field_colors":
				result.append(ThemeAttr(context, key))
			else:
				raise TypeError(f"Unknown formatting type {formatting}")
		else:
			raise TypeError(f"Formatting is of invalid type {type(item)}")

	return result

formatter_to_generator_and_processor: Dict[str, Dict[str, Any]] = {
	"mem": {
		"generator": generator_mem_single,
		"processor": None,
	},
	"float": {
		# The generator is the same, but the name is unfortunate
		"generator": generator_mem_single,
		"processor": None,
	},
	"list": {
		"generator": generator_list,
		"processor": processor_list,
	},
	"list_with_status": {
		"generator": generator_list_with_status,
		"processor": processor_list_with_status,
	},
	"hex": {
		"generator": generator_hex,
		"processor": None,
	},
	"numerical": {
		"generator": generator_numerical,
		"processor": None,
	},
	"numerical_with_units": {
		"generator": generator_numerical_with_units,
		"processor": None,
	},
	"address": {
		"generator": generator_address,
		"processor": None,
		"field_separators_default": [],
	},
	"timestamp": {
		"generator": generator_timestamp,
		"processor": processor_timestamp,
	},
	"timestamp_with_age": {
		"generator": generator_timestamp_with_age,
		"processor": processor_timestamp_with_age,
	},
	"age": {
		"generator": generator_age,
		"processor": processor_age,
	},
	"value_mapper": {
		"generator": generator_value_mapper,
		"processor": None,
	},
}

# This generates old-style fields from new-style fields
def get_formatter(field: Dict) -> Dict:
	tmp_field = {}

	formatter = deep_get(field, DictPath("formatter"))
	generator = deep_get(field, DictPath("generator"), generator_basic)
	if isinstance(generator, str):
		generator = deep_get(generator_allowlist, DictPath(generator), generator_basic)
	processor = deep_get(field, DictPath("processor"))

	field_separators_default = [ThemeRef("separators", "field")]

	if formatter is not None:
		if formatter not in formatter_to_generator_and_processor:
			msg = [
				[("get_formatter()", "emphasis"),
				 (" called with invalid argument(s):", "error")],
				[("field = ", "default"),
				 (yaml.dump(field), "argument"),
				 (" has an invalid ", "default"),
				 ("formatter", "argument")]
			]

			unformatted_msg, formatted_msg = ANSIThemeString.format_error_msg(msg)

			raise ProgrammingError(unformatted_msg,
					       severity = LogLevel.ERR,
					       formatted_msg = formatted_msg)

		generator = deep_get(formatter_to_generator_and_processor, DictPath(f"{formatter}#generator"))
		processor = deep_get(formatter_to_generator_and_processor, DictPath(f"{formatter}#processor"))
		field_separators_default = deep_get(formatter_to_generator_and_processor, DictPath(f"{formatter}#field_separators_default"), field_separators_default)

	theme = get_theme_ref()
	if deep_get(field, DictPath("formatting#field_colors")) is None:
		if "type" in field and field["type"] in theme["types"]:
			field_colors: List[ThemeAttr] = [ThemeAttr("types", deep_get(field, DictPath("type")))]
		else:
			field_colors = cast(List[ThemeAttr], get_formatting(field, "field_colors", {"field_colors": [ThemeAttr("types", "field")]}))
	else:
		field_colors = cast(List[ThemeAttr], get_formatting(field, "field_colors", {"field_colors": [ThemeAttr("types", "field")]}))

	field_prefixes = get_formatting(field, "field_prefixes", {"field_prefixes": []})
	field_suffixes = get_formatting(field, "field_suffixes", {"field_suffixes": []})
	field_separators = get_formatting(field, "field_separators", {"field_separators": field_separators_default})
	ellipsise = deep_get(field, DictPath("formatting#ellipsise"), {"ellipsise": -1})
	ellipsis = get_formatting(field, "ellipsis", {"ellipsis": ThemeRef("separators", "ellipsis")})
	item_separator = get_formatting(field, "item_separator", {"item_separator": ThemeRef("separators", "list")})
	mapping = deep_get(field, DictPath("formatting#mapping"), {})

	tmp_field["generator"] = generator
	tmp_field["processor"] = processor
	# Fix all of these to use the new format
	tmp_field["field_colors"] = field_colors
	tmp_field["field_prefixes"] = field_prefixes
	tmp_field["field_suffixes"] = field_suffixes
	tmp_field["field_separators"] = field_separators
	tmp_field["ellipsise"] = ellipsise
	tmp_field["ellipsis"] = ellipsis
	tmp_field["item_separator"] = item_separator
	tmp_field["mapping"] = mapping
	if "align" in field:
		align = deep_get(field, DictPath("align"), "left")
		tmp_field["ralign"] = align == "right"

	formatting = {
		"item_separator": item_separator,
		"field_separators": field_separators,
		"field_colors": field_colors,
		"ellipsise": ellipsise,
		"ellipsis": ellipsis,
		"field_prefixes": field_prefixes,
		"field_suffixes": field_suffixes,
		"mapping": mapping,
	}

	tmp_field["formatting"] = formatting

	return tmp_field

builtin_fields: Dict[str, Dict[str, Any]] = {
	"age": {
		"header": "Age:",
		"paths": [{
			"path": ["metadata#creationTimestamp"],
			"type": "timestamp",
			"default": -1,
		}],
		"formatter": "age",
		"align": "right",
	},
	"api_support": {
		"header": "API Support:",
		"datagetter": datagetters.datagetter_api_support,
		"formatter": "list",
	},
	"mem": {
		"header": "Mem% / Total:",
		"path": (r"^(\d+).*", ["status#allocatable#memory", "status#capacity#memory"]),
		"datagetter": datagetters.datagetter_regex_split_to_tuples,
		"generator": generator_mem,
		"ralign": True,
	},
	"name": {
		"header": "Name:",
		"path": "metadata#name",
		"type": "str",
	},
	"namespace": {
		"header": "Namespace:",
		"path": "metadata#namespace",
		"type": "str",
		"formatting": {
			"field_colors": [
				{
					"type": "namespace",
				},
			],
		},
	},
	"pod_status": {
		"header": "Status:",
		"datagetter": datagetters.datagetter_pod_status,
		"generator": generator_status,
	},
}

def fieldgenerator(view: str, selected_namespace: str = "", **kwargs: Any) -> Tuple[Optional[Dict], Optional[List[str]], Optional[str], bool]:
	"""
	Generate a dict with the fields necessary for a view

		Parameters:
			view (str): The view to generate the dict for
			field_index (str): The field_index to use
			field_indexes (dict): A dict with the field indexes to choose between
			fields (dict): The fields to available to the field indexes
			denylist (list[str]): Fields to exclude
		Returns:
			(field_dict, field_names, sortcolumn, sortorder_reverse):
				field_dict (dict): The generated dict
				field_names (list[str]): The fields after pruning using the denylist
				sortcolumn (str): The column to use when sorting
				sortorder_reverse (bool): Should the list be sorted in reverse order
	"""

	fields = deep_get(kwargs, DictPath("fields"))
	field_index = deep_get(kwargs, DictPath("field_index"))
	field_indexes = deep_get(kwargs, DictPath("field_indexes"))

	if field_indexes is None or len(field_indexes) == 0:
		return None, None, None, False

	field_names = copy.deepcopy(deep_get(field_indexes, DictPath(f"{field_index}#fields"), []))
	sortcolumn = deep_get(field_indexes, DictPath(f"{field_index}#sortcolumn"))
	sortorder_reverse = deep_get(field_indexes, DictPath(f"{field_index}#sortorder_reverse"), False)

	denylist = copy.deepcopy(deep_get(kwargs, DictPath("denylist"), []))

	if selected_namespace != "" and "namespace" not in denylist:
		denylist.append("namespace")

	# delete all denylisted fields
	for field in denylist:
		try:
			field_names.remove(field)
		except ValueError:
			pass

	# OK, we've pruned the denylisted fields; now we need to check
	# whether the sort column still applies, and if not try to pick
	# another sortcolumn
	if sortcolumn is None or sortcolumn not in field_names:
		if "name" in field_names:
			sortcolumn = "name"
		elif "namespace" in field_names:
			sortcolumn = "namespace"
		else:
			sortcolumn = field_names[0]

	field_dict = {}
	for field in field_names:
		if field in fields:
			field_dict[field] = deep_get(fields, DictPath(field), {})
		elif field in builtin_fields:
			field_dict[field] = deep_get(builtin_fields, DictPath(field), {})
		else:
			msg = [
				[("fieldgenerator()", "emphasis"),
				 (" called with invalid argument(s):", "error")],
				[("View ", "default"),
				 (f"{view}", "argument"),
				 (": field “", "default"),
				 (f"{field}", "argument"),
				 ("“ cannot be found in view or builtin_fields", "default")],
				[(f"View fields: {fields}", "default")],
				[(f"field_names: {field_names}", "default")],
			]

			unformatted_msg, formatted_msg = ANSIThemeString.format_error_msg(msg)

			raise ProgrammingError(unformatted_msg,
					       severity = LogLevel.ERR,
					       formatted_msg = formatted_msg)

	tmp_fields = {}

	for field_name in field_dict:
		field = deep_get(field_dict, DictPath(field_name))

		# This is a custom field, so we need to construct one that's usable here
		tmp_fields[field_name] = copy.deepcopy(field_dict[field_name])

		tmp_field = get_formatter(field)
		if tmp_field is None:
			continue

		for key, value in tmp_field.items():
			tmp_fields[field_name][key] = value
		tmp_fields[field_name]["sortkey1"] = field_name
		# If sortkey1 == sortcolumn this "fails", but it is good enough
		tmp_fields[field_name]["sortkey2"] = sortcolumn

	return tmp_fields, field_names, sortcolumn, sortorder_reverse

# Generators acceptable for direct use in view files
generator_allowlist = {
	"generator_mem": generator_mem,
	"generator_status": generator_status,
}
