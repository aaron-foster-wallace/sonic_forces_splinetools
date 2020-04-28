# -*- coding: utf-8 -*-

# Python Forces Path Exporter by Aaron Foster Wallace
# Translated from 3Dmax Sript  PathExporter.ms  by Radfordhound
# at same time Built on LWPathImporter by arukibree
# end of the chain


from collections import namedtuple
import struct
import enum
import bpy
import io
from mathutils import Vector,Quaternion
  

GLOBAL_UP = [0,1,0]
yzflip = True
meterScale = 10
VERSION = 1 # 0: wii U / 1: PC (only pc is tested)
BE=">"
LE="<"

LONGPAD=b'\x00'*4
LONGLONGPAD=b'\x00'*8
RELATIVE=1



def  midPoint(v1,v2):
   x1,y1,z1=v1
   x2,y2,z2=v2
   xm=x1+ ((x2-x1)*0.5)
   ym=y1+ ((y2-y1)*0.5)
   zm=z1+ ((z2-z1)*0.5)	
   return (xm,ym,zm)

"""
TODO:
I use this funtions because i test outside 
blender i plan to use the Vector class of blender
"""
def cross(a, b):
    return [a[1]*b[2] - a[2]*b[1],
         a[2]*b[0] - a[0]*b[2],
         a[0]*b[1] - a[1]*b[0]]

def norm(a):
    return (a[0]**2+a[1]**2+a[2]**2)**0.5

def normalize(a):
    N=norm(a)
    return [a[0]/N,a[1]/N,a[2]/N]

def  directionTo(v1,v2):
    return normalize([
            v2[0] - v1[0],
            v2[1] - v1[1],
            v2[2] - v1[2]
            ])

def  distance(v1,v2):
    return norm([
            v2[0] - v1[0],
            v2[1] - v1[1],
            v2[2] - v1[2]
            ])

########################################
#file utils
#Fill a file to a byte size that is multiplier of num

def writePad(f,num):
    while (f.tell()% num ) != 0:
        f.write(b'\x00')
        
def  writePoint3(f,edian,P3):
    f.write(struct.pack(edian+"fff",*P3))



StringEntry=namedtuple('StringEntry' , 'st addresses')


def addString( f,stringEntries,st):	
    #The string Exists
    unique = True
    for s in stringEntries:
        if s.st == st:
            s.addresses.append(f.tell())			
            unique=False
            break
    if unique:
        #Is a new String
        entry = StringEntry(st,[f.tell()])
        stringEntries.append(entry)
    
    f.write(LONGLONGPAD)


def  writeTable(f,edian,stringEntries) :
    for s in stringEntries:
        offset = f.tell()
        for a in s.addresses:
            f.seek(a)
            f.write(struct.pack(edian+"L",offset - 0x40))
        f.seek(offset)		
        f.write(s.st.encode())
        f.write(b'\x00')
    


########################################
class ForcesCurveType(enum.Enum):
   Object = 0
   SideView = 1
   GrindRail = 2
   #print (ForcesCurveType(2)) acces by value
   #print (ForcesCurveType['GrindRail']) acces by name

   
