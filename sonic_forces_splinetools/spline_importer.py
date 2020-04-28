# -*- coding: utf-8 -*-
import bpy
import io
from mathutils import Vector,Quaternion
from bpy_extras.object_utils import object_data_add
from xml.dom import minidom
import re
import os,sys
import struct
import itertools


"""
dir=os.path.basename(__file__)
if not dir in sys.path:
    sys.path.append(dir)

print(dir)"""
from .PacArchiveNav import PacArchiveNav


RELATIVE=1

MeterScale = 10

"""
read null terminated string
"""
def readCString(f):
    return ''.join(iter(lambda: f.read(1).decode('ascii'), '\x00'))


def getPtString(f,offset):
    cur=f.tell()
    f.seek(offset + 0x40) 
    str = readCString(f)
    f.seek(cur)
    return str


# Based on the 3Dmax Sript  PathImporter.ms  by Radfordhound
def parseForcesCurveFile(f):
    f.seek(0x40)
    edian="<"
    header=readCString(f)
    if header=="PATH":
        edian=">"
    elif header=="HTAP":
        edian="<"
    else:
        raise("Invalid File, /*no PATH header found*/")
    f.seek(0x48)
    NumPaths=struct.unpack(edian+"L",f.read(4))[0]
    
    f.seek(0x4,RELATIVE) 
    paths_offset=struct.unpack(edian+"L",f.read(4))[0]
    f.seek(paths_offset + 0x40)
    
    curves=[]
    for p in range(NumPaths):
        offset= struct.unpack(edian+"L",f.read(4))[0]
        PathNameStr = getPtString(f,offset)
        f.seek(0x4,RELATIVE) 
        #print(PathNameStr)
        f.seek(0x2,RELATIVE) 
        knot_count = struct.unpack(edian+"H",f.read(2))[0]
        f.seek(0x14,RELATIVE) 
        knots_offset =struct.unpack(edian+"L",f.read(4))[0]
        f.seek(0x14,RELATIVE) 
        double_knot_count =struct.unpack(edian+"L",f.read(4))[0]
        f.seek(0x4,RELATIVE) 
        double_knots_offset =struct.unpack(edian+"L",f.read(4))[0]
        f.seek(0x3C,RELATIVE) 
        end = f.tell()
        cur_splines=[[]]    
        if double_knot_count > 0:
            cur_splines=[[],[]]
            f.seek(double_knots_offset + 0x40)					
            for v in range(double_knot_count):
                # Double spline knot data has the two splines interleaved
                # spline1knot1, spline2knot1, spline1knot2, etc			
                knot= struct.unpack(edian+"fff",f.read(4*3))		
                cur_splines[v%2].append(knot)
        else: #single knots
            f.seek(knots_offset + 0x40)    
            for v in range(knot_count):
                knot= struct.unpack(edian+"fff",f.read(4*3))			
                cur_splines[0].append(knot)    
        curves.append({'name':PathNameStr,'splines':cur_splines})
        f.seek(end)   
    return curves



