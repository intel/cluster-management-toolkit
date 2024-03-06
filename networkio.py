#! /usr/bin/env python3
# Requires: python3 (>= 3.8)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Network I/O helpers
"""

import errno
from getpass import getuser
import hashlib
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import tarfile
import tempfile
import time
from typing import List, Optional, Tuple

import paramiko

import cmtlib
from cmtio_yaml import secure_read_yaml

from cmtpaths import SSH_DIR
import ansithemeprint
from ansithemeprint import ANSIThemeString
from cmttypes import deep_get, DictPath, FilePath

try:
	import urllib3
except ModuleNotFoundError:  # pragma: no cover
	sys.exit("ModuleNotFoundError: Could not import urllib3; you may need to (re-)run `cmt-install` or `pip3 install urllib3`; aborting.")

def scan_and_add_ssh_keys(hosts: List[str]) -> None:
	"""
	Scan hosts and add their public ssh keys to .ssh/known_hosts

		Parameters:
			hosts (list[str]): A list of hostnames
	"""

	known_hosts = FilePath(os.path.join(SSH_DIR, "known_hosts"))

	# Note: Paramiko seems to have issues if .ssh/known_hosts does not exist,
	# so "touch" the file just in case.
	old_umask = os.umask(0o077)
	Path(known_hosts, mode = 0o600, exist_ok = True).touch()
	os.umask(old_umask)

	try:
		hostfile = paramiko.HostKeys(filename = known_hosts)
	except IOError:
		ansithemeprint.ansithemeprint([ANSIThemeString("Critical", "critical"),
					       ANSIThemeString(": Failed to open/read “", "default"),
					       ANSIThemeString(known_hosts, "path"),
					       ANSIThemeString("“; aborting.", "default")], stderr = True)
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
				ansithemeprint.ansithemeprint([ANSIThemeString("Error", "error"),
							       ANSIThemeString(": ", "default"),
							       ANSIThemeString(f"{tmp[2]} (hostname: ", "default"),
							       ANSIThemeString(f"{host}", "hostname"),
							       ANSIThemeString("); aborting.", "default")], stderr = True)
			else:
				ansithemeprint.ansithemeprint([ANSIThemeString("Error", "error"),
							       ANSIThemeString(": Could not extract errno from ", "default"),
							       ANSIThemeString(f"{e}; aborting.", "default")], stderr = True)
			sys.exit(errno.ENOENT)
		except paramiko.ssh_exception.SSHException as e:
			ansithemeprint.ansithemeprint([ANSIThemeString("\nError", "error"),
						       ANSIThemeString(f": {e}; aborting.", "default")], stderr = True)
			sys.exit(errno.EIO)

		try:
			transport.connect()
			key = transport.get_remote_server_key()
			transport.close()
		except paramiko.SSHException:
			ansithemeprint.ansithemeprint([ANSIThemeString("Error", "error"),
						       ANSIThemeString(": Failed to get server key from remote host ", "default"),
						       ANSIThemeString(host, "hostname"),
						       ANSIThemeString("; aborting.", "default")], stderr = True)
			sys.exit(errno.EIO)

		hostfile.add(hostname = host, key = key, keytype = key.get_name())

	try:
		hostfile.save(filename = known_hosts)
	except IOError:
		ansithemeprint.ansithemeprint([ANSIThemeString("Critical", "critical"),
					       ANSIThemeString(": Failed to save modifications to “", "default"),
					       ANSIThemeString(known_hosts, "path"),
					       ANSIThemeString("“; aborting.", "default")], stderr = True)
		sys.exit(errno.EIO)

def verify_checksum(checksum: bytes, checksum_type: str, data: bytearray, filename: Optional[str] = None) -> bool:
	"""
	Checksum data against a checksum file

		Parameters:
			checksum (bytes): The downloaded checksum file
			checksum_type (str): What hash should be used when calculating the checksum?
			data (bytearray): The data to calculate the checksum of
			filename (str): Used to identify the correct checksum entry in a file with multiple checksums (optional)
		Returns:
			retval (bool): True if the checksum matches, False if the checksum does not match
	"""

	if checksum_type is None:
		ansithemeprint.ansithemeprint([ANSIThemeString("Warning", "warning"),
					       ANSIThemeString(": No checksum type provided; checksum ", "default"),
					       ANSIThemeString("not", "emphasis"),
					       ANSIThemeString(" verified", "default")], stderr = True)
		return True

	if checksum_type == "md5":
		m = hashlib.md5()  # nosec
		ansithemeprint.ansithemeprint([ANSIThemeString("Warning", "warning"),
					       ANSIThemeString(": Use of MD5 checksums is ", "default"),
					       ANSIThemeString("strongly", "emphasis"),
					       ANSIThemeString(" discouraged", "default")], stderr = True)
	elif checksum_type in ("sha", "sha1"):
		m = hashlib.sha1()  # nosec nosem
		ansithemeprint.ansithemeprint([ANSIThemeString("Warning", "warning"),
					       ANSIThemeString(": Use of SHA1 checksums is ", "default"),
					       ANSIThemeString("strongly", "emphasis"),
					       ANSIThemeString(" discouraged", "default")], stderr = True)
	elif checksum_type == "sha224":
		m = hashlib.sha224()
	elif checksum_type == "sha256":
		m = hashlib.sha256()
	elif checksum_type == "sha384":
		m = hashlib.sha384()
	elif checksum_type == "sha512":
		m = hashlib.sha512()
	elif checksum_type == "blake2b":
		m = hashlib.blake2b()
	elif checksum_type == "blake2s":
		m = hashlib.blake2s()
	elif checksum_type == "sha3_224":
		m = hashlib.sha3_224()
	elif checksum_type == "sha3_256":
		m = hashlib.sha3_256()
	elif checksum_type == "sha3_384":
		m = hashlib.sha3_384()
	elif checksum_type == "sha3_512":
		m = hashlib.sha3_512()
	elif checksum_type == "shake_128":
		m = hashlib.shake_128()  # type: ignore
	elif checksum_type == "shake_256":
		m = hashlib.shake_256()  # type: ignore
	else:  # pragma: no cover
		return False

	m.update(data)

	# If filename is supplied it is expected that the checksum file can contain
	# more than one checksum, or at least that it contains a filename;
	# if so we find the matching entry
	regex = re.compile(r"^([0-9a-f]+)\s+(\S+)$")
	match_checksum = None

	for line in checksum.decode("utf-8", errors = "replace").splitlines():
		if filename is None and not " " in line:
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

# download_files can extract single files from archives; it will not extract entire archives due to the security risks,
# and it requires the full path of the file within the archive to be specified.
# If later necessary this function could be modified to take a list of multiple files to extract from one tarball;
# for now this does what is necessary though.
#
# fetch_urls is a list of tuples:
# (URL to file or archive, file to extract, URL to checksum, type of checksum)
def download_files(directory: str, fetch_urls: List[Tuple[str, str, Optional[str], Optional[str]]], permissions: int = 0o644) -> bool:
	"""
	Download files; if the file is a tar file it can extract a file.
	If checksum information is provided it can also fetch a checksum and compare against.

		Parameters:
			directory (str): The path to extract the file to
			fetch_urls (list[(url, filename, checksum_url, checksum_type)]):
				url (str): The URL to download
				filename (str): The name of the downloaded file
				checksum_url (str): The URL to the checksum
				checksum_type (str): The type of checksum
			permissions (int): File permissions (*PLEASE* use octal!)
		Returns:
			True on success, False on failure
	"""

	user = getuser()

	# First check that the destination directory is safe; it has to be owned by the user,
	# and other must not have write permissions; also path must resolve to itself to avoid
	# symlink attacks, and it must be a directory
	path = Path(directory)
	resolved_path = path.resolve()
	if path != resolved_path:
		ansithemeprint.ansithemeprint([ANSIThemeString("Critical", "critical"),
					       ANSIThemeString(": The target path ", "default"),
					       ANSIThemeString(f"{directory}", "path"),
					       ANSIThemeString(" does not resolve to itself; this is either a configuration error or a security issue; aborting.", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	if path.owner() != user:
		ansithemeprint.ansithemeprint([ANSIThemeString("Error", "error"),
					       ANSIThemeString(": The target path ", "default"),
					       ANSIThemeString(f"{directory}", "path"),
					       ANSIThemeString(" is not owned by ", "default"),
					       ANSIThemeString(user, "emphasis"),
					       ANSIThemeString("; aborting.", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	path_stat = path.stat()
	path_permissions = path_stat.st_mode & 0o002

	if path_permissions:
		ansithemeprint.ansithemeprint([ANSIThemeString("Critical", "critical"),
					       ANSIThemeString(": The target path ", "default"),
					       ANSIThemeString(f"{directory}", "path"),
					       ANSIThemeString(" is world writable", "default"),
					       ANSIThemeString("; aborting.", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	if not path.is_dir():
		ansithemeprint.ansithemeprint([ANSIThemeString("Error", "error"),
					       ANSIThemeString(": The target path ", "default"),
					       ANSIThemeString(f"{directory}", "path"),
					       ANSIThemeString(" is not a directory", "default"),
					       ANSIThemeString("; aborting.", "default")], stderr = True)
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
				ansithemeprint.ansithemeprint([ANSIThemeString("Error", "error"),
							       ANSIThemeString(": Unknown or missing protocol; Checksum URL ", "default"),
							       ANSIThemeString(f"{checksum_url}", "url")], stderr = True)
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
			ansithemeprint.ansithemeprint([ANSIThemeString("Error", "error"),
						       ANSIThemeString(": Unknown or missing protocol; URL ", "default"),
						       ANSIThemeString(f"{url}", "url")], stderr = True)
			retval = False
			continue

		if r1.status == 200:
			# Check that we actually got any data
			if not r1.data:
				ansithemeprint.ansithemeprint([ANSIThemeString("Critical", "error"),
							       ANSIThemeString(": File downloaded from ", "default"),
							       ANSIThemeString(f"{url}", "url"),
							       ANSIThemeString(" is empty; aborting.", "default")], stderr = True)
				retval = False
				break

			# If we have a checksum we need to confirm that the downloaded file matches the checksum
			if checksum is not None and checksum_type is not None and not verify_checksum(checksum, checksum_type, r1.data, os.path.basename(url)):
				ansithemeprint.ansithemeprint([ANSIThemeString("Critical", "error"),
							       ANSIThemeString(": File downloaded from ", "default"),
							       ANSIThemeString(f"{url}", "url"),
							       ANSIThemeString(" did not match its expected checksum; aborting.", "default")], stderr = True)
				retval = False
				break

			# NamedTemporaryFile with delete = False will create a temporary file owned by user with 0o600 permissions
			with tempfile.NamedTemporaryFile(delete = False) as f:
				f.write(r1.data)
				# We want to use the content before the scope ends, so we need to flush the file
				f.flush()

				# We'd prefer to do this using BytesIO, but tarfile only supports it from Python 3.9+
				if tarfile.is_tarfile(f.name):
					with tarfile.open(name = f.name, mode = "r") as tf:
						members = tf.getnames()
						if filename not in members:
							ansithemeprint.ansithemeprint([ANSIThemeString("Critical", "critical"),
										       ANSIThemeString(": ", "default"),
										       ANSIThemeString(f"{filename}", "path"),
										       ANSIThemeString(" is not a part of archive; aborting.", "default")], stderr = True)
							sys.exit(errno.ENOENT)

						with tempfile.NamedTemporaryFile(delete = False) as f2:
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
			ansithemeprint.ansithemeprint([ANSIThemeString("Error ", "error"),
						       ANSIThemeString(": Failed to fetch URL ", "default"),
						       ANSIThemeString(f"{url}", "url"),
						       ANSIThemeString("; HTTP code: ", "default"),
						       ANSIThemeString(f"{r1.status}", "errorvalue")], stderr = True)
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
			version ([str]): A list of version number elements, or None in case of failure
	"""

	version: Optional[List[str]] = []

	if url is not None:
		with tempfile.TemporaryDirectory() as td:
			if not (retval := download_files(td, [(url, "release.yaml", None, None)], permissions = 0o600)):
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
