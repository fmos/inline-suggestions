# -*- coding: utf-8 -*-
#
# Copyright 2022 Fabian Stanke
#

from abc import ABCMeta, abstractmethod
from collections import namedtuple
from logging import getLogger

from gi.repository import Gtk, Gdk

from zim.gui.pageview import PageViewExtension
from zim.gui.widgets import BrowserTreeView, ScrolledWindow
from zim.notebook.index.tags import TagsView


logger = getLogger('zim.plugins.inlinesuggestions')

LinePos = namedtuple("LinePos", "line offset")


def iter_to_pos(iter: Gtk.TextIter) -> LinePos:
	return LinePos(iter.get_line(), iter.get_line_offset())


class InlineSuggestions(PageViewExtension, metaclass=ABCMeta):

	@abstractmethod
	def fetch_suggestions(self):
		"""
		Return the arguments for SuggestionPopover.load_model
		entries: an iterator
		accessor (optional): a function for unwrapping the entries to a str
		"""
		return ([], lambda x: x)

	def __init__(self, plugin, pageview, activation_char):
		super().__init__(plugin, pageview)

		self.activation_char = activation_char

		self.startpos = LinePos(0, 0)
		self._connected_buffer = None
		self._buffer_signals = ()

		self.popover = SuggestionsPopover(
			self._popover_forward_keypress,
			self._insert_selected)
		self.popover.set_relative_to(self.pageview.textview)
		self.popover.set_position(Gtk.PositionType.RIGHT)

		self.pageview.connect_after('page-changed', self.after_page_changed)
		self._reconnect_buffer()

	def _reconnect_buffer(self):
		if self._connected_buffer:
			for id in self._buffer_signals:
				self._connected_buffer.disconnect(id)
			self._buffer_signals = ()

		buffer = self.pageview.textview.get_buffer()
		self._buffer_signals = (
			buffer.connect_after('insert-text', self.after_insert_text),
			buffer.connect_after('delete-range', self.after_delete_range)
		)
		self._connected_buffer = buffer

	def after_page_changed(self, pageview, page):
		"""
		Attach to new buffer after every page change
		"""
		self._reconnect_buffer()

	def after_insert_text(self, buffer, cursor, text, *args) -> bool:
		"""
		Show and update suggestions based on the inserted text and cursor
		"""
		if self.popover.get_visible():
			if not self._update_popover(buffer, cursor):
				self.popover.popdown()
		elif text.endswith(self.activation_char):
			self._popup_popover(cursor)

		return False

	def after_delete_range(self, buffer, start, end, *args) -> bool:
		"""
		Show and update suggestions based on the inserted text and cursor
		"""
		if self.popover.get_visible():
			if not self._update_popover(buffer, start):
				self.popover.popdown()

		return False

	def _popup_popover(self, cursor):
		self.startpos = iter_to_pos(cursor)
		self.popover.load_model(*self.fetch_suggestions())
		location = self.pageview.textview.get_iter_location(cursor)
		(location.x, location.y) = self.pageview.textview.buffer_to_window_coords(
			Gtk.TextWindowType.WIDGET,  # or TEXT
			location.x, location.y)
		self.popover.set_pointing_to(location)
		self.popover.popup()

	def _popover_forward_keypress(self, event) -> bool:
		return self.pageview.textview.event(event)

	def _update_popover(self, buffer, cursor) -> bool:
		"""
		Return success of the update
		"""
		currpos = iter_to_pos(cursor)

		if (currpos.line != self.startpos.line
			  	or currpos.offset < self.startpos.offset):
			# Not on the same line any more or moved up from the start
			return False

		start = cursor.copy()
		rewind = currpos.offset - self.startpos.offset
		if (rewind > 0 and not start.backward_chars(rewind)):
			# Could not rewind to alleged start - error
			return False

		entered = buffer.get_text(start, cursor, False)
		if ' ' in entered or '\t' in entered:
			# The entered text contains whitespace
			return False

		self.popover.entered = entered

		# Update popover position
		self._update_position(cursor)

		return True

	def _update_position(self, cursor):
		location = self.pageview.textview.get_iter_location(cursor)
		(location.x, location.y) = self.pageview.textview.buffer_to_window_coords(
			Gtk.TextWindowType.WIDGET,
			location.x, location.y)
		self.popover.set_pointing_to(rect=location)

	def _insert_selected(self, selected: str, space=" "):
		"""
		Callback for inserting a tag name into the textview buffer
		"""
		buffer = self.pageview.textview.get_buffer()

		# Wrap changes for a single undo step
		with buffer.user_action:
			# delete entered text, which may mismatch (i.e. be shorter)
			cursor = buffer.get_iter_at_mark(buffer.get_insert())
			currpos = iter_to_pos(cursor)
			start = cursor.copy()
			if start.backward_chars(currpos.offset - self.startpos.offset):
				buffer.delete(start, cursor)

			# insert selected text
			buffer.insert(cursor, selected)

		# Send space to trigger parsing and coloring the new tag immediately
		Gtk.test_widget_send_key(
			self.pageview.textview, Gdk.keyval_from_name("space"), Gdk.ModifierType(0))


