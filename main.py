import webapp2
import logging
import os
import jinja2
import datetime
import json
import hashlib
from base64 import b64encode
from google.appengine.ext import ndb
from google.appengine.datastore.datastore_query import Cursor
from google.appengine.api import urlfetch
from webapp2_extras import sessions
from models import User, Geodata

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'frontend')
jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

config = {
    'salt': ';|BT.8|Gv*4ran{Kj5vB@Sz=uE;ojv L;:s/W5t;78n+f*4X061jO3z[=3{@b-im',
    'webapp2_extras.sessions': {
        'secret_key': ('Y3{QYT>Z76p{}|;.=1t_XHhM$%GD`p4GZ}a&TE-,+q)mA_KU*$$Yw;'
                       'eY>.l;){;p'),
        'session_max_age': 28800,
    }
}


def respond_json(data, callback=None):
    if callback:
        resp = callback + '(' + json.dumps(data) + ');'
    else:
        resp = json.dumps(data)
    return resp


class BaseHandler(webapp2.RequestHandler):
    tv = {}

    def jinja2(self):
        return jinja2.get_jinja2(app=self.app)

    def render(self, filename, **template_args):
        template = jinja_environment.get_template(filename)
        self.response.out.write(template.render(self.tv))

    def dispatch(self):
        self.session_store = sessions.get_store(request=self.request)
        try:
            webapp2.RequestHandler.dispatch(self)
        finally:
            self.session_store.save_sessions(self.response)

    @webapp2.cached_property
    def session(self):
        return self.session_store.get_session()


class IndexHandler(BaseHandler):
    def get(self):
        if 'user' not in self.session:
            self.redirect('/login?r=/')
        self.render('index.html')
        return


class DashboardHandler(BaseHandler):
    def get(self):
        if 'user' not in self.session:
            self.redirect('/login?r=dashboard')
        if self.session['user']['email'] not in ['nell@sym.ph']:
            self.redirect('/?error=0')
        self.tv['user'] = json.dumps(self.session['user'])
        self.render('dashboard.html')
        return


class GeodataAPIHandler(BaseHandler):
    def get(self):
        if 'user' not in self.session:
            self.redirect('/login?r=/api/geodata')
        user = self.request.get('user')
        if user:
            if ',' in user:
                users = user.split(',')
                resp = []
                for user in users:
                    query = Geodata.query()
                    query = query.filter(Geodata.user == user)
                    geodata = query.get()
                    if geodata:
                        resp.append(geodata.to_object())
                self.response.write(respond_json(resp))
                return
            else:
                geodata = Geodata.query(Geodata.user == user).get()
                if not geodata:
                    resp = {'message': 'User not found'}
                    self.response.write(respond_json(resp))
                else:
                    self.response.write(respond_json(geodata.to_object()))
        else:
            data = {}
            data['data'] = []
            c = self.request.get('cursor')
            if c:
                c = Cursor(urlsafe=c)
                geodata, cursor, more = Geodata.query().fetch_page(25, start_cursor=c)
            else:
                geodata, cursor, more = Geodata.query().fetch_page(25)
            if more:
                data['cursor'] = cursor.urlsafe()
            for geodatum in geodata:
                data['data'].append(geodatum.to_object())
            self.response.write(respond_json(data))
        return

    def post(self):
        if 'user' not in self.session:
            resp = {'message': 'Not logged in.'}
            self.response.write(respond_json(resp))
        user = str(self.session['user']['id'])
        lat = self.request.get('lat')
        lng = self.request.get('lng')
        geodata = Geodata.query(Geodata.user == user).get()
        if not geodata:
            geodata = Geodata()
            geodata.user = user
        geodata.lat = float(lat)
        geodata.lng = float(lng)
        geodata.put()
        self.response.write(respond_json(geodata.to_object()))
        return


class UserAPIHandler(BaseHandler):
    def get(self, id=None):
        if id:
            user = User.get_by_id(int(id))
            self.response.write(respond_json(user.to_object()))
            return
        else:
            query = User.query()
            n = 25
            if self.request.get('n'):
                n = int(self.request.get('n'))
            if self.request.get('cursor'):
                cursor = Cursor(urlsafe=self.request.get('cursor'))
                users, cursor, more = query.fetch_page(n, start_cursor=cursor)
            else:
                users, cursor, more = query.fetch_page(n)
            resp = {}
            resp['data'] = []
            if more:
                resp['cursor'] = cursor.urlsafe()
            for user in users:
                resp['data'].append(user.to_object())
            self.response.write(respond_json(resp))
            return


class LoginHandler(BaseHandler):
    def get(self):
        if 'user' in self.session:
            self.redirect('/')
        self.render('login.html')

    def post(self):
        email = self.request.get('email')
        password = config['salt'] + self.request.get('password')
        user = User.query(User.email == email).get()
        if user:
            if user.password == hashlib.md5(password).hexdigest():
                self.session['user'] = user.to_object()
                if user.email in ['nell@sym.ph']:
                    self.redirect('/dashboard?success=0')
                else:
                    self.redirect('/?success=0')
            else:
                self.redirect('/login?error=0')
        else:
            self.redirect('/login?error=1')
        return


class LogoutHandler(BaseHandler):
    def get(self):
        if 'user' in self.session:
            del self.session['user']
        self.redirect('/login')


class RegisterHandler(BaseHandler):
    def get(self):
        if 'user' in self.session:
            self.redirect('/')
        self.render('register.html')

    def post(self):
        email = self.request.get('email')
        password = config['salt'] + self.request.get('password')
        user = User.query(User.email == email).get()
        if not user:
            user = User()
            user.email = email
            user.password = hashlib.md5(password).hexdigest()
            user.put()
            self.redirect('/login?success=0')
        else:
            self.redirect('/register?error=1')
        return


class PassengerHandler(BaseHandler):
    def get(self):
        self.tv['buses'] = []
        buses, cursor, more = Geodata.query().fetch_page(25)
        for bus in buses:
            self.tv['buses'].append(bus.to_object())
        self.tv['cursor'] = cursor.urlsafe()
        self.tv['user'] = {}
        self.render('passenger.html')
        return


application = webapp2.WSGIApplication([
    ('/', IndexHandler),
    ('/dashboard', DashboardHandler),
    ('/passenger', PassengerHandler),
    ('/api/geodata', GeodataAPIHandler),
    ('/api/users/(.*)', UserAPIHandler),
    ('/api/users', UserAPIHandler),
    ('/login', LoginHandler),
    ('/logout', LogoutHandler),
    ('/register', RegisterHandler),
], config=config)
