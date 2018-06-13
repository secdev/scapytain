# Scapytain

See <http://www.secdev.org/projects/scapytain> for more informations
Copyright (C) Philippe Biondi \<<phil@secdev.org>\> This program is
published under a GPLv2 license

Warning: This is beta software. You've been warned.

# Installation

## 1\. Dependencies

This package depends on:

  - python-cherrypy3
  - python-genshi
  - python-sqlobject
  - python-formencode
  - python-pyopenssl
  - python-pysqlite (included in standard library with Python \>= 2.5)
  - scapy
  - highlight
  - graphviz

## 2\. Install libraries and programs

Untar the archive and run

> python setup.py install

## 3\. Configure Scapytain

Edit /etc/scapytainrc.

Set the database URI, for instance:

> database = sqlite:///var/lib/scapytain/scapytain.db

The scapyproxy parameter holds the command to execute the Scapy proxy,
scapytain\_scapyproxy by default. The web application communicates with
the proxy through stdin and stdout. The proxy is the only part that has
to run as root and be able to import Scapy. Thus, it is pessible to have
the web application run unprivileged and have

> scapyproxy = sudo scapytain\_scapyproxy

You can even have Scapy run on another machine:

> scapyproxy = ssh <probe@10.0.0.10> sudo scapytain\_scapyproxy

If you need authentication, add users in the file and make it readable
by the application only. If you do not need authentication, set "auth"
parameter to
false.

<aside class="warning">
WARNING: any user of this application can become root on the box where Scapy runs.
</aside>

If you need SSL: create a certificate and a key. For instance:

> openssl req -new -x509 -nodes -keyout scapytain.key -out scapytain.crt

Then fill ssl\_certificate and ssl\_key with paths to these files.

## 4\. Create the database

Create the database path that you configured in /etc/scapytainrc:

> mkdir /var/lib/scapytain

Then create the database with the user under which you intend to run
scapytain:

> scapytain\_dbutil -c

## 5\. Run Scapytain

> scapytain

Now you can browse <http://localhost:8080> (or whatever TCP port you put
in the configuration file). Click on the HELP link on the top left of
the screen.

If you encounter internal server errors, you can set

> production = False

in /etc/scapytainrc and you should have more output and backtraces in
the console you ran scapytain into.