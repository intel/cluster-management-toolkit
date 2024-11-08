#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.8)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

# pylint: disable=too-many-lines

"""
I/O helpers
"""

import errno
from functools import partial
from getpass import getuser
import os
from pathlib import Path, PurePath
import subprocess  # nosec
from subprocess import PIPE, STDOUT  # nosec
import sys
from typing import Any, cast, Optional

from clustermanagementtoolkit.cmttypes import deep_get, DictPath
from clustermanagementtoolkit.cmttypes import FilePath, FilePathAuditError
from clustermanagementtoolkit.cmttypes import SecurityChecks, SecurityPolicy, SecurityStatus

from clustermanagementtoolkit.cmtpaths import HOMEDIR


# pylint: disable-next=too-many-branches
def expand_path(path: str, search_paths: Optional[list[str]] = None,
                suffixes: Optional[list[str]] = None,
                fallback: str = "") -> tuple[FilePath, bool]:
    """
    Given a path, filename or partial filename, expand it to its full path

        Parameters:
            path (str): A path, filename, or partial filename
            search_paths (list(str)): The list of paths to attempt
                                      when a naked filename is passed
            suffixes (list(str)): If partial_path doesn't exist,
                                  attempt the same path with suffix appended
            fallback (str): The path to use if the provided path is empty or doesn't exist
        Returns:
            (FilePath, bool):
                (FilePath): The full path
                (bool): True if successful, False if fallback is returned
    """
    partial_paths = []
    full_path = None

    if path is None or not path:
        return FilePath(fallback), False

    if path.startswith("{HOME}/"):
        partial_paths.append(os.path.join(HOMEDIR, path[len("{HOME}/"):]))
    elif "/" in path:
        partial_paths.append(path)
    else:
        if search_paths is None:
            return FilePath(fallback), False
        for search_path in search_paths:
            if search_path.startswith("{HOME}/"):
                search_path = os.path.join(HOMEDIR, search_path[len("{HOME}/"):])
            partial_paths.append(os.path.join(search_path, path))

    for partial_path in partial_paths:
        path_entry = Path(partial_path)
        if path_entry.is_file():
            full_path = partial_path
            break
        if suffixes is not None:
            for suffix in suffixes:
                partial_path_suffixed = f"{partial_path}{suffix}"
                path_entry = Path(partial_path_suffixed)
                if path_entry.is_file():
                    full_path = partial_path_suffixed
                    break
    if full_path is None:
        return FilePath(fallback), False

    return FilePath(full_path), True


def join_securitystatus_set(separator: str, securitystatuses: set[SecurityStatus]) -> str:
    """
    Given a set of violations, join it to a sorted string

        Parameters:
            separator (str): The separator to use between items
            securitystatuses (set(SecurityStatus)): The set of security statuses
        Returns:
            (str): The string of joined securitystatuses
    """
    securitystatus_str = ""

    for securitystatus in sorted(securitystatuses):
        if securitystatus_str:
            securitystatus_str += separator
        securitystatus_str += repr(securitystatus)

    return securitystatus_str


