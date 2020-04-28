# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>

"""
Author: Aaron Foster Wallace 


Thanks to:
    -   Skyth's SFPac archive parser
    
    -   Documented on the 3dmax scripts> 
            PathImporter.ms and PathExporter.ms  by Radfordhound
            
"""


bl_info = {
    "name": "Sonic Forces Spline Tools",
    "author": "Aaron Foster Wallace",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Import-Export > Forces Gen Splines",
    "description": "Import-Export Sonic Generations Spline files\n Also inside \"_misc.pac\" archives ",
    "warning": "",
    "wiki_url": "https://github.com/aaron-foster-wallace/sonic_forces_splinetools",
    "category": "Import-Export",
}


#General todos
#TODO: 
#TODO: Export Errors are not displayed just printed in the console
#TODO: Export You most have all curves with all transformations and reset to word origin
#TODO: Export only work on beizers, and only take in acount the points, so use vector handles  to get what you see 
#      (in Edit >[A] to Select all>[V] to change mode to vector)






"""
Import-Export Sonic Generations Spline files


Issues:

Import:

"""


if "bpy" in locals():
    import importlib
    if "spline_exporter" in locals():
        importlib.reload(spline_exporter)
    if "spline_importer" in locals():
        importlib.reload(spline_importer)
    if "register_icons" in locals():
        importlib.reload(register_icons)      
else:
    from . import spline_exporter,spline_importer,register_icons

def register():
    register_icons.register()
    col=register_icons.icon_collections["main"]
    icon=col["sonic"]
    
    spline_importer.register(icon.icon_id)    
    spline_exporter.register(icon.icon_id)


def unregister():
    spline_importer.unregister()
    spline_exporter.unregister()


if __name__ == "__main__":
    register()
