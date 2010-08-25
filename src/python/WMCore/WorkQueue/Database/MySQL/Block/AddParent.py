"""
_New_

MySQL implementation of Block.AddParent
"""

__all__ = []
__revision__ = "$Id: AddParent.py,v 1.3 2009/08/18 23:18:14 swakef Exp $"
__version__ = "$Revision: 1.3 $"

from WMCore.Database.DBFormatter import DBFormatter

class AddParent(DBFormatter):
    sql = """INSERT INTO wq_block_parentage (child, parent) 
                 VALUES (SELECT id FROM wq_block WHERE name = :childName, 
                         SELECT id FROM wq_block WHERE name = :parentName)
          """

    def execute(self, childName, parentName, conn = None, transaction = False):
        binds = {"childName": childName, "parentName": parentName}

        self.dbi.processData(self.sql, binds, conn = conn,
                             transaction = transaction)            
        return