# pylint: disable=too-many-statements,too-many-locals,too-many-branches
def check_path(path: FilePath, **kwargs: Any) -> list[SecurityStatus]:
    """
    Verifies that a path meets certain security criteria;
    if the path fails to meet the criteria the function returns False and optionally
    outputs an error message. Critical errors will either raise an exception or exit the program.

        Parameters:
            path (FilePath): The path to the file to verify
            **kwargs (dict[str, Any]): Keyword arguments
                parent_allowlist ([str]): A list of acceptable file owners;
                                          by default [user, "root"]
                owner_allowlist ([str]): A list of acceptable file owners;
                                         by default [user, "root"]
                checks ([SecurityChecks]): A list of checks that should be performed
                exit_on_critical (bool): By default check_path returns SecurityStatus
                                         if a critical criteria violation is found;
                                         this flag can be used to exit the program
                                         instead if the violation is critical
                message_on_error (bool): If this is set to true an error message
                                         will be printed to the console
        Returns:
            ([SecurityStatus]): [SecurityStatus.OK] if all criteria are met,
                                otherwise a list of all violated policies
    """
    parent_owner_allowlist: Optional[list[str]] = \
        deep_get(kwargs, DictPath("parent_owner_allowlist"), None)
    owner_allowlist: Optional[list[str]] = \
        deep_get(kwargs, DictPath("owner_allowlist"), None)
    checks: Optional[list[SecurityChecks]] = deep_get(kwargs, DictPath("checks"), None)
    exit_on_critical: bool = deep_get(kwargs, DictPath("exit_on_critical"), False)
    message_on_error: bool = deep_get(kwargs, DictPath("message_on_error"), False)

    # This is most likely a security violation; treat it as such
    if "\x00" in path:
        stripped_path = path.replace("\x00", "<NUL>")
        raise ValueError(f"Critical: the path {stripped_path} contains NUL-bytes:\n"
                         "This is either a programming error, a system error, "
                         "file or memory corruption, "
                         "or a deliberate attempt to bypass security; aborting.")

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

    # This test is not optional; if the parent directory does not exist it is always a failure
    if not parent_entry.exists():
        if message_on_error:
            msg = "Critical: The parent of the target path " \
                  f"{path} does not exist"
            if exit_on_critical:  # pragma: no cover
                msg += "; aborting."
                print(msg, file=sys.stderr)
                sys.exit(errno.EINVAL)
            print(msg, sys.stderr)
        violations.append(SecurityStatus.PARENT_DOES_NOT_EXIST)
        return violations

    if not parent_entry.is_dir():
        if message_on_error:
            msg = "Critical: The parent of the target path " \
                  f"{path} exists but is not a directory; " \
                  "this is either a configuration error " \
                  "or a security issue"
            if exit_on_critical:  # pragma: no cover
                msg += "; aborting."
                print(msg, sys.stderr)
                sys.exit(errno.EINVAL)
            print(msg, sys.stderr)
        violations.append(SecurityStatus.PARENT_IS_NOT_DIR)
        return violations

    if SecurityChecks.PARENT_OWNER_IN_ALLOWLIST in checks \
            and parent_entry.owner() not in parent_owner_allowlist:
        if message_on_error:
            msg = "Critical: The parent of the target path " \
                  f"{path} is not owned by one of (" \
                  + ", ".join(parent_owner_allowlist) + ")"
            if exit_on_critical:  # pragma: no cover
                msg += "; aborting."
                print(msg, sys.stderr)
                sys.exit(errno.EINVAL)
            print(msg, sys.stderr)
        violations.append(SecurityStatus.PARENT_OWNER_NOT_IN_ALLOWLIST)

    parent_path_stat = parent_entry.stat()
    parent_path_permissions = parent_path_stat.st_mode & 0o002
    if SecurityChecks.PARENT_PERMISSIONS in checks and parent_path_permissions != 0:
        if message_on_error:
            msg = "Critical: The parent of the target path " \
                  f"{path} is world writable"
            if exit_on_critical:  # pragma: no cover
                msg += "; aborting."
                print(msg, sys.stderr)
                sys.exit(errno.EINVAL)
            print(msg, sys.stderr)
        violations.append(SecurityStatus.PARENT_PERMISSIONS)

    parent_entry_resolved = parent_entry.resolve()
    parent_entry_systemdir = False
    if str(parent_entry) in ("/bin", "/sbin", "/usr/bin", "/usr/sbin") \
            and str(parent_entry_resolved) in ("/bin", "/sbin", "/usr/bin", "/usr/sbin"):
        parent_entry_systemdir = True

    # Are there any path shenanigans going on?  If we are dealing with
    # {/bin,/sbin,/usr/bin,/usr/sbin}/path => {/bin,/sbin,/usr/bin,/usr/sbin}/path
    # the symlink is acceptable.
    if SecurityChecks.PARENT_RESOLVES_TO_SELF in checks \
            and parent_entry != parent_entry_resolved and not parent_entry_systemdir:
        if message_on_error:
            msg = "Critical: The parent of the target path " \
                  f"{path} does not resolve to itself; this is either a " \
                  "configuration error or a security issue"
            if exit_on_critical:  # pragma: no cover
                msg += "; aborting."
                print(msg, sys.stderr)
                sys.exit(errno.EINVAL)
            print(msg, sys.stderr)
        violations.append(SecurityStatus.PARENT_PATH_NOT_RESOLVING_TO_SELF)

    # Are there any path shenanigans going on?  We first resolve the parent path,
    # then check the rest; this way we can see if the target is a symlink and see
    # where it ends up.
    name = path_entry.name
    tmp_entry = Path(os.path.join(parent_entry_resolved, name))

    if SecurityChecks.RESOLVES_TO_SELF in checks and tmp_entry != tmp_entry.resolve():
        if message_on_error:
            msg = "Critical: The target path " \
                  f"{path} does not resolve to itself; this is either a " \
                  "configuration error or a security issue"
            if exit_on_critical:  # pragma: no cover
                msg += "; aborting."
                print(msg, sys.stderr)
                sys.exit(errno.EINVAL)
            print(msg, sys.stderr)
        violations.append(SecurityStatus.PATH_NOT_RESOLVING_TO_SELF)

    if not path_entry.exists():
        if SecurityChecks.EXISTS in checks:
            violations.append(SecurityStatus.DOES_NOT_EXIST)
        if not violations:
            violations = [SecurityStatus.OK]
        return violations

    if SecurityChecks.OWNER_IN_ALLOWLIST in checks and path_entry.owner() not in owner_allowlist:
        if message_on_error:
            msg = f"Critical: The target path {path} is not owned by one of (" \
                  + ", ".join(owner_allowlist) + ")"
            if exit_on_critical:  # pragma: no cover
                msg += "; aborting."
                print(msg, sys.stderr)
                sys.exit(errno.EINVAL)
            print(msg, sys.stderr)
        violations.append(SecurityStatus.OWNER_NOT_IN_ALLOWLIST)

    path_stat = path_entry.stat()
    path_permissions = path_stat.st_mode & 0o002
    if path_permissions != 0:
        if message_on_error:
            msg = f"Critical: The target path {path} is world writable"
            if exit_on_critical:  # pragma: no cover
                msg += "; aborting."
                print(msg, sys.stderr)
                sys.exit(errno.EINVAL)
            print(msg, sys.stderr)
        violations.append(SecurityStatus.PERMISSIONS)

    if path_entry.exists() and SecurityChecks.PERMISSIONS in checks \
            and not os.access(path, os.R_OK):
        if message_on_error:
            msg = f"Critical: The target path {path} cannot be read"
            if exit_on_critical:  # pragma: no cover
                msg += "; aborting."
                print(msg, sys.stderr)
                sys.exit(errno.EINVAL)
            print(msg, sys.stderr)
        violations.append(SecurityStatus.PERMISSIONS)

    if SecurityChecks.IS_SYMLINK in checks and not path_entry.is_symlink():
        if message_on_error:
            msg = f"Error: The target path {path}" \
                  " exists but is not a symlink; this is either a " \
                  "configuration error or a security issue"
            print(msg, sys.stderr)
        violations.append(SecurityStatus.IS_NOT_SYMLINK)

    # is_file() returns True even if path is a symlink to a file rather than a file
    if SecurityChecks.IS_FILE in checks and not path_entry.is_file():
        if message_on_error:
            msg = f"Error: The target path {path}" \
                  " exists but is not a file; this is either a " \
                  "configuration error or a security issue"
            print(msg, sys.stderr)
        violations.append(SecurityStatus.IS_NOT_FILE)

    # is_file() returns True even if path is a symlink to a file rather than a file
    if SecurityChecks.IS_DIR in checks and not path_entry.is_dir():
        if message_on_error:
            msg = f"Error: The target path {path}" \
                  " exists but is not a directory; this is either a " \
                  "configuration error or a security issue"
            print(msg, sys.stderr)
        violations.append(SecurityStatus.IS_NOT_DIR)

    if SecurityChecks.IS_NOT_EXECUTABLE in checks \
            and os.access(path, os.X_OK) and not path_entry.is_dir():
        if message_on_error:
            msg = f"Warning: The target path {path}" \
                  " is executable but should not be; skipping"
            print(msg, sys.stderr)
        violations.append(SecurityStatus.IS_EXECUTABLE)

    if SecurityChecks.IS_EXECUTABLE in checks and not os.access(path, os.X_OK):
        if message_on_error:
            msg = f"Warning: The target path {path}" \
                  " exists but is not executable; skipping"
            print(msg, sys.stderr)
        violations.append(SecurityStatus.IS_NOT_EXECUTABLE)

    if not violations:
        violations = [SecurityStatus.OK]

    return violations


