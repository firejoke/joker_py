# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019/10/15 15:05
"""The Module Has Been Build for start sync server"""
import argparse
import atexit
import signal
import time
import uuid

from watchdog.observers import Observer

from _sync import SyncEventHandler
from util import *


parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="一个基于watchdog和ssh的同步本地项目到远程服务器的工具",
        epilog="""
e.g:
生成配置文件模板:
    Windows:
        .\\virtenv\\Scripts\\python manager.py --conf-gen
    unix:
        ./virtenv/bin/python manager.py --conf-gen
debug模式:
    Windows:
        .\\virtenv\\Scripts\\python manager.py --debug
    unix:
        ./virtenv/bin/python manager.py --debug
        """
)
parser.add_argument('--conf-gen', default=0)
parser.add_argument('--debug', default=0)
args = parser.parse_args()

observer_instances = []


def exit_bos(signum=None, frame=None):
    LOG.error('sync server exit')
    for ob_instance in observer_instances:
        ob_instance.stop()
        ob_instance.join()
    sys.exit(1)


if __name__ == '__main__':
    CONF = load_conf()
    if args.debug:
        LOG = set_log_handler(LOG, 'a', 't')
    else:
        LOG = LOG
    if CONF.get('Sync'):
        for sd_instance in CONF['Sync']:
            observer = Observer()
            observer.schedule(SyncEventHandler(LOG, **sd_instance),
                              sd_instance['source'], recursive=True)
            observer.start()
            observer_instances.append(observer)
        atexit.register(exit_bos)
        signal.signal(signal.SIGINT, exit_bos)
        signal.signal(signal.SIGTERM, exit_bos)
        # windows
        signal.signal(signal.SIGBREAK, exit_bos)
        try:
            while 1:
                time.sleep(1)
        except Exception:
            LOG.warning('systemexit sync')
            for ob_instance in observer_instances:
                ob_instance.stop()
                ob_instance.join()
    else:
        LOG.warning('conf not found Sync')
