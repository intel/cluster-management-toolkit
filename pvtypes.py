#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Known Persistent Volumne types. Note: with the introduction of CSIDrivers
most of these are deprecated.
"""

KNOWN_PV_TYPES = {
    "awsElasticBlockStore": {
        "type": "AWS Elastic Block Storage",
        "description": "Represents a Persistent Disk resource in AWS",
        "properties": {
            "Volume ID:": {"path": "volumeID"},
            "Partition #:": {"path": "partition"},
            "Filesystem Type:": {"path": "fsType", "default": "ext4"},
            "Read Only:": {"path": "readyOnly", "default": False},
        },
    },
    "azureDisk": {
        "type": "Azure Disk",
        "description": "Azure Data Disk mount on the host and bind mount to the pod",
        "properties": {
            "Disk Name:": {"path": "diskName"},
            "Disk URI:": {"path": "diskURI"},
            "Filesystem Type:": {"path": "fsType", "default": "ext4"},
            "Read Only:": {"path": "readyOnly", "default": False},
            "Caching Mode:": {"path": "cachingMode"},
            "Kind:": {"path": "kind", "default": "shared"},
        },
    },
    "azureFile": {
        "type": "Azure File",
        "description": "Azure File Service mount on the host and bind mount to the pod",
        "properties": {
            "Share Name:": {"path": "shareName"},
            "Read Only:": {"path": "readyOnly", "default": False},
            # These two should combine to a shortcut to a secret; needs formatting + helper
            "Secret Name:": {"path": "secretName"},
            "Secret Namespace:": {"path": "secretNamespace", "default": "<pod namespace>"},
        },
    },
    "cephfs": {
        "type": "Ceph",
        "properties": {
            "Path:": {"path": "path", "default": "/"},
            # "Monitors:": {"path": "monitors", "processor": field_processor_list},
            "Read Only:": {"path": "readOnly", "default": "False"},
            "Rados User": {"path": "user", "default": "admin"},
            # Should be a shortcut to a secret; needs formatting
            # "Secret:": {"path": "secretRef"},
            "Secret File:": {"path": "secretFile", "default": "/etc/ceph/user.secret"},
        },
    },
    "cinder": {
        # Deprecated
        "type": "OpenStack Cinder Volume",
        "properties": {
            "Volume ID:": {"path": "volumeID"},
            "Filesystem Type:": {"path": "fsType", "default": "ext4"},
            "Read Only:": {"path": "readOnly", "default": "False"},
            # Should be a shortcut to a secret; needs formatting
            # "Secret:": {"path": "secretRef"},
        },
    },
    "csi": {
        "type": "External CSI Volume",
        "description": "Storage managed by an external CSI volume driver",
        "properties": {
            "Volume Handle:": {"path": "volumeHandle"},
            "Driver:": {"path": "driver"},
            "Filesystem Type:": {"path": "fsType"},
            # {"path": "controllerExpandSecretRef"},
            # {"path": "controllerPublishSecretRef"},
            # {"path": "nodeExpandSecretRef"},
            # {"path": "nodePublishSecretRef"},
            "Read Only:": {"path": "readOnly"},
            # {"path": "volumeAttributes"}, # dict(str, str)
        },
    },
    "fc": {
        "type": "Fibre Channel Volume",
        "properties": {
            "Filesystem Type:": {"path": "fsType", "default": "ext4"},
            # "WorldWide Identifiers:": {"path": "wwids", "processor": field_processor_list},
            # "Target WorldWide Names:": {"path": "targetWWNs", "processor": field_processor_list},
            "Logical Unit Number:": {"path": "lun"},
            "Read Only:": {"path": "readOnly", "default": "False"},
        },
    },
    "flexVolume": {
        "type": "FlexPersistentVolumeSource",
        "description": "Generic persistent volume "
                       "resource provisioned/attached using an exec based plugin",
        "properties": {
            "Driver:": {"path": "driver"},
            "Filesystem Type:": {"path": "fsType", "default": "<script dependent>"},
            "Read Only:": {"path": "readOnly", "default": "False"},
            # Should be a shortcut to a secret; needs formatting
            # "Secret:": {"path": "secretRef"},
            "Options": {"path": "options", "default": {}},
        },
    },
    "flocker": {
        "type": "Flocker Volume",
        "description": "Flocker Volume mounted by the Flocker agent",
        "properties": {
            "Dataset Name:": {"path": "datasetName"},
            "Dataset UUID:": {"path": "datasetUUID"},
        },
    },
    "gcePersistentDisk": {
        "type": "GCE Persistent Disk",
        "description": "Google Compute Engine Persistent Disk resource",
        "properties": {
            "PD Name:": {"path": "pdName"},
            "Partition:": {"path": "partition"},
            "Filesystem Type:": {"path": "fsType", "default": "ext4"},
            "Read Only:": {"path": "readOnly", "default": "False"},
        },
    },
    "glusterfs": {
        "type": "GlusterFS",
        "description": "Glusterfs mount that lasts the lifetime of a pod",
        "properties": {
            "Path:": {"path": "path"},
            "Endpoints:": {"path": "endpoints"},
            "Endpoints Namespace:": {"path": "endpoints", "default": "<PVC namespace>"},
            "Read Only:": {"path": "readOnly", "default": "False"},
        },
    },
    "hostPath": {
        # Only works in single-node clusters
        "type": "Host Path",
        "description": "Host path mapped into a pod",
        "properties": {
            "Path:": {"path": "path"},
            "Host Path Type:": {"path": "type", "default": ""},
        },
    },
    "iscsi": {
        "type": "iSCSI Disk",
        "properties": {
            "iSCSI Qualified Name:": {"path": "iqn"},
            "Logical Unit Number:": {"path": "lun"},
            "Target Portal:": {"path": "targetPortal"},
            # "Target Portals:": {"path": "targetPortals", "processor": field_processor_list},
            "Filesystem Type:": {"path": "fsType", "default": "ext4"},
            "Chap Auth Discovery:": {"path": "chapAuthDiscovery"},
            "Chap Auth Session:": {"path": "chapAuthSession"},
            "iSCSI Initiator:": {"path": "initiatorName"},
            "iSCSI Interface:": {"path": "iscsiInterface", "default": "tcp"},
            "Read Only:": {"path": "readOnly", "default": "False"},
            # Should be a shortcut to a secret; needs formatting
            # "Secret:": {"path": "secretRef"},
        },
    },
    "local": {
        "type": "Local",
        "description": "Directly-attached storage with node affinity",
        "properties": {
            "Path:": {"path": "path"},
            "Filesystem Type:": {"path": "fsType", "default": "<auto-detect>"},
        },
    },
    "nfs": {
        "type": "NFS",
        "description": "NFS mount that lasts the lifetime of a pod",
        "properties": {
            "Server:": {"path": "server"},
            "Path:": {"path": "path"},
            "Read Only:": {"path": "readOnly", "default": "False"},
        },
    },
    "portworxVolume": {
        "type": "Portworx volume",
        "properties": {
            "Volume ID:": {"path": "volumeID"},
            "Filesystem Type:": {"path": "fsType", "default": "ext4"},
            "Read Only:": {"path": "readOnly", "default": "False"},
        },
    },
    "quobyte": {
        "type": "Quobyte Mount",
        "description": "Quobyte mount that lasts the lifetime of a pod",
        "properties": {
            "Volume Name:": {"path": "volume"},
            # "Registry:": {
            #     "path": "registry",
            #     "processor": field_processor_str_to_list,
            #     "formatting": {
            #         "iskeyvalue": True,
            #         "field_separators": [ThemeRef("separators", "host")]
            #     }
            # }, # str(host:port, host:port, ...)
            "Read Only:": {"path": "readOnly", "default": "False"},
            "Tenant:": {"path": "tenant"},
            "User:": {"path": "user", "default": "<service account user>"},
            "Group:": {"path": "group", "default": None},
        },
    },
    "rbd": {
        "type": "RBD",
        "description": "Rados Block Device mount that lasts the lifetime of a pod",
        "properties": {
            "Image:": {"path": "image"},
            "Pool:": {"path": "pool", "default": "rbd"},
            "Filesystem Type:": {"path": "fsType", "default": "ext4"},
            # "Monitors:": {"path": "monitors", "processor": field_processor_list},
            "Read Only:": {"path": "readOnly"},
            "Rados User": {"path": "user", "default": "admin"},
            "Keyring:": {"path": "keyring", "default": "/etc/ceph/keyring"},
            # Should be a shortcut to a secret; needs formatting
            # "Secret:": {"path": "secretRef"},
        },
    },
    "scaleIO": {
        # Deprecated
        "type": "Persistent ScaleIO Volume",
        "properties": {
            "Volume Name:": {"path": "volumeName"},
            "Gateway:": {"path": "gateway"},
            "Storage Pool:": {"path": "storagePool"},
            "Storage System:": {"path": "system"},
            "Storage Mode:": {"path": "storageMode", "default": "ThinProvisioned"},
            "Filesystem Type:": {"path": "fsType", "default": "xfs"},
            "Protection Domain:": {"path": "protectionDomain"},
            "SSL Enabled:": {"path": "sslEnabled", "default": "False"},
            "Read Only:": {"path": "readOnly"},
            # Should be a shortcut to a secret; needs formatting
            # "Secret:": {"path": "secretRef"},
        },
    },
    "storageos": {
        "type": "Persistent StorageOS Volume",
        "properties": {
            "Volume Name:": {"path": "volumeName"},
            "Volume Namespace:": {"path": "volumeNamespace", "default": "<pod namespace>"},
            "Filesystem Type:": {"path": "fsType", "default": "ext4"},
            "Read Only:": {"path": "readOnly"},
            # Should be a shortcut to a secret; needs formatting
            # "Secret:": {"path": "secretRef"},
        },
    },
    "vsphereVolume": {
        "type": "vSphere Volume",
        "properties": {
            "Volume Path:": {"path": "volumePath"},
            "Filesystem Type:": {"path": "fsType", "default": "ext4"},
            "Storage Policy ID:": {"path": "storagePolicyID"},
            "Storage Policy Name:": {"path": "storagePolicyName"},
        },
    },
}
