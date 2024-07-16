# Masto2Bsky

A Python script that reposts public posts from Mastodon to Bluesky.

## Getting Credentials

Use the `save_bsky_session.py` and `save_mastodon_token.py` scripts to store credentials for the different services. Passwords are not stored, but the generated files should be secret.

## Dependencies

This project uses Poetry for dependency management.

```
poetry install
```

## Running

The reposter can be run once credentials are stored:

```
python masto2bsky.py
```

The first run will not repost any toots and instead only stores the latest ID. This is then used to capture newer toots on subsequent runs of the reposter.
