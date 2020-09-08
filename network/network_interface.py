# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019-04-24 17:07
"""The Module Has Been Build for manage network interfaces"""

# from __future__ import unicode_literals

import json
import shutil

import netifaces
import os
import platform
import re
import shlex
import sys
import tempfile
import time
import uuid
import argparse
from collections import OrderedDict
from contextlib import contextmanager
from subprocess import Popen, PIPE


PYV = sys.version_info[0]
code_type = str
if PYV == 3:
    import configparser

    class Config(configparser.ConfigParser):

        def optionxform(self, optionstr):
            return optionstr

    code_type = str
elif PYV == 2:
    import ConfigParser

    class Config(ConfigParser.ConfigParser):

        def optionxform(self, optionstr):
            return optionstr

    code_type = unicode

RedHat = ["centos", "redhat"]
Debian = ["ubuntu", "debian"]
# OS_NAME = re.search('(?i)redhat|centos|debian|ubuntu|deepin|kylin',
#                     platform.dist()[0])
OS_NAME = platform.dist()[0]
OS_NAME = OS_NAME.lower() if OS_NAME else None
if OS_NAME in RedHat:
    OS_SERIES = "redhat"
elif OS_NAME in Debian:
    OS_SERIES = "debian"
else:
    if os.path.exists('/etc/redhat-release') or os.path.exists(
            '/lib/systemd/system/firewalld.service'):
        OS_SERIES = 'redhat'
    elif os.path.exists('/etc/debian_version') or os.path.exists(
            '/lib/systemd/system/ufw.service'):
        OS_SERIES = 'debian'
    else:
        raise SystemExit("The system version could not be found")


def ip_check(ip_address):
    """
    :return: True
    :raises
    """
    try:
        import ipaddress

        try:
            ipaddress.ip_address(code_type(ip_address))
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
                return ip_address.count('.') == 3, None
        except error:
            return False
        else:
            return True


def check_networkmanager():
    status = Popen(shlex.split('systemctl status NetworkManager'),
                   stdout=PIPE, stderr=PIPE).communicate()
    if re.search(r"\bActive: .* \((.*)\)", status[0]).group(1) == 'running':
        return True
    else:
        return False


def run_cmd_in_shell(cmd):
    """
    :param cmd: like ("openstack xxxxx", "vestack xxxx", "su xxx")
    :return: bool
    """
    res = Popen(shlex.split(cmd), stdout=PIPE, stderr=PIPE,
                env=os.environ).communicate()
    er_res = re.search(
        r'(?i)\bfailed\s|\berro(r\b|n\b)|\bmiss(\b|ing\b)|'
        r'\bno(t\b|\b).*\bf(ind\b|ound\b)|\bno\s*such\s*file'
        r'|\bno(\b|t\b).*\bexist(s\b|\b)|没有', res[1].decode('utf8'))
    info_er_res = re.search(
        r'(?i)\nfailed\s|\nerro(r\b|n\b)', res[0].decode('utf8'))
    warn_res = re.search(
        r"(?i)警告|\bwarn(ing\b|\b)", res[1].decode('utf8'))
    if (er_res or info_er_res) and not warn_res:
        if er_res:
            return res[0].decode('utf8'), res[1].decode('utf8')
        if info_er_res:
            return 0, res[0].decode('utf8')
    else:
        if res[0]:
            return res[0].decode('utf8'), 0
        if res[1]:
            return res[1].decode('utf8'), 0
    return 0, 0


class NetInterfacesError(IOError):
    """Network interfaces not exist
    """


class InterfacesNotFoundError(IOError):
    """Not found network interface config
    """


class InterfacesConfigValueError(ValueError):
    """ip value error or attr error
    """


class InterfacesEnableError(IOError):
    """network interfaces reload error
    """


