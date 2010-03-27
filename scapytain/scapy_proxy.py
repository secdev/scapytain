## This file is part of Scapytain
## See http://www.secdev.org/projects/scapytain for more informations
## Copyright (C) Philippe Biondi <phil@secdev.org>
## This program is published under a GPLv2 license

import os,subprocess,struct
import logging
from error import ScapytainException

log = logging.getLogger("scapytain")


class ScapyProxy:
    def __init__(self, scapy_proxy, scapy_path, modules):
        cmd = scapy_proxy.split()
        cmd += ["-s" , scapy_path]
        for m in modules:
            cmd += ["-e", m]
        self.peer_cmd = cmd

    class Proxy:
        cmd = None
        def __init__(self, cmd):
            log.info("Running %s" % cmd)
            self.peer = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        def send(self, test):
            if type(test) is unicode:
                test = test.encode("utf-8")
            self.peer.stdin.write(struct.pack("!I", len(test)))
            self.peer.stdin.write(test)
        def recv(self):
            val = self.peer.stdout.read(1)
            if not val:
                raise ScapytainException("Something wrong with the child")
            l, = struct.unpack("!I", self.peer.stdout.read(4))
            res = self.peer.stdout.read(l).decode("utf8")
            l, = struct.unpack("!I", self.peer.stdout.read(4))
            exn = self.peer.stdout.read(l).decode("utf8")
            return ord(val),res,exn
        def close(self):
            self.peer.stdin.write("\xff\xff\xff\xff")
        def run(self, test):
            self.send(test)
            return self.recv()
        def __del__(self):
            try:
                self.close()
            except:
                pass
            
    def get_proxy(self):
        return self.Proxy(self.peer_cmd)
    
    def run(self,cmds):
        proxy = self.get_proxy()
        return proxy.run(cmds)

    def run_tests_from_tspec(self, tests, init=None):
        return self.run_tests(tests, lambda r: r.tests[-1].code, init=init)

    def run_tests_from_tcode(self, tests, init=None):
        return self.run_tests(tests, lambda r: r.code, init=init)

    def run_tests_from_results(self, results, init=None):
        return self.run_tests(results, lambda r: r.test.code, init=init)

    def run_tests(self, lst, key, init=None):
        proxy = self.get_proxy()
        if init:
            res_val,res,exn = proxy.run(init)
            if res_val != 1:
                log.error("Init code returned %s" % ["failed", "sucess", "exception"][res_val])
                if res_val == 2:
                    log.error("Exception = [%r]" % exn)
        for x in lst:
            yield x,proxy.run(key(x))
        

    def run_tests_with_dependencies(self, lst, key, init=None):
        proxy = self.get_proxy()
        if init:
            res_val,res,exn = proxy.run(init)
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
            
            if depfailed:
                res_val,res,exn = result = 3,"",None
            else:
                res_val,res,exn = result = proxy.run(code)
            if tcode == tspec.tests[-1]:
                done.append(tspec)
                if res_val != 1:
                    failed.append(tspec)
            yield x,result
            
        