class ForcesCurveIO:

    def __init__(self,name,splines):
        self.name = name
        self.splines = splines
        self.ptype=0#object the default 
        self.BBMin=[999999999, 999999999, 999999999]
        self.BBMax=[-999999999, -999999999, -999999999]
        self.mid_spline=[]
        self.upvecs=[]
        self.forwardvecs=[]
        self.errors=[]
        self.pathLength = 0.0
        self.distances=[]
        self.uuid=0
    
    def getName(self):#for sorting ls.sort(key=ForcesCurveIO.getName)
        return self.name
        
    
    def validate(self):    
        slen=len(self.splines)
        self.errors=[]
        if slen<1:
            self.errors.append("The curve object {} cannot be exported because it has no splines".format(self.name))
        if slen>2:
            self.errors.append("The curve object{} cannot be exported because has more than two splines, have {} splines".format(self.name,slen))
           
        if len(self.splines[0])<2:
            self.errors.append("The curve object{} cannot be exported because it  has 1st spline with less than 2 knots  or is not a bezier curve ".format(self.name))
        
        if slen==2:
            if len(self.splines[1])<2:
                self.errors.append("The curve object{} cannot be exported because it has a 2nd spline with less than 2 knots or is not a bezier curve".format(self.name))
            if len(self.splines[0])!=len(self.splines[1]):
                self.errors.append("The curve object{} cannot be exported because it has  2 splines of diferent  knots count".format(self.name))
        return len(self.errors)==0
    
       

    def exportPrepare(self):
        if not self.validate():        
            return    
        #Default _type = ForcesCurveType.Object.value	
        if (self.name[-3:] in ["_SV","_SL"]):
           self.ptype = ForcesCurveType.SideView.value
        elif self.name[-3:] == "_GR":
           self.ptype = ForcesCurveType.GrindRail.value
    
        #BoundingBOx   
        for s in self.splines:
            for k in s:
                for i in range(3):
                    self.BBMin[i]=min(k[i],self.BBMin[i])
                    self.BBMax[i]=max(k[i],self.BBMax[i])
        
        #Midpoints
        if len(self.splines)==2:    
            self.mid_spline=[midPoint(*v)  for v in zip(self.splines[0],self.splines[1])]
        
        
        #distances
        self.pathLength = 0
        prevk=self.splines[0][0]#first node
        self.distances=[0.0]
        for k in self.splines[0][1:]:
            self.pathLength += distance(k,prevk)
            prevk=k
            self.distances.append(self.pathLength)    
 

        #TODO: In case of doble splines Check if parralel curves order maters , maybe up vector directions matters
        #When have 2 splines the right vector is more consistent, points to the 2nd  self        
        splinezip=list(zip(*self.splines))# tuples of one or two parrallel points
        last = GLOBAL_UP
        for i in range(len(splinezip)-1):            
            k=splinezip[i][0]
            nextk=splinezip[i+1][0]
            forward = directionTo(k,nextk)
            if len(self.splines)==2:
                kB=splinezip[i][1] # 2nd parrallel spline point
                right = directionTo(k,kB)
            else:
               right = normalize(cross(forward,last)) 
            up = normalize(cross(right,forward))
            last=up
            self.upvecs.append(up)
            self.forwardvecs.append(forward)
            
        #Last points
        self.upvecs.append(self.upvecs[-1])        
        self.forwardvecs.append(self.forwardvecs[-1])
        
        #uuid
        #self.uuid=
        self.uuid=0
        pts=self.name.split("_")
        pts.reverse()
        for u in pts:
            if u.isdigit():
                self.uuid=int(u)
                break
    """
    @f output file
    @edian '<'  or '>' for use it with struct.pack
    @path number for the header offset in file
    """
    def writeToFile(self,f,edian,pathnumber,stringEntries,offset_array):
        klen=len(self.splines[0])        
        # bool array
        #unknown,but setting everything to 0 has no noticeable effect
        boolsOffset = f.tell()
        f.write(b'\x00'*klen)
        
        writePad(f,4)	#fill to be 4 multiplier     
        # dist array
        distOffset = f.tell()        
        #writeFloatarray
        f.write(struct.pack(edian+"f"*klen,*self.distances))
            
        # knot array
        knotsOffset = f.tell()
        
        knots=self.splines[0]
        if len(self.splines)==2:
            knots=self.mid_spline
                    
        for k in knots:
            writePoint3(f,edian,k)
            
        
        # Up vector array
        upVecsOffset = f.tell()
        
      
        for u  in self.upvecs:
                writePoint3(f,edian,u)		
        
        
        # forward vector array
        forwardVecsOffset = f.tell()        
        for fv in self.forwardvecs:        	
                writePoint3(f,edian,fv)

        # double spline knot array
        doubleSplineOffset = f.tell()
        
        if len(self.splines)==2:
            for k1,k2 in zip(*self.splines):
                writePoint3(f,edian,k1)
                writePoint3(f,edian,k2)            
        else:
            doubleSplineOffset = 0
        
        # metadata
        writePad(f,8)     
        #TODO is shiffted by 8   
        
        metaOffset = f.tell()
        metaCount = 0       
        
        # write metadata
        # "type" field present for all types
        offset_array.append(f.tell())        
        addString(f,stringEntries,"type")
        f.write(LONGLONGPAD)
        f.write(struct.pack(edian+"Q",self.ptype)) 
        metaCount += 1
        
        # "uid" field present for type Object or SV path UUIDs
        if self.ptype in [0,1]:
            offset_array.append(f.tell())    
            addString(f,stringEntries,"uid")
            f.write(LONGLONGPAD)
            f.write(struct.pack(edian+"Q",self.uuid))			
            metaCount += 1
       
         
        # KD tree
        # the exact structure of this part is unknown, but luckily we can cheat our way through this part.
        # there are no noticeable ingame issues from doing it this way; it's likely only a very small performance hit
        KDTreeOffset = f.tell()
        

        numLineSegments=klen*len(self.splines)-len(self.splines)
        
        
        
        f.write(struct.pack(edian+"L",0))
        f.write(struct.pack(edian+"L",2))
        offset_array.append(f.tell())
        f.write(struct.pack(edian+"Q",KDTreeOffset + 0x30 - 0x40))
        
        f.write(struct.pack(edian+"Q",1))
        offset_array.append(f.tell())
        f.write(struct.pack(edian+"Q",KDTreeOffset + 0x40 - 0x40))
        
        f.write(struct.pack(edian+"Q",numLineSegments))
        offset_array.append(f.tell())
        f.write(struct.pack(edian+"Q",KDTreeOffset + 0x48 - 0x40))
        
        # the first data section is the unknown bit
        f.write(struct.pack(edian+"L",0))
        f.write(struct.pack(edian+"L",0))
        f.write(struct.pack(edian+"L",3))
        f.write(struct.pack(edian+"L",0))
        
        # the second bit assigns line segments to... something.
        # [count] int pairs - first is count, second is starting index.
        # eg "add 6 segments staring from segment 7"
        f.write(struct.pack(edian+"Q",numLineSegments))
        
        # the third bit seems to be just line segment indices/IDs
        for i in range(numLineSegments):
            f.write(struct.pack(edian+"L",i))
        
        writePad(f,8)
        
        # done with path data - now backtrack and write path header
        pathDataEnd = f.tell()
        
        headerOffset = 0x58 + 0x80 * pathnumber
        f.seek(headerOffset)
        
        # path header		
        f.write(LONGLONGPAD) # this is the name offset; will be filled in by the writeTable() call later
        f.write(b'\x01') # unknown value, always 0x1
        f.write(b'\x00') # unknown value, always 0x0      
        f.write(struct.pack(edian+"H",klen))
        f.write(struct.pack(edian+"f",self.pathLength))
        f.write(struct.pack(edian+"Q",boolsOffset - 0x40))
        f.write(struct.pack(edian+"Q",distOffset - 0x40))
        f.write(struct.pack(edian+"Q",knotsOffset - 0x40))
        f.write(struct.pack(edian+"Q",upVecsOffset - 0x40))
        f.write(struct.pack(edian+"Q",forwardVecsOffset - 0x40))
        f.write(struct.pack(edian+"Q",klen*2 if len(self.splines)==2 else 0))
        
        if doubleSplineOffset != 0:
            f.write(struct.pack(edian+"Q",(doubleSplineOffset - 0x40)))
        else:
            f.write(LONGLONGPAD)
        
        writePoint3(f,edian,self.BBMin)
        writePoint3(f,edian,self.BBMax)
        f.write(struct.pack(edian+"Q",metaCount))
        f.write(struct.pack(edian+"Q",(metaOffset - 0x40)))
        f.write(LONGLONGPAD) # unknown value, always 0
        f.write(struct.pack(edian+"Q",(KDTreeOffset - 0x40)))	
        f.seek(pathDataEnd)
    
 
