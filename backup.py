from telegramclient import TeleGramClient, NoOpTeleGramClient
import subprocess
import sys
from tendo import singleton
import logging
from logging.handlers import TimedRotatingFileHandler
import socket
import argparse


def configure_logger(log_path: str, loglevel=logging.INFO):
    log_formatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s")
    root_logger = logging.getLogger()

    file_handler = TimedRotatingFileHandler(f"{log_path}/backup.log", when='midnight', backupCount=30)
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(loglevel)
    return root_logger


def verify_mounted(path: str) -> bool:
    result = subprocess.run(['mountpoint', '-q', path])
    return result.returncode == 0


def log_subprocess_output(pipe, logger):
    for line in iter(pipe.readline, b''):
        logger.info(str(line.decode("utf-8").strip()))


def log_subprocess_error(pipe, logger):
    for line in iter(pipe.readline, b''):
        logger.error(str(line.decode("utf-8").strip()))


def run_rdiff_backup(source_path: str, destination_path: str, logger):
    command = [
        'rdiff-backup',
        '-v8',
        source_path,
        destination_path
    ]
    output = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    with output.stdout:
        log_subprocess_output(output.stdout, logger)
    return output


def prune_old_backups(destination_path: str, remove_older_than: str, logger):
    command = [
        'rdiff-backup',
        '-v8',
        '--remove-older-than',
        remove_older_than,
        destination_path
    ]
    output = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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


def parse_args():
    parser = argparse.ArgumentParser(prog='nas-backup',
                                     description='Wrapper around rdiff-backup for automating backups. '
                                                 'Writes rdiff backups, maintains rotating logs of the progress and '
                                                 'notifies via telegram upon error')

    parser.add_argument('action', action='store', help='choose weather to backup data or perform maintenance on backups'
                        , choices=['backup', 'prune'])

    return parser.parse_args()


def parse_backup_args():
    parser = argparse.ArgumentParser(prog='nas-backup',
                                     description='Wrapper around rdiff-backup for automating backups. '
                                                 'Writes rdiff backups, maintains rotating logs of the progress and '
                                                 'notifies via telegram upon error')

    parser.add_argument('source', action='store', help='the directory to back up')
    parser.add_argument('destination', action='store', help='the directory to back up to')

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

    backup_source = args.source
    backup_destination = args.destination

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

    if not verify_mounted(backup_source):
        rootlogger.error("Backup source is not mounted. Cannot backup. Exiting")
        tclient.send_telegram_message(f"[{hostname}]: Backup source is not mounted. Cannot backup. Exiting")
        sys.exit(1)

    if not verify_mounted(backup_destination):
        rootlogger.error("Backup target is not mounted. Cannot backup. Exiting")
        tclient.send_telegram_message(f"[{hostname}]: Backup target is not mounted. Cannot backup. Exiting")
        sys.exit(1)

    rootlogger.info(f"Starting backup of {backup_source} to {backup_destination}")

    output = run_rdiff_backup(backup_source, backup_destination, rootlogger)

    output.wait()

    if output.poll() == 0:
        rootlogger.info("Backup complete! :)")
    else:
        rootlogger.error("Backup Failed!")
        log_subprocess_error(output.stderr, rootlogger)
        tclient.send_telegram_message(
            f"[{hostname}]: Backup failed! Inspect the logs on the host. Logs are stored in {log_path}")
        sys.exit(1)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    run_backup()
