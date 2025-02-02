# -*- coding: utf-8 -*-

# Copyright (C) 2018-2020
# - Pyry Kontio <pyry.kontio@drasa.eu>
# - Jean-Christophe Sirot <simple-furigana@sirot.org>
#
# This file is part of Simple Furigana <https://github.com/jcsirot/anki-simple-furigana>.
#
# Simple Furigana is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Simple Furigana is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Simple Furigana.  If not, see <http://www.gnu.org/licenses/>.

import json
import re
from time import sleep
from aqt import mw
from aqt.utils import showInfo, tooltip
from aqt.qt import *

from anki.hooks import addHook

from . import reading
from . import sanitizer
from . import replacer
from .config import SettingsGui
from .const import *

# import logging
# from pathlib import Path
# logging.basicConfig(filename="%s/simple-furigana.log" % str(Path.home()), level=logging.DEBUG,
#                     format='\n\n-------------------------------------------\n\n\n\n%(asctime)s %(message)s')

def refreshConfig():
    mw.SimpleFuriganaConfig = mw.addonManager.getConfig(__name__)

def setupConfigMenu():
    mw.SimpleFuriganaConfigMenu = QMenu('Simple Furigana',  mw)

    showSettings = QAction("Simple Furigana settings", mw)
    showSettings.triggered.connect(mw.SimpleFuriganaSettings.show)

    mw.form.menuTools.addSeparator()
    mw.form.menuTools.addAction(showSettings)

mw.SimpleFuriganaConfig = mw.addonManager.getConfig(__name__)
mw.SimpleFuriganaSettings = SettingsGui(mw)
mw.refreshConfig = refreshConfig

setupConfigMenu()

mecab = reading.MecabController()

def stripHtml(text):
    text = re.sub(HTMLTAG, r'', text)
    return text


def addButtons(buttons, editor):
    return buttons + [
        editor.addButton(None, "generateRuby", lambda ed=editor: doIt(ed, generateRuby),
            tip=_(u"Automatically generate furigana (Ctrl+.)"), keys=_(u"Ctrl+."), label=_(u"Generate readings")),
        editor.addButton(None, "deleteRuby", lambda ed=editor: doIt(ed, deleteRuby),
            tip=_(u"Mass delete furigana (Ctrl+,)"), keys=_(u"Ctrl+,"), label=_(u"Delete readings"))
    ]


def doIt(editor, action):
    #logging.debug('Do it! '+str(action))
    Selection(editor, lambda s: action(editor, s))


def finalizeRuby(html, s):
    html, spaces = sanitizer.rubySanitizer(html, s.after, s.before)
    s.modify(html, spaceAtLeft=spaces[0], spaceAtRight=spaces[1])


def generateRuby(editor, s):
    html = s.selected
    # logging.debug("Selection: "+str(html))
    # showInfo("%s" % html)
    if mw.SimpleFuriganaConfig['readingsPattern'] == FURIGANA_PATTERNS[0] :
        html = preRender(html)
    html = makeRuby(html)
    # showInfo("%s" % html)
    if mw.SimpleFuriganaConfig['readingsPattern'] == FURIGANA_PATTERNS[0] :
        html = preRender(html)
    # showInfo("%s" % html)
    if html == s.selected:
        tooltip(_("Nothing to generate!"))
        return
    finalizeRuby(html, s)


def deleteRuby(editor, s):
    html = s.selected
    html, number_brackets = catchFuriganaBrackets(html, clearRuby)
    html = preRender(html)
    html, number_html = catchFuriganaBrackets(html, clearRuby)
    html = preRender(html)
    if number_brackets + number_html == 0:
        tooltip(
            _("No furigana text found! Create some first with 'Generate readings.'"))
    finalizeRuby(html, s)


def makeRuby(html):
    r1 = replacer.Replacer()
    html = r1.sub(html, FURIGANA_HTML)

    html, r2 = subForBrackets(html, lambda x: x.group(
        0).replace(x.group(1), generateRuby(x.group(1))))

    r3 = replacer.Replacer()
    html = r3.sub(html, FURIGANA_BRACKETS)
    html = html.replace('\n', '')
    html = mecab.reading(html)

    # logging.debug("reading: %s" % html)

    html = r3.restore(html)
    html = r2.restore(html)
    html = r1.restore(html)
    return html


def clearRuby(match, r):
    return match.group('base')


