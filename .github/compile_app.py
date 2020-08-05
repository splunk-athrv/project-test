#!/usr/bin/env python2.7
# --
# File: compile_app.py
#
# Copyright (c) Phantom Cyber Corporation, 2014-2016
#
# This unpublished material is proprietary to Phantom Cyber.
# All rights reserved. The methods and
# techniques described herein are considered trade secrets
# and/or confidential. Reproduction or distribution, in whole
# or in part, is forbidden except by express written permission
# of Phantom Cyber.
#
# --

import argparse
from pylint import epylint as lint
import glob
import os
import subprocess
import json
import py_compile
import sys
import fnmatch
import imp
import time
import base64
import requests

try:
    from termcolor import colored
except:
    print "Module 'termcolor' does not seem to be installed, Please install it. (pip2.7 can be used)"
    exit(1)

try:
    imp.find_module('flake8')
except:
    print "flake8 does not seem to be installed, Please install it. (pip2.7 can be used)"
    exit(1)

# disable warnings
try:
    requests.packages.urllib3.disable_warnings()
except:
    try:
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    except:
        pass

FLAKE8_IGNORE = "F403,E128,E126,E111,E121,E127,E731,E201,E202,F405,E722,D,W292"
FLAKE8_MAX_LINE_LENGTH = 180
FLAKE8_MAX_COMPLEXITY = 28

# pylint: disable=E1601


def _get_exclude_cmds(app_dir):

    excludes = ["*.swp", "exclude_files.txt", "dont_install", "dont_post_rpm", "deprecated"]

    exclude_file_path = '{0}/exclude_files.txt'.format(app_dir)

    if (os.path.isfile(exclude_file_path)):
        with open(exclude_file_path, 'r') as f:
            excludes.extend([x.strip() for x in f.readlines()])

    exclude_cmd = ' '.join(['--exclude="{}"'.format(x) for x in excludes])
    # print "Exclude command: '{0}'".format(exclude_cmd)

    return exclude_cmd


def _create_app_tarball(app_dir):

    print colored("  Creating tarball...", 'cyan')
    os.chdir('../')
    filename = "{0}.tgz".format(app_dir)
    exclude_cmds = _get_exclude_cmds(app_dir)
    ret_val = os.system('tar {0} -zcf {1} {2}'.format(exclude_cmds, filename, app_dir))

    if (ret_val != 0):
        print colored("  Failed...", 'red')
        exit(1)

    print colored("  ../{0}".format(filename), 'cyan')
    os.chdir('./{0}'.format(app_dir))
    return True


def _remove_status_lines(out_lines):

    out_lines = out_lines.splitlines()

    code_rating = False
    for x in out_lines:
        if ('Your code has been rated' in x):
            code_rating = True
            break

    if (code_rating):
        out_lines = out_lines[:-5]

    out_lines = '\n'.join(out_lines)

    return out_lines


def _compile_py_files(py_files, exclude_flake, exclude_lint):

    error_files = 0
    for py_file in py_files:
        errored_file = False
        print "Compiling: {0}".format(py_file)

        if (exclude_lint is False):
            (pylint_stdout, pylint_strerr) = lint.py_run(py_file, return_std=True)
            out_lines = pylint_stdout.read()
            err_lines = pylint_strerr.read()
            out_lines = _remove_status_lines(out_lines)
            if (len(out_lines) > 0):
                errored_file = True
                print colored(out_lines, 'red')
                if (not args.continue_on_error):
                    print colored("Exiting...", 'cyan')
                    exit(1)
            if (len(err_lines) > 0):
                print err_lines

        if (exclude_flake is False):
            command = ['flake8',
                    '--ignore={0}'.format(FLAKE8_IGNORE),
                    '--max-line-length={0}'.format(FLAKE8_MAX_LINE_LENGTH),
                    '--max-complexity={0}'.format(FLAKE8_MAX_COMPLEXITY),
                    py_file]
            p = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            sout, serr = p.communicate()

            if (len(sout) > 0):
                errored_file = True
                print colored(sout, 'red')
                if (not args.continue_on_error):
                    print colored("Exiting...", 'cyan')
                    exit(1)
            if (len(serr) > 0):
                print serr

        if (errored_file is True):
            error_files += 1
        else:
            py_compile.compile(py_file)

    return error_files


