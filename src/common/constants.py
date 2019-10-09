import os

FRAMERATE = 30

OBS_LIDAR_POINTS = 'lidar_points'
OBS_CAMERA_RGB_IMAGE = 'camera_image'
OBS_POSITION = 'player_pos'
OBS_ACTOR_EGO, OBS_ACTORS_RAW = 'ego_actor', 'all_dynamic_actors'
OBS_GRID_LOCAL, OBS_GRID_COMBINED = 'local_occupancy_grid', 'occupancy_grid'
OBS_GRAPH_LOCAL = 'local_graph'
OBS_GNSS_PREFIX = 'pos_gnss_'

ALIAS_EGO = 'ego'

INCREMENTAL_GRIDS = False  # because buggy
GRID_TTL_SEC = 5

OCCUPANCY_RADIUS_DEFAULT = 5  # (5 and 15 or 10 and 9)
OCCUPANCY_TILE_LEVEL = 24
OCCUPANCY_BBOX_OFFSET = 0.1
OCCUPANCY_BBOX_HEIGHT = 3.5

LIDAR_ANGLE_DEFAULT = 15  # Caution: Choose Lidar angle depending on grid size
LIDAR_MAX_RANGE = 100
LIDAR_Z_OFFSET = 2.8

GNSS_Z_OFFSET = 2.8

RES_X, RES_Y = 1024, 768

TOPIC_GRAPH_RAW_IN = '/graph_raw_in'
TOPIC_PREFIX_GRAPH_FUSED_OUT = '/graph_fused_out'

EDGE_DISTRIBUTION_TILE_LEVEL = 16
REMOTE_GRID_TILE_LEVEL = 19

FUSION_DECAY_LAMBDA = .05

REMOTE_PSEUDO_ID = -1

RECORDING_RATE = 10  # Hz
RECORDING_FILE_TPL = 'data/recordings/<id>_%Y-%m-%d_%H-%M-%S.csv'

NPC_TARGET_SPEED = 30  # km/h
EGO_TARGET_SPEED = 30  # km/h

SCENE2_ROLE_NAME_PREFIX = 'random_hero'
SCENE2_NPC_PREFIX = 'npc'
SCENE2_N_EGOS = 2
SCENE2_N_VEHICLES = 10
SCENE2_N_PEDESTRIANS = 100
SCENE2_N_STATIC = 20
SCENE2_MAP_NAME = 'Town01'

MQTT_BASE_HOSTNAME = os.getenv('MQTT_BASE_HOSTNAME', 'localhost')
