# Removing worker nodes

## Preparation

Note that __CMT__ and __kubectl__ supports having multiple clusters configured in `~/.kube/config`.
Because of this you need to be very, very careful when removing nodes,
to ensure that you don't remove nodes from a different cluster than intended.
This is especially important when using `cmt remove-node ALL`.

## Remove worker nodes

1. `cmt remove-node [--kubernetes-distro KUBERNETES_DISTRO] HOSTNAME[,HOSTNAME...]`

   _(By default kubeadm will be used; if you use RKE2 you need to specify the --kubernetes-distro option)_

2. _[Wait until cmt remove-node completes]_

## Purge Kubernetes configuration from hosts

1. `cmt purge HOSTNAME[,HOSTNAME...]`
2. _[Wait until cmt purge completes]_

## Performance considerations

If you are removing a lot of worker nodes at the same time you may want to increase the parallelism,
using the `--forks FORKS` option. Check `cmt remove-node --help` for more information.
The same option can be used with `cmt purge`.
