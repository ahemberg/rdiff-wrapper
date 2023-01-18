# Rdiff wrapper
A python wrapper for rdiff-backup. It is designed to be run from a crontab or similar. Runs rdiff-backup and logs the output to a rotating log, optionally it can notify via telegram if the backup fails.

## Installation
This wrapper requires rdiff-backup to be installed on the target system. See https://github.com/rdiff-backup/rdiff-backup for more information on installing.

Any other dependencies are installed using pip

```
python3 -m pip install -r requirements.txt
```

## Usage
Invoke the script by issuing

```
python3 backup.py [OPTIONS] source destination
```

The following options are available:

```
  -l LOG_DIR, --log-dir LOG_DIR
                        the directory to save logs to. Defaults to source/.backup-logs/
  --skip-source-mount-verification
                        Do not verify that the backup source is mounted. Set this if you are backing up a folder rather 
                        than an entire drive. If this is Not set then the script will verify if the location is mounted 
                        or not and exit if it isnt. This makes sure that a backup of an empty folder is not done if a 
                        drive is not mounted.
  --skip-target-mount-verification
                        Same as --skip-source-mount-verification but for the backup target
  -t, --telegram-notifications
                        send notifications about errors via telegram. Requires a telegram bot token 
                        and a chat-id to be specified. Defaults to false.
  -b TELEGRAM_BOT_TOKEN, --telegram-bot-token TELEGRAM_BOT_TOKEN
                        Token for sending messages as this bot
  -u TELEGRAM_CHAT_ID, --telegram-chat-id TELEGRAM_CHAT_ID
                        Chat ID for chat to send messages to
```
