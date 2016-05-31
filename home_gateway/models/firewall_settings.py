import logging

from helper import file_helper

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
filename = 'config/firewall_config.pkl'


def save(dict):
    file_helper.save(filename, dict)


def load():
    return file_helper.load(filename)
