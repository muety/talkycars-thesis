const SIZE = 1024
const GRID_LEVEL = 19
const OBSERVATION_LEVEL = 24
const CLIP_GRID = OBSERVATION_LEVEL - GRID_LEVEL
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
    const ws = new WebSocket('ws://localhost:8000/ws')
    const canvas = new fabric.StaticCanvas('c')
    const displayBtn = document.getElementById('btn-display')
    const qkInput = document.getElementById('input-qk')

    let observedKey = qkInput.value
    let observedKeys = new Set()
    let observedTiles = new Set()

    displayBtn.addEventListener('click', () => {
        canvas.clear()
        observedKeys = product(['0', '1', '2', '3'], CLIP_GRID).map(s => s.join(''))
        observedTiles = observedKeys.map(qk2xy)

        reinit()

        ws.onopen = reinit
        ws.onclose = reinit
        ws.onmessage = event => {
            onStatesUpdated(JSON.parse(event.data), observedKey)
        }
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
                stroke: '#c8c8c8'
            }))
        })
    }

    function onStatesUpdated(statemap, observedKey) {
        if (Object.keys(statemap).length <= 1) return
        observedKeys.forEach((key, i) => {
            let fullKey = `${observedKey}${key}`
            let color = statemap.hasOwnProperty(fullKey) ? COLORS[statemap[fullKey][0]] : null
            canvas.item(i).set('fill', color)
        })
        canvas.renderAll()
    }
})