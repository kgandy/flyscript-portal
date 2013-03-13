# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the 
# MIT License set forth at:
#   https://github.com/riverbed/flyscript/blob/master/LICENSE ("License").  
# This software is distributed "AS IS" as set forth in the License.


from time import sleep
import math
import datetime
import shutil
import os
import pickle
import sys
import traceback
import threading
import json
import cgi

from django.db import models
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.core.exceptions import ObjectDoesNotExist

from model_utils.managers import InheritanceManager
from libs.fields import PickledObjectField
from jsonfield import JSONField

import logging
logger = logging.getLogger('datasource')

from apps.datasource.devicemanager import DeviceManager

# Support subclassing via get_subclass()
# objects = InheritanceManager()

lock = threading.Lock()

#
# Device
#
class Device(models.Model):
    name = models.CharField(max_length=200)
    sourcetype = models.CharField(max_length=200)
    host = models.CharField(max_length=200)
    port = models.IntegerField()
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)

    def __unicode__(self):
        return self.name

#
# DataTable
#
class DataTable(models.Model):
    source = models.CharField(max_length=200)    # source module name
    filterexpr = models.TextField(blank=True)
    duration = models.IntegerField()             # length of query in minutes
    resolution = models.IntegerField(default=60) # resolution of graph in seconds
    sortcol = models.ForeignKey('DataColumn', null=True, related_name='DataColumn')
    rows = models.IntegerField(default=-1)

    options = JSONField()

    def poll(self, ts=1):
        # Ultimately, this function must return the data for the DataTable
        # The actual data is pulled from the "DataTable.source" function.
        #
        # This class *may* do caching, in which case there either may be
        # no actual call to the source to get data, or the call my cover
        # a different timeframe

        # Always create a Job
        jobhandle = "job-datatable%s-ts%s" % (self.id, ts)
        with lock:
            try:
                job = Job.objects.get(handle=jobhandle)
                logger.debug("DataTable Job in progress: %s" % jobhandle)

            except ObjectDoesNotExist:
                logger.debug("New DataTable Job: %s" % jobhandle)

                job = Job(datatable=self, handle=jobhandle)
                job.save()

                # Lookup the query class for this source
                import apps.datasource.datasource
                queryclass = apps.datasource.datasource.__dict__[self.source].DataTable_Query
                
                # Create an asynchronous worker to do the work
                worker = AsyncWorker(job, queryclass)
                worker.start()

        return job

    def __unicode__(self):
        return str(self.id)

class DataColumn(models.Model):
    datatable = models.ForeignKey(DataTable)

    querycol = models.CharField(max_length=30)
    label = models.CharField(max_length=30)
    datatype = models.CharField(max_length=50, default='')

    axis = models.IntegerField(default=0)

    def __unicode__(self):
        return self.label

#
# Job
#
class Job(models.Model):
    handle = models.CharField(max_length=100)

    NEW = 0
    RUNNING = 1
    COMPLETE = 2
    ERROR = 3
    
    status = models.IntegerField(default=NEW,
                                 choices = ((NEW, "New"),
                                            (RUNNING, "Running"),
                                            (COMPLETE, "Complete"),
                                            (ERROR, "Error")))

    message = models.CharField(max_length=200, default="")
    progress = models.IntegerField(default=-1)
    remaining = models.IntegerField(default=-1)
    datatable = models.ForeignKey(DataTable)

    def __unicode__(self):
        return "%s, %s %s%%" % (self.handle, self.status, self.progress)
    
    def done(self):
        return self.status == Job.COMPLETE or self.status == Job.ERROR

    def datafile(self):
        return self.handle + ".data"
    
    def data(self):
        f = open(self.datafile(), "r")
        reportdata = pickle.load(f)
        f.close()
        return reportdata

    def savedata(self, data):
        f = open(self.datafile(), "w")
        pickle.dump(data, f)
        f.close()
        
    def json(self, data=None):
        return { 'progress': self.progress,
                 'remaining': self.remaining,
                 'status': self.status,
                 'message': self.message,
                 'data': data }

#
# AsyncWorker
#
class AsyncWorker(threading.Thread):
    def __init__(self, job, queryclass):
        threading.Thread.__init__(self)
        self.job = job
        self.queryclass = queryclass
        
    def run(self):
        logger.debug("Starting job %s" % self.job.handle)
        job = self.job
        try:
            query = self.queryclass(self.job.datatable, self.job)
            query.run()
            job.savedata(query.data)
            logger.debug("Saving job %s as COMPLETE" % self.job.handle)
            job.progress = 100
            job.status = job.COMPLETE
        except :
            traceback.print_exc()
            logger.error("Job %s failed: %s" % (self.job.handle, str(sys.exc_info())))
            job.status = job.ERROR
            job.progress = 100
            job.message = traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1])

        job.save()
        sys.exit(0)