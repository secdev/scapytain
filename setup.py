#! /usr/bin/env python

from distutils.core import setup

setup(
    name = 'scapytain',
    version = '0.3.1beta',
    packages=['scapytain'],
    package_data = {'scapytain':['templates/*.[xr]ml', 'htdocs/*/*']},
    data_files = [ ('/etc',['scapytain/scapytainrc']) ] ,
    scripts = ['bin/scapytain','bin/scapytain_dbutil', 'bin/scapytain_scapyproxy'],
    # Metadata
    author = 'Philippe BIONDI',
    author_email = 'phil(at)secdev.org',
    description = 'Scapytain: running test campaigns with Scapy',
    license = 'GPLv2',
    # keywords = '',
    url = 'http://www.secdev.org/projects/scapytain/',
)
