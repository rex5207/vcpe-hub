import cPickle as pickle
import logging
import os

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
filename = 'nat_config.pkl'

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def save(nat_dict):
    try:
        with open(path, 'wb') as fp:
            pickle.dump(nat_dict, fp)
        return True
    except:
        logging.warning('Failed when saving pickled')
        return False


def load():
    try:
        with open(path, 'rb') as fp:
            return pickle.load(fp)
    except:
        logging.warning('Failed when loading pickled')
        return None
