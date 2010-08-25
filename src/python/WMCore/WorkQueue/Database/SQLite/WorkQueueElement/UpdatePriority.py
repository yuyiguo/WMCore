"""
_UpdatePriority_

SQLite implementation of WorkQueueElement.Priority
"""

__all__ = []
__revision__ = "$Id: UpdatePriority.py,v 1.2 2009/08/18 23:18:12 swakef Exp $"
__version__ = "$Revision: 1.2 $"

from WMCore.WorkQueue.Database.MySQL.WorkQueueElement.UpdatePriority \
     import UpdatePriority as UpdatePriorityMySQL

class UpdatePriority(UpdatePriorityMySQL):
    sql = UpdatePriorityMySQL.sql
