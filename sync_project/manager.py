# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019/10/15 15:05
"""The Module Has Been Build for start sync server"""
import argparse
import atexit
import os
import re
import signal
import socket
import sys
import time
from pathlib import Path

from fabric import Connection
from paramiko import AuthenticationException
from paramiko.ssh_exception import NoValidConnectionsError, SSHException
from watchdog.observers import Observer

from _sync import SyncEventHandler
from conf import CONF, LOG, load_conf
from util import generate_yaml, ConnectionException, put_one


base_path = Path(__file__).parent
parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="一个基于watchdog和ssh的同步本地项目到远程linux服务器的工具",
        epilog="""
e.g:\n
生成配置文件模板:\n
    Windows:\n
        .\\virtenv\\Scripts\\python.exe manager.py util --conf_gen\n
    unix:\n
        ./virtenv/bin/python manager.py util --conf_gen\n
推送一次项目到远程主机:\n
    Windows:\n
        .\\virtenv\\Scripts\\python.exe manager.py util --push\n
    unix:\n
        ./virtenv/bin/python manager.py util --push\n
debug运行模式:
记录日志到日志文件时, 也会在当前命令行显示日志, 同时会抛出所有异常:\n
    Windows:\n
        .\\virtenv\\Scripts\\python.exe manager.py run --debug\n
    unix:\n
        ./virtenv/bin/python manager.py run --debug\n
normal运行模式:\n
不会在当前命令行显示日志, 而且会捕获所有异常, 以便服务继续运行
    Windows:\n
        .\\virtenv\\Scripts\\pythonw.exe manager.py run\n
    unix:\n
        ./virtenv/bin/python manager.py run\n
        """
)
subcmd = parser.add_subparsers(title='subcmd')
run_mode = subcmd.add_parser('run', help='run mode, default: normal')
run_mode.add_argument('mode', nargs='?', default='normal',
                      help='run mode: normal or debug')
util_cmd = subcmd.add_parser('util',
                             help='push once project or generate conf file')
util_cmd.add_argument('--push', action='store_true',
                      help='push once project')
conf_def_path = (base_path / 'sync_object.yaml').absolute()
util_cmd.add_argument('--conf_gen', action='store_const', const=conf_def_path,
                      help=f'Generate the configuration template file, '
                           f'default path: {conf_def_path}')
args = parser.parse_args()

observer_instances = []


def exit_bos(signum=None, frame=None):
    LOG().error(f'signum:{signum}, frame:{frame}')
    for ob_instance in observer_instances:
        ob_instance.stop()
        ob_instance.join()
    sys.exit(1)


if __name__ == '__main__':
    if getattr(args, 'mode', None) in ('normal', 'debug'):
        log = LOG()
        if args.mode == 'debug':
            load_conf(DebugMode=True, LogLevel='DEBUG')
            del log
            del CONF
            from conf import CONF
            log = LOG()
        if CONF.get('Sync'):

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
                while any(ob.is_alive() for ob in observer_instances):
                    time.sleep(1)
                for ob_instance in observer_instances:
                    ob_instance.stop()
                    ob_instance.join()
                log.error('sync exit')
            except Exception as e:
                log.error(e)
                log.error('system exit')
                for ob_instance in observer_instances:
                    ob_instance.stop()
                    ob_instance.join()
        else:
            log.error('conf not found Sync')
    elif getattr(args, 'push', False):

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
                            ps = p.absolute().__str__()
                            if any(re.match(r, ps) for r in ignore_regexes):
                                continue
                            else:
                                if p.is_file():
                                    put_one(src, ps, dst['path'], c)
                                elif p.is_dir():
                                    for b, d, f in os.walk(ps):
                                        for fs in f:
                                            src_ = Path(b) / fs
                                            src_ = src_.__str__()
                                            put_one(src, src_, dst['path'], c)
                    except (AuthenticationException, NoValidConnectionsError,
                            socket.timeout, SSHException, socket.error) as e:
                        LOG().error(e)
                        raise ConnectionException(e)
    elif getattr(args, 'conf_gen', None):
        yaml_path, template_yaml = generate_yaml(args.conf_gen)
        LOG().info(f'配置模板文件路径:  {yaml_path}\n'
                   f'配置模板文件内容:\n{template_yaml}')
    else:
        parser.print_help()
