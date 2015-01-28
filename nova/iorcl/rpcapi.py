"""Client side of the iorcl RPC API."""

from oslo.config import cfg
from oslo import messaging

from nova.objects import base as objects_base
from nova.openstack.common import jsonutils
from nova import rpc

CONF = cfg.CONF

rpcapi_cap_opt = cfg.StrOpt('iorcl',
        help='Set a version cap for messages sent to iorcl services')
CONF.register_opt(rpcapi_cap_opt, 'upgrade_levels')


class IORCLAPI(object):
    """Client side of the iorcl RPC API

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
        super(IORCLAPI, self).__init__()
        target = messaging.Target(topic=CONF.iorcl.topic, version='2.0')
        version_cap = self.VERSION_ALIASES.get(CONF.upgrade_levels.iorcl,
                                               CONF.upgrade_levels.iorcl)
        serializer = objects_base.NovaObjectSerializer()
        self.client = rpc.get_client(target,
                                     version_cap=version_cap,
                                     serializer=serializer)


class ComputeTaskAPI(object):
    """Client side of the iorcl 'compute' namespaced RPC API

    API version history:

    1.0 - Initial version.

    """

    def __init__(self):
        super(ComputeTaskAPI, self).__init__()
        target = messaging.Target(topic=CONF.iorcl.topic,
                                  namespace='compute_task',
                                  version='1.0')
        serializer = objects_base.NovaObjectSerializer()
        self.client = rpc.get_client(target, serializer=serializer)

    def io_attach_volume(self, context, instance, volume_id):
        cctxt = self.client.prepare(version='2.0')
        return cctxt.cast(context, 'io_attach_volume',
                          instance=instance, volume_id=volume_id)

    def io_detach_volume(self, context, instance, volume_id):
        cctxt = self.client.prepare(version='2.0')
        return cctxt.cast(context, 'io_detach_volume',
                          instance=instance, volume_id=volume_id)

    def io_attach_interface(self, context, instance, vif):
        cctxt = self.client.prepare(version='2.0')
        return cctxt.cast(context, 'io_attach_interface',
                          instance=instance, vif=vif)

    def io_detach_interface(self, context, instance, vif):
        cctxt = self.client.prepare(version='2.0')
        return cctxt.cast(context, 'io_detach_interface',
                          instance=instance, vif=vif)

    def io_reset_guest(self, context, instance):
        cctxt = self.client.prepare(version='2.0')
        return cctxt.cast(context, 'io_reset_guest', instance=instance)


