import cad
import math
import geom
import tempfile
import os
from Object import Object
from Object import PyProperty

property_titles = ['leading edge', 'trailing edge', 'root profile', 'tip profile', 'angle graph']
sketch_xml_names = ['LeadingEdge', 'TrailingEdge', 'RootProfile', 'TipProfile', 'AngleGraph']
wing_for_tools = None
drawing_sketches = False
stl_to_add_to = None
section_index = None

wings_dir = os.path.dirname(os.path.realpath(__file__))
list_of_things_to_not_delete = []

type = 0

class Wing(Object):
    def __init__(self):
        Object.__init__(self, 0)
        
        # properties
        self.sketch_ids = [0,0,0,0,0]
        self.mirror = False
        self.centre_straight = True
        self.color = cad.Color(128, 128, 128)
        self.draw_list = None
        
        self.box = None  # if box is None, then the curves need reloading
        self.ResetCurves()
        
    def GetType(self):
        return type

    def TypeName(self):
        return "Wing"
    
    def GetTypeString(self):
        return self.TypeName()
    
    def HasColor(self):
        return False
    
    def GetIconFilePath(self):
        return wings_dir + '/icons/wing.png'
        
    def ResetCurves(self):
        self.curves = []
        for id in self.sketch_ids:
            self.curves.append(None)
            
    def KillGLLists(self):
        if self.draw_list:
            cad.DrawDeleteList(self.draw_list)
        self.draw_list = None
                                            
    def Recalculate(self):
        self.KillGLLists()
        self.box = None
        self.ResetCurves()
        
    def SketchesToCurves(self):
        for i in range(0, len(self.sketch_ids)):
            self.curves[i] = GetCurveFromSketch(self.sketch_ids[i])
        self.root_profile_invtm = GetTmFromCurve(self.curves[2])
        self.tip_profile_invtm = GetTmFromCurve(self.curves[3])
        
    def CalculateBox(self):
        self.box = geom.Box3D()
        for i in range(0, len(self.sketch_ids)):
            if self.curves[i] != None:
                curve_box = self.curves[i].GetBox()
                self.box.InsertBox(geom.Box3D(curve_box.MinX(), curve_box.MinY(), 0.0, curve_box.MaxX(), curve_box.MaxY(), 0.0))

    def GetUnitizedSectionPoints(self, tip_fraction):
        # the start point will be geom.Point(0,0) and the last point will be geom.Point(1,0)
        pts = []
            
        if self.curves[2] and self.curves[3]:
            perim = self.curves[2].Perim()
            cur_perim = 0.0
            prev_v = None
            
            for v in self.curves[2].GetVertices():
                if prev_v != None:
                    span = geom.Span(prev_v.p, v, False)
                    cur_perim += span.Length()
                fraction = cur_perim / perim
                root_point = GetUnitizedPoint(self.curves[2], fraction, self.root_profile_invtm, self.centre_straight and (tip_fraction < 0.01))
                if root_point == None: return
                tip_point = GetUnitizedPoint(self.curves[3], fraction, self.tip_profile_invtm, self.centre_straight and (tip_fraction < 0.01))
                if tip_point == None: return
                vec = tip_point - root_point
                p = root_point + vec * tip_fraction
                pts.append(p)
                prev_v = v
        return pts

    def GetLeadingEdgePoint(self, fraction):
        perim = self.curves[0].Perim()
        return self.curves[0].PerimToPoint(perim * fraction)
        
    def GetTrailingEdgePoint(self, leading_edge_point):
        backward_curve = geom.Curve()
        backward_curve.Append(leading_edge_point)
        backward_curve.Append(leading_edge_point + geom.Point(0, -1000.0))
        pts = backward_curve.Intersections(self.curves[1])
        if len(pts) == 0:
            return None
        return pts[0]
        
    def GetAngle(self, fraction):
        if self.curves[4] == None:
            return 0.0
        box = self.curves[4].GetBox()
        x = box.MinX() + box.Width() * fraction
        curve = geom.Curve()
        curve.Append(geom.Point(x, box.MinY() - 1.0))
        curve.Append(geom.Point(x, box.MaxY() + 1.0))
        pts = curve.Intersections(self.curves[4])
        if len(pts) == 0: return 0.0
        angle = pts[0].y - box.MinY()
        return angle
        
    def GetOrderedSectionPoints(self, fraction):
        leading_edge_p = self.GetLeadingEdgePoint(fraction)
        if leading_edge_p == None: return
        trailing_edge_p = self.GetTrailingEdgePoint(leading_edge_p)
        if trailing_edge_p == None:
            v = geom.Point(0,0)
            length = 0.0
        else:
            v = trailing_edge_p - leading_edge_p
            length = leading_edge_p.Dist(trailing_edge_p)
        pts = self.GetUnitizedSectionPoints(fraction)
        if pts == None: return
        pts2 = []
        a = self.GetAngle(fraction) * 0.01745329251994
        for pt in pts:
            pt.Rotate(a)
            hpoint = leading_edge_p + v * pt.x
            pts2.append(geom.Point3D(hpoint.x, hpoint.y, pt.y * length))
        return pts2

    def DrawSection(self, span):
        if drawing_sketches:
            global stl_to_add_to
            stl_to_add_to = geom.Stl()
            
        xmax = self.curves[1].LastVertex().p.x
        if xmax < 0.001: return
        fraction0 = span.p.x / xmax
        fraction1 = span.v.p.x / xmax
        pts0 = self.GetOrderedSectionPoints(fraction0)
        if pts0 == None: return
        pts1 = self.GetOrderedSectionPoints(fraction1)
        if pts1 == None: return
        
        prev_p0 = None
        prev_p1 = None
        
        if drawing_sketches:
            mirror = False
        else:
            mirror = self.mirror
    
        for p0, p1 in zip(pts0, pts1):
            DrawTrianglesBetweenPoints(prev_p0, prev_p1, p0, p1, mirror)
            prev_p0 = p0
            prev_p1 = p1
            
        if drawing_sketches:
            if section_index != 7:
                return
            surface = stl_to_add_to.GetFlattenedSurface()
            outline = surface.Shadow(geom.Matrix(), True)
            outline.Offset(-2.0)
            curves = surface.GetTrianglesAsCurveList()
            area_fp = tempfile.gettempdir() + '/area.dxf'
            for curve in curves:
                outline.Append(curve)
            outline.WriteDxf(area_fp)
            cad.Import(area_fp)
        
    def OnGlCommands(self, select, marked, no_color):
        if not no_color:
            cad.DrawEnableLighting()
            cad.Material(self.color).glMaterial(1.0)
            
        if self.draw_list:
            cad.DrawCallList(self.draw_list)
        else:
            self.draw_list = cad.DrawNewList()
            if self.box == None:
                self.SketchesToCurves()
                self.CalculateBox()
            
            if self.curves[0] != None and self.curves[1] != None: # can't draw anything without a leading edge nor a trailing edge
                global section_index
                section_index = 0
                
                # use the spans of trailing edge to define the sections
                for span in self.curves[1].GetSpans():
                    self.DrawSection(span)
                    section_index += 1
            cad.DrawEndList()
            
        if not no_color:
            cad.DrawDisableLighting()
                
    def GetProperties(self):
        properties = []
        for i in range(0, 5):
            p = PropertySketch(self, i)
            list_of_things_to_not_delete.append(p) # to not let it be deleted
            properties.append(p)
        p = PyProperty('mirror', 'mirror', self, self.Recalculate)
        list_of_things_to_not_delete.append(p)
        properties.append(p)
        p = PyProperty('centre_straight', 'centre_straight', self, self.Recalculate)
        list_of_things_to_not_delete.append(p)  
        properties.append(p)
        return properties
        
    def GetColor(self):
        return self.color
        
    def SetColor(self, col):
        self.color = col
        
    def GetBox(self, box):
        if self.box == None:
            self.SketchesToCurves()
            self.CalculateBox()

        box.InsertBox(self.box)
        
    def WriteXml(self):
        cad.SetXmlValue('col', self.color.ref())
        for i in range(0, len(self.sketch_ids)):
            cad.SetXmlValue(sketch_xml_names[i], self.sketch_ids[i])
        cad.SetXmlValue('mirror', self.mirror)
        cad.SetXmlValue('centre_straight', self.centre_straight)
        
    def ReadXml(self):
        self.color = cad.Color(cad.GetXmlInt('col', self.color.ref()))
        for i in range(0, len(sketch_xml_names)):
            self.sketch_ids[i] = cad.GetXmlInt(sketch_xml_names[i], 0)
        self.mirror = cad.GetXmlBool('mirror')
        self.centre_straight = cad.GetXmlBool('centre_straight')
        Object.ReadXml(self)
        
    def GetTools(self):
        global wing_for_tools
        wing_for_tools = self
        self.AddTool('Make Sketches', MakeSketches)
        
    def MakeSketches(self):
        global drawing_sketches
        drawing_sketches = True
        self.OnRenderTriangles()
        drawing_sketches = False