class BaseNetworkInterfaces(object):
    """
    对网卡的抽象
    :param interface_name:
    :raises IOError: 判断网卡配置文件是否存在
        ValueError: 判断ip和inter type是否合法
    """
    INTERFACE_CONFIG_PATH = ""

    def __init__(self, interface_name):
        if re.search(r'\s', interface_name) or not interface_name:
            raise InterfacesNotFoundError("interface config dose not exist")
        self.ifname = interface_name
        self._ifcfg = OrderedDict()
        self._ifcfg_key = OrderedDict()
        # 修改NetworkManager的ifupdown的managed参数为false, 避免和NetworkManager冲突
        cf = Config(allow_no_value=True)
        if cf.read("/etc/NetworkManager/NetworkManager.conf"):
            if cf.has_section('ifupdown') and \
                    cf.has_option('ifupdown', 'managed') and \
                    cf.get('ifupdown', 'managed') != 'false':
                cf.set("ifupdown", "managed", "false")
                with open("/etc/NetworkManager/NetworkManager.conf", 'w') as f:
                    cf.write(f)
        del cf

    @property
    def interface_config(self):
        d = OrderedDict()
        [d.update({k: self._ifcfg.get(v)}) for k, v in self._ifcfg_key.items()]
        return d

    @interface_config.setter
    def interface_config(self, d):
        """
        :param d: a dict
        """
        self._ifcfg.update(d)

    @property
    def interface_type(self):
        return self._ifcfg.get(self._ifcfg_key.get("interface_type"), None)

    @interface_type.setter
    def interface_type(self, value):
        """"""

    @classmethod
    def set_inter_type(cls, network_interface_name, interface_type):
        ifcfg = cls(network_interface_name)
        ifcfg.interface_type = interface_type
        ifcfg.commit()

    @interface_type.deleter
    def interface_type(self):
        raise InterfacesConfigValueError("interface proto can't be empty")

    @property
    def ip_address(self):
        return self._ifcfg.get(self._ifcfg_key.get("ip_address"), None)

    @ip_address.setter
    def ip_address(self, value):
        if ip_check(value):
            self._ifcfg[self._ifcfg_key["ip_address"]] = value
        else:
            raise InterfacesConfigValueError('ip address error')

    @classmethod
    def set_ip_address(cls, network_interface_name, ip):
        """
        get_network_cls().set_ip_address
        :raises IOError: not found network interface,
            ValueError: ip check error
        """
        ifcfg = cls(network_interface_name)
        ifcfg.ip_address = ip
        ifcfg.commit()

    @ip_address.deleter
    def ip_address(self):
        try:
            del self._ifcfg[self._ifcfg_key["ip_address"]]
        except KeyError:
            pass

    @property
    def gateway(self):
        return self._ifcfg.get(self._ifcfg_key.get("gateway"), None)

    @gateway.setter
    def gateway(self, value):
        if ip_check(value):
            self._ifcfg[self._ifcfg_key["gateway"]] = value
        else:
            raise InterfacesConfigValueError('gateway address error')

    @classmethod
    def set_gateway(cls, network_interface_name, gateway):
        """
        get_network_cls().set_gateway
        :raises IOError: not found network interface,
            ValueError: ip check error
        """
        ifcfg = cls(network_interface_name)
        ifcfg.gateway = gateway
        ifcfg.commit()

    @gateway.deleter
    def gateway(self):
        try:
            del self._ifcfg[self._ifcfg_key["gateway"]]
        except KeyError:
            pass

    @property
    def dns(self):
        return self._ifcfg.get(self._ifcfg_key.get("dns"), None)

    @dns.setter
    def dns(self, value):
        if ip_check(value):
            self._ifcfg[self._ifcfg_key["dns"]] = value
        else:
            raise InterfacesConfigValueError('dns address error')

    @classmethod
    def set_dns(cls, network_interface_name, dns):
        """
        get_network_cls().set_dns
        :raises IOError: not found network interface,
            ValueError: ip check error
        """
        ifcfg = cls(network_interface_name)
        ifcfg.dns = dns
        ifcfg.commit()

    @dns.deleter
    def dns(self):
        try:
            del self._ifcfg[self._ifcfg_key["dns"]]
        except KeyError:
            pass

    @property
    def netmask(self):
        return self._ifcfg.get(self._ifcfg_key.get("netmask"), None)

    @netmask.setter
    def netmask(self, value):
        if ip_check(value):
            self._ifcfg[self._ifcfg_key["netmask"]] = value
        else:
            raise InterfacesConfigValueError('netmask address error')

    @netmask.deleter
    def netmask(self):
        try:
            del self._ifcfg[self._ifcfg_key["netmask"]]
        except KeyError:
            pass

    def dhcp(self):
        """
        set the network interface prototype to dhcp
        """

    def reset_dhcp(self):
        """
        当更改后,重启服务无法生效时,可以重置为dhcp再做更改
        """
        if self.ifname.startswith('bond'):
            raise InterfacesConfigValueError('bond network don\'t set dhcp')
        self.dhcp()
        return self.commit()

    def promisc(self):
        """
        set the network interface prototype to promisc
        """

    def reset_promisc(self):
        """
        重置为混杂模式
        """
        self.promisc()
        commit_res = self.commit()
        res = run_cmd_in_shell('ip link set %s promisc on' % self.ifname)
        if res[1]:
            raise InterfacesEnableError('ip link set promisc failed')
        return commit_res

    def none_type(self):
        """
        set the network interface prototype to none and clean ip, dns, gateway
        :return:
        """

    def reset_none(self):
        """不启用网卡"""
        self.none_type()
        return self.commit()

    def reset_bonding_slave(self, bond_name):
        """设置为bonding 聚合网卡的子网卡"""
        if self.ifname.startswith('bond'):
            raise InterfacesConfigValueError('bond network don\'t set slave')

    def commit(self):
        """
        Enable configuration 提交更改, 重启网卡
        :return: result
        """

    def rollback(self):
        """
        Roll back the configuration 回滚配置文档
        """

    @classmethod
    def create_interface_config(cls, interface_name):
        """
        添加新的网卡配置文档
        :param interface_name: 网卡名.
        :type interface_name: str, unicode.
        :return: An instance of a BaseNetworkInterfaces subclass.
        """
        import netifaces

        if not re.match(r"bond\d+", interface_name) and interface_name not in \
                netifaces.interfaces():
            raise NetInterfacesError("network interface dose not exist")


class LinuxBaseNetworkInterfaces(BaseNetworkInterfaces):

    # def reset_promisc(self):
    #     res = Popen(shlex.split("ip link set %s promisc on" % self.ifname),
    #                 stderr=PIPE, stdout=PIPE)
    #     res = res.communicate()
    #     if res[1]:
    #         raise InterfacesEnableError(res[1])
    #     return res[0]

    @classmethod
    def set_ip_address(cls, network_interface_name, ip):
        """
        get_network_cls().set_ip_address
        :raises IOError: not found network interface,
            ValueError: ip check error
        """
        if not isinstance(ip, list):
            raise InterfacesConfigValueError('value requires list')
        ifcfg = cls(network_interface_name)
        ifcfg.ip_address = ip
        ifcfg.commit()

    @classmethod
    def set_dns(cls, network_interface_name, dns):
        """
        get_network_cls().set_dns
        :raises IOError: not found network interface,
            ValueError: ip check error
        """
        if not isinstance(dns, list):
            raise InterfacesConfigValueError('value requires list')
        ifcfg = cls(network_interface_name)
        ifcfg.dns = dns
        ifcfg.commit()

    def commit(self):
        """
        linux commit
        :return: success:1| failed:0, success:0| failed: error info
        :rtype tuple
        """
        if check_networkmanager():
            run_cmd_in_shell('systemctl stop NetworkManager')
            run_cmd_in_shell('systemctl disable NetworkManager')
        ifdown_res = run_cmd_in_shell("ifdown %s" % self.ifname)
        if ifdown_res[1]:
            raise InterfacesEnableError(
                "ifdown %s: %s" % (self.ifname, ifdown_res[1]))

        ifup_res = run_cmd_in_shell("ifup %s" % self.ifname)
        if ifup_res[1]:
            raise InterfacesEnableError(
                "ifup %s: %s" % (self.ifname, ifup_res[1].decode('utf8')))

        return ifup_res[0]


