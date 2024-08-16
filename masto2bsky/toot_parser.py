from bs4 import BeautifulSoup
from atproto import client_utils


class TootParser:
    BLUESKY_LIMIT = 300
    OVERRUN_MESSAGE_LENGTH = len("... [Full Text]")

    def __init__(self, toot):
        self.num_chars_left = self.BLUESKY_LIMIT - self.OVERRUN_MESSAGE_LENGTH
        self._text_builder = client_utils.TextBuilder()
        self.overrun = False

        self._parse(toot)

    @property
    def text_builder(self):
        return self._text_builder

    def _parse(self, toot):
        soup = BeautifulSoup(toot.content, "html.parser")

        for br in soup.find_all("br"):
            br.replace_with("\n")

        for tag in soup.descendants:
            is_last_tag = (tag.next_element is None)

            if tag.name is None and tag.parent.name == 'p':
                text = self._fit_text(tag.get_text(), is_last_tag)

                self._text_builder.text(text)

            elif tag.name == 'a':
                if "hashtag" in tag.get('class', []):
                    hashtag = self._fit_text(f"#{tag.span.get_text()}", is_last_tag)

                    self._text_builder.tag(hashtag, hashtag.lstrip("#"))

                elif "class" not in tag.attrs:
                    url = tag['href']
                    visible_elements = [e.get_text() for e in tag.select(":not(.invisible)")]
                    text = self._fit_text("".join(visible_elements), is_last_tag)

                    self._text_builder.link(text, url)

            elif tag.name == 'span' and "h-card" in tag.get('class', []):
                url = tag.a['href']
                instance = url.split('/')[2]
                username = tag.a.span.get_text()

                handle = self._fit_text(f"@{username}@{instance}", is_last_tag)

                self._text_builder.link(handle, url)

            elif tag.name == 'p' \
                    and tag.previous_sibling is not None \
                    and self.num_chars_left >= 2:
                self._text_builder.text("\n\n")
                self.num_chars_left -= 2

            if self.num_chars_left <= 0:
                if self.overrun:
                    self._text_builder.text("... ").link("[Full Text]", toot.url)
                break

    def _fit_text(self, text, is_last_tag):
        return_value = text
        length = len(text)

        if length >= self.num_chars_left \
                and not (is_last_tag and length <= (self.num_chars_left + self.OVERRUN_MESSAGE_LENGTH)):
            return_value = text[:self.num_chars_left]
            self.overrun = True

        self.num_chars_left -= len(return_value)

        return return_value

