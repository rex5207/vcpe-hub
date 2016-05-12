import cPickle as pickle
import os


def log_backup_w(filename, data):
    """Log write to file."""
    if (os.path.exists(filename)):
        os.remove(filename)
    output = open(filename, 'wb')
    # Pickle dictionary using protocol 0.
    pickle.dump(data, output)
    output.close()


def log_backup_r(filename, data):
    """Log read back to db."""
    if (os.path.exists(filename)):
        pkl_file = open(filename, 'rb')
        data = pickle.load(pkl_file)
        pkl_file.close()
