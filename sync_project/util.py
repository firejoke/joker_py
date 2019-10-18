# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019/10/16 11:50
import os
import pathlib
import sys

import yaml

from Colorer_log import LOG, INFO, WARN, ERROR, DEBUG, set_log_handler


class ConnectionException(Exception):
    """connection error """


def load_conf():
    try:
        conf_path = pathlib.Path(__file__).parent.joinpath('sync_project.yaml')
        with open(conf_path, 'r') as f:
            conf = yaml.safe_load(f)
        if isinstance(conf['Sync'], list):
            if conf.get('LOG_Level') in ('info', 'INFO'):
                LOG.setLevel(INFO)
                LOG.info('LOG level change to info')
            elif conf.get('LOG_Level') in ('warn', 'WARN',
                                           'warning', 'WARNING'):
                LOG.setLevel(WARN)
                LOG.warning('LOG level change to warn')
            elif conf.get('LOG_Level') in ('error', 'ERROR'):
                LOG.setLevel(ERROR)
            elif conf.get('LOG_Level') in ('debug', 'DEBUG'):
                LOG.setLevel(DEBUG)
                LOG.debug('LOG level change to debug')
            elif conf.get('LOG_Level'):
                LOG.error('LOG_Level value error')
            return conf
        else:
            LOG.error('type error: Sync require list')
            sys.exit(1)
    except IOError:
        LOG.error('not found config: ./sync_project.yaml')
        sys.exit(1)
    except yaml.YAMLError as e:
        LOG.error("yaml syntax error: " + e.__str__())
        sys.exit(1)


def ip_check(ip_address):
    try:
        import ipaddress

        try:
            ipaddress.ip_address(ip_address)
            return True
        except (ValueError, ipaddress.AddressValueError):
            return False
    except ImportError:
        from socket import error

        try:
            from socket import inet_pton, AF_INET

            inet_pton(AF_INET, ip_address)
        except ImportError:
            try:
                from socket import inet_aton

                inet_aton(ip_address)
            except error:
                return False
            else:
                return ip_address.count('.') == 3
        except error:
            return False
        else:
            return True


def get_dest_path(root_path: str, absolute_path: str, dest_base_path: str):
    relative_path = absolute_path[len(root_path):]
    if relative_path.startswith(('\\', '/')):
        relative_path = relative_path[1:]
    if dest_base_path.startswith('/'):
        relative_path = relative_path.replace('\\', '/')
        dest_path = os.path.join(dest_base_path, relative_path
                                 ).replace('\\', '/')
    # windows: A~Z:\xxxxxxx
    elif dest_base_path.startswith(tuple([chr(i) for i in range(65, 91)])):
        relative_path = relative_path.replace('/', '\\')
        dest_path = os.path.join(dest_base_path, relative_path
                                 ).replace('/', '\\')
    else:
        raise ValueError('不支持该路径格式: %s' % dest_base_path)
    return dest_path
