# Creating a cluster using a template file

## Introduction to `cmtadm create-cluster`

The easiest way to create a cluster using `cmtadm` is by using a template file.
This has several benefits; it means that you'll have a complete blueprint for recreating
or duplicating your cluster. It also means that you can easily check what configuration
you used. All this provided you save your template, obviously.

Using a cluster template you can configure labels, feature gates, deploy workloads, etc.,
all in one action. An example template is available here:

[Example cluster template](examples/cluster_config.yaml#cluster-config)

You need to fill out all sections of the template that say `mandatory`.

## Create the cluster

Once your template file is filled out you can create the cluster simply by running:

```
cmtadm create-cluster TEMPLATE_FILE
```

## Next steps

Once installation finishes it is __strongly__ recommended that you save your cluster template.
We suggest storing it in a version control system (such as git). That way you can easily
retrieve the file if you need to rebuild your cluster, track changes, etc.

## Notes

Cluster creation using template files is a fairly new feature. We have tried to cover most basic
use cases, but it's likely that some things have been overlooked. If you have suggestions
for improvements, let us know. The templates are versioned for a reason.

Please file feature requests in our issue tracker:

[Feature Request](https://github.com/intel/cluster-management-toolkit/issues).
