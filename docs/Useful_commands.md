# Useful commands

## Control plane and cluster
* `cmtadm untaint-control-plane` (Allow the control plane to be used as a worker node)
* `cmtadm taint-control-plane` (Disallow the control plane to be used as a worker node)
* `cmtadm troubleshoot` (Try to find potential problems in the cluster)
* `cmtadm upgrade-control-plane` (Check if there's a newer version of Kubernetes available; if so, upgrade to it)
* `cmtadm upgrade-cni` (Check if there's a newer version of the CNI available; if so, upgrade to it)

## Worker nodes and resources
* `cmt cordon NODE[,...]` (Cordon specified nodes)
* `cmt cordon ALL` (Cordon all nodes)
* `cmt drain NODE[,...]` (Drain specified nodes)
* `cmt drain ALL` (Drain all nodes)
* `cmt force-drain NODE[,...]` (Drain specified nodes and delete emptydir data)
* `cmt force-drain ALL` (Drain all nodes and delete emptydir data)
* `cmt uncordon NODE[,...]` (Uncordon specified nodes)
* `cmt uncordon ALL` (Uncordon all nodes)
* `cmt taint NODE[,...] KEY[:VALUE][=EFFECT]` (Add taint KEY[:VALUE] with EFFECT to specified nodes)
* `cmt taint ALL KEY[:VALUE][=EFFECT]` (Add taint KEY[:VALUE] with EFFECT to all nodes)
* `cmt untaint NODE[,...] KEY[:VALUE][=EFFECT]` (Remove taint KEY[:VALUE] with EFFECT from specified nodes)
* `cmt untaint ALL KEY[:VALUE][=EFFECT]` (Remove taint KEY[:VALUE] with EFFECT from all nodes)
* `cmt upgrade-node NODE,[...]` (Check if the control plane runs a newer version of Kubernetes; if so, upgrade the specified nodes to it)
* `cmt upgrade-node ALL` (Check if the control plane runs a newer version of Kubernetes; if so, upgrade all nodes to it)
* `cmt get-contexts` (List all available contexts)
* `cmt use-context NAME` (Set current context by context name)
* `cmt use-context INDEX` (Set current context by context index)
* `cmt api-resources` (List all available API-resources)

## Inventory
* `cmtinv` (Show __CMT__'s Ansible inventory)
* `cmtinv ping` (Ansible ping all hosts in the inventory)
* `cmtinv ping GROUP[,...]` (Ansible ping all hosts in GROUP[,...])
* `cmtinv ping HOST[,...]` (Ansible ping HOST[,...])
* `cmtinv add-host HOST[,...]` (Add HOST[,...] to the inventory)
* `cmtinv add-host HOST[,...] GROUP[,...]` (Add HOST[,...] to GROUP[,...])
* `cmtinv remove-host HOST[,...]` (Remove HOST[,...] from the inventory)
* `cmtinv remove-host HOST[,...] GROUP[,...]` (Remove HOST[,...] from GROUP[,...])
