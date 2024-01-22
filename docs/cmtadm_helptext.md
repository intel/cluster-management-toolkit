# ___cmtadm___ __COMMAND__ _\[OPTION\]_... _\[ARGUMENT\]_...

Setup or teardown a Kubernetes cluster

## Commands:
### check-versions|cv
#### Update the package cache and show software versions
  
  

_Note_: some of the listed software may not be relevant to the configuration in use
  
  
  __--no-cache-update__
  Do not update the APT cache  
### import-cluster _[_CLUSTER_NAME_,_..._]_
#### Import existing cluster(s) for use with CMT
  
  

If _CLUSTER_NAME_,_..._ is not specified all clusters in _~/.kube/config_ will be imported
  
  
  __-Y__
  Do not ask for confirmation  
  __--no-password__
  Do not prompt for a password  
### prepare __CLUSTER_NAME_ [[_KUBERNETES_DISTRO_=]_KUBERNETES_VERSION_]_
#### Install and configure pre-requisites
  
  

Run this before setup-control-plane. If _KUBERNETES_VERSION_ is not specified the newest available version will be used. Supported versions for _KUBERNETES_DISTRO_ are: _kubeadm_ (default) _rke2_
  
  
  __--control-plane__ __HOST__
  Use _HOST_ as control plane   
  __--resume__
  Resume preparation  
  __--start-at-task__ __TASK__
  Start at _TASK_ instead of running all tasks  
  __--skip-tasks__ __TASK_,_...__
  Skip _TASK_,_..._  
  __--list-tasks__
  List valid values for _TASK_  
  __--no-password__
  Do not prompt for a password  
  __--save-ansible-logs__
  Save logs from Ansible runs  
  __--verbose__
  Be more verbose  
  __-Y__
  Do not ask for confirmation  
### create-cluster __PATH__
#### Create a cluster based on template in _PATH_
  
  

Create a cluster based on a ClusterDeployment template. This combines all the necessary steps to prepare and setup control planes and worker nodes, as well as CNI for a cluster.
  
  
  __--redeploy__
  Redeploy workloads  
  __-Y__
  Do not ask for confirmation  
### setup-control-plane _[_CNI_] [_POD_NETWORK_CIDR_]_
#### Setup and launch the control plane
  
  

Valid options for CNI (Container Network Interface, aka Pod Network):  _antrea_, _calico_, _canal_, _cilium_, _flannel_, _kube-router_, _weave_, _none_ By default _cilium_ will be used as CNI and _10.244.0.0/16_ will be used as pod network CIDR. If you wish to postpone the choice of CNI you can specify _none_
  
  
  __--resume__
  Resume setup  
  __--start-at-task__ __TASK__
  Start at _TASK_ instead of running all tasks  
  __--skip-tasks__ __TASK_,_...__
  Skip _TASK_,_..._  
  __--list-tasks__
  List valid values for _TASK_  
  __--save-ansible-logs__
  Save logs from Ansible runs  
  __--cri__ __CRI__
  Use _CRI_ instead of the default CRI  
  __--enable-dra__
  Enable DRA  
  __--override-cni__
  Override CNI  
  __--verbose__
  Be more verbose  
  __-Y__
  Do not ask for confirmation  
### setup-cni _[_CNI_]_
#### Install and configure CNI
  
  

Valid options for CNI (Container Network Interface, aka Pod Network):  _antrea_, _calico_, _canal_, _cilium_,  _flannel_, _kube-router_, _weave_ By default _cilium_ will be used as CNI
  
  
  __--reinstall__
  Try to reinstall the already installed CNI  
  __-Y__
  Do not ask for confirmation  
  __--verbose__
  Be more verbose  
### uninstall-cni
#### Uninstall the CNI
  
  

This should be used in case you want to switch to another CNI
  
  
  __--cni-version__ __CNI_VERSION__
  The installed CNI version  
  __-Y__
  Do not ask for confirmation  
  __--verbose__
  Be more verbose  
### upgrade-cni _[_CNI_]_
#### Upgrade the CNI
  
  
  __--verbose__
  Be more verbose  
