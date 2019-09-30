import logging
import os
import sys


def run():
    if len(sys.argv) < 2:
        return

    if sys.argv[1] in {'edgenode', 'edge'}:
        from edgenode_v1 import edgenode
        edgenode.run(sys.argv[2:])
    elif sys.argv[1] in {'edgenode-v2', 'edge2'}:
        import subprocess

        current_dir = os.path.dirname(os.path.realpath(__file__))
        target_dir = os.path.join(current_dir, 'edgenode_v2')

        gopaths = [p for p in [os.getenv('GOROOT', default='/usr/bin/go'), '/opt/go/bin/go'] if os.path.isfile(p)]
        if len(gopaths) == 0:
            logging.error('Go executable not found.')
            return

        logging.info('Building executable ...')
        exit_code = subprocess.run([gopaths[0], 'build'], cwd=target_dir).returncode
        if exit_code != 0:
            logging.error(f'Command exited with code {exit_code}.')
            return

        logging.info('Starting sub-process ...')
        exit_code = subprocess.run(['./edgenode_v2', *sys.argv[2:]], cwd=target_dir).returncode
        if exit_code != 0:
            logging.error(f'Command exited with code {exit_code}.')
            return
    elif sys.argv[1] in {'simulation', 'sim'}:
        from simulation import simulation
        simulation.run(sys.argv[2:])
    elif sys.argv[1] in {'ego'}:
        from simulation import ego
        ego.run(sys.argv[2:])
    elif sys.argv[1] in {'generator'}:
        from evaluation.performance import message_generator
        message_generator.run(sys.argv[2:])
    elif sys.argv[1] in {'web'}:
        import uvicorn
        from web.server import app
        uvicorn.run(app, port=8080)

if __name__ == '__main__':
    run()