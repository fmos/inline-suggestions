# -*- coding: utf-8 -*-
#
# Copyright 2022 Fabian Stanke
#

from zim.notebook.index.tags import TagsView

from .common import InlineSuggestions


class TagSuggestions(InlineSuggestions):

	def __init__(self, plugin, pageview):
		super().__init__(plugin, pageview, activation_char="@")

	def fetch_suggestions(self):
		"""
		Return the arguments for SuggestionPopover.load_model
		entries: an iterator
		accessor (optional): a function for unwrapping the entries to a str
		"""
		tagsview = TagsView.new_from_index(self.pageview.notebook.index)
		return (tagsview.list_all_tags(), lambda tag: tag.name)
