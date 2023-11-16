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
		allowed_groups=os.environ.get("NSDF_ALLOWED_GROUPS","*")

		# need to authenticate anyway
		self.ad = easyad.EasyAD({
			'AD_SERVER': os.environ["AD_SERVER"],
			'AD_DOMAIN': os.environ["AD_DOMAIN"],
			"AD_BIND_USERNAME":username,
			"AD_BIND_PASSWORD":password
		})		
		user  = self.ad.authenticate_user(username, password, json_safe=True)

		# check if is inside allowed group
		is_authorised=True if user else False

		if is_authorised and allowed_groups!="*":
			groups=[it for it in allowed_groups.split(";") if it]
			is_authorised = is_authorised and any([self.ad.user_is_member_of_group(user,group) for group in groups]) 

		if is_authorised:
			self.set_secure_cookie("user", json_encode(username))
			self.redirect(APP_URL)
		else:
			self.redirect(login_url + "?error=" + url_escape("Login incorrect."))
			self.clear_cookie("user")
