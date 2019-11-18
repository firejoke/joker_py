# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2019/11/5 17:53
"""The Module Has Been Build for generate conf"""
import sys
from pathlib import Path

import yaml

from Colorer_log import (
    logger, INFO, WARN, ERROR, DEBUG, TerminalH, FileH, DEBUG_FORMAT, )


CONF = dict()
LOG = lambda: logger
DebugMode = lambda: CONF.get('DebugMode')


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
        CONF.update(kwargs)
        logger.warning(f'CONF:\n{CONF}')
        if isinstance(CONF['Sync'], list):
            log_level = CONF.get('LogLevel')
            if log_level:
                if log_level in ('info', 'INFO'):
                    logger.setLevel(INFO)
                    logger.info('logger level: info')
                elif log_level in ('warn', 'WARN', 'warning', 'WARNING'):
                    logger.setLevel(WARN)
                    logger.warning('logger level: warn')
                elif log_level in ('error', 'ERROR'):
                    logger.setLevel(ERROR)
                elif log_level in ('debug', 'DEBUG'):
                    FileH.setFormatter(DEBUG_FORMAT)
                    TerminalH.setFormatter(DEBUG_FORMAT)
                    logger.addHandler(TerminalH)
                    logger.setLevel(DEBUG)
                    logger.debug('logger level: debug')
                elif log_level:
                    logger.error('logger_Level value error')
            if CONF.get('LogOut') == 'file':
                for h in logger.handlers:
                    logger.removeHandler(h)
                logger.addHandler(FileH)
            if CONF.get('LogOut') == 'terminal':
                for h in logger.handlers:
                    logger.removeHandler(h)
                logger.addHandler(TerminalH)
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


