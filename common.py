import os, os.path as osp, logging, re, time, json
from collections import OrderedDict
from contextlib import contextmanager
import requests
import numpy as np
import uuid, sys, time, argparse

def setup_logger(name='HGCAL SPS plotting'):
    if name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(name)
        logger.info('Logger %s is already defined', name)
    else:
        fmt = logging.Formatter(
            fmt = (
                f'\033[34m[%(name)s:%(levelname)s:%(asctime)s:%(module)s:%(lineno)s {os.uname()[1]}]\033[0m'
                + ' %(message)s'
                ),
            datefmt='%Y-%m-%d %H:%M:%S'
            )
        handler = logging.StreamHandler()
        handler.setFormatter(fmt)
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
    return logger
logger = setup_logger()


def pull_arg(*args, **kwargs):
    """
    Pulls specific arguments out of sys.argv.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(*args, **kwargs)
    args, other_args = parser.parse_known_args()
    sys.argv = [sys.argv[0]] + other_args
    return args

def read_arg(*args, **kwargs):
    """
    Reads specific arguments from sys.argv but does not modify sys.argv
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(*args, **kwargs)
    args, _ = parser.parse_known_args()
    return args


#from contextlib import contextmanager

#@contextmanager
class Scripter:
    def __init__(self):
        self.scripts = {}

    def __call__(self, fn):
        self.scripts[fn.__name__] = fn
        return fn

    def run(self):
        script = pull_arg('script', choices=list(self.scripts.keys())).script
        logger.info('Running %s', script)
        self.scripts[script]()


# Where data are stored at
DATADIR = '/home/snabili/data/HGCAL/'

@contextmanager
def time_and_log(begin_msg, end_msg='Done'):
    try:
        t1 = time.time()
        logger.info(begin_msg)
        yield None
    finally:
        t2 = time.time()
        nsecs = t2-t1
        nmins = int(nsecs//60)
        nsecs %= 60
        logger.info(end_msg + f' (took {nmins:02d}m:{nsecs:.2f}s)')

def imgcat(path):
    """
    Only useful if you're using iTerm with imgcat on the $PATH:
    Display the image in the terminal.
    """
    os.system('imgcat ' + path)


def set_matplotlib_fontsizes(small=18, medium=22, large=26):
    import matplotlib.pyplot as plt
    plt.rc('font', size=small)          # controls default text sizes
    plt.rc('axes', titlesize=small)     # fontsize of the axes title
    plt.rc('axes', labelsize=medium)    # fontsize of the x and y labels
    plt.rc('xtick', labelsize=small)    # fontsize of the tick labels
    plt.rc('ytick', labelsize=small)    # fontsize of the tick labels
    plt.rc('legend', fontsize=small)    # legend fontsize
    plt.rc('figure', titlesize=large)   # fontsize of the figure title

# for later use
def add_key_value_to_json(json_file, key, value):
    with open(json_file, 'r') as f:
        json_str = f.read()
    json_str = json_str.rstrip()
    json_str = json_str[:-1] # Strip off the last }
    json_str += f',"{key}":{json.dumps(value)}}}'
    with open(json_file, 'w') as f:
        f.write(json_str)
    logger.info(f'Added "{key}":{json.dumps(value)} to {json_file}')


def read_content(jfile):
    """
    Reads the content from a .json file.
    """
    with open(jfile, 'rb') as f:
        content = json.load(f)
        return content['contents']
