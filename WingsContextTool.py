import ContextTool
import wx

class WingsContextTool(ContextTool.CADContextTool):
    def __init__(self, title, bitmap_name, method):
        ContextTool.CADContextTool.__init__(self, title, bitmap_name, method)
        
    def BitmapPath(self):
        return wx.GetApp().wings_dir + '/bitmaps/'+ self.BitmapName() + '.png'
   

class WingsObjectContextTool(WingsContextTool):
    def __init__(self, object, title, bitmap_name, method):
        WingsContextTool.__init__(self, title, bitmap_name, method)
        self.object = object
        
    def Run(self, event):
        self.method(self.object)
        
     