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
DRAWING_MODE_RENDER = 0
DRAWING_MODE_SKETCHES = 1
DRAWING_MODE_TRIANGLES = 2
DRAWING_MODE_STL = 3
drawing_mode = DRAWING_MODE_RENDER
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
        self.render_wing = True
        self.render_pattern = False
        self.pattern_border = 0.0
        self.pattern_x_step = 30.0
        self.pattern_wall = 2.0
        self.split_into_pieces = 0
        self.split_wall_width = 0.0
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
                
        if self.mirror:
            self.box.InsertPoint(-500.0, self.box.MaxY(), 0.0)

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
        if drawing_mode == DRAWING_MODE_SKETCHES:
            global stl_to_add_to
            stl_to_add_to = geom.Stl()
            
        perim = self.curves[1].Perim()
        if perim < 0.001: return
        fraction0 = self.curves[1].PointToPerim(span.p)/perim
        fraction1 = self.curves[1].PointToPerim(span.v.p)/perim
        pts0 = self.GetOrderedSectionPoints(fraction0)
        if pts0 == None: return
        pts1 = self.GetOrderedSectionPoints(fraction1)
        if pts1 == None: return
        
        prev_p0 = None
        prev_p1 = None
        
        if drawing_mode == DRAWING_MODE_SKETCHES:
            mirror = False
        else:
            mirror = self.mirror
    
        for p0, p1 in zip(pts0, pts1):
            self.DrawTrianglesBetweenPoints(prev_p0, prev_p1, p0, p1, mirror)
            prev_p0 = p0
            prev_p1 = p1
            
        if drawing_mode == DRAWING_MODE_SKETCHES:
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

    def DrawEndFaceTriangle(self, pts, i0, i1, i2):
        self.DrawTriangle(pts[i0].x, pts[i0].y, pts[i0].z, pts[i1].x, pts[i1].y, pts[i1].z, pts[i2].x, pts[i2].y, pts[i2].z, True)
        
    def DrawEndFace(self):
        pts = self.GetOrderedSectionPoints(1.0) # get end profile
        
        num = len(pts)
        odd = ((num % 2) != 0)
        halfway = num/2
        end_point = num - 1
        
        # render even number of points, todo render odd number of points
        for i in range(0, int(halfway)):
            # make two triangles
            self.DrawEndFaceTriangle(pts, end_point,i,i + 1)
            self.DrawEndFaceTriangle(pts, end_point-1,end_point,i+1)
            end_point -= 1

    def DrawTriangle(self, x0, y0, z0, x1, y1, z1, x2, y2, z2, mirror):
        if drawing_mode == DRAWING_MODE_SKETCHES:
            AddTriangleToSketch(x0, y0, z0, x1, y1, z1, x2, y2, z2)
        elif drawing_mode == DRAWING_MODE_TRIANGLES:
            self.AddTriangle(x0, y0, z0, x1, y1, z1, x2, y2, z2)
            if mirror:
                self.AddTriangle(-x1, y1, z1, -x0, y0, z0, -x2, y2, z2)
        elif drawing_mode == DRAWING_MODE_STL:
            AddTriangleToSketch(x0, y0, z0, x1, y1, z1, x2, y2, z2)
            if mirror:
                AddTriangleToSketch(-x1, y1, z1, -x0, y0, z0, -x2, y2, z2)
        else:
            cad.DrawTriangle(x0, y0, z0, x1, y1, z1, x2, y2, z2)
            if mirror:
                cad.DrawTriangle(-x1, y1, z1, -x0, y0, z0, -x2, y2, z2)

    def DrawTrianglesBetweenPoints(self, prev_p0, prev_p1, p0, p1, mirror):
        if prev_p0 == None:
            return
        self.DrawTriangle(p1.x, p1.y, p1.z, prev_p0.x, prev_p0.y, prev_p0.z, p0.x, p0.y, p0.z, mirror)
        self.DrawTriangle(prev_p1.x, prev_p1.y, prev_p1.z, prev_p0.x, prev_p0.y, prev_p0.z, p1.x, p1.y, p1.z, mirror)

    def MakePatternedArea(self, outline, wing_box):
        box = geom.Box(geom.Point(wing_box.MinX(), wing_box.MinY()), geom.Point(wing_box.MaxX(), wing_box.MaxY()))
        box.minxy.x -= 5.0
        box.minxy.y -= 5.0
        box.maxxy.x += 5.0
        box.maxxy.y += 5.0

        tx = self.pattern_x_step - self.pattern_wall * 2.309
        if tx < 0.0:
            return
        ty = self.pattern_y_step * 0.5 - self.pattern_wall
        if ty < 0.0:
            return
        
        a = geom.Area()
        
        x = box.MinX()
        while x < box.MaxX():
            y = box.MinY()
            while y < box.MaxY():
                c = geom.Curve()
                c.Append(geom.Point(x - tx*0.5, y))
                c.Append(geom.Point(x + tx*0.5, y))
                c.Append(geom.Point(x, y + ty))
                c.Append(geom.Point(x - tx*0.5, y))
                a.Append(c)
                
                c = geom.Curve()
                c.Append(geom.Point(x + self.pattern_x_step * 0.5, y))
                c.Append(geom.Point(x + self.pattern_x_step * 0.5 + tx*0.5, y + ty))
                c.Append(geom.Point(x + self.pattern_x_step * 0.5 - tx*0.5, y + ty))
                c.Append(geom.Point(x + self.pattern_x_step * 0.5, y))
                a.Append(c)
                
                c = geom.Curve()
                c.Append(geom.Point(x + self.pattern_x_step * 0.5 - tx*0.5, y + self.pattern_y_step * 0.5))
                c.Append(geom.Point(x + self.pattern_x_step * 0.5 + tx*0.5, y + self.pattern_y_step * 0.5))
                c.Append(geom.Point(x + self.pattern_x_step * 0.5, y + self.pattern_y_step * 0.5 + ty))
                c.Append(geom.Point(x + self.pattern_x_step * 0.5 - tx*0.5, y + self.pattern_y_step * 0.5))
                a.Append(c)
                
                c = geom.Curve()
                c.Append(geom.Point(x, y + self.pattern_y_step * 0.5))
                c.Append(geom.Point(x + tx*0.5, y + self.pattern_y_step * 0.5 + ty))
                c.Append(geom.Point(x - tx*0.5, y + self.pattern_y_step * 0.5 + ty))
                c.Append(geom.Point(x, y + self.pattern_y_step * 0.5))
                a.Append(c)
                y += self.pattern_y_step
            x += self.pattern_x_step

        if self.split_into_pieces > 1:
            wall_a = geom.Area()
            for i in range(0, self.split_into_pieces):
                x = wing_box.MinX() + (wing_box.MaxX() - wing_box.MinX()) * float(i + 1) / self.split_into_pieces
                c = geom.Curve()
                c.Append(geom.Point(x - self.split_wall_width * 0.5, wing_box.MinX() - 10.0))
                c.Append(geom.Point(x + self.split_wall_width * 0.5, wing_box.MinX() - 10.0))
                c.Append(geom.Point(x + self.split_wall_width * 0.5, wing_box.MaxX() + 10.0))
                c.Append(geom.Point(x - self.split_wall_width * 0.5, wing_box.MaxX() + 10.0))
                c.Append(geom.Point(x - self.split_wall_width * 0.5, wing_box.MinX() - 10.0))
                wall_a.Append(c)
            a.Subtract(wall_a)
            
        outline.Intersect(a)
        
        return outline
        
    def DrawPointTriangle(self, pts, i0, i1, i2):
        self.DrawTriangle(pts[i0].x, pts[i0].y, 0.0, pts[i1].x, pts[i1].y, 0.0, pts[i2].x, pts[i2].y, 0.0, False)
        
    def DrawPatternTriangles(self):
        stl = self.MakeStlSolid()
        
        outline = stl.Shadow(geom.Matrix(), True)
        outline.Offset(self.pattern_border)
        
        pattern = self.MakePatternedArea(outline, stl.GetBox())

        for curve in pattern.GetCurves():
            spans = curve.GetSpans()
            pts = []
            for span in spans:
                pts.append(span.p)
            for i in range(2, len(pts)):
                self.DrawPointTriangle(pts, 0,i,i -1)

    def OnRenderTriangles(self):
        if self.box == None:
            self.SketchesToCurves()
            self.CalculateBox()
            
        if self.render_wing:
            if self.curves[0] != None and self.curves[1] != None: # can't draw anything without a leading edge nor a trailing edge
                global section_index
                section_index = 0
                
                # use the spans of trailing edge to define the sections
                for span in self.curves[1].GetSpans():
                    self.DrawSection(span)
                    section_index += 1
                    
                self.DrawEndFace()
                
        if self.render_pattern:
            self.DrawPatternTriangles()
        
    def OnGlCommands(self, select, marked, no_color):
        if not no_color:
            cad.DrawEnableLighting()
            cad.Material(self.color).glMaterial(1.0)
            
        if self.draw_list:
            cad.DrawCallList(self.draw_list)
        else:
            self.draw_list = cad.DrawNewList()
            self.OnRenderTriangles()
                    
            cad.EndLinesOrTriangles()
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
        p = PyProperty('render_wing', 'render_wing', self, self.Recalculate)
        list_of_things_to_not_delete.append(p)  
        properties.append(p)
        p = PyProperty('render_pattern', 'render_pattern', self, self.Recalculate)
        list_of_things_to_not_delete.append(p)  
        properties.append(p)
        p = PyProperty('pattern_border', 'pattern_border', self, self.Recalculate)
        list_of_things_to_not_delete.append(p)  
        properties.append(p)
        p = PyProperty('pattern_x_step', 'pattern_x_step', self, self.Recalculate)
        list_of_things_to_not_delete.append(p)  
        properties.append(p)
        p = PyProperty('pattern_y_step', 'pattern_y_step', self, self.Recalculate)
        list_of_things_to_not_delete.append(p)  
        properties.append(p)
        p = PyProperty('pattern_wall', 'pattern_wall', self, self.Recalculate)
        list_of_things_to_not_delete.append(p) 
        properties.append(p)
        p = PyProperty('split_into_pieces', 'split_into_pieces', self, self.Recalculate)
        list_of_things_to_not_delete.append(p)         
        properties.append(p)
        p = PyProperty('split_wall_width', 'split_wall_width', self, self.Recalculate)
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
        cad.SetXmlValue('render_wing', self.render_wing)
        cad.SetXmlValue('render_pattern', self.render_pattern)
        cad.SetXmlValue('pattern_border', self.pattern_border)
        cad.SetXmlValue('pattern_x_step', self.pattern_x_step)
        cad.SetXmlValue('pattern_y_step', self.pattern_y_step)
        cad.SetXmlValue('pattern_wall', self.pattern_wall)
        cad.SetXmlValue('split_into_pieces', self.split_into_pieces)
        cad.SetXmlValue('split_wall_width', self.split_wall_width)
        
    def ReadXml(self):
        self.color = cad.Color(cad.GetXmlInt('col', self.color.ref()))
        for i in range(0, len(sketch_xml_names)):
            self.sketch_ids[i] = cad.GetXmlInt(sketch_xml_names[i], 0)
        self.mirror = cad.GetXmlBool('mirror')
        self.centre_straight = cad.GetXmlBool('centre_straight')
        self.render_wing = cad.GetXmlBool('render_wing', True)
        self.render_pattern = cad.GetXmlBool('render_pattern', False)
        self.pattern_border = cad.GetXmlFloat('pattern_border', 10.0)
        self.pattern_x_step = cad.GetXmlFloat('pattern_x_step', 20.0)
        self.pattern_y_step = cad.GetXmlFloat('pattern_y_step', 30.0)
        self.pattern_wall = cad.GetXmlFloat('pattern_wall', 2.0)
        self.split_into_pieces = cad.GetXmlInt('split_into_pieces', 6)
        self.split_wall_width = cad.GetXmlFloat('split_wall_width', 4.0)
        
        Object.ReadXml(self)
        
    def GetTools(self):
        global wing_for_tools
        wing_for_tools = self
        self.AddTool('Make Sketches', MakeSketches)
        
    def MakeSketches(self):
        global drawing_mode
        save_mode = drawing_mode
        drawing_mode = DRAWING_MODE_SKETCHES
        self.OnRenderTriangles()
        drawing_sketches = save_mode
        
    def GetTriangles(self):
        global drawing_mode
        save_mode = drawing_mode
        drawing_mode = DRAWING_MODE_TRIANGLES
        self.OnRenderTriangles()
        drawing_mode = save_mode
        
    def MakeCuboidSection(self, index, num, box, margin):
        section_width = (box.MaxX() - box.MinX())/num
        minx = box.MinX() + section_width * index
        miny = box.MinY() - margin
        minz = box.MinZ() - margin
        maxx = box.MinX() + section_width * (index + 1)
        maxy = box.MaxY() + margin
        maxz = box.MaxZ() + margin
        if index == 0:
            minx -= margin
        if index == num - 1:
            maxx += margin
            
        stl = geom.Stl()
        stl.Add(geom.Point3D(minx, miny, minz), geom.Point3D(maxx, miny, minz), geom.Point3D(maxx, miny, maxz))
        stl.Add(geom.Point3D(minx, miny, minz), geom.Point3D(maxx, miny, maxz), geom.Point3D(minx, miny, maxz))
        stl.Add(geom.Point3D(maxx, miny, minz), geom.Point3D(maxx, maxy, minz), geom.Point3D(maxx, maxy, maxz))
        stl.Add(geom.Point3D(maxx, miny, minz), geom.Point3D(maxx, maxy, maxz), geom.Point3D(maxx, miny, maxz))
        stl.Add(geom.Point3D(maxx, maxy, minz), geom.Point3D(minx, maxy, minz), geom.Point3D(minx, maxy, maxz))
        stl.Add(geom.Point3D(maxx, maxy, minz), geom.Point3D(minx, maxy, maxz), geom.Point3D(maxx, maxy, maxz))
        stl.Add(geom.Point3D(minx, maxy, minz), geom.Point3D(minx, miny, minz), geom.Point3D(minx, miny, maxz))
        stl.Add(geom.Point3D(minx, maxy, minz), geom.Point3D(minx, miny, maxz), geom.Point3D(minx, maxy, maxz))
        stl.Add(geom.Point3D(minx, miny, maxz), geom.Point3D(maxx, miny, maxz), geom.Point3D(maxx, maxy, maxz))
        stl.Add(geom.Point3D(minx, miny, maxz), geom.Point3D(maxx, maxy, maxz), geom.Point3D(minx, maxy, maxz))
        stl.Add(geom.Point3D(maxx, miny, minz), geom.Point3D(minx, miny, minz), geom.Point3D(maxx, maxy, minz))
        stl.Add(geom.Point3D(maxx, maxy, minz), geom.Point3D(minx, miny, minz), geom.Point3D(minx, maxy, minz))
        
        return stl
        
        
    def ExportFiles(self, path):
        wing = self.MakeStlSolid()
        wing.WriteStl(path)
        
        outline = wing.Shadow(geom.Matrix(), True)
        outline.Offset(self.pattern_border)
        
        pattern = self.MakePatternedArea(outline, wing.GetBox())
        pattern_stl = self.MakeExtrudedAreaSolid(pattern, wing.GetBox().MinZ() - 10, wing.GetBox().MaxZ() + 10)
        pattern_path = path[:-4] + ' pattern.stl'
        pattern_stl.WriteStl(pattern_path)
        
        outer_box = wing.GetBox()
        outer_box.InsertPoint(outer_box.MinX() - 1.0, outer_box.MinY() - 1.0, outer_box.MinZ() - 1.0)
        outer_box.InsertPoint(outer_box.MaxX() + 1.0, outer_box.MaxY() + 1.0, outer_box.MaxZ() + 1.0)
        for i in range(0, self.split_into_pieces):
            stl = self.MakeCuboidSection(i, self.split_into_pieces, wing.GetBox(), 1.0)
            indexstr = str(i)
            if len(indexstr) < 2:
                indexstr = '0' + indexstr
            stl.WriteStl(path[:-4] + ' section' + indexstr + '.stl')

    def MakeExtrudedAreaSolid(self, pattern, minz, maxz):
        stl = geom.Stl()
        for curve in pattern.GetCurves():
            if math.fabs(curve.GetArea()) > 1.0:
                spans = curve.GetSpans()
                pts = []
                for span in spans:
                    stl.Add(geom.Point3D(span.p.x, span.p.y, minz), geom.Point3D(span.v.p.x, span.v.p.y, minz), geom.Point3D(span.v.p.x, span.v.p.y, maxz))
                    stl.Add(geom.Point3D(span.p.x, span.p.y, minz), geom.Point3D(span.v.p.x, span.v.p.y, maxz), geom.Point3D(span.p.x, span.p.y, maxz))
                    pts.append(span.p)
                for i in range(2, len(pts)):
                    stl.Add(geom.Point3D(pts[i].x, pts[i].y, maxz), geom.Point3D(pts[0].x, pts[0].y, maxz), geom.Point3D(pts[i-1].x, pts[i-1].y, maxz))
                    stl.Add(geom.Point3D(pts[0].x, pts[0].y, minz), geom.Point3D(pts[i].x, pts[i].y, minz), geom.Point3D(pts[i-1].x, pts[i-1].y, minz))
        return stl

    def MakeStlSolid(self):
        global drawing_mode
        global stl_to_add_to
        save_mode = drawing_mode
        save_render_pattern = self.render_pattern
        save_render_wing = self.render_wing
        stl_to_add_to = geom.Stl()
        drawing_mode = DRAWING_MODE_STL
        self.render_pattern = False
        self.render_wing = True
        self.OnRenderTriangles()
        drawing_mode = save_mode
        self.render_wing = save_render_wing
        self.save_render_pattern = save_render_pattern
        return stl_to_add_to

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
 
    ps = GetMinXPoint(curve)
    pe = GetMaxXPoint(curve)
     
    xdist = ps.Dist(pe)
        
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