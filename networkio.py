#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.8)
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
import os
from pathlib import Path, PurePath
import re
import shutil
import socket
import sys
import tarfile
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import paramiko

import cmtlib
from cmtio_yaml import secure_read_yaml, secure_write_yaml

from cmtpaths import HOMEDIR, SSH_DIR, SOFTWARE_SOURCES_DIR
from cmtpaths import VERSION_CACHE_DIR, VERSION_CACHE_LAST_UPDATED_PATH
from ansithemeprint import ansithemeprint, ANSIThemeString
from cmttypes import deep_get, DictPath, FilePath

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


def scan_and_add_ssh_keys(hosts: List[str]) -> None:
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
        ansithemeprint([ANSIThemeString("Critical", "critical"),
                        ANSIThemeString(": Failed to open/read “", "default"),
                        ANSIThemeString(known_hosts, "path"),
                        ANSIThemeString("“; aborting.", "default")], stderr=True)
        sys.exit(errno.EIO)

    for host in hosts:
        try:
            transport = paramiko.Transport(host)
        except socket.gaierror as e:
            if str(e) in ("[Errno -2] Name or service not known",
                          "[Errno -3] Temporary failure in name resolution",
                          "[Errno -5] No address associated with hostname"):
                continue
            tmp = re.match(r"^\[Errno (-\d+)\] (.+)", str(e))
            if tmp is not None:
                ansithemeprint([ANSIThemeString("Error", "error"),
                                ANSIThemeString(": ", "default"),
                                ANSIThemeString(f"{tmp[2]} (hostname: ", "default"),
                                ANSIThemeString(f"{host}", "hostname"),
                                ANSIThemeString("); aborting.", "default")],
                               stderr=True)
            else:
                ansithemeprint([ANSIThemeString("Error", "error"),
                                ANSIThemeString(": Could not extract errno from ", "default"),
                                ANSIThemeString(f"{e}; aborting.", "default")], stderr=True)
            sys.exit(errno.ENOENT)
        except paramiko.ssh_exception.SSHException as e:
            ansithemeprint([ANSIThemeString("\nError", "error"),
                            ANSIThemeString(f": {e}; aborting.", "default")], stderr=True)
            sys.exit(errno.EIO)

        try:
            transport.connect()
            key = transport.get_remote_server_key()
            transport.close()
        except paramiko.SSHException:
            ansithemeprint([ANSIThemeString("Error", "error"),
                            ANSIThemeString(": Failed to get server key from remote host ",
                                            "default"),
                            ANSIThemeString(host, "hostname"),
                            ANSIThemeString("; aborting.", "default")], stderr=True)
            sys.exit(errno.EIO)

        hostfile.add(hostname=host, key=key, keytype=key.get_name())

    try:
        hostfile.save(filename=known_hosts)
    except IOError:
        ansithemeprint([ANSIThemeString("Critical", "critical"),
                        ANSIThemeString(": Failed to save modifications to “", "default"),
                        ANSIThemeString(known_hosts, "path"),
                        ANSIThemeString("“; aborting.", "default")], stderr=True)
        sys.exit(errno.EIO)


checksum_functions: Dict[str, Callable] = {
    "md5": hashlib.md5,  # nosec
    "sha": hashlib.sha1,  # nosec nosem
    "sha1": hashlib.sha1,  # nosec nosem
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
    "shake_128": hashlib.shake_128,  # type: ignore
    "shake_256": hashlib.shake_256,  # type: ignore
}


