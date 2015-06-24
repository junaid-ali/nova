"""Client side of the dr_orchestrator RPC API."""

from oslo.config import cfg
from oslo import messaging

from nova.objects import base as objects_base
from nova.openstack.common import jsonutils
from nova import rpc

CONF = cfg.CONF

rpcapi_cap_opt = cfg.StrOpt('dr_orchestrator',
        help='Set a version cap for messages sent to dr_orchestrator services')
CONF.register_opt(rpcapi_cap_opt, 'upgrade_levels')


class OrchestratorAPI(object):
    """Client side of the dr_orchestrator RPC API

    API version history:

    * 1.0 - Initial version.

    Juno supports message version 2.0.  So, any changes to
    existing methods in 2.x after that point should be done such
    that they can handle the version_cap being set to 2.0.

    """

    VERSION_ALIASES = {
        'juno': '2.0',
    }

    def __init__(self):
        super(OrchestratorAPI, self).__init__()
        target = messaging.Target(topic=CONF.dr_orchestrator.topic,
                                  version='2.0')
        version_cap = self.VERSION_ALIASES.get(
                                CONF.upgrade_levels.dr_orchestrator,
                                CONF.upgrade_levels.dr_orchestrator)
        serializer = objects_base.NovaObjectSerializer()
        self.client = rpc.get_client(target,
                                     version_cap=version_cap,
                                     serializer=serializer)


    def protect(self, context, resource_id, resource_type):
        cctxt = self.client.prepare(version='2.0')
        return cctxt.call(context, 'protect',
                          resource_id=resource_id,
                          resource_type=resource_type)

    def recover(self, context, datacenter):
        cctxt = self.client.prepare(version='2.0')
        return cctxt.cast(context, 'recover',
                          datacenter=datacenter)
