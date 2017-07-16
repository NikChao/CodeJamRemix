import os
import sys
import logging
import json

import falcon

from peewee import *

from playhouse.postgres_ext import ArrayField
from werkzeug.serving import run_simple
from playhouse.pool import PooledPostgresqlExtDatabase

import config

# PG DB connection string
database = PooledPostgresqlExtDatabase(None, stale_timeout=300, max_connections=20, register_hstore=False)

# PeeWee models
class BaseModel(Model):
    class Meta:
        database = database

class User(BaseModel):
    username = CharField(unique=True)
    password = CharField()
    remember_token = CharField(unique=True)
    join_date = DateTimeField()

    def get_points(self):
        return sum([x.problem.points for x in self.solutions])

    class Meta:
        order_by = ('username',)

class Problem(BaseModel):
    name = CharField(unique=True)
    description = TextField()
    points = IntegerField()
    test_file_hash = CharField()

class Solution(BaseModel):
    user = ForeignKeyField(User, related_name='solutions')
    problem = ForeignKeyField(Problem, related_name='solutions')
    last_attempt = CharField() # Hash of last file uploaded
    solved = BooleanField(default=False)

# Database
def init_database(db_name='app'):
    ''' initialises and returns
    database'''
    database.init(
        host='localhost',
        database='codejam',
        user='codejam',
        password='codejam'
    )
    return database

# Middleware
class PeeweeConnectionMiddleware(object):
    '''Handle database connection for each request.'''

    def process_request(self, request, response):
        '''Open a connection.'''
        database.connect()

    def process_response(self, request, response, resource):
        '''Close the connection.'''
        if not database.is_closed():
            database.close()

class ResponseFormatMiddleware(object):
    '''Handle response formatting'''

    def process_response(self, request, response, resource):
        ''' processes responses to be json formatted
        before sending them off '''
        response.content_type = 'application/json; charset=utf-8'
        response.body = json.dumps(response.body)

class AuthMiddleware(object):
    '''Handle authentication'''

    def process_request(self, request, response):
        ''' Checks that a user is authenticated before sending a
        response '''
        token = request.get_header('Authorization')
        account_id = request.get_header('Account-Id')

        challenges = ['Token type="Fernet"']

        if token is not None:
            description = ('Please provide an auth token '
                           'as part of the request.')

            raise falcon.HTTPUnauthorized('Auth token required',
                                          description,
                                          challenges,
                                          href='http://docs.example.com/auth')

        if not self._token_is_valid(token, account_id):
            description = ('The provided auth token is not valid. '
                           'Please request a new token and try again.')

            raise falcon.HTTPUnauthorized('Authentication required',
                                          description,
                                          challenges,
                                          href='http://docs.example.com/auth')

    def _token_is_valid(self, token, account_id):
        return token is not None and account_id is not None

def error_serialiser(request, response, ex):
    ''' Serialise all errors as JSON irrespective of what the client prefers. '''
    response.body = ex.to_json()

# Handlers
class CatchAllHandler(Exception):
    ''' Handler for all Internal server errors '''
    @staticmethod
    def handle(ex, request, response, params):
        ''' Called if an exception has not been handled. Logs the exception. '''
        if isinstance(ex, falcon.HTTPError):
            # Don't log stack trace for request errors
            raise ex

        raise falcon.HTTPInternalServerError('Internal server error.',
                                             'An internal error occurred. If this problem persists,'
                                             + ' please contact us.')

class DoesNotExistHandler(Exception):
    ''' Handler for 404 Errors '''
    @staticmethod
    def handle(ex, request, response, params):
        ''' Called if a resource is not found. Returns 404. '''
        raise falcon.HTTPNotFound()

# Resources
class RootResource(object):
    ''' Class for resource at '/' '''
    def on_get(self, request, response):
        '''GET / '''
        response.body = 'Hello, World!'
        response.status = falcon.HTTP_200

class LoginResource(object):
    ''' Resource for handing logins '''
    def on_get(self, request, response):
        ''' Returns login page '''
        response.body = {'Success': True, 'Message': 'Here is the login page'}
        response.status = falcon.HTTP_200

    def on_post(self, request, response):
        ''' Logs user in '''
        response.body = {'Success': True, 'Message': 'You have successfully logged in'}
        response.status = falcon.HTTP_200

class LogoutResource(object):
    def on_get(self, request, response):
        response.body = {'Success': True, 'Message': 'You have successfully logged out'}
        response.status = falcon.HTTP_200

class ProblemCollection(object):
    def on_get(self, request, response):
        response.body = {'Success': True, 'Problems': [1, 2, 3]}
        response.status = falcon.HTTP_200

class ProblemResource(object):
    def on_get(self, request, response):
        response.body = {'Success': True, 'Problem': {'Name': 'ProblemName'}}
        response.status = falcon.HTTP_200

    def on_post(self, request, response):
        print('here')
        response.body = {'Success': True, 'Message': 'You have successfully solved the problem!'}
        response.status = falcon.HTTP_200

class UserCollection(object):
    def on_get(self, request, response):
        response.body = {'Success': True, 'Competitors': [1, 2, 3, 4, 5]}
        response.status = falcon.HTTP_200

class UserResource(object):
    def on_get(self, request, response):
        if request.params['id'] == '1':
            response.body = {'Success': True, 'Competitor': {'Name': 'Name', 'Points': 100}}
        else:
            response.body = {'Success': True, 'Competitor': {'Name': 'Name2', 'Points': 99}}
        response.status = falcon.HTTP_200

# Init WebApi
class WebApi(falcon.API):
    ''' Wrapper around falcon.API to correctly register routes, error handlers
        and middleware. Allows for flexible defining of middleware (to facilitate
        testing)
    '''
    def __init__(self, media_type=falcon.DEFAULT_MEDIA_TYPE,
                 request_type=falcon.Request, response_type=falcon.Response,
                 middleware=None, router=None):
        super().__init__(media_type, request_type, response_type, middleware, router)

        self.register_routes()
        self.register_error_handlers()
        self.set_error_serializer(error_serialiser)

    def register_routes(self):
        self.add_route('/', RootResource())
        self.add_route('/login', LoginResource())
        self.add_route('/problems', ProblemCollection())
        self.add_route('/problem', ProblemResource())
        self.add_route('/competitors', UserCollection())
        self.add_route('/competitor', UserResource())

    def register_error_handlers(self):
        self.add_error_handler(Exception, CatchAllHandler.handle)
        self.add_error_handler(DoesNotExist, DoesNotExistHandler.handle)


# Initialise the database
init_database()

# Define middleware
middleware = [
    PeeweeConnectionMiddleware(),
    AuthMiddleware(),
    ResponseFormatMiddleware()
]

application = WebApi(middleware=middleware)

if __name__ == '__main__':
    os.environ['PYTHONPATH'] = os.getcwd()

    run_simple('localhost', 5001, application, use_reloader=True)
