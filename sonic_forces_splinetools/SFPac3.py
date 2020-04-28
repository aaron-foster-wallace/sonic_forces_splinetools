#Skyth's SFPac archive parser 
import struct
import os
import sys
import uuid
import time



from itertools import groupby

from builtins import input as raw_input

if sys.version_info.major > 2: xrange = range

class BINAStream(object):
    def __init__(self, f):
        self.f = f
        
        # Write
        self.fillOffsets = {}
        self.offsets = []
        self.integers = []
        self.strings = []
        
    def read(self):
        return self.f.read()
        
    def read(self, size):
        return self.f.read(size)
        
    def write(self, data):
        self.f.write(data)

    def readFormat(self, format):
        structSize = struct.calcsize(format)
        return struct.unpack(format, self.f.read(structSize))
    
    def writeFormat(self, format, *args):
        self.f.write(struct.pack(format, *args))
    
    def readByte(self):
        return self.readFormat("B")[0]
        
    def writeByte(self, value):
        self.writeFormat("B", value)
        
    def readUShort(self):
        return self.readFormat("<H")[0]
        
    def writeUShort(self, value):
        self.writeFormat("<H", value)
    
    def readUInt(self):
        return self.readFormat("<I")[0]
        
    def writeUInt(self, value):
        self.writeFormat("<I", value)
        
    def readInt(self):
        return self.readFormat("<i")[0]
        
    def writeInt(self, value):
        self.writeFormat("<i", value)

    def readULong(self):
        return self.readFormat("<Q")[0]
        
    def writeULong(self, value):
        self.writeFormat("<Q", value)
        
    def readCString(self):
        character = self.read(1)
        result = b""
        
        while character != b'\0':
            result += character
            character = self.read(1)
            
        return result.decode()
        
    def writeCString(self, value):
        self.f.write(value.encode() + b'\0')
        
    def writeNulls(self, amount):
        self.f.write(b'\0' * amount)
        
    def pad(self, alignment):
        factor = alignment - self.f.tell() % alignment
        
        if factor != alignment:
            self.f.write(b"\0" * factor)
            
    def addOffset(self, value = 0):
        offset = self.f.tell()
        self.offsets.append(offset)
        self.writeULong(value)
        return offset
        
    def addFillOffset(self, key):
        self.fillOffsets[key] = self.addOffset()
        
    def addString(self, value):
        if value != "":
            matchFound = False
            for string in self.strings:
                if string[0] == value:
                    string[1].append(self.addOffset())
                    return
            self.strings.append((value, [self.addOffset()]))
        else:
            self.f.write(b"\0" * 8)
            
    def addIntegers(self, value, sorter = 0):
        if len(value) > 0:
            self.integers.append((value, self.addOffset(), sorter))
        else:
            self.f.write(b"\0" * 8)
            
    def writeFillOffset(self, key):
        offset = self.f.tell()
        self.f.seek(self.fillOffsets[key])
        self.writeULong(offset)
        self.f.seek(offset)
        self.fillOffsets.pop(key)
            
    def writeOffsetTable(self):
        startOffset = self.f.tell()
    
        self.offsets = list(set(self.offsets))
        self.offsets.sort()
        
        currentOffset = 0
        for offset in self.offsets:
            difference = offset - currentOffset
            
            if difference > 0xFFFC:
                self.writeFormat(">I", 0xC0000000 | (difference >> 2))
            elif difference > 0xFC:
                self.writeFormat(">H", 0x8000 | (difference >> 2))
            else:
                self.writeFormat(">B", 0x40 | (difference >> 2))
            
            currentOffset = offset
        
        self.pad(8)
        return self.f.tell() - startOffset
        
    def writeIntegerTable(self):
        startOffset = self.f.tell()
        
        self.integers.sort(key = lambda x: x[2])
        for integers in self.integers:
            integersOffset = self.f.tell()
            
            for integer in integers[0]:
                self.writeInt(integer)
                
            self.pad(8)
            
            endOffset = self.f.tell()
            self.f.seek(integers[1])
            self.writeULong(integersOffset)
            self.f.seek(endOffset)
            
        return self.f.tell() - startOffset
        
    def writeStringTable(self):
        startOffset = self.f.tell()
        
        self.strings.sort(key = lambda x: x[1][0])
        
        for string in self.strings:
            stringOffset = self.f.tell()
            self.writeCString(string[0])
            endOffset = self.f.tell()
            
            for offset in string[1]:
                self.f.seek(offset)
                self.writeULong(stringOffset)
                
            self.f.seek(endOffset)
            
        self.pad(8)
        return self.f.tell() - startOffset

    def seek(self, offset, mode = 0):
        self.f.seek(offset, mode)
        
    def move(self, amount = 1):
        self.f.seek(amount, 1)
        
    def tell(self):
        return self.f.tell()
        
