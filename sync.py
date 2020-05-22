#!bin/python

import argparse
import errno
import logging
import os
import re
import shutil
import sys
from contextlib import contextmanager

import yaml

logging.basicConfig()
__logger__ = logging.getLogger('sync-script')


def run(
    cmd
):
    __logger__.debug('execute command: %s', cmd)
    os.system(cmd)


def safe_copy(
    src,  # type: str
    dst  # type: str
):
    try:
        if os.path.isdir(src):
            if os.path.exists(dst):
                __logger__.warning('%s already exists, remove it first', dst)
                shutil.rmtree(dst)
                __logger__.info('copy directory %s to %s', src, dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy(src, dst)
    except IOError as err:
        # ENOENT(2): file does not exist, raised also on missing dest parent dir
        if err.errno != errno.ENOENT:
            print(err.__dict__)
            raise
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        return safe_copy(src, dir)
    except Exception as err:  # python >2.5
        raise


@contextmanager
def safe_chdir(
    pth  # type: str
):
    "safely change directory to pth, and then go back"
    currdir = os.getcwd()
    try:
        if not pth:
            pth = currdir
        os.chdir(pth)
        __logger__.debug("changing directory to %s", pth)
        yield pth
    finally:
        os.chdir(currdir)
        __logger__.debug("changing directory back to %s", currdir)


def get_index(
    fname  # type: str
):
    def relpath(
        pth  # type: str
    ):
        return os.path.relpath(
            os.path.abspath(os.path.join(os.path.dirname(fname), pth)),
            os.path.abspath('docs')
        ).replace('\\', '/')

    finder = re.compile('\d+\.\s+\[([\w\s]+)\]\s*\((.+)\)')
    indexes = [
        {'Introduction': relpath('README.md')}
    ]
    with open(fname) as fn:
        lines = fn.readlines()
        for line in lines:
            line = line.strip('\n')
            m = finder.match(line)
            if m:
                annotation, fpath = m.groups()
                fpath = relpath(fpath)
                indexes.append({annotation: fpath})
    return indexes


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pai-dir', help='the directory of openpai repo')
    parser.add_argument('--pai-branch', help='the branch of openpai repo')
    args = parser.parse_args()

    pai_dir, pai_branch = args.pai_dir, args.pai_branch
    pai_dir = os.path.expanduser(pai_dir).rstrip('/')
    assert os.path.basename(pai_dir) == 'pai', 'the --pai-dir should be like /path/to/pai, but now {}'.format(pai_dir)

    # git clone the openpai repo if not exist
    if not os.path.isdir(pai_dir):
        with safe_chdir(os.path.dirname(pai_dir)):
            run('git clone https://github.com/microsoft/openpaisdk.git')
    with safe_chdir(pai_dir):
        run('git checkout {}'.format(pai_branch))
        run('git pull')

    # copy file to current repo
    safe_copy(os.path.join(pai_dir, 'manual'), os.path.join('docs', 'manual'))
    safe_copy(os.path.join(pai_dir, 'README.md'), os.path.join('docs', 'index.md'))
    safe_copy(os.path.join(pai_dir, 'pailogo.jpg'), os.path.join('docs', 'pailogo.jpg'))
    safe_copy(os.path.join(pai_dir, 'docs/images'), os.path.join('docs', 'docs/images'))

    # update indexes
    with open('mkdocs.yml') as fn:
        cfg = yaml.safe_load(fn.read())
    cfg['nav'][1] = {
        'User Manual': get_index(os.path.join('docs', 'manual', 'cluster-user', 'README.md'))
    }
    cfg['nav'][2] = {
        'Operational Manual': get_index(os.path.join('docs', 'manual', 'cluster-admin', 'README.md'))
    }
    with open('mkdocs.yml', 'w') as fn:
        yaml.safe_dump(cfg, fn)
