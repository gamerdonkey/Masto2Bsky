from atproto import Client as BlueskyClient
from getpass import getpass

username = input("Username: ")
password = getpass()

bluesky_client = BlueskyClient()
bluesky_client.login(username, password)

with open("bluesky_session.txt", "w") as bluesky_session_file:
    bluesky_session_file.write(bluesky_client.export_session_string())

