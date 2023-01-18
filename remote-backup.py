"""Backups to remote host using duplicty"""

from telegramclient import TeleGramClient, NoOpTeleGramClient
import subprocess
import sys
from tendo import singleton
import logging
from logging.handlers import TimedRotatingFileHandler
import socket
import argparse
import os


def configure_logger(log_path: str, loglevel=logging.INFO):
    log_formatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s")
    root_logger = logging.getLogger()

    file_handler = TimedRotatingFileHandler(f"{log_path}/backup-remote.log", when='midnight', backupCount=30)
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(loglevel)
    return root_logger


def log_subprocess_output(pipe, logger):
    for line in iter(pipe.readline, b''):
        logger.info(str(line.decode("utf-8").strip()))


def log_subprocess_error(pipe, logger):
    for line in iter(pipe.readline, b''):
        logger.error(str(line.decode("utf-8").strip()))


def run_duplicity_backup(gpg_key_id: str, gpg_passphrase: str, source_path: str, destination_path: str, logger):
    #duplicity --encrypt-key C1F8301F8E3FE201FB1AC236E967107FB4F484C8 wave-reader/ sftp://alex@localhost:7000//home/alex

    env = {
        **os.environ,
        "PASSPHRASE": str(1234),
    }

    command = [
        'duplicity',
        '-v',
        'info',
        '--asynchronous-upload',
        '--encrypt-key',
        gpg_key_id,
        source_path,
        destination_path
    ]
    output = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

    with output.stdout:
        log_subprocess_output(output.stdout, logger)
    return output


def ensure_only_one_execution(logger, telegram_client):
    try:
        me = singleton.SingleInstance()
    except singleton.SingleInstanceException as e:
        logger.warning("Backup in progress by another process. Will exit")
        telegram_client.send_telegram_message("Backup in progress by another process. Will exit")
        sys.exit(0)


def parse_backup_args():
    parser = argparse.ArgumentParser(prog='nas-backup',
                                     description='Wrapper around duplicity for automating backups. '
                                                 'Writes encrypted duplicty, maintains rotating logs of the progress '
                                                 'and notifies via telegram upon error')

    parser.add_argument('gpg_key', action='store', help='gpg key to encrypt the backup with')
    parser.add_argument('gpg_pass', action='store', help='path to file containing the passphrase of the gpg-key')
    parser.add_argument('source', action='store', help='the directory to back up')
    parser.add_argument('host_destination', action='store', help='the host to backup to and the destination. In the'
                                                                 'format used by duplicity, for example: '
                                                                 'sftp://user@host:port/path')

    parser.add_argument('-l', '--log-dir', action='store', help='the directory to save logs to. Defaults to '
                                                                'source/.backup-logs/'
                        )

    parser.add_argument('-t', '--telegram-notifications',
                        action='store_true',
                        help='send notifications about errors via telegram. '
                             'Requires a telegram bot token and a chat-id to be specified. Defaults to false')

    parser.add_argument('-b', '--telegram-bot-token',
                        action='store',
                        help='Token for sending messages as this bot')

    parser.add_argument('-u', '--telegram-chat-id',
                        action='store',
                        help='Token for sending messages as this bot')

    parsed = parser.parse_args()

    print(parsed)

    if parsed.log_dir is None:
        print(f"No logging path specified. Logging to {parsed.source}/.backup-logs/")
        parsed.log_dir = f"{parsed.source}/.backup-logs"
    print(parsed)

    if parsed.telegram_notifications and (parsed.telegram_bot_token is None or parsed.telegram_chat_id is None):
        print(
            "nas-backup: error: the following arguments are required when telegram notifications are on:"
            " --telegram-bot-token, --telegram-chat-id")
        sys.exit(1)

    return parsed


def run_backup():
    args = parse_backup_args()

    gpg_key = args.gpg_key
    backup_source = args.source
    backup_destination = args.host_destination

    with open(args.gpg_pass) as passfile:
        gpg_pass = passfile.readlines()[0]

    if args.telegram_notifications:
        tclient = TeleGramClient(args.telegram_bot_token, args.telegram_chat_id)
    else:
        tclient = NoOpTeleGramClient()

    log_path = args.log_dir
    print(args)
    print(log_path)
    rootlogger = configure_logger(log_path)
    hostname = socket.gethostname()

    ensure_only_one_execution(rootlogger, tclient)

    rootlogger.info(f"Starting duplicity backup of {backup_source} to {backup_destination}")

    output = run_duplicity_backup(gpg_key, gpg_pass, backup_source, backup_destination, rootlogger)

    output.wait()

    if output.poll() == 0:
        rootlogger.info(f"Backup to {backup_destination} complete! :)")
    else:
        rootlogger.error("Backup Failed!")
        log_subprocess_error(output.stderr, rootlogger)
        tclient.send_telegram_message(
            f"[{hostname}]: Backup to {backup_destination} failed! Inspect the logs on the host. Logs are stored in {log_path}")
        sys.exit(1)


if __name__ == '__main__':
    run_backup()
