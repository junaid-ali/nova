"""Handles IORCL requests from other (conductor) nova services."""

'''
import copy
import itertools

import six

from nova import block_device
from nova.compute import task_states
from nova.compute import utils as compute_utils
from nova.compute import vm_states
from nova.conductor.tasks import live_migrate
from nova import exception
from nova import image
from nova import notifications
from nova.objects import base as nova_object
from nova.openstack.common import timeutils
from nova import quota
from nova.scheduler import client as scheduler_client
from nova.scheduler import driver as scheduler_driver
from nova.scheduler import utils as scheduler_utils
'''

import time

from oslo import messaging

from nova.db import base

from nova import manager
from nova import network
from nova import volume
from nova import utils
from nova.compute import api as compute_api
from nova.compute import rpcapi as compute_rpcapi
from nova.network.security_group import openstack_driver
from nova.cells import rpcapi as cells_rpcapi

from nova.i18n import _

from nova.objects import block_device as block_device_obj
from nova.virt import block_device as driver_block_device

from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging
from nova.openstack.common import excutils

from nova.virt import virtapi
from nova.virt import driver

from nova.volume import encryptors


LOG = logging.getLogger(__name__)


class IORCLManager(manager.Manager):
    """Mission: IO Resource Consolidation Layer things.

    The methods in the base API for nova-iorcl are various operations
    performed to connect IO resource to/from VMs through the IO Hypervisor.

    The nova-iorcl service also exposes an API in the 'compute_task'
    namespace.  See the ComputeTaskManager class for details.
    """

    target = messaging.Target(version='1.0')

    def __init__(self, *args, **kwargs):
        super(IORCLManager, self).__init__(service_name='iorcl',
                                               *args, **kwargs)
        self.security_group_api = (
            openstack_driver.get_openstack_security_group_driver())
        self._network_api = None
        self._compute_api = None
        self._volume_api = None
        self.compute_task_mgr = ComputeTaskManager()
        self.cells_rpcapi = cells_rpcapi.CellsAPI()
        self.additional_endpoints.append(self.compute_task_mgr)

    @property
    def network_api(self):
        # NOTE(danms): We need to instantiate our network_api on first use
        # to avoid the circular dependency that exists between our init
        # and network_api's
        if self._network_api is None:
            self._network_api = network.API()
        return self._network_api

    @property
    def compute_api(self):
        if self._compute_api is None:
            self._compute_api = compute_api.API()
        return self._compute_api

    @property
    def volume_api(self):
        if self._volume_api is None:
            self._volume_api = volume.API()
        return self._volume_api

    def ping(self, context, arg):
        # NOTE(russellb) This method can be removed in 2.0 of this API.  It is
        # now a part of the base rpc API.
        return jsonutils.to_primitive({'service': 'iorcl', 'arg': arg})


class ComputeVirtAPI(virtapi.VirtAPI):
    def __init__(self, compute):
        super(ComputeVirtAPI, self).__init__()
        self._compute = compute


