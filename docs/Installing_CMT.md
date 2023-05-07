# Installing CMT

If you haven't already cloned the CMT repository, first do so:

`git clone https://github.com/intel/cluster-management-toolkit.git`

## Without proxy

`$ cd cluster-management-toolkit`  
`$ ./cmt-install`

## With proxy

`$ cd cluster-management-toolkit`  
`$ ./cmt-install --pip-proxy PROXY`

Running `cmt-install` creates necessary symlinks, directories, etc.,
and installs the packages necessary to run __CMT__. Note that `cmt-install`
does not perform any cluster setup; all changes takes place on your
local computer. To create a cluster, check [Setup a control plane](Setup_a_control_plane.md#Setting_up_a_control_plane).