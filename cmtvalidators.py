#! /usr/bin/env python3

"""
This module contains data validators, mainly for validating user input
"""

import errno
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Tuple

try:
	import validators # type: ignore
except ModuleNotFoundError: # pragma: no cover
	print("ModuleNotFoundError: Could not import validators; you may need to (re-)run `cmt-install` "
	      "or `pip3 install validators`; disabling IP-address validation.\n", file = sys.stderr)
	validators = None

from ansithemeprint import ANSIThemeString, ansithemeprint, ansithemestring_join_tuple_list
from cmttypes import deep_get, DictPath, HostNameStatus, ProgrammingError

programname = None

def validate_name(rtype: str, name: str) -> bool:
	"""
	Given a name validate whether it is valid for the given type

		Parameters:
			rtype (str): The resource type; valid types are:
				dns-label
				dns-subdomain
				path-segment
				port-name
			name (str): The name to check for validity
		Returns:
			valid (bool): True if valid, False if invalid
	"""

	invalid = False
	tmp = None
	maxlen = -1

	if name is None:
		return False

	# Safe
	name_regex = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
	# Safe
	portname_regex = re.compile(r"^([a-z0-9]+[a-z0-9-].*[a-z0-9]|[a-z0-9])$")

	if rtype in ("dns-subdomain", "dns-label"):
		if rtype == "dns-label":
			maxlen = 63
			if "." in name:
				invalid = True
		else:
			maxlen = 253

		# A dns-subdomain can be at most 253 characters long
		# and cannot start or end with "-"; it must be made up
		# of valid dns-labels; each of which are separated by "."
		# and have to meet the same standards as a dns-label
		labels = name.lower().split(".")

		for label in labels:
			if len(label) == 0 or len(label) > 63:
				invalid = True
				break

			tmp = name_regex.match(label)
			if tmp is None:
				invalid = True
	elif rtype == "path-segment":
		# XXX: Are there any other requirements? maxlen or similar?
		if name in (".", "..") or "/" in name or "%" in name:
			invalid = True
		maxlen = os.pathconf("/", "PC_NAME_MAX")
	elif rtype == "port-name":
		# Any name containing adjacent "-" is invalid
		if "--" in name:
			invalid = True
		# As is any port-name that does not contain any character in [a-z]
		if portname_regex.match(name.lower()) is None:
			invalid = True
		# A portname can be at most 15 characters long
		# and cannot start or end with "-"
		tmp = name_regex.match(name.lower())
		if tmp is None:
			invalid = True
		maxlen = 15

	return not invalid and len(name) <= maxlen

