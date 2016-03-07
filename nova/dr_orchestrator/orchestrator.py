"""Handles DR-Orchestrator requests and the optimization loop."""

import os

from oslo import messaging
from oslo.config import cfg

from nova.db import base
from nova import manager
from nova.network.security_group import openstack_driver
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging
from nova.openstack.common import periodic_task
from nova import exception

from nova import context as ctxt

from nova import volume
from nova import compute
from nova.dr_orchestrator import dragon
from nova.dr_orchestrator.logic import logic

from dragonclient import client as dr_client
from keystoneclient.v2_0 import client as ksclient

LOG = logging.getLogger(__name__)


interval_opts = [
    cfg.IntOpt('drlogic_interval',
               default=30,
               help='Interval for the DR-Logic optimization control loop.'),
    cfg.IntOpt('drlogic_clean_up_interval',
               default=3600,
               help='Interval for data protection clean up.'),
    cfg.IntOpt('max_protection_interval',
               default=30,
               help='Maximum interval between protecting actions (minutes).'),
]

dr_opts = [
    cfg.StrOpt('dr_policy_name',
               default='orbit1.ds.cs.umu.se',
               help='Default name used to protect the VMs/Volumes.'),

    cfg.IntOpt('dr_instance',
               default=1,
               help='Default value to represent instance protect type.'),
    cfg.IntOpt('dr_volume',
               default=2,
               help='Default value to represent volume protect type.'),

    cfg.StrOpt('dr_default_instance_action',
               default="Image Copy",
               help='Default replication action for instances.'),
#    cfg.StrOpt('dr_default_volume_action',
#               default="Volume Replication",
#               help='Default replication action for volumes.'),
]

CONF = cfg.CONF
CONF.register_opts(interval_opts)
CONF.register_opts(dr_opts)

PROTECTABLE_STATES = ("available","in-use")