def _install_app(app_tarball):

    sys.path.append('/opt/phantom/www/phantom_ui')
    import import_app as importer

    try:
        importer.main(app_tarball, True)
    except Exception as e:
        return False, e.message

    return True, "App Installed"


def _install_app_rest(app_tarball):

    ip = 'https://' + str(args.install_app_rest[0]) + '/rest/app'
    username = args.install_app_rest[1]
    password = args.install_app_rest[2]

    file_contents = open(app_tarball, 'rb').read()
    encoded_contents = base64.b64encode(file_contents)
    payload = {'app': encoded_contents}
    r = requests.post(ip, auth=(username, password), json=payload, verify=False)
    try:
        r.raise_for_status()
    except Exception as e:
        return False, e.message

    return True, "App Installed"


def _is_contains_same(contains_l, contains_r):

    # both could be None, in that case they are equal
    try:
        contains_l.sort()
        contains_r.sort()
    except:
        pass

    if (contains_l == contains_r):
        return True

    return False


def _validate_package_name(package_name):

    msg = "package_name must use the 'phantom_' prefix, can contain alphanumeric characters, should be lower case"

    if (not package_name.startswith('phantom_')):
        return (False, msg)

    package_name = package_name.replace('_', '')

    if (not package_name.isalnum()):
        return (False, msg)

    if (not all(x.islower() for x in package_name if x.isalpha())):
        return (False, msg)

    return (True, 'package_name is valid')


def _validate_parameter_name(param_name):

    msg = 'Parameter names must only contain alphanumeric characters and underscores, should be lower case.'

    param_name = param_name.replace('_', '')

    if (not param_name.isalnum()):
        return (False, msg)

    if (not all(x.islower() for x in param_name if x.isalpha())):
        return (False, msg)

    return (True, 'Parameter name is valid')


def _validate_contains(contains_list):

    msg = '"{0}". Contains must only contain alphanumeric characters and spaces, should be lower case.'

    if (not contains_list):
        return (True, False, "Empty Contains")

    if (type(contains_list) != list):
        return (False, True, "it must be a list")

    for contains in contains_list:

        contains_mod = contains.replace(' ', '')
        contains_mod = contains_mod.replace('*', '')

        if (not contains_mod):
            continue

        if (not contains_mod.isalnum()):
            return (False, False, msg.format(contains))

        if (not all(x.islower() for x in contains_mod if x.isalpha())):
            return (False, False, msg.format(contains))

    return (True, False, 'Contains is valid')


def _validate_action_name(action_name):

    msg = 'Action names must only contain alpha characters and spaces, should be lower case.'

    action_name_mod = action_name.replace(' ', '')

    if (not action_name_mod.isalpha()):
        return (False, False, msg)

    if (not all(x.islower() for x in action_name_mod)):
        return (False, True, "Action names should be lower case")

    if (action_name.startswith(' ') or action_name.endswith(' ')):
        return (False, True, "Action names should not start or end with spaces")

    # make sure action names are no longer than 3 words
    space_count = action_name.count(' ')

    # make sure action names are no longer than 3 words
    if (not ( 1 <= space_count <= 2)):
        return (False, False, "Action names should be 2 or 3 words long separated by a space")

    return (True, False, 'Action Name is valid')


