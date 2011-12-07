#!/usr/bin/env python

"""
_PilotManagerClient_



"""





import os
import time
import inspect
import threading

#from MessageService.MessageService import MessageService
from WMCore.Agent.Configuration import loadConfigurationFile
from WMCore.WMFactory import WMFactory
from WMCore.Database.Transaction import Transaction
from WMCore.Database.DBFactory import DBFactory
#for logging
import logging
#TaskQueue
from PilotManager.PilotManagerComponent import PilotManagerComponent


config = loadConfigurationFile(\
                       '/data/khawar/prototype/PilotManager/DefaultConfig.py')

config.section_("General")

config.General.workDir = '/data/khawar/prototype/work/PilotManager'
config.Agent.componentName='PilotManager'

config.section_("CoreDatabase")
config.CoreDatabase.dialect = 'mysql'
config.CoreDatabase.socket = '/data/khawar/PAProd/0_12_13/prodAgent/mysqldata/mysql.sock'
config.CoreDatabase.user = 'root'
config.CoreDatabase.passwd = '98passwd'
config.CoreDatabase.hostname = 'localhost'
config.CoreDatabase.name = 'ProdAgentDB'


#start the module
pilotManager = PilotManagerComponent(config)
pilotManager.prepareToStart()

#pilotManager.startDaemon()

#pilotManager.handleMessage('NewPilotJob','Pilot#45,45,xyzfiles')

pilotManager.handleMessage('SubmitPilotJob','Pilot#45,45,xyzfiles')
