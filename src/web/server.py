import asyncio
import logging
import math
from collections import deque
from typing import Deque, Dict, Any

from fastapi import FastAPI
from pyquadkey2 import quadkey
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from common.bridge import MqttBridge
from common.constants import *
from common.serialization.schema.base import PEMTrafficScene

PUBLISH_RATE = 5  # Hz

graph_queue: Deque[Dict[str, Any]] = deque(maxlen=1)


def on_graph(message: bytes):
    try:
        graph: PEMTrafficScene = PEMTrafficScene.from_bytes(message)
        graph_queue.append(graph2json(graph))
    except:
        print('Failed to parse graph.')


def graph2json(graph: PEMTrafficScene) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        'timestamp': graph.timestamp,
        'states': {},
        'occupants': {}
    }

    for c in graph.occupancy_grid.cells:
        qk = quadkey.from_int(c.hash)

        if not c.state or not c.state.confidence or math.isnan(c.state.confidence):
            continue
        data['states'][qk.key] = [int(c.state.object.value), round(c.state.confidence, 2)]

        if not c.occupant or not c.occupant.object:
            continue
        data['occupants'][qk.key] = [c.occupant.object.id, round(c.occupant.confidence, 2)]

    return data


app: FastAPI = FastAPI()
mqtt: MqttBridge = None


def connect_mqtt(for_file: str):
    global mqtt

    if mqtt:
        mqtt.disconnect()

    mqtt = MqttBridge()
    mqtt.subscribe(f'{TOPIC_PREFIX_GRAPH_FUSED_OUT}/{for_file}', on_graph)
    mqtt.listen(block=False)

    logging.info(f'Subscribed to {TOPIC_PREFIX_GRAPH_FUSED_OUT}/{for_file}')


@app.on_event('shutdown')
def shutdown():
    if mqtt:
        mqtt.disconnect()


'''
>> ROUTES <<
'''


@app.get('/', status_code=307)
async def index(response: Response):
    response.headers['Location'] = '/status/index.html'
    return None


app.mount('/status', StaticFiles(
    directory=os.path.join(os.path.dirname(__file__), 'public'),
    html=True
), name='index')


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    tile: str = websocket.query_params.get('tile')
    connect_mqtt(tile)

    while True:
        try:
            data: Dict[str, Any] = graph_queue.pop()
            await websocket.send_json(data)
        except IndexError:
            pass

        await asyncio.sleep(1 / PUBLISH_RATE)