def secure_rm(path: FilePath, ignore_non_existing: bool = False) -> None:
    """
    Remove a file

        Parameters:
            path (FilePath): The path to the file to remove
        Raises:
            cmttypes.FilePathAuditError
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

    violations = check_path(path, checks=checks)

    ignoring_non_existing = False

    if ignore_non_existing:
        try:
            violations.remove(SecurityStatus.DOES_NOT_EXIST)
            ignoring_non_existing = True
        except ValueError:
            # This is to allow remove when DOES_NOT_EXIST isn't in violations
            pass

    if not violations:
        violations = [SecurityStatus.OK]

    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=path)

    if not ignoring_non_existing:
        Path(path).unlink()


def secure_rmdir(path: FilePath, ignore_non_existing: bool = False) -> None:
    """
    Remove a directory

        Parameters:
            path (FilePath): The path to the directory to remove
            ignore_non_existing (bool): Ignore non-existing directories
        Raises:
            cmttypes.FilePathAuditError
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

    violations = check_path(path, checks=checks)

    ignoring_non_existing = False

    if ignore_non_existing:
        try:
            violations.remove(SecurityStatus.DOES_NOT_EXIST)
            ignoring_non_existing = True
        except ValueError:
            # This is to allow remove when DOES_NOT_EXIST isn't in violations
            pass

    if not violations:
        violations = [SecurityStatus.OK]

    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=path)

    if not ignoring_non_existing:
        violations = []
        try:
            Path(path).rmdir()
        except OSError as e:
            if "[Errno 39] Directory not empty" in str(e):
                violations.append(SecurityStatus.DIR_NOT_EMPTY)
                violations_joined = join_securitystatus_set(",", set(violations))
                raise FilePathAuditError(f"Violated rules: {violations_joined}", path=path) from e
            raise OSError from e