class OrchestratorManager(manager.Manager):
    """Mission: DR-Orchestration actions and optimization logic.

    """

    target = messaging.Target(version='2.0')

    def __init__(self, *args, **kwargs):
        super(OrchestratorManager, self).__init__(
                         service_name='dr_orchestrator', *args, **kwargs)

        self.security_group_api = (
            openstack_driver.get_openstack_security_group_driver())

        # POJECT ID is set in the dragon/dragon.py file
        #self._project_id  = None

        self._resources_to_protect = []

        self._policy_name = CONF.dr_policy_name
        self._policy_id = None

        self._default_instance_replication_action = None
        self._default_volume_replication_action = None
        self._default_volume_snapshot_action = None

        self.volume_api = volume.API()
        self.nova_api = compute.API()
        self.dragon_api = dragon.API()

        self.logic_api = logic.Logic()

        self._default_loops_to_protect= int((60.0 / CONF.drlogic_interval) * \
                                             CONF.max_protection_interval)
        self._loops_to_protect = 5


    def ping(self, context, arg):
        # NOTE(russellb) This method can be removed in 2.0 of this API.  It is
        # now a part of the base rpc API.
        return jsonutils.to_primitive({'service': 'dr_orchestrator', 
                                       'arg': arg})


    def _get_default_replication_action(self, context, resource_type_id, 
                                        resource_type):
        if resource_type == "Instance":
            for policy in self.dragon_api.list_actions(context, 
                                                       resource_type_id):
                if policy["name"] == CONF.dr_default_instance_action:
                    return policy["id"]
        if resource_type == "Volume":
            replication_id = None
            snapshot_id = None
            for policy in self.dragon_api.list_actions(context, 
                                                       resource_type_id):
                if policy["name"] == "Volume Replication":
                    replication_id = policy["id"]
                elif policy["name"] == "Volume Snapshot":
                    snapshot_id = policy["id"]
            return replication_id, snapshot_id
        return None


    def _create_base_workload_policy(self, context):
        """After the service is initialized, but before we fully bring
        the service up by listening on RPC queues, make sure that a 
        workload policy is available.
        """
        if not self._check_workload_policy_exists(context):
            workload_policy = self.dragon_api.create_workload_policy(
                                                          context,
                                                          self._policy_name)
            self._policy_id = workload_policy["id"]

        LOG.debug("Workload policy name is %s with ID %s", 
                                          self._policy_name, self._policy_id)


    def _check_workload_policy_exists(self, context):
        """ Check if there is a workload_policy to protect VMs/Volumes
        """
        LOG.debug("Checking if the workload_policy is already configured.")
        for workload_policies in self.dragon_api.list_workload_policies(
                                                     context):
            if workload_policies["name"] == self._policy_name:
                LOG.debug("Policy already exists")
                self._policy_id = workload_policies["id"]
                return True
        return False


    @periodic_task.periodic_task(spacing=CONF.drlogic_clean_up_interval,
                                 run_immediately=True)
    def dr_cleanup(self, context):
        LOG.debug("Cleaning up old protection data.")
        policies = self.dragon_api.recovery_list_policies(context)
        for policy in policies:
            executions = self.dragon_api.recovery_list_policy_executions(context, policy['id'])
            for execution in executions[1:]:
                LOG.debug("Deleting container wit id: %s", execution['id'])
                self.dragon_api.delete_policy_execution(context, execution['id'])




    @periodic_task.periodic_task(spacing=CONF.drlogic_interval,
                                 run_immediately=True)    
    def dr_logic(self, context):
        """ Control Loop that optimized the backup actions over time.
        """
        LOG.debug("DR-Logic Loop")

        """Initializing the sytem.
        Set default parameters and create default workload policy.
        """
        if self._policy_id == None:
            LOG.debug("Initializing DR-Orchestration")
            
            self._default_instance_replication_action = \
                         self._get_default_replication_action(
                                  context,
                                  CONF.dr_instance,
                                  resource_type="Instance")
            (self._default_volume_replication_action, 
                self._default_volume_snapshot_action) = \
                         self._get_default_replication_action(
                                  context,
                                  CONF.dr_volume,
                                  resource_type="Volume")

            self._create_base_workload_policy(context)
        

        """ Calls the optimization Logic -- DR-Logic."""
        triggerProtect, resources_to_include = \
                       self.logic_api.get_optimization_actions(
                                          context, 
                                          self._resources_to_protect)
    
        LOG.debug("Protect need to be triggered: %s", triggerProtect)
        LOG.debug("Resources to be included are: %s", resources_to_include)

        """Include the selected resources in the workload policy."""
        if resources_to_include:
            self._add_resources(context, resources_to_include)

        """Protect the workload policy based on DR-Logic decision ."""
        if triggerProtect or self._loops_to_protect == 0:
            self._dr_protect(context, self._policy_id)
            self._loops_to_protect = self._default_loops_to_protect
        
        self._loops_to_protect -= 1



    def _add_resources(self, context, resources_to_protect):
        """ Include the new resources in the workload policy.

        The default policy for VMs is image_copy.
        The default policy for Volumes is volume_replication.
        """
        for resource in resources_to_protect:
            # remove resource from the list
            self._resources_to_protect.remove(resource)
            if resource["resource_type_id"] == CONF.dr_instance:
                self.dragon_api.create_resource_action(
                         context,
                         resource["id"],
                         self._default_instance_replication_action,
                         self._policy_id)

            elif resource["resource_type_id"] == CONF.dr_volume:
                if resource['volume_type'] == 'drbddriver-1':  
                    self.dragon_api.create_resource_action(
                             context,
                             resource["id"],
                             self._default_volume_replication_action,
                             self._policy_id)
                else:
                    self.dragon_api.create_resource_action(
                             context,
                             resource["id"],
                             self._default_volume_snapshot_action,
                             self._policy_id)

            else:
                LOG.debug("Not protecting resource %s." 
                          "Reason: Unknown type of resource", resource["id"])


    def _dr_protect(self, context, policy_id):
        """ Protect the resources within the given policy.

        It call DR-Engine to perform the actions
        """
        LOG.debug("Calling DR-Engine to protect the workoad_policy %s",
                  policy_id)

        self.dragon_api.protect(context, policy_id)


    def _enough_network_capacity(self):
        """TO DO
 
        Here we need to implement the required admission control policies.

        NOTE: all the VMs are accepted for now.
        """
        return True


    def _get_policies_for_datacenter(self, context, datacenter):
        """TO DO
        Here we need to implement a method to obtain the policies that 
        belong to datacenter 'datacenter'

        It could also return them in the order they want to be recovered,
        by calling the proper method at the logic policy driver.

        NOTE: just one policy per datacenter, with policy name equals hostname
        """
        return datacenter

    
    # API offered to users/horizon
    def protect(self, context, resource_id, resource_type):
        """ Makes the resource ready to be protected.

        It first decides whether or not it is possible to protect it.
        
        NOTE: this does not mean the resource is protected, just that it
        will be eventually protected when the Optimization Logic decides 
        it is a good time.
        """
        if self._enough_network_capacity():
            if resource_type == "Instance":
                instance = self.nova_api.get(context, resource_id)
                if instance['vm_state'] == "active":
                    self.dragon_api.create_resource(context,
                                                    instance['uuid'],
                                                    instance['display_name'],
                                                    CONF.dr_instance)
                    resource_info = {
                        'id': instance['uuid'],
                        'resource_type_id': CONF.dr_instance}
                    self._resources_to_protect.append(resource_info)
                else:
                    raise exception.DROrchestratorInstanceNotActive()

            elif resource_type == "Volume":
                volume = self.volume_api.get(context, resource_id)
                if volume['status'] in PROTECTABLE_STATES:
                    self.dragon_api.create_resource(context,
                                                    volume['id'],
                                                    volume['display_name'],
                                                    CONF.dr_volume)
                    resource_info = {
                        'id': volume['id'],
                        'resource_type_id': CONF.dr_volume,
                        'volume_type': volume['volume_type_id']}

                    self._resources_to_protect.append(resource_info)
                else:
                    raise exception.DROrchestratorVolumeNotAvailable()
            else:
                LOG.debug("Resource type unknown or not supported.")
                raise exception.DROrchestratorUnknownResourceType()

        else:
            LOG.debug("There is no network capacity to protect more "
                      "VMs/Volumes.")
            raise exception.DROrchestratorNoNetworkCapacity()
        

    # API offered to fault detection (FT) 
    def recover(self, context, datacenter):
        """ Recover all the VMs/Volumes protected in DC: datacenter.
        """
        LOG.debug("Recovering datacenter: %s", datacenter)

        for policy in self._get_policies_for_datacenter(datacenter):
            container_to_recover = \
                  self.dragon_api.recovery_list_policy_executions(context,
                                                                  policy)
            self.dragon_api.recover(context, container_to_recover[0]["id"])


