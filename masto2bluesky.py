import arrow
import feedparser
import logging
import requests
import sys

from atproto import Client as BlueskyClient, client_utils as bluesky_client_utils
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class Masto2Bluesky:
    LAST_UPDATED_FILENAME = "last_updated"
    BLUESKY_SESSION_FILENAME = "bluesky_session.txt"

    def __init__(self, mastodon_rss_url):
        self.mastodon_rss_url = mastodon_rss_url

        try:
            with open(self.LAST_UPDATED_FILENAME, "r") as last_updated_file:
                last_feed_updated_string = last_updated_file.read()
                self.last_feed_updated = arrow.get(last_feed_updated_string)

        except FileNotFoundError:
            self.last_feed_updated = arrow.utcnow()
            
        self.bluesky_client = BlueskyClient()
        try:
            with open(self.BLUESKY_SESSION_FILENAME, "r") as bluesky_session_file:
                self.bluesky_client.login(session_string=bluesky_session_file.read())

        except FileNotFoundError as file_not_found_error:
            e = Exception("Could not find saved Bluesky session. Run 'save_bluesky_session.py'.")
            raise e from file_not_found_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        with open(self.BLUESKY_SESSION_FILENAME, "w") as bluesky_session_file:
            bluesky_session = self.bluesky_client.export_session_string()
            bluesky_session_file.write(bluesky_session)

        with open(self.LAST_UPDATED_FILENAME, "w") as last_updated_file:
            last_updated_file.write(self.last_feed_updated.isoformat())

    def process_feed(self):
        rss = feedparser.parse(self.mastodon_rss_url)

        feed_updated = arrow.get(rss.feed.updated_parsed)

        for entry in rss.entries[::-1]:
            entry_date = arrow.get(entry.published_parsed)
            if entry_date > self.last_feed_updated:
                logger.info(f"Resposting {entry.link}")
                self.post_to_bluesky(entry)

        self.last_feed_updated = feed_updated

    def post_to_bluesky(self, entry):
        entry_text = self.parse_entry(entry)

        if "media_content" in entry:
            images = []
            image_alts = []

            for i, media in enumerate(entry.media_content):
                if media["medium"] == "image":
                    image_url = media["url"]

                    if int(media["filesize"]) > 976560:  # apparently Bluesky's limit
                        image_url = image_url.replace("original", "small")

                    logger.info(f"Getting image {image_url}")
                    image_resp = requests.get(image_url, stream=True)
                    image_resp.raw.decode_content = True
                    images.append(image_resp.raw.read())

                    if "content" in entry and i < len(entry.content):
                        image_alts.append(entry.content[i]["value"])
                    else:
                        image_alts.append("")  # match length of images

            if images:
                self.bluesky_client.send_images(text=entry_text, images=images, image_alts=image_alts)

        else:
            self.bluesky_client.send_post(entry_text)

    @staticmethod
    def parse_entry(entry):
        soup = BeautifulSoup(entry.description, "html.parser")
        paragraphs = []

        for tag in soup.children:
            if tag.name == "p":
                for br in soup.find_all("br"):
                    br.replace_with("\n")
                paragraphs.append(tag.get_text())

        fulltext = "\n\n".join(paragraphs)

        text_builder = bluesky_client_utils.TextBuilder()
        if len(fulltext) > 300:
            final_text = text_builder.text(f"{fulltext[:285]}... ").link("[Full Text]", entry.link)
        else:
            final_text = text_builder.text(fulltext)

        return final_text 


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <mastodon rss url>")
        exit(1)

    with Masto2Bluesky(sys.argv[1]) as masto2bluesky:
        masto2bluesky.process_feed()
