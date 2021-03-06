import logging
import os

from helper import file_helper

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
filename = '../config/firewall_config.pkl'

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def save(dict):
    return file_helper.save(path, dict)


def load():
    return file_helper.load(path)