### upgrade-control-plane _[_KUBERNETES_VERSION_]_
#### Upgrade the control plane
  
  

If _KUBERNETES_VERSION_ is not specified the newest available version will be used. Upgrading requires all nodes to be drained first. Once the control plane has been uppgraded you __must__ upgrade all nodes to the same version. __Important__: skipping PATCH REVISIONS is acceptable, but when upgrading to a newer MINOR version all intermediate MINOR versions must be installed first; this applies to nodes too.
  
  
  __--no-cache-update__
  Do not update the APT cache  
  __--resume__
  Resume upgrade  
  __--start-at-task__ __TASK__
  Start at _TASK_ instead of running all tasks  
  __--skip-tasks__ __TASK_,_...__
  Skip _TASK_,_..._  
  __--list-tasks__
  List valid values for _TASK_  
  __--reinstall__
  Allow installing the same version  
  __--override__
  Override/rebuild installation info  
  __--save-ansible-logs__
  Save logs from Ansible runs  
  __--verbose__
  Be more verbose  
  __-Y__
  Do not ask for confirmation  
### teardown-control-plane
#### Tear down the control plane
  
  

__Note__: Before running this command all nodes must have been removed first. The configuration for the control plane and any software installed during setup will NOT be removed
  
  
  __--resume__
  Resume teardown  
  __--start-at-task__ __TASK__
  Start at _TASK_ instead of running all tasks  
  __--skip-tasks__ __TASK_,_...__
  Skip _TASK_,_..._  
  __--list-tasks__
  List valid values for _TASK_  
  __--save-ansible-logs__
  Save logs from Ansible runs  
  __--verbose__
  Be more verbose  
  __-Y__
  Do not ask for confirmation  
### purge-control-plane
#### Purge configuration and packages
  
  

Software and configuration needed for CMT itself will not be purged
  
  
  __--resume__
  Resume purge; can be used if purge was aborted  
  __--start-at-task__ __TASK__
  Start at _TASK_ instead of running all tasks  
  __--skip-tasks__ __TASK_,_...__
  Skip _TASK_,_..._  
  __--list-tasks__
  List valid values for _TASK_  
  __--save-ansible-logs__
  Save logs from Ansible runs  
  __--verbose__
  Be more verbose  
  __-Y__
  Do not ask for confirmation  
### taint-control-plane _[_CONTROLPLANE_,_..._]_
#### Mark control plane(s) as tainted
  
  

If you have previously marked your control plane(s) as untainted you can mark them as tainted using this command. If _CONTROLPLANE_,_..._ is not specified all control planes will be tainted
  
  
### untaint-control-plane _[_CONTROLPLANE_,_..._]_
#### Mark control plane(s) as untainted
  
  

By default control planes are marked as tainted; workloads that lack tolerations will not be scheduled to control planes. If you are running a single-node cluster, or if the control plane is very powerful it might be useful to permit workloads on control plane(s) too. If _CONTROLPLANE_,_..._ is not specified all control planes will be untainted
  
  
### audit
#### Search for potential security issues in the cluster
  
  

__Note__: If the system is configured to use __usergroups__ (every user have their own group that only they belong to); if the name of that group differs from the username be sure to specify that group using the __--usergroup__ _USERGROUP_ option, to prevent the permission checker from complaining about insecure permissions
  
  
  __--disable-usergroup-autodetect__
  Disable usergroup autodetect  
  __--usergroup__ __USERGROUP__
  The name of the usergroup  
### preflight-check __CONTROLPLANE__
#### Preflight check
  
  

Check for potential pitfalls that may prevent preparation or setup from succeeding
  
  
  __--no-password__
  Do not prompt for a password  
### troubleshoot
#### Search for potential problems in the cluster
  
  
  
  
### help __COMMAND__
#### Display help about _COMMAND_ and exit
  
  
  __--format__ __FORMAT__
  Output the help as _FORMAT_ instead  
### help|--help
#### Display this help and exit
  
  
  __--format__ __FORMAT__
  Output the help as _FORMAT_ instead  
### version|--version
#### Output version information and exit
  
  