def exportCurvesToFile(path_file,curves):    
    f = open(path_file,"wb")    
    edian=""
    if (VERSION == 0): 
        edian=BE
    elif (VERSION == 1):
        edian=LE
    offset_array = []
    stringEntries = []
    pathCount = len(curves)
    # start writing    
    # BINA header	
    f.write(b'BINA') # BINA
    f.write(b'210L') # 210L
    f.write(LONGPAD) # file size (fill in later) Long
    f.write(struct.pack(edian+"L",0x1))
    f.write(b'DATA') # DATA
    f.write(LONGPAD) # DATA size (fill in later) Long
    f.write(LONGPAD) # string table offset (fill in later)Long
    f.write(LONGPAD) # string table length (fill in later)Long
    f.write(LONGPAD) # final table length (fill in later)Long
    
    f.write(struct.pack(edian+"L",0x18))
    f.write(LONGLONGPAD)
    f.write(LONGLONGPAD)
    f.write(LONGLONGPAD)
    
    # header
    f.write(b'HTAP' if edian==LE else b'PATH') # "PATH" magic
    f.write(struct.pack(edian+"H",0x200))
    f.write(struct.pack(edian+"H",0))
    f.write(struct.pack(edian+"Q",pathCount))
    
    offset_array.append(f.tell())
    
    f.write(struct.pack(edian+"Q",0x18))
    # path headers - first pass, enter junk. We'll write this later. the only thing we'll do now is add strings/offsets.
    
    for cur in curves:
        start = f.tell()
        offset_array.append(f.tell())
        addString(f,stringEntries,cur.name)
        
        offset_array.append(start + 0x10)
        offset_array.append(start + 0x18)
        offset_array.append(start + 0x20)
        offset_array.append(start + 0x28)
        offset_array.append(start + 0x30)
        if len(cur.splines)==2:
            offset_array.append(start + 0x40)
        offset_array.append(start + 0x68)
        offset_array.append(start + 0x78)
    
        # write temp junk (space for 30 Longs)
        f.write(LONGPAD*30) 
    
    pathnumber=0
    for cur in curves:
        cur.writeToFile(f,edian,pathnumber,stringEntries,offset_array)
        pathnumber+=1
    
    # write string and offset table
    stringTablePos = f.tell()
    writeTable(f,edian,stringEntries)
    writePad(f,4)
    footerStartPos = f.tell()
    lastOffsetPos = 0x40
    
    #Seems that the following bitwise operations 
    #are for write a number that is in an unknow format
    #warning: only works on little edian i thoug
    for offset  in offset_array:
        d = (offset - lastOffsetPos) >> 2
        if d<=0x3F:		
            n=0x40 | d            
            print(n,d)
            f.write(struct.pack("B",n))
        elif d <= 0x3FFF:		
            n=(0x80 << 8) | d 
            f.write(struct.pack(BE+"H",n))		
        else:
            n=(0xC0 << 24) | d
            f.write(struct.pack(BE+"L",n))
        lastOffsetPos = offset
    
    # fix padding
    writePad(f,4)
    fileSize = f.tell()
    
    # fill-In header values
    f.seek(0x8)
    f.write(struct.pack(edian+"L",fileSize)) # file size
    f.seek(0x8,RELATIVE)
    f.write(struct.pack(edian+"L",(fileSize - 0x10))) # DATA size
    
    f.write(struct.pack(edian+"L",(stringTablePos - 0x40))) # string table offset
    f.write(struct.pack(edian+"L",(footerStartPos - stringTablePos))) # string table size
    f.write(struct.pack(edian+"L",(fileSize - footerStartPos))) # offset table size
    
    # finished
    f.close()