def _process_action_json(action_json, args):

    render = action_json.get('render')
    if (not render):
        print colored('      Missing render dictionary', 'yellow')

    req_act_dps = ['action_result.data', 'action_result.summary', 'action_result.status', 'action_result.message']

    output = action_json.get('output', [])

    if (not output):
        print colored('      Output data_paths missing', 'yellow')
        return True

    parameters = action_json.get('parameters', {})

    param_dp_contains = dict()

    if (parameters):
        param_dp_contains = {'action_result.parameter.{}'.format(k): v.get('contains') for (k, v) in parameters.iteritems()}
        req_act_dps.extend([x for x in param_dp_contains.keys()])
        for k, v in parameters.iteritems():
            ret_val, msg = _validate_parameter_name(k)
            if (not ret_val):
                print colored('      Parameter name "{0}" is invalid, {1}'.format(k, msg), 'magenta')

            contains_value = v.get('contains')
            if (contains_value):
                ret_val, fatal, msg = _validate_contains(contains_value)
                if (not ret_val):
                    color = 'red' if fatal else 'magenta'
                    print colored('      Parameter "{0}" has invalid contains, {1}'.format(k, msg), color)
                    if (fatal):
                        return False

    contains_matched = True
    for curr_op_item in output:
        req_act_dps = [x for x in req_act_dps if x not in curr_op_item.get('data_path')]

        curr_dp = curr_op_item.get('data_path')

        # before checking if the contains are same, check if the contains of the data path is valied
        ret_val, fatal, msg = _validate_contains(curr_op_item.get('contains'))
        if (not ret_val):
            color = 'red' if fatal else 'magenta'
            print colored('      Data Path "{0}" has invalid contains, {1}'.format(curr_dp, msg), color)
            if (fatal):
                return False

        if ('action_result.parameter' in curr_dp):

            if (curr_dp not in param_dp_contains):
                print colored('      Data path "{0}" found in output, but respective parameter not defined for action'.format(curr_dp), 'magenta')
                contains_matched = False
                continue

            contains = param_dp_contains.get(curr_dp)

            if (not _is_contains_same(contains, curr_op_item.get('contains'))):
                print colored('      Contains for {0} does not match'.format(curr_dp), 'magenta')
                contains_matched = False

    req_act_dps = [x for x in req_act_dps if 'action_result.parameter.ph' not in x]
    if (req_act_dps):
        print colored('      Following required data paths not in output list', 'yellow')
        for req_act_dp in req_act_dps:
            print colored('        {0}'.format(req_act_dp), 'magenta')
    elif(contains_matched):
        print colored('      Done', 'green')

    return True


VALIDATORS = [
        {'key_name': 'package_name', 'validator_function': _validate_package_name, 'fatal': False}]


def _process_app_json(app_json, args):

    print colored('  Processing App Json', 'cyan')

    for curr_validator in VALIDATORS:

        # get the value of the key
        curr_value = app_json.get(curr_validator['key_name'])

        ret_val, message = curr_validator['validator_function'](curr_value)

        if (not ret_val):

            color = 'red' if (curr_validator['fatal']) else 'magenta'
            print colored('      Key "{0}" is invalid. {1}'.format(curr_validator['key_name'], message), color)

            if (curr_validator['fatal']):
                return False

    print colored('  Processing actions', 'cyan')

    actions = app_json.get('actions', [])

    if (not actions):
        print colored('No Action found in app', 'yellow')
        return True

    for action in actions:

        name = action.get('action')
        print colored('    {0}'.format(name), 'cyan')
        if (not name):
            print colored('Un-named Action found in app', 'yellow')

        ret_val, fatal, msg = _validate_action_name(name)
        if (not ret_val):
            color = 'red' if fatal else 'magenta'
            print colored('      Action name "{0}" is invalid. {1}'.format(name, msg), color)
            if (fatal):
                return False

        if (name == 'test connectivity'):
            print colored('      No further processing coded for this action', 'yellow')
            continue

        ret_val = _process_action_json(action, args)

        if (not ret_val):
            return ret_val

    return True


def _find_app_json_file(app_dir, args):

    print colored('Validating App Json', 'cyan')

    # Create the glob to the json file
    json_file_glob = './*.json'

    # Check if it exists
    files_matched = glob.glob(json_file_glob)

    if (not files_matched):
        print colored('App Json file not found.', 'red')
        return (False, None)

    for json_file in files_matched:
        print colored('  Working on: {0}'.format(json_file), 'cyan')

        with open(json_file) as f:
            try:
                app_json = json.load(f)
            except Exception as e:
                print colored('   Unable to load due to exception: "{0}"'.format(str(e)), 'cyan')
                continue

            if 'appid' not in app_json:
                print colored('   Did not find appid in json, ingoring.', 'cyan')
                continue

            required_fields = ['appid', 'name', 'description', 'publisher', 'package_name', 'type',
                    'license', 'main_module', 'app_version', 'product_vendor',
                    'product_name', 'product_version_regex', 'min_phantom_version', 'logo', 'configuration', 'actions']

            found_all = True
            for field in required_fields:
                if field not in app_json:
                    print colored('    Did not find required field, "{0}" in json, ignoring.'.format(field), 'cyan')
                    found_all = False
                    break

            if not found_all:
                continue

            print colored('    Looks like an app json', 'cyan')
            return (True, app_json)

    return (False, None)


