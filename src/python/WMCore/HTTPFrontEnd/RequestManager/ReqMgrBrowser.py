#!/usr/bin/env python
""" Main Module for browsing and modifying requests """
import WMCore.RequestManager.RequestDB.Interface.User.Registration as Registration
import WMCore.RequestManager.RequestDB.Interface.Request.GetRequest as GetRequest
import WMCore.RequestManager.RequestDB.Interface.Admin.SoftwareManagement as SoftwareAdmin
import WMCore.RequestManager.RequestDB.Interface.Admin.ProdManagement as ProdManagement
import WMCore.RequestManager.RequestDB.Settings.RequestStatus as RequestStatus
import WMCore.RequestManager.RequestDB.Interface.Admin.GroupManagement as GroupManagement
import WMCore.RequestManager.RequestDB.Interface.Admin.UserManagement as UserManagement
import WMCore.RequestManager.RequestDB.Interface.Group.Information as GroupInfo
import WMCore.RequestManager.RequestDB.Interface.User.Requests as UserRequests
import WMCore.RequestManager.RequestDB.Interface.Request.ListRequests as ListRequests
import WMCore.RequestManager.RequestDB.Interface.Request.ChangeState as ChangeState


from WMCore.HTTPFrontEnd.RequestManager.ReqMgrWebTools import parseRunList, parseBlockList, parseSite, allSoftwareVersions, saveWorkload, loadWorkload, changePriority, changeStatus
from WMCore.WMSpec.WMWorkload import WMWorkloadHelper
from WMCore.Cache.WMConfigCache import ConfigCache 
import WMCore.HTTPFrontEnd.RequestManager.Sites
import WMCore.Lexicon
import logging
import cherrypy
import json
import os.path
import urllib
import threading
import types

from WMCore.WebTools.Page import TemplatedPage
from WMCore.WebTools.WebAPI import WebAPI

def detailsBackLink(requestName):
    """ HTML to return to the details of this request """
    return  ' <A HREF=details/%s>Details</A> <A HREF=".">Browse</A><BR>' % requestName

def linkedTableEntry(methodName, entry):
    """ Makes an HTML table entry with the entry name, and a link to a
    method with that entry as an argument"""
    return '<a href="%s/%s">%s</a>' % (methodName, entry, entry)

def statusMenu(requestName, defaultField):
    """ Makes an HTML menu for setting the status """
    html = defaultField + '&nbsp<SELECT NAME="%s:status"> <OPTION></OPTION>' % requestName
    for field in RequestStatus.NextStatus[defaultField]:
        html += '<OPTION>%s</OPTION>' % field
    html += '</SELECT>'
    return html

def priorityMenu(request):
    """ Returns HTML for a box to set priority """
    return '(%su, %sg) %s &nbsp<input type="text" size=2 name="%s:priority">' % (
            request['ReqMgrRequestorBasePriority'], request['ReqMgrGroupBasePriority'], 
            request['ReqMgrRequestBasePriority'],
            request['RequestName'])

def biggestUpdate(field, request):
    """ Finds which of the updates has the biggest number """
    biggest = 0
    for update in request["RequestUpdates"]:
        if update.has_key(field):
            biggest = update[field]
    return "%i%%" % biggest

def addHtmlLinks(d):
    """ Any entry that starts with http becomes an HTML link """
    for key, value in d.iteritems():
        if isinstance(value, types.StringTypes) and value.startswith('http'):
            target = value
            # assume CVS browsers need extra tags
            if 'cvs' in target:
                target += '&view=markup'
            d[key] = '<a href="%s">%s</a>' % (target, value)

