import os
import sys

dict_updater = lambda base,updater: (lambda innerbase,innerupdater:([innerbase.update(innerupdater), innerbase][1]))(base.copy(),updater)
"Returns a dictionary which is based on base and updated by updater, but the base is not mutated"

def get_filename_in_cwd(filename):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    else:
        return filename
