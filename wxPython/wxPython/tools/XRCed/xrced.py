# Name:         xrced.py
# Purpose:      XRC editor, main module
# Author:       Roman Rolinsky <rolinsky@mema.ucl.ac.be>
# Created:      20.08.2001
# RCS-ID:       $Id$

from globals import *

# Additional wx modules
from wxPython.xrc import *
from wxPython.html import wxHtmlWindow
import os, sys, getopt, re, traceback

# Local modules
from tree import *                      # imports xxx which imports params
from panel import *
# Cleanup recursive import sideeffects, otherwise we can't create undoMan
import undo
undo.ParamPage = ParamPage
undoMan = g.undoMan = UndoManager()

# Set application path for loading resources
if __name__ == '__main__':
    basePath = os.path.dirname(sys.argv[0])
else:
    basePath = os.path.dirname(__file__)

# 1 adds CMD command to Help menu
debug = 0

helpText = """\
<HTML><H2>Welcome to XRCed!</H2><H3><font color="green">DON'T PANIC :)</font></H3>
To start select tree root, then popup menu with your right mouse button,
select "Append Child", and then any command.<P>
Enter XML ID, change properties, create children.<P>
To test your interface select Test command (View menu).<P>
Consult README file for the details.</HTML>
"""

defaultIDs = {xxxPanel:'PANEL', xxxDialog:'DIALOG', xxxFrame:'FRAME',
              xxxMenuBar:'MENUBAR', xxxMenu:'MENU', xxxToolBar:'TOOLBAR'}

################################################################################

# ScrolledMessageDialog - modified from wxPython lib to set fixed-width font
class ScrolledMessageDialog(wxDialog):
    def __init__(self, parent, msg, caption, pos = wxDefaultPosition, size = (500,300)):
        from wxPython.lib.layoutf import Layoutf
        wxDialog.__init__(self, parent, -1, caption, pos, size)
        text = wxTextCtrl(self, -1, msg, wxDefaultPosition,
                             wxDefaultSize, wxTE_MULTILINE | wxTE_READONLY)
        text.SetFont(modernFont)
        dc = wxWindowDC(text)
        w, h = dc.GetTextExtent(' ')
        ok = wxButton(self, wxID_OK, "OK")
        text.SetConstraints(Layoutf('t=t5#1;b=t5#2;l=l5#1;r=r5#1', (self,ok)))
        text.SetSize((w * 80 + 30, h * 40))
        ok.SetConstraints(Layoutf('b=b5#1;x%w50#1;w!80;h!25', (self,)))
        self.SetAutoLayout(TRUE)
        self.Fit()
        self.CenterOnScreen(wxBOTH)

################################################################################

class Frame(wxFrame):
    def __init__(self, pos, size):
        wxFrame.__init__(self, None, -1, '', pos, size)
        global frame
        frame = g.frame = self
        self.CreateStatusBar()
        self.SetIcon(images.getIconIcon())

        # Idle flag
        self.inIdle = false

        # Make menus
        menuBar = wxMenuBar()

        menu = wxMenu()
        menu.Append(wxID_NEW, '&New\tCtrl-N', 'New file')
        menu.Append(wxID_OPEN, '&Open...\tCtrl-O', 'Open XRC file')
        menu.Append(wxID_SAVE, '&Save\tCtrl-S', 'Save XRC file')
        menu.Append(wxID_SAVEAS, 'Save &As...', 'Save XRC file under different name')
        menu.AppendSeparator()
        menu.Append(wxID_EXIT, '&Quit\tCtrl-Q', 'Exit application')
        menuBar.Append(menu, '&File')

        menu = wxMenu()
        menu.Append(wxID_UNDO, '&Undo\tCtrl-Z', 'Undo')
        menu.Append(wxID_REDO, '&Redo\tCtrl-Y', 'Redo')
        menu.AppendSeparator()
        menu.Append(wxID_CUT, 'Cut\tCtrl-X', 'Cut to the clipboard')
        menu.Append(wxID_COPY, '&Copy\tCtrl-C', 'Copy to the clipboard')
        menu.Append(wxID_PASTE, '&Paste\tCtrl-V', 'Paste from the clipboard')
        self.ID_DELETE = wxNewId()
        menu.Append(self.ID_DELETE, '&Delete\tCtrl-D', 'Delete object')
#        menu.AppendSeparator()
        ID_SELECT = wxNewId()