# pylint: disable-next=too-many-return-statements
def validate_fqdn(fqdn: str, message_on_error: bool = False) -> HostNameStatus:
	"""
	Verifies that a FQDN / hostname is valid

		Parameters:
			fqdn (str): The FQDN / hostname to validate
			message_on_error (bool): Should an error message be printed on error?
		Returns:
			result (HostNameStatus): The result of the validation; HostNameStatus.OK on success
	"""

	if fqdn is None or len(fqdn) == 0:
		if message_on_error:
			msg = [ansithemeprint.ANSIThemeString("Error", "error"),
			       ansithemeprint.ANSIThemeString(": A FQDN or hostname cannot be empty.", "default")]
			ansithemeprint.ansithemeprint(msg, stderr = True)
		return HostNameStatus.DNS_SUBDOMAIN_EMPTY
	if "\x00" in fqdn:
		stripped_fqdn = fqdn.replace("\x00", "<NUL>")
		msg = [ansithemeprint.ANSIThemeString("Critical", "critical"),
		       ansithemeprint.ANSIThemeString(": the FQDN / hostname ", "default"),
		       ansithemeprint.ANSIThemeString(stripped_fqdn, "hostname")]
		msg += [ansithemeprint.ANSIThemeString(" contains NUL-bytes (replaced here);\n"
					"this is either a programming error, a system error, file or memory corruption, "
					"or a deliberate attempt to bypass security; aborting.", "default")]
		ansithemeprint.ansithemeprint(msg, stderr = True)
		sys.exit(errno.EINVAL)
	if len(fqdn) > 253:
		if message_on_error:
			msg = [ansithemeprint.ANSIThemeString("Critical", "critical"),
			       ansithemeprint.ANSIThemeString(": the FQDN / hostname ", "default"),
			       ansithemeprint.ANSIThemeString(fqdn, "hostname")]
			msg = [ansithemeprint.ANSIThemeString(" is invalid; ", "default"),
			       ansithemeprint.ANSIThemeString("a FQDN cannot be more than 253 characters long.", "default")]
			ansithemeprint.ansithemeprint(msg, stderr = True)
		return HostNameStatus.DNS_SUBDOMAIN_TOO_LONG
	if fqdn != fqdn.lower():
		if message_on_error:
			msg = [ansithemeprint.ANSIThemeString("Error", "error"),
			       ansithemeprint.ANSIThemeString(": The FQDN / hostname ", "default"),
			       ansithemeprint.ANSIThemeString(fqdn, "hostname"),
			       ansithemeprint.ANSIThemeString(" is invalid; ", "default"),
			       ansithemeprint.ANSIThemeString("a FQDN / hostname must be lowercase.", "default")]
			ansithemeprint.ansithemeprint(msg, stderr = True)
		return HostNameStatus.DNS_SUBDOMAIN_WRONG_CASE
	if fqdn.startswith(".") or fqdn.endswith(".") or ".." in fqdn:
		if message_on_error:
			msg = [ansithemeprint.ANSIThemeString("Error", "error"),
			       ansithemeprint.ANSIThemeString(": The FQDN / hostname ", "default"),
			       ansithemeprint.ANSIThemeString(fqdn, "hostname"),
			       ansithemeprint.ANSIThemeString(" is invalid; ", "default"),
			       ansithemeprint.ANSIThemeString("a FQDN / hostname cannot begin or end with “.“, and must not have consecutive “.“.", "default")]
			ansithemeprint.ansithemeprint(msg, stderr = True)
		return HostNameStatus.DNS_SUBDOMAIN_INVALID_FORMAT

	dnslabels = fqdn.split(".")
	dnslabel_regex = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

	for dnslabel in dnslabels:
		if dnslabel.startswith("xn--"):
			if message_on_error:
				msg = [ansithemeprint.ANSIThemeString("Error", "error"),
				       ansithemeprint.ANSIThemeString(": The DNS label ", "default"),
				       ansithemeprint.ANSIThemeString(dnslabel, "hostname"),
				       ansithemeprint.ANSIThemeString(" is invalid; ", "default"),
			               ansithemeprint.ANSIThemeString("a DNS label cannot start with the ACE prefix “xn--“.", "default")]
				ansithemeprint.ansithemeprint(msg, stderr = True)
			return HostNameStatus.DNS_LABEL_STARTS_WITH_IDNA

		# This indirectly checks non-IDNA labels for max length too
		idna_dnslabel = dnslabel
		try:
			idna_dnslabel = dnslabel.encode("idna").decode("utf-8")
		except UnicodeError as e:
			if "label too long" in str(e):
				if message_on_error:
					msg = [ansithemeprint.ANSIThemeString("Error", "error"),
					       ansithemeprint.ANSIThemeString(": the DNS label ", "default"),
					       ansithemeprint.ANSIThemeString(dnslabel, "hostname"),
					       ansithemeprint.ANSIThemeString(" is invalid; ", "default")]
					msg += [ansithemeprint.ANSIThemeString("a DNS label cannot be more than 63 characters long.", "default")]
					ansithemeprint.ansithemeprint(msg, stderr = True)
				return HostNameStatus.DNS_LABEL_TOO_LONG
			if "label empty or too long" in str(e):
				if message_on_error:
					msg = [ansithemeprint.ANSIThemeString("Error", "error"),
					       ansithemeprint.ANSIThemeString(": the DNS label ", "default"),
					       ansithemeprint.ANSIThemeString(dnslabel, "hostname"),
					       ansithemeprint.ANSIThemeString(" is invalid; ", "default")]
					msg += [ansithemeprint.ANSIThemeString("a decoded Punycode (IDNA) DNS label cannot be more than 63 characters long.", "default")]
					ansithemeprint.ansithemeprint(msg, stderr = True)
				return HostNameStatus.DNS_LABEL_PUNYCODE_TOO_LONG
			raise

		tmp = dnslabel_regex.match(idna_dnslabel)

		if tmp is None:
			if message_on_error:
				msg = [ansithemeprint.ANSIThemeString("Error", "error"),
				       ansithemeprint.ANSIThemeString(": the DNS label ", "default"),
				       ansithemeprint.ANSIThemeString(dnslabel, "hostname")]
				if idna_dnslabel != dnslabel:
					msg += [ansithemeprint.ANSIThemeString(" (Punycode: ", "default"),
						ansithemeprint.ANSIThemeString(idna_dnslabel, "hostname"),
						ansithemeprint.ANSIThemeString(")", "default")]
				msg += [ansithemeprint.ANSIThemeString(" is invalid; a DNS label must be in the format ", "default"),
				        ansithemeprint.ANSIThemeString("[a-z0-9]([-a-z0-9]*[a-z0-9])?", "hostname"),
				        ansithemeprint.ANSIThemeString(" after Punycode decoding.", "default")]
				ansithemeprint.ansithemeprint(msg, stderr = True)
			return HostNameStatus.DNS_LABEL_INVALID_CHARACTERS

		if dnslabel.startswith("-") or dnslabel.endswith("-"):
			if message_on_error:
				msg = [ansithemeprint.ANSIThemeString("Error", "error"),
				       ansithemeprint.ANSIThemeString(": The DNS label ", "default"),
				       ansithemeprint.ANSIThemeString(dnslabel, "hostname")]
				if idna_dnslabel != dnslabel:
					msg += [ansithemeprint.ANSIThemeString(" (Punycode: ", "default"),
						ansithemeprint.ANSIThemeString(idna_dnslabel, "hostname"),
						ansithemeprint.ANSIThemeString(")", "default")]
				msg += [ansithemeprint.ANSIThemeString(" is invalid; ", "default"),
					ansithemeprint.ANSIThemeString("a DNS label cannot begin or end with “-“.", "default")]
				ansithemeprint.ansithemeprint(msg, stderr = True)
			return HostNameStatus.DNS_LABEL_INVALID_FORMAT
	return HostNameStatus.OK

