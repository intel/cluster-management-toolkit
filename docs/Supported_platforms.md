# Supported platforms

## Platform support (cluster installation)

| Functionality: | Distribution:            | Version:        |
| :------------- | :----------------------- | :-------------- |
| kubeadm/RKE2   | Debian                   | 11+             |
| kubeadm/RKE2   | Ubuntu                   | 22.04+          |
| kubeadm/RKE2   | Ubuntu Server            | 22.04+          |
| kubeadm        | Red Hat Enterprise Linux | 8*              |
| kubeadm        | Red Hat Enterprise Linux | 9+              |
| kubeadm/RKE2   | SUSE Enterprise Linux    | SLES 15.4+*     |
| kubeadm/RKE2   | openSUSE                 | openSUSE 15.4+* |

## What prevents __CMT__ from being support on other Distributions / Older versions

In most cases it's simply because it hasn't been tested on those distributions or versions.
But for enterprise distros it's usually because the depencies are either missing or too old.

__CMT__ is written in Python3 and requires version 3.9 or newer.
This rules out installer & tool support for Debian 10 (Python 3.7).

On openSUSE/SLES 15 and RHEL 8 you should be able to install python39
and python39-pip or newer to get a recent version of Python3.
You also need to specify `ansible_python_interpreter: <path to python>`
in the Ansible inventory for such hosts, since Ansible playbooks
will fail to run otherwise.

## Limitations

* CRI-O is currently not support as CRI on Red Hat-based distros.
* Upgrading is not supported on SUSE-based distros.