def secure_write_string(path: FilePath, string: str, **kwargs: Any) -> None:
    """
    Write a string to a file in a safe manner

        Parameters:
            path (FilePath): The path to write to
            string (str): The string to write
            **kwargs (dict[str, Any]): Keyword arguments
                permissions (int): File permissions (None uses system defaults)
                write_mode (str): [w, a, x, wb, ab, xb] Write, Append, Exclusive Write,
                                                        text or binary
                allow_relative_path (bool): Is it acceptable to have the path not resolve to self?
                temporary (bool): Is the file a tempfile?
                                  If so we need to disable the check for parent permissions
        Raises:
            cmttypes.FilePathAuditError
    """
    permissions: Optional[int] = deep_get(kwargs, DictPath("permissions"), None)
    write_mode: str = deep_get(kwargs, DictPath("write_mode"), "w")
    allow_relative_path: bool = deep_get(kwargs, DictPath("allow_relative_path"), False)
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    if write_mode not in ("a", "ab", "w", "wb", "x", "xb"):
        raise ValueError(f"Invalid write mode “{write_mode}“; "
                         "permitted modes: “a(b)“ (append (binary)), "
                         "“w(b)“ (write (binary)) and “x(b)“ (exclusive write (binary))")

    checks = [
        SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
        SecurityChecks.OWNER_IN_ALLOWLIST,
        SecurityChecks.PERMISSIONS,
        SecurityChecks.PARENT_PERMISSIONS,
        SecurityChecks.IS_FILE,
    ]

    if temporary:
        checks.remove(SecurityChecks.PARENT_PERMISSIONS)

    if not allow_relative_path:
        checks += [
            SecurityChecks.PARENT_RESOLVES_TO_SELF,
            SecurityChecks.RESOLVES_TO_SELF,
        ]

    violations = check_path(path, checks=checks)

    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=path)

    if "b" in write_mode:
        # We have no default recourse if this write fails, so if the caller can handle the failure
        # they have to capture the exception
        try:
            if permissions is None:
                # This code path will only be used for binary writes,
                # but pylint seems to stupid to realise this, so it complains
                # about missing encoding, hence we have to override that warning
                # pylint: disable-next=unspecified-encoding
                with open(path, write_mode) as f:
                    f.write(string)
            else:
                # This code path will only be used for binary writes,
                # but pylint seems to stupid to realise this, so it complains
                # about missing encoding, hence we have to override that warning
                # pylint: disable-next=unspecified-encoding
                with open(path, write_mode, opener=partial(os.open, mode=permissions)) as f:
                    f.write(string)
        except FileExistsError as e:
            if write_mode == "xb":
                raise FilePathAuditError(f"Violated rules: {repr(SecurityStatus.EXISTS)}",
                                         path=path) from e
    else:
        # We have no default recourse if this write fails, so if the caller can handle the failure
        # they have to capture the exception
        try:
            if permissions is None:
                with open(path, write_mode, encoding="utf-8") as f:
                    f.write(string)
            else:
                with open(path, write_mode, opener=partial(os.open, mode=permissions),
                          encoding="utf-8") as f:
                    f.write(string)
        except FileExistsError as e:
            if write_mode == "x":
                raise FilePathAuditError(f"Violated rules: {repr(SecurityStatus.EXISTS)}",
                                         path=path) from e


