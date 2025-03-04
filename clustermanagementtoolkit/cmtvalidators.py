#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
This module contains data validators, mainly for validating user input
"""

import errno
import os
from pathlib import Path
import re
import sys
from typing import Any

try:
    import validators
except ModuleNotFoundError:
    print("ModuleNotFoundError: Could not import validators; "
          "you may need to (re-)run `cmt-install` "
          "or `pip3 install validators`; disabling IP-address validation.\n", file=sys.stderr)
    validators = None  # pylint: disable=invalid-name

from clustermanagementtoolkit.ansithemeprint import ANSIThemeStr, ansithemeprint
from clustermanagementtoolkit.ansithemeprint import ansithemestr_join_list, ansithemearray_to_str

from clustermanagementtoolkit.cmtpaths import HOMEDIR

from clustermanagementtoolkit.cmttypes import deep_get, DictPath
from clustermanagementtoolkit.cmttypes import HostNameStatus, ProgrammingError
from clustermanagementtoolkit.cmttypes import LogLevel, ArgumentValidationError

programname = None  # pylint: disable=invalid-name


# pylint: disable-next=too-many-branches
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
            (bool): True if valid, False if invalid
    """
    invalid = False
    tmp = None
    maxlen = -1

    if name is None:
        return False

    name_regex = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
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
    else:
        msg = [
            [("validate_name()", "emphasis"),
             (" called with invalid argument(s):", "error")],
            [("Unknown value for ", "default"),
             ("rtype = ", "default"),
             (f"{rtype}", "argument")],
        ]

        unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

        raise ProgrammingError(unformatted_msg,
                               severity=LogLevel.ERR,
                               formatted_msg=formatted_msg)

    return not invalid and len(name) <= maxlen