#        menu.Append(ID_SELECT, '&Select', 'Select object')
        menuBar.Append(menu, '&Edit')

        menu = wxMenu()
        self.ID_EMBED_PANEL = wxNewId()
        menu.Append(self.ID_EMBED_PANEL, '&Embed Panel',
                    'Toggle embedding properties panel in the main window', true)
        menu.Check(self.ID_EMBED_PANEL, conf.embedPanel)
        menu.AppendSeparator()
        self.ID_TEST = wxNewId()
        menu.Append(self.ID_TEST, '&Test\tF5', 'Test window')
        self.ID_REFRESH = wxNewId()
        menu.Append(self.ID_REFRESH, '&Refresh\tCtrl-R', 'Refresh test window')
        self.ID_AUTO_REFRESH = wxNewId()
        menu.Append(self.ID_AUTO_REFRESH, '&Auto-refresh\tCtrl-A',
                    'Toggle auto-refresh mode', true)
        menu.Check(self.ID_AUTO_REFRESH, conf.autoRefresh)
        menuBar.Append(menu, '&View')

        menu = wxMenu()
        menu.Append(wxID_ABOUT, '&About...', 'About XCRed')
        self.ID_README = wxNewId()
        menu.Append(self.ID_README, '&Readme...', 'View the README file')
        if debug:
            self.ID_DEBUG_CMD = wxNewId()
            menu.Append(self.ID_DEBUG_CMD, 'CMD', 'Python command line')
            EVT_MENU(self, self.ID_DEBUG_CMD, self.OnDebugCMD)
        menuBar.Append(menu, '&Help')

        self.menuBar = menuBar
        self.SetMenuBar(menuBar)

        # Create toolbar
        tb = self.CreateToolBar(wxTB_HORIZONTAL | wxNO_BORDER | wxTB_FLAT)
        tb.SetToolBitmapSize((24, 23))
        tb.AddSimpleTool(wxID_NEW, images.getNewBitmap(), 'New', 'New file')
        tb.AddSimpleTool(wxID_OPEN, images.getOpenBitmap(), 'Open', 'Open file')
        tb.AddSimpleTool(wxID_SAVE, images.getSaveBitmap(), 'Save', 'Save file')
        tb.AddControl(wxStaticLine(tb, -1, size=(-1,23), style=wxLI_VERTICAL))
        tb.AddSimpleTool(wxID_UNDO, images.getUndoBitmap(), 'Undo', 'Undo')
        tb.AddSimpleTool(wxID_REDO, images.getRedoBitmap(), 'Redo', 'Redo')
        tb.AddControl(wxStaticLine(tb, -1, size=(-1,23), style=wxLI_VERTICAL))
        tb.AddSimpleTool(wxID_CUT, images.getCutBitmap(), 'Cut', 'Cut')
        tb.AddSimpleTool(wxID_COPY, images.getCopyBitmap(), 'Copy', 'Copy')
        tb.AddSimpleTool(wxID_PASTE, images.getPasteBitmap(), 'Paste', 'Paste')
        tb.AddControl(wxStaticLine(tb, -1, size=(-1,23), style=wxLI_VERTICAL))
        tb.AddSimpleTool(self.ID_TEST, images.getTestBitmap(), 'Test', 'Test window')
        tb.AddSimpleTool(self.ID_REFRESH, images.getRefreshBitmap(),
                         'Refresh', 'Refresh view')
        tb.AddSimpleTool(self.ID_AUTO_REFRESH, images.getAutoRefreshBitmap(),
                         'Auto-refresh', 'Toggle auto-refresh mode', true)
        if wxPlatform == '__WXGTK__':
            tb.AddSeparator()   # otherwise auto-refresh sticks in status line
        tb.ToggleTool(self.ID_AUTO_REFRESH, conf.autoRefresh)
        tb.Realize()
        self.tb = tb
        self.minWidth = tb.GetSize()[0] # minimal width is the size of toolbar

        # File
        EVT_MENU(self, wxID_NEW, self.OnNew)
        EVT_MENU(self, wxID_OPEN, self.OnOpen)
        EVT_MENU(self, wxID_SAVE, self.OnSaveOrSaveAs)
        EVT_MENU(self, wxID_SAVEAS, self.OnSaveOrSaveAs)
        EVT_MENU(self, wxID_EXIT, self.OnExit)
        # Edit
        EVT_MENU(self, wxID_UNDO, self.OnUndo)
        EVT_MENU(self, wxID_REDO, self.OnRedo)
        EVT_MENU(self, wxID_CUT, self.OnCutDelete)
        EVT_MENU(self, wxID_COPY, self.OnCopy)
        EVT_MENU(self, wxID_PASTE, self.OnPaste)
        EVT_MENU(self, self.ID_DELETE, self.OnCutDelete)
        EVT_MENU(self, ID_SELECT, self.OnSelect)
        # View
        EVT_MENU(self, self.ID_EMBED_PANEL, self.OnEmbedPanel)
        EVT_MENU(self, self.ID_TEST, self.OnTest)
        EVT_MENU(self, self.ID_REFRESH, self.OnRefresh)
        EVT_MENU(self, self.ID_AUTO_REFRESH, self.OnAutoRefresh)
        # Help
        EVT_MENU(self, wxID_ABOUT, self.OnAbout)
        EVT_MENU(self, self.ID_README, self.OnReadme)

        # Update events
        EVT_UPDATE_UI(self, wxID_CUT, self.OnUpdateUI)
        EVT_UPDATE_UI(self, wxID_COPY, self.OnUpdateUI)
        EVT_UPDATE_UI(self, wxID_PASTE, self.OnUpdateUI)
        EVT_UPDATE_UI(self, wxID_UNDO, self.OnUpdateUI)
        EVT_UPDATE_UI(self, wxID_REDO, self.OnUpdateUI)
        EVT_UPDATE_UI(self, self.ID_DELETE, self.OnUpdateUI)
        EVT_UPDATE_UI(self, self.ID_TEST, self.OnUpdateUI)
        EVT_UPDATE_UI(self, self.ID_REFRESH, self.OnUpdateUI)

        # Build interface
        sizer = wxBoxSizer(wxVERTICAL)
        sizer.Add(wxStaticLine(self, -1), 0, wxEXPAND)
        splitter = wxSplitterWindow(self, -1, style=wxSP_3DSASH)
        self.splitter = splitter
        splitter.SetMinimumPaneSize(100)
        # Create tree
        global tree
        g.tree = tree = XML_Tree(splitter, -1)

        # !!! frame styles are broken
        # Miniframe for not embedded mode
        miniFrame = wxFrame(self, -1, 'Properties Panel',
                            (conf.panelX, conf.panelY),
                            (conf.panelWidth, conf.panelHeight))
        self.miniFrame = miniFrame
        sizer2 = wxBoxSizer()
        miniFrame.SetAutoLayout(true)
        miniFrame.SetSizer(sizer2)
        EVT_CLOSE(self.miniFrame, self.OnCloseMiniFrame)
        # Create panel for parameters
        global panel
        if conf.embedPanel:
            panel = Panel(splitter)
            # Set plitter windows
            splitter.SplitVertically(tree, panel, conf.sashPos)
        else:
            panel = Panel(miniFrame)
            sizer2.Add(panel, 1, wxEXPAND)
            miniFrame.Show(true)
            splitter.Initialize(tree)
        sizer.Add(splitter, 1, wxEXPAND)
        self.SetAutoLayout(true)
        self.SetSizer(sizer)

        # Init pull-down menu data
        global pullDownMenu
        pullDownMenu = g.pullDownMenu = PullDownMenu(self)
        # Mapping from IDs to element names
        self.createMap = {
            pullDownMenu.ID_NEW_PANEL: 'wxPanel',
            pullDownMenu.ID_NEW_DIALOG: 'wxDialog',
            pullDownMenu.ID_NEW_FRAME: 'wxFrame',
            pullDownMenu.ID_NEW_TOOL_BAR: 'wxToolBar',
            pullDownMenu.ID_NEW_TOOL: 'tool',
            pullDownMenu.ID_NEW_MENU_BAR: 'wxMenuBar',
            pullDownMenu.ID_NEW_MENU: 'wxMenu',
            pullDownMenu.ID_NEW_MENU_ITEM: 'wxMenuItem',
            pullDownMenu.ID_NEW_SEPARATOR: 'separator',

            pullDownMenu.ID_NEW_STATIC_TEXT: 'wxStaticText',
            pullDownMenu.ID_NEW_TEXT_CTRL: 'wxTextCtrl',

            pullDownMenu.ID_NEW_BUTTON: 'wxButton',
            pullDownMenu.ID_NEW_BITMAP_BUTTON: 'wxBitmapButton',
            pullDownMenu.ID_NEW_RADIO_BUTTON: 'wxRadioButton',
            pullDownMenu.ID_NEW_SPIN_BUTTON: 'wxSpinButton',

            pullDownMenu.ID_NEW_STATIC_BOX: 'wxStaticBox',
            pullDownMenu.ID_NEW_CHECK_BOX: 'wxCheckBox',
            pullDownMenu.ID_NEW_RADIO_BOX: 'wxRadioBox',
            pullDownMenu.ID_NEW_COMBO_BOX: 'wxComboBox',
            pullDownMenu.ID_NEW_LIST_BOX: 'wxListBox',

            pullDownMenu.ID_NEW_STATIC_LINE: 'wxStaticLine',
            pullDownMenu.ID_NEW_STATIC_BITMAP: 'wxStaticBitmap',
            pullDownMenu.ID_NEW_CHOICE: 'wxChoice',
            pullDownMenu.ID_NEW_SLIDER: 'wxSlider',
            pullDownMenu.ID_NEW_GAUGE: 'wxGauge',
            pullDownMenu.ID_NEW_SCROLL_BAR: 'wxScrollBar',
            pullDownMenu.ID_NEW_TREE_CTRL: 'wxTreeCtrl',
            pullDownMenu.ID_NEW_LIST_CTRL: 'wxListCtrl',
            pullDownMenu.ID_NEW_CHECK_LIST: 'wxCheckList',
            pullDownMenu.ID_NEW_NOTEBOOK: 'wxNotebook',
            pullDownMenu.ID_NEW_HTML_WINDOW: 'wxHtmlWindow',
            pullDownMenu.ID_NEW_CALENDAR_CTRL: 'wxCalendarCtrl',
            pullDownMenu.ID_NEW_GENERIC_DIR_CTRL: 'wxGenericDirCtrl',
            pullDownMenu.ID_NEW_SPIN_CTRL: 'wxSpinCtrl',

            pullDownMenu.ID_NEW_BOX_SIZER: 'wxBoxSizer',
            pullDownMenu.ID_NEW_STATIC_BOX_SIZER: 'wxStaticBoxSizer',
            pullDownMenu.ID_NEW_GRID_SIZER: 'wxGridSizer',
            pullDownMenu.ID_NEW_FLEX_GRID_SIZER: 'wxFlexGridSizer',
            pullDownMenu.ID_NEW_SPACER: 'spacer',
            pullDownMenu.ID_NEW_UNKNOWN: 'unknown',
            }
        pullDownMenu.controls = [
            ['control', 'Various controls',
             (pullDownMenu.ID_NEW_STATIC_TEXT, 'Label', 'Create static label'),
             (pullDownMenu.ID_NEW_STATIC_LINE, 'Line', 'Create static line'),
             (pullDownMenu.ID_NEW_TEXT_CTRL, 'TextBox', 'Create text box control'),
             (pullDownMenu.ID_NEW_CHOICE, 'Choice', 'Create choice control'),
             (pullDownMenu.ID_NEW_SLIDER, 'Slider', 'Create slider control'),
             (pullDownMenu.ID_NEW_GAUGE, 'Gauge', 'Create gauge control'),
             (pullDownMenu.ID_NEW_SPIN_CTRL, 'SpinCtrl', 'Create spin control'),
             (pullDownMenu.ID_NEW_SCROLL_BAR, 'ScrollBar', 'Create scroll bar'),
             (pullDownMenu.ID_NEW_TREE_CTRL, 'TreeCtrl', 'Create tree control'),
             (pullDownMenu.ID_NEW_LIST_CTRL, 'ListCtrl', 'Create list control'),
             (pullDownMenu.ID_NEW_HTML_WINDOW, 'HtmlWindow', 'Create HTML window'),
             (pullDownMenu.ID_NEW_CALENDAR_CTRL, 'CalendarCtrl', 'Create calendar control'),
             (pullDownMenu.ID_NEW_GENERIC_DIR_CTRL, 'GenericDirCtrl', 'Create generic dir control'),
             (pullDownMenu.ID_NEW_UNKNOWN, 'Unknown', 'Create custom control placeholder'),
             ],
            ['button', 'Buttons',
             (pullDownMenu.ID_NEW_BUTTON, 'Button', 'Create button'),
             (pullDownMenu.ID_NEW_BITMAP_BUTTON, 'BitmapButton', 'Create bitmap button'),
             (pullDownMenu.ID_NEW_RADIO_BUTTON, 'RadioButton', 'Create radio button'),
             (pullDownMenu.ID_NEW_SPIN_BUTTON, 'SpinButton', 'Create spin button'),
             ],
            ['box', 'Boxes',
             (pullDownMenu.ID_NEW_STATIC_BOX, 'StaticBox', 'Create static box'),
             (pullDownMenu.ID_NEW_CHECK_BOX, 'CheckBox', 'Create check box'),
             (pullDownMenu.ID_NEW_RADIO_BOX, 'RadioBox', 'Create radio box'),
             (pullDownMenu.ID_NEW_COMBO_BOX, 'ComboBox', 'Create combo box'),
             (pullDownMenu.ID_NEW_LIST_BOX, 'ListBox', 'Create list box'),
             (pullDownMenu.ID_NEW_CHECK_LIST, 'CheckListBox', 'Create check list control'),
             ],
            ['container', 'Containers',
             (pullDownMenu.ID_NEW_PANEL, 'Panel', 'Create panel'),
             (pullDownMenu.ID_NEW_NOTEBOOK, 'Notebook', 'Create notebook control'),
             (pullDownMenu.ID_NEW_TOOL_BAR, 'ToolBar', 'Create toolbar'),
             ],
            ['sizer', 'Sizers',
             (pullDownMenu.ID_NEW_BOX_SIZER, 'BoxSizer', 'Create box sizer'),
             (pullDownMenu.ID_NEW_STATIC_BOX_SIZER, 'StaticBoxSizer',
              'Create static box sizer'),
             (pullDownMenu.ID_NEW_GRID_SIZER, 'GridSizer', 'Create grid sizer'),
             (pullDownMenu.ID_NEW_FLEX_GRID_SIZER, 'FlexGridSizer',
              'Create flexgrid sizer'),
             (pullDownMenu.ID_NEW_SPACER, 'Spacer', 'Create spacer'),
             ]
            ]
        pullDownMenu.menuControls = [
            (pullDownMenu.ID_NEW_MENU, 'Menu', 'Create menu'),
            (pullDownMenu.ID_NEW_MENU_ITEM, 'MenuItem', 'Create menu item'),
            (pullDownMenu.ID_NEW_SEPARATOR, 'Separator', 'Create separator'),
            ]
        pullDownMenu.toolBarControls = [
            (pullDownMenu.ID_NEW_TOOL, 'Tool', 'Create tool'),
            (pullDownMenu.ID_NEW_SEPARATOR, 'Separator', 'Create separator'),
            ['control', 'Various controls',
             (pullDownMenu.ID_NEW_STATIC_TEXT, 'Label', 'Create static label'),
             (pullDownMenu.ID_NEW_STATIC_LINE, 'Line', 'Create static line'),
             (pullDownMenu.ID_NEW_TEXT_CTRL, 'TextBox', 'Create text box control'),
             (pullDownMenu.ID_NEW_CHOICE, 'Choice', 'Create choice control'),
             (pullDownMenu.ID_NEW_SLIDER, 'Slider', 'Create slider control'),
             (pullDownMenu.ID_NEW_GAUGE, 'Gauge', 'Create gauge control'),
             (pullDownMenu.ID_NEW_SCROLL_BAR, 'ScrollBar', 'Create scroll bar'),
             (pullDownMenu.ID_NEW_LIST_CTRL, 'ListCtrl', 'Create list control'),
             ],
            ['button', 'Buttons',
             (pullDownMenu.ID_NEW_BUTTON, 'Button', 'Create button'),
             (pullDownMenu.ID_NEW_BITMAP_BUTTON, 'BitmapButton', 'Create bitmap button'),
             (pullDownMenu.ID_NEW_RADIO_BUTTON, 'RadioButton', 'Create radio button'),
             (pullDownMenu.ID_NEW_SPIN_BUTTON, 'SpinButton', 'Create spin button'),
             ],
            ['box', 'Boxes',
             (pullDownMenu.ID_NEW_STATIC_BOX, 'StaticBox', 'Create static box'),
             (pullDownMenu.ID_NEW_CHECK_BOX, 'CheckBox', 'Create check box'),
             (pullDownMenu.ID_NEW_RADIO_BOX, 'RadioBox', 'Create radio box'),
             (pullDownMenu.ID_NEW_COMBO_BOX, 'ComboBox', 'Create combo box'),
             (pullDownMenu.ID_NEW_LIST_BOX, 'ListBox', 'Create list box'),
             (pullDownMenu.ID_NEW_CHECK_LIST, 'CheckListBox',
              'Create check list control'),
             ],
            ]

        # Initialize
        self.clipboard = None
        self.Clear()

        # Other events
        EVT_IDLE(self, self.OnIdle)
        EVT_CLOSE(self, self.OnCloseWindow)
        EVT_LEFT_DOWN(self, self.OnLeftDown)

    def OnNew(self, evt):
        self.Clear()

    def OnOpen(self, evt):
        if not self.AskSave(): return
        dlg = wxFileDialog(self, 'Open', os.path.dirname(self.dataFile),
                           '', '*.xrc', wxOPEN | wxCHANGE_DIR)
        if dlg.ShowModal() == wxID_OK:
            path = dlg.GetPath()
            self.SetStatusText('Loading...')
            wxYield()
            wxBeginBusyCursor()
            if self.Open(path):
                self.SetStatusText('Data loaded')
            else:
                self.SetStatusText('Failed')
            wxEndBusyCursor()
        dlg.Destroy()

    def OnSaveOrSaveAs(self, evt):
        if evt.GetId() == wxID_SAVEAS or not self.dataFile:
            if self.dataFile: defaultName = ''
            else: defaultName = 'UNTITLED.xrc'
            dlg = wxFileDialog(self, 'Save As', os.path.dirname(self.dataFile),
                               defaultName, '*.xrc',
                               wxSAVE | wxOVERWRITE_PROMPT | wxCHANGE_DIR)
            if dlg.ShowModal() == wxID_OK:
                path = dlg.GetPath()
                dlg.Destroy()
            else:
                dlg.Destroy()
                return
        else:
            path = self.dataFile
        self.SetStatusText('Saving...')
        wxYield()
        wxBeginBusyCursor()
        try:
            self.Save(path)
            self.dataFile = path
            self.SetStatusText('Data saved')
        except IOError:
            self.SetStatusText('Failed')
        wxEndBusyCursor()

    def OnExit(self, evt):
        self.Close()

    def OnUndo(self, evt):
        # Extra check to not mess with idle updating
        if undoMan.CanUndo():
            undoMan.Undo()

    def OnRedo(self, evt):
        if undoMan.CanRedo():
            undoMan.Redo()

    def OnCopy(self, evt):
        selected = tree.selection
        if not selected: return         # key pressed event
        xxx = tree.GetPyData(selected)
        self.clipboard = xxx.element.cloneNode(true)
        self.SetStatusText('Copied')

    def OnPaste(self, evt):
        selected = tree.selection
        if not selected: return         # key pressed event
        # For pasting with Ctrl pressed
        if evt.GetId() == pullDownMenu.ID_PASTE_SIBLING: appendChild = false
        else: appendChild = not tree.NeedInsert(selected)
        xxx = tree.GetPyData(selected)
        if not appendChild:
            # If has next item, insert, else append to parent
            nextItem = tree.GetNextSibling(selected)
            parentLeaf = tree.GetItemParent(selected)
        # Expanded container (must have children)
        elif tree.IsExpanded(selected) and tree.GetChildrenCount(selected, false):
            # Insert as first child
            nextItem = tree.GetFirstChild(selected, 0)[0]
            parentLeaf = selected
        else:
            # No children or unexpanded item - appendChild stays true
            nextItem = wxTreeItemId()   # no next item
            parentLeaf = selected
        parent = tree.GetPyData(parentLeaf).treeObject()

        # Create a copy of clipboard element
        elem = self.clipboard.cloneNode(true)
        # Tempopary xxx object to test things
        xxx = MakeXXXFromDOM(parent, elem)

        # Check compatibility
        error = false
        # Top-level
        x = xxx.treeObject()
        if x.__class__ in [xxxDialog, xxxFrame, xxxMenuBar]:
            # Top-level classes
            if parent.__class__ != xxxMainNode: error = true
        elif x.__class__ == xxxToolBar:
            # Toolbar can be top-level of child of panel or frame
            if parent.__class__ not in [xxxMainNode, xxxPanel, xxxFrame]: error = true
        elif x.__class__ == xxxPanel and parent.__class__ == xxxMainNode:
            pass
        elif x.__class__ == xxxSpacer:
            if not parent.isSizer: error = true
        elif x.__class__ == xxxSeparator:
            if not parent.__class__ in [xxxMenu, xxxToolBar]: error = true
        elif x.__class__ == xxxTool:
            if parent.__class__ != xxxToolBar: error = true
        elif x.__class__ == xxxMenuItem:
            if not parent.__class__ in [xxxMenuBar, xxxMenu]: error = true
        elif x.isSizer and parent.__class__ == xxxNotebook: error = true
        else:                           # normal controls can be almost anywhere
            if parent.__class__ == xxxMainNode or \
               parent.__class__ in [xxxMenuBar, xxxMenu]: error = true
        if error:
            if parent.__class__ == xxxMainNode: parentClass = 'root'
            else: parentClass = parent.className
            wxLogError('Incompatible parent/child: parent is %s, child is %s!' %
                       (parentClass, x.className))
            return

        # Check parent and child relationships.
        # If parent is sizer or notebook, child is of wrong class or
        # parent is normal window, child is child container then detach child.
        isChildContainer = isinstance(xxx, xxxChildContainer)
        if isChildContainer and \
           ((parent.isSizer and not isinstance(xxx, xxxSizerItem)) or \
           (isinstance(parent, xxxNotebook) and not isinstance(xxx, xxxNotebookPage)) or \
           not (parent.isSizer or isinstance(parent, xxxNotebook))):
            elem.removeChild(xxx.child.element) # detach child
            elem.unlink()           # delete child container
            elem = xxx.child.element # replace
            # This may help garbage collection
            xxx.child.parent = None
            isChildContainer = false
        # Parent is sizer or notebook, child is not child container
        if parent.isSizer and not isChildContainer and not isinstance(xxx, xxxSpacer):
            # Create sizer item element
            sizerItemElem = MakeEmptyDOM('sizeritem')
            sizerItemElem.appendChild(elem)
            elem = sizerItemElem
        elif isinstance(parent, xxxNotebook) and not isChildContainer:
            pageElem = MakeEmptyDOM('notebookpage')
            pageElem.appendChild(elem)
            elem = pageElem
        # Insert new node, register undo
        newItem = tree.InsertNode(parentLeaf, parent, elem, nextItem)
        undoMan.RegisterUndo(UndoPasteCreate(parentLeaf, parent, newItem, selected))
        # Scroll to show new item (!!! redundant?)
        tree.EnsureVisible(newItem)
        tree.SelectItem(newItem)
        if not tree.IsVisible(newItem):
            tree.ScrollTo(newItem)
            tree.Refresh()
        # Update view?
        if g.testWin and tree.IsHighlatable(newItem):
            if conf.autoRefresh:
                tree.needUpdate = true
                tree.pendingHighLight = newItem
            else:
                tree.pendingHighLight = None
        self.modified = true
        self.SetStatusText('Pasted')

    def OnCutDelete(self, evt):
        selected = tree.selection
        if not selected: return         # key pressed event
        # Undo info
        if evt.GetId() == wxID_CUT:
            self.lastOp = 'CUT'
            status = 'Removed to clipboard'
        else:
            self.lastOp = 'DELETE'
            status = 'Deleted'
        # Delete testWin?
        if g.testWin:
            # If deleting top-level item, delete testWin
            if selected == g.testWin.item:
                g.testWin.Destroy()
                g.testWin = None
            else:
                # Remove highlight, update testWin
                if g.testWin.highLight:
                    g.testWin.highLight.Remove()
                tree.needUpdate = true
        # Prepare undo data
        panel.Apply()
        index = tree.ItemFullIndex(selected)
        parent = tree.GetPyData(tree.GetItemParent(selected)).treeObject()
        elem = tree.RemoveLeaf(selected)
        undoMan.RegisterUndo(UndoCutDelete(index, parent, elem))
        if evt.GetId() == wxID_CUT:
            if self.clipboard: self.clipboard.unlink()
            self.clipboard = elem.cloneNode(true)
        tree.pendingHighLight = None
        tree.Unselect()
        panel.Clear()
        self.modified = true
        self.SetStatusText(status)

    def OnSelect(self, evt):
        print >> sys.stderr, 'Xperimental function!'
        wxYield()
        self.SetCursor(wxCROSS_CURSOR)
        self.CaptureMouse()

    def OnLeftDown(self, evt):
        pos = evt.GetPosition()
        self.SetCursor(wxNullCursor)
        self.ReleaseMouse()

    def OnEmbedPanel(self, evt):
        conf.embedPanel = evt.IsChecked()
        if conf.embedPanel:
            # Remember last dimentions
            conf.panelX, conf.panelY = self.miniFrame.GetPosition()
            conf.panelWidth, conf.panelHeight = self.miniFrame.GetSize()
            size = self.GetSize()
            pos = self.GetPosition()
            sizePanel = panel.GetSize()
            panel.Reparent(self.splitter)
            self.miniFrame.GetSizer().RemoveWindow(panel)
            wxYield()
            # Widen
            self.SetDimensions(pos.x, pos.y, size.x + sizePanel.x, size.y)
            self.splitter.SplitVertically(tree, panel, conf.sashPos)
            self.miniFrame.Show(false)
        else:
            conf.sashPos = self.splitter.GetSashPosition()
            pos = self.GetPosition()
            size = self.GetSize()
            sizePanel = panel.GetSize()
            self.splitter.Unsplit(panel)
            sizer = self.miniFrame.GetSizer()
            panel.Reparent(self.miniFrame)
            panel.Show(true)
            sizer.Add(panel, 1, wxEXPAND)
            self.miniFrame.Show(true)
            self.miniFrame.SetDimensions(conf.panelX, conf.panelY,
                                         conf.panelWidth, conf.panelHeight)
            wxYield()
            # Reduce width
            self.SetDimensions(pos.x, pos.y,
                               max(size.x - sizePanel.x, self.minWidth), size.y)

    def OnTest(self, evt):
        if not tree.selection: return   # key pressed event
        tree.ShowTestWindow(tree.selection)

    def OnRefresh(self, evt):
        # If modified, apply first
        selection = tree.selection
        if selection:
            xxx = tree.GetPyData(selection)
            if xxx and panel.IsModified():
                tree.Apply(xxx, selection)
        if g.testWin:
            # (re)create
            tree.CreateTestWin(g.testWin.item)
        tree.needUpdate = false

    def OnAutoRefresh(self, evt):
        conf.autoRefresh = evt.IsChecked()
        self.menuBar.Check(self.ID_AUTO_REFRESH, conf.autoRefresh)
        self.tb.ToggleTool(self.ID_AUTO_REFRESH, conf.autoRefresh)

    def OnAbout(self, evt):
        str = '%s %s\n\nRoman Rolinsky <rolinsky@mema.ucl.ac.be>' % \
              (progname, version)
        dlg = wxMessageDialog(self, str, 'About ' + progname, wxOK | wxCENTRE)
        dlg.ShowModal()
        dlg.Destroy()

    def OnReadme(self, evt):
        text = open(os.path.join(basePath, 'README'), 'r').read()
        dlg = ScrolledMessageDialog(self, text, "XRCed README")
        dlg.ShowModal()
        dlg.Destroy()

    # Simple emulation of python command line
    def OnDebugCMD(self, evt):
        import traceback
        while 1:
            try:
                exec raw_input('C:\> ')
            except EOFError:
                print '^D'
                break
            except:
                (etype, value, tb) =sys.exc_info()
                tblist =traceback.extract_tb(tb)[1:]
                msg =string.join(traceback.format_exception_only(etype, value)
                        +traceback.format_list(tblist))
                print msg

    def OnCreate(self, evt):
        selected = tree.selection
        if tree.ctrl: appendChild = false
        else: appendChild = not tree.NeedInsert(selected)
        xxx = tree.GetPyData(selected)
        if not appendChild:
            # If insert before
            if tree.shift:
                # If has previous item, insert after it, else append to parent
                nextItem = selected
                parentLeaf = tree.GetItemParent(selected)
            else:
                # If has next item, insert, else append to parent
                nextItem = tree.GetNextSibling(selected)
                parentLeaf = tree.GetItemParent(selected)
        # Expanded container (must have children)
        elif tree.shift and tree.IsExpanded(selected) \
           and tree.GetChildrenCount(selected, false):
            nextItem = tree.GetFirstChild(selected, 0)[0]
            parentLeaf = selected
        else:
            nextItem = wxTreeItemId()
            parentLeaf = selected
        parent = tree.GetPyData(parentLeaf)
        if parent.hasChild: parent = parent.child

        # Create element
        className = self.createMap[evt.GetId()]
        xxx = MakeEmptyXXX(parent, className)

        # Set default name for top-level windows
        if parent.__class__ == xxxMainNode:
            cl = xxx.treeObject().__class__
            frame.maxIDs[cl] += 1
            xxx.treeObject().name = '%s%d' % (defaultIDs[cl], frame.maxIDs[cl])
            xxx.treeObject().element.setAttribute('name', xxx.treeObject().name)

        # Insert new node, register undo
        elem = xxx.element
        newItem = tree.InsertNode(parentLeaf, parent, elem, nextItem)
        undoMan.RegisterUndo(UndoPasteCreate(parentLeaf, parent, newItem, selected))
        tree.EnsureVisible(newItem)
        tree.SelectItem(newItem)
        if not tree.IsVisible(newItem):
            tree.ScrollTo(newItem)
            tree.Refresh()
        # Update view?
        if g.testWin and tree.IsHighlatable(newItem):
            if conf.autoRefresh:
                tree.needUpdate = true
                tree.pendingHighLight = newItem
            else:
                tree.pendingHighLight = None

    # Expand/collapse subtree
    def OnExpand(self, evt):
        if tree.selection: tree.ExpandAll(tree.selection)
        else: tree.ExpandAll(tree.root)
    def OnCollapse(self, evt):
        if tree.selection: tree.CollapseAll(tree.selection)
        else: tree.CollapseAll(tree.root)

    def OnPullDownHighlight(self, evt):
        menuId = evt.GetMenuId()
        if menuId != -1:
            menu = evt.GetEventObject()
            help = menu.GetHelpString(menuId)
            self.SetStatusText(help)
        else:
            self.SetStatusText('')

    def OnUpdateUI(self, evt):
        if evt.GetId() in [wxID_CUT, wxID_COPY, self.ID_DELETE]:
            evt.Enable(tree.selection is not None and tree.selection != tree.root)
        elif evt.GetId() == wxID_PASTE:
            evt.Enable((self.clipboard and tree.selection) != None)
        elif evt.GetId() == self.ID_TEST:
            evt.Enable(tree.selection is not None and tree.selection != tree.root)
        elif evt.GetId() == wxID_UNDO:  evt.Enable(undoMan.CanUndo())
        elif evt.GetId() == wxID_REDO:  evt.Enable(undoMan.CanRedo())

    def OnIdle(self, evt):
        if self.inIdle: return          # Recursive call protection
        self.inIdle = true
        if tree.needUpdate:
            if conf.autoRefresh:
                if g.testWin:
                    self.SetStatusText('Refreshing test window...')
                    # (re)create
                    tree.CreateTestWin(g.testWin.item)
                    wxYield()
                    self.SetStatusText('')
                tree.needUpdate = false
        elif tree.pendingHighLight:
            tree.HighLight(tree.pendingHighLight)
        else:
            evt.Skip()
        self.inIdle = false

    # We don't let close panel window
    def OnCloseMiniFrame(self, evt):
        return

    def OnCloseWindow(self, evt):
        if not self.AskSave(): return
        if g.testWin: g.testWin.Destroy()
        # Destroy cached windows
        panel.cacheParent.Destroy()
        if not panel.GetPageCount() == 2:
            panel.page2.Destroy()
        conf.x, conf.y = self.GetPosition()
        conf.width, conf.height = self.GetSize()
        if conf.embedPanel:
            conf.sashPos = self.splitter.GetSashPosition()
        else:
            conf.panelX, conf.panelY = self.miniFrame.GetPosition()
            conf.panelWidth, conf.panelHeight = self.miniFrame.GetSize()
        evt.Skip()

    def Clear(self):
        self.dataFile = ''
        if self.clipboard:
            self.clipboard.unlink()
            self.clipboard = None
        undoMan.Clear()
        self.modified = false
        tree.Clear()
        panel.Clear()
        if g.testWin:
            g.testWin.Destroy()
            g.testWin = None
        self.SetTitle(progname)
        # Numbers for new controls
        self.maxIDs = {}
        self.maxIDs[xxxPanel] = self.maxIDs[xxxDialog] = self.maxIDs[xxxFrame] = \
        self.maxIDs[xxxMenuBar] = self.maxIDs[xxxMenu] = self.maxIDs[xxxToolBar] = 0

    def Open(self, path):
        if not os.path.exists(path):
            wxLogError('File does not exists: %s' % path)
            return false
        # Try to read the file
        try:
            f = open(path)
            self.Clear()
            # Parse first line to get encoding (!! hack, I don't know a better way)
            line = f.readline()
            mo = re.match(r'^<\?xml ([^<>]* )?encoding="(?P<encd>[^<>].*)"\?>', line)
            # Build wx tree
            f.seek(0)
            dom = minidom.parse(f)
            # Set encoding global variable and document encoding property
            import xxx
            if mo:
                dom.encoding = xxx.currentEncoding = mo.group('encd')
            else:
                xxx.currentEncoding = 'iso-8859-1'
                dom.encoding = ''
            f.close()
            # Change dir
            dir = os.path.dirname(path)
            if dir: os.chdir(dir)
            tree.SetData(dom)
            self.dataFile = path
            self.SetTitle(progname + ': ' + os.path.basename(path))
        except:
            # Nice exception printing
            inf = sys.exc_info()
            wxLogError(traceback.format_exception(inf[0], inf[1], None)[-1])
            wxLogError('Error reading file: %s' % path)
            return false
        return true

    def Indent(self, node, indent = 0):
        # Copy child list because it will change soon
        children = node.childNodes[:]
        # Main node doesn't need to be indented
        if indent:
            text = self.domCopy.createTextNode('\n' + ' ' * indent)
            node.parentNode.insertBefore(text, node)
        if children:
            # Append newline after last child, except for text nodes
            if children[-1].nodeType == minidom.Node.ELEMENT_NODE:
                text = self.domCopy.createTextNode('\n' + ' ' * indent)
                node.appendChild(text)
            # Indent children which are elements
            for n in children:
                if n.nodeType == minidom.Node.ELEMENT_NODE:
                    self.Indent(n, indent + 2)

    def Save(self, path):
        try:
            # Apply changes
            if tree.selection and panel.IsModified():
                self.OnRefresh(wxCommandEvent())
            f = open(path, 'w')
            # Make temporary copy for formatting it
            # !!! We can't clone dom node, it works only once
            #self.domCopy = tree.dom.cloneNode(true)
            self.domCopy = MyDocument()
            mainNode = self.domCopy.appendChild(tree.mainNode.cloneNode(true))
            self.Indent(mainNode)
            self.domCopy.writexml(f, encoding=tree.rootObj.params['encoding'].value())
            f.close()
            self.domCopy.unlink()
            self.domCopy = None
            self.modified = false
            panel.SetModified(false)
        except:
            wxLogError('Error writing file: %s' % path)
            raise

    def AskSave(self):
        if not (self.modified or panel.IsModified()): return true
        flags = wxICON_EXCLAMATION | wxYES_NO | wxCANCEL | wxCENTRE
        dlg = wxMessageDialog( self, 'File is modified. Save before exit?',
                               'Save before too late?', flags )
        say = dlg.ShowModal()
        dlg.Destroy()
        if say == wxID_YES:
            self.OnSaveOrSaveAs(wxCommandEvent(wxID_SAVE))
            # If save was successful, modified flag is unset
            if not self.modified: return true
        elif say == wxID_NO:
            self.modified = false
            panel.SetModified(false)
            return true
        return false

    def SaveUndo(self):
        pass                            # !!!

