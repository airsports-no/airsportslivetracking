from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render


# Create your views here.
def verification_successful(request):
    messages.success(request, "Email address successfully verified")
    return HttpResponseRedirect("/")