# pylint: disable-next=too-many-return-statements,too-many-branches,too-many-statements
def validate_fqdn(fqdn: str, message_on_error: bool = False) -> HostNameStatus:
    """
    Verifies that a FQDN / hostname is valid

        Parameters:
            fqdn (str): The FQDN / hostname to validate
            message_on_error (bool): Should an error message be printed on error?
        Returns:
            (HostNameStatus): The result of the validation; HostNameStatus.OK on success
    """
    if fqdn is None or len(fqdn) == 0:
        if message_on_error:
            msg = [ANSIThemeStr("Error", "error"),
                   ANSIThemeStr(": A FQDN or hostname cannot be empty.", "default")]
            ansithemeprint(msg, stderr=True)
        return HostNameStatus.DNS_SUBDOMAIN_EMPTY
    if "\x00" in fqdn:
        stripped_fqdn = fqdn.replace("\x00", "<NUL>")
        if message_on_error:
            msg = [ANSIThemeStr("Critical", "critical"),
                   ANSIThemeStr(": the FQDN / hostname ", "default"),
                   ANSIThemeStr(stripped_fqdn, "hostname")]
            msg += [ANSIThemeStr(" contains NUL-bytes (replaced here).\n"
                                 "This is either a programming error, a system error, "
                                 "file or memory corruption, or a deliberate attempt "
                                 "to bypass security; aborting.", "default")]
            ansithemeprint(msg, stderr=True)
        emsg = [[("validate_fqdn()", "emphasis"),
                 (": The FQDN / hostname ", "default"),
                 (stripped_fqdn, "hostname"),
                 (" contains NUL-bytes (replaced here).", "default")],
                [("This is either a programming error, a system error, "
                  "file or memory corruption, ", "default"),
                 ("or a deliberate attempt to bypass security; aborting.", "default")]]
        raise ArgumentValidationError(formatted_msg=emsg)
    if len(fqdn) > 253:
        if message_on_error:
            msg = [ANSIThemeStr("Critical", "critical"),
                   ANSIThemeStr(": the FQDN / hostname ", "default"),
                   ANSIThemeStr(fqdn, "hostname")]
            msg = [ANSIThemeStr(" is invalid; ", "default"),
                   ANSIThemeStr("a FQDN cannot be more than 253 characters long.", "default")]
            ansithemeprint(msg, stderr=True)
        return HostNameStatus.DNS_SUBDOMAIN_TOO_LONG
    if fqdn != fqdn.lower():
        if message_on_error:
            msg = [ANSIThemeStr("Error", "error"),
                   ANSIThemeStr(": The FQDN / hostname ", "default"),
                   ANSIThemeStr(fqdn, "hostname"),
                   ANSIThemeStr(" is invalid; ", "default"),
                   ANSIThemeStr("a FQDN / hostname must be lowercase.", "default")]
            ansithemeprint(msg, stderr=True)
        return HostNameStatus.DNS_SUBDOMAIN_WRONG_CASE
    if fqdn.startswith(".") or fqdn.endswith(".") or ".." in fqdn:
        if message_on_error:
            msg = [ANSIThemeStr("Error", "error"),
                   ANSIThemeStr(": The FQDN / hostname ", "default"),
                   ANSIThemeStr(fqdn, "hostname"),
                   ANSIThemeStr(" is invalid; ", "default"),
                   ANSIThemeStr("a FQDN / hostname cannot begin or end with “.“, "
                                "and must not have consecutive “.“.", "default")]
            ansithemeprint(msg, stderr=True)
        return HostNameStatus.DNS_SUBDOMAIN_INVALID_FORMAT

    dnslabels = fqdn.split(".")
    dnslabel_regex = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

    for dnslabel in dnslabels:
        if dnslabel.startswith("xn--"):
            if message_on_error:
                msg = [ANSIThemeStr("Error", "error"),
                       ANSIThemeStr(": The DNS label ", "default"),
                       ANSIThemeStr(dnslabel, "hostname"),
                       ANSIThemeStr(" is invalid; ", "default"),
                       ANSIThemeStr("a DNS label cannot start "
                                    "with the ACE prefix “xn--“.", "default")]
                ansithemeprint(msg, stderr=True)
            return HostNameStatus.DNS_LABEL_STARTS_WITH_IDNA

        # This indirectly checks non-IDNA labels for max length too
        idna_dnslabel = dnslabel
        try:
            idna_dnslabel = dnslabel.encode("idna").decode("utf-8")
        except UnicodeError as e:
            if "label too long" in str(e):
                if message_on_error:
                    msg = [ANSIThemeStr("Error", "error"),
                           ANSIThemeStr(": the DNS label ", "default"),
                           ANSIThemeStr(dnslabel, "hostname"),
                           ANSIThemeStr(" is invalid; ", "default")]
                    msg += [ANSIThemeStr("a DNS label cannot "
                                         "be more than 63 characters long.", "default")]
                    ansithemeprint(msg, stderr=True)
                return HostNameStatus.DNS_LABEL_TOO_LONG
            if "label empty or too long" in str(e):
                if message_on_error:
                    msg = [ANSIThemeStr("Error", "error"),
                           ANSIThemeStr(": the DNS label ", "default"),
                           ANSIThemeStr(dnslabel, "hostname"),
                           ANSIThemeStr(" is invalid; ", "default")]
                    msg += [ANSIThemeStr("a decoded Punycode (IDNA) DNS label cannot "
                                         "be more than 63 characters long.", "default")]
                    ansithemeprint(msg, stderr=True)
                return HostNameStatus.DNS_LABEL_PUNYCODE_TOO_LONG
            raise

        tmp = dnslabel_regex.match(idna_dnslabel)

        if tmp is None:
            if message_on_error:
                msg = [ANSIThemeStr("Error", "error"),
                       ANSIThemeStr(": the DNS label ", "default"),
                       ANSIThemeStr(dnslabel, "hostname")]
                if idna_dnslabel != dnslabel:
                    msg += [ANSIThemeStr(" (Punycode: ", "default"),
                            ANSIThemeStr(idna_dnslabel, "hostname"),
                            ANSIThemeStr(")", "default")]
                msg += [ANSIThemeStr(" is invalid; a DNS label must "
                                     "be in the format ", "default"),
                        ANSIThemeStr("[a-z0-9]([-a-z0-9]*[a-z0-9])?", "hostname"),
                        ANSIThemeStr(" after Punycode decoding.", "default")]
                ansithemeprint(msg, stderr=True)
            return HostNameStatus.DNS_LABEL_INVALID_CHARACTERS
    if len(dnslabels) == 1:
        return HostNameStatus.OK

    if not (dnslabels[-1:][0][0].isascii()
            and dnslabels[-1:][0][0].isalpha() and len(dnslabels[-1:][0]) > 1):
        # The dnslabel is OK if either of these apply:
        # * It only has one field (it doesn't have a tld)
        # * The first character in the TLD is [a-z] and the the TLD is longer than 1 character
        if message_on_error:
            msg = [ANSIThemeStr("Error", "error"),
                   ANSIThemeStr(": The DNS label ", "default"),
                   ANSIThemeStr(fqdn, "hostname"),
                   ANSIThemeStr(" is invalid; ", "default"),
                   ANSIThemeStr("the TLD must start with [a-z] and "
                                "be at least 2 characters long.", "default")]
            ansithemeprint(msg, stderr=True)
        return HostNameStatus.DNS_TLD_INVALID

    return HostNameStatus.OK


