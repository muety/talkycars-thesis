import asyncio
import math
import os
from collections import deque
from typing import Deque, Dict, Any

from fastapi import FastAPI
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from common.bridge import MqttBridge
from common.constants import *
from common.serialization.schema.base import PEMTrafficScene

PUBLISH_RATE = 1  # Hz

graph_queue: Deque[Dict[str, Any]] = deque(maxlen=1)


def on_graph(message: bytes):
    graph: PEMTrafficScene = PEMTrafficScene.from_bytes(message)
    graph_queue.append(graph2json(graph))


def graph2json(graph: PEMTrafficScene) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        'timestamp': graph.timestamp
    }

    for c in graph.occupancy_grid.cells:
        if not c.state.confidence or math.isnan(c.state.confidence):
            continue
        data[c.hash] = [int(c.state.object.value), c.state.confidence]

    return data


app: FastAPI = FastAPI()
mqtt: MqttBridge = None


@app.on_event('startup')
def startup():
    global mqtt
    mqtt = MqttBridge()
    mqtt.subscribe(f'{TOPIC_PREFIX_GRAPH_FUSED_OUT}/#', on_graph)
    mqtt.listen(block=False)


@app.on_event('shutdown')
def shutdown():
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
    while True:
        try:
            data: Dict[str, Any] = graph_queue.pop()
            await websocket.send_json(data)
        except IndexError:
            pass

        await asyncio.sleep(1 / PUBLISH_RATE)