class PacNodeTree(object):
    def __init__(self):
        self.rootNode = PacNode()
        
    def read(self, s, entryChecksum):
        nodeCount = s.readUInt()
        dataNodeCount = s.readUInt()
        rootNodeOffset = s.readULong()
        dataNodeIndicesOffset = s.readULong()
        
        s.seek(rootNodeOffset)
        self.rootNode.read(s, entryChecksum, rootNodeOffset)
        
    def write(self, s):
        indexData = [0, 0]
        dataNodeIndices = []
        self.rootNode._sort()
        self.rootNode._makeIndices(indexData, dataNodeIndices)
        
        s.writeUInt(indexData[0])
        s.writeUInt(indexData[1])
        
        s.addOffset(s.tell() + 16)
        s.addIntegers(dataNodeIndices)
        
        self.rootNode.write(s)
        
class PacNode(object):
    def __init__(self, name = "", data = None, parent = None):
        self.name = name
        self.data = data
        self.parent = parent
        self.nodes = []
        
        self._uuid = uuid.uuid1()
        self._index = -1
        self._dataIndex = -1
        
    @property
    def fullPath(self):
        if self.parent == None:
            return self.name
        else:
            return str(self.parent.fullPath) + str(self.name)
        
    @property
    def fullPathSize(self):
        if self.parent == None:
            return len(self.name)
        else:
            return self.parent.fullPathSize + len(self.name)
        
    def getDataNodes(self):
        for node in self.nodes:
            if node.data != None:
                yield node
            for dataNode in node.getDataNodes():
                yield dataNode
                
    def makeChildNode(self, name = "", data = None):
        node = PacNode(name, None, self)
        self.nodes.append(node)
        
        if data != None:
            dataNode = PacNode("", data, node)
            node.nodes.append(dataNode)
            
            return dataNode
        else:
            return node
                
    def packToNodes(self, dataList):
        dataListLength = len(dataList)
          
        if dataListLength == 0:
            return
            
        if dataListLength == 1:
            self.makeChildNode(dataList[0][0], dataList[0][1])
            return
        
        canPack = False
        
        for data in dataList:
            if data[0] == b"":
                raise ValueError("Empty string found during node packing!")
           
            for dataToCompare in dataList:
                if data != dataToCompare and data[0][0] == dataToCompare[0][0]:
                    canPack = True
                    break
                    
            if canPack:
                break
                
        if canPack:
            dataList.sort(key = lambda x: x[0])
            
            nameToCompare = dataList[0][0]
            minLength = len(nameToCompare)
            
            matches = []
            noMatches = []
            
            for data in dataList:
                name = data[0]
                compareLength = min(minLength, len(name))
                
                matchLength = 0
                for i in xrange(compareLength):
                    if name[i] != nameToCompare[i]:
                        break
                    else:
                        matchLength += 1
                        
                if matchLength >= 1:
                    matches.append(data)
                    minLength = min(minLength, matchLength)
                else:
                    noMatches.append(data)
                    
            if len(matches) >= 1:
                parentNode = None
                if minLength == len(nameToCompare):
                    parentNode = self.makeChildNode(dataList[0][0], dataList[0][1]).parent
                    matches = matches[1:]          
                else:
                    parentNode = self.makeChildNode(nameToCompare[:minLength])
                    
                parentNode.packToNodes([(x[0][minLength:], x[1]) for x in matches])
                
            if len(noMatches) >= 1:
                self.packToNodes(noMatches)
        else:
            for data in dataList:
                self.makeChildNode(data[0], data[1])
        
    def read(self, s, entryChecksum, rootNodeOffset):
        nameOffset = s.readULong()
        dataOffset = s.readULong()
        childIndicesOffset = s.readULong()
        parentIndex = s.readInt()
        index = s.readInt()
        dataIndex = s.readInt()
        childCount = s.readUShort()
        hasData = s.readByte()
        fullPathSize = s.readByte()
        nodeEndOffset = s.tell()
        
        if nameOffset > 0:
            s.seek(nameOffset)
            self.name = s.readCString()

        if hasData:
            s.seek(dataOffset)
            if s.readUInt() == entryChecksum:
                dataSize = s.readUInt()
                padding1 = s.readULong()
                dataOffset = s.readULong()
                padding2 = s.readULong()
                extensionOffset = s.readULong()
                dataType = s.readUInt()
                
                s.seek(extensionOffset)
                extension = s.readCString()
                
                entry = PacEntry()
                entry.name = self.fullPath
                entry.extension = extension
                entry.offset = dataOffset
                entry.size = dataSize
                entry.isProxy = dataType == 1
                
                self.data = entry
            else:
                s.seek(dataOffset)
                
                nodeTree = PacNodeTree()
                nodeTree.read(s, entryChecksum)
                
                self.data = nodeTree
        
        if childIndicesOffset > 0:
            s.seek(childIndicesOffset)
            
            childIndices = []
            for i in xrange(childCount):
                childIndices.append(s.readInt())
        
            for index in childIndices:
                s.seek(rootNodeOffset + index * 40)
            
                node = PacNode()
                node.parent = self
                node.read(s, entryChecksum, rootNodeOffset)
                self.nodes.append(node)
            
    def write(self, s):
        s.addString(self.name)
        if self.data != None:
            s.addFillOffset(self._uuid)
        else:
            s.writeNulls(8)
        s.addIntegers([x._index for x in self.nodes], 1)
        if self.parent != None:
            s.writeInt(self.parent._index)
        else:
            s.writeInt(-1)
        s.writeInt(self._index)
        s.writeInt(self._dataIndex)
        s.writeUShort(len(self.nodes))
        s.writeByte(self.data != None)
        s.writeByte(self.fullPathSize - len(self.name))
        
        for node in self.nodes:
            node.write(s)
        
    def _sort(self):
        self.nodes.sort(key = lambda x: x.name.lower())
        
        for node in self.nodes:
            node._sort()
    
    def _makeIndices(self, indexData, dataNodeIndices):
        self._index = indexData[0]
        indexData[0] += 1
        
        if self.data != None:
            dataNodeIndices.append(self._index)
            self._dataIndex = indexData[1]
            indexData[1] += 1
        
        for node in self.nodes:
            node._makeIndices(indexData, dataNodeIndices)
        
