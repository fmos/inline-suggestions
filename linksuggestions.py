# -*- coding: utf-8 -*-
#
# Copyright 2022 Fabian Stanke
#

from zim.notebook.index.pages import PagesView

from .common import InlineSuggestions


class AbsoluteLinkSuggestions(InlineSuggestions):

	def __init__(self, plugin, pageview):
		super().__init__(plugin, pageview, activation_char=":")

	def fetch_suggestions(self):
		"""
		Return the arguments for SuggestionPopover.load_model
		entries: an iterator
		accessor (optional): a function for unwrapping the entries to a str
		"""
		pagesview = PagesView.new_from_index(self.pageview.notebook.index)
		return (pagesview.walk(), lambda page: page.name)


class RelativeLinkSuggestions(InlineSuggestions):

	def __init__(self, plugin, pageview):
		super().__init__(plugin, pageview, activation_char="+")

	def fetch_suggestions(self):
		"""
		Return the arguments for SuggestionPopover.load_model
		entries: an iterator
		accessor (optional): a function for unwrapping the entries to a str
		"""
		pagesview = PagesView.new_from_index(self.pageview.notebook.index)
		return (pagesview.walk("+"), lambda page: page.name)
