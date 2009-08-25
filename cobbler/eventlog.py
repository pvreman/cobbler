"""
Event log writing and reading.

Copyright 2006-2009, Red Hat, Inc
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


FIELDS = ["time","system","user","deployid","title","message"]
EVENT_CSVFILE = "/var/log/cobbler/eventlog.csv"

EVENT_START   = "start"
EVENT_STOP    = "stop"
EVENT_INFO    = "info"

class EventLog:
    """
    Handles the reading and writing of events
    """
            
    def __init__(self,config):
        """
        Constructor
        """
        self.config      = config
        self.api         = config.api
        self.logger      = self.api.logger
        self.events      = []
        self.active_event_ids = {}
        self._read_events()

    def _read_events(self):
        self.events = []
        try:
            inf = file(EVENT_CSVFILE,"rb")
            rd = csv.DictReader( inf, FIELDS )
            logger.debug("loading old events from %s" % EVENT_CSVFILE)
            for event in rd:
                self.events.append(event)
        except:
            pass

    def _write_event(self,event):
        inf = file(EVENT_CSVFILE,"ab")
        wr = csv.DictWriter( inf, FIELDS )
        wr.writerow(event)
                    
    def log(self,event_id,status,message):
        event_info=active_event_ids.get(event_id,None)
        if event_info is None:
            raise CX("Event id %s is not active" % event_id)
        event={}
        t = time.time()
        (year, month, day, hour, minute, second, weekday, julian, dst) = time.localtime()
        event["time"]="%04d-%02d-%02d %02d:%02d:%02d" % (year,month,day,hour,minute,second)
        event["event_id"]=event_id
        event["action"]=event_info["action"]
        event["system"]=event_info["system"]
        event["user"]=event_info["user"]
        event["status"]=status
        event["message"]=message
        _write_event(event)
        logger.info("EVENT: %s" % event)
        # Remove from active events if we received STOP
        if status==EVENT_STOP:
            logger.debug("removing event_id %s from active events" % event_id)
            del active_event_ids[event_id]
        
    def new_event_id(self,action,system="",user=""):
        # Generate ID, based on the current time
        # FIXME this is not unique for events within the same second
        t = time.time()
        (year, month, day, hour, minute, second, weekday, julian, dst) = time.localtime()
        event_id="%04d-%02d-%02d_%02d%02d%02d" % (year,month,day,hour,minute,second)

        # Register in active events
        logger.debug("adding event_id %s to active events" % event_id)
        event_info={}
        event_info["action"]=action
        event_info["system"]=system
        event_info["user"]=user
        active_event_ids[event_id]=event_info
        return event_id

    def task_log_filename(self,event_id):
        """
        Returns the filename to use for logging the output of a task
        """
        event_info=active_event_ids.get(event_id,None)
        if event_info is None:
            raise CX("Event id %s is not active" % event_id)
        stripped_event_id = str(event_id).replace("..","").replace("/","")
        return "/var/log/cobbler/tasks/%s_%s.log" % (stripped_event_id,event_info["action"])

    def get_task_log(self,event_id):
        """
        Returns the contents of a task log.
        Events that are not task-based do not have logs.
        """
        self.logger.debug("Reading log for task %s" % event_id)
        path = task_log_filename(event_id)
        if os.path.exists(path):
           fh = open(path, "r")
           data = str(fh.read())
           data = self.translator(data)
           fh.close()
           return data
        else:
           return "?"
