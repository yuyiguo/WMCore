"""
_Exists_

MySQL implementation of WMSpec.Exists
"""
__all__ = []
__revision__ = "$Id: Exists.py,v 1.2 2009/08/18 23:18:12 swakef Exp $"
__version__ = "$Revision: 1.2 $"

from WMCore.Database.DBFormatter import DBFormatter

class Exists(DBFormatter):
    sql = """SELECT id FROM wq_wmspec WHERE name = :name"""
    
    def format(self, result):
        result = DBFormatter.format(self, result)
        if len(result) == 0:
            return False
        else:
            return int(result[0][0])
        
    def getBinds(self, name = None):
        return self.dbi.buildbinds(self.dbi.makelist(name), 'name')
        
    def execute(self, name = None, conn = None, transaction = False):
        result = self.dbi.processData(self.sql, self.getBinds(name), 
                         conn = conn, transaction = transaction)
        return self.format(result)