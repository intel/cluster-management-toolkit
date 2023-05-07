## Tearing down a control plane

## Preparation

Tearing down a control plane in essence means tearing down the cluster. To do this you first need to remove all worker nodes from the cluster; see [Remove worker nodes](Remove_worker_node.md#Remove_worker_nodes).

Note that __CMT__ and __kubectl__ supports having multiple clusters configured in `~/.kube/config`. Because of this you need to be very, very careful when tearing down a cluster, to ensure that you don't tear down a different cluster than intended.

## Tear down the cluster

1. `cmtadm teardown-control-plane`
2. _[Wait until cmtadm teardown-control-plane completes]_

## Purge Kubernetes configuration from control plane

1. `cmtadm purge-control-plane`
2. _[Wait until cmtadm purge-control-plane completes]_