def validator_bool(value: Any, error_on_failure: bool = True) -> tuple[bool, bool]:
    """
    Checks whether the value represents a bool.
    Note: this validator is not meant to validate all forms of truthiness; only user input.

        Parameters:
            value (any): The representation of value
            error_on_failure (bool): Print an error message on failure
        Returns:
            (bool, bool):
                (bool): True if the value can be represented as bool, False if not
                (bool): True if value is True, False if value is False
    """
    result = False
    retval = False

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
            ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                            ANSIThemeStr(": “", "default"),
                            ANSIThemeStr(f"{value}", "option"),
                            ANSIThemeStr("“ is not a boolean.", "default")], stderr=True)

    return result, retval


def validator_int(minval: int, maxval: int, value: Any, **kwargs: Any) -> bool:
    """
    Checks whether value can be represented as an integer,
    and whether it's within the range [min, max].

        Parameters:
            min (int): The minimum value
            max (int): The maximum value
            value (any): The representation of value
            **kwargs (dict[str, Any]): Keyword arguments
                error_on_failure (bool): Show an error message on failure
                exit_on_failure (bool): exit on failure
        Returns:
            (bool): True if the value can be represented as int, False if not
    """
    error_on_failure: bool = deep_get(kwargs, DictPath("error_on_failure"), True)

    try:
        value = int(value)
    except ValueError:
        if error_on_failure:
            ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                            ANSIThemeStr(": “", "default"),
                            ANSIThemeStr(f"{value}", "option"),
                            ANSIThemeStr("“ is not an integer.", "default")], stderr=True)
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
            ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                            ANSIThemeStr(": “", "default"),
                            ANSIThemeStr(f"{value}", "option"),
                            ANSIThemeStr("“ is not in the range [", "default"),
                            ANSIThemeStr(minval_str, "emphasis"),
                            ANSIThemeStr(", ", "default"),
                            ANSIThemeStr(maxval_str, "emphasis"),
                            ANSIThemeStr("].", "default")], stderr=True)
        return False
    return True


def validator_cidr(value: str, **kwargs: Any) -> bool:
    """
    Validate a string to see if it's a valid CIDR

        Parameters:
            value (str): The string to validate
            **kwargs (dict[str, Any]): Keyword arguments
                error_on_failure (bool): Show an error message on failure
        Returns:
            (bool): True if valid, False if invalid
    """
    error_on_failure: bool = deep_get(kwargs, DictPath("error_on_failure"), True)
    valid = False

    if "/" in value:
        ip, netmask = value.split("/")
        if validators is not None:
            valid_ipv4_address = validators.ipv4(ip)
            valid_ipv6_address = validators.ipv6(ip)
        else:  # pragma: no cover
            valid_ipv4_address = True
            valid_ipv6_address = True
        try:
            if valid_ipv4_address and 0 < int(netmask) <= 32:
                valid = True
            if valid_ipv6_address and 0 < int(netmask) <= 128:
                valid = True
        except ValueError:
            pass

    if not valid and error_on_failure:
        ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                        ANSIThemeStr(": “", "default"),
                        ANSIThemeStr(f"{value}", "option"),
                        ANSIThemeStr("“ is not a valid POD Network CIDR.", "default")],
                       stderr=True)
    return valid


def validator_path(value: str, **kwargs: Any) -> bool:
    """
    Validate a string to see if it's a valid path

        Parameters:
            value (str): The string to validate
            **kwargs (dict[str, Any]): Keyword arguments
                error_on_failure (bool): Show an error message on failure
        Returns:
            (bool): True if valid, False if invalid
    """
    error_on_failure = deep_get(kwargs, DictPath("error_on_failure"), True)
    valid = True

    if not Path(value).is_file():
        valid = False
    if not valid and error_on_failure:
        ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                        ANSIThemeStr(": “", "default"),
                        ANSIThemeStr(f"{value}", "option"),
                        ANSIThemeStr("“ is not a valid path.", "default")], stderr=True)
    return valid


