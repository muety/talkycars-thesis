from lib import quadkey

class TileFactory:
    def __init__(self):
        pass

    @staticmethod
    def gnss_to_quadkey(location, level=20):
        return quadkey.from_geo(location, level)