def secure_read(path: FilePath,
                checks: Optional[list[SecurityChecks]] = None,
                directory_is_symlink: bool = False,
                read_mode: str = "r", temporary: bool = False) -> str | bytes:
    """
    Read the content of a file in a safe manner

        Parameters:
            path (FilePath): The path to read from
            checks ([SecurityChecks]): A list of checks that should be performed
            directory_is_symlink (bool): The directory that the path points to is a symlink
            read_mode (str): [r, rb] Read text or binary
            temporary (bool): Is the file a tempfile?
                              If so we need to disable the check for parent permissions
        Returns:
            (union[str, bytes]): The read string
        Raises:
            cmttypes.FilePathAuditError
    """
    if read_mode not in ("r", "rb"):
        raise ValueError(f"Invalid read mode “{read_mode}“; "
                         "permitted modes: “r(b)“ (read (binary))")

    if checks is None:
        if directory_is_symlink:
            parent_dir = FilePath(PurePath(path).parent)

            # The directory itself may be a symlink. This is expected behaviour when installing
            # from a git repo, but we only allow it if the rest of the path components are secure.
            checks = [
                SecurityChecks.PARENT_RESOLVES_TO_SELF,
                SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
                SecurityChecks.OWNER_IN_ALLOWLIST,
                SecurityChecks.PARENT_PERMISSIONS,
                SecurityChecks.PERMISSIONS,
                SecurityChecks.EXISTS,
                SecurityChecks.IS_DIR,
            ]

            if temporary:
                checks.remove(SecurityChecks.PARENT_PERMISSIONS)

            violations = check_path(parent_dir, checks=checks)
            if violations != [SecurityStatus.OK]:
                violations_joined = join_securitystatus_set(",", set(violations))
                raise FilePathAuditError(f"Violated rules: {violations_joined}", path=parent_dir)

            # We do not want to check that parent resolves to itself,
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

    if temporary:
        try:
            checks.remove(SecurityChecks.PARENT_PERMISSIONS)
        except ValueError:
            pass

    violations = check_path(path, checks=checks)

    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=path)

    # We have no default recourse if this write fails, so if the caller can handle the failure
    # they have to capture the exception
    if read_mode == "r":
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            string: str | bytes = f.read()
    else:
        with open(path, "rb") as bf:
            string = bf.read()

    return string


def secure_read_string(path: FilePath, checks: Optional[list[SecurityChecks]] = None,
                       directory_is_symlink: bool = False, temporary: bool = False) -> str:
    """
    Read a string from a file in a safe manner

        Parameters:
            path (FilePath): The path to read from
            checks ([SecurityChecks]): A list of checks that should be performed
            directory_is_symlink (bool): The directory that the path points to is a symlink
            temporary (bool): Is the file a tempfile?
                              If so we need to disable the check for parent permissions
        Returns:
            (str): The read string
        Raises:
            cmttypes.FilePathAuditError
    """
    return cast(str, secure_read(path, checks=checks,
                                 directory_is_symlink=directory_is_symlink,
                                 read_mode="r", temporary=temporary))


