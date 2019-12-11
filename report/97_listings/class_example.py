class PEREntity(ABC):
    pass

class PERRelation(ABC):
    def __init__(self):
        self.obj: Union[PEREntity, Any] = None
        self.confidence: float = 0.0

class OccupancyCell(PEREntity):
    def __init__(self):
        self.hash: int = 0
        self.state: Union[PERRelation[OccupancyState], None] = None

class OccupancyState(Enum):
    FREE = 1
    OCCUPIED = 2
    UNKNOWN = 3