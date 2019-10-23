# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019/10/15 15:45
import re
import socket

from watchdog.events import RegexMatchingEventHandler
from watchdog.utils import unicode_paths, has_attribute

from util import ip_check, ConnectionException, get_dest_path

from fabric import Connection
from paramiko import SSHException
from paramiko.ssh_exception import (
    NoValidConnectionsError, AuthenticationException, )


class SyncEventHandler(RegexMatchingEventHandler):
    """Sync src to dst"""

    def __init__(self, LOG, source, destinations, regexes=None,
                 ignore_regexes=[], ignore_directories=False,
                 case_sensitive=True):
        """"""
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
            if not ip_check(dst['host']):
                raise ConnectionException('host error')
            # 测试连接是否可用
            with Connection(host=dst['host'], port=dst['port'], user=dst['user'],
                            connect_kwargs={'password': dst['password']},
                            connect_timeout=30) as c:
                try:
                    # 测试参数可用
                    c.run('hostname', hide=True)
                except (AuthenticationException, NoValidConnectionsError,
                        socket.timeout, SSHException, socket.error) as e:
                    raise ConnectionException(e)
        self.src = source
        self.dests = destinations
        self.LOG = LOG

    @classmethod
    def generate_yaml(cls):
        context = dict(module_name=cls.__module__, klass_name=cls.__name__)
        template_yaml = """
LOG_Level: WARN
Sync:
  - source: E:\\PycharmProjects\\NGD_HKBANK_version
    destinations:
    - host: 192.168.8.150
      user: root
      password: pwd
      port: '22'
      path: /root/NGD_HKBANK_version/
    # 正则匹配规则
    regexes:
      - .*
    ignore_regexes:
      - ".idea/*"
      - ".idea\\\\*"
      - "py_.*"
    ignore_directories: false
    case_sensitive: true
  - source: E:\\PycharmProjects\\NGD_CEPH_version
    destinations:
      - host: 192.168.8.150
        user: root
        password: joker
        port: '22'
        path: /root/NGD_CEPH_version/
    regexes:
      - .*
    ignore_regexes:
      - ".idea/*"
      - ".idea\\\\*"
      - "py_"
    ignore_directories: false
    case_sensitive: true
    """
        return template_yaml % context

    def on_any_event(self, event):
        """
        TODO: 报警系统
        """
        super().on_any_event(event)

    def on_created(self, event):
        super().on_created(event)
        self.LOG.warning(f'Create: {event.src_path}')

        for dst in self.dests:
            dst_path = get_dest_path(self.src, event.src_path, dst['path'])
            with Connection(host=dst['host'], port=dst['port'],
                            user=dst['user'],
                            connect_kwargs={'password': dst['password']},
                            connect_timeout=30) as c:
                try:
                    # unix command
                    if dst_path.startswith('/'):
                        if event.is_directory:
                            self.LOG.warning(f'{dst["host"]}: mkdir -p {dst_path}')
                            c.run(f'mkdir -p {dst_path}')
                        else:
                            self.LOG.warning(f'put {event.src_path} to {dst_path}')
                            c.put(event.src_path, dst_path)
                    else:
                        if event.is_directory:
                            # TODO: windows command
                            pass
                        else:
                            c.put(event.src_path, dst_path)
                except Exception as e:
                    self.LOG.warning(e)
                        
    def on_moved(self, event):
        super().on_moved(event)
        self.LOG.warning(f'Move: {event.src_path} to {event.dest_path}')
        if event.is_directory:
            pass

    def on_modified(self, event):
        super().on_modified(event)
        if event.is_directory:
            return
        self.LOG.warning(f'Modified: {event.src_path}')

    def on_deleted(self, event):
        super().on_deleted(event)
        self.LOG.warning(f'Deleted: {event.src_path}')