# pylint: disable-next=too-many-branches
def validator_taint(string: str, validator: str, **kwargs: Any) -> bool:
    """
    Validate a string to see if it's a valid taint

        Parameters:
            string (str): The string to validate
            **kwargs (dict[str, Any]): Keyword arguments
                error_on_failure (bool): Show an error message on failure
        Returns:
            (bool): True if valid, False if invalid
    """
    error_on_failure = deep_get(kwargs, DictPath("error_on_failure"), True)
    valid = True

    # Format: dns-subdomain[:dns-label]={NoSchedule,PreferNoSchedule,NoExecute}
    if ":" in string:
        key_value, effect = string.split(":", maxsplit=1)
    else:
        key_value = string
        effect = ""

    if "=" in key_value:
        key, value = key_value.split("=", maxsplit=1)
    else:
        key = key_value
        value = ""

    valid_key = validate_name("dns-subdomain", key)
    if value:
        valid_value = validate_name("dns-label", value)
    else:
        valid_value = True

    valid_effects = ("NoSchedule", "PreferNoSchedule", "NoExecute")
    valid_effect = effect in valid_effects
    if not effect and validator == "untaint":
        valid_effect = True

    if not valid_key:
        if error_on_failure:
            ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                            ANSIThemeStr(": “", "default"),
                            ANSIThemeStr(f"{key}", "option"),
                            ANSIThemeStr("“ is not a valid taint-key.", "default")],
                           stderr=True)
        valid = False
    if not valid_value:
        if error_on_failure:
            ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                            ANSIThemeStr(": “", "default"),
                            ANSIThemeStr(f"{value}", "option"),
                            ANSIThemeStr("“ is not a valid taint-value.", "default")],
                           stderr=True)
        valid = False
    if not valid_effect:
        if error_on_failure:
            ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                            ANSIThemeStr(": “", "default"),
                            ANSIThemeStr(f"{effect}", "option"),
                            ANSIThemeStr("“ is not a valid taint-effect.", "default")],
                           stderr=True)
            ansithemeprint([ANSIThemeStr("Valid options are: ", "description")],
                           stderr=True)
            ansithemeprint(ansithemestr_join_list(valid_effects, formatting="argument"),
                           stderr=True)
        valid = False
    return valid


