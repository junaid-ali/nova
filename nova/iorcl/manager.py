"""Handles IORCL requests from other (conductor) nova services."""

'''
import copy
import itertools

import six

from nova.api.ec2 import ec2utils
from nova import block_device
from nova.compute import task_states
from nova.compute import utils as compute_utils
from nova.compute import vm_states
from nova.conductor.tasks import live_migrate
from nova.db import base
from nova import exception
from nova.i18n import _
from nova import image
from nova import manager
from nova import notifications
from nova import objects
from nova.objects import base as nova_object
from nova.openstack.common import excutils
from nova.openstack.common import timeutils
from nova import quota
from nova.scheduler import client as scheduler_client
from nova.scheduler import driver as scheduler_driver
from nova.scheduler import utils as scheduler_utils
'''

from oslo import messaging

from nova import network
from nova import volume
from nova.compute import api as compute_api
from nova.compute import rpcapi as compute_rpcapi
from nova.network.security_group import openstack_driver
from nova.cells import rpcapi as cells_rpcapi

from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class IORCLManager(manager.Manager):
    """Mission: IO Resource Consolidation Layer things.

    The methods in the base API for nova-iorcl are various operations
    performed to connect IO resource to/from VMs through the IO Hypervisor.

    The nova-iorcl service also exposes an API in the 'compute_task'
    namespace.  See the ComputeTaskManager class for details.
    """

    target = messaging.Target(version='2.0')

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


class ComputeTaskManager(base.Base):
    """Namespace for compute methods.

    This class presents an rpc API for nova-iorcl under the 'compute_task'
    namespace.  The methods here are compute operations that are invoked
    by the API service.  These methods see the operation to completion, which
    may involve coordinating activities on multiple compute nodes.
    """

    target = messaging.Target(namespace='compute_task', version='1.9')

    def __init__(self):
        super(ComputeTaskManager, self).__init__()
        self.compute_rpcapi = compute_rpcapi.ComputeAPI()
        self.volume_api = volume.API()
        self.network_api = network.API()


    def io_attach_volume(self, context, instance, volume_id):
        LOG.debug("ORBIT DEBUG: Attaching the volume %s to instance %s",
                   volume_id, instance['uuid'])

        network_info = self.network_api.get_instance_nw_info(context,
                                                             instance)

    def io_detach_volume(self, context, instance, volume_id):
        LOG.debug("ORBIT DEBUG: Detaching the volume %s from instance %s",
                   volume_id, instance['uuid'])

        network_info = self.network_api.get_instance_nw_info(context,
                                                             instance)

    def io_attach_interface(self, context, instance, vif):
        LOG.debug("ORBIT DEBUG: Attaching the interface %s to instance %s",
                   vif, instance['uuid'])

        network_info = self.network_api.get_instance_nw_info(context,
                                                             instance)

    def io_detach_interface(self, context, instance, vif):
        LOG.debug("ORBIT DEBUG: Detaching the interface %s from instance %s",
                   vif, instance['uuid'])

        network_info = self.network_api.get_instance_nw_info(context,
                                                             instance)

    def io_reset_guest(self, context, instance):
        LOG.debug("ORBIT DEBUG: Reset the IO devices from guest instance %s",
                   instance['uuid'])