class RedHatNetworkInterfaces(LinuxBaseNetworkInterfaces):
    """network interface configuration schema
/etc/sysconfig/network-scripts/ifcfg-xxx

TYPE=Ethernet
PROXY_METHOD=none
BROWSER_ONLY=no
BOOTPROTO=static
DEFROUTE=no
IPV4_FAILURE_FATAL=yes
IPV6INIT=no
IPV6_AUTOCONF=no
IPV6_DEFROUTE=no
IPV6_FAILURE_FATAL=no
IPV6_ADDR_GEN_MODE=stable-privacy
NAME=xxx
UUID=f7c0403f-2ad1-4883-8d86-2b58c8fbd0bf
DEVICE=xxx
ONBOOT=yes
IPADDR1=192.168.50.52
IPADDR2=192.168.50.53
NETMASK=255.255.255.0
GATEWAY=192.168.50.254
DNS1=114.114.114.114
    """
    INTERFACE_CONFIG_PATH = "/etc/sysconfig/network-scripts/"

    def __init__(self, interface_name):
        super(RedHatNetworkInterfaces, self).__init__(interface_name)
        self.interface_path = "%sifcfg-%s" % (self.INTERFACE_CONFIG_PATH,
                                              self.ifname)
        [self._ifcfg_key.update({k[0]: k[1]}) for k in [
            ("interface_type", "BOOTPROTO"), ("gateway", "GATEWAY"),
            ('promisc', 'PROMISC'), ('default_route', 'DEFROUTE'),
            ('slave', 'SLAVE'), ('master', 'MASTER'),
            ('bond_opts', 'BONDING_OPTS'), ('bond_mod', 'BONDING_MOD'),
            ('bond_miimon', 'BONDING_MIIMON'), ('onboot', 'ONBOOT'),
            ('netmask', 'NETMASK')
        ]]
        try:
            with open(self.interface_path, 'r') as f:
                self._ifcfg_backup = ""
                for option in f:
                    self._ifcfg_backup += option
                    self._ifcfg.setdefault(
                        option.strip().split('=')[0],
                        "=".join(option.strip().split('=')[1:]).rstrip('=')
                    )
            self._ifcfg_key['ip_address'] = filter(
                lambda _k: re.match(r'IPADDR', _k), self._ifcfg.keys())
            self._ifcfg_key['dns'] = filter(
                lambda _k: re.match(r'DNS', _k), self._ifcfg.keys())
            promisc = Popen(shlex.split('ip link show %s' % interface_name),
                            stdout=PIPE, stderr=PIPE).communicate()[0]
            promisc = re.search("PROMISC", promisc)
            if self._ifcfg.get('PROMISC'):
                if not promisc:
                    self._ifcfg.pop("PROMISC")
            if self._ifcfg.get('BOOTPROTO') == 'dhcp':
                ips = [
                    net.get('addr') for net in
                    netifaces.ifaddresses(interface_name).get(
                        netifaces.AF_INET, [])
                ]
                ips = filter(lambda _ip: ip_check(_ip), ips)
                if ips:
                    if len(ips) == 1:
                        self._ifcfg['IPADDR'] = ips[0]
                        self._ifcfg_key['ip_address'] = ['IPADDR']
                    else:
                        self._ifcfg_key['ip_address'] = []
                        for i, ip in enumerate(ips):
                            self._ifcfg['IPADDR%s' % int(i + 1)] = ip
                            self._ifcfg_key['ip_address'].append(
                                'IPADDR%s' % int(i + 1))

        except IOError:
            raise InterfacesNotFoundError
        self._ifcfg.update({"ONBOOT": "yes"})

    @property
    def interface_config(self):
        d = OrderedDict()
        for k, v in self._ifcfg_key.items():
            if isinstance(v, list):
                d.update({_k: self._ifcfg.get(_k) for _k in v})
            else:
                d.update({k: self._ifcfg.get(v)})
        d.update(ip_address=self.ip_address)
        return d

    @property
    def interface_type(self):
        return self._ifcfg.get(self._ifcfg_key.get("interface_type"), None)

    @interface_type.setter
    def interface_type(self, value):
        if value and (value in ("dhcp", "static", "promisc", "none")):
            if value == 'dhcp':
                self.reset_dhcp()
            elif value == 'promisc':
                self.reset_promisc()
            elif value == 'static':
                self._ifcfg[self._ifcfg_key["interface_type"]] = 'static'
                if self._ifcfg_key.get('promisc') and self._ifcfg.get(
                        self._ifcfg_key["promisc"]):
                    del self._ifcfg[self._ifcfg_key["promisc"]]
            elif value == 'none':
                self.reset_none()
            else:
                raise InterfacesConfigValueError('interface type not found')
        else:
            raise InterfacesConfigValueError("interface proto can't be empty")

    @property
    def ip_address(self):
        if self._ifcfg_key.get('ip_address'):
            return [self._ifcfg.get(k) for k in self._ifcfg_key['ip_address']]
        else:
            return None

    @ip_address.setter
    def ip_address(self, value):
        """
        :param value: ["192.168.8.1", "192.168.8.2", ...]
        :return:
        """
        if not isinstance(value, list):
            try:
                value = json.loads(value)
                if isinstance(value, list):
                    raise InterfacesConfigValueError(
                        'value requires list-jsonstring')
            except (TypeError, ValueError):
                raise InterfacesConfigValueError('value requires list')
        if value and len(filter(ip_check, value)) == len(value):
            if len(self._ifcfg_key.get('ip_address')) != len(value):
                if self._ifcfg_key.get('ip_address'):
                    [self._ifcfg.pop(k) for k in self._ifcfg_key['ip_address']]
                if len(value) == 1:
                    self._ifcfg.update({'IPADDR': value[0]})
                else:
                    [self._ifcfg.update({'IPADDR' + str(n): e}) for n, e in
                        enumerate(value)]
            elif len(self._ifcfg_key.get('ip_address')) == len(value):

                [self._ifcfg.update({k: v}) for k, v in
                    zip(self._ifcfg_key['ip_address'], value)]
        else:
            raise InterfacesConfigValueError('ip address error')

    @ip_address.deleter
    def ip_address(self):
        try:
            if self._ifcfg_key.get('ip_address'):
                [self._ifcfg.pop(k) for k in self._ifcfg_key['ip_address']]
        except KeyError:
            pass

    @property
    def default_route(self, ):
        return self._ifcfg.get(self._ifcfg_key.get("default_route"))

    @default_route.setter
    def default_route(self, value):
        if value in ("yes", "no", "YES", "NO"):
            self._ifcfg[self._ifcfg_key["default_route"]] = value.lower()
        else:
            raise InterfacesConfigValueError('default route must be yes or no')

    @property
    def dns(self):
        return [self._ifcfg.get(k) for k in self._ifcfg_key.get("dns")]

    @dns.setter
    def dns(self, value):
        if not isinstance(value, list):
            try:
                value = json.loads(value)
                if isinstance(value, list):
                    raise InterfacesConfigValueError(
                        'value requires list-jsonstring')
            except (TypeError, ValueError):
                raise InterfacesConfigValueError('value requires list')
        if len(filter(ip_check, value)) == len(value):
            if len(self._ifcfg_key.get('dns')) != len(value):
                if self._ifcfg_key.get('dns'):
                    [self._ifcfg.pop(k) for k in self._ifcfg_key['dns']]
                [self._ifcfg.setdefault('DNS' + str(n + 1), e) for n, e in
                    enumerate(value)]
            elif len(self._ifcfg_key.get('dns')) == len(value):
                [self._ifcfg.setdefault(k, v) for k, v in
                    zip(self._ifcfg_key['dns'], value)]
        else:
            raise InterfacesConfigValueError('dns address error')

    @dns.deleter
    def dns(self):
        try:
            if self._ifcfg_key.get('dns'):
                [self._ifcfg.pop(k) for k in self._ifcfg_key['dns']]
        except KeyError:
            pass

    @property
    def master(self):
        return self._ifcfg.get(self._ifcfg_key.get('master'), None)

    @master.setter
    def master(self, value):
        self._ifcfg[self._ifcfg_key['master']] = value

    @master.deleter
    def master(self):
        try:
            del self._ifcfg[self._ifcfg_key["master"]]
        except KeyError:
            pass

    @property
    def slave(self):
        return self._ifcfg.get(self._ifcfg_key.get('slave'), None)

    @slave.setter
    def slave(self, value):
        if isinstance(
                value, (unicode, str)) and value.lower() in (
                'yes', 'no'):
            self._ifcfg[self._ifcfg_key['slave']] = value.lower()
        else:
            raise InterfacesConfigValueError('slave must be yes or no')

    @slave.deleter
    def slave(self):
        try:
            del self._ifcfg[self._ifcfg_key["slave"]]
        except KeyError:
            pass

    @property
    def bond_opts(self):
        return self._ifcfg.get(self._ifcfg_key.get('bond_opts'), None)

    @bond_opts.setter
    def bond_opts(self, value):
        self._ifcfg[self._ifcfg_key['bond_opts']] = value.lower()

    @bond_opts.deleter
    def bond_opts(self):
        try:
            del self._ifcfg[self._ifcfg_key["bond_opts"]]
        except KeyError:
            pass

    def commit(self):
        if self.slave == 'no':
            del self.master
            del self.slave
        with open(self.interface_path, 'w') as f:
            tmp = ""
            for k, v in self._ifcfg.items():
                if v:
                    tmp += k + "=" + str(v) + "\n"
            f.write(str(tmp))
        if self._ifcfg.get('GATEWAY'):
            with open('/etc/sysconfig/network', 'r') as f:
                old = f.read()
                if re.search(r'GATEWAY', old):
                    new = re.sub(
                        r"(GATEWAY)(=| = ).*",
                        lambda s: s.group(1) + s.group(2) +
                        self._ifcfg.get('GATEWAY'), old)
                else:
                    new = old.decode('utf-8') + '\nGATEWAY=' + \
                        self._ifcfg.get('GATEWAY')
            with open('/etc/sysconfig/network', 'w') as f:
                f.write(new.encode('utf-8'))
        try:
            commit_res = super(RedHatNetworkInterfaces, self).commit()
            # run_cmd_in_shell('systemctl restart network')
            return commit_res
        except InterfacesEnableError:
            raise

    def dhcp(self):
        [self._ifcfg.pop(k) for k in self._ifcfg.keys() if k not in (
            'TYPE', 'DEVICE', 'UUID', 'ONBOOT', 'NAME')]
        self._ifcfg.update({"BOOTPROTO": "dhcp"})

    def promisc(self):
        # [self._ifcfg.pop(k) for k in self._ifcfg.keys() if k not in (
        #     'TYPE', 'DEVICE', 'UUID', 'ONBOOT', 'NAME')]
        [self._ifcfg.pop(k) for k in self._ifcfg.keys()
            if re.match(r'(?i)ip|gateway|bootproto|dns', k)]
        self._ifcfg.update(PROMISC='yes')

    def none_type(self):
        [self._ifcfg.pop(k) for k in self._ifcfg.keys() if
            k not in ('TYPE', 'DEVICE', 'UUID', 'ONBOOT', 'NAME')]
        self._ifcfg.update({"BOOTPROTO": "none"})

    def reset_bonding_slave(self, bond_name):
        super(RedHatNetworkInterfaces, self).reset_bonding_slave(bond_name)
        [self._ifcfg.pop(k) for k in self._ifcfg.keys() if
            k not in ('TYPE', 'DEVICE', 'UUID', 'ONBOOT', 'NAME')]
        self._ifcfg.update({
            "BOOTPROTO": "none", 'SLAVE': 'yes'
        })
        self.master = bond_name
        return self.commit()

    def rollback(self):
        with open(self.interface_path, 'w') as f:
            f.write(str(self._ifcfg_backup))
        try:
            commit_res = super(RedHatNetworkInterfaces, self).commit()
            # run_cmd_in_shell('systemctl restart network')
            return commit_res
        except InterfacesEnableError:
            raise

    @classmethod
    def create_interface_config(cls, interface_name):
        super(RedHatNetworkInterfaces, cls).create_interface_config(
            interface_name)
        try:
            # 验证是否已经有了配置文档
            cls(interface_name)
            raise InterfacesConfigValueError("The interfaces config already "
                                             "exists")
        except InterfacesNotFoundError:
            _conf = [
                "TYPE=Ethernet\n",
                "PROXY_METHOD=none\n",
                "BROWSER_ONLY=no\n",
                "BOOTPROTO=none\n",
                "DEFROUTE=no\n",
                "NETMASK=255.255.255.0\n",
                "IPV4_FAILURE_FATAL=yes\n",
                "IPV6INIT=no\n",
                "IPV6_AUTOCONF=no\n",
                "IPV6_DEFROUTE=no\n",
                "IPV6_FAILURE_FATAL=no\n",
                "IPV6_ADDR_GEN_MODE=stable-privacy\n",
                "NAME=%s\n" % interface_name,
                "UUID=%s\n" % uuid.uuid4().__str__(),
                "DEVICE=%s\n" % interface_name,
                "ONBOOT=yes\n"
            ]
            if interface_name.startswith('bond'):
                _conf = [
                    "TYPE=Bond\n",
                    "BONDING_MASTER=yes\n",
                    "BONDING_OPTS=\"mode=0 miimon=100\"\n",
                    "PROXY_METHOD=none\n",
                    "BROWSER_ONLY=no\n",
                    "BOOTPROTO=none\n",
                    "DEFROUTE=no\n",
                    "NETMASK=255.255.255.0\n",
                    "IPV4_FAILURE_FATAL=yes\n",
                    "IPV6INIT=no\n",
                    "IPV6_AUTOCONF=no\n",
                    "IPV6_DEFROUTE=no\n",
                    "IPV6_FAILURE_FATAL=no\n",
                    "IPV6_ADDR_GEN_MODE=stable-privacy\n",
                    "NAME=%s\n" % interface_name,
                    "UUID=%s\n" % uuid.uuid4().__str__(),
                    "DEVICE=%s\n" % interface_name, "ONBOOT=yes\n"]
            with open("%sifcfg-%s" % (cls.INTERFACE_CONFIG_PATH,
                                      interface_name), 'w') as f:
                f.writelines(_conf)
            return cls(interface_name)


