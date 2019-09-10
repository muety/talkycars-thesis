import sys


def run():
    if len(sys.argv) < 2:
        return

    if sys.argv[1] in {'edgenode', 'edge'}:
        from edgenode import edgenode
        edgenode.run(sys.argv[2:])
    elif sys.argv[1] in {'simulation', 'sim'}:
        from simulation import simulation
        simulation.run(sys.argv[2:])
    elif sys.argv[1] in {'ego'}:
        from simulation import ego
        ego.run(sys.argv[2:])
    elif sys.argv[1] in {'web'}:
        import uvicorn
        from web.server import app
        uvicorn.run(app, port=8080)

if __name__ == '__main__':
    run()