class SuggestionsPopover(Gtk.Popover):

	VIS_COL = 0
	DATA_COL = 1

	def __init__(self, callback_forward_keypress, callback_insert_selected):
		super().__init__()

		self.callback_insert_selected = callback_insert_selected
		self.callback_forward_keypress = callback_forward_keypress

		self.model = Gtk.ListStore(bool, str)

		modelfilter = self.model.filter_new()
		modelfilter.set_visible_column(self.VIS_COL)
		modelsort = Gtk.TreeModelSort(modelfilter)
		modelsort.set_sort_column_id(self.DATA_COL, Gtk.SortType.ASCENDING)

		renderer = Gtk.CellRendererText()

		column = Gtk.TreeViewColumn()
		column.pack_start(renderer, False)
		column.set_attributes(
			renderer,
			text=self.DATA_COL)

		treeview = BrowserTreeView(modelsort)
		treeview.set_enable_search(False)
		treeview.set_headers_visible(False)
		treeview.append_column(column)
		treeview.connect('row-activated', self.do_row_activated)
		self.treeview = treeview

		scroll = ScrolledWindow(treeview)
		# scroll.set_min_content_width(150)  # These do not matter
		# scroll.set_max_content_width(300)
		scroll.set_min_content_height(200)  # This is effectively fixed
		# scroll.set_max_content_height(500)
		scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
		scroll.show_all()

		self.add(scroll)

		self.connect('key-press-event', self.on_key_press_event)

	@property
	def has_content(self):
		return len(self.model) > 0

	def load_model(self, entries, accessor=lambda x: x):
		self.model.clear()

		for tag in entries:
			self.model.append((True, accessor(tag)))

		if self.has_content:
			# Reset entered name
			self.entered = ""

		self.treeview.columns_autosize()

	@property
	def entered(self):
		return self._entered

	@entered.setter
	def entered(self, value):
		"""
		Update popover list based on (partial) entry
		"""
		self._entered = value

		# Hide unmatching entries
		def filter(model, path, iter):
			model[iter][self.VIS_COL] = self._entered.upper(
			) in model[iter][self.DATA_COL].upper()
			return False
		self.model.foreach(filter)

		# Select first match
		loopdata = {'select_path': None}

		def select(model, path, iter, data):
			if model[iter][self.DATA_COL].upper().startswith(self._entered.upper()):
				data['select_path'] = path
				return True
			else:
				return False
		self.treeview.get_model().foreach(select, loopdata)
		if loopdata['select_path'] is not None:
			self.treeview.scroll_to_cell(loopdata['select_path'])
			self.treeview.set_cursor(loopdata['select_path'])

	def do_row_activated(self, view, path, col) -> bool:
		"""
		Signal handler when row is actived by user

		see https://docs.gtk.org/gtk3/signal.TreeView.row-activated.html
		"""
		self._insert()
		self.popdown()
		return True

	def on_key_press_event(self, widget, event) -> bool:
		"""
		Signal handler to forward key signals grabbed by popover to the textview.
		Forwards all except for keys that are needed for navigating the popover.
		"""
		keyval_name = Gdk.keyval_name(event.keyval)
		popover_navigation_keys =\
			{'Up', 'Down', 'Page_Up', 'Page_Down', 'Home', 'End', 'Return'}
		if keyval_name in popover_navigation_keys:
			# These should be handled by the default handler
			return False
		else:
			# Skip default handler
			return self.callback_forward_keypress(event)

	def _insert(self):
		"""
		Insert the currently selected tag name
		"""
		selection = self.treeview.get_selection()
		(model, treeiter) = selection.get_selected()

		if treeiter is not None:
			# is there any entry left or is the list empty?
			selected = model[treeiter][self.DATA_COL]
			self.callback_insert_selected(selected)