PacResourceTypes = {
	"asm":"ResAnimator",
	"anm.hkx":"ResAnimSkeleton",
	"uv-anim":"ResAnimTexSrt",
	"material":"ResMirageMaterial",
	"model":"ResModel",
	"rfl":"ResReflection",
	"skl.hkx":"ResSkeleton",
	"dds":"ResTexture",
	"cemt":"ResCyanEffect",
	"cam-anim":"ResAnimCameraContainer",
	"effdb":"ResParticleLocation",
	"mat-anim":"ResAnimMaterial",
	"phy.hkx":"ResHavokMesh",
	"vis-anim":"ResAnimVis",
	"scfnt":"ResScalableFontSet",
	"pt-anim":"ResAnimTexPat",
	"scene":"ResScene",
	"pso":"ResMiragePixelShader",
	"vso":"ResMirageVertexShader",
	"shader-list":"ResShaderList",
	"vib":"ResVibration",
	"bfnt":"ResBitmapFont",
	"codetbl":"ResCodeTable",
	"cnvrs-text":"ResText",
	"cnvrs-meta":"ResTextMeta",
	"cnvrs-proj":"ResTextProject",
	"shlf":"ResSHLightField",
	"swif":"ResSurfRideProject",
	"gedit":"ResObjectWorld",
	"fxcol.bin":"ResFxColFile",
	"path":"ResSplinePath",
	"lit-anim":"ResAnimLightContainer",
	"gism":"ResGismoConfig",
	"light":"ResMirageLight",
	"probe":"ResProbe",
	"svcol.bin":"ResSvCol",
	"terrain-instanceinfo":"ResMirageTerrainInstanceInfo",
	"terrain-model":"ResMirageTerrainModel",
	"model-instanceinfo":"ResModelInstanceInfo",
	"grass.bin":"ResTerrainGrassInfo"
	}
	
PacRootExclusiveExtensions = [
"asm",
"anm.hkx",
"cemt",
"phy.hkx",
"skl.hkx",
"rfl",
"bfnt",
"effdb",
"vib",
"scene",
"shlf",
"scfnt",
"codetbl",
"cnvrs-text",
"swif",
"fxcol.bin",
"path",
"gism",
"light",
"probe",
"svcol.bin",
"terrain-instanceinfo",
"model-instanceinfo",
"grass.bin",
"shader-list",
"gedit",
"cnvrs-meta",
"cnvrs-proj"]
        