def verify_checksum(checksum: bytes,
                    checksum_type: str, data: bytearray, filename: Optional[str] = None) -> bool:
    """
    Checksum data against a checksum file

        Parameters:
            checksum (bytes): The downloaded checksum file
            checksum_type (str): What hash should be used when calculating the checksum?
            data (bytearray): The data to calculate the checksum of
            filename (str): Used to identify the correct checksum entry
                            in a file with multiple checksums (optional)
        Returns:
            (bool): True if the checksum matches,
                    False if the checksum does not match
    """
    if checksum_type is None:
        ansithemeprint([ANSIThemeString("Warning", "warning"),
                        ANSIThemeString(": No checksum type provided; checksum ", "default"),
                        ANSIThemeString("not", "emphasis"),
                        ANSIThemeString(" verified", "default")], stderr=True)
        return True

    if (hashfun := deep_get(checksum_functions, DictPath(f"{checksum_type}"))) is None:
        return False

    if checksum_type == "md5":
        ansithemeprint([ANSIThemeString("Warning", "warning"),
                        ANSIThemeString(": Use of MD5 checksums is ", "default"),
                        ANSIThemeString("strongly", "emphasis"),
                        ANSIThemeString(" discouraged", "default")], stderr=True)
    elif checksum_type in ("sha", "sha1"):
        ansithemeprint([ANSIThemeString("Warning", "warning"),
                        ANSIThemeString(": Use of SHA1 checksums is ", "default"),
                        ANSIThemeString("strongly", "emphasis"),
                        ANSIThemeString(" discouraged", "default")], stderr=True)

    m = hashfun()
    m.update(data)

    # If filename is supplied it is expected that the checksum file can contain
    # more than one checksum, or at least that it contains a filename;
    # if so we find the matching entry
    regex = re.compile(r"^([0-9a-f]+)\s+(\S+)$")
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
        # pylint: disable-next=too-many-function-args
        if m.hexdigest(shake_length) != match_checksum:  # type: ignore
            return False
    else:
        if m.hexdigest() != match_checksum:
            return False

    return True


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
                   fetch_urls: List[Tuple[str, str, Optional[str], Optional[str]]],
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
        ansithemeprint([ANSIThemeString("Critical", "critical"),
                        ANSIThemeString(": The target path ", "default"),
                        ANSIThemeString(f"{directory}", "path"),
                        ANSIThemeString(" does not resolve to itself; "
                                        "this is either a configuration error "
                                        "or a security issue; aborting.", "default")],
                       stderr=True)
        sys.exit(errno.EINVAL)

    if path.owner() != user:
        ansithemeprint([ANSIThemeString("Error", "error"),
                        ANSIThemeString(": The target path ", "default"),
                        ANSIThemeString(f"{directory}", "path"),
                        ANSIThemeString(" is not owned by ", "default"),
                        ANSIThemeString(user, "emphasis"),
                        ANSIThemeString("; aborting.", "default")], stderr=True)
        sys.exit(errno.EINVAL)

    path_stat = path.stat()
    path_permissions = path_stat.st_mode & 0o002

    if path_permissions:
        ansithemeprint([ANSIThemeString("Critical", "critical"),
                        ANSIThemeString(": The target path ", "default"),
                        ANSIThemeString(f"{directory}", "path"),
                        ANSIThemeString(" is world writable", "default"),
                        ANSIThemeString("; aborting.", "default")], stderr=True)
        sys.exit(errno.EINVAL)

    if not path.is_dir():
        ansithemeprint([ANSIThemeString("Error", "error"),
                        ANSIThemeString(": The target path ", "default"),
                        ANSIThemeString(f"{directory}", "path"),
                        ANSIThemeString(" is not a directory", "default"),
                        ANSIThemeString("; aborting.", "default")], stderr=True)
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

        # If there's a checksum file, download it first
        checksum = None

        if checksum_url is not None:
            if checksum_url.startswith("http://"):
                r1 = pm.request("GET", checksum_url)  # type: ignore
            elif checksum_url.startswith("https://"):
                r1 = spm.request("GET", checksum_url)  # type: ignore
            else:
                ansithemeprint([ANSIThemeString("Error", "error"),
                                ANSIThemeString(": Unknown or missing protocol; "
                                                "Checksum URL ", "default"),
                                ANSIThemeString(f"{checksum_url}", "url")], stderr=True)
                retval = False
                break

            if r1.status == 200:
                checksum = r1.data
            else:
                retval = False
                break

        if url.startswith("http://"):
            r1 = pm.request("GET", url)  # type: ignore
        elif url.startswith("https://"):
            r1 = spm.request("GET", url)  # type: ignore
        else:
            ansithemeprint([ANSIThemeString("Error", "error"),
                            ANSIThemeString(": Unknown or missing protocol; URL ", "default"),
                            ANSIThemeString(f"{url}", "url")], stderr=True)
            retval = False
            continue

        if r1.status == 200:
            # Check that we actually got any data
            if not r1.data:
                ansithemeprint([ANSIThemeString("Critical", "error"),
                                ANSIThemeString(": File downloaded from ", "default"),
                                ANSIThemeString(f"{url}", "url"),
                                ANSIThemeString(" is empty; aborting.", "default")], stderr=True)
                retval = False
                break

            # If we have a checksum we need to confirm that the downloaded file matches the checksum
            if checksum is not None and \
                    checksum_type is not None and \
                    not verify_checksum(checksum, checksum_type, r1.data, os.path.basename(url)):
                ansithemeprint([ANSIThemeString("Critical", "error"),
                                ANSIThemeString(": File downloaded from ", "default"),
                                ANSIThemeString(f"{url}", "url"),
                                ANSIThemeString(" did not match its expected checksum; "
                                                "aborting.", "default")], stderr=True)
                retval = False
                break

            # NamedTemporaryFile with delete = False will create a temporary file
            # owned by user with 0o600 permissions.
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(r1.data)
                # We want to use the content before the scope ends, so we need to flush the file
                f.flush()

                # We'd prefer to do this using BytesIO,
                # but tarfile only supports it from Python 3.9+
                if tarfile.is_tarfile(f.name):
                    with tarfile.open(name=f.name, mode="r") as tf:
                        members = tf.getnames()
                        if filename not in members:
                            ansithemeprint([ANSIThemeString("Critical", "critical"),
                                            ANSIThemeString(": ", "default"),
                                            ANSIThemeString(f"{filename}", "path"),
                                            ANSIThemeString(" is not a part of archive; "
                                                            "aborting.", "default")], stderr=True)
                            sys.exit(errno.ENOENT)

                        with tempfile.NamedTemporaryFile(delete=False) as f2:
                            with tf.extractfile(filename) as tff:  # type: ignore
                                f2.write(tff.read())

                            # Here we change to the permissions we are supposed to use
                            os.chmod(f2.name, permissions)
                            # Here we atomically move it in place
                            shutil.move(f2.name, f"{directory}/{filename}")
                            os.remove(f.name)
                else:
                    # Here we change to the permissions we are supposed to use
                    os.chmod(f.name, permissions)
                    # Here we atomically move it in place
                    shutil.move(f.name, f"{directory}/{filename}")
        else:
            ansithemeprint([ANSIThemeString("Error ", "error"),
                            ANSIThemeString(": Failed to fetch URL ", "default"),
                            ANSIThemeString(f"{url}", "url"),
                            ANSIThemeString("; HTTP code: ", "default"),
                            ANSIThemeString(f"{r1.status}", "errorvalue")], stderr=True)
            retval = False
            continue
    pm.clear()  # type: ignore
    spm.clear()  # type: ignore

    return retval


