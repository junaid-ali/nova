"""Starter script for Nova IORCL."""

import sys

from oslo.config import cfg

from nova import config
from nova import objects
from nova.openstack.common import log as logging
from nova.openstack.common import processutils
from nova.openstack.common.report import guru_meditation_report as gmr
from nova import service
from nova import utils
from nova import version

CONF = cfg.CONF
CONF.import_opt('topic', 'nova.iorcl.api', group='iorcl')


def main():
    config.parse_args(sys.argv)
    logging.setup("nova")
    utils.monkey_patch()
    objects.register_all()

    gmr.TextGuruMeditation.setup_autorun(version)

    server = service.Service.create(binary='nova-iorcl',
                                    topic=CONF.iorcl.topic,
                                    manager=CONF.iorcl.manager)
    workers = CONF.iorcl.workers or processutils.get_worker_count()
    service.serve(server, workers=workers)
    service.wait()
