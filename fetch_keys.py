#!/usr/bin/env python
"""
Standalone script to fetch all ssh public keys for users in a github org

Fetches these public keys and can write them to a file. The users must be
listed as "public" in the organization.

"""
import os
import argparse
import shutil
import stat
import subprocess
import sys
import tempfile
from distutils.spawn import find_executable


# Python 2 & 3
try:
    from urllib import urlretrieve
except ImportError:
    from urllib.request import urlretrieve

VENV_VERSION = '1.11.6'
VENV_URL = ("https://pypi.python.org/packages/source/v/"
            "virtualenv/virtualenv-%s.tar.gz" % VENV_VERSION)
DEPENDENCIES = {
    'requests': 'requests'
}

def bootstrap_virtualenv(env):
    """
    Activate a virtualenv, creating it if necessary.
    Parameters
    ----------
    env : str
        Path to the virtualenv
    """
    if not os.path.exists(env):
        # If virtualenv command exists, use that
        if find_executable('virtualenv') is not None:
            cmd = ['virtualenv'] + [env]
            subprocess.check_call(cmd)
        else:
            # Otherwise, download virtualenv from pypi
            path = urlretrieve(VENV_URL)[0]
            subprocess.check_call(['tar', 'xzf', path])
            subprocess.check_call(
                [sys.executable,
                 "virtualenv-%s/virtualenv.py" % VENV_VERSION,
                 env])
            os.unlink(path)
            shutil.rmtree("virtualenv-%s" % VENV_VERSION)
        print("Created virtualenv %s" % env)

    executable = os.path.join(env, 'bin', 'python')
    os.execv(executable, [executable] + sys.argv)


def is_inside_virtualenv(env):
    return any((p.startswith(env) for p in sys.path))


def install_lib(venv, name, pip_name=None):
    try:
        __import__(name)
    except ImportError:
        if pip_name is None:
            pip_name = name
        pip = os.path.join(venv, 'bin', 'pip')
        subprocess.check_call([pip, 'install', pip_name])

def main():
    """ Generate a ssh authorized_keys file from a github org """
    parser = argparse.ArgumentParser(description=main.__doc__)
    default_venv_dir = os.path.join(tempfile.gettempdir(), 'ssh_gen_keys_env')
    parser.add_argument('-v', help="path to virtualenv (default %(default)s)",
                        default=default_venv_dir)
    parser.add_argument('-f', help="The file to write to (default is stdout)")
    parser.add_argument('-t', help="Access token")
    parser.add_argument('organization', help="The name of the github organization")
    parser.add_argument('team', help="The name of the team", nargs='?')
    args = parser.parse_args()

    venv_dir = args.v
    if not is_inside_virtualenv(venv_dir):
        bootstrap_virtualenv(venv_dir)
        return
    for name, pip_name in DEPENDENCIES.items():
        install_lib(venv_dir, name, pip_name)

    import requests
    def get(uri):
        """ Helper method for hitting the github API """
        headers = {}
        if args.t is not None:
            headers['Authorization'] = 'token %s' % args.t
        url = 'https://api.github.com%s' % uri
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if not resp.ok:
            if 'message' in data:
                print(data['message'])
            if 'documentation_url' in data:
                print(data['documentation_url'])
        resp.raise_for_status()
        return data

    if args.team is not None:
        teams = get("/orgs/%s/teams" % args.organization)
        team = None
        for t in teams:
            if args.team == t['slug'] or args.team == t['name']:
                team = t
                break
        if team is None:
            print("Could not find team %r" % args.team)
            sys.exit(1)
        members = get("/teams/%s/members" % team['id'])
    else:
        members = get("/orgs/%s/members" % args.organization)

    lines = []
    for user in members:
        username = user['login']
        print("Getting key for %s" % username)
        keys = get("/users/%s/keys" % username)
        for key in keys:
            lines.append(key['key'])

    if args.f is None:
        print(os.linesep.join(lines))
    else:
        tempname = tempfile.mktemp()
        with open(tempname, 'w') as ofile:
            for line in lines:
                ofile.write(line)
                ofile.write(os.linesep)
        os.chmod(tempname, stat.S_IRUSR | stat.S_IWUSR)
        shutil.move(tempname, args.f)

if __name__ == '__main__':
    main()
