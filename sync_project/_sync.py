# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019/10/15 15:45
import os
import shutil
import socket
from copy import copy, deepcopy
from pathlib import Path

from watchdog.events import RegexMatchingEventHandler

from fabric import Connection
from paramiko import SSHException
from paramiko.ssh_exception import (
    NoValidConnectionsError, AuthenticationException, )

from util import ip_check, get_dest_path, put_one, enforce
from conf import CONF, logger


class SyncEventHandler(RegexMatchingEventHandler):
    """Sync src to dst"""

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
            if set(dst.keys()) - {
                'path', 'host', 'port', 'user', 'password', 'pkey',
                'key_filename', 'timeout', 'allow_agent', 'look_for_keys',
                'compress', 'sock', 'gss_auth', 'gss_kex', 'gss_deleg_creds',
                'gss_host', 'banner_timeout', 'auth_timeout',
                'gss_trust_dns', 'passphrase', 'disabled_algorithms'
            }:
                raise KeyError(
                    """host keys must in {
                'path', 'host', 'port', 'user', 'password', 'pkey',
                'key_filename', 'timeout', 'allow_agent', 'look_for_keys', 
                'compress', 'sock', 'gss_auth', 'gss_kex', 'gss_deleg_creds',
                'gss_host', 'banner_timeout', 'auth_timeout', 
                'gss_trust_dns', 'passphrase', 'disabled_algorithms'
            }""")
            assert dst.get("path", None), "must be a 'path' key"
            if dst['host'] not in('0.0.0.0', '127.0.0.1') and \
               dst['host'].lower() != 'localhost':
                _path = dst.pop("path")
                c = self._create_connection(**dst)
                c.path = _path
                self.remote.append(c)
            else:
                self.local.append(dst)
        self.src = source

    def _create_connection(self, **dst):
        assert ip_check(dst['host']), 'host error'
        with Connection(host=dst.pop('host'), port=dst.pop('port', None),
                        user=dst.pop('user', None), connect_kwargs=dst) as c:
            return c

    def _check_connection(self, connection):
        try:
            connection.run("hostname", hide=True, warn=True)
            return True
        except (AuthenticationException, NoValidConnectionsError,
                    socket.timeout, SSHException, socket.error) as e:
            logger.error(e)
            assert not CONF.get("DebugMode"), e
            return False

    def dispatch(self, event):
        tmp_c = copy(self.remote)
        for c in tmp_c:
            if not self._check_connection(c):
                self.remote.remove(c)
                logger.warning("reconnection")
                _c = self._create_connection(host=c.host, user=c.user,
                                             port=c.port, **c.connect_kwargs)
                _c.path = c.path
                self.remote.append(_c)
        return super(SyncEventHandler, self).dispatch(event)

    @enforce
    def on_created(self, event):
        super().on_created(event)
        logger.info(f'Create: {event.src_path}')

        if event.is_directory:
            if Path(event.src_path).stat().st_size == 0:
                for c in self.remote:
                    dst_path = get_dest_path(self.src, event.src_path,
                                             c.path)
                    logger.info(f'mkdir {dst_path}')
                    res = c.run(f'mkdir -p {dst_path}', hide=True,
                                warn=True)
                    if res.stdout:
                        logger.info(res.stdout)
                    if res.stderr:
                        logger.error(res.stderr)
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
                            logger.info(f'cp {src_} to {dst_path}')
                            shutil.copy(src_, dst_path)
        else:
            for c in self.remote:
                put_one(self.src, event.src_path, c.path, c)
            for l in self.local:
                dst_path = get_dest_path(self.src, event.src_path,
                                         l['path'])
                os.makedirs(Path(dst_path).parent)
                logger.info(f'cp {event.src_path} to {dst_path}')
                shutil.copy(event.src_path, dst_path)

    @enforce
    def on_moved(self, event):
        super().on_moved(event)
        logger.info(f'MOVE: {event.src_path} to {event.dest_path}')
        # if event.is_directory and Path(event.src_path).stat().st_size > 0:
        #     logger.warning(f'{event.src_path} not empty, size: '
        #                      f'{Path(event.src_path).stat().st_size}')
        for c in self.remote:
            dest_src_path = get_dest_path(self.src, event.src_path,
                                          c.path)
            dest_dst_path = get_dest_path(self.src, event.dest_path,
                                          c.path)
            logger.info(f'{c.host}: mv {dest_src_path} to'
                          f' {dest_dst_path}')
            res = c.run(
                    f'mkdir -p {os.path.dirname(dest_dst_path)}',
                    hide=True, warn=True)
            if res.stdout:
                logger.info(res.stdout)
            if res.stderr:
                logger.error(res.stderr)
            res = c.run(f'mv {dest_src_path} {dest_dst_path}',
                        hide=True, warn=True)
            if res.stdout:
                logger.info(res.stdout)
            if res.stderr:
                logger.error(res.stderr)
        for l in self.local:
            dest_src_path = get_dest_path(self.src, event.src_path,
                                          l['path'])
            dest_dst_path = get_dest_path(self.src, event.dest_path,
                                          l['path'])
            logger.info(f'mv {dest_src_path} to {dest_dst_path}')
            os.makedirs(Path(dest_dst_path).parent)
            shutil.move(dest_src_path, dest_dst_path)

    @enforce
    def on_modified(self, event):
        super().on_modified(event)
        logger.info(f'Modified: {event.src_path}')
        if event.is_directory:
            return
        else:
            for c in self.remote:
                put_one(self.src, event.src_path, c.path, c)
            for l in self.local:
                dst_path = get_dest_path(self.src, event.src_path,
                                         l['path'])
                logger.info(f'cp {event.src_path} to {dst_path}')
                shutil.copy(event.src_path, dst_path)

    @enforce
    def on_deleted(self, event):
        super().on_deleted(event)
        logger.info(f'Deleted: {event.src_path}')

        for c in self.remote:
            dst_path = get_dest_path(self.src, event.src_path, c.path)
            if dst_path.startswith('/'):
                # unix command
                logger.info(
                    f'{c.host}: rm -rf {dst_path}')
                res = c.run(f'rm -rf {dst_path}', hide=True, warn=True)
                if res.stdout:
                    logger.info(res.stdout)
                if res.stderr:
                    logger.error(res.stderr)
            else:
                # TODO: windows command
                c.run('')
        for l in self.local:
            dst_path = get_dest_path(self.src, event.src_path, l['path'])
            logger.info(f'rm -rf {dst_path}')
            if event.is_directory:
                os.removedirs(dst_path)
            else:
                os.remove(dst_path)