def validator_bool(value: Any, error_on_failure: bool = True, exit_on_failure: bool = True) -> Tuple[bool, bool]:
	"""
	Checks whether the value represents a bool.
	Note: this validator is not meant to validate all forms of truthiness; only user input.

		Parameters:
			value (any): The representation of value
			error_on_failure (bool): Print an error message on failure
			exit_on_failure (bool): Exit on failure
		Returns:
			result (bool): True if the value can be represented as bool, False if not
			retval (bool): True if value is True, False if value is False
	"""

	result = False
	retval = None

	if isinstance(value, bool):
		result = True
		retval = value
	elif isinstance(value, int):
		if value == 0:
			result = True
			retval = False
		elif value == 1:
			result = True
			retval = True
	elif isinstance(value, str):
		if value.lower() in ("1", "y", "yes", "true"):
			result = True
			retval = True
		elif value.lower() in ("0", "n", "no", "false"):
			result = True
			retval = False

	if not result:
		if error_on_failure:
			ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
					ANSIThemeString(": “", "default"),
					ANSIThemeString(f"{value}", "option"),
					ANSIThemeString("“ is not a boolean.", "default")], stderr = True)
		if exit_on_failure: # pragma: no cover
			sys.exit(errno.EINVAL)

	return result, retval

def validator_int(minval: int, maxval: int, value: Any, error_on_failure: bool = True, exit_on_failure: bool = True) -> bool:
	"""
	Checks whether value can be represented as an integer,
	and whether it's within the range [min, max].

		Parameters:
			min (int): The minimum value
			max (int): The maximum value
			value (any): The representation of value
			error_on_failure (bool): Print an error message on failure
			exit_on_failure (bool): Exit on failure
		Returns:
			result (bool): True if the value can be represented as int, False if not
	"""

	try:
		value = int(value)
	except ValueError:
		if error_on_failure:
			ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
					ANSIThemeString(": “", "default"),
					ANSIThemeString(f"{value}", "option"),
					ANSIThemeString("“ is not an integer.", "default")], stderr = True)
		if exit_on_failure: # pragma: no cover
			sys.exit(errno.EINVAL)
		return False

	if minval is None:
		minval = -sys.maxsize
		minval_str = "<any>"
	else:
		minval_str = str(minval)

	if maxval is None:
		maxval = sys.maxsize
		maxval_str = "<any>"
	else:
		maxval_str = str(maxval)

	if minval > maxval:
		raise ProgrammingError(f"minval {minval} > maxval {maxval}")

	if not minval <= int(value) <= maxval:
		if error_on_failure:
			ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
					ANSIThemeString(": “", "default"),
					ANSIThemeString(f"{value}", "option"),
					ANSIThemeString("“ is not in the range [", "default"),
					ANSIThemeString(minval_str, "emphasis"),
					ANSIThemeString(", ", "default"),
					ANSIThemeString(maxval_str, "emphasis"),
					ANSIThemeString("].", "default")], stderr = True)
		if exit_on_failure: # pragma: no cover
			sys.exit(errno.EINVAL)
		return False
	return True

