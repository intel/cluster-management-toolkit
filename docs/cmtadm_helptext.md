# ___`cmtadm`___ __`COMMAND`__ _`[OPTION]`_... _`[ARGUMENT]`_...

Setup or teardown a Kubernetes cluster.

## Commands:
### `check-versions|cv`
#### Update the package cache and show software versions
  
_Note_: some of the listed software may not be relevant to the configuration in use.
  
  __`--force`__
  Force update of the version cache  
  Typically version cache updates are
  rate-limited to once per hour; this option
  forces an update during the cooldown period.

  __`--no-cache-update`__
  Do not update the package caches  
  Alias for:
  “__--no-pkg-cache-update --no-upstream-cache-update__“.

  __`--no-pkg-cache-update`__
  Do not update the distro package cache  

  __`--no-upstream-cache-update`__
  Do not update the upstream package cache  

  __`--verbose`__
  Be more verbose  

### `import-cluster` _[_CLUSTER_NAME_,_..._]_
#### Import existing cluster(s) for use with CMT
  
If _CLUSTER_NAME_,_..._ is not specified all clusters in _~/.kube/config_ will be imported.
  
  __`-Y`__
  Do not ask for confirmation  

  __`--no-password`__
  Do not prompt for a password  
  Use this if the hosts you are importing
  are already configured for login using an SSH key

  __`--save-ansible-logs`__
  Save logs from Ansible runs  
  The logs can be viewed using “cmu logs“

  __`--verbose`__
  Be more verbose  

### `import-kubeconfig` _[_PATH_,_..._]_
#### Merge kubeconfig(s) into _/home/tao/.kube/config_
  
### `prepare` __CLUSTER_NAME_ [[_KUBERNETES_DISTRO_=]_KUBERNETES_VERSION_]_
#### Install and configure pre-requisites
  
Run this before setup-control-plane. If _KUBERNETES_VERSION_ is not specified the newest available version will be used. Supported versions for _KUBERNETES_DISTRO_ are: _kubeadm_ (default) _rke2_
  
  __`--control-plane`__ __HOST__
  Use _HOST_ as control plane   
  _Note_: if possible _HOST_ should be a resolvable
  hostname; using an IP-address may cause issues

  __`--resume`__
  Resume preparation  
  This can be used to resume operations
  if preparation was aborted

  __`--start-at-task`__ __TASK__
  Start at _TASK_ instead of running all tasks  

  __`--skip-tasks`__ __TASK_,_...__
  Skip _TASK_,_..._  

  __`--list-tasks`__
  List valid values for _TASK_  
  List valid values to use with __--start-at-task__
  and __--skip-tasks__

  __`--no-password`__
  Do not prompt for a password  
  Use this if the hosts you are preparing
  are already configured for login using an SSH key

  __`--save-ansible-logs`__
  Save logs from Ansible runs  
  The logs can be viewed using “cmu logs“

  __`--verbose`__
  Be more verbose  

  __`-Y`__
  Do not ask for confirmation  

### `create-cluster` __PATH__
#### Create a cluster based on template in _PATH_
  
Create a cluster based on a ClusterDeployment template. This combines all the necessary steps to prepare and setup control planes and worker nodes, as well as CNI for a cluster.
  
  __`--redeploy`__
  Redeploy workloads  

  __`-Y`__
  Do not ask for confirmation  

### `setup-control-plane` _[_CNI_] [_POD_NETWORK_CIDR_]_
#### Setup and launch the control plane
  
Valid options for CNI (Container Network Interface, aka Pod Network):  _antrea_, _calico_, _canal_, _cilium_, _flannel_, _kube-router_, _weave_, _none_ By default _cilium_ will be used as CNI and _10.244.0.0/16_ will be used as pod network CIDR. If you wish to postpone the choice of CNI you can specify _none_.
  
  __`--resume`__
  Resume setup  
  This can be used to resume operations
  if control plane setup was aborted

  __`--start-at-task`__ __TASK__
  Start at _TASK_ instead of running all tasks  

  __`--skip-tasks`__ __TASK_,_...__
  Skip _TASK_,_..._  

  __`--list-tasks`__
  List valid values for _TASK_  
  List valid values to use with __--start-at-task__
  and __--skip-tasks__

  __`--save-ansible-logs`__
  Save logs from Ansible runs  
  The logs can be viewed using “cmu logs“

  __`--cri`__ __CRI__
  Use _CRI_ instead of the default CRI  
  Valid options for CRI
  (Container Runtime Interface) are:
  _containerd_, _cri-o_
  Default CRI:
  _containerd_ (rke2),
  _containerd_ (kubeadm),
  _cri-o_ (kubeadm with __--enable-dra__)
  _Note_: Kubernetes >= _1.26_ requires
  _containerd_ >= _1.6_ or _cri-o_

  __`--enable-dra`__
  Enable DRA  
  Enables the feature gates necessary to use
  Dynamic Resource Allocation (DRA).
  Currently only _cri-o_ supports DRA

  __`--override-cni`__
  Override CNI  
  Allow a change of CNI even if installation
  started with a different CNI

  __`--verbose`__
  Be more verbose  

  __`-Y`__
  Do not ask for confirmation  

### `setup-cni` _[_CNI_]_
#### Install and configure CNI
  
Valid options for CNI (Container Network Interface, aka Pod Network):  _antrea_, _calico_, _canal_, _cilium_,  _flannel_, _kube-router_, _weave_ By default _cilium_ will be used as CNI
  
  __`--reinstall`__
  Try to reinstall the already installed CNI  

  __`-Y`__
  Do not ask for confirmation  

  __`--verbose`__
  Be more verbose  

### `uninstall-cni`
#### Uninstall the CNI
  