def XMLRead():
    new_object = Wing()
    s = cad.GetXmlValue('col')
    if s != '':
        new_object.color = cad.Color(int(s))
    for i in range(0, len(sketch_xml_names)):
        new_object.sketch_ids[i] = int(cad.GetXmlValue(sketch_xml_names[i]))
    s = cad.GetXmlValue('mirror')
    if s != '': new_object.mirror = bool(s)
    
    return new_object

def GetCurveFromSketch(sketch_id):
    sketch_file_path = tempfile.gettempdir() + '/sketch.dxf'
    sketch = cad.GetObjectFromId(cad.OBJECT_TYPE_SKETCH, sketch_id)
    if sketch == None:
        return
    else:
        sketch.WriteDxf(sketch_file_path)
        area = geom.AreaFromDxf(sketch_file_path)
        curves = area.GetCurves()
        if len(curves)>0:
            curve = curves[0]
            if curve.NumVertices() > 1:
                if curve.FirstVertex().p.x > curve.LastVertex().p.x:
                    curve.Reverse()
                return curve
    return None

class PropertySketch(cad.Property):
    def __init__(self, wing, index):
        cad.Property.__init__(self, cad.PROPERTY_TYPE_INT, property_titles[index], wing)
        self.index = index
        self.wing = wing
        
    def GetType(self):
        # why is this not using base class?
        return cad.PROPERTY_TYPE_INT
    
    def GetTitle(self):
        # why is this not using base class?
        return property_titles[self.index]
        
    def editable(self):
        # why is this not using base class?
        return True
    
    def SetInt(self, value):
        self.wing.sketch_ids[self.index] = value
        self.wing.Recalculate()
        
    def GetInt(self):
        return self.wing.sketch_ids[self.index]
    
    def MakeACopy(self, o):
        p = PropertySketch(self.wing, self.index)
        list_of_things_to_not_delete.append(p)
        return p
        
