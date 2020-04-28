import bpy
from xml.etree.ElementTree import Element, SubElement, tostring as xml2str
from xml.dom import minidom


import re

import os,sys

import shutil

from . import PathExporter
from .PacArchiveNav import PacArchiveNav
from .SFPac3 import PacArchive
import tempfile


meterScale = 10
def getAllCurveData(objects):
    allcurves=[] 
    for ob in objects: 
      if ob.type == 'CURVE':       
        ob.name            
        sps=[]
        for spline in ob.data.splines :
            ks=[]
            for pt in spline.bezier_points.values() :               
              (x,y,z)=pt.co*meterScale
              ks.append([x,z,-y])
            sps.append(ks)
        cur=PathExporter.ForcesCurveIO(ob.name,sps)
        allcurves.append(cur)
    #-----prepare and validate
    curves=[]
    errors=[]
    for curve in allcurves:
        curve.exportPrepare()
        if curve.errors!=[]:
            errors.extend(curve.errors)
        else:
            curves.append(curve)
    curves.sort(key=PathExporter.ForcesCurveIO.getName)
    #TODO: Show in a message
    print(errors)    
    print("Found valid curves {} of {}:".format(len(curves),len(allcurves)))    
    return (curves,errors)

 
def write_some_data(context, filepath, use_some_setting):
    print("runing spline exporter to sonic forces ...")
    allerrors=[]
    if filepath.endswith(".pac"):      
        collections=bpy.context.scene.collection.children         
        valid_collections=[col for col in  collections  if col.name.lower().endswith(".path")]
        if valid_collections==[]:
            return ["There is not valid collections to repack to the pac file {}, the collection most be named like the path file includind the extension ex : 'w9a01_path.path'".format(filepath)]
        
        basedir=os.path.dirname(filepath)
        tmp_dirpath = tempfile.mkdtemp(prefix="extracted-"+os.path.basename(filepath),dir=basedir)
        
        #SFPac in action
        archive = PacArchive()
        archive.load(filepath)
        archive.unpack(tmp_dirpath)  

        print("===================================>>")            
        print("files extracted to"+tmp_dirpath)
        print("===================================>>")
        #get collections on the top of the scene

        for col in  valid_collections:            
            print("Saving Collection "+ col.name + " :")
            path_file=os.path.join(tmp_dirpath,col.name)                
            (fcurves,errors)=getAllCurveData(col.objects.values())
            allerrors.extend(errors)
            print(path_file)
            PathExporter.exportCurvesToFile(path_file,fcurves)                                
         
        #SFPac in action again
        archive = PacArchive()
        archive.addFolder(tmp_dirpath)
        archive.splitToDepends()
        archive.save(filepath)                        
        
        shutil.rmtree(tmp_dirpath)#be careful delete a whole dir                                                  
    else:
        if not filepath.lower().endswith(".path"):
            filepath+=".path"
        coll=bpy.context.selected_objects
        if 'CURVE' not in [c.type for c in coll]:
            coll=bpy.context.view_layer.objects
        (fcurves,allerrors)=getAllCurveData(coll)
        PathExporter.exportCurvesToFile(filepath,fcurves)
    return allerrors


# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


def ShowMessageBox(message = "", title = "Message Box", icon = 'INFO'):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)



class ExportSomeData(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "export_sonicforces.spline"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export Sonic Forces Splines Data"

    # ExportHelper mixin class uses this
    filename_ext = ""

    filter_glob: StringProperty(
        default="*.path;*_misc.pac",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    use_setting: BoolProperty(
        name="Overwrite Existing Curves",
        description="Example Tooltip",
        default=True,
    )

    type: EnumProperty(
        name="Example Enum",
        description="Choose between two items",
        items=(
            ('OPT_A', "First Option", "Description one"),
            ('OPT_B', "Second Option", "Description two"),
        ),
        default='OPT_A',
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
        errors=write_some_data(context, self.filepath, self.use_setting)
        if len(errors)>0:
            ShowMessageBox("Export ScriptFinished", "There was errors, the splines may exported parcially or may not exported at all.",'ERROR')
        else:
            ShowMessageBox("Export ScriptFinished", "The Forces Splines ws exported sucefully.")
        return {'FINISHED'}

# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):    
    global sonicico
    self.layout.operator(ExportSomeData.bl_idname, text="Sonic Forces Splines(*.path| *_misc.pac)",icon_value=sonicico)


def register(icon_id=None):
    global sonicico
    sonicico=icon_id
    bpy.utils.register_class(ExportSomeData)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportSomeData)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    
            
  
    
           
if __name__ == "__main__":
    #register()    
    # test call
    bpy.ops.export_test.some_data('INVOKE_DEFAULT')