def preRender(html):

    def htmlToBrackets(match):
        original = match.group(0)
        if 'hidden' in match.group('base_hide'):
            bracket_base = u"\u00a0{0}!"
        else:
            bracket_base = u"\u00a0{0}"
        if 'hidden' in match.group('ruby_hide'):
            bracket_ruby = u"[!{1}]"
        else:
            bracket_ruby = u"[{1}]"
        base_cleaned, r = subForBrackets(
            match.group('base'), lambda x: x.group(0))
        base_cleaned = base_cleaned.replace(r'\u00a0', '').replace(r' ', '')
        bracket_pattern = bracket_base + bracket_ruby
        furigana_repl = bracket_pattern.format(
            base_cleaned, match.group('ruby'))
        furigana_repl = r.restore(furigana_repl)
        return furigana_repl

    r = replacer.Replacer()
    html = r.sub(html, FURIGANA_HTML, 'HTML_TO_BRACKETS',
                 processing=htmlToBrackets)
    html = renderFurigana(html)
    html = r.restore(html)
    return html


def renderFurigana(html):
    html, number = catchFuriganaBrackets(html, bracketsToHtml)
    return html


def bracketsToHtml(match, r, insideCloze=False):
    base = r.restore(match.group('base'))
    ruby = r.restore(match.group('ruby'))
    base_hide = (match.group('base_hide') == '!')
    ruby_hide = (match.group('ruby_hide') == '!')
    base_cloze = re.search(CLOZEDELETION_PATTERN_HTML, base)
    ruby_cloze = re.search(CLOZEDELETION_PATTERN_HTML, ruby)
    return htmlRuby(base, ruby, base_hide, ruby_hide, base_cloze, ruby_cloze, insideCloze)


def htmlRuby(base, ruby, base_hide, ruby_hide, base_cloze, ruby_cloze, insideCloze):
    if ruby_hide:
        ruby_hide = ' class="hidden"'
    else:
        ruby_hide = ''
    if base_hide:
        base_hide = ' class="hidden"'
    else:
        base_hide = ''
    title = stripHtml(base+'('+ruby+')')
    html = u'''<ruby title="{4}"><rb{0}>{1}</rb><rt{2}>{3}</rt></ruby>'''.format(
        base_hide, base, ruby_hide, ruby, title)
    return html


def htmlToHtml(match):
    base = match.group('base')
    ruby = match.group('ruby')
    base_hide = 'hidden' in match.group('base_hide')
    ruby_hide = 'hidden' in match.group('ruby_hide')
    base_cloze = re.search(CLOZEDELETION_PATTERN_HTML, base)
    ruby_cloze = re.search(CLOZEDELETION_PATTERN_HTML, ruby)
    return htmlRuby(base, ruby, base_hide, ruby_hide, base_cloze, ruby_cloze, False)


def catchFuriganaBrackets(html, callback):
    html, r = subForBrackets(html, lambda match: inside_cloze(match, callback))
    html, number = re.subn(FURIGANA_BRACKETS, lambda match: callback(
        match, r), html, flags=re.UNICODE)
    html = r.restore(html)
    return html, number


def inside_cloze(match, callback):
    "makes furigana work even inside clozes"
    inside = match.group(1)
    r = replacer.Replacer()
    furigana = re.sub(FURIGANA_BRACKETS, lambda match: callback(
        match, r, insideCloze=True), inside, flags=re.UNICODE)
    return match.group(0).replace(inside, furigana)


