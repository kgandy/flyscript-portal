# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the 
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").  
# This software is distributed "AS IS" as set forth in the License.

import time
import logging
import threading
import datetime

import rvbd.profiler
from rvbd.profiler.filters import TimeFilter, TrafficFilter
from rvbd.common.jsondict import JsonDict

from apps.datasource.models import Device, Table
from apps.datasource.devicemanager import DeviceManager

logger = logging.getLogger(__name__)
lock = threading.Lock()

def DeviceManager_new(*args, **kwargs):
    # Used by DeviceManger to create a Profiler instance
    return rvbd.profiler.Profiler(*args, **kwargs)

class TableOptions(JsonDict):
    _default = { 'groupby' : None,
                 'realm' : None,
                 'centricity' : None }

class TimeSeriesTable:
    @classmethod
    def create(cls, name, device, duration, interface=False, **kwargs):
        t = Table(name=name, module=__name__, device=device, duration=duration,
                  options=TableOptions(groupby='time',
                                       realm='traffic_overall_time_series',
                                       centricity='int' if interface else 'hos'),
                  **kwargs)
        t.save()
        return t
        

class GroupByTable:
    @classmethod
    def create(cls, name, device, groupby, duration, filterexpr=None, interface=False, **kwargs):
        t = Table(name=name, module=__name__, device=device, duration=duration,
                  filterexpr=filterexpr,
                  options=TableOptions(groupby=groupby,
                                       realm='traffic_summary',
                                       centricity='int' if interface else 'hos'),
                  **kwargs)
        t.save()
        return t
        
class TableQuery:
    # Used by Table to actually run a query
    def __init__(self, table, job):
        self.table = table
        self.job = job

    def fake_run(self):
        import fake_data
        self.data = fake_data.make_data(self.table)
        
    def run(self):
        #self.fake_run()
        #return
    
        table = self.table
        options = table.options

        profiler = DeviceManager.get_device(table.device.id)
        report = rvbd.profiler.report.SingleQueryReport(profiler)

        columns = [col.name for col in table.get_columns(synthetic=False)]

        sortcol=None
        if table.sortcol is not None:
            sortcol=table.sortcol.name

        criteria = self.job.criteria
        tf = TimeFilter(start=datetime.datetime.fromtimestamp(criteria.starttime),
                        end=datetime.datetime.fromtimestamp(criteria.endtime))

        logger.info("Running report for timeframe %s" % str(tf))
        if table.datafilter:
            datafilter = table.datafilter.split(',')
        else:
            datafilter = None

        with lock:
            report.run(realm=options.realm,
                       groupby=profiler.groupbys[options.groupby],
                       centricity=options.centricity,
                       columns=columns,
                       timefilter=tf, 
                       trafficexpr = TrafficFilter(self.job.combine_filterexprs()),
                       data_filter=datafilter,
                       resolution="%dmin" % (int(table.resolution / 60)),
                       sort_col=sortcol,
                       sync=False
                       )

        done = False
        logger.info("Waiting for report to complete")
        while not done:
            time.sleep(0.5)
            with lock:
                s = report.status()

            self.job.progress = int(s['percent'])
            self.job.save()
            done = (s['status'] == 'completed')

        # Retrieve the data
        with lock:
            self.data = report.get_data()

        if table.rows > 0:
            self.data = self.data[:table.rows]

        logger.info ("job %s return %s rows" % (self.job, len(self.data)))
        return True

