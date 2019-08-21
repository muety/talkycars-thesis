const SIZE = 1024
const GRID_LEVEL = 19
const OBSERVATION_LEVEL = 24
const CLIP_GRID = OBSERVATION_LEVEL - GRID_LEVEL
const MAX_TTL_SEC = 3
const COLORS = ['green', 'red', 'blue']

function qk2xy(qk) {
    let tileX = 0
    let tileY = 0
    const lvl = qk.length
    for (let i = lvl; i > 0; i--) {
        let mask = 1 << (i - 1)
        switch (qk[lvl - i]) {
            case '0':
                break;
            case '1':
                tileX |= mask;
                break;
            case '2':
                tileY |= mask;
                break;
            case '3':
                tileX |= mask;
                tileY |= mask;
                break;
            default:
                throw new Error('Invalid key')
        }
    }
    return [tileX, tileY]
}

window.addEventListener('load', () => {
    const canvas = new fabric.Canvas('c')
    const displayBtn = document.getElementById('btn-display')
    const disconnectBtn = document.getElementById('btn-disconnect')
    const qkInput = document.getElementById('input-qk')
    const tsIndicator = document.getElementById('timestamp-indicator')

    let ws
    let latestUpdate
    let observedKey
    let observedKeys = new Set()
    let observedTiles = new Set()
    let running = false

    let timerLoop
    let tooltipNode

    displayBtn.addEventListener('click', () => {
        if (running) return

        observedKey = qkInput.value
        observedKeys = product(['0', '1', '2', '3'], CLIP_GRID).map(s => s.join(''))
        observedTiles = observedKeys.map(qk2xy)

        if (ws) ws.close()
        ws = new WebSocket(`ws://localhost:8000/ws?tile=${observedKey}`)

        reinit()
        running = true

        ws.onopen = reinit
        ws.onclose = reinit
        ws.onmessage = event => {
            const parsed = JSON.parse(event.data)
            latestUpdate = new Date(parseInt(parsed.timestamp * 1000))
            onGraphUpdate(parsed.states, parsed.occupants, observedKey)
        }

        timerLoop = setInterval(() => {
            if (!latestUpdate) return
            let timeDiff = ((new Date() - latestUpdate) / 1000)
            tsIndicator.innerText = timeDiff.toString()

            if (timeDiff > MAX_TTL_SEC && parseInt(timeDiff) % MAX_TTL_SEC === 0) {
                onGraphUpdate({}, {}, observedKey)
            }
        }, 100)
    })

    disconnectBtn.addEventListener('click', () => {
        ws.onopen = undefined
        ws.onclose = undefined
        ws.onmessage = undefined

        ws.close()
        canvas.clear()
        clearInterval(timerLoop)
        tsIndicator.innerText = '–'

        running = false
    })

    function reinit() {
        canvas.clear()
        drawGrid()
    }

    function drawGrid() {
        const size = Math.floor(SIZE / Math.pow(2, CLIP_GRID))

        observedTiles.forEach((tile, i) => {
            canvas.add(new fabric.Rect({
                id: observedKeys[i],
                left: tile[0] * size,
                top: tile[1] * size,
                width: size,
                height: size,
                fill: null,
                stroke: '#c8c8c8',
                selectable: false
            }))
        })

        canvas.on('mouse:over', (e) => {
            if (!e.target.id) return
            if (tooltipNode) canvas.remove(tooltipNode)

            let text = `${e.target.id}\n${e.target.opacity}`
            if (e.target.occupant) text += `\n${e.target.occupant}`
            tooltipNode = new fabric.Text(text, {
                top: e.target.top,
                left: e.target.left,
                fontFamily: 'Arial',
                fontSize: 10,
                textAlign: 'center',
                backgroundColor: '#c8c8c8'
            })
            canvas.add(tooltipNode)
            tooltipNode.render()
        })
    }

    function onGraphUpdate(stateMap, occupantMap, observedKey) {
        observedKeys.forEach((key, i) => {
            const fullKey = `${observedKey}${key}`
            const state = stateMap.hasOwnProperty(fullKey) ? stateMap[fullKey] : null
            const occupant = occupantMap.hasOwnProperty(fullKey) ? occupantMap[fullKey] : null
            const color = state ? COLORS[state[0]] : null
            const cellItem = canvas.item(i)

            cellItem.set('fill', color)

            if (state) cellItem.set('opacity', state[1].toFixed(2))
            if (occupant) {
                cellItem.set('strokeWidth', 4)
                cellItem.set('occupant', occupant[0])
            } else {
                cellItem.set('strokeWidth', 1)
                cellItem.set('occupant', null)
            }
        })

        canvas.renderAll()
    }
})