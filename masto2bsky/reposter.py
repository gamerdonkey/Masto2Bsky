import logging
import requests
import signal

from atproto import (Client as BlueskyClient, client_utils as bluesky_utils,
        SessionEvent as BlueskySessionEvent, models as bluesky_models)
from masto2bsky.toot_parser import TootParser
from mastodon import Mastodon
from mastodon.errors import MastodonNetworkError
from threading import Event


logger = logging.getLogger(__name__)


class Reposter:
    BLUESKY_SESSION_FILENAME = "bluesky_session.txt"
    MASTODON_TOKEN_FILENAME = "mastodon_token.secret"

    def __init__(self):
        self._exit_event = Event()

        self._last_toot_id = None
        self._last_reposted_toot_id = None
        self._last_post_ref = None
        self._last_root_post_ref = None

        self._bluesky = BlueskyClient()
        self._bluesky.on_session_change(self._on_bluesky_session_change)
        try:
            with open(self.BLUESKY_SESSION_FILENAME, "r") as bluesky_session_file:
                self._bluesky.login(session_string=bluesky_session_file.read())

        except FileNotFoundError as file_not_found_error:
            e = Exception("Could not find saved Bluesky session. Run 'save_bluesky_session.py'.")
            raise e from file_not_found_error

        self._mastodon = Mastodon(access_token=self.MASTODON_TOKEN_FILENAME)
        self._mastodon_account = self._mastodon.me()

    def run(self):
        self._exit_event.clear()

        signal.signal(signal.SIGINT, self._on_sigint)
        signal.signal(signal.SIGTERM, self._on_sigint)

        while not self._exit_event.is_set():
            self.process_feed()
            self._exit_event.wait(timeout=60 * 5)

    def _on_sigint(self, signum, frame):
        logger.warning(f"Exiting on signal: {signal.strsignal(signum)}")
        self._exit_event.set()

    def _on_bluesky_session_change(self, event, session):
        if event in (BlueskySessionEvent.CREATE, BlueskySessionEvent.REFRESH):
            self._save_bluesky_session(session.export())

    def _save_bluesky_session(self, bluesky_session):
        with open(self.BLUESKY_SESSION_FILENAME, "w") as bluesky_session_file:
            bluesky_session_file.write(bluesky_session)

    def process_feed(self):
        toots = []
        try:
            toots = self._mastodon.account_statuses(self._mastodon_account,
                                                    exclude_reblogs=True,
                                                    since_id=self._last_toot_id)
        except MastodonNetworkError:
            logger.exception("Errror retrieving toots!")

        if self._last_toot_id is None and toots:
            self._last_toot_id = toots[0].id
        else:
            for toot in toots[::-1]:
                if toot.visibility == "public" \
                        and (toot.in_reply_to_account_id is None \
                            or toot.in_reply_to_account_id == self._mastodon_account.id):
                    logger.info(f"Resposting {toot.url}")
                    self.post_to_bluesky(toot)

                self._last_toot_id = toot.id

    def post_to_bluesky(self, toot):
        toot_text = TootParser(toot).text_builder

        reply_ref = None
        if toot.in_reply_to_id \
                and toot.in_reply_to_id == self._last_reposted_toot_id \
                and self._last_post_ref \
                and self._last_root_post_ref:
            reply_ref = bluesky_models.AppBskyFeedPost.ReplyRef(parent=self._last_post_ref,
                                                                root=self._last_root_post_ref)

        if toot.media_attachments:
            images = []
            image_alts = []

            for media in toot.media_attachments:
                if media.type == "image":
                    logger.info(f"Getting image {media.preview_url}")
                    image_resp = requests.get(media.preview_url, stream=True)
                    image_resp.raw.decode_content = True
                    images.append(image_resp.raw.read())

                    image_alts.append(media.description)

            if images:
                response = self._bluesky.send_images(text=toot_text,
                                                     images=images,
                                                     image_alts=image_alts,
                                                     reply_to=reply_ref)

        else:
            response = self._bluesky.send_post(toot_text, reply_to=reply_ref)

        self._last_reposted_toot_id = toot.id
        self._last_post_ref = bluesky_models.create_strong_ref(response)

        if reply_ref is None:
            self._last_root_post_ref = self._last_post_ref

