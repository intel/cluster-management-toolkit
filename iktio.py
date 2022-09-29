#! /usr/bin/env python3
# Requires: python3 (>= 3.6)
from functools import partial
import hashlib
import os
import re
import sys
import tarfile
import tempfile

try:
	import urllib3
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: You probably need to install python3-urllib3; did you forget to run ikt-install?")

import iktlib
from iktlib import deep_get

from iktprint import iktprint

def verify_checksum(checksum, checksum_type, data, filename = None):
	if checksum_type is None:
		return True

	if checksum_type in ["md5"]:
		m = hashlib.md5()
	elif checksum_type in ["sha", "sha1"]:
		m = hashlib.sha1()
	elif checksum_type in ["sha224"]:
		m = hashlib.sha224()
	elif checksum_type in ["sha256"]:
		m = hashlib.sha256()
	elif checksum_type in ["sha384"]:
		m = hashlib.sha384()
	elif checksum_type in ["sha512"]:
		m = hashlib.sha512()
	elif checksum_type in ["blake2b"]:
		m = hashlib.blake2b()
	elif checksum_type in ["blake2s"]:
		m = hashlib.blake2s()
	elif checksum_type in ["sha3"]:
		m = hashlib.sha3()
	elif checksum_type in ["sha3_224"]:
		m = hashlib.sha3_224()
	elif checksum_type in ["sha3_256"]:
		m = hashlib.sha3_256()
	elif checksum_type in ["sha3_384"]:
		m = hashlib.sha3_384()
	elif checksum_type in ["sha3_512"]:
		m = hashlib.sha3_512()
	elif checksum_type in ["shake_128"]:
		m = hashlib.shake_128()
	elif checksum_type in ["shake_256"]:
		m = hashlib.shake_256()
	else:
		return False

	m.update(data)

	# If filename is supplied it's expected that the checksum file can contain
	# more than one checksum, or at least that it contains a filename;
	# if so we find the matching entry
	regex = re.compile(r"^([0-9a-f]+)\s+(\S+)$")
	match_checksum = None

	for line in checksum.decode("utf-8").splitlines():
		if filename is not None:
			tmp = regex.match(line)
			if tmp is not None:
				if tmp[2] != filename:
					continue
				match_checksum = tmp[1]
				break
		else:
			match_checksum = line
			break

	if match_checksum is None:
		return False
	elif m.hexdigest() != match_checksum:
		return False

	return True

# download_files can extract single files from archives; it will not extract entire archives due to the security risks,
# and it requires the full path of the file within the archive to be specified.
# If later necessary this function could be modified to take a list of multiple files to extract from one tarball;
# for now this does what is necessary though.
#
# fetch_urls is a list of tuples:
# (URL to file or archive, file to extract, URL to checksum, type of checksum)
def download_files(directory, fetch_urls, permissions = 0o644):
	iktconfig = iktlib.read_iktconfig()

	http_proxy = deep_get(iktconfig, "Network#http_proxy", "")
	https_proxy = deep_get(iktconfig, "Network#https_proxy", "")
	retval = True

	if http_proxy is not None and http_proxy != "":
		pm = urllib3.ProxyManager(http_proxy)
	else:
		pm = urllib3.PoolManager()
	if https_proxy is not None and https_proxy != "":
		spm = urllib3.ProxyManager(https_proxy)
	else:
		spm = urllib3.PoolManager()

	for url, filename, checksum_url, checksum_type in fetch_urls:
		# If there's a checksum file, download it first
		checksum = None

		if checksum_url is not None:
			if checksum_url.startswith("http"):
				r1 = pm.request("GET", checksum_url)
			elif checksum_url.startswith("https"):
				r1 = spm.request("GET", checksum_url)
			else:
				iktprint([("Error:", "error"), (" Unknown or missing protocol; Checksum URL ", "description"), (f"{checksum_url}", "url")], stderr = True)
				retval = False
				break

			if r1.status == 200:
				checksum = r1.data
			else:
				retval = False
				break

		if url.startswith("http"):
			r1 = pm.request("GET", url)
		elif url.startswith("https"):
			r1 = spm.request("GET", url)
		else:
			iktprint([("Error:", "error"), (" Unknown or missing protocol; URL ", "description"), (f"{url}", "url")], stderr = True)
			retval = False
			continue

		if r1.status == 200:
			# If we have a checksum we need to confirm that the downloaded file matches the checksum
			if checksum is not None and verify_checksum(checksum, checksum_type, r1.data, os.path.basename(url)) == False:
				iktprint([("Critical:", "error"), (" File downloaded from ", "description"), (f"{url}", "url"), (" did not match its expected checksum; aborting.", "description")], stderr = True)
				retval = False
				break

			dl = tempfile.NamedTemporaryFile(delete = False)
			with open(dl.name, "wb", opener = partial(os.open, mode = 0o600)) as f:
				try:
					f.write(r1.data)
				except Exception as e:
					iktprint([("Error: ", "error"), ("Could not write temporary file; exception:", "default")], stderr = True)
					iktprint([(e, "warning")], stderr = True)
					retval = False
					continue

			if tarfile.is_tarfile(dl.name) == True:
				with tempfile.TemporaryDirectory() as td:
					tf = tarfile.open(dl.name, "r")
					members = tf.getnames()
					if filename not in members:
						iktprint([("Critical: ", "critical"), (f"{filename} is not a part of archive; aborting.", "default")], stderr = True)
						sys.exit(errno.ENOENT)

					member = [tf.getmember(filename)]
					tf.extractall(path = td, members = member)
					tf.close()
					os.chmod(f"{td}/{filename}", permissions)
					# The file we extract might be in a subdirectory,
					# but we always want it directly in the destination directory,
					# hence we use basename
					os.rename(f"{td}/{filename}", f"{directory}/{os.path.basename(filename)}")
			else:
				os.chmod(dl.name, permissions)
				os.rename(dl.name, f"{directory}/{filename}")
		else:
			iktprint([("Error: ", "error"), ("Failed to fetch URL ", "default"), (f"{url}", "url"), ("; HTTP code: ", "default"), (f"{r1.status}", "errorvalue")], stderr = True)
			retval = False
			continue
	pm.clear()
	spm.clear()

	return retval
