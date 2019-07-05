class TileUtils:
    @staticmethod
    def get_tile2world_conversion(level):
        # TODO
        return lambda x: (x[0] * 1e-10 + 10, x[1] * 0.2 + 20, x[2])