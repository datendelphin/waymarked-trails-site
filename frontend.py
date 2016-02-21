#!/usr/bin/python3
# This file is part of waymarkedtrails.org
# Copyright (C) 2015 Sarah Hoffmann
#
# This is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

import sys
from os.path import join as os_join
from os import environ as os_environ
from json import dumps
import cherrypy

import config.defaults
import api.tools

api.tools.SAEnginePlugin(cherrypy.engine).subscribe()
cherrypy.tools.db = api.tools.SATool()

from api.routes import RoutesApi
from frontend.compatibility import CompatibilityLinks
from frontend.help import Helppages

@cherrypy.tools.I18nTool()
class Trails(object):

    def __init__(self, maptype, langs):
        self.api = RoutesApi(maptype)
        self.help = Helppages()
        compobj = CompatibilityLinks()
        for l in langs:
            setattr(self, l[0], compobj)

    @cherrypy.expose
    def index(self, **params):
        gconf = cherrypy.request.app.config.get('Global')
        lconf = cherrypy.request.app.config.get('Site')
        _ = cherrypy.request.i18n.gettext
        js_params = { 'MEDIA_URL': gconf['MEDIA_URL'],
                      'API_URL' : gconf['API_URL'],
                      'TILE_URL' : lconf['tile_url'],
                      'GROUPS' : dict([(k, _(v)) for k,v in lconf['groups'].items()]),
                      'GROUP_SHIFT' : lconf['group_shift'],
                      'GROUPS_DEFAULT' : _(lconf['groups_default'])}
        return cherrypy.request.templates.get_template('index.html').render(
                                     g=gconf, l=lconf, jsparam = dumps(js_params))


class _MapDBOption:
    no_engine = True

def setup_site(confname, script_name=''):
    globalconf = {}
    for var in dir(sys.modules['config.defaults']):
        if var.isupper():
            globalconf[var] = getattr(sys.modules['config.defaults'], var)

    site_cfg = {}
    try:
        __import__('config.sites.' + confname)
        site_cfg = getattr(sys.modules['config.sites.' + confname], 'SITE', {})
    except ImportError:
        print("Missing config for site '%s'. Skipping." % site)
        raise

    os_environ['ROUTEMAPDB_CONF_MODULE'] = 'maps.%s' % confname
    from db import conf as db_config
    mapdb_pkg = 'db.%s' % db_config.get('MAPTYPE')
    mapdb_class = __import__(mapdb_pkg, globals(), locals(), ['DB'], 0).DB

    app = cherrypy.tree.mount(Trails(db_config.get('MAPTYPE'), globalconf['LANGUAGES']),
                                script_name + '/',
                                {
                                    '/favicon.ico':
                                    {
                                        'tools.staticfile.on': True,
                                        'tools.staticfile.filename':
                                          '%s/img/map/map_%s.ico' %
                                          (globalconf['MEDIA_ROOT'], confname)
                                        }
                                    })

    app.config['DB'] = { 'map' : mapdb_class(_MapDBOption()) }
    app.config['Global'] = globalconf
    app.config['Global']['BASENAME'] = confname
    app.config['Global']['MAPTYPE'] = db_config.get('MAPTYPE')
    app.config['Site'] = site_cfg

    # now disable trailing slash
    cherrypy.config.update({'tools.trailing_slash.on': False })


def application(environ, start_response):
    """ Handler for WSGI appications."""
    setup_site(environ['WMT_CONFIG'], script_name=environ['SCRIPT_NAME'])
    globals()['application'] = cherrypy.tree
    return cherrypy.tree(environ, start_response)

if __name__ == '__main__':
    setup_site(os_environ['WMT_CONFIG'])
    cherrypy.config.update({'server.socket_host' : '0.0.0.0'})
    cherrypy.engine.start()
    cherrypy.engine.block()
