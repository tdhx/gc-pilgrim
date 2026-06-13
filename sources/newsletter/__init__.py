"""Newsletter adapter boundary for future PDF extraction."""


def fetch(_config):
    raise NotImplementedError("Newsletter fetching is not enabled yet")


def normalise(_document):
    raise NotImplementedError("Newsletter classification is not enabled yet")
from sources.newsletter.pipeline import load_community_records


__all__ = ["load_community_records"]
