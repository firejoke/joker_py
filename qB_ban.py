# -*- coding: utf-8 -*-
import re
from logging.config import dictConfig
from logging import Formatter, getLogger
from pathlib import Path
from pprint import pformat

import requests
import json
import time


def get_torrents(
    url, /, state: str = None, category: str = None, tag: str = None,
    sort: str = None, reverse: bool = False, limit: int = None,
    offset: int = None, hashes: list = None
) -> list[dict]:
    content = {'rid': 0}
    if state:
        content.update(filter=state)
    if category:
        content.update(category=category)
    if tag:
        content.update(tag=tag)
    if sort:
        content.update(sort=sort)
    if reverse:
        content.update(reverse=reverse)
    if limit:
        content.update(limit=limit)
    if offset:
        content.update(offset=offset)
    if hashes:
        content.update(hashes="|".join(hashes))
    res = requests.get(url, params=content)
    if res.status_code != 200:
        return []
    return json.loads(res.text)


def get_peers(url, hash_id) -> list[dict]:
    content = {'rid': 0, 'hash': hash_id}
    res = requests.get(url, params=content)
    if res.status_code != 200:
        return []
    return json.loads(res.text)['peers']


def ban_peers(url, peers: list):
    peers = "|".join(peers)
    content = {"peers": peers}
    return requests.post(url, data=content)


class BanPeerPolicy(object):
    ban_clients = re.compile(r'(?i)-xl0012|xunlei|xfplay|qqdownload|7\.')

    def __init__(self, torrent):
        self.torrent = torrent
        self.min_uploaded = 0.01
        self.min_downloaded = 0.01
        self.min_relevance = 0.02
        self.min_download_speed = 0.8 * 1024
        self.max_upload_speed = 8 * 1024
        self.download_policy = {
            "and": [
                self.check_uploaded,
                self.check_downloaded,
                self.check_download_speed,
                self.check_upload_speed,
                self.check_relevance,
                self.check_client,
            ],
            "or": []
        }
        self.upload_policy = {
            "and": [
                self.check_client,
            ],
            "or": [],
        }
        if self.torrent["state"].lower() in ("downloading", "forceddl"):
            self.policy = self.download_policy
        elif self.torrent["state"].lower() in ("uploading", "forcedup"):
            self.policy = self.upload_policy

    def check_uploaded(self, peer):
        log.debug(f"{peer['ip']}.uploaded: {peer['uploaded']}")
        return peer["uploaded"] / self.torrent["size"] >= \
            self.min_uploaded

    def check_downloaded(self, peer):
        log.debug(f"{peer['ip']}.downloaded: {peer['downloaded']}")
        return peer["downloaded"] / self.torrent["size"] < \
            self.min_downloaded

    def check_download_speed(self, peer):
        log.debug(f"{peer['ip']}.dl_speed: {peer['dl_speed']}")
        return peer["dl_speed"] < self.min_download_speed

    def check_upload_speed(self, peer):
        log.debug(f"{peer['ip']}.up_speed: {peer['up_speed']}")
        return peer["up_speed"] > self.max_upload_speed

    def check_relevance(self, peer):
        log.debug(f"{peer['ip']}.relevance: {peer['relevance']}")
        return peer["relevance"] >= self.min_relevance

    def check_client(self, peer):
        log.debug(f"{peer['ip']}.client: {peer['client']}")
        return self.ban_clients.match(peer["client"])


