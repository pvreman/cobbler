"""
Task registeration and persistent task events writing and reading

Copyright 2006-2009, Red Hat, Inc
Peter Vreman <peter.vreman@acision.com>
Michael DeHaan <mdehaan@redhat.com>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
02110-1301  USA
"""

import utils
import item
from cexceptions import *
from utils import _
import time
import codes
import csv
import os
import string

# Event CSV definiation
EVENT_CSVFILE = "/var/log/cobbler/events.csv"
EVENT_FIELDS  = ["time","task_id","task_name","event","system","user","message"]
TASK_FIELDS   = ["task_id","name","system","user","start_time","end_time"]

# Event status
EVENT_START    = "start"
EVENT_COMPLETE = "complete"
EVENT_FAILED   = "failed"
EVENT_INFO     = "info"

TIME_FMT    = "%Y-%m-%d %H:%M:%S"
TASK_ID_FMT = "%Y%m%d_%H%M%S"

class Tasks:
    """
    Handles the reading and writing of tasks
    """
            
    def __init__(self,config):
        """
        Constructor
        """
        self.config       = config
        self.api          = config.api
        self.logger       = self.api.logger
        self.translator   = utils.Translator(keep=string.printable)
        self.events       = []
        self.active_tasks = {}
        self._read_old_events()

    def _read_old_events(self):
        """
        Read old events in a list
        """
        self.events = []
        if os.path.exists(EVENT_CSVFILE):
            inf = file(EVENT_CSVFILE,"rb")
            rd = csv.DictReader( inf, EVENT_FIELDS )
            self.logger.debug("loading old task events from %s" % EVENT_CSVFILE)
            for event in rd:
                self.events.append(event)

    def _write_event(self,event):
        """
        Write event to csv file and store in list
        """
        inf = file(EVENT_CSVFILE,"ab")
        wr = csv.DictWriter( inf, EVENT_FIELDS )
        wr.writerow(event)
        self.events.append(event)
                    
    def _log(self,task_id,task_event,message):
        active_task=self.get_active_task(task_id)
        event={}
        event["time"]=time.strftime(TIME_FMT)
        event["task_id"]=task_id
        event["task_name"]=active_task["name"]
        event["event"]=task_event
        event["system"]=active_task["system"]
        event["user"]=active_task["user"]
        event["message"]=message
        self._write_event(event)
        self.logger.info("EVENT task_id(%s); task_name(%s); event(%s); %s" % (task_id,active_task["name"],task_event,message))

    def event_start(self,task_id,message):
        self._log(task_id,EVENT_START,message)

    def event_complete(self,task_id,message):
        self._log(task_id,EVENT_COMPLETE,message)
        if self.active_tasks.has_key(task_id):
            self.active_tasks[task_id]["end_time"]=time.strftime(TIME_FMT)

    def event_failed(self,task_id,message):
        self._log(task_id,EVENT_FAILED,message)
        if self.active_tasks.has_key(task_id):
            self.active_tasks[task_id]["end_time"]=time.strftime(TIME_FMT)

    def event_info(self,task_id,message):
        self._log(task_id,EVENT_INFO,message)

    def new_task(self,name,system="",user=""):
        # Generate ID, based on the current time
        # FIXME this is not unique for tasks within the same second
        task_id=time.strftime(TASK_ID_FMT)

        # Register in active tasks
        self.logger.debug("adding task_id %s to active tasks" % task_id)
        active_task={}
        active_task["task_id"]=task_id
        active_task["name"]=name
        active_task["system"]=system
        active_task["user"]=user
        active_task["start_time"]=time.strftime(TIME_FMT)
        self.active_tasks[task_id]=active_task
        return task_id

    def get_active_task(self,task_id):
        active_task=self.active_tasks.get(task_id,None)
        if active_task is None:
            raise CX("task id %s is not active" % task_id)
        return active_task

    def get_detailed_logfile(self,task_id):
        """
        Returns the filename to use for logging the output of a task
        """
        active_task=self.get_active_task(task_id)
        stripped_task_id = str(task_id).replace("..","").replace("/","")
        return "/var/log/cobbler/tasks/%s_%s.log" % (stripped_task_id,active_task["name"])

    def get_detailed_log(self,task_id):
        """
        Returns the contents of a task log.
        tasks that are not task-based do not have logs.
        """
        self.logger.debug("Reading log for task %s" % task_id)
        path = self.get_detailed_logfile(task_id)
        if os.path.exists(path):
            fh = open(path, "r")
            data = str(fh.read())
            data = self.translator(data)
            fh.close()
            return data
        else:
            return "?"

    def find_events(self,recent=False,running=False,criteria={}):
        """
        Returns a list of hashes with the tasks matching the criteria.
        Recent checks also if the task is still in the active_task list
        Running checks also that the end_time is not yet known
        """
        if running:
            recent=True
        self.events_filtered = []
        for event in self.events:
            skip=False
            for (key,value) in criteria.iteritems():
                if event.get(key,"")!=value:
                    skip=True
                    break
            if skip:
                continue
            if recent:
                active_task=self.active_tasks.get(event["task_id"],None)
                if active_task is None:
                    continue
                if running and active_task.has_key("end_time"):
                    continue
            self.events_filtered.append(event)
        return self.events_filtered

    def find_tasks(self,recent=False,running=False,criteria={}):
        """
        Returns a list of hashes with the tasks matching the criteria.
        Recent checks also if the task is still in the active_task list
        Running checks also that the end_time is not yet known
        """
        if running:
            recent=True
        self.tasks_filtered = []
        for task in self.active_tasks.iteritems():
            skip=False
            for (key,value) in criteria.iteritems():
                if task.get(key,"")!=value:
                    skip=True
                    break
            if skip:
                continue
            if recent:
                active_task=self.active_tasks.get(task["task_id"],None)
                if active_task is None:
                    continue
                if running and active_task.has_key("end_time"):
                    continue
            self.tasks_filtered.append(task)
        return self.tasks_filtered
