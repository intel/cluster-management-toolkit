# Setting up worker nodes

## Preparation

0. _OPTIONAL_: If you want to add a network proxy, see [Configuring a proxy](Configuration.md#Configuring_a_proxy)
1. `cmt prepare HOSTNAME[,HOSTNAME...]`
2. _[Wait until cmt prepare completes]_

## Add worker nodes
1. `cmt add-node HOSTNAME[,HOSTNAME...]`
2. _[Wait until cmt add-node completes]_

## Performance considerations

If you are preparing a lot of worker nodes at the same time you may want to increase the parallelism, using the `--forks FORKS` option. Check `cmt prepare --help` for more information.  The same option can be used with `cmt add-node`.