if __name__ == "__main__":
    DEBUG = False
    RootPath = Path(__file__).parent
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "debug": {
                "format": "%(asctime)s %(levelname)s %(name)s "
                          "[%(processName)s(%(process)d):"
                          "%(threadName)s(%(thread)d)] "
                          "%(pathname)s[%(funcName)s:%(lineno)d] "
                          "- %(message)s"
            },
            "verbose": {
                "format": "%(asctime)s %(levelname)s %(name)s "
                          "%(module)s [%(funcName)s:%(lineno)d] "
                          "- %(message)s"
            },
            "simple": {
                "format": "%(asctime)s %(levelname)s %(name)s "
                          "- %(message)s"
            },
        },
        "handlers": {
            "root": {
                "level": "DEBUG",
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": RootPath / "qB_ban.log",
                "encoding": "utf-8",
                "when": "W0",
                "backupCount": 6,
                "formatter": "simple"
            },
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
            
        },
        "loggers": {
            "root": {
                "handlers": ["root"],
                "level": "INFO" if not DEBUG else "DEBUG",
            },
        },
    }
    dictConfig(LOGGING)
    log = getLogger()
    github_trackers_url = 'https://raw.githubusercontent.com/ngosang' \
                          '/trackerslist/master/trackers_all_ip.txt'

    root_url = 'http://127.0.0.1:9080'
    get_preferences_url = root_url + '/api/v2/app/preferences'
    set_preferences_url = root_url + '/api/v2/app/setPreferences'
    torrents_url = root_url + '/api/v2/torrents/info'
    peers_url = root_url + '/api/v2/sync/torrentPeers'
    ban_peers_url = root_url + '/api/v2/transfer/banPeers'

    log.info("=" * 80)
    log.info("get preferences:")
    preferences = json.loads(
        requests.get(get_preferences_url).text.encode("utf-8")
    )
    for _key, _value in preferences.items():
        log.info(f"{_key}: {_value}")
    log.info("=" * 80)

    try:
        github_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                      'image/webp,image/apng,*/*;q=0.8,'
                      'application/signed-exchange;v=b3 ',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/108.0.5359.125 Safari/537.36 ',
            'Accept-Encoding': 'gzip, deflate, br',
        }
        proxies = {
            "http": "127.0.0.1:7890",
            "https": "127.0.0.1:7890",
        }
        _res = requests.get(
            github_trackers_url, proxies=proxies, headers=github_headers,
            timeout=10,
            )
        _trackers = _res.text
        log.info('加载tracker服务器列表成功。')
    except requests.RequestException:
        _trackers = None
        log.error('加载tracker服务器列表失败。')
    if _trackers and _trackers != preferences["add_trackers"]:
        _params = {'add_trackers_enabled': True, 'add_trackers': _trackers}
        _content = {'json': json.dumps(_params)}
        requests.post(set_preferences_url, data=_content)
    log.info('过滤器初始化成功。')

    while 1:
        _torrents = get_torrents(torrents_url)
        for _torrent in _torrents:
            if _torrent["state"].lower() in (
                    "uploading", "downloading", "forcedup", "forceddl"
            ):
                ban_policy = BanPeerPolicy(torrent=_torrent)
                log.debug(f"torrent name: {_torrent['name']}")
                log.debug(f"torrent params:")
                for _param, _value in _torrent.items():
                    log.debug(f"{_param}: {pformat(_value)}")
                for _peer in get_peers(peers_url, _torrent["hash"]).values():
                    log.debug(f'peer ip: {_peer["ip"]}')
                    log.debug(f"peer params:")
                    for _param, _value in _peer.items():
                        log.debug(f'{_param}: {pformat(_value)}')
                    log.debug(f'{pformat(_peer)}')
                    and_res = {
                        func.__name__: func(_peer)
                        for func in ban_policy.policy["and"]
                    }
                    or_res = {
                        func.__name__: func(_peer)
                        for func in ban_policy.policy["or"]
                    }
                    if and_res.values() and all(and_res.values()) \
                            or any(or_res.values()):
                        log.info("=" * 80)
                        log.info(f"and_res: {and_res}")
                        log.info(f"or_res: {or_res}")
                        log.info(
                            f"leeches were detected in this torrent: "
                            f"{_torrent['name']}({_torrent['progress']})"
                        )
                        log.info("will be banned:")
                        for _key, _value in _peer.items():
                            log.info(f'{_key}: {_value}')
                        ban_peers(
                            ban_peers_url,
                            [f"{_peer['ip']}" f":{_peer['port']}"]
                        )
                        time.sleep(1)
                time.sleep(1)
        time.sleep(1)
