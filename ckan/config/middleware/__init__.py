# encoding: utf-8

"""WSGI app initialization"""

import logging

import six
from six.moves.urllib.parse import urlparse

from ckan.lib.i18n import get_locales_from_config
from ckan.config.environment import load_environment
from ckan.config.middleware.flask_app import make_flask_stack
from ckan.common import config
from ckan.views import handle_i18n


log = logging.getLogger(__name__)

if six.PY2:
    import webob
    from routes import request_config as routes_request_config
    from ckan.config.middleware.pylons_app import make_pylons_stack

    # This monkey-patches the webob request object because of the way it messes
    # with the WSGI environ.

    # Start of webob.requests.BaseRequest monkey patch
    original_charset__set = webob.request.BaseRequest._charset__set

    def custom_charset__set(self, charset):
        original_charset__set(self, charset)
        if self.environ.get('CONTENT_TYPE', '').startswith(';'):
            self.environ['CONTENT_TYPE'] = ''

    webob.request.BaseRequest._charset__set = custom_charset__set

    webob.request.BaseRequest.charset = property(
        webob.request.BaseRequest._charset__get,
        custom_charset__set,
        webob.request.BaseRequest._charset__del,
        webob.request.BaseRequest._charset__get.__doc__)

    # End of webob.requests.BaseRequest monkey patch

# This is a test Flask request context to be used internally.
# Do not use it!
_internal_test_request_context = None


def make_app(conf):
    '''
    Initialise both the pylons and flask apps, and wrap them in dispatcher
    middleware.
    '''

    load_environment(conf)

    flask_app = make_flask_stack(conf)
    if six.PY2:
        full_stack = True
        static_files = True
        pylons_app = make_pylons_stack(
            conf, full_stack, static_files)

        app = AskAppDispatcherMiddleware(
            {'pylons_app': pylons_app,
             'flask_app': flask_app})
    else:
        app = flask_app

    # Set this internal test request context with the configured environment so
    # it can be used when calling url_for from tests
    global _internal_test_request_context
    _internal_test_request_context = flask_app._wsgi_app.test_request_context()

    return app


class AskAppDispatcherMiddleware(object):

    '''
    Dispatches incoming requests to either the Flask or Pylons apps depending
    on the WSGI environ.

    Used to help transition from Pylons to Flask, and should be removed once
    Pylons has been deprecated and all app requests are handled by Flask.

    Each app should handle a call to 'can_handle_request(environ)', responding
    with a tuple:
        (<bool>, <app>, [<origin>])
    where:
       `bool` is True if the app can handle the payload url,
       `app` is the wsgi app returning the answer
       `origin` is an optional string to determine where in the app the url
        will be handled, e.g. 'core' or 'extension'.

    Order of precedence if more than one app can handle a url:
        Flask Extension > Pylons Extension > Flask Core > Pylons Core
    '''

    def __init__(self, apps=None):
        # Dict of apps managed by this middleware {<app_name>: <app_obj>, ...}
        self.apps = apps or {}
        self.default_locale = config.get('ckan.locale_default', 'en')
        self.locale_list = get_locales_from_config()

    def ask_around(self, environ):
        '''Checks with all apps whether they can handle the incoming request
        '''
        answers = [
            app._wsgi_app.can_handle_request(environ)
            for name, app in six.iteritems(self.apps)
        ]
        # Sort answers by app name
        answers = sorted(answers, key=lambda x: x[1])
        log.debug('Route support answers for {0} {1}: {2}'.format(
            environ.get('REQUEST_METHOD'), environ.get('PATH_INFO'),
            answers))

        return answers

    def __call__(self, environ, start_response):
        '''Determine which app to call by asking each app if it can handle the
        url and method defined on the eviron'''

        # Process locale part on the incoming request URL so it doesn't affect
        # the mapper queries
        handle_i18n(environ)

        app_name = 'pylons_app'  # currently defaulting to pylons app
        answers = self.ask_around(environ)
        available_handlers = []
        for answer in answers:
            if len(answer) == 2:
                can_handle, asked_app = answer
                origin = 'core'
            else:
                can_handle, asked_app, origin = answer
            if can_handle:
                available_handlers.append('{0}_{1}'.format(asked_app, origin))

        # Enforce order of precedence:
        # Flask Extension > Pylons Extension > Flask Core > Pylons Core
        if available_handlers:
            if 'flask_app_extension' in available_handlers:
                app_name = 'flask_app'
            elif 'pylons_app_extension' in available_handlers:
                app_name = 'pylons_app'
            elif 'flask_app_core' in available_handlers:
                app_name = 'flask_app'

        log.debug('Serving request via {0} app'.format(app_name))
        environ['ckan.app'] = app_name
        # HDX-8093: no SCRIPT_NAME provided by nginx unit for old wsgi
        if 'SCRIPT_NAME' not in environ:
            environ['SCRIPT_NAME'] = ''

        if app_name == 'flask_app':
            # This request will be served by Flask, but we still need the
            # Pylons URL builder (Routes) to work
            parts = urlparse(
                config.get('ckan.site_url', 'http://0.0.0.0:5000'))
            request_config = routes_request_config()
            request_config.host = str(parts.netloc + parts.path)
            request_config.protocol = str(parts.scheme)
            request_config.mapper = config['routes.map']

            return self.apps[app_name](environ, start_response)
        else:
            # Although this request will be served by Pylons we still
            # need an application context in order for the Flask URL
            # builder to work and to be able to access the Flask config
            flask_app = self.apps['flask_app']._wsgi_app

            with flask_app.test_request_context():
                return self.apps[app_name](environ, start_response)