def drawcurves(curves,collection_name=None,ForcesMode=False):
    collection=None
    if collection_name:        
        if collection_name in bpy.context.scene.collection.children.keys():
            collection=bpy.context.scene.collection.children[collection_name]
        else:
            collection=bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection)

    for cur in curves:
        # create curve
        dataCurve = bpy.data.curves.new(name=cur['name'], type='CURVE')  # curvedatablock
        # create object with newCurve
        Curve = object_data_add(bpy.context, dataCurve)  # place in active scene
        
        if collection:
            Curve.users_collection[0].objects.unlink(Curve)
            collection.objects.link(Curve)

        if ForcesMode:            
            Curve.location=Vector([0,0,0])
            Curve.scale=Vector([1,1,1])
            Curve.rotation_mode='QUATERNION'
            Curve.rotation_quaternion=Quaternion()
            #Curve.data.extrude=1
        else:
            (x,y,z)=cur['translate']
            Curve.location=Vector([x,-z,y])
            (x,y,z)=cur['scale']
            Curve.scale=Vector([x,z,y])
            Curve.rotation_mode='QUATERNION'
            (x,y,z,w)=cur['rotate']
            Curve.rotation_quaternion=Quaternion((w,x,-z,y))
            Curve.data.extrude=cur['width']

        Curve.select_set(True)

        Curve.data.dimensions = "3D"
        Curve.data.use_path = True
        Curve.data.fill_mode = 'FULL'
        
        if not ForcesMode:
            Curve.data.twist_mode="TANGENT"

        for ks in cur["splines"]:
            newSpline = dataCurve.splines.new(type="BEZIER")          # spline
            newSpline.bezier_points.add(len(ks)-1)
            for i in range(0, len(ks)):
                if ForcesMode:
                    (x,y,z)=ks[i]   
                    newSpline.bezier_points[i].co=Vector([x,-z,y])/MeterScale
                    #Seems that forces souport only corner nodes or still there is not enought informations
                    #Corner node type in blender is called "VECTOR"                     
                    newSpline.bezier_points[i].handle_left_type="VECTOR"
                    newSpline.bezier_points[i].handle_right_type="VECTOR"                 
                else:                    
                    (x,y,z)=ks[i]['point']    
                    newSpline.bezier_points[i].co=Vector([x,-z,y])
                    ctype=path2blend[ks[i]['type']]
                    newSpline.bezier_points[i].handle_left_type=ctype
                    newSpline.bezier_points[i].handle_right_type=ctype
                    (x,y,z)=ks[i]['invec']
                    newSpline.bezier_points[i].handle_left=Vector([x,-z,y])
                    (x,y,z)=ks[i]['outvec']
                    newSpline.bezier_points[i].handle_right=Vector([x,-z,y])
                    (x,y,z)=ks[i]['point']
                


def read_some_data(context, filepath, use_some_setting):
    print("runing another dude import spline to sonic forces...")
    if filepath.lower().endswith(".pac"):        
        archive = PacArchiveNav()
        archive.load(filepath)
        entries=archive.getAllEntriesByExtension("path")   
        curves=[]
        for e in entries:
            with open(filepath, "rb") as f:    
                #read the file from the pack to a buffer memory file
                o = io.BytesIO()
                f.seek(e.offset)
                o.write(f.read(e.size))
                o.seek(0)
                curves=parseForcesCurveFile(o)
                drawcurves(curves,collection_name=e.name+"."+e.extension,ForcesMode=True)     
    else:
        with open(filepath, "rb") as f:    
            curves=parseForcesCurveFile(f)
            drawcurves(curves,ForcesMode=True)        
    return {'FINISHED'}


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


def ShowMessageBox(message = "", title = "Message Box", icon = 'INFO'):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

 

class ImportSomeData(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "import_sonicforces.spline"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import  Sonic Forces Splines Data(*.path;*_misc.pac)"

    # ImportHelper mixin class uses this
    filename_ext = "*.path;*_misc.pac"

    filter_glob: StringProperty(
        default="*.path;*_misc.pac",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
        
    filelist: EnumProperty(
        name="Example Enum",
        description="Choose between two items",
        items=(
            ('OPT_A', "First Option", "Description one"),
            ('OPT_B', "Second Option", "Description two"),
        ),
        default='OPT_A',
    )
    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    use_setting: BoolProperty(
        name="Overwrite Existing Curves",
        description="Example Tooltip",
        default=True,
    )
 
    def draw(self, context):        
        layout = self.layout  
        if self.filepath.lower().endswith(".pac"):            
            archive = PacArchiveNav()
            archive.load(self.filepath)
            entries=archive.getAllEntriesByExtension("path") 
            layout.label(text="Path files in the Archive:")
            for e in entries:
                layout.label(text="   "+e.name+"."+e.extension)

    def execute(self, context):        
        read_some_data(context, self.filepath, self.use_setting)
        ShowMessageBox("Spline import finished", "The spline import finished, show the console in case of errors")
        return {'FINISHED'}


# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    global sonicico
    self.layout.operator(ImportSomeData.bl_idname, text="Sonic Forces Splines(*.path| *_misc.pac)",icon_value=sonicico)


def register(icon_id=None):
    global sonicico
    sonicico=icon_id
    bpy.utils.register_class(ImportSomeData)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportSomeData)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
    # test call
    bpy.ops.import_test.some_data('INVOKE_DEFAULT')

