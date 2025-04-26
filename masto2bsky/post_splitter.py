from dataclasses import dataclass


@dataclass
class Post:
    text: str
    facets: list


class PostSplitter:
    LIMIT = 300
    SPLIT_STRINGS = ['\n\n', '\n', '?', '!', '.', ';', ',', ' ']

    def __init__(self, text_builder):
        self._text_builder = text_builder
        self._text = self._text_builder.build_text()
        self._facets = self._text_builder.build_facets()

    def split(self):
        posts = []

        start = 0
        end = self.LIMIT
        text_length = len(self._text)

        while end < text_length:
            for sub in self.SPLIT_STRINGS:
                split_index = self.find_split(sub, start, end)

                if split_index:
                    end = split_index + 1
                    break

            posts.append(Post(text=self._text[start:end].strip(), facets=self.get_contained_facets(start, end)))
            start = end
            end = start + self.LIMIT

        posts.append(Post(text=self._text[start:text_length].strip(), facets=self.get_contained_facets(start, text_length)))

        return posts

    def find_split(self, sub: str, start: int, end: int):
        possible_split = self._text.rfind(sub, start, end)

        if possible_split < start:
            return None

        enclosing_facet = self.get_enclosing_facet(possible_split)

        if enclosing_facet:
            return self.find_split(sub, start, enclosing_facet.index.byte_start)
        else:
            return possible_split

    def get_enclosing_facet(self, index: int):
        for facet in self._facets:
            if facet.index.byte_start <= index and facet.index.byte_end > index:
                return facet

        return None

    def get_contained_facets(self, start: int, end: int):
        contained_facets = []

        for facet in self._facets:
            if facet.index.byte_start >= start and facet.index.byte_end <= end:
                facet.index.byte_start = facet.index.byte_start - start
                facet.index.byte_end = facet.index.byte_end - start

                contained_facets.append(facet)

        return contained_facets
