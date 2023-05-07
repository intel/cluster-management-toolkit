# Pre-requisites / tested platforms for the toolkit

The installer, `cmt-install` has only been tested on Debian and Ubuntu.
Any up to date Debian-derivative is likely work.

If the dependencies are installed manually, any distro or self-compiled
system that provides recent enough versions of all pre-requisites should be expected to work.
Windows is not supported at the moment, and is unlikely to work even
if all dependencies are been provided manually, due to differences
in path lookup and various I/O-operations.

## Dependencies for the toolkit (from `requirements.txt`)

* `python3-ansible-runner` (>= 2.1.3)
* `python3-natsort` (>= 8.0.2)
* `python3-yaml` (>= 6.0)
* `python3-ujson` (>= 5.4; not a strict necessity, just a nice performance improvement)
* `python3-urllib3` (>= 1.26.9)
* `python3-validators` (>= 0.14.2)

# Pre-requisites / tested platforms for setting up Kubernetes clusters

The development platform for __CMT__ is Debian and Ubuntu, and those two are thus the most tested platforms. But limited testing has also been performed on RHEL8; some functionality, such as support for _CRI-O_, is currently missing on RHEL, but other than that it should be possible to install a cluster on a RHEL system using `cmtadm`/`cmt`.

Support for Suse is currently work in progress.  Other distributions are not supported at this point. This also applies to Windows.

# Supported hardware architectures

The only supported hardware architecture at the moment is _x86-64_/_amd64_.
_arm_, _arm64_, _ppc64le_, and _s390x_ are not supported, but may be added if there's enough interest.

# Other pre-requisites

`cmt-install`, `cmtadm`, `cmt`, and `cmu` requires the user to have _sudo_ access. None of the programs can be run directly as root. The user also needs _sudo_ access on any remote system intended for use as control planes or worker nodes in a cluster.
