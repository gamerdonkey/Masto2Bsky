import re

from bs4 import BeautifulSoup
from atproto import client_utils, IdResolver


class TootParser:

    def __init__(self, toot):
        self._text_builder = client_utils.TextBuilder()
        self._resolver = IdResolver()

        self._parse(toot)

    @property
    def text_builder(self):
        return self._text_builder

    def _parse(self, toot):
        soup = BeautifulSoup(toot.content, "html.parser")

        for br in soup.find_all("br"):
            br.replace_with("\n")

        for tag in soup.descendants:
            if tag.name is None and tag.parent.name == 'p':
                text = tag.get_text()
                last_end = 0

                for m in re.finditer(r"\@[\w\-\.]+\w", text):
                    self._text_builder.text(text[last_end:m.start()])

                    handle = m.group(0)
                    did = self._resolver.handle.resolve(handle.lstrip("@"))

                    if did:
                        self._text_builder.mention(handle, did)
                    else:
                        self._text_builder.text(handle)

                    last_end = m.end()

                self._text_builder.text(text[last_end:])

            elif tag.name == 'a':
                if "hashtag" in tag.get('class', []):
                    hashtag = f"#{tag.span.get_text()}"

                    self._text_builder.tag(hashtag, hashtag.lstrip("#"))

                elif "class" not in tag.attrs:
                    url = tag['href']
                    visible_elements = [e.get_text() for e in tag.select(":not(.invisible)")]
                    text = "".join(visible_elements)

                    self._text_builder.link(text, url)

            elif tag.name == 'span' and "h-card" in tag.get('class', []):
                url = tag.a['href']
                instance = url.split('/')[2]
                username = tag.a.span.get_text()

                handle = f"@{username}@{instance}"

                self._text_builder.link(handle, url)

            elif tag.name == 'p' \
                    and tag.previous_sibling is not None:
                self._text_builder.text("\n\n")