def get_github_version(url: str, version_regex: str) -> Optional[List[str]]:
    """
    Given a github repository find the latest released version

        Parameters:
            url (str): The github API URL to check for latest version
            version_regex (str): A regex
        Returns:
            ([str]): A list of version number elements, or None in case of failure
    """
    version: Optional[List[str]] = []

    if url is not None:
        with tempfile.TemporaryDirectory() as td:
            if not download_files(td, [(url, "release.yaml", None, None)], permissions=0o600):
                return None
            tmp = secure_read_yaml(FilePath(f"{td}/release.yaml"))
            result = deep_get(tmp, DictPath("tag_name"), "")
            versionoutput = result.splitlines()
            _version_regex = re.compile(version_regex)
            for line in versionoutput:
                tmp = _version_regex.match(line)
                if tmp is not None:
                    version = list(tmp.groups())
                    break
    return version


def get_kubernetes_version(**kwargs: Any) -> str:
    """
    Extract the latest upstream Kubernetes version from the release notes

        Parameters:
            path (FilePath): The path to the release notes
        Returns:
            (str): The version string, or an empty string if not available
    """
    tmp_release_notes_path: Optional[FilePath] = deep_get(kwargs, DictPath("path"))
    version = ""
    changelog_version = ""

    if tmp_release_notes_path:
        release_notes_path = \
            FilePath(str(PurePath(VERSION_CACHE_DIR).joinpath(tmp_release_notes_path)))
        d = secure_read_yaml(release_notes_path)
        try:
            # First the backup path
            version = f"{d['schedules'][0]['release']}.0"
        except KeyError:
            pass
        try:
            version = d["schedules"][0]["previousPatches"][0]["release"]
        except KeyError:
            pass
    if version:
        changelog_version = version.rsplit(".", maxsplit=1)[0]
    return version, changelog_version


