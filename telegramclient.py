import requests


class TelegramException(Exception):
    pass


class TeleGramClient:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send_telegram_message(self, message: str) -> None:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage?chat_id={self.chat_id}&text={message}"
        response = requests.get(url).json()
        if not response['ok']:
            raise TelegramException(f"{response['error_code']}: {response['description']}")


class NoOpTeleGramClient(TeleGramClient):
    def __init__(self):
        super().__init__("", "")

    def send_telegram_message(self, message: str) -> None:
        return None
