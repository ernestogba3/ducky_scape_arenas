from django.contrib.auth import authenticate, login, logout, views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from accounts.decorators import role_required

from .forms import LoginForm, RegisterForm
from .models import ProfileUser


@role_required("ADMIN")
def dashboard_view(request):
    return render(request, 'accounts/dashboard.html')

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('accounts:profile')
            form.add_error(None, "Invalid username or password")
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()


            return redirect('accounts:login')
        else:
            form.add_error(None, "Please correct the errors below.")
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


class PasswordResetView(auth_views.PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    success_url = reverse_lazy('accounts:password_reset_done')


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html')


@login_required
def delete_account_view(request):
    if request.method == 'POST':
        user = request.user
        user.delete()
        logout(request)
        return redirect('accounts:login')
    return redirect('accounts:profile')


def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('accounts:login')
    return redirect('accounts:login')
