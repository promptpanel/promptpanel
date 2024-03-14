from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from user.decorators import view_authenticated


def login(request):
    if not User.objects.exists():
        return redirect("/onboarding/")
    context = {}
    return render(request, "login.html", context)


def onboarding(request):
    if User.objects.exists():
        return redirect("/login/")
    context = {}
    return render(request, "onboarding.html", context)


@view_authenticated
def onboarding_first(request):
    context = {}
    return render(request, "onboarding_first.html", context)


@view_authenticated
def profile(request):
    context = {}
    return render(request, "profile.html", context)


@view_authenticated
def update_password(request):
    context = {}
    return render(request, "update_password.html", context)


@view_authenticated
def system(request):
    context = {}
    return render(request, "system.html", context)


@view_authenticated
def local_model(request):
    context = {}
    return render(request, "local_model.html", context)