def AddTriangleToSketch(x0, y0, z0, x1, y1, z1, x2, y2, z2):
    p0 = geom.Point3D(x0,y0,z0)
    p1 = geom.Point3D(x1,y1,z1)
    p2 = geom.Point3D(x2,y2,z2)
    if p0 == p1:
        return
    if p1 == p2:
        return
    if p2 == p0:
        return
    stl_to_add_to.Add(p0, p1, p2)

def DrawTriangle(x0, y0, z0, x1, y1, z1, x2, y2, z2):
    if drawing_sketches:
        AddTriangleToSketch(x0, y0, z0, x1, y1, z1, x2, y2, z2)
    else:
        cad.DrawTriangle(x0, y0, z0, x1, y1, z1, x2, y2, z2)

def DrawTrianglesBetweenPoints(prev_p0, prev_p1, p0, p1, mirror):
    if prev_p0 == None:
        return
    DrawTriangle(p1.x, p1.y, p1.z, prev_p0.x, prev_p0.y, prev_p0.z, p0.x, p0.y, p0.z)
    DrawTriangle(prev_p1.x, prev_p1.y, prev_p1.z, prev_p0.x, prev_p0.y, prev_p0.z, p1.x, p1.y, p1.z)
    if mirror:
        cad.DrawTriangle(-prev_p0.x, prev_p0.y, prev_p0.z, -p1.x, p1.y, p1.z, -p0.x, p0.y, p0.z)
        cad.DrawTriangle(-prev_p0.x, prev_p0.y, prev_p0.z, -prev_p1.x, prev_p1.y, prev_p1.z, -p1.x, p1.y, p1.z)
    cad.EndLinesOrTriangles()

def GetMinXPoint(curve):
    minxp = None
    for v in curve.GetVertices():
        if minxp == None or v.p.x < minxp.x:
            minxp = v.p
    return minxp

def GetMaxXPoint(curve):
    maxxp = None
    for v in curve.GetVertices():
        if maxxp == None or v.p.x > maxxp.x:
            maxxp = v.p
    return maxxp

def GetTmFromCurve(curve):
    if curve == None:
        return
    ps = GetMinXPoint(curve)
    pe = GetMaxXPoint(curve)
    vx = pe - ps
    vx.Normalize()
    vy = ~vx
    o = geom.Point3D(ps.x, ps.y, 0.0)
    vvx = geom.Point3D(vx.x, vx.y, 0.0)
    vvy = geom.Point3D(vy.x, vy.y, 0.0)
    tm = geom.Matrix(o, vvx, vvy)
    return tm.Inverse()

def GetUnitizedPoint(curve, fraction, invtm, centre_straight):
    if curve == None: return
    xdist = curve.LastVertex().p.Dist(curve.FirstVertex().p)
    if xdist < 0.00001:
        return geom.Point(0,0)
    scale = 1.0/xdist
    p = curve.PerimToPoint(curve.Perim() * fraction)
    p.Transform(invtm)
    pu = geom.Point(p.x * scale, p.y * scale)
    if centre_straight:
        pu.y = 0
    return pu
 
def MakeSketches():
    global wing_for_tools
    wing_for_tools.MakeSketches()