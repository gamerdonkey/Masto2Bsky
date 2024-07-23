import logging
import requests
import signal

from atproto import (Client as BlueskyClient, client_utils as bluesky_utils, SessionEvent as BlueskySessionEvent)
from bs4 import BeautifulSoup
from mastodon import Mastodon
from threading import Event


logger = logging.getLogger(__name__)


class Masto2Bsky:
    LAST_STATUS_FILENAME = "last_mastodon_status.txt"
    BLUESKY_SESSION_FILENAME = "bluesky_session.txt"
    MASTODON_TOKEN_FILENAME = "mastodon_token.secret"

    def __init__(self):
        self.exit_event = Event()

        try:
            with open(self.LAST_STATUS_FILENAME, "r") as last_status_file:
                self.last_status_id = int(last_status_file.read())

        except FileNotFoundError:
            self.last_status_id = None
            
        self.bluesky = BlueskyClient()
        self.bluesky.on_session_change(self.on_bluesky_session_change)
        try:
            with open(self.BLUESKY_SESSION_FILENAME, "r") as bluesky_session_file:
                self.bluesky.login(session_string=bluesky_session_file.read())

        except FileNotFoundError as file_not_found_error:
            e = Exception("Could not find saved Bluesky session. Run 'save_bluesky_session.py'.")
            raise e from file_not_found_error

        self.mastodon = Mastodon(access_token=self.MASTODON_TOKEN_FILENAME)
        self.mastodon_account = self.mastodon.me()

    def on_bluesky_session_change(self, event, session):
        if event in (BlueskySessionEvent.CREATE, BlueskySessionEvent.REFRESH):
            self.save_bluesky_session(session.export())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.save_bluesky_session(self.bluesky.export_session_string())
        self.save_last_status()

    def save_bluesky_session(self, bluesky_session):
        with open(self.BLUESKY_SESSION_FILENAME, "w") as bluesky_session_file:
            bluesky_session_file.write(bluesky_session)

    def save_last_status(self):
        with open(self.LAST_STATUS_FILENAME, "w") as last_status_file:
            last_status_file.write(str(self.last_status_id))

    def on_sigint(self, signum, frame):
        logger.warning(f"Exiting on signal: {signal.strsignal(signum)}")
        self.exit_event.set()

    def run(self):
        self.exit_event.clear()
        signal.signal(signal.SIGINT, self.on_sigint)
        signal.signal(signal.SIGTERM, self.on_sigint)

        while not self.exit_event.is_set():
            self.process_feed()
            self.exit_event.wait(timeout=60)

    def process_feed(self):
        statuses = self.mastodon.account_statuses(self.mastodon_account,
                                                  exclude_reblogs=True,
                                                  since_id=self.last_status_id)

        if self.last_status_id is None and statuses:
            self.last_status_id = statuses[0].id
        else:
            for status in statuses[::-1]:
                if status.visibility == "public" \
                        and (status.in_reply_to_account_id is None \
                            or status.in_reply_to_account_id == self.mastodon_account.id):
                    logger.info(f"Resposting {status.url}")
                    self.post_to_bluesky(status)

                self.last_status_id = status.id

    def post_to_bluesky(self, status):
        status_text = self.parse_status(status)

        if status.media_attachments:
            images = []
            image_alts = []

            for media in status.media_attachments:
                if media.type == "image":
                    logger.info(f"Getting image {media.preview_url}")
                    image_resp = requests.get(media.preview_url, stream=True)
                    image_resp.raw.decode_content = True
                    images.append(image_resp.raw.read())

                    image_alts.append(media.description)

            if images:
                self.bluesky.send_images(text=status_text, images=images, image_alts=image_alts)

        else:
            self.bluesky.send_post(status_text)

    @staticmethod
    def parse_status(status):
        soup = BeautifulSoup(status.content, "html.parser")
        paragraphs = []

        for tag in soup.children:
            if tag.name == "p":
                for br in soup.find_all("br"):
                    br.replace_with("\n")
                paragraphs.append(tag.get_text())

        fulltext = "\n\n".join(paragraphs)

        text_builder = bluesky_utils.TextBuilder()
        if len(fulltext) > 300:
            final_text = text_builder.text(f"{fulltext[:285]}... ").link("[Full Text]", status.url)
        else:
            final_text = text_builder.text(fulltext)

        return final_text 


def main():
    with Masto2Bsky() as masto2bsky:
        masto2bsky.run()


if __name__ == "__main__":
    main()
