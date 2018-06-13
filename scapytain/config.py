#! /usr/bin/env python

## This file is part of Scapytain
## See http://www.secdev.org/projects/scapytain for more informations
## Copyright (C) Philippe Biondi <phil@secdev.org>
## This program is published under a GPLv2 license

from __future__ import absolute_import
import os,logging
from threading import Semaphore
import six.moves.configparser
log = logging.getLogger("scapytain")
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
log.addHandler(console_handler)


class conf:
    _loaded = False
    _sem = Semaphore(1)
    # paths
    templates_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
    static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'htdocs'))
    highlight_path = "highlight"
    modules = []
    # server
    port = 8080
    production = True
    ssl_certificate = None
    ssl_key = None
    auth = True
    database = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scapytain.db")).replace("\\", "/")
    db = "sqlite:/" + database
    loglevel=1
    # users
    users = {}


def get_config(configfile=None):
    conf._sem.acquire()
    if not conf._loaded:
        
        config = six.moves.configparser.ConfigParser()
        if configfile is None:
            configfile=['scapytainrc',os.path.expanduser('~/.scapytainrc'),'/etc/scapytainrc']
        cf=config.read(configfile)
        log.info("Configuration loaded from [%s]" % ":".join(cf))
        
        for sec in config.sections():
            for opt,optarg in config.items(sec):
                if sec == "paths":
                    if opt == "scapy":
                        conf.scapy_path = config.get(sec,opt)
                    elif opt == "scapyproxy":
                        conf.scapyproxy_path = optarg
                    elif opt == "modules":
                        conf.modules += optarg.split(":")
                    elif opt == "highlight":
                        conf.highlight_path = optarg
                    elif opt == "templates":
                        conf.templates_path = optarg
                    elif opt == "static":
                        conf.static_path = optarg
                elif sec == "server":
                    if opt == "port":
                        conf.port = config.getint(sec, opt)
                    elif opt == "production":
                        conf.production = config.getboolean(sec, opt)
                    elif opt == "ssl_certificate":
                        conf.ssl_certificate = optarg
                    elif opt == "ssl_key":
                        conf.ssl_key = optarg
                    elif opt == "auth":
                        conf.auth = config.getboolean(sec, opt)
                    elif opt == "database":
                        conf.database = optarg
                        conf.db = "sqlite:/" + database
                elif sec == "users":
                    conf.users = dict(config.items(sec))
    
        log.setLevel(conf.loglevel)
        conf._loaded = True
    conf._sem.release()
    return conf

