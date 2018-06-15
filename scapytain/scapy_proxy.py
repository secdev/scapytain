## This file is part of Scapytain
## See http://www.secdev.org/projects/scapytain for more informations
## Copyright (C) Philippe Biondi <phil@secdev.org>
## This program is published under a GPLv2 license

from __future__ import absolute_import
import os, sys, importlib
import logging
from .error import ScapytainException
import six

from scapy import all as scapy

log = logging.getLogger("scapytain")


class ScapyProxy(object):
    def __init__(self, modules):
        self.globals = importlib.import_module(".all", "scapy").__dict__
        for module in modules:
            output, res = scapy.load_contrib(module, globals_dict=self.globals)
            if not (res is None or res):
                print(output)
        self.pre_run()

    def pre_run(self):
        if scapy.consts.WINDOWS:
            if not scapy.pcap_service_status()[2]:
                scapy.pcap_service_start()
            scapy.route_add_loopback()
    
    def run(self, cmds):
        sys.last_value = None
        output, res = scapy.autorun_get_html_interactive_session(cmds)
        if res is None or res:
            res = 1
        elif sys.last_value is not None:
            res = 2
        else:
            res = 0
        err = sys.last_value
        exn = "%s: %s" % (err.__class__.__name__, str(err))
        return res, output, exn

    def run_tests_from_tspec(self, tests, init=None):
        return self.run_tests(tests, lambda r: r.tests[-1].code, init=init)

    def run_tests_from_tcode(self, tests, init=None):
        return self.run_tests(tests, lambda r: r.code, init=init)

    def run_tests_from_results(self, results, init=None):
        return self.run_tests(results, lambda r: r.test.code, init=init)

    def run_tests(self, lst, key, init=None):
        if init:
            res_val, res, exn = self.run(init)
            if res_val != 1:
                log.error("Init code returned %s" % ["failed", "sucess", "exception"][res_val])
                if res_val == 0:
                    log.error("Exception = [%r]" % exn)
        for x in lst:
            yield x, self.run(key(x))
        

    def run_tests_with_dependencies(self, lst, key, init=None, keywords=None):
        if init:
            res_val, res, exn = self.run(init)
            if res_val != 1:
                log.error("Init code returned %s" % ["failed", "sucess", "exception"][res_val])
                if res_val == 2:
                    log.error("Exception = [%r]" % exn)

            
        done = []
        failed = []
        while lst:
            for i,x in enumerate(lst):
                found=True
                depfailed=False
                for p in key(x).test_spec.parents:
                    if p in failed:
                        depfailed=True
                    if p not in done:
                        found=False
                        break
                if found:
                    break
            del(lst[i])
            tcode = key(x)
            code = tcode.code
            tspec = tcode.test_spec
            if keywords:
                if not keywords(tcode):
                    done.append(tspec)
                    yield x, (4,"",None) # In the list it's 4, the real status number is 8
                    continue
            
            if depfailed:
                res_val,res,exn = result = 3,"",None
            else:
                res_val,res,exn = result = self.run(code)
            if tcode == tspec.tests[-1]:
                done.append(tspec)
                if res_val != 1:
                    failed.append(tspec)
            yield x, result
            
        