fetch_function_allowlist = {
    "get_kubernetes_version": get_kubernetes_version,
}


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def update_version_cache(**kwargs: Any) -> None:
    """
    Fetch the latest kubernetes version

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                software_sources_dir (FilePath): Path to the software-sources dir (optional)
                                                 Default: "{HOME}/software-sources"
                verbose (bool): True for verbose output about actions
                force (bool): Force update the cache even if the interval isn't exceeded
    """
    software_sources_dir = deep_get(kwargs,
                                    DictPath("software_sources_dir"), SOFTWARE_SOURCES_DIR)
    verbose = deep_get(kwargs, DictPath("verbose"), False)
    force = deep_get(kwargs, DictPath("force"), False)
    # Substitute {HOME}/ for {HOMEDIR}
    if software_sources_dir.startswith(("{HOME}/", "{HOME}\\")):
        software_sources_dir = \
            FilePath(str(PurePath(HOMEDIR).joinpath(software_sources_dir[len('{HOME}/'):])))

    if not Path(software_sources_dir).is_dir():
        sys.exit(f"{software_sources_dir} does not exist; "
                 "you may need to (re-)run `cmt-install`; aborting.")

    sources = {}
    for path in natsorted(Path(software_sources_dir).iterdir()):
        if not str(path).endswith((".yml", ".yaml")):
            continue
        source = secure_read_yaml(FilePath(str(path)), directory_is_symlink=True)
        for key, data in source.items():
            if verbose and key in sources:
                old_path = deep_get(sources, DictPath(f"{key}#entry_path"), {})
                ansithemeprint([ANSIThemeString("Note", "note"),
                                ANSIThemeString(": overriding entry ", "default"),
                                ANSIThemeString(f"{key}", "emphasis"),
                                ANSIThemeString(" from ", "default"),
                                ANSIThemeString(f"{old_path}", "path"),
                                ANSIThemeString(" with entry from ", "default"),
                                ANSIThemeString(f"{path}", "path")])
                sources.pop(key)
            sources[key] = data
    if Path(VERSION_CACHE_LAST_UPDATED_PATH).is_file():
        last_update_data = secure_read_yaml(VERSION_CACHE_LAST_UPDATED_PATH)
    else:
        last_update_data = {}
    if last_update_data is None:
        last_update_data = {}

    for key, data in sources.items():
        # description = deep_get(data, DictPath("description"), "<none>")
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
        tmp_pre_fetch_function = deep_get(data, DictPath("candidate_version#pre_fetch_function"))
        pre_fetch_function = deep_get(fetch_function_allowlist,
                                      DictPath(tmp_pre_fetch_function))
        pre_fetch_args = deep_get(data, DictPath("candidate_version#pre_fetch_args"))
        tmp_post_fetch_function = deep_get(data, DictPath("candidate_version#post_fetch_function"))
        post_fetch_function = deep_get(fetch_function_allowlist,
                                       DictPath(tmp_post_fetch_function))
        post_fetch_args = deep_get(data, DictPath("candidate_version#post_fetch_args"))

        # tmp_candidate_version_regex = deep_get(data, DictPath("candidate_version#regex"), "")
        # candidate_version_regex = rf"{tmp_candidate_version_regex}"
        candidate_version_urls = deep_get(data, DictPath("candidate_version#urls"), [])

        update_version = False
        update_changelog = False

        # By default we only update the cache once per hour unless forced
        # or the configuration says differently
        if force or not version_age or version_age.days > 0 or version_age.seconds > interval:
            update_version = True
        if force or not changelog_age or changelog_age.days > 0 or changelog_age.seconds > interval:
            update_changelog = True

        if pre_fetch_function and update_version:
            _version, changelog_version = pre_fetch_function(**pre_fetch_args)
        fetch_urls = []
        for candidate_version_url in candidate_version_urls:
            url = deep_get(candidate_version_url, DictPath("url"))
            dest = deep_get(candidate_version_url, DictPath("dest"))
            fetch_urls.append((url, dest, None, None))
        if fetch_urls and update_version:
            if not download_files(VERSION_CACHE_DIR, fetch_urls):
                ansithemeprint([ANSIThemeString("Error", "error"),
                                ANSIThemeString(": Failed to fetch ", "default"),
                                ANSIThemeString(f"{url}", "url"),
                                ANSIThemeString("; skipping.", "default")], stderr=True)
            else:
                if key not in last_update_data:
                    last_update_data[key] = {}
                last_update_data[key]["version"] = datetime.now()
                secure_write_yaml(VERSION_CACHE_LAST_UPDATED_PATH,
                                  last_update_data, permissions=0o644)
        if post_fetch_function:
            _version, changelog_version = post_fetch_function(**post_fetch_args)

        # We (hopefully) have a version now; time to fetch the changelog (if requested)
        if update_changelog:
            changelog_urls = deep_get(data, DictPath("changelog#urls"), [])
            fetch_urls = []
            for changelog_url in changelog_urls:
                url = deep_get(changelog_url, DictPath("url"))
                if "<<<version>>>" in url and changelog_version == "":
                    continue
                url = cmtlib.substitute_string(url, {"<<<version>>>": changelog_version})
                dest = deep_get(changelog_url, DictPath("dest"))
                fetch_urls.append((url, dest, None, None))
            if fetch_urls:
                if not download_files(VERSION_CACHE_DIR, fetch_urls):
                    ansithemeprint([ANSIThemeString("Error", "error"),
                                    ANSIThemeString(": Failed to fetch ", "default"),
                                    ANSIThemeString(f"{url}", "url"),
                                    ANSIThemeString("; skipping.", "default")], stderr=True)
                else:
                    if key not in last_update_data:
                        last_update_data[key] = {}
                    last_update_data[key]["changelog"] = datetime.now()
                    secure_write_yaml(VERSION_CACHE_LAST_UPDATED_PATH,
                                      last_update_data, permissions=0o644)
