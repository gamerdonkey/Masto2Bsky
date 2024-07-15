import logging
import requests

from atproto import Client as BlueskyClient, client_utils as bluesky_client_utils
from bs4 import BeautifulSoup
from mastodon import Mastodon


logger = logging.getLogger(__name__)


class Masto2Bluesky:
    LAST_STATUS_FILENAME = "last_mastodon_status.txt"
    BLUESKY_SESSION_FILENAME = "bluesky_session.txt"
    MASTODON_TOKEN_FILENAME = "mastodon_token.secret"

    def __init__(self):
        try:
            with open(self.LAST_STATUS_FILENAME, "r") as last_status_file:
                self.last_status_id = int(last_status_file.read())

        except FileNotFoundError:
            self.last_status_id = None
            
        self.bluesky_client = BlueskyClient()
        try:
            with open(self.BLUESKY_SESSION_FILENAME, "r") as bluesky_session_file:
                self.bluesky_client.login(session_string=bluesky_session_file.read())

        except FileNotFoundError as file_not_found_error:
            e = Exception("Could not find saved Bluesky session. Run 'save_bluesky_session.py'.")
            raise e from file_not_found_error

        self.mastodon = Mastodon(access_token=self.MASTODON_TOKEN_FILENAME)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        with open(self.BLUESKY_SESSION_FILENAME, "w") as bluesky_session_file:
            bluesky_session = self.bluesky_client.export_session_string()
            bluesky_session_file.write(bluesky_session)

        with open(self.LAST_STATUS_FILENAME, "w") as last_status_file:
            last_status_file.write(str(self.last_status_id))

    def process_feed(self):
        mastodon_account = self.mastodon.me()
        statuses = self.mastodon.account_statuses(mastodon_account,
                                                  exclude_reblogs=True,
                                                  since_id=self.last_status_id)

        if self.last_status_id is None and statuses:
            self.last_status_id = statuses[0].id
        else:
            for status in statuses[::-1]:
                if status.visibility == "public" \
                        and (status.in_reply_to_account_id is None \
                            or status.in_reply_to_account_id == mastodon_account.id):
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
                self.bluesky_client.send_images(text=status_text, images=images, image_alts=image_alts)

        else:
            self.bluesky_client.send_post(status_text)

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

        text_builder = bluesky_client_utils.TextBuilder()
        if len(fulltext) > 300:
            final_text = text_builder.text(f"{fulltext[:285]}... ").link("[Full Text]", status.url)
        else:
            final_text = text_builder.text(fulltext)

        return final_text 


if __name__ == "__main__":
    with Masto2Bluesky() as masto2bluesky:
        masto2bluesky.process_feed()
