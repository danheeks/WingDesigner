import wx
import os
import sys

wings_dir = os.path.dirname(os.path.realpath(__file__))
pycad_dir = os.path.realpath(wings_dir + '/../../PyCAD/trunk')
sys.path.append(pycad_dir)
import cad
import wing
from App import App # from CAD
from WingsFrame import WingsFrame
import WingsContextTool
from HeeksConfig import HeeksConfig

def CreateWing(): return wing.Wing()

class WingsApp(App):
    def __init__(self):
        self.wings_dir = wings_dir
        App.__init__(self)
        
    def RegisterObjectTypes(self):
        App.RegisterObjectTypes(self)
        wing.type = cad.RegisterObjectType("Wing", CreateWing)
    
    def NewFrame(self, pos=wx.DefaultPosition, size=wx.DefaultSize):
        return WingsFrame(None, pos = pos, size = size)
    
    def ExportWing(self, object):
        config = HeeksConfig()
        default_directory = config.Read('WingsExportDirectory', self.GetDefaultDir())
        wildcard_string = 'STL files (*.stl)|*.stl'
        dialog = wx.FileDialog(self.frame, 'Export Wing STL File', default_directory, '', wildcard_string, wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        dialog.CenterOnParent()
        
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            object.ExportFiles(path)
            config.Write('WingsExportDirectory', dialog.GetDirectory())
        
    def GetObjectTools(self, object, from_tree_canvas = False):
        tools = App.GetObjectTools(self, object, from_tree_canvas)
        if object.GetType() == wing.type:
            tools.append(WingsContextTool.WingsObjectContextTool(object, "Export Wing", "export", self.ExportWing))
        return tools
    
