import sys
import os
import wx

wings_dir = os.path.dirname(os.path.realpath(__file__))
pycad_dir = os.path.realpath(wings_dir + '/../../PyCAD/trunk')
sys.path.append(pycad_dir)
wings = []

import cad
from wing import Wing
from Frame import Frame # from CAD

class WingsFrame(Frame):
    def __init__(self, parent, id=-1, pos=wx.DefaultPosition, size=wx.DefaultSize, style=wx.DEFAULT_FRAME_STYLE, name=wx.FrameNameStr):
        Frame.__init__(self, parent, id, pos, size, style, name)
        
    def OnWing(self, e):
        o = Wing()
        wings.append(o)
        cad.AddUndoably(o, None, None)

    def AddExtraMenus(self):
        self.bitmap_path = wings_dir + '/icons'
        self.AddMenu('&Wings')
        self.AddMenuItem('Add a Wing', self.OnWing, None, 'wing')        
