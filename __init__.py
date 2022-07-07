# -*- coding: utf-8 -*-
#
# Copyright 2022 Fabian Stanke
#

from zim.plugins import PluginClass

from . import tagsuggestions


class InlineSuggestionsPlugin(PluginClass):

	plugin_info = {
		'name': _('Inline Suggestions'),
		'description': _('''\
This plugin provides inline suggestions for tags. \
It is inspired by the Tag Autocompletion plugin from Murat Güven.
'''),
		'author': "Fabian Stanke",
		'help': 'Plugins:Inline Suggestions',
	}


TagSuggestions = tagsuggestions.TagSuggestions
