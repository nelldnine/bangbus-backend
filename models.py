import logging
from google.appengine.ext import ndb


class User(ndb.Model):
    email = ndb.StringProperty()
    password = ndb.StringProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    def to_object(self):
        return {
            'id': self.key.id(),
            'email': self.email,
            'created': self.created.strftime('%c'),
            'updated': self.updated.strftime('%c'),
        }


class Geodata(ndb.Model):
    user = ndb.StringProperty()
    lat = ndb.FloatProperty()
    lng = ndb.FloatProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    def to_object(self):
        return {
            'id': self.key.id(),
            'user': ndb.Key('User', int(self.user)).get().to_object(),
            'lat': self.lat,
            'lng': self.lng,
            'created': self.created.strftime('%c'),
            'updated': self.updated.strftime('%c'),
        }