def main(args):

    # CD into the app directory, everything happens in relation to that
    print colored("cd'ing into {0}".format(args.app_dir), 'cyan')
    os.chdir(args.app_dir)

    app_dir = os.path.split(os.getcwd())[1]

    if (args.create_tarball):
        _create_app_tarball(app_dir)
        print colored("Done...", 'cyan')
        return 0

    error_files = 0

    if (args.single_pyfile is not None):
        py_files = glob.glob(args.single_pyfile)
        error_files += _compile_py_files(py_files, args.exclude_flake, args.exclude_lint)
        # ignore everything else
        return 0

    # make a list of files that are to be ignored
    ignore_fnames = []

    if (args.ignore_file):
        if (os.path.isfile(args.ignore_file)):
            with open(args.ignore_file) as f:
                ignore_fnames = f.readlines()
                # clean up the list a bit
                ignore_fnames = [x.strip() for x in ignore_fnames if len(x.strip()) > 0]
                if (ignore_fnames):
                    print colored('Will be ignoring: {0}'.format(', '.join(ignore_fnames)), 'cyan')

    py_files = glob.glob("./*.py")
    if (ignore_fnames):
        # remove the files that we are supposed to ignore
        py_files = [x for x in py_files if not [y for y in ignore_fnames if fnmatch.fnmatch(x, y)]]
    error_files = _compile_py_files(py_files, args.exclude_flake, args.exclude_lint)

    found, app_json = _find_app_json_file(app_dir, args)
    if (not found):
        print colored("Unable to find a valid app json, Exiting...", 'red')
        return 1

    ret_val = _process_app_json(app_json, args)

    if (not ret_val):
        print colored("Unable to find process app_json, Exiting...", 'red')
        return 1

    if (error_files > 0):
        return 1

    if (args.install_app is True or args.install_app_rest is not None):

        func = _install_app_rest
        if args.install_app is True:
            print colored("Installing app...", 'cyan')
            func = _install_app
        else:
            print colored("Installing app over REST...", 'cyan')

        time.sleep(2)

        _create_app_tarball(app_dir)

        os.chdir('../')
        print colored("  Calling installer...", 'cyan')

        ret_val, err_string = func("{0}.tgz".format(app_dir))

        if (ret_val is False):
            print colored("  Error: {0}".format(err_string), 'red')
            return 1

        os.chdir('./{0}'.format(app_dir))
        # exit(0)
        print colored("  Success", 'green')
        return 0

    print colored("Done", 'green')
    return 0


if __name__ == '__main__':

    args = None

    argparser = argparse.ArgumentParser()

    arggroup = argparser.add_mutually_exclusive_group(required=True)
    arggroup.add_argument('-s', '--single_pyfile', help='Compile a Single python file and exit')
    arggroup.add_argument('-i', '--install_app', help='Install app after compilation', action='store_true', default=False)
    arggroup.add_argument('-r', '--install_app_rest', help='Install app over REST after compilation', metavar=("IP", "Username", "Password"), default=False, nargs=3)
    arggroup.add_argument('-t', '--create_tarball', help='Only create the app tarball and exit, compilation or installation is not carried out', action='store_true', default=False)
    arggroup.add_argument('-c', '--compile_app', help='Compile the app and exit', action='store_true', default=False)

    argparser.add_argument('-a', '--app_dir', help='app directory', default='./')
    argparser.add_argument('-d', '--exclude_flake', help='Dont run flake', action='store_true', default=False)
    argparser.add_argument('-e', '--continue_on_error', help='Stop on error', action='store_true', default=False)
    argparser.add_argument('-g', '--ignore_file', help='files that contains the list of files to ignore, by default it is .compile_app.ignore', default='./.compile_app.ignore')
    argparser.add_argument('-x', '--exclude_lint', help='Exclude running pylint', action='store_true', default=False)
    args = argparser.parse_args()

    ret_val = main(args)

    exit(ret_val)
