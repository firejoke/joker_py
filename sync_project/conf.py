# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019/11/5 17:53
"""The Module Has Been Build for generate conf"""
import sys
from pathlib import Path

import yaml

from Colorer_log import logger, INFO, WARN, ERROR, DEBUG, set_log_handler


CONF = dict()
LOG = lambda: logger


def load_conf(**kwargs):
    """
    读取配置文件, 或者通过kwargs添加改变配置
    :return: CONF, LOG
    """
    global logger, CONF
    try:
        conf_path = Path(__file__).parent.joinpath('sync_project.yaml')
        with open(conf_path, 'r') as f:
            CONF = yaml.safe_load(f)
        if isinstance(CONF['Sync'], list):
            if kwargs.get('logger_Level'):
                log_level = kwargs.get('logger_Level')
            else:
                log_level = CONF.get('logger_Level')
            if log_level:
                if log_level in ('info', 'INFO'):
                    logger.setLevel(INFO)
                    logger.info('logger level change to info')
                elif log_level in ('warn', 'WARN', 'warning', 'WARNING'):
                    logger.setLevel(WARN)
                    logger.warning('logger level change to warn')
                elif log_level in ('error', 'ERROR'):
                    logger.setLevel(ERROR)
                elif log_level in ('debug', 'DEBUG'):
                    logger = set_log_handler(logger, 'a', 't')
                    logger.setLevel(DEBUG)
                    logger.debug('logger level change to debug')
                elif log_level:
                    logger.error('logger_Level value error')
        else:
            logger.error('type error: Sync require list')
            sys.exit(1)
    except IOError:
        logger.error('not found config: ./sync_project.yaml')
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error("yaml syntax error: " + e.__str__())
        sys.exit(1)


load_conf()


