"""Handles all requests to the iorcl service."""

from oslo.config import cfg
from oslo import messaging

from nova import baserpc
from nova.dr_orchestrator import rpcapi
from nova.i18n import _
from nova.openstack.common import log as logging
from nova import utils

dr_orchestrator_opts = [
    cfg.StrOpt('topic',
               default='dr_orchestrator',
               help='The topic on which dr_orchestrator nodes listen'),
    cfg.StrOpt('orchestrator',
               default='nova.dr_orchestrator.orchestrator.OrchestratorManager',
               help='Full class name for the Manager for dr_orchestrator'),
    cfg.IntOpt('workers',
               help='Number of workers for OpenStack DR-Orchestrator service. '
                    'The default will be the number of CPUs available.')
]

dr_orchestrator_group = cfg.OptGroup(name='dr_orchestrator',
                               title='DR_Orchestrator Options')
CONF = cfg.CONF
CONF.register_group(dr_orchestrator_group)
CONF.register_opts(dr_orchestrator_opts, dr_orchestrator_group)

LOG = logging.getLogger(__name__)


class API(object):
    """IORCL API that works via RPC to the IORCLManager."""

    def __init__(self):
        self._orchestrator = rpcapi.OrchestratorAPI()
        self.base_rpcapi = baserpc.BaseAPI(topic=CONF.dr_orchestrator.topic)

    def wait_until_ready(self, context, early_timeout=10, early_attempts=10):
        '''Wait until a dr_orchestrator service is up and running.

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
                    LOG.info(_('dr-orchestrator connection '
                               'established successfully'))
                break
            except messaging.MessagingTimeout:
                has_timedout = True
                LOG.warning(_('Timed out waiting for nova-iorcl.  '
                              'Is it running? Or did this service start '
                              'before nova-iorcl?  '
                              'Reattempting establishment of '
                              'nova-iorcl connection...'))

    def protect(self, context, resource_id, resource_type):
        """Calls recover RCPI call. 
        """
        self._orchestrator.protect(context, resource_id, resource_type)


    def recover(self, context, datacenter):
        """Calls recover RCPI call. 
        """
        self._orchestrator.recover(context, datacenter)



