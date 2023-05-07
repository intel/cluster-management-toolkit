# Setting up a control plane

## Preparation

0. _OPTIONAL_: If you want to add a network proxy, see [Configuring a proxy](Configuration.md#configuring-a-proxy)
1. `cmtadm preflight-check HOSTNAME`
2. `cmtadm prepare --control-plane HOSTNAME CLUSTER_NAME [KUBERNETES_VERSION]` (`KUBERNETES_VERSION` is only necessary if you _don't_ want to use the latest version of Kubernetes)
3. _[Wait until cmtadm prepare completes]_

# Create the cluster

1. `cmtadm setup-control-plane [CNI] [POD_NETWORK_CIDR]`
2. _[Wait until cmtadm setup-control-plane completes]_

## Next steps

If you intend to add worker nodes to your cluster, continue to [Setup a worker node](Setup_worker_nodes.md); if you intend to use the control plane as a worker node, see [Use the control plane as a worker node](#use-the-control-plane-as-a-worker-node).

## Use the control plane as a worker node

If you wish to use the control plane as a worker node, you can do so by removing the control plane taint.

`cmtadm untaint-control-plane`

## Performance considerations

If you intend to create a large cluster (hundreds of worker nodes), especially if those nodes are running from virtual machines, it is recommended that you pass `none` as CNI. Once all worker nodes have been added you can then run `cmtadm setup-cni` with the CNI you want to use.
