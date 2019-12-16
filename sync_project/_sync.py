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
from conf import LOG, INFO


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
        self.remote = []
        self.local = []
        for dst in destinations:
            if dst.keys() != {'host', 'port', 'user', 'password', 'path'}:
                raise KeyError("host keys must be {'host', 'port', 'user', "
                               "'password', 'path'}")
            if dst['host'] not in('0.0.0.0', '127.0.0.1') and \
               dst['host'].lower() != 'localhost':
                c = self._create_connection(dst)
                c.path = dst['path']
                self.remote.append(c)
            self.local.append(dst)
        self.src = source
        self.dests = destinations

    def _create_connection(self, dst):
        assert ip_check(dst['host']), 'host error'
        # 测试连接是否可用
        with Connection(host=dst['host'], port=dst['port'], user=dst['user'],
                        connect_kwargs={'password': dst['password']},
                        connect_timeout=30) as c:
            try:
                # 测试参数可用
                c.run('hostname', hide=True, warn=True)
                return c
            except (AuthenticationException, NoValidConnectionsError,
                    socket.timeout, SSHException, socket.error) as e:
                self.log.error(e)
                if self.log.level == INFO:
                    class C:
                        def __init__(self):
                            self.dst = dst
                            self.path = dst['path']

                        def run(self, cmd, **kwargs):
                            result = object()
                            result.stdout = None
                            result.stderr = e
                            return result
                    return C()
                else:
                    raise ConnectionException(e)

    def dispatch(self, event):
        tmp_c = self.remote
        if tmp_c:
            for c in self.remote:
                if not isinstance(c, Connection):
                    self.remote.remove(c)
                    _c = self._create_connection(c.dst)
                    _c.path = c.path
                    self.remote.append(_c)
        return super(SyncEventHandler, self).dispatch(event)

    def on_created(self, event):
        super().on_created(event)
        self.log.info(f'Create: {event.src_path}')

        if event.is_directory:
            if Path(event.src_path).stat().st_size == 0:
                for c in self.remote:
                    dst_path = get_dest_path(self.src, event.src_path,
                                             c.path)
                    self.log.info(f'mkdir {dst_path}')
                    res = c.run(f'mkdir -p {dst_path}', hide=True,
                                warn=True)
                    if res.stdout:
                        self.log.info(res.stdout)
                    if res.stderr:
                        self.log.error(res.stderr)
                for l in self.local:
                    dst_path = get_dest_path(self.src, event.src_path,
                                             l['path'])
                    os.makedirs(dst_path)
            else:
                for b, d, f in os.walk(event.src_path):
                    for fs in f:
                        src_ = Path(b) / fs
                        src_ = src_.__str__()
                        for c in self.remote:
                            put_one(self.src, src_, c.path, c)
                        for l in self.local:
                            dst_path = get_dest_path(self.src, src_,
                                                     l['path'])
                            os.makedirs(Path(dst_path).parent)
                            self.log.info(f'cp {src_} to {dst_path}')
                            shutil.copy(src_, dst_path)
        else:
            for c in self.remote:
                put_one(self.src, event.src_path, c.path, c)
            for l in self.local:
                dst_path = get_dest_path(self.src, event.src_path,
                                         l['path'])
                os.makedirs(Path(dst_path).parent)
                self.log.info(f'cp {event.src_path} to {dst_path}')
                shutil.copy(event.src_path, dst_path)

    @is_continue
    def on_moved(self, event):
        super().on_moved(event)
        self.log.info(f'MOVE: {event.src_path} to {event.dest_path}')
        # if event.is_directory and Path(event.src_path).stat().st_size > 0:
        #     self.log.warning(f'{event.src_path} not empty, size: '
        #                      f'{Path(event.src_path).stat().st_size}')
        for c in self.remote:
            dest_src_path = get_dest_path(self.src, event.src_path,
                                          c.path)
            dest_dst_path = get_dest_path(self.src, event.dest_path,
                                          c.path)
            self.log.info(f'{c.host}: mv {dest_src_path} to'
                          f' {dest_dst_path}')
            res = c.run(
                    f'mkdir -p {os.path.dirname(dest_dst_path)}',
                    hide=True, warn=True)
            if res.stdout:
                self.log.info(res.stdout)
            if res.stderr:
                self.log.error(res.stderr)
            res = c.run(f'mv {dest_src_path} {dest_dst_path}',
                        hide=True, warn=True)
            if res.stdout:
                self.log.info(res.stdout)
            if res.stderr:
                self.log.error(res.stderr)
        for l in self.local:
            dest_src_path = get_dest_path(self.src, event.src_path,
                                          l['path'])
            dest_dst_path = get_dest_path(self.src, event.dest_path,
                                          l['path'])
            self.log.info(f'mv {dest_src_path} to {dest_dst_path}')
            os.makedirs(Path(dest_dst_path).parent)
            shutil.move(dest_src_path, dest_dst_path)

    def on_modified(self, event):
        super().on_modified(event)
        self.log.info(f'Modified: {event.src_path}')
        if event.is_directory:
            return
        else:
            for c in self.remote:
                put_one(self.src, event.src_path, c.path, c)
            for l in self.local:
                dst_path = get_dest_path(self.src, event.src_path,
                                         l['path'])
                self.log.info(f'cp {event.src_path} to {dst_path}')
                shutil.copy(event.src_path, dst_path)

    def on_deleted(self, event):
        super().on_deleted(event)
        self.log.info(f'Deleted: {event.src_path}')

        for c in self.remote:
            dst_path = get_dest_path(self.src, event.src_path, c.path)
            if dst_path.startswith('/'):
                # unix command
                self.log.info(
                    f'{c.host}: rm -rf {dst_path}')
                res = c.run(f'rm -rf {dst_path}', hide=True, warn=True)
                if res.stdout:
                    self.log.info(res.stdout)
                if res.stderr:
                    self.log.error(res.stderr)
            else:
                # TODO: windows command
                c.run('')
        for l in self.local:
            dst_path = get_dest_path(self.src, event.src_path, l['path'])
            self.log.info(f'rm -rf {dst_path}')
            if event.is_directory:
                os.removedirs(dst_path)
            else:
                os.remove(dst_path)


