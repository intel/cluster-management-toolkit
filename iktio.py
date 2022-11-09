#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
I/O helpers for Intel Kubernetes Toolkit
"""

import errno
from functools import partial
from getpass import getuser
import os
from pathlib import Path, PurePath
import re
import subprocess
from subprocess import PIPE, STDOUT
import sys
from typing import Dict, List, Optional, Union

from ikttypes import ANSIThemeString, FilePath, HostNameStatus, FilePathAuditError, SecurityChecks, SecurityPolicy, SecurityStatus
from iktpaths import HOMEDIR

import iktprint

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
		if message_on_error == True:
			msg = [ANSIThemeString("Error", "error"), ANSIThemeString(": A FQDN or hostname cannot be empty.", "default")]
			iktprint.iktprint(msg, stderr = True)
		return HostNameStatus.DNS_SUBDOMAIN_EMPTY
	if "\x00" in fqdn:
		stripped_fqdn = fqdn.replace("\x00", "<NUL>")
		msg = [ANSIThemeString("Critical", "critical"), ANSIThemeString(": the FQDN / hostname ", "default"),
		       ANSIThemeString(stripped_fqdn, "hostname")]
		msg += [ANSIThemeString(" contains NUL-bytes (replaced here);\n"
			"this is either a programming error, a system error, file or memory corruption, "
			"or a deliberate attempt to bypass security; aborting.", "default")]
		iktprint.iktprint(msg, stderr = True)
		sys.exit(errno.EINVAL)
	if len(fqdn) > 253:
		if message_on_error == True:
			msg = [ANSIThemeString("Critical", "critical"), ANSIThemeString(": the FQDN / hostname ", "default"),
			       ANSIThemeString(fqdn, "hostname")]
			msg = [ANSIThemeString(" is invalid; ", "default"),
			       ANSIThemeString("a FQDN cannot be more than 253 characters long.", "default")]
			iktprint.iktprint(msg, stderr = True)
		return HostNameStatus.DNS_SUBDOMAIN_TOO_LONG
	if fqdn != fqdn.lower():
		if message_on_error == True:
			msg = [ANSIThemeString("Error", "error"), ANSIThemeString(": The FQDN / hostname ", "default"),
			       ANSIThemeString(fqdn, "hostname"),
			       ANSIThemeString(" is invalid; ", "default"),
			       ANSIThemeString("a FQDN / hostname must be lowercase.", "default")]
			iktprint.iktprint(msg, stderr = True)
		return HostNameStatus.DNS_SUBDOMAIN_WRONG_CASE
	if fqdn.startswith(".") or fqdn.endswith(".") or ".." in fqdn:
		if message_on_error == True:
			msg = [ANSIThemeString("Error", "error"), ANSIThemeString(": The FQDN / hostname ", "default"),
			       ANSIThemeString(fqdn, "hostname"),
			       ANSIThemeString(" is invalid; ", "default"),
			       ANSIThemeString("a FQDN / hostname cannot begin or end with “.“, and must not have consecutive “.“.", "default")]
			iktprint.iktprint(msg, stderr = True)
		return HostNameStatus.DNS_SUBDOMAIN_INVALID_FORMAT

	dnslabels = fqdn.split(".")
	dnslabel_regex = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

	for dnslabel in dnslabels:
		if dnslabel.startswith("xn--"):
			if message_on_error == True:
				msg = [ANSIThemeString("Error", "error"), ANSIThemeString(": The DNS label ", "default"),
				       ANSIThemeString(dnslabel, "hostname"),
				       ANSIThemeString(" is invalid; ", "default"),
			               ANSIThemeString("a DNS label cannot start with the ACE prefix “xn--“.", "default")]
				iktprint.iktprint(msg, stderr = True)
			return HostNameStatus.DNS_LABEL_STARTS_WITH_IDNA

		# This indirectly checks non-IDNA labels for max length too
		idna_dnslabel = dnslabel
		try:
			idna_dnslabel = dnslabel.encode("idna").decode("utf-8")
		except UnicodeError as e:
			if "label too long" in str(e):
				if message_on_error == True:
					msg = [ANSIThemeString("Error", "error"), ANSIThemeString(": the DNS label ", "default"),
					       ANSIThemeString(dnslabel, "hostname"),
					       ANSIThemeString(" is invalid; ", "default")]
					msg += [ANSIThemeString("a DNS label cannot be more than 63 characters long.", "default")]
					iktprint.iktprint(msg, stderr = True)
				return HostNameStatus.DNS_LABEL_TOO_LONG
			if "label empty or too long" in str(e):
				if message_on_error == True:
					msg = [ANSIThemeString("Error", "error"), ANSIThemeString(": the DNS label ", "default"),
					       ANSIThemeString(dnslabel, "hostname"),
					       ANSIThemeString(" is invalid; ", "default")]
					msg += [ANSIThemeString("a decoded Punycode (IDNA) DNS label cannot be more than 63 characters long.", "default")]
					iktprint.iktprint(msg, stderr = True)
				return HostNameStatus.DNS_LABEL_PUNYCODE_TOO_LONG
			raise

		tmp = dnslabel_regex.match(idna_dnslabel)

		if tmp is None:
			if message_on_error == True:
				msg = [ANSIThemeString("Error", "error"), ANSIThemeString(": the DNS label ", "default"),
				       ANSIThemeString(dnslabel, "hostname")]
				if idna_dnslabel != dnslabel:
					msg += [ANSIThemeString(" (Punycode: ", "default"),
						ANSIThemeString(idna_dnslabel, "hostname"),
						ANSIThemeString(")", "default")]
				msg += [ANSIThemeString(" is invalid; a DNS label must be in the format ", "default"),
				        ANSIThemeString("[a-z0-9]([-a-z0-9]*[a-z0-9])?", "hostname"),
				        ANSIThemeString(" after Punycode decoding.", "default")]
				iktprint.iktprint(msg, stderr = True)
			return HostNameStatus.DNS_LABEL_INVALID_CHARACTERS

		if dnslabel.startswith("-") or dnslabel.endswith("-"):
			if message_on_error == True:
				msg = [ANSIThemeString("Error", "error"), ANSIThemeString(": The DNS label ", "default"),
				       ANSIThemeString(dnslabel, "hostname")]
				if idna_dnslabel != dnslabel:
					msg += [ANSIThemeString(" (Punycode: ", "default"),
						ANSIThemeString(idna_dnslabel, "hostname"),
						ANSIThemeString(")", "default")]
				msg += [ANSIThemeString(" is invalid; ", "default"),
					ANSIThemeString("a DNS label cannot begin or end with “-“.", "default")]
				iktprint.iktprint(msg, stderr = True)
			return HostNameStatus.DNS_LABEL_INVALID_FORMAT
	return HostNameStatus.OK

# pylint: disable=too-many-arguments,line-too-long
def check_path(path: FilePath, parent_owner_allowlist = None, owner_allowlist = None, checks = None, exit_on_critical: bool = False, message_on_error: bool = False) -> List[SecurityStatus]:
	"""
	Verifies that a path meets certain security criteria;
	if the path fails to meet the criteria the function returns False and optionally
	outputs an error message. Critical errors will either raise an exception or exit the program.

		Parameters:
			path (FilePath): The path to the file to verify
			owner_allowlist (list[str]): A list of acceptable file owners;
				 by default [user, "root"]
			checks (list[SecurityChecks]): A list of checks that should be performed
			exit_on_critical (bool): By default check_path return SecurityStatus if a critical criteria violation
				is found; this flag can be used to exit the program instead if the violation is critical.
			message_on_error (bool): If this is set to true an error message will be printed to the console.
		Returns:
			list[SecurityStatus]: [SecurityStatus.OK] if all criteria are met, otherwise a list of all violated policies
	"""

	# This is most likely a security violation; treat it as such
	if "\x00" in path:
		stripped_path = path.replace("\x00", "<NUL>")
		raise ValueError(f"Critical: the path {stripped_path} contains NUL-bytes (replaced here);\n"
				  "this is either a programming error, a system error, file or memory corruption, or a deliberate attempt to bypass security; aborting.")

	violations = []

	if checks is None:
		# These are the default checks for a file
		checks = [
			SecurityChecks.PARENT_RESOLVES_TO_SELF,
			SecurityChecks.OWNER_IN_ALLOWLIST,
			SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
			SecurityChecks.PERMISSIONS,
			SecurityChecks.PARENT_PERMISSIONS,
			SecurityChecks.EXISTS,
			SecurityChecks.IS_FILE,
		]

	user = getuser()

	if parent_owner_allowlist is None:
		parent_owner_allowlist = [user, "root"]

	if owner_allowlist is None:
		owner_allowlist = [user, "root"]

	path_entry = Path(path)
	parent_entry = Path(PurePath(path).parent)

	# This test isn't optional; if the parent directory doesn't exist it's always a failure
	if not parent_entry.exists():
		if message_on_error == True:
			msg = [ANSIThemeString("Critical", "critical"), ANSIThemeString(": The parent of the target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" does not exist", "default")]
			if exit_on_critical == True:
				msg.append(ANSIThemeString("; aborting.", "default"))
				iktprint.iktprint(msg, stderr = True)
				sys.exit(errno.EINVAL)
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.PARENT_DOES_NOT_EXIST)
		return violations

	if not parent_entry.is_dir():
		if message_on_error == True:
			msg = [ANSIThemeString("Critical", "critical"), ANSIThemeString(": The parent of the target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" exists but is not a directory; this is either a configuration error or a security issue", "default")]
			if exit_on_critical == True:
				msg.append(ANSIThemeString("; aborting.", "default"))
				iktprint.iktprint(msg, stderr = True)
				sys.exit(errno.EINVAL)
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.PARENT_IS_NOT_DIR)
		return violations

	if SecurityChecks.PARENT_OWNER_IN_ALLOWLIST in checks and parent_entry.owner() not in parent_owner_allowlist:
		if message_on_error == True:
			msg = [ANSIThemeString("Critical", "critical"),
			       ANSIThemeString(": The parent of the target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" is not owned by one of (", "default")] +\
			      iktprint.ansithemestring_join_tuple_list(parent_owner_allowlist, formatting = "emphasis", separator = ANSIThemeString(", ", "separator")) +\
			      [ANSIThemeString(")", "default")]
			if exit_on_critical == True:
				msg.append(ANSIThemeString("; aborting.", "default"))
				iktprint.iktprint(msg, stderr = True)
				sys.exit(errno.EINVAL)
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.PARENT_OWNER_NOT_IN_ALLOWLIST)

	parent_path_stat = parent_entry.stat()
	parent_path_permissions = parent_path_stat.st_mode & 0o002
	if SecurityChecks.PARENT_WORLD_WRITABLE in checks and parent_path_permissions != 0:
		if message_on_error == True:
			msg = [ANSIThemeString("Critical", "critical"),
			       ANSIThemeString(": The parent of the target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" is world writable", "default")]
			if exit_on_critical == True:
				msg.append(ANSIThemeString("; aborting.", "default"))
				iktprint.iktprint(msg, stderr = True)
				sys.exit(errno.EINVAL)
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.PARENT_WORLD_WRITABLE)

	parent_entry_resolved = parent_entry.resolve()
	parent_entry_systemdir = False
	if str(parent_entry) in ("/bin", "/sbin", "/usr/bin", "/usr/sbin") and str(parent_entry_resolved) in ("/bin", "/sbin", "/usr/bin", "/usr/sbin"):
		parent_entry_systemdir = True

	# Are there any path shenanigans going on?
	# If we're dealing with {/bin,/sbin,/usr/bin,/usr/sbin}/path => {/bin,/sbin,/usr/bin,/usr/sbin}/path the symlink is acceptable
	if SecurityChecks.PARENT_RESOLVES_TO_SELF in checks and parent_entry != parent_entry_resolved and parent_entry_systemdir == False:
		if message_on_error == True:
			msg = [ANSIThemeString("Critical", "critical"), ANSIThemeString(": The parent of the target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" does not resolve to itself; this is either a configuration error or a security issue", "default")]
			if exit_on_critical == True:
				msg.append(ANSIThemeString("; aborting.", "default"))
				iktprint.iktprint(msg, stderr = True)
				sys.exit(errno.EINVAL)
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.PARENT_PATH_NOT_RESOLVING_TO_SELF)

	# Are there any path shenanigans going on?
	# We first resolve the parent path, then check the rest; this way we can see if the target is a symlink and see
	# where it ends up
	name = path_entry.name
	tmp_entry = Path(os.path.join(parent_entry_resolved, name))

	if SecurityChecks.RESOLVES_TO_SELF in checks and tmp_entry != tmp_entry.resolve():
		if message_on_error == True:
			msg = [ANSIThemeString("Critical", "critical"), ANSIThemeString(": The target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" does not resolve to itself; this is either a configuration error or a security issue", "default")]
			if exit_on_critical == True:
				msg.append(ANSIThemeString("; aborting.", "default"))
				iktprint.iktprint(msg, stderr = True)
				sys.exit(errno.EINVAL)
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.PATH_NOT_RESOLVING_TO_SELF)

	if not path_entry.exists():
		if SecurityChecks.EXISTS in checks:
			violations.append(SecurityStatus.DOES_NOT_EXIST)
		return violations

	if SecurityChecks.OWNER_IN_ALLOWLIST in checks and path_entry.owner() not in owner_allowlist:
		if message_on_error == True:
			msg = [ANSIThemeString("Critical", "critical"), ANSIThemeString(": The target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" is not owned by one of (", "default")] +\
			      iktprint.ansithemestring_join_tuple_list(owner_allowlist, formatting = "emphasis", separator = ANSIThemeString(", ", "separator")) +\
			      [ANSIThemeString(")", "default")]
			if exit_on_critical == True:
				msg.append(ANSIThemeString("; aborting.", "default"))
				iktprint.iktprint(msg, stderr = True)
				sys.exit(errno.EINVAL)
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.OWNER_NOT_IN_ALLOWLIST)

	path_stat = path_entry.stat()
	path_permissions = path_stat.st_mode & 0o002
	if path_permissions != 0:
		if message_on_error == True:
			msg = [ANSIThemeString("Critical", "critical"), ANSIThemeString(": The target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" is world writable", "default")]
			if exit_on_critical == True:
				msg.append(ANSIThemeString("; aborting.", "default"))
				iktprint.iktprint(msg, stderr = True)
				sys.exit(errno.EINVAL)
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.WORLD_WRITABLE)

	if SecurityChecks.IS_SYMLINK in checks and not path_entry.is_symlink():
		if message_on_error == True:
			msg = [ANSIThemeString("Error", "error"), ANSIThemeString(": The target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" exists but is not a symlink; this is either a configuration error or a security issue", "default")]
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.IS_NOT_SYMLINK)

	# is_file() returns True even if path is a symlink to a file rather than a file
	if SecurityChecks.IS_FILE in checks and not path_entry.is_file():
		if message_on_error == True:
			msg = [ANSIThemeString("Error", "error"), ANSIThemeString(": The target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" exists but is not a file; this is either a configuration error or a security issue", "default")]
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.IS_NOT_FILE)

	# is_file() returns True even if path is a symlink to a file rather than a file
	if SecurityChecks.IS_DIR in checks and not path_entry.is_dir():
		if message_on_error == True:
			msg = [ANSIThemeString("Error", "error"), ANSIThemeString(": The target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" exists but is not a directory; this is either a configuration error or a security issue", "default")]
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.IS_NOT_DIR)

	if SecurityChecks.IS_EXECUTABLE in checks and not os.access(path, os.X_OK):
		if message_on_error == True:
			msg = [ANSIThemeString("Warning", "warning"), ANSIThemeString(": The target path ", "default"),
			       ANSIThemeString(f"{path}", "path"),
			       ANSIThemeString(" exists but is not executable; skipping", "default")]
			iktprint.iktprint(msg, stderr = True)
		violations.append(SecurityStatus.IS_NOT_EXECUTABLE)

	return violations

def secure_rm(path: FilePath, ignore_non_existing: bool = False) -> None:
	"""
	Remove a file

		Parameters:
			path (FilePath): The path to the file to remove
		Raises:
			ikttypes.FilePathAuditError
			FileNotFoundError
	"""

	checks = [
		SecurityChecks.PARENT_RESOLVES_TO_SELF,
		SecurityChecks.RESOLVES_TO_SELF,
		SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
		SecurityChecks.OWNER_IN_ALLOWLIST,
		SecurityChecks.PARENT_PERMISSIONS,
		SecurityChecks.PERMISSIONS,
		SecurityChecks.EXISTS,
		SecurityChecks.IS_FILE,
	]

	violations = check_path(path, checks = checks)

	ignoring_non_existing = False

	if ignore_non_existing:
		try:
			violations.pop(SecurityStatus.DOES_NOT_EXIST)
			ignoring_non_existing = True
		except IndexError:
			pass

	if len(violations) > 0:
		violation_strings = []
		for violation in violations:
			violation_strings.append(str(violation))
		violations_joined = ",".join(violation_strings)
		raise FilePathAuditError(f"Violated rules: {violations_joined}", path = path)

	if ignoring_non_existing == False:
		Path(path).unlink()

def secure_rmdir(path: FilePath, ignore_non_existing: bool = False) -> None:
	"""
	Remove a directory

		Parameters:
			path (FilePath): The path to the directory to remove
			ignore_non_existing
		Raises:
			ikttypes.FilePathAuditError
			FileNotFoundError
	"""

	checks = [
		SecurityChecks.PARENT_RESOLVES_TO_SELF,
		SecurityChecks.RESOLVES_TO_SELF,
		SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
		SecurityChecks.OWNER_IN_ALLOWLIST,
		SecurityChecks.PARENT_PERMISSIONS,
		SecurityChecks.PERMISSIONS,
		SecurityChecks.EXISTS,
		SecurityChecks.IS_DIR,
	]

	violations = check_path(path, checks = checks)

	ignoring_non_existing = False

	if ignore_non_existing:
		try:
			violations.pop(SecurityStatus.DOES_NOT_EXIST)
			ignoring_non_existing = True
		except IndexError:
			pass

	if len(violations) > 0:
		violation_strings = []
		for violation in violations:
			violation_strings.append(str(violation))
		violations_joined = ",".join(violation_strings)
		raise FilePathAuditError(f"Violated rules: {violations_joined}", path = path)

	if ignoring_non_existing == False:
		Path(path).rmdir()

def secure_write_string(path: FilePath, string: str, permissions = None, write_mode = "w") -> None:
	"""
	Write a string to a file in a safe manner

		Parameters:
			path (FilePath): The path to write to
			string (str): The string to write
			permissions (int): File permissions (None uses system defaults)
			write_type (str): [w, a, x, wb, ab, xb] Write, Append, Exclusive Write, text or binary
		Raises:
			ikttypes.FilePathAuditError
	"""

	if write_mode not in ("a", "ab", "w", "wb", "x", "xb"):
		raise ValueError(f"Invalid write mode “{write_mode}“; permitted modes are “a(b)“ (append (binary)), “w(b)“ (write (binary)) and “x“ (exclusive write (binary))")

	checks = [
		SecurityChecks.PARENT_RESOLVES_TO_SELF,
		SecurityChecks.RESOLVES_TO_SELF,
		SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
		SecurityChecks.OWNER_IN_ALLOWLIST,
		SecurityChecks.PARENT_PERMISSIONS,
		SecurityChecks.PERMISSIONS,
		SecurityChecks.IS_FILE,
	]

	violations = check_path(path, checks = checks)

	if len(violations) > 0:
		violation_strings = []
		for violation in violations:
			violation_strings.append(str(violation))
		violations_joined = ",".join(violation_strings)
		raise FilePathAuditError(f"Violated rules: {violations_joined}", path = path)

	# We have no default recourse if this write fails, so if the caller can handle the failure
	# they have to capture the exception
	if permissions is None:
		with open(path, write_mode, encoding = "utf-8") as f:
			f.write(string)
	else:
		with open(path, write_mode, opener = partial(os.open, mode = permissions), encoding = "utf-8") as f:
			f.write(string)

def secure_read_string(path: FilePath, checks = None, directory_is_symlink: bool = False) -> str:
	"""
	Read a string from a file in a safe manner

		Parameters:
			path (FilePath): The path to read from
			directory_is_symlink (bool): The directory that the path points to is a symlink
		Returns:
			string (str): The read string
		Raises:
			ikttypes.FilePathAuditError
	"""

	if checks is None:
		if directory_is_symlink == True:
			parent_dir = FilePath(str(PurePath(path).parent))

			# The directory itself may be a symlink. This is expected behaviour when installing from a git repo,
			# but we only allow it if the rest of the path components are secure
			checks = [
				SecurityChecks.PARENT_RESOLVES_TO_SELF,
				SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
				SecurityChecks.OWNER_IN_ALLOWLIST,
				SecurityChecks.PARENT_PERMISSIONS,
				SecurityChecks.PERMISSIONS,
				SecurityChecks.EXISTS,
				SecurityChecks.IS_DIR,
			]

			violations = check_path(parent_dir, checks = checks)
			if len(violations) > 0:
				violation_strings = []
				for violation in violations:
					violation_strings.append(str(violation))
				violations_joined = ",".join(violation_strings)
				raise FilePathAuditError(f"Violated rules: {violations_joined}", path = parent_dir)

			# We don't want to check that parent resolves to itself,
			# because when we have an installation with links directly to the git repo
			# the parsers directory will be a symlink
			checks = [
				SecurityChecks.RESOLVES_TO_SELF,
				SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
				SecurityChecks.OWNER_IN_ALLOWLIST,
				SecurityChecks.PARENT_PERMISSIONS,
				SecurityChecks.PERMISSIONS,
				SecurityChecks.EXISTS,
				SecurityChecks.IS_FILE,
			]
		else:
			checks = [
				SecurityChecks.PARENT_RESOLVES_TO_SELF,
				SecurityChecks.RESOLVES_TO_SELF,
				SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
				SecurityChecks.OWNER_IN_ALLOWLIST,
				SecurityChecks.PARENT_PERMISSIONS,
				SecurityChecks.PERMISSIONS,
				SecurityChecks.EXISTS,
				SecurityChecks.IS_FILE,
			]

	violations = check_path(path, checks = checks)

	if len(violations) > 0:
		violation_strings = []
		for violation in violations:
			violation_strings.append(str(violation))
		violations_joined = ",".join(violation_strings)
		raise FilePathAuditError(f"Violated rules: {violations_joined}", path = path)

	# We have no default recourse if this write fails, so if the caller can handle the failure
	# they have to capture the exception
	with open(path, "r", encoding = "utf-8") as f:
		string = f.read()

	return string

def secure_which(path: FilePath, fallback_allowlist, security_policy: SecurityPolicy = SecurityPolicy.STRICT) -> FilePath:
	"""
	Path is the default path where the file expected to be found,
	or if no such default path exists, just the base name of the file.

	Path resolution occurs as follows:

	1. If the file exists at the location, and meets the security criteria
	   imposed by security_policy, it will be returned.

	2. If not, and the security policy permits, the entries in fallback_allowlist
	   will be used as parent for the filename to check for matches.

	3. If no matches are found in step 2, and security_policy permits,
	   path will be passed to shutil.which().

		Parameters:
			paths (list[FilePath]): A list of paths to the executable
			security_policy (SecurityPolicy):
				The policy to use when deciding whether or not
				it's OK to use the file at the path.
		Returns:
			path (FilePath): A path to the executable
		Exceptions:
			FileNotFoundError: Raised whenever no executable could
			be found that matched both path and security criteria
			RuntimeError: The path loops
	"""

	fully_resolved_paths = []

	for allowed_path in fallback_allowlist:
		if Path(allowed_path).resolve() == Path(allowed_path):
			fully_resolved_paths.append(allowed_path)

	violations = check_path(path,
				checks = [
					SecurityChecks.PARENT_RESOLVES_TO_SELF,
					SecurityChecks.RESOLVES_TO_SELF,
					SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
					SecurityChecks.OWNER_IN_ALLOWLIST,
					SecurityChecks.PARENT_PERMISSIONS,
					SecurityChecks.PERMISSIONS,
					SecurityChecks.EXISTS,
					SecurityChecks.IS_FILE,
					SecurityChecks.IS_EXECUTABLE,
				])

	# If we're using SecurityPolicy.STRICT we fail if we don't find a match here
	if security_policy == SecurityPolicy.STRICT:
		if len(violations) == 0:
			return path

		raise FileNotFoundError(f"secure_which() could not find an acceptable match for {path}")

	# If the security policy is ALLOWLIST* and fallback_allowlist isn't empty,
	# all paths in the fallback list will be tested one at a time with the basename from path,
	# until a match is found (or the list reaches the end).
	#
	# ALLOWLIST_STRICT behaves like STRICT, except with an allowlist
	# ALLOWLIST_RELAXED additionally allows the path not to resolve to itself, as long as it resolves
	# to a path in the allowlist that resolves to itself

	# Try the fallback options one by one
	name = PurePath(path).name

	tmp_allowlist = []
	for directory in fallback_allowlist:
		if directory.startswith("{HOME}"):
			directory.replace("{HOME}", HOMEDIR, count = 1)

		tmp_allowlist.append(directory)

	fallback_allowlist = tmp_allowlist

	for directory in fallback_allowlist:
		path = FilePath(os.path.join(directory, name))

		violations = check_path(path,
					checks = [
						SecurityChecks.PARENT_RESOLVES_TO_SELF,
						SecurityChecks.RESOLVES_TO_SELF,
						SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
						SecurityChecks.OWNER_IN_ALLOWLIST,
						SecurityChecks.PARENT_PERMISSIONS,
						SecurityChecks.PERMISSIONS,
						SecurityChecks.EXISTS,
						SecurityChecks.IS_FILE,
						SecurityChecks.IS_EXECUTABLE,
					])

		if len(violations) > 0:
			if security_policy == SecurityPolicy.ALLOWLIST_STRICT:
				continue

			if SecurityStatus.DOES_NOT_EXIST in violations:
				continue

			# IF the only violation is that the path doesn't resolve to
			# itself, but it resolves to a path that otherwise has no violations
			# and that is within the fallback_allowlist (and that entry in turn
			# resolves to itself) we return the path if policy is relaxed.
			# Since the behaviour of the called program might change if we call it
			# by a different name we do not return the resolved path; we return
			# the original path
			if len({ SecurityStatus.PATH_NOT_RESOLVING_TO_SELF,
			         SecurityStatus.PARENT_PATH_NOT_RESOLVING_TO_SELF }.union(violations)) <= 2:
				return path
			continue

		return path

	raise FileNotFoundError(f"secure_which() could not find an acceptable match for {name}")

def mkdir_if_not_exists(directory: FilePath, permissions: int = 0o750, verbose: bool = False, exit_on_failure: bool = False) -> None:
	"""
	Create a directory if it doesn't already exist
		Parameters:
			directory (str): The path to the directory to create
			permissions (int): File permissions (None uses system defaults)
			verbose (bool): Should extra debug messages be printed?
			exit_on_failure (bool): True to exit on failure, False to return (when possible)
	"""

	if verbose == True:
		iktprint.iktprint([ANSIThemeString("Creating directory ", "default"), ANSIThemeString(f"{directory}", "path"),
				   ANSIThemeString(" with permissions ", "default"), ANSIThemeString(f"{permissions:03o}", "emphasis")])

	user = getuser()

	violations = check_path(directory,
				message_on_error = verbose,
				parent_owner_allowlist = [user, "root"],
				owner_allowlist = [user],
				checks = [
					SecurityChecks.PARENT_RESOLVES_TO_SELF,
					SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
					SecurityChecks.OWNER_IN_ALLOWLIST,
					SecurityChecks.PARENT_PERMISSIONS,
					SecurityChecks.PERMISSIONS,
					SecurityChecks.EXISTS,
					SecurityChecks.IS_DIR,
				],
				exit_on_critical = exit_on_failure)

	if SecurityStatus.PARENT_DOES_NOT_EXIST in violations:
		sys.exit(errno.ENOENT)

	if SecurityStatus.PARENT_IS_NOT_DIR in violations:
		sys.exit(errno.EINVAL)

	if SecurityStatus.DOES_NOT_EXIST not in violations and SecurityStatus.IS_NOT_DIR in violations:
		sys.exit(errno.EEXIST)

	# These are the only acceptable conditions where we'd try to create the directory
	if len(violations) == 0 or violations == [SecurityStatus.DOES_NOT_EXIST]:
		Path(directory).mkdir(mode = permissions, exist_ok = True)

def copy_if_not_exists(src: FilePath, dst: FilePath, verbose: bool = False, exit_on_failure: bool = False, permissions = None) -> None:
	"""
	Copy a file if it doesn't already exist
		Parameters:
			src (str): The path to copy from
			dst (str): The path to copy to
			verbose (bool): Should extra debug messages be printed?
			exit_on_failure (bool): True to exit on failure, False to return (when possible)
			permissions (int): The file permissions to use (None to use system defaults)
	"""

	user = getuser()

	if verbose == True:
		iktprint.iktprint([ANSIThemeString("Copying file ", "default"), ANSIThemeString(f"{src}", "path"), ANSIThemeString(" to ", "default"), ANSIThemeString(f"{dst}", "path")])

	dst_path_parent = PurePath(dst).parent
	dst_path_parent_resolved = Path(dst_path_parent).resolve()

	dst_path = Path(dst)

	if dst_path.exists():
		if verbose == True:
			iktprint.iktprint([ANSIThemeString("Error", "error"), ANSIThemeString(": The target path ", "default"),
					   ANSIThemeString(f"{dst}", "path"),
					   ANSIThemeString(" already exists; refusing to overwrite.", "default")], stderr = True)
		return

	# Are there any path shenanigans going on?
	if dst_path_parent != dst_path_parent_resolved:
		iktprint.iktprint([ANSIThemeString("Critical", "critical"), ANSIThemeString(": The target path ", "default"),
				   ANSIThemeString(f"{dst}", "path"),
				   ANSIThemeString(" does not resolve to itself; this is either a configuration error or a security issue.", "default")], stderr = True)
		if exit_on_failure == True:
			iktprint.iktprint([ANSIThemeString("Aborting.", "default")], stderr = True)
			sys.exit(errno.EINVAL)

		iktprint.iktprint([ANSIThemeString("Refusing to copy file.", "default")], stderr = True)
		return

	dst_path_parent_path = Path(dst_path_parent)

	if not dst_path_parent_path.is_dir():
		iktprint.iktprint([ANSIThemeString("Error", "error"), ANSIThemeString(": The parent of the target path ", "default"),
				   ANSIThemeString(f"{dst}", "path"),
				   ANSIThemeString(" is not a directory; aborting.", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	if dst_path_parent_path.owner() not in ("root", user):
		iktprint.iktprint([ANSIThemeString("Error", "error"), ANSIThemeString(": The parent of the target path ", "default"),
				   ANSIThemeString(f"{dst}", "path"),
				   ANSIThemeString(" is not owned by ", "default"), ANSIThemeString("root", "emphasis"),
				   ANSIThemeString(" or ", "default"), ANSIThemeString(user, "emphasis"), ANSIThemeString("; aborting.", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	parent_path_stat = dst_path_parent_path.stat()
	parent_path_permissions = parent_path_stat.st_mode & 0o002

	if parent_path_permissions != 0:
		iktprint.iktprint([ANSIThemeString("Critical", "critical"), ANSIThemeString(": The parent of the target path ", "default"),
				   ANSIThemeString(f"{dst}", "path"),
				   ANSIThemeString(" is world writable", "default"), ANSIThemeString("; aborting.", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	# We don't need to inspect the content, so open it in binary mode
	with open(src, "rb") as fr:
		content = fr.read()
		# We shouldn't need "xb", since we've already checked that dst doesn't exist,
		# but better be safe than sorry
		if permissions is None:
			with open(dst, "xb") as fw:
				fw.write(content)
		else:
			with open(dst, "xb", opener = partial(os.open, mode = permissions)) as fw:
				fw.write(content)

def replace_symlink(src: FilePath, dst: FilePath, verbose: bool = False, exit_on_failure: bool = False) -> None:
	"""
	Replace as symlink (or create if it doesn't exist)
		Parameters:
			src (str): The path to link from
			dst (str): The path to link to
			verbose (bool): Should extra debug messages be printed?
			exit_on_failure (bool): True to exit on failure, False to return (when possible)
	"""

	user = getuser()

	if verbose == True:
		iktprint.iktprint([ANSIThemeString("Creating symbolic link ", "default"), ANSIThemeString(f"{dst}", "path"), ANSIThemeString(" pointing to ", "default"), ANSIThemeString(f"{src}", "path")])

	dst_path_parent = PurePath(dst).parent
	dst_path_parent_resolved = Path(dst_path_parent).resolve()

	dst_path = Path(dst)
	src_path = Path(src)

	# Are there any path shenanigans going on?
	if dst_path_parent != dst_path_parent_resolved:
		iktprint.iktprint([ANSIThemeString("Critical", "critical"), ANSIThemeString(": The target path ", "default"),
				   ANSIThemeString(f"{dst}", "path"),
				   ANSIThemeString(" does not resolve to itself; this is either a configuration error or a security issue.", "default")], stderr = True)
		if exit_on_failure == True:
			iktprint.iktprint([ANSIThemeString("Aborting.", "default")], stderr = True)
			sys.exit(errno.EINVAL)

		iktprint.iktprint([ANSIThemeString("Refusing to create symlink.", "default")], stderr = True)
		return

	dst_path_parent_path = Path(dst_path_parent)

	if not dst_path_parent_path.is_dir():
		iktprint.iktprint([ANSIThemeString("Error", "error"), ANSIThemeString(": The parent of the target path ", "default"),
				   ANSIThemeString(f"{dst}", "path"),
				   ANSIThemeString(" is not a directory; aborting.", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	if dst_path_parent_path.owner() not in ("root", user):
		iktprint.iktprint([ANSIThemeString("Error", "error"), ANSIThemeString(": The parent of the target path ", "default"),
				   ANSIThemeString(f"{dst}", "path"),
				   ANSIThemeString(" is not owned by ", "default"),
				   ANSIThemeString("root", "emphasis"),
				   ANSIThemeString(" or ", "default"),
				   ANSIThemeString(user, "emphasis"),
				   ANSIThemeString("; aborting.", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	parent_path_stat = dst_path_parent_path.stat()
	parent_path_permissions = parent_path_stat.st_mode & 0o002

	if parent_path_permissions != 0:
		iktprint.iktprint([ANSIThemeString("Critical", "critical"), ANSIThemeString(": The parent of the target path ", "default"),
				   ANSIThemeString(f"{dst}", "path"),
				   ANSIThemeString(" is world writable", "default"), ANSIThemeString("; aborting.", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	# Since the parent path resolves safely, we can unlink dst_path if it's a symlink
	if dst_path.is_symlink():
		dst_path.unlink()

	dst_path.symlink_to(src_path)

# This executes a command without capturing the output
def execute_command(args: List[Union[FilePath, str]], env: Optional[Dict] = None, comparison: int = 0) -> bool:
	"""
	Executes a command

		Parameters:
			args (list[str]): The commandline
			env (dict): Environment variables to set
			comparison (int): The value to compare retval to
		Returns:
			retval.returncode == comparison (bool): True if retval.returncode == comparison, False otherwise
	"""

	if env is None:
		retval = subprocess.run(args, check = False)
	else:
		retval = subprocess.run(args, env = env, check = False)
	return retval.returncode == comparison

# This executes a command with the output captured
def execute_command_with_response(args: List[str]) -> str:
	"""
	Executes a command and returns stdout

		Parameters:
			args (list[str]): The commandline
		Returns:
			stdout (str): The stdout from the execution
	"""
	result = subprocess.run(args, stdout = PIPE, stderr = STDOUT, check = False)
	return result.stdout.decode("utf-8")
