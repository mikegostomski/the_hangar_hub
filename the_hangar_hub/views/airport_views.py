from django.shortcuts import render
from django.http import HttpResponse, HttpResponseForbidden
from base.classes.util.log import Log
from base.models.utility.audit import Audit
log = Log()

def welcome(request):
    return HttpResponse("Create a new airport")


