import logging

from helper import file_helper

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
filename = 'config/nat_config.pkl'


def save(nat_dict):
    file_helper.save(filename, nat_dict)


def load():
    return file_helper.load(filename)