class Selection:

    js_get_html = u"""
        var currentField = getCurrentField();
        sel = currentField && currentField.getSelection();
        range = sel && sel.getRangeAt(0);
        if (!currentField || !sel || range.collapsed) {
            html = ""; htmlAfter = ""; htmlBefore = "";
        } else {
            ancestorStart = $(range.startContainer).closest("ruby").get(0);
            ancestorEnd = $(range.endContainer).closest("ruby").get(0);

            if ( ancestorStart ) {
                range.setStartBefore( ancestorStart );
            }

            if ( ancestorEnd ) {
                range.setEndAfter( ancestorEnd );
            }

            afterRange = range.cloneRange();
            afterRange.collapse(false);
            endPoint = $(range.endContainer).closest("anki-editable").get(0).lastChild; 
            afterRange.setEndAfter(endPoint);
            docFragmentAfter = afterRange.cloneContents();
            div = document.createElement('div');
            div.appendChild(docFragmentAfter);
            htmlAfter = div.innerHTML;
            div = null;

            beforeRange = range.cloneRange();
            beforeRange.collapse(true);
            startPoint = $(range.startContainer).closest("anki-editable").get(0).firstChild;
            beforeRange.setStartBefore(startPoint);
            docFragmentBefore = beforeRange.cloneContents();
            div = document.createElement('div');
            div.appendChild(docFragmentBefore);
            htmlBefore = div.innerHTML;
            div = null;

            sel.removeAllRanges();
            sel.addRange(range);

            docFragment = range.cloneContents();
            div = document.createElement('div');
            div.appendChild(docFragment);
            html = div.innerHTML;
            div = null;

            range.detach();
            afterRange.detach();
            beforeRange.detach();
        }
        [htmlBefore, html, htmlAfter]
    """

    def __init__(self, window, callback):
        self.window = window

        # self.window.web.eval("setFormat('selectAll', '');")
        window.web.page().runJavaScript(self.js_get_html,
                                        lambda x: self._setHtml(x, callback))

    def _setHtml(self, elements, callback, allowEmpty=False):
        self.before, self.selected, self.after = elements
        if not allowEmpty and self.selected.strip() == '':
            self.window.web.eval("setFormat('selectAll', '');")
            self.window.web.page().runJavaScript(self.js_get_html,
                                                 lambda x: self._setHtml(x, callback, True))
            return
        self.selected = self.selected.replace('&nbsp;', u'\u00a0')
        self.before = self.before.replace('&nbsp;', u'\u00a0')
        self.after = self.after.replace('&nbsp;', u'\u00a0')
        callback(self)

    def length(self, callback, text=None):
        html = text if text else self.selected
        # Btw. inserthtml doesn't have inserted html selected, so we must select it by ourselves:
        textRows = []
        rows = html.split("<div>")

        def appendText(text, textRows):
            textRows.append(text)
            if len(textRows) == len(rows):
                if textRows[0] == '':
                    textRows = textRows[1:]
                selectedText = '\n'.join(textRows).replace('&nbsp;', u'\u00a0')
                selectedText = re.sub(r'( +)', ' ', selectedText)
                selectionLength = len(selectedText)
                selectionLength += len(re.findall(
                    r'<rt[^>]*>', html)) + html.count('</rt>')
                callback(selectionLength)
        for row in rows:
            js_get_text = u"""
			div = document.createElement('div');
			div.innerHTML = {0};
			text = div.textContent;
			div = null;
			text
			""".format(json.dumps(row))
            self.window.web.page().runJavaScript(
                js_get_text, lambda x: appendText(x, textRows))

    def modify(self, html, selectionLength=None, spaceAtLeft=0, spaceAtRight=0):
        def insert(selectionLength):
            self.window.web.eval(
                "setFormat('inserthtml', %s);" % json.dumps(html))
            # for _ in range(spaceAtRight):
            #     self.window.web.triggerPageAction(QWebPage.MoveToPreviousChar)
            # for _ in range(selectionLength-spaceAtLeft):
            #     self.window.web.triggerPageAction(QWebPage.SelectPreviousChar)
        html = html.replace(u'\u00a0', '&nbsp;')
        if not html.endswith("</ruby>") and not self.selected.endswith("</ruby>") and not self.after.startswith('<ruby') and not self.after.startswith('<div') and self.after != '' and self.before != '' and not self.before.endswith('</div>'):
            self.length(insert, html)

        # if the selection contains ruby element on its end border, QWebView can't handle it without creating mess.
        # So, we must implement our own replacement code - unfortunately this doesn't have undo functionality.
        else:
            js_replace_selection = u"""
			sel = getCurrentField().getSelection();
			range = sel.getRangeAt(0);
			frag = document.createDocumentFragment();
			div = document.createElement('div');
			div.innerHTML = {0};
			while (child = div.firstChild) {{
				frag.appendChild(child);
			}}
			div = null;
			ancestorStart = $(range.startContainer).closest("ruby").get(0);
			ancestorEnd = $(range.endContainer).closest("ruby").get(0);
				if ( ancestorStart ) {{
					range.setStartBefore( ancestorStart );
				}}
				if ( ancestorEnd ) {{
					range.setEndAfter( ancestorEnd );
				}}
			range.deleteContents();
			range.insertNode(frag);
			sel.removeAllRanges();
			sel.addRange(range);
			range.toString(); 
			""".format(json.dumps(html))
            self.window.web.page().runJavaScript(js_replace_selection)


def subForBrackets(html, cloze_processor):
    r = replacer.Replacer()
    html = r.sub(html, TYPEIN_PATTERN, 'TYPEIN')
    html = r.sub(html, SOUND_PATTERN, 'SOUND')
    html = r.sub(html, CLOZEDELETION_PATTERN_HTML, 'CLOZE', cloze_processor)
    html = r.sub(html, CLOZEDELETION_PATTERN_BRACES,
                 'CLOZE_BRACES', cloze_processor)
    html = r.sub(html, LINEBREAK, 'LINEBREAK\n')
    html = r.sub(html, HTMLTAG, 'HTMLTAG')
    return html, r


addHook("setupEditorButtons", addButtons)
