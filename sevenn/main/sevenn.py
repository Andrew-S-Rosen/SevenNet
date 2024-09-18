import argparse
import os
import random
import sys
import time

import torch
import torch.distributed as dist

import sevenn._keys as KEY
from sevenn import __version__
from sevenn.parse_input import read_config_yaml
from sevenn.scripts.train import train, train_v2
from sevenn.sevenn_logger import Logger
from sevenn.util import unique_filepath

description = (
    f'sevenn version={__version__}, train model based on the input.yaml'
)

input_yaml_help = 'input.yaml for training'
mode_help = 'main training script to run. Default is train.'
working_dir_help = 'Path to write outputs. Default is cwd.'
log_help = 'Name of logfile. Default is log.sevenn. It never not overwrite.'
screen_help = 'Print log to stdout'
distributed_help = 'Set this flag to enable DDP training.'

# Metainfo will be saved to checkpoint
global_config = {
    'version': __version__,
    'when': time.ctime(),
    KEY.MODEL_TYPE: 'E3_equivariant_model',
}


def main(args=None):
    """
    main function of sevenn
    """
    args = cmd_parse_main(args)
    input_yaml = args.input_yaml
    mode = args.mode
    working_dir = args.working_dir
    log = args.log
    screen = args.screen
    distributed = args.distributed

    if working_dir is None:
        working_dir = os.getcwd()
    elif not os.path.isdir(working_dir):
        os.makedirs(working_dir, exist_ok=True)

    if distributed:
        local_rank = int(os.environ['LOCAL_RANK'])
        rank = int(os.environ['RANK'])
        world_size = int(os.environ['WORLD_SIZE'])
        dist.init_process_group(
            backend='nccl', world_size=world_size, rank=rank
        )
    else:
        local_rank, rank, world_size = 0, 0, 1

    log_fname = unique_filepath(f'{os.path.abspath(working_dir)}/{log}')
    with Logger(filename=log_fname, screen=screen, rank=rank) as logger:
        logger.greeting()

        if distributed:
            logger.writeline(
                f'Distributed training enabled, total world size is {world_size}'
            )

        try:
            model_config, train_config, data_config = read_config_yaml(input_yaml)
        except Exception as e:
            logger.writeline('Failed to parsing input.yaml')
            logger.error(e)
            sys.exit(1)

        train_config[KEY.IS_DDP] = distributed
        train_config[KEY.LOCAL_RANK] = local_rank
        train_config[KEY.RANK] = rank
        train_config[KEY.WORLD_SIZE] = world_size

        logger.print_config(model_config, data_config, train_config)
        # don't have to distinguish configs inside program
        global_config.update(model_config)
        global_config.update(train_config)
        global_config.update(data_config)

        # Not implemented
        if global_config[KEY.DTYPE] == 'double':
            raise Exception('double precision is not implemented yet')
            # torch.set_default_dtype(torch.double)

        seed = global_config[KEY.RANDOM_SEED]
        random.seed(seed)
        torch.manual_seed(seed)

        # run train
        if mode == 'train':
            train(global_config, working_dir)
        elif mode == 'train_v2':
            train_v2(global_config, working_dir)


def cmd_parse_main(args=None):
    ag = argparse.ArgumentParser(description=description)
    ag.add_argument('input_yaml', help=input_yaml_help, type=str)
    ag.add_argument(
        '-m',
        '--mode',
        choices=['train', 'train_v2'],
        default='train',
        help=mode_help,
        type=str,
    )
    ag.add_argument(
        '-w',
        '--working_dir',
        nargs='?',
        const=os.getcwd(),
        help=working_dir_help,
        type=str,
    )
    ag.add_argument(
        '-l',
        '--log',
        default='log.sevenn',
        help=log_help,
        type=str,
    )
    ag.add_argument(
        '-s',
        '--screen',
        help=screen_help,
        action='store_true'
    )
    ag.add_argument(
        '-d',
        '--distributed',
        help=distributed_help,
        action='store_true'
    )

    return ag.parse_args()


if __name__ == '__main__':
    main()