class DebianNetworkInterfaces(LinuxBaseNetworkInterfaces):
    """network interface configuration schema
/etc/network/interfaces

# The loopback network interface
auto lo
iface lo inet loopback

# 导入这个文件夹下的各个网卡配置文件
source-directory interfaces.d
================================================================================
/etc/network/interfaces.d/ens33
# The primary network interface
auto ens33
allow-hotplug
iface ens33 inet static
    address 192.168.50.51
    netmask 255.255.255.0
    gateway 192.168.50.254
    dns-nameserver 1.2.4.8

    """
    INTERFACE_CONFIG_DIRECTORY = "/etc/network/"
    INTERFACE_CONFIG_PATH = INTERFACE_CONFIG_DIRECTORY + "interfaces"

    def __init__(self, interface_name):
        super(DebianNetworkInterfaces, self).__init__(interface_name)
        [
            self._ifcfg_key.update({k[0]: k[1]}) for k in
            [
                ("interface_type", "inet"),
                ("gateway", "gateway"), ("ip_address", "multiple_ip"),
                ("netmask", "netmask"), ("dns", "dns-nameservers"),
                ("slaves", "slaves"), ("master", "bond-master"),
                ("bond_mode", "bond-mode")
            ]
        ]

        promisc = Popen(shlex.split('ip link show %s' % interface_name),
                        stdout=PIPE, stderr=PIPE).communicate()[0]
        promisc = re.search("PROMISC", promisc)
        self.ifcfg_sources = dict()
        ifcfg_pattern = re.compile(r"iface +%s.*\n+( *\S.*\n?)*" % self.ifname)

        with open(self.INTERFACE_CONFIG_PATH, 'r') as f:
            self._configs = f.read()
        # 查找当前的配置文件里有没有这个网卡的配置
        self._ifcfg_backup = self._findall(ifcfg_pattern, self._configs)
        # 查找从其他位置引入的文件内有没有这个网卡的配置
        if re.search(r'source *.*', self._configs):
            for p in re.findall(r'source +(.*)', self._configs):
                if not p.startswith('/'):
                    _path = self.INTERFACE_CONFIG_DIRECTORY + p
                else:
                    _path = p
                if _path.endswith('*'):
                    _path = _path[:-1]
                if os.path.exists(_path):
                    if os.path.isdir(_path):
                        for _p in os.listdir(_path):
                            _p = os.path.join(_path, _p)
                            if not os.path.isdir(_p):
                                with open(_p) as _f:
                                    _cfg = _f.read()
                                if ifcfg_pattern.search(_cfg):
                                    self.ifcfg_sources[_p] = {
                                        'config': _cfg,
                                        'backup': self._findall(ifcfg_pattern,
                                                                _cfg)
                                    }
                    elif os.path.isfile(_path):
                        with open(_path) as f:
                            _cfg = f.read()
                        if ifcfg_pattern.search(_cfg):
                            self.ifcfg_sources[_path] = {
                                'config': _cfg,
                                'backup': self._findall(ifcfg_pattern, _cfg)
                            }
                else:
                    self._configs = re.sub(
                        r'source +%s' % p, '', self._configs)
        # 查找从其他目录下引入的所有文件内有没有这个网卡的配置
        if re.search(r'source-directory *.*', self._configs):
            for dp in re.findall(r'source-directory +(.*)',
                                 self._configs):
                if not dp.startswith('/'):
                    ifcfg_directory = self.INTERFACE_CONFIG_DIRECTORY + dp
                else:
                    ifcfg_directory = dp
                if os.path.exists(ifcfg_directory):
                    for p in os.listdir(ifcfg_directory):
                        _path = os.path.join(ifcfg_directory, p)
                        if not os.path.isdir(_path):
                            with open(_path) as _f:
                                _cfg = _f.read()
                            if ifcfg_pattern.search(_cfg):
                                self.ifcfg_sources[_path] = {
                                    'config': _cfg, 'backup': self._findall(
                                        ifcfg_pattern, _cfg)}
                else:
                    self._configs = re.sub(
                        r'source-directroy +%s' % dp, '', self._configs)
        self._ifcfg['inet'] = None
        self._ifcfg['netmask'] = None
        self._ifcfg['pre_up'] = []
        self._ifcfg['up'] = []
        self._ifcfg['post_up'] = []
        self._ifcfg['pre_down'] = []
        self._ifcfg['down'] = []
        self._ifcfg['post_down'] = []
        self._ifcfg['dns-nameservers'] = []
        self._ifcfg['multiple_ip'] = []
        if not self._ifcfg_backup and not self.ifcfg_sources:
            raise InterfacesNotFoundError
        self._set_ifcfg("\n".join(self._ifcfg_backup))
        for source_conf in self.ifcfg_sources.values():
            self._set_ifcfg("\n".join(source_conf['backup']))
        if promisc and self._is_active_promisc():
            self._ifcfg['promisc'] = 'yes'
        if not promisc and self._is_active_promisc():
            self._ifcfg['promisc'] = 'prepare'

    def _set_ifcfg(self, config):
        iftype = re.findall(r'inet +(\w+)', config)
        if iftype:
            if (self._ifcfg['inet'] and self._ifcfg['inet'] != iftype[0]
                ) or not all(
                    map(lambda x: 1 if x == iftype[0] else 0, iftype)):
                self._ifcfg['inet'] = 'none'
            else:
                self._ifcfg['inet'] = iftype[0]
        config = re.sub(r"iface +%s +inet.*\n" % self.ifname, '', config)
        for option in config.split('\n'):
            if option:
                k, v = option.strip().split()[0], " ".join(
                    option.strip().split()[1:])
                if k in ('pre-up', 'up', 'post-up', 'pre-down', 'down',
                         'post-down'):
                    if re.search(
                            r'''(?x)ip\ +a(d(d(r(es{0,2})?)?)?)?\ +
                            # ip address 命令可以是 ip a[d[d[r[e[s[s]]]]]]
                            (add|del|change|replace)\ +
                            # 这几个子命令可以在网卡up或down的时候执行添加或删除命令
                            ((25[0-5]|2[0-4]\d|1?\d{1,2})\.){3}
                            (25[0-5]|2[0-4]\d|1?\d{1,2})(\ +|/\d+).*
                            # ipv4 的正则匹配''', v):
                        _ip = re.search(
                            r'''(?x)(?<=\ )
                            # 匹配空格开头, 空格或子网掩码结尾的合法ip地址
                            ((25[0-5]|2[0-4]\d|1?\d{1,2})\.){3}
                            (25[0-5]|2[0-4]\d|1?\d{1,2})(?=\ +|/\d+)''',
                            v).group()
                        if _ip not in self._ifcfg['multiple_ip']:
                            self._ifcfg['multiple_ip'].append(_ip)
                    else:
                        self._ifcfg[k.replace('-', '_')].append(v)
                elif k == 'address':
                    if ip_check(v.strip()):
                        self._ifcfg['multiple_ip'].append(v.strip())
                elif k in ('dns-nameserver', 'dns-nameservers'):
                    for dns in v.strip().split():
                        if ip_check(dns):
                            self._ifcfg['dns-nameservers'].append(dns)
                else:
                    self._ifcfg[k] = v

    def _findall(self, pattern, ifcfg):
        """
        :type pattern: re.RegexObject
        :type ifcfg: str
        :return: list
        """
        result = []
        _res = pattern.search(ifcfg)
        _end = 0
        while _res and _end <= len(ifcfg):
            result.append(_res.group())
            _end += _res.end()
            _res = pattern.search(ifcfg[_end + 1:])
        return result

    @property
    def interface_config(self):
        d = super(DebianNetworkInterfaces, self).interface_config
        if 'promisc' in self._ifcfg:
            d.update(promisc=self._ifcfg['promisc'])
        return d

    @property
    def interface_type(self):
        return self._ifcfg.get(self._ifcfg_key.get("interface_type"), None)

    @interface_type.setter
    def interface_type(self, value):
        if value and (value in ("dhcp", "static", "promisc", "none")):
            if value == 'dhcp':
                self.reset_dhcp()
            elif value == 'promisc':
                self.reset_promisc()
            elif value == 'static':
                self._ifcfg[self._ifcfg_key["interface_type"]] = 'static'
                if self._is_active_promisc():
                    for cmds in ('pre_up', 'up', 'post_up', 'pre_down',
                                 'down', 'post_down'):
                        _new_cmds = []
                        for l in self._ifcfg[cmds]:
                            if not re.search('promisc', l):
                                _new_cmds.append(l)
                        self._ifcfg[cmds] = _new_cmds
                    run_cmd_in_shell('ip l set %s promisc off' % self.ifname)
            elif value == 'none':
                self.reset_none()
            else:
                raise InterfacesConfigValueError('interface type not found')
        else:
            raise InterfacesConfigValueError("interface proto can't be empty")

    def _is_active_promisc(self):
        _up_cmds = self._ifcfg['pre_up'] + self._ifcfg['up'] + self._ifcfg[
            'post_up']
        for cmd in _up_cmds:
            if re.search(r'ip +l(i(n(k?)?)?)? +set.* +promisc +on', cmd):
                return True

    def promisc(self):
        self._ifcfg[self._ifcfg_key["interface_type"]] = "manual"
        del self.ip_address
        self._ifcfg.pop(self._ifcfg_key.get('gateway'), None)
        if not self._is_active_promisc():
            self._ifcfg['up'].append('ip link set $IFACE promisc on')
            self._ifcfg['down'].append('ip link set $IFACE promisc off')

    def dhcp(self):
        self._ifcfg[self._ifcfg_key["interface_type"]] = "dhcp"
        del self.ip_address
        self._ifcfg.pop(self._ifcfg_key.get('gateway'), None)
        del self.dns

    def none_type(self):
        self._ifcfg[self._ifcfg_key["interface_type"]] = "manual"
        del self.ip_address
        self._ifcfg.pop(self._ifcfg_key.get('gateway'), None)
        del self.dns
        self._ifcfg.pop('pre_up', None)
        self._ifcfg.pop('up', None)
        self._ifcfg.pop('post_up', None)
        self._ifcfg.pop('pre_down', None)
        self._ifcfg.pop('down', None)
        self._ifcfg.pop('post_down', None)

    def reset_bonding_slave(self, bond_name):
        super(DebianNetworkInterfaces, self).reset_bonding_slave(bond_name)
        self._ifcfg[self._ifcfg_key["interface_type"]] = "manual"
        self._ifcfg[self._ifcfg_key['master']] = bond_name
        del self.ip_address
        self._ifcfg.pop(self._ifcfg_key.get('gateway'), None)
        del self.dns
        self._ifcfg.pop('pre_up', None)
        self._ifcfg.pop('up', None)
        self._ifcfg.pop('post_up', None)
        self._ifcfg.pop('pre_down', None)
        self._ifcfg.pop('down', None)
        self._ifcfg.pop('post_down', None)

    @property
    def ip_address(self):
        return self._ifcfg.get(self._ifcfg_key.get('ip_address'), None)

    @ip_address.setter
    def ip_address(self, value):
        """
        :param value: ["192.168.8.1", "192.168.8.2", ...]
        :return:
        """
        if not isinstance(value, list):
            try:
                value = json.loads(value)
                if isinstance(value, list):
                    raise InterfacesConfigValueError(
                        'value requires list-jsonstring')
            except (TypeError, ValueError):
                raise InterfacesConfigValueError('value requires list')
        if value and len(filter(ip_check, value)) == len(value):
            self._ifcfg[self._ifcfg_key['ip_address']] = value
        else:
            raise InterfacesConfigValueError('ip address error')

    @ip_address.deleter
    def ip_address(self):
        if self._ifcfg.get('address', None):
            run_cmd_in_shell('ip a del %s dev %s' %
                             (self._ifcfg['address'], self.ifname))
        for _ip in self._ifcfg.get(self._ifcfg_key['ip_address'], []):
            run_cmd_in_shell('ip a del %s dev %s' % (_ip, self.ifname))
        self._ifcfg.pop(self._ifcfg_key['ip_address'], None)
        self._ifcfg.pop('address', None)

    @property
    def dns(self):
        return self._ifcfg.get(self._ifcfg_key.get('dns'), None)

    @dns.setter
    def dns(self, value):
        if not isinstance(value, list):
            try:
                value = json.loads(value)
                if isinstance(value, list):
                    raise InterfacesConfigValueError(
                        'value requires list-jsonstring')
            except (TypeError, ValueError):
                raise InterfacesConfigValueError('value requires list')
        if len(filter(ip_check, value)) == len(value):
            self._ifcfg[self._ifcfg_key['dns']] = value
        else:
            raise InterfacesConfigValueError('dns address error')

    @dns.deleter
    def dns(self):
        self._ifcfg.pop(self._ifcfg_key['dns'], None)
        self._ifcfg.pop('dns-nameservers', None)
        self._ifcfg.pop('dns-nameserver', None)

    @property
    def master(self):
        return self._ifcfg.get(self._ifcfg_key.get('master'), None)

    @master.setter
    def master(self, value):
        self._ifcfg[self._ifcfg_key['master']] = value

    @master.deleter
    def master(self):
        self._ifcfg.pop(self._ifcfg_key['master'], None)

    @property
    def slave(self):
        return self._ifcfg.get(self._ifcfg_key.get('slaves'), None)

    @slave.setter
    def slave(self, value):
        self._ifcfg[self._ifcfg_key['slaves']] = value

    @slave.deleter
    def slave(self):
        self._ifcfg.pop(self._ifcfg_key['slaves'], None)

    @classmethod
    def create_interface_config(cls, interface_name):
        super(DebianNetworkInterfaces, cls).create_interface_config(
            interface_name)
        try:
            cls(interface_name)
            raise InterfacesConfigValueError("The interfaces config already "
                                             "exists")
        except InterfacesNotFoundError:
            new_file = cls.INTERFACE_CONFIG_DIRECTORY + '/interfaces.d/%s' % \
                interface_name
            if os.path.exists(new_file):
                os.remove(new_file)
                # os.stat(new_file)
                # new_file += time.strftime("%Y%m%d-%H%M%S", time.localtime())
            _conf = [
                "auto %s\n" % interface_name,
                "iface %s inet dhcp\n" % interface_name
            ]
            if interface_name.startswith('bond'):
                _conf = [
                    "auto %s\n" % interface_name,
                    "iface %s inet static\n" % interface_name,
                    "    bond_mod 0",
                    "    bond_miimon 100",
                ]
            with open(new_file, 'w') as f:
                f.writelines(_conf)
            return cls(interface_name)

    def rollback(self):
        with open(self.INTERFACE_CONFIG_PATH, 'w') as f:
            f.write(self._configs)
        for p, back in self.ifcfg_sources.items():
            with open(p, 'w') as f:
                f.write(back['config'])

    def commit(self):
        # 默认把所有散落的同一个网卡的配置集中到一个配置文件内
        # 先把旧有关于该网卡的配置清空
        # 设置ip
        if self._ifcfg.get(self._ifcfg_key['ip_address'], None):
            self._ifcfg['address'] = self._ifcfg[
                self._ifcfg_key['ip_address']][0]
            if len(self._ifcfg[self._ifcfg_key['ip_address']]) > 1:
                for _ip in self._ifcfg[self._ifcfg_key['ip_address']][1:]:
                    self._ifcfg['up'].append(
                        'ip address add %s/24 dev $IFACE' % _ip)
                    self._ifcfg['down'].append(
                        'ip address del %s/24 dev $IFACE' % _ip)
            self._ifcfg.pop(self._ifcfg_key['ip_address'], None)
        else:
            del self.ip_address
        # 设置dns
        if self._ifcfg.get(self._ifcfg_key['dns'], None):
            self._ifcfg['dns-nameservers'] = " ".join(
                self._ifcfg[self._ifcfg_key['dns']])
            self._ifcfg.pop('dns-nameserver', None)
        else:
            del self.dns
        if self._ifcfg[self._ifcfg_key["interface_type"]] != 'static' and \
                not self._ifcfg['netmask']:
            self._ifcfg['netmask'] = '255.255.255.0'
        self._ifcfg.pop('promisc', None)
        # 写入文件
        _new = re.sub('auto +%s\n' % self.ifname, '', self._configs)
        _new = re.sub('allow-hotplug +%s\n' % self.ifname, '', _new)
        for _old in self._ifcfg_backup:
            _new = _new.replace(_old, '')
        if not re.search(
                r'source-directory *interfaces.d|source *%s/interfaces.d/\*' %
                self.INTERFACE_CONFIG_DIRECTORY, _new):
            _new += '\nsource-directory interfaces.d'
        with open(self.INTERFACE_CONFIG_PATH, 'w') as f:
            f.write(_new)
        for p, back in self.ifcfg_sources.items():
            _new = re.sub('auto +%s\n' % self.ifname, '', back['config'])
            _new = re.sub('allow-hotplug +%s\n' % self.ifname, '', _new)
            for _old in back['backup']:
                _new = _new.replace(_old, '')
            if _new.strip():
                with open(p, 'w') as f:
                    f.write(_new)
            else:
                os.remove(p)
        _new = """auto {0}
allow-hotplug {0}
iface {0} inet {1}\n
""".format(self.ifname, self._ifcfg[self._ifcfg_key['interface_type']])
        self._ifcfg.pop(self._ifcfg_key['interface_type'])
        for k, v in self._ifcfg.items():
            if k in ('pre_up', 'up', 'post_up', 'pre_down', 'down',
                     'post_down'):
                for l in v:
                    _new += "    %s %s\n" % (k.replace('_', '-'), l)
            else:
                _new += "    %s %s\n" % (k, v)
        new_file = self.INTERFACE_CONFIG_DIRECTORY + \
            'interfaces.d/%s' % self.ifname
        if os.path.exists(new_file):
            os.remove(new_file)
            # new_file += time.strftime("%Y%m%d-%H%M%S", time.localtime())
        with open(new_file, 'w') as f:
            f.write(_new)
        try:
            commit_res = super(DebianNetworkInterfaces, self).commit()
            return commit_res
        except InterfacesEnableError as e:
            os.remove(new_file)
            raise e


