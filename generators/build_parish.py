from copy import deepcopy

from generators.io import read_json
from validators.feeds import validate_parish


def build(path):
    return validate_parish(deepcopy(read_json(path)))
