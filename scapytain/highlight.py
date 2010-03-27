#! /usr/bin/env python

## This file is part of Scapytain
## See http://www.secdev.org/projects/scapytain for more informations
## Copyright (C) Philippe Biondi <phil@secdev.org>
## This program is published under a GPLv2 license

import os,config

conf = config.get_config()

HIGHLIGHT="%s -u utf-8 -S py" % conf.highlight_path

def highlight_python(py):
    if type(py) is unicode:
        py = py.encode("utf-8")

    w,r = os.popen2(HIGHLIGHT)
    try:
        w.write(py)
        w.close()
    except IOError:
        pass
    
    html = r.read()
    if html == "":
        html="<pre>%s</pre>" % py
    else:
        html=html[html.find("<pre"):html.find("</pre>")+7]
    return html.decode("utf-8")
    