################################################################################

def usage():
    print >> sys.stderr, 'usage: xrced [-dvh] [file]'

class App(wxApp):
    def OnInit(self):
        global debug
        # Process comand-line
        try:
            opts, args = getopt.getopt(sys.argv[1:], 'dvh')
        except getopt.GetoptError:
            print >> sys.stderr, 'Unknown option'
            usage()
            sys.exit(1)
        for o,a in opts:
            if o == '-h':
                usage()
                sys.exit(0)
            elif o == '-d':
                debug = true
            elif o == '-v':
                print 'XRCed version', version
                sys.exit(0)

        self.SetAppName('xrced')
        # Settings
        global conf
        conf = g.conf = wxConfig(style = wxCONFIG_USE_LOCAL_FILE)
        conf.autoRefresh = conf.ReadInt('autorefresh', true)
        pos = conf.ReadInt('x', -1), conf.ReadInt('y', -1)
        size = conf.ReadInt('width', 800), conf.ReadInt('height', 600)
        conf.embedPanel = conf.ReadInt('embedPanel', true)
        conf.sashPos = conf.ReadInt('sashPos', 200)
        if not conf.embedPanel:
            conf.panelX = conf.ReadInt('panelX', -1)
            conf.panelY = conf.ReadInt('panelY', -1)
        else:
            conf.panelX = conf.panelY = -1
        conf.panelWidth = conf.ReadInt('panelWidth', 200)
        conf.panelHeight = conf.ReadInt('panelHeight', 200)
        conf.panic = not conf.HasEntry('nopanic')
        # Add handlers
        wxFileSystem_AddHandler(wxMemoryFSHandler())
        wxInitAllImageHandlers()
        # Create main frame
        frame = Frame(pos, size)
        frame.Show(true)
        # Load resources from XRC file (!!! should be transformed to .py later?)
        frame.res = wxXmlResource('')
        frame.res.Load(os.path.join(basePath, 'xrced.xrc'))

        # Load file after showing
        if args:
            conf.panic = false
            frame.open = frame.Open(args[0])

        return true

    def OnExit(self):
        # Write config
        global conf
        wc = wxConfigBase_Get()
        wc.WriteInt('autorefresh', conf.autoRefresh)
        wc.WriteInt('x', conf.x)
        wc.WriteInt('y', conf.y)
        wc.WriteInt('width', conf.width)
        wc.WriteInt('height', conf.height)
        wc.WriteInt('embedPanel', conf.embedPanel)
        if not conf.embedPanel:
            wc.WriteInt('panelX', conf.panelX)
            wc.WriteInt('panelY', conf.panelY)
        wc.WriteInt('sashPos', conf.sashPos)
        wc.WriteInt('panelWidth', conf.panelWidth)
        wc.WriteInt('panelHeight', conf.panelHeight)
        wc.WriteInt('nopanic', 1)
        wc.Flush()

def main():
    app = App(0, useBestVisual=false)
    app.MainLoop()
    app.OnExit()
    global conf
    del conf

if __name__ == '__main__':
    main()