def secure_which(path: FilePath, fallback_allowlist: list[str],
                 security_policy: SecurityPolicy = SecurityPolicy.STRICT,
                 executable: bool = True) -> FilePath:
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
            paths ([FilePath]): A list of paths to the executable
            security_policy (SecurityPolicy): The policy to use when deciding whether or not
                                              it is OK to use the file at the path.
            executable (bool): Should the path point to an executable?
        Returns:
            (FilePath): A path to the executable
        Exceptions:
            FileNotFoundError: Raised whenever no executable could be found
                               that matched both path and security criteria
            RuntimeError: The path loops
    """
    fully_resolved_paths = []

    for allowed_path in fallback_allowlist:
        if Path(allowed_path).resolve() == Path(allowed_path):
            fully_resolved_paths.append(allowed_path)

    checks = [
        SecurityChecks.PARENT_RESOLVES_TO_SELF,
        SecurityChecks.RESOLVES_TO_SELF,
        SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
        SecurityChecks.OWNER_IN_ALLOWLIST,
        SecurityChecks.PARENT_PERMISSIONS,
        SecurityChecks.EXISTS,
        SecurityChecks.IS_FILE,
    ]

    if executable:
        checks.append(SecurityChecks.IS_EXECUTABLE)
    else:
        checks.append(SecurityChecks.PERMISSIONS)

    violations = check_path(path, checks=checks)

    if violations == [SecurityStatus.OK]:
        return path

    # If we are using SecurityPolicy.STRICT we fail if we cannot find a match here
    if security_policy == SecurityPolicy.STRICT:
        raise FileNotFoundError(f"secure_which() could not find an acceptable match for {path}")

    # If the security policy is ALLOWLIST* and fallback_allowlist is not empty,
    # all paths in the fallback list will be tested one at a time with the basename from path,
    # until a match is found (or the list reaches the end).
    #
    # ALLOWLIST_STRICT behaves like STRICT, except with an allowlist
    # ALLOWLIST_RELAXED additionally allows the path not to resolve to itself,
    # as long as it resolves to a path in the allowlist that resolves to itself.

    # Try the fallback options one by one
    name = PurePath(path).name

    tmp_allowlist = []
    for directory in fallback_allowlist:
        if directory.startswith("{HOME}"):
            directory = directory.replace("{HOME}", HOMEDIR, 1)

        tmp_allowlist.append(directory)

    fallback_allowlist = tmp_allowlist

    for directory in fallback_allowlist:
        path = FilePath(os.path.join(directory, name))

        violations = check_path(path, checks=checks)

        if violations != [SecurityStatus.OK]:
            if security_policy == SecurityPolicy.ALLOWLIST_STRICT:
                continue

            if SecurityStatus.DOES_NOT_EXIST in violations:
                continue

            # If the only violation is that the path does not resolve to
            # itself, but it resolves to a path that otherwise has no violations
            # and that is within the fallback_allowlist (and that entry in turn
            # resolves to itself) we return the path if policy is relaxed.
            # Since the behaviour of the called program might change if we call it
            # by a different name we do not return the resolved path; we return
            # the original path
            if len({SecurityStatus.PATH_NOT_RESOLVING_TO_SELF,
                    SecurityStatus.PARENT_PATH_NOT_RESOLVING_TO_SELF}.union(violations)) <= 2:
                return path
            continue

        return path

    raise FileNotFoundError(f"secure_which() could not find an acceptable match for {name}")


def secure_mkdir(directory: FilePath, permissions: int = 0o750, verbose: bool = False,
                 exist_ok: bool = True, exit_on_failure: bool = False) -> list[SecurityStatus]:
    """
    Create a directory if it does not already exist
        Parameters:
            directory (str): The path to the directory to create
            permissions (int): File permissions (None uses system defaults)
            verbose (bool): Should extra debug messages be printed?
            exit_on_failure (bool): True to exit on failure, False to return (when possible)
        Returns:
            ([SecurityStatus]): [SecurityStatus.OK] if all criteria are met,
                                otherwise a list of all violated policies
    """
    if verbose:
        print(f"Creating directory {directory}"
              f" with permissions {permissions:03o}")

    user = getuser()

    violations = check_path(directory, message_on_error=verbose,
                            parent_owner_allowlist=[user, "root"],
                            owner_allowlist=[user],
                            checks=[
                                SecurityChecks.PARENT_RESOLVES_TO_SELF,
                                SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
                                SecurityChecks.OWNER_IN_ALLOWLIST,
                                SecurityChecks.PARENT_PERMISSIONS,
                                SecurityChecks.PERMISSIONS,
                                SecurityChecks.EXISTS,
                                SecurityChecks.IS_DIR,
                            ],
                            exit_on_critical=exit_on_failure)

    if SecurityStatus.PARENT_DOES_NOT_EXIST in violations:
        if exit_on_failure:  # pragma: no cover
            sys.exit(errno.ENOENT)
        return violations

    if SecurityStatus.PARENT_IS_NOT_DIR in violations:
        if exit_on_failure:  # pragma: no cover
            sys.exit(errno.EINVAL)
        return violations

    if SecurityStatus.DOES_NOT_EXIST not in violations and SecurityStatus.IS_NOT_DIR in violations:
        if exit_on_failure:  # pragma: no cover
            sys.exit(errno.EEXIST)
        return violations

    # These are the only acceptable conditions where we'd try to create the directory
    if violations in ([SecurityStatus.OK], [SecurityStatus.DOES_NOT_EXIST]):
        violations = []
        try:
            Path(directory).mkdir(mode=permissions, exist_ok=exist_ok)
        except FileExistsError:
            violations.append(SecurityStatus.EXISTS)
        if not violations:
            violations.append(SecurityStatus.OK)

    return violations


def secure_copy(src: FilePath, dst: FilePath, verbose: bool = False,
                exit_on_failure: bool = False,
                permissions: Optional[int] = None) -> list[SecurityStatus]:
    """
    Copy a file
        Parameters:
            src (str): The path to copy from
            dst (str): The path to copy to
            verbose (bool): Should extra debug messages be printed?
            exit_on_failure (bool): True to exit on failure, False to return (when possible)
            permissions (int): The file permissions to use (None to use system defaults)
        Returns:
            ([SecurityStatus]): [SecurityStatus.OK] if all criteria are met,
                                                    otherwise a list of all violated policies
    """
    if verbose:
        print(f"Copying file {src} to {dst}")

    # Are there any path shenanigans going on?
    checks = [
        SecurityChecks.PARENT_RESOLVES_TO_SELF,
        SecurityChecks.RESOLVES_TO_SELF,
        SecurityChecks.OWNER_IN_ALLOWLIST,
        SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
        SecurityChecks.PERMISSIONS,
        SecurityChecks.PARENT_PERMISSIONS,
        SecurityChecks.EXISTS,
        SecurityChecks.IS_FILE,
    ]

    violations = check_path(src, checks=checks)
    if violations != [SecurityStatus.OK]:
        if verbose:
            violations_joined = join_securitystatus_set(",", set(violations))
            print(f"Critical: The source path {src}"
                  " violates the following security checks "
                  f"[{violations_joined}]; this is either a "
                  "configuration error or a security issue.", sys.stderr)
        if exit_on_failure:  # pragma: no cover
            sys.exit(errno.EINVAL)
        return violations

    # Are there any path shenanigans going on?
    checks = [
        SecurityChecks.PARENT_RESOLVES_TO_SELF,
        SecurityChecks.RESOLVES_TO_SELF,
        SecurityChecks.OWNER_IN_ALLOWLIST,
        SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
        SecurityChecks.PERMISSIONS,
        SecurityChecks.PARENT_PERMISSIONS,
        SecurityChecks.IS_DIR,
    ]

    dst_path_parent = PurePath(dst).parent
    violations = check_path(FilePath(PurePath(dst).parent), checks=checks)

    if violations != [SecurityStatus.OK]:
        if verbose:
            violations_joined = join_securitystatus_set(",", set(violations))
            print(f"Critical: The target path {dst_path_parent}"
                  " violates the following security checks "
                  f"[{violations_joined}]; this is either a "
                  "configuration error or a security issue.", sys.stderr)
        if exit_on_failure:  # pragma: no cover
            sys.exit(errno.EINVAL)
        return violations

    dst_path = Path(dst)

    if dst_path.exists():
        if verbose:
            print(f"Error: The target path {dst}"
                  " already exists; refusing to overwrite.", sys.stderr)
        if exit_on_failure:  # pragma: no cover
            sys.exit(errno.EINVAL)
        return [SecurityStatus.EXISTS]

    # We do not need to inspect the content, so open it in binary mode
    # We should not need "xb", since we have already checked that dst does not exist,
    # but better be safe than sorry
    try:
        if permissions is None:
            with open(src, "rb") as fr, open(dst, "xb") as fw:
                content = fr.read()
                fw.write(content)
        else:
            with open(src, "rb") as fr, open(dst, "xb",
                                             opener=partial(os.open, mode=permissions)) as fw:
                content = fr.read()
                fw.write(content)
    except PermissionError:
        if verbose:
            print(f"Error: The target path {dst}"
                  " cannot be written to (Permission denied).", sys.stderr)
        if exit_on_failure:  # pragma: no cover
            sys.exit(errno.EINVAL)
        return [SecurityStatus.PERMISSIONS]

    return [SecurityStatus.OK]


# pylint: disable-next=too-many-return-statements,too-many-statements
def secure_symlink(src: FilePath, dst: FilePath, verbose: bool = False,
                   exit_on_failure: bool = False,
                   replace_existing: bool = False) -> list[SecurityStatus]:
    """
    Create or replace a symlink
        Parameters:
            src (str): The path to link from
            dst (str): The path to link to
            verbose (bool): Should extra debug messages be printed?
            exit_on_failure (bool): True to exit on failure, False to return (when possible)
        Returns:
            ([SecurityStatus]): [SecurityStatus.OK] if all criteria are met,
                                otherwise a list of all violated policies
    """
    user = getuser()

    if verbose:
        print(f"Creating symbolic link {dst} pointing to {src}")

    dst_path_parent = PurePath(dst).parent
    dst_path_parent_resolved = Path(dst_path_parent).resolve()

    dst_path = Path(dst)
    src_path = Path(src)

    # Are there any path shenanigans going on?
    if dst_path_parent != dst_path_parent_resolved:
        if verbose:
            print("Critical: The target path "
                  f"{dst} does not resolve to itself; this is either a "
                  "configuration error or a security issue.", sys.stderr)
        if exit_on_failure:  # pragma: no cover
            if verbose:
                print("Aborting.", sys.stderr)
            sys.exit(errno.EINVAL)
        if verbose:
            print("Refusing to create symlink.", sys.stderr)
        return [SecurityStatus.PARENT_PATH_NOT_RESOLVING_TO_SELF]

    dst_path_parent_path = Path(dst_path_parent)

    if not dst_path_parent_path.is_dir():
        if verbose:
            print("Error: The parent of the target path "
                  f"{dst} is not a directory.", sys.stderr)
        if exit_on_failure:  # pragma: no cover
            if verbose:
                print("Aborting.", sys.stderr)
            sys.exit(errno.EINVAL)
        if verbose:
            print("Refusing to create symlink.", sys.stderr)
        return [SecurityStatus.PARENT_IS_NOT_DIR]

    if dst_path_parent_path.owner() not in ("root", user):
        if verbose:
            print("Error: The parent of the target path "
                  f"{dst} is not owned by root or {user}.", sys.stderr)
        if exit_on_failure:  # pragma: no cover
            if verbose:
                print("Aborting.", sys.stderr)
            sys.exit(errno.EINVAL)
        if verbose:
            print("Refusing to create symlink.", sys.stderr)
        return [SecurityStatus.PARENT_OWNER_NOT_IN_ALLOWLIST]

    parent_path_stat = dst_path_parent_path.stat()
    parent_path_permissions = parent_path_stat.st_mode & 0o002

    if parent_path_permissions != 0:
        print("Critical: The parent of the target path "
              f"{dst} is world writable.", sys.stderr)
        if exit_on_failure:  # pragma: no cover
            if verbose:
                print("Aborting.", sys.stderr)
            sys.exit(errno.EINVAL)
        if verbose:
            print("Refusing to create symlink.", sys.stderr)
        return [SecurityStatus.PARENT_PERMISSIONS]

    # Verify that the source path exists and that the owner and permissions are reliable;
    # we do not make further assumptions.
    checks = [
        SecurityChecks.PARENT_RESOLVES_TO_SELF,
        SecurityChecks.RESOLVES_TO_SELF,
        SecurityChecks.OWNER_IN_ALLOWLIST,
        SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
        SecurityChecks.PERMISSIONS,
        SecurityChecks.PARENT_PERMISSIONS,
        SecurityChecks.EXISTS,
    ]

    violations = check_path(FilePath(src_path), checks=checks)

    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        if verbose:
            print("Critical: The source path "
                  f"{src} violates the following security checks "
                  f"[{violations_joined}]; this is either a "
                  "configuration error or a security issue.", sys.stderr)
        if exit_on_failure:  # pragma: no cover
            if verbose:
                print("Aborting.", sys.stderr)
            sys.exit(errno.EINVAL)
        if verbose:
            print("Refusing to create symlink.", sys.stderr)
        return violations

    # Since the parent path resolves safely, we can unlink dst_path if it is a symlink
    if dst_path.is_symlink():
        if not replace_existing:
            if verbose:
                print("Critical: The source path "
                      f"{src} exists and replace_existing=False.", sys.stderr)
            if exit_on_failure:  # pragma: no cover
                if verbose:
                    print("Aborting.", sys.stderr)
                sys.exit(errno.EEXIST)
            if verbose:
                print("Refusing to create symlink.", sys.stderr)
            return [SecurityStatus.EXISTS]

        dst_path.unlink()

    try:
        dst_path.symlink_to(src_path)
    except FileExistsError:
        return [SecurityStatus.EXISTS]
    return [SecurityStatus.OK]


# This executes a command without capturing the output
def execute_command(args: list[FilePath | str],
                    env: Optional[dict] = None, comparison: int = 0) -> bool:
    """
    Executes a command

        Parameters:
            args ([str]): The commandline
            env (dict): Environment variables to set
            comparison (int): The value to compare retval to
        Returns:
            (bool): True if retval.returncode == comparison, False otherwise
    """
    if env is None:
        retval = subprocess.run(args, check=False)
    else:
        retval = subprocess.run(args, env=env, check=False)
    return retval.returncode == comparison


# This executes a command with the output captured
def execute_command_with_response(args: list[str], env: Optional[dict] = None) -> str:
    """
    Executes a command and returns stdout

        Parameters:
            args ([str]): The commandline
            env (dict): Environment variables to set
        Returns:
            (str): The stdout from the execution
    """
    if env is None:
        result = subprocess.run(args, stdout=PIPE, stderr=STDOUT, check=False)
    else:
        result = subprocess.run(args, stdout=PIPE, stderr=STDOUT, env=env, check=False)
    return result.stdout.decode("utf-8", errors="replace")