# pylint: disable-next=too-many-branches,too-many-statements,too-many-locals
def validate_argument(arg: str, arg_string: list[ANSIThemeStr], options: dict) -> bool:
    """
    Validate an argument or argument list

        Parameters:
            arg (str): The argument to validate
            arg_string (ansithemearray): A ansithemearray with the formatted
                                         representation of the expected data format
            options (dict): Options to pass to the validators
        Returns:
            (bool): True on success, False on failure
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
            if not (result := validator_cidr(subarg, error_on_failure=error_on_failure)):
                break
        elif validator == "path":
            if subarg.startswith("~/"):
                subarg = subarg.replace("~", HOMEDIR, 1)
            if not (result := validator_path(subarg, error_on_failure=error_on_failure)):
                break
        elif validator in ("hostname", "hostname_or_path", "hostname_or_ip", "ip"):
            valid_dns_label = validate_name("dns-subdomain", subarg)
            if validators is not None:
                valid_ipv4_address = validators.ipv4(subarg)
                valid_ipv6_address = validators.ipv6(subarg)
            else:  # pragma: no cover
                valid_ipv4_address = True
                valid_ipv6_address = True
            if not (valid_ipv4_address or valid_ipv6_address):
                # If the DNS-label is not an IP-address
                # it cannot end with a fully numerical dns-subdomain
                if "." in subarg and subarg.split(".")[-1:][0].isnumeric():
                    valid_dns_label = False

            if validator in ("hostname", "hostname_or_path") and not valid_dns_label:
                # If validation failed as subdomain we check if it's a valid path;
                # this will need deeper checks in the main function
                if validator == "hostname_or_path":
                    if Path(subarg).is_file():
                        break
                if error_on_failure:
                    ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                                    ANSIThemeStr(": “", "default"),
                                    ANSIThemeStr(f"{subarg}", "option"),
                                    ANSIThemeStr("“ is not a valid hostname or path.",
                                                 "default")], stderr=True)
                result = False
                break
            if validator == "ip" and not valid_ipv4_address and not valid_ipv6_address:
                if error_on_failure:
                    ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                                    ANSIThemeStr(": “", "default"),
                                    ANSIThemeStr(f"{subarg}", "option"),
                                    ANSIThemeStr("“ is not a valid IP-address.",
                                                 "default")], stderr=True)
                result = False
                break
            if validator == "hostname_or_ip" and not valid_dns_label \
                    and not valid_ipv4_address and not valid_ipv6_address:
                if error_on_failure:
                    ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                                    ANSIThemeStr(": “", "default"),
                                    ANSIThemeStr(f"{subarg}", "option"),
                                    ANSIThemeStr("“ is neither a valid hostname "
                                                 "nor a valid IP-address.",
                                                 "default")], stderr=True)
                result = False
                break
        elif validator in ("taint", "untaint"):
            if not (result := validator_taint(subarg, validator,
                                              error_on_failure=error_on_failure)):
                break
        elif validator == "bool":
            result, _value = validator_bool(subarg, error_on_failure=error_on_failure)
            if not result:
                break
        elif validator == "int":
            if not (result := validator_int(minval, maxval, subarg,
                                            error_on_failure=error_on_failure)):
                break
        elif validator == "allowlist":
            result = subarg in allowlist
            if result is False:
                if error_on_failure:
                    ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                                    ANSIThemeStr(": “", "default"),
                                    ANSIThemeStr(f"{subarg}", "argument"),
                                    ANSIThemeStr("“ is not a valid argument for ", "default")]
                                   + arg_string + [ANSIThemeStr(".", "default")],
                                   stderr=True)
                    ansithemeprint([ANSIThemeStr("Valid options are: ",
                                                 "description")], stderr=True)
                    ansithemeprint(ansithemestr_join_list(allowlist, formatting="argument"),
                                   stderr=True)
                break
        elif validator == "regex":
            tmp = re.match(validator_regex, subarg)
            if tmp is None:
                if error_on_failure:
                    ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                                    ANSIThemeStr(": “", "default"),
                                    ANSIThemeStr(f"{subarg}", "argument"),
                                    ANSIThemeStr("“ is not a valid argument for ", "default")]
                                   + arg_string + [ANSIThemeStr(".", "default")], stderr=True)
                result = False
                break
        elif validator == "url":
            tmp_arg = subarg
            if not tmp_arg.startswith("http"):
                tmp_arg = f"https://{arg}"

            # Workaround; it seems validators.url accepts usernames that start with "-"
            if subarg.startswith("-") or validators is not None and not validators.url(tmp_arg):
                if error_on_failure:
                    ansithemeprint([ANSIThemeStr(f"{programname}", "programname"),
                                    ANSIThemeStr(": “", "default"),
                                    ANSIThemeStr(f"{subarg}", "option"),
                                    ANSIThemeStr("“ is not a valid URL.", "default")],
                                   stderr=True)
                result = False
                break
        elif validator == "":
            # We cannot use format_error_msg() here since we'd lose the formatting for arg_string
            unformatted_msg = f"{programname}: no validator defined for argument " + \
                              ansithemearray_to_str(arg_string) + "."
            formatted_msg = [[ANSIThemeStr(f"{programname}", "emphasis"),
                              ANSIThemeStr(": no validator defined for argument ", "default")]
                             + arg_string + [ANSIThemeStr(".", "default")]]

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   formatted_msg=formatted_msg)
        else:
            msg = [
                [("validate_argument()", "emphasis"),
                 (" called with invalid argument(s):", "error")],
                [("Unknown value for ", "default"),
                 ("validator = ", "default"),
                 (f"{validator}", "argument")],
            ]

            unformatted_msg, formatted_msg = ANSIThemeStr.format_error_msg(msg)

            raise ProgrammingError(unformatted_msg,
                                   severity=LogLevel.ERR,
                                   formatted_msg=formatted_msg)

    if not result and exit_on_failure:  # pragma: no cover
        sys.exit(errno.EINVAL)

    return result


def set_programname(programname_: str) -> None:
    """
    Set the name of the calling program, to ensure that error messages are correct
    Note: This should be removed; libraries should not print error messages

        Parameters:
            programname_ (str): The name of the program
    """
    global programname  # pylint: disable=global-statement
    programname = programname_
