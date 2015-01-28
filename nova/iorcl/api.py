"""Handles all requests to the iorcl service."""

from oslo.config import cfg
from oslo import messaging

from nova import baserpc
from nova.iorcl import manager
from nova.iorcl import rpcapi
from nova.i18n import _
from nova.openstack.common import log as logging
from nova import utils

conductor_opts = [
    cfg.BoolOpt('use_local',
                default=False,
                help='Perform nova-iorcl operations locally'),
    cfg.StrOpt('topic',
               default='iorcl',
               help='The topic on which iorcl nodes listen'),
    cfg.StrOpt('manager',
               default='nova.iorcl.manager.IORCLManager',
               help='Full class name for the Manager for iorcl'),
    cfg.IntOpt('workers',
               help='Number of workers for OpenStack IORCL service. '
                    'The default will be the number of CPUs available.')
]
iorcl_group = cfg.OptGroup(name='iorcl',
                               title='IORCL Options')
CONF = cfg.CONF
CONF.register_group(iorcl_group)
CONF.register_opts(iorcl_opts, iorcl_group)

LOG = logging.getLogger(__name__)


class LocalAPI(object):
    """A local version of the iorcl API that works
    locally instead of via RPC.
    """

    def __init__(self):
        # TODO(danms): This needs to be something more generic for
        # other/future users of this sort of functionality.
        self._manager = utils.ExceptionHelper(manager.IORCLManager())

    def wait_until_ready(self, context, *args, **kwargs):
        # nothing to wait for in the local case.
        pass


class LocalComputeTaskAPI(object):
    def __init__(self):
        # TODO(danms): This needs to be something more generic for
        # other/future users of this sort of functionality.
        self._manager = utils.ExceptionHelper(
                manager.ComputeTaskManager())

    def io_attach_volume(self, context, instance, volume_id):
        self._manager.io_attach_volume(context, instance, volume_id)

    def io_detach_volume(self, context, instance, volume_id):
        self._manager.io_detach_volume(context, instance, volume_id)

    def io_attach_interface(self, context, instance, vif):
        self._manager.io_attach_interface(context, instance, vif)

    def io_detach_interface(self, context, instance, vif):
        self._manager.io_detach_interface(context, instance, vif)

    def io_reset_guest(self, context, instance):
        self._manager.io_reset_guest(context, instance)



class API(LocalAPI):
    """IORCL API that works via RPC to the IORCLManager."""

    def __init__(self):
        self._manager = rpcapi.IORCLAPI()
        self.base_rpcapi = baserpc.BaseAPI(topic=CONF.iorcl.topic)

    def wait_until_ready(self, context, early_timeout=10, early_attempts=10):
        '''Wait until a iorcl service is up and running.

        This method calls the remote ping() method on the iorcl topic until
        it gets a response.  It starts with a shorter timeout in the loop
        (early_timeout) up to early_attempts number of tries.  It then drops
        back to the globally configured timeout for rpc calls for each retry.
        '''
        attempt = 0
        timeout = early_timeout
        # if we show the timeout message, make sure we show a similar
        # message saying that everything is now working to avoid
        # confusion
        has_timedout = False
        while True:
            # NOTE(danms): Try ten times with a short timeout, and then punt
            # to the configured RPC timeout after that
            if attempt == early_attempts:
                timeout = None
            attempt += 1

            # NOTE(russellb): This is running during service startup. If we
            # allow an exception to be raised, the service will shut down.
            # This may fail the first time around if nova-conductor wasn't
            # running when this service started.
            try:
                self.base_rpcapi.ping(context, '1.21 GigaWatts',
                                      timeout=timeout)
                if has_timedout:
                    LOG.info(_('nova-iorcl connection '
                               'established successfully'))
                break
            except messaging.MessagingTimeout:
                has_timedout = True
                LOG.warning(_('Timed out waiting for nova-iorcl.  '
                              'Is it running? Or did this service start '
                              'before nova-iorcl?  '
                              'Reattempting establishment of '
                              'nova-iorcl connection...'))



class ComputeTaskAPI(object):
    """ComputeTask API that queues up compute tasks for nova-iorcl."""

    def __init__(self):
        self.iorcl_compute_rpcapi = rpcapi.ComputeTaskAPI()

    def io_attach_volume(self, context, instance, volume_id):
        return self.iorcl_compute_rpcapi.io_attach_volume(context,
                                                          instance,
                                                          volume_id)

    def io_detach_volume(self, context, instance, volume_id):
        return self.iorcl_compute_rpcapi.io_detach_volume(context,
                                                          instance,
                                                          volume_id)

    def io_attach_interface(self, context, instance, vif):
        return self.iorcl_compute_rpcapi.io_attach_interface(context,
                                                             instance,
                                                             vif)

    def io_detach_interface(self, context, instance, vif):
        return self.iorcl_compute_rpcapi.io_detach_interface(context,
                                                             instance,
                                                             vif)

    def io_reset_guest(self, context, instance):
        return self.iorcl_compute_rpcapi.io_reset_guest(context,
                                                        instance)