def validate_argument(arg: str, arg_string: List[ANSIThemeString], options: Dict) -> bool:
	"""
	Validate an argument or argument list

		Parameters:
			arg (str): The argument to validate
			arg_string (ansithemearray): A ansithemearray with the formatted representation of the expected data format
			options (dict): Options to pass to the validators
		Returns:
			True on success, False on failure
	"""

	result = True

	validator = deep_get(options, DictPath("validator"), "")
	list_separator = deep_get(options, DictPath("list_separator"))
	minval, maxval = deep_get(options, DictPath("valid_range"), (None, None))
	allowlist = deep_get(options, DictPath("allowlist"), [])
	validator_regex = deep_get(options, DictPath("regex"), r"")
	exit_on_failure = deep_get(options, DictPath("exit_on_failure"), True)
	error_on_failure = deep_get(options, DictPath("error_on_failure"), True)

	if list_separator is None:
		arglist = [arg]
	else:
		arglist = arg.split(list_separator)

	for subarg in arglist:
		if validator == "cidr":
			valid = False
			if "/" in subarg:
				ip, netmask = subarg.split("/")
				if validators is not None:
					valid_ipv4_address = validators.ipv4(ip)
					valid_ipv6_address = validators.ipv6(ip)
				else: # pragma: no cover
					valid_ipv4_address = True
					valid_ipv6_address = True
				try:
					if valid_ipv4_address and 0 < int(netmask) <= 32:
						valid = True
					if valid_ipv6_address and 0 < int(netmask) <= 128:
						valid = True
				except ValueError:
					pass

			if not valid:
				if error_on_failure:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{subarg}", "option"),
							ANSIThemeString("“ is not a valid POD Network CIDR.", "default")], stderr = True)
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				result = False
				break
		elif validator == "path":
			if not Path(subarg).is_file():
				if error_on_failure:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{subarg}", "option"),
							ANSIThemeString("“ is not a valid path.", "default")], stderr = True)
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				result = False
				break
		elif validator in ("hostname", "hostname_or_path", "hostname_or_ip", "ip"):
			valid_dns_label = validate_name("dns-subdomain", subarg)
			if validators is not None:
				valid_ipv4_address = validators.ipv4(subarg)
				valid_ipv6_address = validators.ipv6(subarg)
			else: # pragma: no cover
				valid_ipv4_address = True
				valid_ipv6_address = True

			if validator in ("hostname", "hostname_or_path") and not valid_dns_label:
				# If validation failed as subdomain we check if it's a valid path;
				# this will need deeper checks in the main function
				if validator == "hostname_or_path":
					if Path(subarg).is_file():
						break
				if error_on_failure:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{subarg}", "option"),
							ANSIThemeString("“ is not a valid hostname or path.", "default")], stderr = True)
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				result = False
			if validator == "ip" and not valid_ipv4_address and not valid_ipv6_address:
				if error_on_failure:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{subarg}", "option"),
							ANSIThemeString("“ is not a valid IP-address.", "default")], stderr = True)
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				result = False
				break
			if validator == "hostname_or_ip" and not valid_dns_label and not valid_ipv4_address and not valid_ipv6_address:
				if error_on_failure:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{subarg}", "option"),
							ANSIThemeString("“ is neither a valid hostname nor a valid IP-address.", "default")], stderr = True)
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				result = False
				break
		elif validator in ("taint", "untaint"):
			# Format: dns-subdomain[:dns-label]={NoSchedule,PreferNoSchedule,NoExecute}
			valid = False
			if ":" in subarg:
				key_value, effect = subarg.split(":")
			else:
				key_value = subarg
				effect = ""

			if "=" in key_value:
				key, value = key_value.split("=")
			else:
				key = key_value
				value = ""

			valid_key = validate_name("dns-subdomain", key)
			if len(value) > 0:
				valid_value = validate_name("dns-label", value)
			else:
				valid_value = True

			valid_effect = effect in ("NoSchedule", "PreferNoSchedule", "NoExecute")
			if len(effect) == 0 and validator == "untaint":
				valid_effect = True

			if not valid_key:
				if error_on_failure:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{key}", "option"),
							ANSIThemeString("“ is not a valid taint-key.", "default")], stderr = True)
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				result = False
				break
			if not valid_value:
				if error_on_failure:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{value}", "option"),
							ANSIThemeString("“ is not a valid taint-value.", "default")], stderr = True)
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				result = False
				break
			if not valid_effect:
				if error_on_failure:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{effect}", "option"),
							ANSIThemeString("“ is not a valid taint-effect.", "default")], stderr = True)
					ansithemeprint([ANSIThemeString("Valid options are: ", "description")], stderr = True)
					ansithemeprint(ansithemestring_join_tuple_list(["NoSchedule", "PreferNoSchedule", "NoExecute"],
										       formatting = "argument", separator = ANSIThemeString(", ", "separator")), stderr = True)
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				result = False
				break
		elif validator == "bool":
			result, _value = validator_bool(subarg, error_on_failure = error_on_failure, exit_on_failure = exit_on_failure)
			if not result:
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				break
		elif validator == "int":
			result = validator_int(minval, maxval, subarg, error_on_failure = error_on_failure, exit_on_failure = exit_on_failure)
			if not result:
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				break
		elif validator == "allowlist":
			result = subarg in allowlist
			if result is False:
				if error_on_failure:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{subarg}", "argument"),
							ANSIThemeString("“ is not a valid argument for ", "default"),
						       ] + arg_string + [ANSIThemeString(".", "default")], stderr = True)
					ansithemeprint([ANSIThemeString("Valid options are: ", "description")], stderr = True)
					ansithemeprint(ansithemestring_join_tuple_list(allowlist, formatting = "argument",
										       separator = ANSIThemeString(", ", "separator")), stderr = True)
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				break
		elif validator == "regex":
			tmp = re.match(validator_regex, subarg)
			if tmp is None:
				if error_on_failure:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{subarg}", "argument"),
							ANSIThemeString("“ is not a valid argument for ", "default"),
						       ] + arg_string + [ANSIThemeString(".", "default")], stderr = True)
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				result = False
				break
		elif validator == "url":
			tmp_arg = subarg
			if not tmp_arg.startswith("http"):
				tmp_arg = f"https://{arg}"

			# Workaround; it seems validators.url accepts usernames that start with "-"
			if subarg.startswith("-") or validators is not None and not validators.url(tmp_arg):
				if error_on_failure:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{subarg}", "option"),
							ANSIThemeString("“ is not a valid URL.", "default")], stderr = True)
				if exit_on_failure: # pragma: no cover
					sys.exit(errno.EINVAL)
				result = False
				break

	return result

def set_programname(__programname: str) -> None:
	global programname
	programname = __programname
