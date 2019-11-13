# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019/10/16 11:50
import functools
import os
from pathlib import Path

from fabric import Connection

from conf import LOG, DebugMode


class ConnectionException(Exception):
    """connection error """


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


def generate_yaml(yaml_path=None):
    if not yaml_path:
        yaml_path = Path(__file__).parent / 'sync_project.yaml'
    template_yaml = """
LOG_Level: WARN
Sync:
  - source: E:\\absolute_path\\root_directory
    destinations:
    - host: host ip
      user: root
      password: pwd
      port: '22'
      path: /dst_absolute_path/dst_root_directory/
    # 正则匹配规则
    regexes:
      - .*
    ignore_regexes:
      - ".*.tmp"
      - ".*.idea*"
      - ".*.svn"
      - ".*.py_.*"
    ignore_directories: false
    case_sensitive: true
  - source: F:\\absolute_path\\root_directory
    destinations:
      - host: host ip
        user: root
        password: pwd
        port: '22'
        path: /dst_absolute_path/dst_root_directory/
    regexes:
      - .*
    ignore_regexes:
      - ".*.tmp"
      - ".*.idea"
      - ".*.svn"
      - ".*.py_.*"
    ignore_directories: false
    case_sensitive: true
    """
    with open(yaml_path, 'w') as f:
        f.write(template_yaml)
    return yaml_path, template_yaml


def is_continue(method):
    """
    当为normal模式时, 不捕获异常, 强制继续运行
    :return:
    """
    log = LOG()

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except Exception as e:
            log.error(e)
            assert not DebugMode(), e
    return wrapper


@is_continue
def put_one(base_src: str, src: str, base_dst: str, con: Connection):
    log = LOG()
    base_src = Path(base_src).absolute().__str__()
    src = Path(src).absolute().__str__()
    assert Path(src).is_file(), 'src file must be file'
    dst_path = get_dest_path(base_src, src, base_dst)
    dst_parent = os.path.split(dst_path)[0]
    if dst_path.startswith('/'):
        con.run(f"mkdir -p {dst_parent}")
    else:
        # TODO: windows command
        pass
    log.info(f'src: {src}')
    log.info(f'pushing to {con.host}: {dst_path}')
    con.put(src, dst_path, preserve_mode=False)
    log.info(f'file size: {os.path.getsize(src) / 1024 / 1024}M')


def get_dest_path(root_path: str, absolute_path: str, dest_base_path: str):
    if os.path.commonprefix([root_path, absolute_path]) != root_path:
        raise ValueError(f'{absolute_path} 没有被包含在 {root_path} 的目录树内')
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
        raise ValueError(f'不支持该路径格式: {dest_base_path}')
    return dest_path


