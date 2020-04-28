# -*- coding: utf-8 -*-
 
from . import SFPac3
import os
import itertools
 


class PacArchiveNav(SFPac3.PacArchive):
    def printmn(self, output = ""):
        if output == "":
            output = os.path.splitext(self.filePath)[0]
        with open(self.filePath, "rb") as f:
            for entry in self.entries:
                if not entry.isProxy:                    
                    print(os.path.join(output, entry.name + "." + entry.extension))
        for depend in self.depends:
            depend.printmn(output)
    def getAllEntries(self):            
            return [e for e in itertools.chain(
                    (entry for entry in self.entries if not entry.isProxy),
                    (entry for depend in self.depends for entry in depend.entries))]
                
    def getAllEntriesByExtension(self,ext):            
        return [e for e in itertools.chain(
                    (entry for entry in self.entries if not entry.isProxy),
                    (entry for depend in self.depends for entry in depend.entries))if e.extension== ext]
    
     