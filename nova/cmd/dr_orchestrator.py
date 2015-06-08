"""Starter script for Nova DR-Orchestrator."""

import sys

from oslo.config import cfg

from nova import config
from nova import objects
from nova.openstack.common import log as logging
from nova.openstack.common.report import guru_meditation_report as gmr
from nova import service
from nova import utils
from nova import version

CONF = cfg.CONF
CONF.import_opt('topic', 'nova.dr_orchestrator.api', group='dr_orchestrator')


def main():
    objects.register_all()
    config.parse_args(sys.argv)
    logging.setup("nova")
    utils.monkey_patch()

    gmr.TextGuruMeditation.setup_autorun(version)

    server = service.Service.create(binary='nova-dr_orchestrator',
                                    topic=CONF.dr_orchestrator.topic,
                                    manager=CONF.dr_orchestrator.orchestrator)
    #workers = CONF.dr_orchestrator.workers or utils.cpu_count()
    service.serve(server) #, workers=workers)
    service.wait()
