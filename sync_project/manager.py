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
from conf import CONF, logger, load_conf
from util import generate_yaml, ConnectionException, put_one


base_path = Path(__file__).parent
parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="一个基于watchdog和ssh的同步本地项目到远程linux服务器的python脚本，python>=3.6.8",
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
        .\\virtenv\\Scripts\\python.exe manager.py run debug\n
    unix:\n
        ./virtenv/bin/python manager.py run debug\n
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


def ending(signum=None, frame=None):
    logger.warning(f'signum:{signum}, frame:{frame}')
    for ob_instance in observer_instances:
        ob_instance.stop()
        ob_instance.join()
    sys.exit(1)


if __name__ == '__main__':
    if getattr(args, 'mode', None) in ('normal', 'debug'):
        if args.mode == 'debug':
            load_conf(DebugMode=True, LogLevel='DEBUG')
        if CONF.get('Sync'):

            for sd_instance in CONF['Sync']:
                observer = Observer()
                observer.schedule(SyncEventHandler(**sd_instance),
                                  sd_instance['source'], recursive=True)
                observer.start()
                observer_instances.append(observer)
            atexit.register(ending)
            signal.signal(signal.SIGINT, ending)
            signal.signal(signal.SIGTERM, ending)
            # windows
            signal.signal(signal.SIGBREAK, ending)
            try:
                while any(ob.is_alive() for ob in observer_instances):
                    time.sleep(1)
                for ob_instance in observer_instances:
                    ob_instance.stop()
                    ob_instance.join()
                logger.error('All processes exit')
            except Exception as e:
                logger.error(e)
                for ob_instance in observer_instances:
                    ob_instance.stop()
                    ob_instance.join()
        else:
            logger.error('conf not found Sync')
    elif getattr(args, 'push', False):
        load_conf(LogOut='terminal')

        time_list = {}
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
                        start_time = time.time()
                        now_size = 0
                        full_size = Path(src).stat().st_size
                        for p in Path(src).iterdir():
                            ps = p.absolute().__str__()
                            if any(re.match(r, ps) for r in ignore_regexes):
                                continue
                            else:
                                if p.is_file():
                                    size = put_one(src, ps, dst['path'], c)
                                    now_size += size
                                    logger.info(
                                        f'{dst["path"]}:progress======>>'
                                        f'{now_size / full_size * 100}%')
                                elif p.is_dir():
                                    for b, d, f in os.walk(ps):
                                        for fs in f:
                                            src_ = Path(b) / fs
                                            src_ = src_.__str__()
                                            size = put_one(src, src_,
                                                           dst['path'], c)
                                            now_size += size
                                            logger.info(
                                                f'{dst["path"]}:'
                                                f'progress======>>'
                                                f'{now_size / full_size * 100}%'
                                            )
                        time_list[dst['path']] = time.time() - start_time
                    except (AuthenticationException, NoValidConnectionsError,
                            socket.timeout, SSHException, socket.error) as e:
                        logger.error(e)
                        raise ConnectionException(e)
        if time_list:
            logger.info(f'elapsed time:\n{time_list}')
    elif getattr(args, 'conf_gen', None):
        yaml_path, template_yaml = generate_yaml(args.conf_gen)
        logger.info(f'配置模板文件路径:  {yaml_path}\n'
                    f'配置模板文件内容:\n{template_yaml}')
    else:
        parser.print_help()