def get_network_cls(os_v=OS_SERIES):
    """
    :param os_v: OS name
    :return:  RedHatNetworkInterfaces or DebianNetworkInterfaces
    :raise SystemExit: OS not found
    """
    if os_v == 'redhat':
        return RedHatNetworkInterfaces
    elif os_v == 'debian':
        return DebianNetworkInterfaces
    raise SystemExit("OS NOT FOUND")


def alter_ifcfg(ifcfg, conf_dict):
    """
    更改网卡配置
    :param ifcfg: 网卡实例
    :param conf_dict: 配置字典
    :return: success
    :raise: InterfacesConfigValueError
    """
    reset_type = filter(lambda t: t in ('reset_dhcp', "reset_promisc",
                                        "reset_none"),
                        conf_dict.keys())
    if reset_type:
        if reset_type.__len__() == 1:
            res = getattr(ifcfg, reset_type[0])()
        else:
            raise InterfacesConfigValueError(
                'error: reset_dhcp and reset_promisc cannot coexist')
    elif conf_dict.get('interface_type') in ('dhcp', 'promisc'):
        setattr(ifcfg, 'interface_type', conf_dict.get('interface_type'))
        res = "success"
    else:
        for k, v in conf_dict.items():
            if v in ('del', 'delete', 'drop'):
                delattr(ifcfg, k)
            else:
                setattr(ifcfg, k, v)
        res = ifcfg.commit()
    return res


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        # usage='alter network interfaces config',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="You must run as root!",
        epilog="""
e.g.:
get network interfaces config
    python %(prog)s --netifaces
alter network interface config
    python %(prog)s --alter ens33 \'{"ip_address": ["192.168.50.1", ....],
    "gateway": "192.168.50.254", "dns": ["1.2.4.8", ...]}\'
    or
    python %(prog)s --alter ens37 \'{"reset_dhcp": 1}\'
    or
    python %(prog)s --alter ens37 \'{"reset_promisc": 1}\'
    python %(prog)s --alter ens37 \'{"reset_none": 1}\'
remote
    $(nohup python /tmp/network/network_interface.pyc --alter 'json str' >& /dev/null < /dev/null &) && sleep 1
            """
    )
    parser.add_argument('--netifaces', action='store_true',
                        help='get network interfaces')
    parser.add_argument('--alter', nargs=2,
                        metavar=('name,', 'config json'), type=code_type,
                        help='Alter network interfaces config, '
                             'new config must be json string')
    parser.add_argument(
        '--tty',
        metavar='1 or 0',
        default=0,
        type=int,
        help='1: Output to terminal, 0: tmp file(/tmp/network-interfaces-std*),'
             ' default: 0')
    args = parser.parse_args()

    @contextmanager
    def change_std(change=args.tty):
        if not change:
            stdout = tempfile.mkstemp(prefix='network-interfaces-stdout',
                                      text=True)[1]
            stdout = open(stdout, 'w')
            stderr = tempfile.mkstemp(prefix='network-interfaces-stderr',
                                      text=True)[1]
            stderr = open(stderr, 'w')
        else:
            stdout, stderr = sys.stdout, sys.stderr
        try:
            yield {'stdout': stdout, 'stderr': stderr}
        except Exception as _error:
            stderr.write(_error.__str__())
        finally:
            stdout.close()
            stderr.close()

    with change_std() as std:
        guid = str(os.getuid())
        with open("/etc/passwd") as user:
            user = re.search(":" + guid + r":(\d*):", user.read())
            if user.group(1) != '0':
                # 当运行项目的用户不属于root用户组时, 退出进程并提示
                std['stderr'].write(
                    "Permission Denied! Must be run by the root user!\n")
                sys.exit()
        if args.netifaces:
            network_interfaces = OrderedDict()
            for interface in netifaces.interfaces():
                try:
                    network_interfaces[interface] = get_network_cls()(
                        interface).interface_config
                except InterfacesNotFoundError:
                    network_interfaces[interface] = 0
            network_interfaces.pop('lo', None)
            std['stdout'].write(json.dumps(network_interfaces) + '\n')
        elif args.alter:
            time.sleep(1)
            netifc_name = args.alter[0]
            new_config = json.loads(args.alter[1])
            ifconf = None
            try:
                ifconf = get_network_cls()(netifc_name)
            except InterfacesNotFoundError:
                try:
                    ifconf = get_network_cls().create_interface_config(
                        netifc_name)
                except (InterfacesConfigValueError, NetInterfacesError
                        ) as error:
                    std['stderr'].write(error.__str__() + '\n')
            if ifconf:
                slaves = []
                if new_config.get('slaves'):
                    for slave_ifname in new_config['slaves']:
                        try:
                            slave = get_network_cls()(slave_ifname)
                        except InterfacesNotFoundError:
                            try:
                                slave = get_network_cls(
                                ).create_interface_config(slave_ifname)
                            except (InterfacesConfigValueError,
                                    NetInterfacesError) as error:
                                raise InterfacesConfigValueError(error)
                        slaves.append(slave)
                    try:
                        for slave in slaves:
                            reset_res = slave.reset_none()
                            if reset_res:
                                std['stdout'].write("%s\n" % reset_res)
                    except (InterfacesConfigValueError,
                            InterfacesEnableError) as error:
                        for slave in slaves:
                            slave.rollback()
                        std['stderr'].write(error.__str__() + '\n')
                        raise error
                try:
                    alt_res = alter_ifcfg(ifconf, new_config)
                    if alt_res:
                        std['stdout'].write("%s\n" % alt_res)
                    try:
                        for slave in slaves:
                            bond_res = slave.reset_bonding_slave(ifconf.ifname)
                            if bond_res:
                                std['stdout'].write("%s\n" % bond_res)
                    except (InterfacesConfigValueError,
                            InterfacesEnableError) as error:
                        for slave in slaves:
                            slave.rollback()
                        std['stderr'].write(error.__str__() + '\n')
                except (InterfacesConfigValueError, InterfacesEnableError
                        ) as error:
                    ifconf.rollback()
                    std['stderr'].write(error.__str__() + '\n')
                    if slaves:
                        for slave in slaves:
                            slave.rollback()
        else:
            parser.print_help()