class ReqMgrBrowser(WebAPI):
    """ Main class for browsing and modifying requests """
    def __init__(self, config):
        WebAPI.__init__(self, config)
        # Take a guess
        self.templatedir = config.templates
        self.urlPrefix = '%s/download/?filepath=' % config.reqMgrHost
        self.fields = ['RequestName', 'Group', 'Requestor', 'RequestType',
                       'ReqMgrRequestBasePriority', 'RequestStatus', 'Complete', 'Success']
        self.calculatedFields = {'Written': 'percentWritten', 'Merged':'percentMerged',
                                 'Complete':'percentComplete', 'Success' : 'percentSuccess'}
        # entries in the table that show up as HTML links for that entry
        self.linkedFields = {'Group':'group', 'Requestor':'user', 'RequestName':'details'}
        self.detailsFields = ['RequestName', 'RequestType', 'Requestor', 'CMSSWVersion',
                """ Main class for browsing and modifying requests """
            'ScramArch', 'GlobalTag', 'RequestSizeEvents',
            'InputDataset', 'PrimaryDataset', 'AcquisitionEra', 'ProcessingVersion', 
            'RunWhitelist', 'RunBlacklist', 'BlockWhitelist', 'BlockBlacklist', 
            'RequestWorkflow', 'Scenario', 'PrimaryDataset',
            'Acquisition Era', 'Processing Version', 'Merged LFN Base', 'Unmerged LFN Base',
            'Site Whitelist', 'Site Blacklist']

        self.adminMode = True
        # don't allow mass editing.  Make people click one at a time.
        #self.adminFields = {'RequestStatus':'statusMenu', 'ReqMgrRequestBasePriority':'priorityMenu'}
        self.adminFields = {}
        self.requests = []
        self.couchUrl = config.couchUrl
        self.configDBName = config.configDBName
        self.sites = WMCore.HTTPFrontEnd.RequestManager.Sites.sites()
        self.allMergedLFNBases =  ["/store/backfill/1", "/store/backfill/2", "/store/data",  "/store/mc"]
        self.mergedLFNBases = {"ReReco" : ["/store/backfill/1", "/store/backfill/2", "/store/data"],
                               "MonteCarlo" : ["/store/backfill/1", "/store/backfill/2", "/store/mc"]}
        self.yuiroot = config.yuiroot
        cherrypy.engine.subscribe('start_thread', self.initThread)

    def initThread(self, thread_index):
        """ The ReqMgr expects the DBI to be contained in the Thread  """
        myThread = threading.currentThread()
        #myThread = cherrypy.thread_data
        # Get it from the DBFormatter superclass
        myThread.dbi = self.dbi

    def validate(self, v, name=''):
       """ Checks if alphanumeric, tolerating spaces """
       try:
          WMCore.Lexicon.identifier(v)
       except AssertionError:
          raise cherrypy.HTTPError(400, "Bad input %s" % name)
       return v

    @cherrypy.expose
    def index(self):
        """ Main web page """
        requests = GetRequest.getAllRequestDetails()
        tableBody = self.drawRequests(requests)
        return self.templatepage("ReqMgrBrowser", yuiroot=self.yuiroot, 
                                 fields=self.fields, tableBody=tableBody)

    @cherrypy.expose
    def search(self, value, field):
        """ Search for a regular expression in a certain field of all requests """
        filteredRequests = []
        requests = GetRequest.getAllRequestDetails()
        for request in requests:
            if request[field].find(value) != -1:
                filteredRequests.append(request)
        requests = filteredRequests
        tableBody = self.drawRequests(requests)
        return self.templatepage("ReqMgrBrowser", yuiroot=self.yuiroot, 
                                 fields=self.fields, tableBody=tableBody)
        
    @cherrypy.expose
    def splitting(self, requestName):
        """
        _splitting_

        Retrieve the current values for splitting parameters for all tasks in
        the spec.  Format them in the manner that the splitting page expects
        and pass them to the template.
        """
        self.validate(requestName)
        request = GetRequest.getRequestByName(requestName)
        helper = loadWorkload(request)
        splittingDict = helper.listJobSplittingParametersByTask()
        timeOutDict = helper.listTimeOutsByTask()
        taskNames = splittingDict.keys()
        taskNames.sort()

        splitInfo = []
        for taskName in taskNames:
            # We basically stringify the splitting params dictionary and pass
            # that to the splitting page as javascript.  We need to change
            # boolean values to strings as the javascript true is different from
            # the python True.  We'll also add the timeouts here.
            splittingDict[taskName]["timeout"] = timeOutDict[taskName]
            if "split_files_between_job" in splittingDict[taskName]:
                splittingDict[taskName]["split_files_between_job"] = str(splittingDict[taskName]["split_files_between_job"])
                
            splitInfo.append({"splitAlgo": splittingDict[taskName]["algorithm"],
                              "splitParams": str(splittingDict[taskName]),
                              "taskType": splittingDict[taskName]["type"],
                              "taskName": taskName})

        return self.templatepage("Splitting", requestName = requestName,
                                 taskInfo = splitInfo, taskNames = taskNames)
            
    @cherrypy.expose
    def handleSplittingPage(self, requestName, splittingTask, splittingAlgo,
                            **submittedParams):
        """
        _handleSplittingPage_

        Parse job splitting parameters sent from the splitting parameter update
        page.  Pull down the request and modify the new spec applying the
        updated splitting parameters.
        """
        splitParams = {}
        if splittingAlgo == "FileBased":
            splitParams["files_per_job"] = int(submittedParams["files_per_job"])
        elif splittingAlgo == "TwoFileBased":
            splitParams["files_per_job"] = int(submittedParams["two_files_per_job"])
        elif splittingAlgo == "LumiBased":
            splitParams["lumis_per_job"] = int(submittedParams["lumis_per_job"])
            if str(submittedParams["split_files_between_job"]) == "True":
                splitParams["split_files_between_job"] = True
            else:
                splitParams["split_files_between_job"] = False                
        elif splittingAlgo == "EventBased":
            splitParams["events_per_job"] = int(submittedParams["events_per_job"])
        elif 'Merg' in splittingTask:
            for field in ['min_merge_size', 'max_merge_size', 'max_merge_events']:
                splitParams[field] = int(submittedParams[field])
            
        request = GetRequest.getRequestByName(requestName)
        helper = loadWorkload(request)
        logging.info("SetSplitting " + requestName + splittingTask + splittingAlgo + str(splitParams))
        helper.setJobSplittingParameters(splittingTask, splittingAlgo, splitParams)
        helper.setTaskTimeOut(splittingTask, int(submittedParams["timeout"]))
        saveWorkload(helper, workloadUrl)
        return "Successfully updated splitting parameters for " + splittingTask \
               + " " + detailsBackLink(requestName)

    @cherrypy.expose
    def details(self, requestName):
        """ A page showing the details for the requests """
        self.validate(requestName)
        request = GetRequest.getRequestDetails(requestName)
        helper = loadWorkload(request)
        task = helper.getTopLevelTask()
        docId = None
        d = helper.data.request.schema.dictionary_()
        d['RequestWorkflow'] = request['RequestWorkflow']
        d['Site Whitelist'] = task.siteWhitelist()
        d['Site Blacklist'] = task.siteBlacklist()
        if d.has_key('ProdConfigCacheID') and d['ProdConfigCacheID'] != "":
            docId = d['ProdConfigCacheID']        
        assignments = GetRequest.getAssignmentsByName(requestName)
        adminHtml = statusMenu(requestName, request['RequestStatus']) \
                  + ' Priority ' + priorityMenu(request)
        return self.templatepage("Request", requestName=requestName,
                                detailsFields = self.detailsFields, requestSchema=d,
                                docId=docId, assignments=assignments,
                                adminHtml = adminHtml,
                                messages=request['RequestMessages'],
                                updateDictList=request['RequestUpdates'])
                                 

    @cherrypy.expose
    def showOriginalConfig(self, docId):
        """ Makes a link to the original text of the config """
        configCache = ConfigCache(self.couchUrl, self.configDBName)
        configCache.loadByID(docId)
        configString =  configCache.getConfig()
        if configString == None:
            return "Cannot find document " + str(docId) + " in Couch DB"
        return '<pre>' + configString + '</pre>'

    @cherrypy.expose
    def showTweakFile(self, docId):
        """ Makes a link to the dump of the tweakfile """
        configCache = ConfigCache(self.couchUrl, self.configDBName)
        configCache.loadByID(docId)
        return str(configCache.getPSetTweaks()).replace('\n', '<br>')

    @cherrypy.expose
    def showWorkload(self, url):
        """ Displays the workload """
        request = {'RequestWorkflow':url}
        helper = loadWorkload(request)
        return str(helper.data).replace('\n', '<br>')
 
    def drawRequests(self, requests):
        """ Display all requests """
        result = ""
        for request in requests:
            # see if this is slower
            result += self.drawRequest(request)
        return result

    def drawRequest(self, request):
        """ make a table row with information from this request """
        html = '<tr>'
        requestName = request['RequestName']
        for field in self.fields:
            # hanole any fields that have functions linked to them
            html += '<td>'
            if self.adminMode and self.adminFields.has_key(field):
                method = getattr(self, self.adminFields[field])
                html += method(requestName, str(request[field]))
            elif self.linkedFields.has_key(field):
                html += linkedTableEntry(self.linkedFields[field], str(request[field]))
            elif self.calculatedFields.has_key(field):
                method = getattr(self, self.calculatedFields[field])
                html += method(request)
            else:
                html += str(request[field]) 
            html += '</td>'
        html += '</tr>\n'
        return html

    def percentWritten(self, request):
        maxPercent = 0
        for update in request["RequestUpdates"]:
            if update.has_key("events_written") and request["RequestSizeEvents"] != 0:
                percent = update["events_written"] / request["RequestSizeEvents"]
                if percent > maxPercent:
                    maxPercent = percent
            if update.has_key("files_written") and request["RequestSizeFiles"] != 0:
                percent = update["files_written"] / request["RequestSizeFiles"]
                if percent > maxPercent:
                    maxPercent = percent
        return "%i%%" % maxPercent

    def percentMerged(self, request):
        maxPercent = 0
        for update in request["RequestUpdates"]:
            if update.has_key("events_merged") and request["RequestSizeEvents"] != 0:
                percent = update["events_merged"] / request["RequestSizeEvents"]
                if percent > maxPercent:
                    maxPercent = percent
            if update.has_key("files_merged") and request["RequestSizeFiles"] != 0:
                percent = update["files_merged"] / request["RequestSizeFiles"]
                if percent > maxPercent:
                    maxPercent = percent
        return "%i%%" % maxPercent

    def percentComplete(self, request):
        pct = request.get('percent_complete', 0)
        return "%i%%" % pct

    def percentSuccess(self, request):
        pct = request.get('percent_success', 0)
        return "%i%%" % pct

    @cherrypy.expose
    def doAdmin(self, **kwargs):
        """  format of kwargs is {'requestname:status' : 'approved', 'requestname:priority' : '2'} """
        message = ""
        for k, v in kwargs.iteritems():
            if k.endswith(':status'): 
                requestName = k.split(':')[0]
                self.validate(requestName)
                status = v
                priority = kwargs[requestName+':priority']
                if priority != '':
                    changePriority(requestName, priority)
                    message += "Changed priority for %s to %s\n" % (requestName, priority)
                if status != "":
                    changeStatus(requestName, status)
                    message += "Changed status for %s to %s\n" % (requestName, status)
                    if status == "assigned":
                        # make a page to choose teams
                        return self.assignOne(requestName)
        return message + detailsBackLink(requestName)

    def assignOne(self,  requestName):
        request =  GetRequest.getRequestByName(requestName)
        requestType = request["RequestType"]
        # get assignments
        teams = ProdManagement.listTeams()
        assignments = GetRequest.getAssignmentsByName(requestName)
        # might be a list, or a dict team:priority
        if isinstance(assignments, dict):
            assignments = assignments.keys()
        return self.templatepage("Assign", requests=[request], teams=teams, 
                 assignments=assignments, sites=self.sites, mergedLFNBases = self.mergedLFNBases[requestType])

    def requestsWhichCouldLeadTo(self, newStatus):
        # see which status can lead to the new status
        requestIds = []
        for status, next in RequestStatus.NextStatus.iteritems():
            if newStatus in next:
                # returns dict of  name:id
                theseIds = ListRequests.listRequestsByStatus(status).values()
                requestIds.extend(theseIds)

        requests = []
        for requestId in requestIds:
            request = GetRequest.getRequest(requestId)
            if 'InputDataset' in request and request['InputDataset'] != '':
                request['Input'] = request['InputDataset']
            elif 'InputDatasets' in request and len(request['InputDatasets']) != 0:
                request['Input'] = str(request['InputDatasets']).strip("[]'")
            else:
                request['Input'] = "Total Events: %s" % request['RequestSizeEvents']
            if len(request.get('SoftwareVersions', [])) > 0:
                # only show one version
                request['SoftwareVersions'] = request['SoftwareVersions'][0]
            request['PriorityMenu'] = priorityMenu(request)
            requests.append(request)
        return requests

    @cherrypy.expose    
    def assign(self):
        # returns dict of  name:id
        requests = self.requestsWhichCouldLeadTo('assigned')
        teams = ProdManagement.listTeams()
        return self.templatepage("Assign", requests=requests, teams=teams,
                 assignments=[], sites=self.sites, mergedLFNBases = self.allMergedLFNBases)

    @cherrypy.expose
    def handleAssignmentPage(self, **kwargs):
        # handle the checkboxes
        teams = []
        requests = []
        for key, value in kwargs.iteritems():
            if isinstance(value, types.StringTypes):
                kwargs[key] = value.strip()
            if key.startswith("Team"):
                teams.append(key[4:])
            if key.startswith("checkbox"):
                requests.append(key[8:])
        
        for requestName in requests:
            if kwargs['action'] == 'Reject':
                ChangeState.changeRequestStatus(requestName, 'rejected') 
            else:
                assignments = GetRequest.getAssignmentsByName(requestName)
                if teams == [] and assignments == []:
                    raise cherrypy.HTTPError(400, "Must assign to one or more teams")
                self.assignWorkload(requestName, kwargs)
                for team in teams:
                    if not team in assignments:
                        ChangeState.assignRequest(requestName, team)
                priority= kwargs.get(requestName+':priority', '')
                if priority != '':
                    changePriority(requestName, priority)
        return self.templatepage("Acknowledge", participle=kwargs['action']+'ed', requests=requests)

    def assignWorkload(self, requestName, kwargs):
        request = GetRequest.getRequestByName(requestName)
        helper = loadWorkload(request)
        schema = helper.data.request.schema
        for field in ["AcquisitionEra", "ProcessingVersion"]:
            self.validate(kwargs[field], field)
        helper.setSiteWhitelist(parseSite(kwargs,"SiteWhitelist"))
        helper.setSiteBlacklist(parseSite(kwargs,"SiteBlacklist"))
        helper.setProcessingVersion(kwargs["ProcessingVersion"])
        helper.setAcquisitionEra(kwargs["AcquisitionEra"])
        #FIXME not validated
        helper.setLFNBase(kwargs["MergedLFNBase"], kwargs["UnmergedLFNBase"])
        helper.setMergeParameters(int(kwargs["MinMergeSize"]), int(kwargs["MaxMergeSize"]), int(kwargs["MaxMergeEvents"]))
        saveWorkload(helper, request['RequestWorkflow'])
 
    @cherrypy.expose
    def approve(self):
        requests = self.requestsWhichCouldLeadTo('assignment-approved')
        return self.templatepage("Approve", requests=requests)

    @cherrypy.expose
    def handleApprovalPage(self, **kwargs):
        # handle the checkboxes
        requests = []
        for key, value in kwargs.iteritems():
            if isinstance(value, types.StringTypes):
                kwargs[key] = value.strip()
            if key.startswith("checkbox"):
                requests.append(key[8:])
        particple = ''
        for requestName in requests:
            if kwargs['action'] == 'Reject':
                participle = 'rejected'
                ChangeState.changeRequestStatus(requestName, 'rejected')
            else:
                participle = 'approved'
                ChangeState.changeRequestStatus(requestName, 'assignment-approved')
        return self.templatepage("Acknowledge", participle=participle, 
                                 requests=requests)


    @cherrypy.expose
    def modifyWorkload(self, requestName, workload,
                       runWhitelist=None, runBlacklist=None, 
                       blockWhitelist=None, blockBlacklist=None):
        """ handles the "Modify" button of the details page """
        self.validate(requestName) 
        helper = WMWorkloadHelper()
        helper.load(workload)
        schema = helper.data.request.schema
        message = ""
        #inputTask = helper.getTask(requestType).data.input.dataset
        if runWhitelist != "" and runWhitelist != None:
            l = parseRunList(runWhitelist)
            schema.RunWhitelist = l
            helper.setRunWhitelist(l)
            message += 'Changed runWhiteList to %s<br>' % l
        if runBlacklist != "" and runBlacklist != None:
            l = parseRunList(runBlacklist)
            schema.RunBlacklist = l
            helper.setRunBlacklist(l)
            message += 'Changed runBlackList to %s<br>' % l
        if blockWhitelist != "" and blockWhitelist != None:
            l = parseBlockList(blockWhitelist)
            schema.BlockWhitelist = l
            helper.setBlockWhitelist(l)
            message += 'Changed blockWhiteList to %s<br>' % l
        if blockBlacklist != "" and blockBlacklist != None:
            l = parseBlockList(blockBlacklist)
            schema.BlockBlacklist = l
            helper.setBlockBlacklist(l)
            message += 'Changed blockBlackList to %s<br>' % l
        saveWorkload(helper, workload)
        return message + detailsBackLink(requestName)

    @cherrypy.expose
    def user(self, userName):
        self.validate(userName)
        """ Web page of details about the user, and sets user priority """
        groups = GroupInfo.groupsForUser(userName).keys()
        requests = UserRequests.listRequests(userName).keys()
        priority = UserManagement.getPriority(userName)
        allGroups = GroupInfo.listGroups()
        return self.templatepage("User", user=userName, groups=groups, 
            allGroups=allGroups, requests=requests, priority=priority)

    @cherrypy.expose
    def handleUserPriority(self, user, userPriority):
        """ Handles setting user priority """
        self.validate(user)
        UserManagement.setPriority(user, userPriority)
        return "Updated user %s priority to %s" % (user, userPriority)

    @cherrypy.expose
    def group(self, groupName):
        """ Web page of details about the user, and sets user priority """
        self.validate(groupName)
        users = GroupInfo.usersInGroup(groupName)
        priority = GroupManagement.getPriority(groupName)
        return self.templatepage("Group", group=groupName, users=users, priority=priority)

    @cherrypy.expose
    def handleGroupPriority(self, group, groupPriority):
        """ Handles setting group priority """
        self.validate(group)
        GroupManagement.setPriority(group, groupPriority)
        return "Updated group %s priority to %s" % (group, groupPriority)

    @cherrypy.expose
    def users(self):
        """ Lists all users.  Should be paginated later """
        allUsers = Registration.listUsers()
        return self.templatepage("Users", users=allUsers)

    @cherrypy.expose
    def handleAddUser(self, user, email=None):
        """ Handles setting user priority """
        self.validate(user)
        result = Registration.registerUser(user, email)
        return "Added user %s" % user

    @cherrypy.expose
    def handleAddToGroup(self, user, group):
        """ Adds a user to the group """
        self.validate(user)
        self.validate(group)
        GroupManagement.addUserToGroup(user, group)
        return "Added %s to %s " % (user, group)

    @cherrypy.expose
    def groups(self):
        """ Lists all users.  Should be paginated later """
        allGroups = GroupInfo.listGroups()
        return self.templatepage("Groups", groups=allGroups)

    @cherrypy.expose
    def handleAddGroup(self, group):
        """ Handles adding a group """
        self.validate(group)
        GroupManagement.addGroup(group)
        return "Added group %s " % group

    @cherrypy.expose
    def teams(self):
        """ Lists all teams """
        return self.templatepage("Teams", teams = ProdManagement.listTeams()
)

    @cherrypy.expose
    def team(self, teamName):
        """ Details for a team """
        self.validate(teamName)
        assignments = ListRequests.listRequestsByTeam(teamName)
        return self.templatepage("Team", team=teamName, requests=assignments.keys())

    @cherrypy.expose
    def handleAddTeam(self, team):
        """ Handles a request to add a team """
        self.validate(team)
        ProdManagement.addTeam(team)
        return "Added team %s" % team

    @cherrypy.expose
    def versions(self):
        """ Lists all versions """
        versions = SoftwareAdmin.listSoftware().keys()
        versions.sort()
        return self.templatepage("Versions", versions=versions)

    @cherrypy.expose
    def handleAddVersion(self, version):
        """ Registers a version """
        WMCore.Lexicon.cmsswversion(version)
        SoftwareAdmin.addSoftware(version)
        return "Added version %s" % version

    @cherrypy.expose
    def handleAllVersions(self):
        """ Registers all versions in the TC """
        currentVersions = SoftwareAdmin.listSoftware().keys()

        allVersions = allSoftwareVersions()
        result = ""
        for version in allVersions:
            if not version in currentVersions:
               SoftwareAdmin.addSoftware(version)
               result += "Added version %s<br>" % version
        if result == "":
            result = "Version list is up to date"
        return result

