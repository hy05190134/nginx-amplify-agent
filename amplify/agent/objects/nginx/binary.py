# -*- coding: utf-8 -*-
import re

from amplify.agent.common.util import subp

__author__ = "Mike Belov"
__copyright__ = "Copyright (C) Nginx, Inc. All rights reserved."
__credits__ = ["Mike Belov", "Andrei Belov", "Ivan Poluyanov", "Oleg Mamontov", "Andrew Alexeev"]
__license__ = ""
__maintainer__ = "Mike Belov"
__email__ = "dedm@nginx.com"

DEFAULT_PREFIX = '/usr/local/nginx'
DEFAULT_CONFPATH = 'conf/nginx.conf'


def nginx_v(bin_path):
    """
    call -V and parse results

    :param bin_path str - path to binary
    :return {} - see result
    """
    result = {
        'version': None,
        'plus': {'enabled': False, 'release': None},
        'ssl': {'built': None, 'run': None},
        'configure': {}
    }

    _, nginx_v_err = subp.call("%s -V" % bin_path)
    for line in nginx_v_err:
        # SSL stuff
        if line.lower().startswith('built with') and 'ssl' in line.lower():
            lib_name, lib_version, lib_day, lib_month, lib_year = line.split()[2:7]
            lib_date = ' '.join((lib_day, lib_month, lib_year))
            result['ssl']['built'] = [lib_name, lib_version, lib_date]

            # example: "built with OpenSSL 1.0.2g-fips 1 Mar 2016 (running with OpenSSL 1.0.2g 1 Mar 2016)"
            if '(running with' in line.lower() and ')' in line.lower():
                parenthetical = line.split('(', 1)[1].rsplit(')', 1)[0]
                lib_name, lib_version, lib_day, lib_month, lib_year = parenthetical.split()[2:7]
                lib_date = ' '.join((lib_day, lib_month, lib_year))

            result['ssl']['run'] = [lib_name, lib_version, lib_date]

        elif line.lower().startswith('run with') and 'ssl' in line.lower():
            lib_name, lib_version, lib_day, lib_month, lib_year = line.split()[2:7]
            lib_date = ' '.join((lib_day, lib_month, lib_year))
            result['ssl']['run'] = [lib_name, lib_version, lib_date]

        parts = line.split(':', 1)
        if len(parts) < 2:
            continue

        # parse version
        key, value = parts
        if key == 'nginx version':
            # parse major version
            major_parsed = re.match('.*/([\d\w\.]+)', value)
            result['version'] = major_parsed.group(1) if major_parsed else value.lstrip()

            # parse plus version
            if 'plus' in value:
                plus_parsed = re.match('.*\(([\w\-]+)\).*', value)
                if plus_parsed:
                    result['plus']['enabled'] = True
                    result['plus']['release'] = plus_parsed.group(1)

        # parse configure
        elif key == 'configure arguments':
            arguments = _parse_arguments(value)
            result['configure'] = arguments

    return result


def get_prefix_and_conf_path(cmd, configure=None):
    """
    Finds prefix and path to config based on running cmd and optional configure args

    :param running_binary_cmd: full cmd from ps
    :param configure: parsed configure args from nginx -V
    :return: prefix, conf_path
    """
    cmd = cmd.replace('nginx: master process ', '')
    params = iter(cmd.split())

    # find bin path
    bin_path = next(params)
    prefix = None
    conf_path = None


    # try to find config and prefix
    for param in params:
        if param == '-c':
            conf_path = next(params, None)
        elif param == '-p':
            prefix = next(params, None)

    # parse nginx -V
    parsed_v = nginx_v(bin_path)
    if configure is None:
        configure = parsed_v['configure']

    # if prefix was not found in cmd - try to read it from configure args
    # if there is no key "prefix" in args, then use default
    if not prefix:
        prefix = configure.get('prefix', DEFAULT_PREFIX)
    if not conf_path:
        conf_path = configure.get('conf-path', DEFAULT_CONFPATH)

    # remove trailing slashes from prefix
    prefix = prefix.rstrip('/')

    # start processing conf_path
    # if it has not an absolutely path, then we should add prefix to it
    if not conf_path.startswith('/'):
        conf_path = '%s/%s' % (prefix, conf_path)

    return bin_path, prefix, conf_path, parsed_v['version']


def _parse_arguments(argstring):
    """
    Parses argstring from nginx -V

    :param argstring: configure string
    :return: {} of parsed string
    """
    if argstring.startswith('configure arguments:'):
        __, argstring = argstring.split(':', 1)

    arg_parts = iter(filter(len, argstring.split(' --')))
    arguments = {}

    for part in arg_parts:
        # if the argument is a simple switch, add it and move on
        if '=' not in part:
            arguments[part] = True
            continue

        key, value = part.split('=', 1)

        # this fixes quoted argument values that broke from the ' --' split
        if value.startswith("'"):
            while not value.endswith("'"):
                value += ' --' + next(arg_parts)

        # if a key is set multiple times, values are stored as a list
        if not key in arguments:
            arguments[key] = value
        elif not isinstance(arguments[key], list):
            arguments[key] = [arguments[key], value]
        else:
            arguments[key].append(value)

    return arguments
