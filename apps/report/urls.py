# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the 
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").  
# This software is distributed "AS IS" as set forth in the License.


from django.conf.urls import patterns, include, url
from django.views.generic import DetailView, ListView
from apps.report.models import Job
import apps.report.views as views

for j in Job.objects.all():
    j.delete()

urlpatterns = patterns(
    'apps.report.views',
    url(r'^$', views.ReportView.as_view(), name='report-view-root'),

    url(r'^reload$', 'reload_config', name='reload-all'),

    url(r'^(?P<report_slug>[0-9_a-zA-Z]+)/$',
        views.ReportView.as_view(), name='report-view'),

    #url(r'^(?P<report_slug>[0-9_a-zA-Z]+)/configure$', 'configure'),

    url(r'^(?P<report_slug>[0-9_a-zA-Z]+)/reload$', 'reload_config', name='reload-report'),

    #url(r'^(?P<report_slug>[0-9_a-zA-Z]+)/configure/(?P<widget_id>[0-9]+)$', 'configure'),

    url(r'^(?P<report_slug>[0-9_a-zA-Z]+)/widget/(?P<widget_id>[0-9]+)/jobs/$',
        views.WidgetJobsList.as_view()),
    
    url(r'^(?P<report_slug>[0-9_a-zA-Z]+)/widget/(?P<widget_id>[0-9]+)/jobs/(?P<job_id>[0-9]+)/$',
        views.WidgetJobDetail.as_view(),
        name='report-job-detail'),
)
