# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019/10/15 15:45
import re
import socket

from watchdog.events import PatternMatchingEventHandler

from util import ip_check, ConnectionException, LOG

from fabric import Connection
from paramiko import SSHException
from paramiko.ssh_exception import (
    NoValidConnectionsError, AuthenticationException, )


class SyncEventHandler(PatternMatchingEventHandler):
    """Sync src to dst"""

    def __init__(self, LOG, source, destinations, patterns=None,
                 ignore_patterns=None, ignore_directories=False):
        """"""
        super(SyncEventHandler, self).__init__(
                patterns, ignore_patterns, ignore_directories,
                case_sensitive=True)
        if not isinstance(destinations, list):
            raise TypeError('dst must be dict')
        for dst in destinations:
            if dst.keys() != {'ip', 'port', 'user', 'password', 'path'}:
                raise KeyError("host keys must be {'ip', 'port', 'user', "
                               "'password', 'path'}")
            if not ip_check(dst['ip']):
                raise ConnectionException('ip error')
            # 测试连接是否可用
            with Connection(host=dst['ip'], port=dst['port'], user=dst['user'],
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
    - ip: 192.168.8.150
      user: root
      password: pwd
      port: '22'
      path: /root/NGD_HKBANK_version/
    patterns: null
    ignore_patterns:
      - ".idea/*"
      - ".idea\\\\*"
      - "py_.*"
    ignore_directories: false
  - source: E:\\PycharmProjects\\NGD_CEPH_version
    destinations:
      - ip: 192.168.8.150
        user: root
        password: joker
        port: '22'
        path: /root/NGD_CEPH_version/
    patterns: null
    ignore_patterns:
      - ".idea/*"
      - ".idea\\\\*"
      - "py_.*"
    ignore_directories: false
    """
        return template_yaml % context

    def dispatch(self, event):
        src_ignore = filter(lambda p: re.search(p, event.src_path),
                            self.ignore_patterns)
        if hasattr(event, "dest_path"):
            dest_ignore = filter(lambda p: re.search(p, event.dest_path),
                                 self.ignore_patterns)
        else:
            dest_ignore = []
        ignore = [i for i in src_ignore] + [i for i in dest_ignore]
        if ignore:
            return
        else:
            super(SyncEventHandler, self).dispatch(event)

    def on_any_event(self, event):
        """
        TODO: 报警系统
        """
        super(SyncEventHandler, self).on_any_event(event)

    def on_created(self, event):
        super(SyncEventHandler, self).on_created(event)
        self.LOG.warning('Create: %s, event: %s' % (
            event.src_path, event.__dict__))

        for dst in self.dests:
            """
            TODO: 上传创建的新文件到目标主机
            """

    def on_moved(self, event):
        super(SyncEventHandler, self).on_moved(event)
        self.LOG.warning('Move: %s to %s, event: %s' % (
            event.src_path, event.dest_path, event.__dict__))

    def on_modified(self, event):
        super(SyncEventHandler, self).on_modified(event)
        if event.is_directory:
            return
        self.LOG.warning('Modified: %s, event: %s' % (
            event.src_path, event.__dict__))

    def on_deleted(self, event):
        super(SyncEventHandler, self).on_deleted(event)
        self.LOG.warning('Deleted: %s, event: %s' % (
            event.src_path, event.__dict__))


