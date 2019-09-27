import logging
import random
from typing import List, Iterable

from agents.navigation.basic_agent import BasicAgent

import carla
from common.constants import *
from common.util.waypoint import WaypointProvider

"""
Attempts to spawn n pedestrian on random locations. If a spawn fails due to a collision, no further spawn attempts will be made.
Accordingly the actual amount of spawned pedestrians might be less than n.
CAUTION:    Returns all spawned actors, which is two actual actors for each pedestrian, namely a carla.Walker and a carla.WalkerAIController.
            Every even list element is a carla.Walker, every odd element is the corresponding controller.
"""


def try_spawn_pedestrians(carla_client: carla.Client, n=10) -> List[carla.Actor]:
    # -------------
    # Spawn Walkers
    # -------------

    world: carla.World = carla_client.get_world()
    walker_blueprints = world.get_blueprint_library().filter('walker.pedestrian.000[1-7]*')
    walkers_list = []
    all_id = []

    # 1. take all the random locations to spawn
    spawn_points = []
    for i in range(n):
        spawn_point = carla.Transform()
        loc = world.get_random_location_from_navigation()
        if (loc != None):
            spawn_point.location = loc
            spawn_points.append(spawn_point)
    # 2. we spawn the walker object
    batch = []
    for spawn_point in spawn_points:
        walker_bp = random.choice(walker_blueprints)
        # set as not invincible
        if walker_bp.has_attribute('is_invincible'):
            walker_bp.set_attribute('is_invincible', 'false')
        batch.append(carla.command.SpawnActor(walker_bp, spawn_point))
    results = carla_client.apply_batch_sync(batch, True)
    for i in range(len(results)):
        if results[i].error:
            logging.error(results[i].error)
        else:
            walkers_list.append({"id": results[i].actor_id})
    # 3. we spawn the walker controller
    batch = []
    walker_controller_bp = world.get_blueprint_library().find('controller.ai.walker')
    for i in range(len(walkers_list)):
        batch.append(carla.command.SpawnActor(walker_controller_bp, carla.Transform(), walkers_list[i]["id"]))
    results = carla_client.apply_batch_sync(batch, True)
    for i in range(len(results)):
        if results[i].error:
            logging.error(results[i].error)
        else:
            walkers_list[i]["con"] = results[i].actor_id
    # 4. we put altogether the walkers and controllers id to get the objects from their id
    for i in range(len(walkers_list)):
        all_id.append(walkers_list[i]["con"])
        all_id.append(walkers_list[i]["id"])
    all_actors: carla.ActorList = world.get_actors(all_id)

    # wait for a tick to ensure client receives the last transform of the walkers we have just created
    world.wait_for_tick()

    # 5. initialize each controller and set target to walk to (list is [controller, actor, controller, actor ...])
    for i in range(0, len(all_id), 2):
        # start walker
        all_actors[i].start()
        try:
            # set walk to random point
            all_actors[i].go_to_location(world.get_random_location_from_navigation())
            # random max speed
            all_actors[i].set_max_speed(1 + random.random())  # max speed between 1 and 2 (default is 1.4 m/s)
        except Exception as e:
            all_actors[i].stop()
            all_actors = all_actors[:i] + all_actors[i + 2:]

    return [a for a in all_actors]


def spawn_npcs(carla_client: carla.Client, wpp: WaypointProvider = None, n=10) -> List[BasicAgent]:
    world: carla.World = carla_client.get_world()
    vehicle_blueprints = world.get_blueprint_library().filter('vehicle.*')

    if not wpp:
        wpp = WaypointProvider(world.get_map().get_spawn_points())

    start_points: List[carla.Location] = []
    end_points: List[carla.Location] = []

    agent_ids: List[int] = []
    agents: List[BasicAgent] = []

    batch: List[carla.command.SpawnActor] = []
    for i in range(n):
        blueprint = random.choice(vehicle_blueprints)
        blueprint.set_attribute('role_name', f'npc_{i}')
        if blueprint.has_attribute('color'):
            color = random.choice(blueprint.get_attribute('color').recommended_values)
            blueprint.set_attribute('color', color)

        start_points.append(wpp.get())
        end_points.append(wpp.get())

        batch.append(carla.command.SpawnActor(blueprint, start_points[-1]))

    results = carla_client.apply_batch_sync(batch, True)
    for i in range(len(results)):
        if results[i].error:
            logging.error(results[i].error)
        else:
            agent_ids.append(results[i].actor_id)

    world.wait_for_tick()

    agent_actors: carla.ActorList = world.get_actors(agent_ids)

    for i, actor in enumerate(agent_actors):
        agent: BasicAgent = BasicAgent(actor, target_speed=NPC_TARGET_SPEED)
        agent.set_location_destination(end_points[i].location)
        agents.append(agent)

    return agents


def multi_destroy(carla_client: carla.Client, actors: Iterable[carla.Actor]):
    batch = list(map(lambda a: carla.command.DestroyActor(a), actors))
    carla_client.apply_batch_sync(batch, True)


def get_world_settings() -> carla.WorldSettings:
    return carla.WorldSettings(
        no_rendering_mode=False,
        synchronous_mode=True,
        fixed_delta_seconds=1 / FRAMERATE
    )


def count_present_vehicles(role_name_prefix: str, world: carla.World) -> int:
    all_actors: carla.ActorList = world.get_actors().filter('vehicle.*')
    n_egos_present = len([a for a in all_actors if has_prefixed_attribute(a, 'role_name', role_name_prefix)])
    return n_egos_present


def has_prefixed_attribute(a: carla.Actor, attr: str, prefix: str) -> bool:
    if attr not in a.attributes or not type(a.attributes[attr]) == str:
        return False
    return a.attributes[attr].startswith(prefix)