This should be used in case you want to switch to another CNI
  
  __`--cni-version`__ __CNI_VERSION__
  The installed CNI version  
  Use this option to specify
  the version in case it cannot
  be autodetected

  __`-Y`__
  Do not ask for confirmation  

  __`--verbose`__
  Be more verbose  

### `upgrade-cni` _[_CNI_]_
#### Upgrade the CNI
  
  __`--verbose`__
  Be more verbose  

### `upgrade-control-plane` _[_KUBERNETES_VERSION_]_
#### Upgrade the control plane
  
If _KUBERNETES_VERSION_ is not specified the newest available version will be used. Upgrading requires all nodes to be drained first. Once the control plane has been uppgraded you __must__ upgrade all nodes to the same version. __Important__: skipping PATCH REVISIONS is acceptable, but when upgrading to a newer MINOR version all intermediate MINOR versions must be installed first; this applies to nodes too.
  
  __`--ignore-feature-gates`__
  Ignore the result of the feature gates check  
  Upgrading a cluster may fail if the default
  set of feature gates has been altered; by default
  upgrades are aborted if such changesare detected.
  This option makes the check non-aborting.
  _Note_: this may yield a failed installation
  or non-operational cluster

  __`--no-cache-update`__
  Do not update the APT cache  

  __`--resume`__
  Resume upgrade  
  This can be used to resume operations
  if upgrade was aborted

  __`--start-at-task`__ __TASK__
  Start at _TASK_ instead of running all tasks  

  __`--skip-tasks`__ __TASK_,_...__
  Skip _TASK_,_..._  

  __`--list-tasks`__
  List valid values for _TASK_  
  List valid values to use with __--start-at-task__
  and __--skip-tasks__

  __`--reinstall`__
  Allow installing the same version  
  This option allows you to install the same
  version that's already running in the cluster

  __`--override`__
  Override/rebuild installation info  

  __`--save-ansible-logs`__
  Save logs from Ansible runs  
  The logs can be viewed using “cmu logs“

  __`--verbose`__
  Be more verbose  

  __`-Y`__
  Do not ask for confirmation  

### `teardown-control-plane`
#### Tear down the control plane
  
__Note__: Before running this command all nodes must have been removed first. The configuration for the control plane and any software installed during setup will NOT be removed
  
  __`--resume`__
  Resume teardown  
  This can be used to resume operations
  if teardown was aborted

  __`--start-at-task`__ __TASK__
  Start at _TASK_ instead of running all tasks  

  __`--skip-tasks`__ __TASK_,_...__
  Skip _TASK_,_..._  

  __`--list-tasks`__
  List valid values for _TASK_  
  List valid values to use with __--start-at-task__
  and __--skip-tasks__

  __`--save-ansible-logs`__
  Save logs from Ansible runs  
  The logs can be viewed using “cmu logs“

  __`--verbose`__
  Be more verbose  

  __`-Y`__
  Do not ask for confirmation  

### `purge-control-plane`
#### Purge configuration and packages
  
Software and configuration needed for CMT itself will not be purged
  
  __`--resume`__
  Resume purge; can be used if purge was aborted  

  __`--start-at-task`__ __TASK__
  Start at _TASK_ instead of running all tasks  

  __`--skip-tasks`__ __TASK_,_...__
  Skip _TASK_,_..._  

  __`--list-tasks`__
  List valid values for _TASK_  
  List valid values to use with __--start-at-task__
  and __--skip-tasks__

  __`--save-ansible-logs`__
  Save logs from Ansible runs  
  The logs can be viewed using “cmu logs“

  __`--verbose`__
  Be more verbose  

  __`-Y`__
  Do not ask for confirmation  

### `taint-control-plane` _[_CONTROLPLANE_,_..._]_
#### Mark control plane(s) as tainted
  
If you have previously marked your control plane(s) as untainted you can mark them as tainted using this command. If _CONTROLPLANE_,_..._ is not specified all control planes will be tainted
  
### `untaint-control-plane` _[_CONTROLPLANE_,_..._]_
#### Mark control plane(s) as untainted
  
By default control planes are marked as tainted; workloads that lack tolerations will not be scheduled to control planes. If you are running a single-node cluster, or if the control plane is very powerful it might be useful to permit workloads on control plane(s) too. If _CONTROLPLANE_,_..._ is not specified all control planes will be untainted
  
### `audit`
#### Search for potential security issues in the cluster
  
__Note__: If the system is configured to use __usergroups__ (every user have their own group that only they belong to); if the name of that group differs from the username be sure to specify that group using the __--usergroup__ _USERGROUP_ option, to prevent the permission checker from complaining about insecure permissions
  
  __`--disable-usergroup-autodetect`__
  Disable usergroup autodetect  
  __Note__: the audit command attempts
  to autodetect whether __usergroups__ are in use;
  use this option to disable autodetect

  __`--usergroup`__ __USERGROUP__
  The name of the usergroup  

### `preflight-check` __CONTROLPLANE__
#### Preflight check
  
Check for potential pitfalls that may prevent preparation or setup from succeeding
  
  __`--no-password`__
  Do not prompt for a password  
  Use this if the hosts you are preparing
  are already configured for login using an SSH key

### `troubleshoot`
#### Search for potential problems in the cluster
  
  
### `help` __COMMAND__
#### Display help about _COMMAND_ and exit
  
  __`--format`__ __FORMAT__
  Output the help as _FORMAT_ instead  
  Valid formats are:
  _default_, _markdown_

### `help|--help`
#### Display this help and exit
  
  __`--format`__ __FORMAT__
  Output the help as _FORMAT_ instead  
  Valid formats are:
  _default_, _markdown_

### `version|--version`
#### Output version information and exit
  
