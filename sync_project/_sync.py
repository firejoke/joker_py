# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019/10/15 15:45
import os
import re
import shutil
import socket
from pathlib import Path

from invoke import run
from watchdog.events import RegexMatchingEventHandler
from watchdog.utils import unicode_paths, has_attribute

from fabric import Connection
from paramiko import SSHException
from paramiko.ssh_exception import (
    NoValidConnectionsError, AuthenticationException, )

from util import (
    ip_check, ConnectionException, get_dest_path, put_one, is_continue, )
from conf import LOG


class SyncEventHandler(RegexMatchingEventHandler):
    """Sync src to dst"""
    log = LOG()

    def __init__(self, source, destinations, regexes=None,
                 ignore_regexes=[], ignore_directories=False,
                 case_sensitive=True):
        if not regexes:
            regexes = [r'.*']

        super().__init__(
                regexes, ignore_regexes, ignore_directories, case_sensitive)
        if not isinstance(destinations, list):
            raise TypeError('dst must be list')
        for dst in destinations:
            if dst.keys() != {'host', 'port', 'user', 'password', 'path'}:
                raise KeyError("host keys must be {'host', 'port', 'user', "
                               "'password', 'path'}")
            if dst['host'] in('0.0.0.0', '127.0.0.1') or \
               dst['host'].lower() == 'localhost':
                self.run = run
            else:
                assert ip_check(dst['host']), 'host error'
                # 测试连接是否可用
                with Connection(host=dst['host'], port=dst['port'],
                                user=dst['user'],
                                connect_kwargs={'password': dst['password']},
                                connect_timeout=30) as c:
                    try:
                        # 测试参数可用
                        c.run('hostname', hide=True, warn=True)
                        self.c = c
                        self.run = c.run
                    except (AuthenticationException, NoValidConnectionsError,
                            socket.timeout, SSHException, socket.error) as e:
                        self.log.error(e)
                        raise ConnectionException(e)
        self.src = source
        self.dests = destinations

    def on_created(self, event):
        super().on_created(event)
        self.log.info(f'Create: {event.src_path}')

        for dst in self.dests:
            if event.is_directory:
                if Path(event.src_path).stat().st_size == 0:
                    dst_path = get_dest_path(self.src, event.src_path,
                                             dst['path'])
                    self.log.info(f'mkdir {dst_path}')
                    if hasattr(self, 'c'):
                        res = self.c.run(f'mkdir -p {dst_path}', hide=True,
                                         warn=True)
                        if res.stdout:
                            self.log.info(res.stdout)
                        if res.stderr:
                            self.log.error(res.stderr)
                    else:
                        os.makedirs(dst_path)
                else:
                    for b, d, f in os.walk(event.src_path):
                        for fs in f:
                            src_ = Path(b) / fs
                            src_ = src_.__str__()
                            if hasattr(self, 'c'):
                                put_one(self.src, src_, dst['path'], self.c)
                            else:
                                dst_path = get_dest_path(self.src, src_,
                                                         dst['path'])
                                os.makedirs(Path(dst_path).parent)
                                self.log.info(f'cp {src_} to {dst_path}')
                                shutil.copy(src_, dst_path)
            else:
                if hasattr(self, 'c'):
                    put_one(self.src, event.src_path, dst['path'], self.c)
                else:
                    dst_path = get_dest_path(self.src, event.src_path,
                                             dst['path'])
                    os.makedirs(Path(dst_path).parent)
                    self.log.info(f'cp {event.src_path} to {dst_path}')
                    shutil.copy(event.src_path, dst_path)

    @is_continue
    def on_moved(self, event):
        super().on_moved(event)
        self.log.info(f'Move: {event.src_path} to {event.dest_path}')
        for dst in self.dests:
            dest_src_path = get_dest_path(self.src, event.src_path,
                                          dst['path'])
            dest_dst_path = get_dest_path(self.src, event.dest_path,
                                          dst['path'])
            if event.is_directory and Path(event.src_path).stat().st_size > 0:
                self.log.warning(f'{event.src_path} not empty, size: '
                                 f'{Path(event.src_path).stat().st_size}')
            else:
                if hasattr(self, 'c'):
                    self.log.info(f'{self.c.host}: mv {dest_src_path} to'
                                  f' {dest_dst_path}')
                    res = self.c.run(
                            f'mkdir -p {os.path.dirname(dest_dst_path)}',
                            hide=True, warn=True)
                    if res.stdout:
                        self.log.info(res.stdout)
                    if res.stderr:
                        self.log.error(res.stderr)
                    self.c.run(f'mv {dest_src_path} {dest_dst_path}',
                               hide=True, warn=True)
                else:
                    self.log.info(f'mv {dest_src_path} to {dest_dst_path}')
                    os.makedirs(Path(dest_dst_path).parent)
                    shutil.move(dest_src_path, dest_dst_path)

    def on_modified(self, event):
        super().on_modified(event)
        self.log.info(f'Modified: {event.src_path}')
        if event.is_directory:
            return
        else:
            for dst in self.dests:
                if hasattr(self, 'c'):
                    put_one(self.src, event.src_path, dst['path'], self.c)
                else:
                    dst_path = get_dest_path(self.src, event.src_path,
                                             dst['path'])
                    self.log.info(f'cp {event.src_path} to {dst_path}')
                    shutil.copy(event.src_path, dst_path)

    def on_deleted(self, event):
        super().on_deleted(event)
        self.log.info(f'Deleted: {event.src_path}')

        for dst in self.dests:
            dst_path = get_dest_path(self.src, event.src_path, dst['path'])
            self.log.info(f'rm -rf {dst_path}')
            if hasattr(self, 'c'):
                if dst_path.startswith('/'):
                    # unix command
                    self.log.info(
                        f'{dst["host"]}: rm -rf {dst_path}')
                    res = self.c.run(f'rm -rf {dst_path}', hide=True, warn=True)
                    if res.stdout:
                        self.log.info(res.stdout)
                    if res.stderr:
                        self.log.error(res.stderr)
                else:
                    # TODO: windows command
                    self.c.run('')
            else:
                if event.is_directory:
                    os.removedirs(dst_path)
                else:
                    os.remove(dst_path)


