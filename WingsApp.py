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

def CreateWing(): return wing.Wing()

class WingsApp(App):
    def __init__(self):
        App.__init__(self)
        
    def RegisterObjectTypes(self):
        App.RegisterObjectTypes(self)
        wing.type = cad.RegisterObjectType("Wing", CreateWing)
    
    def NewFrame(self, pos=wx.DefaultPosition, size=wx.DefaultSize):
        return WingsFrame(None, pos = pos, size = size)
    
