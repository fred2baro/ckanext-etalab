# -*- coding: utf-8 -*-


# CKANExt-Etalab -- CKAN extension for Etalab
# By: Emmanuel Raviart <emmanuel@raviart.com>
#
# Copyright (C) 2013 Emmanuel Raviart
# http://gitorious.org/etalab/ckanext-etalab
#
# This file is part of CKANExt-Etalab.
#
# CKANExt-Etalab is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# CKANExt-Etalab is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import json
import urllib2

from ckan import plugins
import ckan.plugins.toolkit as tk


class EtalabDatasetFormPlugin(plugins.SingletonPlugin, tk.DefaultDatasetForm):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IDatasetForm)
    plugins.implements(plugins.ITemplateHelpers)

    def _modify_package_schema(self, schema):
        from ckan.logic import converters
        schema.update(dict(
            temporal_coverage_from = [
#                tk.get_validator('ignore_missing'),
                converters.date_to_db,
                tk.get_converter('convert_to_extras'),
                ],
            temporal_coverage_to = [
#                tk.get_validator('ignore_missing'),
                converters.date_to_db,
                tk.get_converter('convert_to_extras'),
                ],
            territorial_coverage = [
                tk.get_validator('ignore_missing'),
                # TODO: Add validator.
                tk.get_converter('convert_to_extras'),
                ],
            territorial_coverage_granularity = [
                tk.get_validator('ignore_missing'),
                # TODO: Add validator.
                tk.get_converter('convert_to_extras'),
                ],
            ))
        return schema

    def create_package_schema(self):
        schema = super(EtalabDatasetFormPlugin, self).create_package_schema()
        schema = self._modify_package_schema(schema)
        return schema

    def get_helpers(self):
        return dict(
            reject_extras = reject_extras,
            )

    def is_fallback(self):
        # Return True to register this plugin as the default handler for
        # package types not handled by any other IDatasetForm plugin.
        return True

    def package_types(self):
        # This plugin doesn't handle any special package types, it just
        # registers itself as the default (above).
        return []

    def show_package_schema(self):
        from ckan.logic import converters
        schema = super(EtalabDatasetFormPlugin, self).show_package_schema()
        schema.update(dict(
            temporal_coverage_from = [
                tk.get_converter('convert_from_extras'),
                converters.date_to_form,
#                tk.get_validator('ignore_missing'),
                ],
            temporal_coverage_to = [
                tk.get_converter('convert_from_extras'),
                converters.date_to_form,
#                tk.get_validator('ignore_missing'),
                ],
            territorial_coverage = [
                tk.get_converter('convert_from_extras'),
                tk.get_validator('ignore_missing'),
                ],
            territorial_coverage_granularity = [
                tk.get_converter('convert_from_extras'),
                tk.get_validator('ignore_missing'),
                ],
            ))

        return schema

    def update_config(self, config):
        # Add this plugin's templates dir to CKAN's extra_template_paths, so
        # that CKAN will use this plugin's custom templates.
        tk.add_template_directory(config, 'templates')

    def update_package_schema(self):
        schema = super(EtalabDatasetFormPlugin, self).update_package_schema()
        schema = self._modify_package_schema(schema)
        return schema


class EtalabQueryPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IPackageController, inherit = True)

    def before_index(self, pkg_dict):
        temporal_coverage_from = pkg_dict.get('temporal_coverage_from')
        year_from = temporal_coverage_from.split('-', 1)[0] if temporal_coverage_from is not None else None
        temporal_coverage_to = pkg_dict.get('temporal_coverage_to')
        year_to = temporal_coverage_to.split('-', 1)[0] if temporal_coverage_to is not None else None
        if year_from is None:
            if year_to is not None:
                pkg_dict['covered_years'] = [year_to]
        elif year_to is None:
            pkg_dict['covered_years'] = [year_from]
        else:
            year_from, year_to = sorted([year_from, year_to])
            pkg_dict['covered_years'] = [
                str(year)
                for year in range(int(year_from), int(year_to) + 1)
                ]

        territorial_coverage = pkg_dict.get('territorial_coverage')
        if territorial_coverage:
            pkg_dict['covered_territories'] = sorted(set(
                covered_territory
                for covered_territory in territorial_coverage.split(',')
                if covered_territory
                ))
        return pkg_dict

    def before_search(self, search_params):
        territory = search_params.get('extras', {}).get('ext_territory')
        if territory is not None:
            territory_kind, territory_code = territory.split('/')
            response = urllib2.urlopen('http://localhost:8090/api/v1/territory?kind={}&code={}'.format(territory_kind,
                territory_code))
            response_dict = json.loads(response.read())
            ancestors_kind_code = response_dict.get('data', {}).get('ancestors_kind_code')
            if ancestors_kind_code:
                territories = [
                    u'{}/{}'.format(ancestor_kind_code['kind'], ancestor_kind_code['code'])
                    for ancestor_kind_code in ancestors_kind_code
                    ]
#                search_params['fq'] = '{} +covered_territories:{}'.format(search_params['fq'], territory)
                search_params['fq'] = '{} +covered_territories:({})'.format(search_params['fq'],
                    ' OR '.join(territories))

            # Add territory to c, to ensure that search.html can use it.
            from ckan.lib.base import c
            c.territory = territory
        return search_params


class EtalabPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)

    def get_helpers(self):
        # Tell CKAN what custom template helper functions this plugin provides,
        # see the ITemplateHelpers plugin interface.
        return dict(
            smart_viewers = smart_viewers,
            )

    def update_config(self, config):
        # Update CKAN's config settings, see the IConfigurer plugin interface.
        tk.add_public_directory(config, 'public')
        tk.add_template_directory(config, 'templates')
        tk.add_resource('public', 'ckanext-etalab')


def reject_extras(container, *names):
    extras = container.get('extras')
    if extras:
        container = container.copy()
        container['extras'] = [
            extra
            for extra in extras
            if extra['key'] not in names
            ]
    return container


def smart_viewers(package):
    """Helper function to extract smart viewers from the related of a package."""
    # TODO
#    print package['id']
    return []
#    return [
#        related
#        for related in package.related
#        if related.type == 'smart_viewer'
#        ]