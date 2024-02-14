"""
auth.py, when hooked into Bokeh server, will require Active Directory login by users.
Currently, it expects the environment variables AD_SERVER and AD_DOMAIN to be set correctly.

This module is meant to be specified as argument to a bokeh server.
bokeh serve --auth-module=auth.py --cookie-secret YOURSECRETHERE [...]
"""
import os

import easyad
from tornado.escape import json_decode, url_escape, json_encode
from tornado.web import RequestHandler


login_url  = "/app/login"
logout_url = "/app/logout"

# //////////////////////////////////////////////////////
def get_user(request_handler):
	user_json = request_handler.get_secure_cookie("user")
	if user_json:
		return json_decode(user_json)
	else:
		return None

# //////////////////////////////////////////////////////
class LogoutHandler(RequestHandler):
	def get(self):
		self.clear_cookie("user")
		self.redirect(login_url)


# //////////////////////////////////////////////////////
class LoginHandler(RequestHandler):
	"""
	The handler for logins. Bokeh promises to include a route to this handler
	"""

	def get(self):
		self.render("chess_login.html")

	def post(self):

		username = self.get_argument("username", "")
		password = self.get_argument("password", "")

		# need to authenticate anyway
		self.ad = easyad.EasyAD({
			'AD_SERVER': os.environ["AD_SERVER"],
			'AD_DOMAIN': os.environ["AD_DOMAIN"],
			"AD_BIND_USERNAME":username,
			"AD_BIND_PASSWORD":password
		})		
		user  = self.ad.authenticate_user(username, password, json_safe=True)

		if not user:
			self.redirect(f"{login_url}?error={url_escape('Login incorrect')}&next={next}")
			self.clear_cookie("user")
			return

		# I am going to a specific group
		next = self.get_argument("next", "")
		from urllib.parse import unquote, urlparse, parse_qs
		group=parse_qs(urlparse(unquote(next)).query).get('group',['nsdf-group'])[0]

		with open("group_permissions.json","r") as f:
			permissions_per_group=json.load(f)

		allowed=False
		for ad_group in permissions_per_group.get(group,"*"):
			allowed=allowed or (ad_group=="*" or self.ad.user_is_member_of_group(user, ad_group))

		if not allowed:
			self.redirect(f"{login_url}?error={url_escape('No allowed AD group')}&next={next}")
			self.clear_cookie("user")
		else:
			self.set_secure_cookie("user", json_encode(username))
			self.redirect(next) # this way I am keeping the group

