from getpass import getpass
from mastodon import Mastodon


username = input("Email: ")
password = getpass()

mastodon = Mastodon(client_id="reposter_app.secret")
mastodon.log_in(username, password, to_file="mastodon_token.secret")
