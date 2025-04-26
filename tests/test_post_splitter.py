import pytest

from atproto import client_utils, models
from masto2bsky.post_splitter import PostSplitter

class TestPostSplitter:
    @pytest.fixture
    def text_builder(self):
        return client_utils.TextBuilder()

    @pytest.mark.parametrize("size", [299, 300])
    def test_post_that_fits_is_not_split(self, size, text_builder):
        post = "0"*size
        text_builder.text(post)

        posts = PostSplitter(text_builder).split()

        assert len(posts) == 1
        assert posts[0].text == post

    @pytest.mark.parametrize("substring",
            ["\n\n", "\n", "?", ".", "!", ";", ",", " "]
    )
    def test_split_on_proper_substrings(self, substring, text_builder):
        post_0 = "0"*150
        post_1 = "1"*151
        text_builder.text(f"{post_0}{substring}{post_1}")

        posts = PostSplitter(text_builder).split()

        assert posts[0].text == (post_0 + substring).strip()
        assert posts[1].text == post_1
    
    def test_split_on_multiple_substrings(self, text_builder):
        post_0 = ("0"*150) + "?"
        post_1 = ("1"*150) + "."
        post_2 = ("2"*150) + "."
        text_builder.text(f"{post_0} {post_1} {post_2}")

        posts = PostSplitter(text_builder).split()

        assert posts[0].text == post_0
        assert posts[1].text == post_1
        assert posts[2].text == post_2

    def test_splits_post_with_no_proper_substrings(self, text_builder):
        post_0 = "0"*300
        post_1 = "1"
        text_builder.text(f"{post_0}{post_1}")

        posts = PostSplitter(text_builder).split()

        assert posts[0].text == post_0
        assert posts[1].text == post_1
    
    @pytest.mark.parametrize("primary_sub,secondary_sub",
            [
                ("\n\n", "\n"),
                ("\n", "?"),
                ("?", "!"),
                ("!", "."),
                (".", ";"),
                (";", ","),
                (",", " ")
            ]
    )
    def test_splits_on_preferred_substring(self, primary_sub, secondary_sub, text_builder):
        post_0 = "0"*149 + primary_sub
        post_1 = "1"*10 + secondary_sub + "1"*140
        text_builder.text(f"{post_0}{post_1}")

        posts = PostSplitter(text_builder).split()

        assert posts[0].text == post_0.strip()
        assert posts[1].text == post_1.strip()

    def test_does_not_split_facet(self, text_builder):
        post_0 = ("0"*290) + "."
        post_1 = "1"*100
        url = "www.19charslong.com"
        text_builder.text(post_0)
        text_builder.link(url, url)
        text_builder.text(post_1)

        posts = PostSplitter(text_builder).split()

        assert posts[0].text == post_0
        assert posts[1].text == url + post_1

    def test_chooses_another_substring_if_no_better_option_before_facet(self, text_builder):
        sentence_0 = "Check out "
        url = "www.19charslong.com"
        sentence_1 = ", it's so cool;"
        post_0 = f"{sentence_0}{url}{sentence_1}"
        post_1 = "1"*299
        text_builder.text(sentence_0)
        text_builder.link(url, url)
        text_builder.text(sentence_1)
        text_builder.text(post_1)

        posts = PostSplitter(text_builder).split()

        assert posts[0].text == post_0
        assert posts[1].text == post_1
    
    def test_handles_multiple_facets(self, text_builder):
        sentence_0 = "Check out "
        url = "www.19charslong.com"
        sentence_1 = ", it's so cool;"
        post_0 = f"{sentence_0}{url}{url}{url}{sentence_1}"
        post_1 = "1"*299
        text_builder.text(sentence_0)
        text_builder.link(url, url)
        text_builder.link(url, url)
        text_builder.link(url, url)
        text_builder.text(sentence_1)
        text_builder.text(post_1)

        posts = PostSplitter(text_builder).split()

        assert posts[0].text == post_0
        assert posts[1].text == post_1
    
    def test_includes_facets_in_post(self, text_builder):
        url = "www.19charslong.com"
        text_builder.link(url, url)

        posts = PostSplitter(text_builder).split()

        expected_features = [models.app.bsky.richtext.facet.Link(uri=url)]

        assert posts[0].text == url
        assert len(posts[0].facets) == 1
        
        actual_facet = posts[0].facets[0]
        assert actual_facet.index.byte_start == 0
        assert actual_facet.index.byte_end == 19
        assert actual_facet.features == expected_features

    def test_includes_facets_in_split_post(self, text_builder):
        url = "www.19charslong.com"
        post_0 = f"{url}{url}"
        post_1 = "1"*300

        text_builder.link(url, url)
        text_builder.link(url, url)
        text_builder.text("\n")
        text_builder.text(post_1)

        posts = PostSplitter(text_builder).split()

        expected_features = [models.app.bsky.richtext.facet.Link(uri=url)]

        assert posts[0].text == post_0
        assert posts[1].text == post_1
        assert len(posts[0].facets) == 2
        
        facet_0 = posts[0].facets[0]
        assert facet_0.index.byte_start == 0
        assert facet_0.index.byte_end == 19
        assert facet_0.features == expected_features
        facet_1 = posts[0].facets[1]
        assert facet_1.index.byte_start == 19
        assert facet_1.index.byte_end == 38
        assert facet_1.features == expected_features
    
    def test_includes_facets_in_second_split_post(self, text_builder):
        post_0 = "0"*300
        url = "www.19charslong.com"
        text_builder.text(post_0)
        text_builder.link(url, url)

        posts = PostSplitter(text_builder).split()

        expected_features = [models.app.bsky.richtext.facet.Link(uri=url)]

        assert posts[0].text == post_0
        assert posts[1].text == url
        assert len(posts[1].facets) == 1
        
        actual_facet = posts[1].facets[0]
        assert actual_facet.index.byte_start == 0
        assert actual_facet.index.byte_end == 19
        assert actual_facet.features == expected_features