class PacEntry(object):
    def __init__(self):
        self.name = ""
        self.extension = ""
        self.offset = 0
        self.size = 0
        
        self.sourceFileName = ""
        self.isProxy = False
        
    @property
    def isRootExclusive(self):
        return self.extension in PacRootExclusiveExtensions
        
    def makeProxy(self):
        self.isProxy = True
    
        entry = PacEntry()
        entry.name = self.name
        entry.extension = self.extension
        entry.size = self.size
        entry.sourceFileName = self.sourceFileName
        return entry
global lastpk
class PacArchive(object):
    def __init__(self):
        self.entries = []
        
        # Only for Root PAC.
        self.depends = []
        self.filePath = ""
        
    def _loadSingle(self, path):
        self.filePath = path
        lastpk=path
        print("opening:"+path)
        with open(path, "rb") as f:
            s = BINAStream(f)            
            return self.read(s)
        
    def load(self, path):
        if not ".pac" in path.lower():
            raise ValueError("Given path is not a .PAC file: {}".format(path))

        dependPacCount = self._loadSingle(path)
        
        for i in xrange(dependPacCount):
            dependPacPath = path + "." + str(i).zfill(3)
            if not os.path.exists(dependPacPath):
                print("PAC Depend ({}) not found!".format(os.path.basename(dependPacPath)))
            else:
                dependPacArchive = PacArchive()
                dependPacArchive._loadSingle(dependPacPath)
                self.depends.append(dependPacArchive)
                
    def _saveSingle(self, output, entryChecksum, baseName = ""):
        with open(output, "wb") as f:
            s = BINAStream(f)
            self.write(s, entryChecksum, baseName)

    def save(self, output):
        entryChecksum = int(time.time())
        
        self._saveSingle(output, entryChecksum, os.path.basename(output))
        
        for i in xrange(len(self.depends)):
            self.depends[i]._saveSingle(output + "." + str(i).zfill(3), entryChecksum)

    def unpack(self, output = ""):
        if output == "":
            output = os.path.splitext(self.filePath)[0]
            
        if not os.path.exists(output):
            os.mkdir(output)
            
        with open(self.filePath, "rb") as f:
            for entry in self.entries:
                if not entry.isProxy:
                    print(entry.name + "." + entry.extension)
                    with open(os.path.join(output, entry.name + "." + entry.extension), "wb") as o:
                        f.seek(entry.offset)
                        o.write(f.read(entry.size))

        for depend in self.depends:
            depend.unpack(output)
            
    def addFolder(self, inputDir):
        for path, subDirs, names in os.walk(inputDir):
            for name in names:
                if os.path.isfile(os.path.join(path, name)):
                    index = name.find(".")
                    if index >= 1:
                        extension = name[index+1:].lower()
                        
                        if extension in PacResourceTypes:
                            entry = PacEntry()
                            entry.name = name[:index]
                            entry.extension = extension
                            entry.sourceFileName = os.path.join(path, name)
                            entry.size = os.path.getsize(entry.sourceFileName)
                            self.entries.append(entry)
                        else:
                            print("Extension '{}' not recognized!".format(extension))
                            
        self._sort()

    def _sort(self):
        entries = self.entries[:]
        entries.sort(key = lambda x: PacResourceTypes[x.extension])

        self.entries = []
        for (extension, entries) in groupby(entries, lambda x: x.extension):
            entriesList = list(entries)
            entriesList.sort(key = lambda x: x.name)
            self.entries += entriesList
            
    def splitToDepends(self):
        depend = PacArchive()
        dependSize = 0
        
        for entry in self.entries:
            if not entry.isRootExclusive:
                if dependSize > 0x1E00000 - entry.size:
                    self.depends.append(depend)
                    depend = PacArchive()
                    dependSize = 0
                depend.entries.append(entry.makeProxy())
                dependSize += entry.size
        
        if dependSize > 0:
            self.depends.append(depend)

    def read(self, s):             
        if s.read(8) != b'PACx301L':
            raise ValueError("Unknown file format.")
        
        entryChecksum = s.readUInt()
        fileSize = s.readUInt()
        nodeTreeSectionSize = s.readUInt()
        pacDependsSectionSize = s.readUInt()
        entrySectionSize = s.readUInt()
        stringTableSize = s.readUInt()
        dataSectionSize = s.readUInt()
        offsetTableSize = s.readUInt()
        pacType = s.readUShort()
        constant = s.readUShort()
        dependPacCount = s.readUInt()

        typeNodeTree = PacNodeTree()
        typeNodeTree.read(s, entryChecksum)

        for fileNodeTree in typeNodeTree.rootNode.getDataNodes():
            for entryNode in fileNodeTree.data.rootNode.getDataNodes():
                self.entries.append(entryNode.data)
        
        return dependPacCount
        
    def write(self, s, entryChecksum, baseName = ""):
        # Prepare Header
        s.writeNulls(0x30)
        
        # Type Node Tree
        types = []
        
        self.entries.sort(key = lambda x: x.extension)
        for (extension, entries) in groupby(self.entries, lambda x: x.extension):
            files = PacNodeTree()
            files.rootNode.packToNodes([(x.name, x) for x in entries])
            types.append((PacResourceTypes[extension], files))

        typeNodeTree = PacNodeTree()
        typeNodeTree.rootNode.packToNodes(types)
        typeNodeTree.write(s)
        
        dataNodes = list(typeNodeTree.rootNode.getDataNodes())
        for node in dataNodes:
            s.writeFillOffset(node._uuid)
            node.data.write(s)
            
        s.writeIntegerTable()
        
        nodeTreeSectionSize = s.tell() - 0x30
        pacDependSectionStart = s.tell()
        
        # PAC Depends
        if len(self.depends) > 0:
            s.writeUInt(len(self.depends))
            s.writeNulls(4)
            s.addOffset(s.tell() + 8)
            for i in xrange(len(self.depends)):
                s.addString(baseName + "." + str(i).zfill(3))
            
        pacDependSectionSize = s.tell() - pacDependSectionStart
        entrySectionStart = s.tell()
        
        entryNodes = []
        for dataNode in dataNodes:
            for entryNode in dataNode.data.rootNode.getDataNodes():
                s.writeFillOffset(entryNode._uuid)
                s.writeUInt(entryChecksum)
                s.writeUInt(entryNode.data.size)
                s.writeNulls(8)
                
                if not entryNode.data.isProxy:
                    entryNodes.append(entryNode)
                    s.addFillOffset(entryNode._uuid)
                else:
                    s.writeNulls(8)
                    
                s.writeNulls(8)
                s.addString(entryNode.data.extension)
                
                if not entryNode.data.isProxy:
                    with open(entryNode.data.sourceFileName, "rb") as f:
                        if f.read(4) == b"BINA":
                            s.writeUInt(2)
                        else:
                            s.writeUInt(0)
                else:
                    s.writeUInt(1)
                    
                s.writeNulls(4)
                
        entrySectionSize = s.tell() - entrySectionStart
        stringTableSize = s.writeStringTable()
        dataSectionStart = s.tell()
                 
        for entryNode in entryNodes:
            s.pad(16)
            
            s.writeFillOffset(entryNode._uuid)
            with open(entryNode.data.sourceFileName, "rb") as f:
                s.write(f.read())
                
        s.pad(8)
            
        dataSectionSize = s.tell() - dataSectionStart
        offsetTableSize = s.writeOffsetTable()
        fileSize = s.tell()
        
        s.seek(0)
        s.write(b"PACx301L")
        s.writeUInt(entryChecksum)
        s.writeUInt(fileSize)
        s.writeUInt(nodeTreeSectionSize)
        s.writeUInt(pacDependSectionSize)
        s.writeUInt(entrySectionSize)
        s.writeUInt(stringTableSize)
        s.writeUInt(dataSectionSize)
        s.writeUInt(offsetTableSize)
        
        if baseName != "":
            if len(self.depends) > 0:
                s.writeUShort(5)
            else:
                s.writeUShort(1)
        else:
            s.writeUShort(2)
            
        s.writeUShort(0x108)
        s.writeUInt(len(self.depends))

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print("PAC Unpacker/Packer made by Skyth")
        print("Usage: [*]")
        print("Drag and drop a .PAC to unpack.")
        print("Drag and drop a folder to pack.")
        raw_input()
    else:
        for path in sys.argv[1:]:
            if os.path.isfile(path) and path.lower().endswith(".pac"):
                archive = PacArchive()
                archive.load(path)
                archive.unpack()                
            elif os.path.isdir(path):
                archive = PacArchive()
                archive.addFolder(path)
                archive.splitToDepends()
                archive.save(path + ".pac")
