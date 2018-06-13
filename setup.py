#! /usr/bin/env python

from setuptools import setup

setup(
    name = 'scapytain',
    version = '0.3.1b0',
    packages=['scapytain'],
    package_data = {'scapytain':['templates/*.[xr]ml', 'htdocs/*/*']},
    scripts = ['bin/scapytain','bin/scapytain_dbutil', 'bin/scapytain_scapyproxy'],
    install_requires=[
        'cherrypy>=3',
        'genshi',
        'sqlobject',
        'formencode',
        'pyopenssl',
        'scapy',
        'highlight',
        'graphviz',
        'trml2pdf',
        'six'
    ]
    # Metadata
    author = 'Philippe BIONDI',
    author_email = 'phil(at)secdev.org',
    description = 'Scapytain: running test campaigns with Scapy',
    license = 'GPLv2',
    # keywords = '',
    url = 'http://www.secdev.org/projects/scapytain/',
)
