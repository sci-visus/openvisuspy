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

APP_URL    = "/app"
login_url  = f"{APP_URL}/login"
logout_url = f"{APP_URL}/logout"

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

		# in case you want to limit the dashboards to some particular users
		allowed_users=os.environ.get("NSDF_ALLOWED_USERS","*")
		
		if allowed_users and allowed_users!="*" and username not in allowed_users.split(";"):
			self.redirect(login_url + "?error=" + url_escape("User not allowed for this dashboard"))
			return

		self.ad = easyad.EasyAD({
			'AD_SERVER': os.environ["AD_SERVER"],
			'AD_DOMAIN': os.environ["AD_DOMAIN"]
		})		
		is_authorised = self.ad.authenticate_user(username, password, json_safe=True)

		if is_authorised and username:
			self.set_secure_cookie("user", json_encode(username))
			self.redirect(APP_URL)
		else:
			self.redirect(login_url + "?error=" + url_escape("Login incorrect."))
			self.clear_cookie("user")