class ComputeTaskManager(base.Base):
    """Namespace for compute methods.

    This class presents an rpc API for nova-iorcl under the 'compute_task'
    namespace.  The methods here are compute operations that are invoked
    by the API service.  These methods see the operation to completion, which
    may involve coordinating activities on multiple compute nodes.
    """

    target = messaging.Target(namespace='compute_task', version='1.0')

    def __init__(self, compute_driver=None):
        super(ComputeTaskManager, self).__init__()
        self.compute_rpcapi = compute_rpcapi.ComputeAPI()
        self.volume_api = volume.API()
        self.network_api = network.API()

        self.virtapi = ComputeVirtAPI(self)
        self.driver = driver.load_compute_driver(self.virtapi, compute_driver)


    def io_attach_volume(self, context, instance, volume_id):
        """Attach a volume to an instance through the IO Hypervisor.""" 
        bdm = block_device_obj.BlockDeviceMapping.get_by_volume_id(
                context, volume_id)
        driver_bdm = driver_block_device.DriverVolumeBlockDevice(bdm)

        @utils.synchronized(instance.uuid)
        def do_attach_volume(context, instance, driver_bdm):
            try:
                return self._attach_volume(context, instance, driver_bdm)
            except Exception:
                with excutils.save_and_reraise_exception():
                    bdm.destroy(context)

        info = do_attach_volume(context, instance, driver_bdm)

        # At this point, the volume is mounted in the local host, but
        # not linked to the VM
        # Remaining steps:
        #    - Create veth pair with the proper VLAN
        #    - Call IO Hyp. API to link VM to the volume:
        #        + ioManager.py VM_MAC local_IF local_dev
        #        + NOTE: if vm in FT mode, ioManager should also attach the 
        #          block device to the secondary VM
        network_info = self.network_api.get_instance_nw_info(context, 
                                                             instance)

        instanceMAC= network_info[0]['address']
        instanceIP = (
            network_info[0]['network']['subnets'][0]['ips'][0]['address'])

        volume_mount_device = driver_bdm['mount_device'][5:]
        volume_block_device = driver_bdm['connection_info']['data']['host_device']
        instanceVLAN = network_info[0]['network']['meta']['vlan']

        self._create_connection_to_instance_vlan(context, instanceVLAN)
        io_veth_name = "io-veth" + str(instanceVLAN)

        context = context.elevated()
       
        LOG.audit(_('Calling the IO Hyp. with: '
                  'iohyp_create_blk_device.sh -i %(veth_device)s '
                  '-p %(volume_id)s -w %(mountpoint)s '
                  '-g %(mac)s -t %(ip)s'),
                  {'veth_device': io_veth_name,
                  'volume_id': volume_block_device,
                  'mountpoint': volume_mount_device,
                  'mac': instanceMAC,
                  'ip': instanceIP},
                  context=context, instance=instance)

        args = ['-i', str(io_veth_name),
                '-p', str(volume_block_device),
                '-w', str(volume_mount_device),
                '-g', str(instanceMAC),
                '-t', str(instanceIP)]
        full_args = ['iohyp_create_blk_device.sh'] + args
        utils.execute(*full_args, run_as_root=True)


        return info

    def _create_connection_to_instance_vlan(self, context, vlan):
        self.driver.create_io_vlan_connection(context, vlan)

    def _attach_volume(self, context, instance, bdm):
        # NOTE (LTB): I still need to make some extra checking, such as:
        #    - Is it a FT VM? Primary? Secondary? 
        #    - Is the volume already attached? Then do not do all the steps
        context = context.elevated()
        LOG.audit(_('Attaching IO volume %(volume_id)s to %(mountpoint)s'),
                  {'volume_id': bdm.volume_id,
                  'mountpoint': bdm['mount_device']},
                  context=context, instance=instance)
        try:
            # NOTE: do_driver_attach = False as the link between the 
            # volume and the VM will be through the network from the 
            # I/O Hypervisor
            bdm.attach(context, instance, self.volume_api, self.driver,
                       do_check_attach=False, do_driver_attach=False,
                       do_io_attach=True)
        except Exception:  # pylint: disable=W0702
            with excutils.save_and_reraise_exception():
                LOG.exception(_LE("Failed to attach %(volume_id)s "
                                  "at %(mountpoint)s"),
                              {'volume_id': bdm.volume_id,
                               'mountpoint': bdm['mount_device']},
                              context=context, instance=instance)
                self.volume_api.unreserve_volume(context, bdm.volume_id)

        info = {'volume_id': bdm.volume_id}
        return info


    def io_detach_volume(self, context, instance, bdm):
        # NOTE (LTB): I still need to make some extra checking, such as:
        #    - Is it a FT VM? Primary? Secondary? 
        #    - Is the volume attached to several VMs?
        #      Then do not do all the steps

        # At this point, the volume is mounted in the local host
        # and linked to the VM
        # Remaining steps:
        #    - Call IO Hyp API to unlink VM to the volume
        #    - Remove veth pair
        # NOTE: if vm in FT mode, ioManager should consider 
        # if it is the primary or the secondary

        # After those steps, terminate iSCSI connection between:
        # IO Hyp. host and the cinder host
        self._detach_volume(context, instance, bdm)
        connector = self.driver.get_volume_connector(instance)
        self.volume_api.terminate_connection(context, bdm.volume_id, connector)

    def _detach_volume(self, context, instance, bdm):
        """Do the actual driver detach using block device mapping."""
        mp = bdm.device_name
        volume_id = bdm.volume_id

        LOG.audit(_('Detach IO volume %(volume_id)s from mountpoint %(mp)s'),
                  {'volume_id': volume_id, 'mp': mp},
                  context=context, instance=instance)

        connection_info = jsonutils.loads(bdm.connection_info)

        # LTB: QUICK FIX TO BE REMOVED
        volume_connection = "/dev/disk/by-path/ip-192.168.26.1:3260-iscsi-iqn.2010-10.org.openstack:volume-" + str(volume_id) + "-lun-0"

        LOG.audit(_('Calling the IO Hyp. with: '
                  'iohyp_remove_blk_device.sh -p %(volume_id)s'),
                  #{'volume_id': connection_info['data']['host_device']},
                  {'volume_id': volume_connection},
                  context=context, instance=instance)

        #args = ['-p', str(connection_info['data']['host_device'])]
        args = ['-p', str(volume_connection)]
        full_args = ['iohyp_remove_blk_device.sh'] + args
        utils.execute(*full_args, run_as_root=True)

        time.sleep(3.0)

        # NOTE(vish): We currently don't use the serial when disconnecting,
        #             but added for completeness in case we ever do.
        if connection_info and 'serial' not in connection_info:
            connection_info['serial'] = volume_id
        try:
            encryption = encryptors.get_encryption_metadata(
                context, self.volume_api, volume_id, connection_info)

            self.driver.io_detach_volume(connection_info,
                                      instance,
                                      mp,
                                      encryption=encryption)
        except Exception:  # pylint: disable=W0702
            with excutils.save_and_reraise_exception():
                LOG.exception(_LE('Failed to detach IO volume %(volume_id)s '
                                  'from %(mp)s'),
                              {'volume_id': volume_id, 'mp': mp},
                              context=context, instance=instance)
                self.volume_api.roll_detaching(context, volume_id)
 
    def io_reset_guest(self, context, instance):
        LOG.debug("ORBIT DEBUG: Reset the IO devices from guest instance %s",
                   instance['uuid'])


