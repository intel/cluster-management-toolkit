# Supported platforms

## Platform support (cluster installation)

| Functionality: | Distribution:            | Version:       |
| -------------- | ------------------------ | -------------- |
| kubeadm/RKE2   | Debian                   | 11+            |
| kubeadm/RKE2   | Ubuntu                   | 20.04+         |
| kubeadm/RKE2   | Ubuntu Server            | 20.04+         |
| kubeadm        | Red Hat Enterprise Linux | 8*             |
| kubeadm        | Red Hat Enterprise Linux | 9+             |
| RKE2           | SUSE Enterprise Linux    | SLES 15.4*     |
| RKE2           | openSUSE                 | openSUSE 15.4* |

## What prevents __CMT__ from being support on other Distributions / Older versions

In most cases it's simply because it hasn't been tested on those distributions or versions.
But for enterprise distros it's usually because the depencies are either missing or too old.

__CMT__ is written in Python3 and requires version 3.8 or newer.
This rules out installer & tool support for Debian 10 (Python 3.7).

On openSUSE/SLES 15 and RHEL 8 you should be able to install python38
and python38-pip or newer to get a recent version of Python3.

Some attempts were made to add Kubeadm Cluster support for SLES 15, but since upstream
Kubernetes only is available for Debian and Red Hat distributions, and since SUSE's own
Kubernetes distribution RKE2 is well supported and freely available it was decided not to
continue down that path.
