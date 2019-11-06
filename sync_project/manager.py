# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019/10/15 15:05
"""The Module Has Been Build for start sync server"""
import argparse
import atexit
import re
import signal
import socket
import sys
import time
import uuid
from pathlib import Path

from fabric import Connection
from paramiko import AuthenticationException
from paramiko.ssh_exception import NoValidConnectionsError, SSHException
from watchdog.observers import Observer

from conf import CONF, LOG, load_conf


parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="一个基于watchdog和ssh的同步本地项目到远程服务器的工具",
        epilog="""
e.g:\n
生成配置文件模板:\n
    Windows:\n
        .\\virtenv\\Scripts\\python manager.py --conf_gen\n
    unix:\n
        ./virtenv/bin/python manager.py --conf_gen\n
手动推送到远程主机:\n
    Windows:\n
        .\\virtenv\\Scripts\\python manager.py --put\n
    unix:\n
        ./virtenv/bin/python manager.py --put\n
debug模式:\n
    Windows:\n
        .\\virtenv\\Scripts\\python manager.py --debug\n
    unix:\n
        ./virtenv/bin/python manager.py --debug\n
start:\n
    Windows:\n
        .\\virtenv\\Scripts\\python manager.py --start\n
    unix:\n
        ./virtenv/bin/python manager.py --start\n
        """
)
parser.add_argument('--conf_gen', default=0,
                    help='生成sync_project.yaml配置模板文件')
parser.add_argument('--put', default=0, help='')
parser.add_argument('--debug', default=0, help='debug mode')
parser.add_argument('--start', default=0, help='start run')
args = parser.parse_args()

observer_instances = []


def exit_bos(signum=None, frame=None):
    LOG().error('sync server exit')
    for ob_instance in observer_instances:
        ob_instance.stop()
        ob_instance.join()
    sys.exit(1)


if __name__ == '__main__':
    if args.debug or args.start:
        if args.debug:
            load_conf(LOG_Level='debug')
        if CONF.get('Sync'):
            from _sync import SyncEventHandler

            for sd_instance in CONF['Sync']:
                observer = Observer()
                observer.schedule(SyncEventHandler(**sd_instance),
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
                LOG().warning('systemexit sync')
                for ob_instance in observer_instances:
                    ob_instance.stop()
                    ob_instance.join()
        else:
            LOG().warning('conf not found Sync')
    elif args.put:
        from util import ConnectionException, put_one

        for sd_instance in CONF['Sync']:
            src = sd_instance['source']
            regexes = sd_instance['regexes']
            ignore_regexes = sd_instance['ignore_regexes']
            dsts = sd_instance['destinations']
            for dst in dsts:
                with Connection(host=dst['host'], port=dst['port'],
                                user=dst['user'],
                                connect_kwargs={'password': dst['password']},
                                connect_timeout=30) as c:
                    try:
                        c.run('hostname', hide=True)
                        for p in Path(src).iterdir():
                            p = p.absolute().__str__()
                            if any(re.match(r, p) for r in ignore_regexes):
                                continue
                            else:
                                put_one(src, p, dst['path'], c)
                    except (AuthenticationException, NoValidConnectionsError,
                            socket.timeout, SSHException, socket.error) as e:
                        raise ConnectionException(e)
    elif args.conf_gen:
        from util import generate_yaml

        yaml_path, template_yaml = generate_yaml()
        LOG().info(f'模板配置文件路径:\n{yaml_path}\n'
                   f'模板配置文件内容:\n{template_yaml}')
    else:
        parser.print_help()
