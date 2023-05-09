# Supported platforms

## Platform support

| Functionality:  | Distribution:            | Version: |
| --------------  | ------------------------ | -------- |
| Full            | Debian                   | 11       |
| Full            | Ubuntu                   | 20.04    |
| Kubeadm Cluster | Red Hat Enterprise Linux | 8        |
| None            | SUSE Enterprise Linux    | SLES 15  |

## What prevents __CMT__ from being support on other Distributions / Older versions

In most cases it's simply because it hasn't been tested on those distributions or versions.
But for enterprise distros it's usually because the depencies are either missing or too old.

__CMT__ is written in Python3 and requires version 3.8 or newer.
This rules out installer & tool support for Debian 10 (Python 3.7) and SLES 15 (Python 3.6).
Installation and use of the CMT tools on RHEL 8 systems has not been attempted,
so it's unknown whether it's possible or not.

Some attempts were made to add Kubeadm Cluster support for SLES 15, but since upstream
Kubernetes only is available for Debian and Red Hat distributions, and since SUSE's own
Kubernetes distribution RKE2 is well supported and freely available it was decided not to
continue down that path.
