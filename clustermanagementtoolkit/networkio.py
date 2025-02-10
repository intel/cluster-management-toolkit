#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Network I/O helpers
"""

from datetime import datetime
import errno
from getpass import getuser
import hashlib
import io
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import tarfile
import tempfile
import time
from typing import Any, cast, Optional
from collections.abc import Callable, Sequence

import paramiko

try:
    from natsort import natsorted
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import natsort; "
             "you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

try:
    import urllib3
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import urllib3; "
             "you may need to (re-)run `cmt-install` or `pip3 install urllib3`; aborting.")

from clustermanagementtoolkit import cmtlib

from clustermanagementtoolkit.cmtio import secure_write_string
from clustermanagementtoolkit.cmtio_yaml import secure_read_yaml, secure_write_yaml

from clustermanagementtoolkit import cmtpaths
from clustermanagementtoolkit.cmtpaths import HOMEDIR, SSH_DIR
from clustermanagementtoolkit.cmtpaths import VERSION_CACHE_DIR, VERSION_CACHE_LAST_UPDATED_PATH
from clustermanagementtoolkit.cmtpaths import VERSION_CANDIDATES_FILE, NETRC_PATH

from clustermanagementtoolkit.ansithemeprint import ansithemeprint, ANSIThemeStr

from clustermanagementtoolkit.cmttypes import deep_get, DictPath, FilePath, FilePathAuditError


def reformat_github_release_notes(changelog: str = "") -> str:
    """
    Given a release message from GitHub reformat it as (extremely) rudimentary Markdown.

        Parameters:
            changelog (str): The changelog to reformat
        Returns:
            (str): The reformatted changelog
    """
    formatted_changelog = []

    previous_line = None
    for line in changelog.splitlines():
        if previous_line is None:
            previous_line = line
            continue
        if line == "---":
            formatted_changelog.append(f"## {previous_line}")
            previous_line = None
            continue
        formatted_changelog.append(previous_line)
        previous_line = line

    if previous_line is not None:
        formatted_changelog.append(previous_line)

    return "\n".join(formatted_changelog)


def scan_and_add_ssh_keys(hosts: list[str]) -> None:
    """
    Scan hosts and add their public ssh keys to .ssh/known_hosts

        Parameters:
            hosts ([str]): A list of hostnames
    """
    known_hosts = FilePath(os.path.join(SSH_DIR, "known_hosts"))

    # Note: Paramiko seems to have issues if .ssh/known_hosts does not exist,
    # so "touch" the file just in case.
    old_umask = os.umask(0o077)
    Path(known_hosts, mode=0o600, exist_ok=True).touch()
    os.umask(old_umask)

    try:
        hostfile = paramiko.HostKeys(filename=known_hosts)
    except IOError:
        ansithemeprint([ANSIThemeStr("Critical", "critical"),
                        ANSIThemeStr(": Failed to open/read “", "default"),
                        ANSIThemeStr(known_hosts, "path"),
                        ANSIThemeStr("“; aborting.", "default")], stderr=True)
        sys.exit(errno.EIO)

    for host in hosts:
        try:
            with paramiko.Transport(host) as transport:
                transport.connect()
                key = transport.get_remote_server_key()
        except socket.gaierror as e:
            if str(e) in ("[Errno -2] Name or service not known",
                          "[Errno -3] Temporary failure in name resolution",
                          "[Errno -5] No address associated with hostname"):
                continue
            tmp = re.match(r"^\[Errno (-\d+)\] (.+)", str(e))
            if tmp is not None:
                ansithemeprint([ANSIThemeStr("Error", "error"),
                                ANSIThemeStr(": ", "default"),
                                ANSIThemeStr(f"{tmp[2]} (hostname: ", "default"),
                                ANSIThemeStr(f"{host}", "hostname"),
                                ANSIThemeStr("); aborting.", "default")],
                               stderr=True)
            else:
                ansithemeprint([ANSIThemeStr("Error", "error"),
                                ANSIThemeStr(": Could not extract errno from ", "default"),
                                ANSIThemeStr(f"{e}; aborting.", "default")], stderr=True)
            sys.exit(errno.ENOENT)
        except paramiko.SSHException as e:
            ansithemeprint([ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(": Failed to get server key from remote host ",
                                         "default"),
                            ANSIThemeStr(host, "hostname"),
                            ANSIThemeStr(f": {e}; aborting.", "default")], stderr=True)
            sys.exit(errno.EIO)

        hostfile.add(hostname=host, key=key, keytype=key.get_name())

    try:
        hostfile.save(filename=known_hosts)
    except IOError:
        ansithemeprint([ANSIThemeStr("Critical", "critical"),
                        ANSIThemeStr(": Failed to save modifications to “", "default"),
                        ANSIThemeStr(known_hosts, "path"),
                        ANSIThemeStr("“; aborting.", "default")], stderr=True)
        sys.exit(errno.EIO)


checksum_functions: dict[str, Callable] = {
    "md5": hashlib.md5,  # nosec
    "sha": hashlib.sha1,  # nosec
    "sha1": hashlib.sha1,  # nosec
    "sha224": hashlib.sha224,
    "sha256": hashlib.sha256,
    "sha384": hashlib.sha384,
    "sha512": hashlib.sha512,
    "blake2b": hashlib.blake2b,
    "blake2s": hashlib.blake2s,
    "sha3_224": hashlib.sha3_224,
    "sha3_256": hashlib.sha3_256,
    "sha3_384": hashlib.sha3_384,
    "sha3_512": hashlib.sha3_512,
    "shake_128": hashlib.shake_128,
    "shake_256": hashlib.shake_256,
}


def verify_checksum(checksum: bytes,
                    checksum_type: str, data: bytes, filename: Optional[str] = None) -> bool:
    """
    Checksum data against a checksum file

        Parameters:
            checksum (bytes): The downloaded checksum file
            checksum_type (str): What hash should be used when calculating the checksum?
            data (bytes): The data to calculate the checksum of
            filename (str): Used to identify the correct checksum entry
                            in a file with multiple checksums (optional)
        Returns:
            (bool): True if the checksum matches,
                    False if the checksum does not match
    """
    if checksum_type is None:
        ansithemeprint([ANSIThemeStr("Warning", "warning"),
                        ANSIThemeStr(": No checksum type provided; checksum ", "default"),
                        ANSIThemeStr("not", "emphasis"),
                        ANSIThemeStr(" verified", "default")], stderr=True)
        return True

    if (hashfun := deep_get(checksum_functions, DictPath(f"{checksum_type}"))) is None:
        return False

    if checksum_type == "md5":
        ansithemeprint([ANSIThemeStr("Warning", "warning"),
                        ANSIThemeStr(": Use of MD5 checksums is ", "default"),
                        ANSIThemeStr("strongly", "emphasis"),
                        ANSIThemeStr(" discouraged", "default")], stderr=True)
    elif checksum_type in ("sha", "sha1"):
        ansithemeprint([ANSIThemeStr("Warning", "warning"),
                        ANSIThemeStr(": Use of SHA1 checksums is ", "default"),
                        ANSIThemeStr("strongly", "emphasis"),
                        ANSIThemeStr(" discouraged", "default")], stderr=True)

    m = hashfun()
    m.update(data)

    # If filename is supplied it is expected that the checksum file can contain
    # more than one checksum, or at least that it contains a filename;
    # if so we find the matching entry
    regex: re.Pattern[str] = re.compile(r"^([0-9a-f]+)\s+(\S+)$")
    match_checksum = None

    for line in checksum.decode("utf-8", errors="replace").splitlines():
        if filename is None and " " not in line:
            match_checksum = line
            break

        tmp = regex.match(line)
        if tmp is not None:
            if filename is not None and tmp[2] != filename:
                continue
            match_checksum = tmp[1]
            break

    if match_checksum is None:
        return False

    if checksum_type in ("shake_128", "shake_256"):
        shake_length = len(match_checksum) // 2
        if m.hexdigest(shake_length) != match_checksum:
            return False
    else:
        if m.hexdigest() != match_checksum:
            return False

    return True


def get_netrc_token(url: Optional[str]) -> Optional[str]:
    """
    Given a URL, check whether there's a matching bearer token in .netrc,
    and if so, return it.

        Parameters:
            url (str): The URL to find a bearer token for
        Returns:
            (str): A bearer token, o None if no token could be found
    """
    token: Optional[str] = None

    if url is None or not url.startswith(("http://", "https://")):
        return token

    base_url: str = url.removeprefix("http://").removeprefix("https://").split("/", maxsplit=1)[0]

    netrc_lines: list[str] = []

    try:
        with open(NETRC_PATH, "r", encoding="utf-8") as f:
            netrc_lines = f.readlines()
    except FileNotFoundError:
        return token

    is_machine: bool = False

    for line in netrc_lines:
        tmp: Optional[re.Match] = re.match(r"^(machine|password)\s(.+)$", line.strip())
        if tmp is not None:
            if tmp[1] == "machine" and tmp[2] == base_url:
                is_machine = True
                continue
            if tmp[1] == "password" and is_machine:
                token = tmp[2]
                break
    return token


# download_files can extract single files from archives;
# it will not extract entire archives due to the security risks,
# and it requires the full path of the file within the archive to be specified.
# If later necessary this function could be modified
# to take a list of multiple files to extract from one tarball;
# for now this does what is necessary though.
#
# fetch_urls is a list of tuples:
# (URL to file or archive, file to extract, URL to checksum, type of checksum)

# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def download_files(directory: str,
                   fetch_urls: Sequence[tuple[str, str, Optional[str], Optional[str]]],
                   permissions: int = 0o644) -> bool:
    """
    Download files; if the file is a tar file it can extract a file.
    If checksum information is provided it can also fetch a checksum and compare against.

        Parameters:
            directory (str): The path to extract the file to
            fetch_urls ([(str, str, str, str)]):
                (str): The URL to download
                (str): The name of the downloaded file
                (str): The URL to the checksum
                (str): The type of checksum
            permissions (int): File permissions (*PLEASE* use octal!)
        Returns:
            (bool): True on success, False on failure
    """
    user = getuser()

    # First check that the destination directory is safe; it has to be owned by the user,
    # and other must not have write permissions; also path must resolve to itself to avoid
    # symlink attacks, and it must be a directory
    path = Path(directory)
    resolved_path = path.resolve()
    if path != resolved_path:
        ansithemeprint([ANSIThemeStr("Critical", "critical"),
                        ANSIThemeStr(": The target path ", "default"),
                        ANSIThemeStr(f"{directory}", "path"),
                        ANSIThemeStr(" does not resolve to itself; "
                                     "this is either a configuration error "
                                     "or a security issue; aborting.", "default")],
                       stderr=True)
        sys.exit(errno.EINVAL)

    if path.owner() != user:
        ansithemeprint([ANSIThemeStr("Error", "error"),
                        ANSIThemeStr(": The target path ", "default"),
                        ANSIThemeStr(f"{directory}", "path"),
                        ANSIThemeStr(" is not owned by ", "default"),
                        ANSIThemeStr(user, "emphasis"),
                        ANSIThemeStr("; aborting.", "default")], stderr=True)
        sys.exit(errno.EINVAL)

    path_stat = path.stat()
    path_permissions = path_stat.st_mode & 0o002

    if path_permissions:
        ansithemeprint([ANSIThemeStr("Critical", "critical"),
                        ANSIThemeStr(": The target path ", "default"),
                        ANSIThemeStr(f"{directory}", "path"),
                        ANSIThemeStr(" is world writable", "default"),
                        ANSIThemeStr("; aborting.", "default")], stderr=True)
        sys.exit(errno.EINVAL)

    if not path.is_dir():
        ansithemeprint([ANSIThemeStr("Error", "error"),
                        ANSIThemeStr(": The target path ", "default"),
                        ANSIThemeStr(f"{directory}", "path"),
                        ANSIThemeStr(" is not a directory", "default"),
                        ANSIThemeStr("; aborting.", "default")], stderr=True)
        sys.exit(errno.EINVAL)

    # OK, the destination is not a symlink and does not contain ".." or similar,
    # it is owned by the user, and is an existing directory; we can safely continue

    http_proxy = deep_get(cmtlib.cmtconfig, DictPath("Network#http_proxy"), "")
    https_proxy = deep_get(cmtlib.cmtconfig, DictPath("Network#https_proxy"), "")
    retval = True

    if http_proxy is not None and http_proxy != "":
        pm = urllib3.ProxyManager(http_proxy)
    else:
        pm = urllib3.PoolManager()  # type: ignore
    if https_proxy is not None and https_proxy != "":
        spm = urllib3.ProxyManager(https_proxy)
    else:
        spm = urllib3.PoolManager()  # type: ignore

    for url, filename, checksum_url, checksum_type in fetch_urls:
        # In case we're downloading heaps of files it's good manners to rate-limit our requests
        time.sleep(1)

        header_params: dict[str, str] = {}

        # If the URL has a token in .netrc, use it for the download; this can help alleviate
        # rate-limiting for api.github.com, possibly also other sites.
        if token := get_netrc_token(checksum_url):
            header_params["Authorization"] = f"Bearer {token}"

        # If there's a checksum file, download it first
        checksum = None

        if checksum_url is not None:
            if checksum_url.startswith("http://"):
                r1 = pm.request("GET", checksum_url, headers=header_params)
            elif checksum_url.startswith("https://"):
                r1 = spm.request("GET", checksum_url, headers=header_params)
            else:
                ansithemeprint([ANSIThemeStr("Error", "error"),
                                ANSIThemeStr(": Unknown or missing protocol; "
                                             "Checksum URL ", "default"),
                                ANSIThemeStr(f"{checksum_url}", "url")], stderr=True)
                retval = False
                break

            if r1.status == 200:
                checksum = r1.data
            else:
                retval = False
                break

        header_params = {}

        # If the URL has a token in .netrc, use it for the download; this can help alleviate
        # rate-limiting for api.github.com, possibly also other sites.
        if token := get_netrc_token(url):
            header_params["Authorization"] = f"Bearer {token}"

        try:
            if url.startswith("http://"):
                r1 = pm.request("GET", url, headers=header_params)
            elif url.startswith("https://"):
                r1 = spm.request("GET", url, headers=header_params)
            else:
                ansithemeprint([ANSIThemeStr("Error", "error"),
                                ANSIThemeStr(": Unknown or missing protocol; URL ", "default"),
                                ANSIThemeStr(f"{url}", "url")], stderr=True)
                retval = False
                continue
        except urllib3.exceptions.MaxRetryError as e:
            if "No route to host" in str(e):
                ansithemeprint([ANSIThemeStr("Error", "error"),
                                ANSIThemeStr(": No route to host; URL ", "default"),
                                ANSIThemeStr(f"{url}", "url")], stderr=True)
                retval = False
                continue
            raise

        if r1.status == 200:
            # Check that we actually got any data
            if not r1.data:
                ansithemeprint([ANSIThemeStr("Critical", "error"),
                                ANSIThemeStr(": File downloaded from ", "default"),
                                ANSIThemeStr(f"{url}", "url"),
                                ANSIThemeStr(" is empty; aborting.", "default")], stderr=True)
                retval = False
                break

            # If we have a checksum we need to confirm that the downloaded file matches the checksum
            if checksum is not None and \
                    checksum_type is not None and \
                    not verify_checksum(checksum, checksum_type, r1.data, os.path.basename(url)):
                ansithemeprint([ANSIThemeStr("Critical", "error"),
                                ANSIThemeStr(": File downloaded from ", "default"),
                                ANSIThemeStr(f"{url}", "url"),
                                ANSIThemeStr(" did not match its expected checksum; "
                                             "aborting.", "default")], stderr=True)
                retval = False
                break

            fname: str = ""
            # NamedTemporaryFile with delete = False will create a temporary file
            # owned by user with 0o600 permissions.
            with tempfile.NamedTemporaryFile(delete=False) as f:
                biodata = io.BytesIO(r1.data)

                if tarfile.is_tarfile(biodata):
                    with tarfile.open(fileobj=biodata) as tf:
                        members = tf.getnames()
                        if filename not in members:
                            ansithemeprint([ANSIThemeStr("Critical", "critical"),
                                            ANSIThemeStr(": ", "default"),
                                            ANSIThemeStr(f"{filename}", "path"),
                                            ANSIThemeStr(" is not a part of archive; "
                                                         "aborting.", "default")], stderr=True)
                            sys.exit(errno.ENOENT)

                        with tf.extractfile(filename) as tff:  # type: ignore
                            f.write(tff.read())
                else:
                    f.write(r1.data)
                fname = f.name
            # Here we change to the permissions we are supposed to use
            os.chmod(fname, permissions)
            # Here we atomically move it in place
            shutil.move(fname, f"{directory}/{filename}")
        else:
            reason = []
            if r1.reason is not None:
                reason = [ANSIThemeStr(" (reason: ", "default"),
                          ANSIThemeStr(f"{r1.reason}", "emphasis"),
                          ANSIThemeStr(")", "default")]
            ansithemeprint([ANSIThemeStr("Error ", "error"),
                            ANSIThemeStr(": Failed to fetch URL ", "default"),
                            ANSIThemeStr(f"{url}", "url"),
                            ANSIThemeStr("; HTTP code: ", "default"),
                            ANSIThemeStr(f"{r1.status}", "errorvalue")] + reason, stderr=True)
            retval = False
            continue
    pm.clear()
    spm.clear()

    return retval


def get_github_version(url: str, version_regex: str) -> Optional[tuple[list[str], str, str]]:
    """
    Given a github repository find the latest release;
    exclude releases that do not match the regex and prereleases.

        Parameters:
            url (str): The github API URL to check for latest version
            version_regex (str): A regex
        Returns:
            ([str], str):
                ([str]): A list of version number elements, or None in case of failure
                (str): The release data
                (str): The release page body
    """
    versions: list[tuple[list[str], str, str]] = []

    if url is not None and url and version_regex is not None and version_regex:
        compiled_version_regex = re.compile(version_regex)
        with tempfile.TemporaryDirectory() as td:
            if not download_files(td, [(url, "releases.yaml", None, None)], permissions=0o600):
                return None
            tmp = list(secure_read_yaml(FilePath(f"{td}/releases.yaml")))
            for release in tmp:
                prerelease = deep_get(release, DictPath("prerelease"), False)
                draft = deep_get(release, DictPath("draft"), False)
                if prerelease or draft:
                    continue
                name = deep_get(release, DictPath("tag_name"), "")
                if (tmp := compiled_version_regex.match(name)) is None:
                    continue
                created_at = deep_get(release, DictPath("created_at"), "<unknown>")
                published_at = deep_get(release, DictPath("published_at"), created_at)
                body = deep_get(release, DictPath("body"), "")
                versions.append((list(tmp.groups()), published_at, body))
    if versions:
        return cast(tuple[list[str], str, str], natsorted(versions, reverse=True)[0])

    return [], "", ""


candidate_version_function_allowlist: dict[str, Callable] = {
    "get_github_version": get_github_version,
}

reformatter_allowlist: dict[str, Callable] = {
    "reformat_github_release_notes": reformat_github_release_notes,
}


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def update_version_cache(**kwargs: Any) -> None:
    """
    Update the list of component versions, and, where applicable, fetch their changelogs

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                software_sources_dir (FilePath): Path to the software-sources dir (optional)
                                                 Default: "{HOME}/.cmt/sources"
                verbose (bool): True for verbose output about actions
                force (bool): Force update the cache even if the interval isn't exceeded
    """
    software_sources_dir = \
        deep_get(kwargs, DictPath("software_sources_dir"), cmtpaths.SOFTWARE_SOURCES_DIR)
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)
    force: bool = deep_get(kwargs, DictPath("force"), False)
    # Substitute {HOME}/ for {HOMEDIR}
    if software_sources_dir.startswith(("{HOME}/", "{HOME}\\")):
        software_sources_dir = HOMEDIR.joinpath(software_sources_dir[len('{HOME}/'):])

    sources: dict = {}
    try:
        for path in natsorted(Path(cmtpaths.SYSTEM_SOFTWARE_SOURCES_DIR).iterdir()):
            path = str(path)
            if not path.endswith((".yml", ".yaml")):
                continue
            source = dict(secure_read_yaml(FilePath(path), directory_is_symlink=True))
            for key, data in source.items():
                if verbose and key in sources:
                    old_path = deep_get(sources, DictPath(f"{key}#entry_path"), {})
                    ansithemeprint([ANSIThemeStr("Note", "note"),
                                    ANSIThemeStr(": overriding entry ", "default"),
                                    ANSIThemeStr(f"{key}", "emphasis"),
                                    ANSIThemeStr(" from ", "default"),
                                    ANSIThemeStr(f"{old_path}", "path"),
                                    ANSIThemeStr(" with entry from ", "default"),
                                    ANSIThemeStr(f"{path}", "path")])
                    sources.pop(key)
                sources[key] = data
    except FileNotFoundError:
        pass

    try:
        for path in natsorted(Path(software_sources_dir).iterdir()):
            path = str(path)
            if not path.endswith((".yml", ".yaml")):
                continue
            source = dict(secure_read_yaml(FilePath(path), directory_is_symlink=True))
            for key, data in source.items():
                if verbose and key in sources:
                    old_path = deep_get(sources, DictPath(f"{key}#entry_path"), {})
                    ansithemeprint([ANSIThemeStr("Note", "note"),
                                    ANSIThemeStr(": overriding entry ", "default"),
                                    ANSIThemeStr(f"{key}", "emphasis"),
                                    ANSIThemeStr(" from ", "default"),
                                    ANSIThemeStr(f"{old_path}", "path"),
                                    ANSIThemeStr(" with entry from ", "default"),
                                    ANSIThemeStr(f"{path}", "path")])
                    sources.pop(key)
                sources[key] = data
    except FileNotFoundError:
        pass

    if Path(VERSION_CACHE_LAST_UPDATED_PATH).is_file():
        last_update_data = dict(secure_read_yaml(VERSION_CACHE_LAST_UPDATED_PATH))
    else:
        last_update_data = {}
    if last_update_data is None:
        last_update_data = {}

    try:
        candidate_versions = dict(secure_read_yaml(VERSION_CANDIDATES_FILE))
    except FilePathAuditError as e:
        if "DOES_NOT_EXIST" in str(e):
            candidate_versions = {}
        else:
            raise

    changed = False

    for key, data in sources.items():
        interval = deep_get(data, DictPath("interval"), 60 * 60)
        version_last_updated = deep_get(last_update_data, DictPath(f"{key}#version"))
        if version_last_updated:
            version_age = datetime.now() - version_last_updated
        else:
            version_age = None
        changelog_last_updated = deep_get(last_update_data, DictPath(f"{key}#changelog"))
        if changelog_last_updated:
            changelog_age = datetime.now() - changelog_last_updated
        else:
            changelog_age = None
        tmp: str = deep_get(data, DictPath("candidate_version#function"), "")
        candidate_version_func: Optional[Callable] = \
            deep_get(candidate_version_function_allowlist, DictPath(tmp))
        candidate_version_args: dict = deep_get(data, DictPath("candidate_version#args"), {})

        candidate_version_tuple: Optional[tuple] = None
        release_body = ""

        # By default we only update the cache once per hour unless forced
        # or the configuration says differently
        if force or not version_age or version_age.days > 0 or version_age.seconds > interval:
            if candidate_version_func:
                release_info = candidate_version_func(**candidate_version_args)
                if release_info is not None:
                    candidate_version_tuple, release_date, release_body = release_info
                    if key not in candidate_versions:
                        candidate_versions[key] = {"release": "", "release_date": ""}
                    candidate_versions[key]["release"] = \
                        "".join(cast(tuple, candidate_version_tuple))
                    candidate_versions[key]["release_date"] = "".join(release_date)
                    if key not in last_update_data:
                        last_update_data[key] = {}
                    last_update_data[key]["version"] = datetime.now()
                    secure_write_yaml(VERSION_CACHE_LAST_UPDATED_PATH,
                                      last_update_data, permissions=0o644)
            changed = True

        if candidate_version_tuple is None:
            # If we've already fetched the data recently we need to use the existing data.
            tmp = deep_get(candidate_versions, DictPath(f"{key}#release"), "")
            if not tmp:
                continue
            # Split it using the same regex that we'd normally use to split the string.
            candidate_version_regex = \
                deep_get(candidate_version_args, DictPath("version_regex"), "")
            tmp2 = re.match(candidate_version_regex, tmp)
            if tmp2 is not None:
                candidate_version_tuple = tmp2.groups()

        if not (force or not changelog_age
                or changelog_age.days > 0 or changelog_age.seconds > interval):
            continue

        # We (hopefully) have a version now; time to fetch the changelog (if requested)
        changelog_url: str = deep_get(data, DictPath("changelog#url"), "")
        changelog_dest: str = deep_get(data, DictPath("changelog#dest"), "")
        changelog_from_body: str = deep_get(data, DictPath("changelog#from_body"), False)
        reformatter: str = deep_get(data, DictPath("changelog#reformatter"))

        if not (changelog_url or changelog_from_body and release_body) or not changelog_dest:
            continue

        if changelog_from_body:
            # First step: replace \r\n with \n.
            release_body = release_body.replace("\r\n", "\n")
            # Add extra newlines at the end; one to help the reformatter,
            # one because the field typically lacks a trailing newline.
            release_body += "\n\n\n"

            if (reformatter := deep_get(reformatter_allowlist, DictPath(reformatter))) is not None:
                release_body = reformatter(release_body)
            secure_write_string(VERSION_CACHE_DIR.joinpath(changelog_dest), release_body,
                                allow_relative_path=True, permissions=0o644)
        else:
            version_substitutions: dict = {}
            if candidate_version_tuple:
                for i, item in enumerate(candidate_version_tuple):
                    version_substitutions[f"<<<version.{i}>>>"] = item
            changelog_url = cmtlib.substitute_string(changelog_url, version_substitutions)
            if "<<<version" in changelog_url:
                # If still have remaining substitutions to be made after using the versions we have
                # there is no recourse but to skip fetching the changelog.
                continue
            fetch_url = [(changelog_url, changelog_dest, None, None)]
            if not download_files(VERSION_CACHE_DIR, fetch_url):
                ansithemeprint([ANSIThemeStr("Error", "error"),
                                ANSIThemeStr(": Failed to fetch ", "default"),
                                ANSIThemeStr(f"{changelog_url}", "url"),
                                ANSIThemeStr("; skipping.", "default")], stderr=True)
                continue
        if key not in last_update_data:
            last_update_data[key] = {}
        last_update_data[key]["changelog"] = datetime.now()
        secure_write_yaml(VERSION_CACHE_LAST_UPDATED_PATH,
                          last_update_data, permissions=0o644)

    if changed:
        secure_write_yaml(VERSION_CANDIDATES_FILE, candidate_versions, permissions=0o644)
