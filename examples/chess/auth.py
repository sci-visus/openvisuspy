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

import panel as pn

# panel serve --prefix "" (it removes anything before the `app`)
login_url  = f"/app/login"
logout_url = f"/app/logout"

app_url="/app"

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
		# __cookie=self.get_secure_cookie("user")
		self.clear_cookie("user")
		# __cookie=self.get_secure_cookie("user")
		# print(f"LogoutHandler self.request.path=[{self.request.path}] redirecting to [{login_url}]")
		self.redirect(login_url)

# //////////////////////////////////////////////////////
class LoginHandler(RequestHandler):
	"""
	The handler for logins. Bokeh promises to include a route to this handler
	"""

	def get(self):
		# print(f"LoginHandler::get(self) self.request.path=[{self.request.path}] rendering [chess_login.html]")
		self.render("chess_login.html")

	def post(self):

		username = self.get_argument("username", "")
		password = self.get_argument("password", "")
		# print(f"LoginHandler::post username=[{username}] self.request.path=[{self.request.path}]")

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
			# print(f"username={username} is_authorised self.request.path=[{self.request.path}]")
			self.set_secure_cookie("user", json_encode(username))
			self.redirect(app_url)
		else:
			# print("username={username}  is not authorized self.request.path=[{self.request.path}]")
			self.redirect(f"{login_url}?error={url_escape('Login incorrect')}")
			self.clear_cookie("user")
