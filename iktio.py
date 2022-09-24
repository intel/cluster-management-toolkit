#! /usr/bin/env python3
# Requires: python3 (>= 3.6)
from functools import partial
import os
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

# download_files can extract single files from archives; it will not extract entire archives due to the security risks,
# and it requires the full path of the file within the archive to be specified.
# If later necessary this function could be modified to take a list of multiple files to extract from one tarball;
# for now this does what is necessary though.
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

	for url in fetch_urls:
		if type(url) == tuple:
			url, filename = url
		else:
			tmp = re.match(r".*/(.*)", url)
			if tmp is None:
				iktprint([("Error: ", "error"), ("Could not extract filename from URL ", "default"), (f"{url}", "url")], stderr = True)
				retval = False
				continue
			filename = tmp[1]

		if url.startswith("http"):
			r1 = pm.request("GET", url)
		elif url.startswith("https"):
			r1 = spm.request("GET", url)
		else:
			iktprint([("Error: ", "error"), ("Unknown or missing protocol; URL ", "description"), (f"{url}", "url")], stderr = True)
			retval = False
			continue

		if r1.status == 200:
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
