import argparse
import logging
import os
import sys
import time


def run():
    if len(sys.argv) < 2:
        return

    if sys.argv[1] in {'edgenode', 'edge'}:
        import subprocess
        import glob
        import shutil

        current_dir = os.path.dirname(os.path.realpath(__file__))
        schema_dir = os.path.join(current_dir, 'common/serialization/schema/proto')
        target_dir = os.path.join(current_dir, 'edgenode')
        schema_target_dir = os.path.join(target_dir, 'schema')

        for file in glob.glob(f'{schema_dir}/*.go'):
            shutil.copy(file, schema_target_dir)

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
        exit_code = subprocess.run(['./edgenode', *sys.argv[2:]], cwd=target_dir).returncode
        if exit_code != 0:
            logging.error(f'Command exited with code {exit_code}.')
            return

    elif sys.argv[1] in {'simulation', 'sim'}:
        from simulation import simulation
        simulation.run(sys.argv[2:])

    elif sys.argv[1] in {'ego'}:
        from simulation import ego
        ego.run(sys.argv[2:])

    elif sys.argv[1] in {'egos'}:
        # E.g. python3 run.py egos -n 5 --render false --debug false --record true --strat-seed 8 --strategy random_path

        from simulation import ego
        from multiprocessing import Process

        argparser = argparse.ArgumentParser()
        argparser.add_argument('-n', default=1, type=int, help='Number of concurrent egos to spawn')
        args, _ = argparser.parse_known_args(sys.argv[2:])

        processes = []
        for i in range(int(args.n)):
            p = Process(target=ego.run, daemon=False, kwargs={'args': sys.argv[2:]})
            p.start()
            processes.append(p)
            time.sleep(0.2)

        for p in processes:
            p.join()

    elif sys.argv[1] in {'generator'}:
        from evaluation.performance import message_generator
        message_generator.run(sys.argv[2:])

    elif sys.argv[1] in {'web'}:
        import uvicorn
        from web.server import app
        uvicorn.run(app, port=8080)

    elif sys.argv[1] in {'collector'}:
        from evaluation.perception import grid_collector
        grid_collector.run(sys.argv[2:])

    elif sys.argv[1] in {'evaluator'}:
        from evaluation.perception import grid_evaluator
        grid_evaluator.run(sys.argv[2:])

    elif sys.argv[1] in {'clean'}:
        import glob
        list(map(os.remove, glob.glob('../data/recordings/*.csv')))
        list(map(os.remove, glob.glob('../data/evaluation/perception/eval_log.txt')))
        list(map(os.remove, glob.glob('../data/evaluation/perception/actual/*.pkl')))
        list(map(os.remove, glob.glob('../data/evaluation/perception/observed/*.pkl')))


if __name__ == '__main__':
    run()
