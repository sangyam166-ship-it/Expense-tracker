import csv
import json
import datetime
from decimal import Decimal
from io import BytesIO, StringIO

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db import transaction as db_transaction
from django.db.models import Sum, Q, Count, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

from .models import (
    UserProfile, Category, Transaction, Budget,
    SavingsGoal, RecurringTransaction, Notification
)
from .forms import (
    FinoraUserRegistrationForm, FinoraLoginForm, UserProfileForm,
    FinoraPasswordChangeForm, TransactionForm, BudgetForm,
    SavingsGoalForm, SavingsContributionForm, RecurringTransactionForm,
    CategoryForm, CSVImportForm, DataRestoreForm
)
from .serializers import (
    TransactionSerializer, BudgetSerializer,
    CategorySerializer, SavingsGoalSerializer, NotificationSerializer
)


# ==============================================================================
# AUTHENTICATION & PROFILE VIEWS
# ==============================================================================

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = FinoraUserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            currency = form.cleaned_data.get('currency', 'USD')
            profile = user.profile
            profile.currency = currency
            profile.save()

            login(request, user)
            messages.success(request, f"Welcome to FINORA, {user.first_name or user.username}! Your workspace has been initialized.")
            return redirect('dashboard')
        else:
            messages.error(request, "Please correct the errors below to create your account.")
    else:
        form = FinoraUserRegistrationForm()

    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = FinoraLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = FinoraLoginForm()

    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    return redirect('dashboard')


@login_required
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
            user = request.user
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.email = request.POST.get('email', user.email)
            user.save()

            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Your profile details have been updated successfully.")
                return redirect('profile')
            else:
                messages.error(request, "Error updating profile details.")
                password_form = FinoraPasswordChangeForm(user=request.user)

        elif action == 'change_password':
            password_form = FinoraPasswordChangeForm(user=request.user, data=request.POST)
            profile_form = UserProfileForm(instance=profile, initial={
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
            })
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Your password has been changed securely.")
                return redirect('profile')
            else:
                messages.error(request, "Failed to change password. Please check requirements.")
        else:
            profile_form = UserProfileForm(instance=profile, initial={
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
            })
            password_form = FinoraPasswordChangeForm(user=request.user)
    else:
        profile_form = UserProfileForm(instance=profile, initial={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        })
        password_form = FinoraPasswordChangeForm(user=request.user)

    context = {
        'profile': profile,
        'profile_form': profile_form,
        'password_form': password_form,
        'restore_form': DataRestoreForm(),
    }
    return render(request, 'tracker/profile.html', context)


@login_required
def toggle_theme_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    new_theme = 'light' if profile.theme == 'dark' else 'dark'
    profile.theme = new_theme
    profile.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax'):
        return JsonResponse({'status': 'success', 'theme': new_theme})
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


@login_required
def update_currency_view(request):
    if request.method == 'POST':
        new_currency = request.POST.get('currency', 'USD')
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if new_currency in dict(UserProfile.CURRENCY_CHOICES):
            profile.currency = new_currency
            profile.save()
            messages.success(request, f"Currency updated to {profile.get_currency_display()}.")
    return redirect(request.META.get('HTTP_REFERER', 'profile'))


# ==============================================================================
# FINANCIAL HEALTH & CREDIT INDEX ALGORITHM
# ==============================================================================

def compute_financial_health_score(user, current_year, current_month):
    """
    Computes an empirical 0-100 Financial Health & Credit Index score based on:
    - Savings rate (35 pts)
    - Budget discipline & adherence (30 pts)
    - Debt-to-income / Burn rate buffer (20 pts)
    - Goals momentum & wealth building (15 pts)
    """
    month_txs = Transaction.objects.filter(user=user, date__year=current_year, date__month=current_month)
    income = month_txs.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    expense = month_txs.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    savings = income - expense

    # 1. Savings Ratio Score (Max 35)
    savings_score = 0
    if income > Decimal('0.00'):
        ratio = float(savings / income)
        if ratio >= 0.25:
            savings_score = 35
        elif ratio > 0:
            savings_score = int(ratio * 140)
        else:
            savings_score = 5
    else:
        savings_score = 15

    # 2. Budget Discipline Score (Max 30)
    budget = Budget.objects.filter(user=user, category__isnull=True, month=current_month, year=current_year).first()
    budget_score = 20  # default baseline
    if budget and budget.amount > Decimal('0.00'):
        pct = float(budget.get_percentage())
        if pct <= 75.0:
            budget_score = 30
        elif pct <= 95.0:
            budget_score = 22
        elif pct <= 100.0:
            budget_score = 15
        else:
            budget_score = 5
    elif expense > Decimal('0.00'):
        budget_score = 15

    # 3. Burn Rate / Operational Buffer (Max 20)
    burn_score = 10
    if income > Decimal('0.00'):
        burn_ratio = float(expense / income)
        if burn_ratio <= 0.50:
            burn_score = 20
        elif burn_ratio <= 0.75:
            burn_score = 14
        elif burn_ratio <= 1.0:
            burn_score = 8
        else:
            burn_score = 2

    # 4. Wealth Goals Momentum (Max 15)
    goals = SavingsGoal.objects.filter(user=user)
    goals_score = 5
    if goals.filter(status='COMPLETED').exists():
        goals_score = 15
    elif goals.filter(status='IN_PROGRESS', current_amount__gt=Decimal('0.00')).exists():
        goals_score = 12
    elif goals.exists():
        goals_score = 8

    total_score = min(100, max(10, savings_score + budget_score + burn_score + goals_score))

    if total_score >= 85:
        tier = "A+"
        status_label = "Superb Financial Health"
        badge_class = "success"
        color = "var(--emerald-green)"
        recommendation = "Outstanding capital discipline! You are retaining strong cashflow and hitting wealth-building benchmarks."
    elif total_score >= 70:
        tier = "A"
        status_label = "Strong Financial Health"
        badge_class = "normal"
        color = "var(--electric-blue)"
        recommendation = "Solid foundation. Increase allocations to active savings targets to graduate into the A+ tier."
    elif total_score >= 50:
        tier = "B"
        status_label = "Fair & Balanced"
        badge_class = "warning"
        color = "var(--amber-warning)"
        recommendation = "Spending is near parity with earnings. Set category budgets to build a stronger emergency cushion."
    else:
        tier = "C"
        status_label = "Needs Optimization"
        badge_class = "danger"
        color = "var(--coral-red)"
        recommendation = "High burn rate detected. Review subscriptions and discretionary expenses to restore positive cash flow."

    return {
        'score': total_score,
        'tier': tier,
        'status_label': status_label,
        'badge_class': badge_class,
        'color': color,
        'recommendation': recommendation,
        'savings_score': savings_score,
        'budget_score': budget_score,
        'burn_score': burn_score,
        'goals_score': goals_score,
    }


# ==============================================================================
# DASHBOARD VIEW (ACTUAL DATABASE METRICS)
# ==============================================================================

@login_required
def dashboard_view(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    today = timezone.now().date()
    current_year = today.year
    current_month = today.month

    # Transactions Base Queryset
    user_txs = Transaction.objects.filter(user=user)

    # All-time aggregates
    total_income_all = user_txs.filter(type='INCOME').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expense_all = user_txs.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_balance = total_income_all - total_expense_all

    # Current month aggregates
    month_txs = user_txs.filter(date__year=current_year, date__month=current_month)
    month_income = month_txs.filter(type='INCOME').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    month_expense = month_txs.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    month_savings = month_income - month_expense

    savings_percentage = 0.0
    if month_income > Decimal('0.00'):
        savings_percentage = round(float((month_savings / month_income) * Decimal('100.0')), 1)

    # Monthly comparison with previous month
    prev_date = today.replace(day=1) - relativedelta(days=1)
    prev_month_txs = user_txs.filter(date__year=prev_date.year, date__month=prev_date.month)
    prev_month_expense = prev_month_txs.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    prev_month_income = prev_month_txs.filter(type='INCOME').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    expense_growth_pct = 0.0
    if prev_month_expense > Decimal('0.00'):
        diff = month_expense - prev_month_expense
        expense_growth_pct = round(float((diff / prev_month_expense) * Decimal('100.0')), 1)

    income_growth_pct = 0.0
    if prev_month_income > Decimal('0.00'):
        diff = month_income - prev_month_income
        income_growth_pct = round(float((diff / prev_month_income) * Decimal('100.0')), 1)

    # Recent Transactions (last 7)
    recent_transactions = user_txs.select_related('category')[:7]

    # Category breakdown for current month
    category_expenses = (
        month_txs.filter(type='EXPENSE')
        .values('category__name', 'category__color', 'category__icon')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    # Overall Monthly Budget Check
    overall_budget = Budget.objects.filter(
        user=user, category__isnull=True, month=current_month, year=current_year
    ).first()

    budget_stats = None
    if overall_budget:
        budget_spent = overall_budget.get_spent_amount()
        budget_pct = overall_budget.get_percentage()
        budget_rem = overall_budget.get_remaining()
        budget_stats = {
            'target': overall_budget.amount,
            'spent': budget_spent,
            'percentage': budget_pct,
            'remaining': budget_rem,
            'is_warning': overall_budget.is_warning(),
            'is_exceeded': overall_budget.is_exceeded(),
        }

    # Category budgets status
    category_budgets = Budget.objects.filter(
        user=user, category__isnull=False, month=current_month, year=current_year
    ).select_related('category')[:4]

    # Active savings goals
    active_goals = SavingsGoal.objects.filter(user=user, status='IN_PROGRESS')[:4]

    # Upcoming recurring transactions
    upcoming_recurring = RecurringTransaction.objects.filter(
        user=user, is_active=True, next_due_date__gte=today
    ).select_related('category')[:3]

    # Financial Health Index
    health_index = compute_financial_health_score(user, current_year, current_month)

    # Recurring due in next 7 days
    next_week = today + datetime.timedelta(days=7)
    recurring_next_7_days = RecurringTransaction.objects.filter(
        user=user, is_active=True, next_due_date__gte=today, next_due_date__lte=next_week
    )
    recurring_week_count = recurring_next_7_days.count()
    recurring_week_sum = recurring_next_7_days.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    # Projected monthly burn at current rate
    day_count = max(today.day, 1)
    projected_burn = round((month_expense / Decimal(day_count)) * Decimal('30'), 2)

    # Quick Transaction Form for Modal
    tx_form = TransactionForm(user=user)

    context = {
        'total_balance': total_balance,
        'total_income_all': total_income_all,
        'total_expense_all': total_expense_all,
        'month_income': month_income,
        'month_expense': month_expense,
        'month_savings': month_savings,
        'savings_percentage': savings_percentage,
        'expense_growth_pct': expense_growth_pct,
        'income_growth_pct': income_growth_pct,
        'recent_transactions': recent_transactions,
        'category_expenses': list(category_expenses),
        'budget_stats': budget_stats,
        'category_budgets': category_budgets,
        'active_goals': active_goals,
        'upcoming_recurring': upcoming_recurring,
        'health_index': health_index,
        'recurring_week_count': recurring_week_count,
        'recurring_week_sum': recurring_week_sum,
        'projected_burn': projected_burn,
        'tx_form': tx_form,
        'current_month_name': today.strftime('%B %Y'),
    }
    return render(request, 'tracker/dashboard.html', context)


# ==============================================================================
# EXPENSE & INCOME CRUD AND TRANSACTIONS
# ==============================================================================

@login_required
def transactions_list_view(request):
    user = request.user
    tx_qs = Transaction.objects.filter(user=user).select_related('category')

    # Search query
    q = request.GET.get('q', '').strip()
    if q:
        tx_qs = tx_qs.filter(
            Q(title__icontains=q) |
            Q(notes__icontains=q) |
            Q(category__name__icontains=q)
        )

    # Filter by Type (Expense / Income)
    tx_type = request.GET.get('type', '').strip()
    if tx_type in ['EXPENSE', 'INCOME']:
        tx_qs = tx_qs.filter(type=tx_type)

    # Filter by Category
    category_id = request.GET.get('category', '').strip()
    if category_id:
        tx_qs = tx_qs.filter(category_id=category_id)

    # Filter by Payment Method
    payment_method = request.GET.get('payment_method', '').strip()
    if payment_method:
        tx_qs = tx_qs.filter(payment_method=payment_method)

    # Filter by Date Range
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    date_preset = request.GET.get('preset', '').strip()

    today = timezone.now().date()
    if date_preset == 'this_month':
        tx_qs = tx_qs.filter(date__year=today.year, date__month=today.month)
    elif date_preset == 'last_month':
        lm = today.replace(day=1) - relativedelta(days=1)
        tx_qs = tx_qs.filter(date__year=lm.year, date__month=lm.month)
    elif date_preset == 'this_year':
        tx_qs = tx_qs.filter(date__year=today.year)
    else:
        if start_date:
            tx_qs = tx_qs.filter(date__gte=start_date)
        if end_date:
            tx_qs = tx_qs.filter(date__lte=end_date)

    # Filter by Amount Range
    min_amount = request.GET.get('min_amount', '').strip()
    max_amount = request.GET.get('max_amount', '').strip()
    if min_amount:
        try:
            tx_qs = tx_qs.filter(amount__gte=Decimal(min_amount))
        except Exception:
            pass
    if max_amount:
        try:
            tx_qs = tx_qs.filter(amount__lte=Decimal(max_amount))
        except Exception:
            pass

    # Sort options
    sort_by = request.GET.get('sort', '-date')
    valid_sorts = {
        'date_desc': '-date',
        'date_asc': 'date',
        'amount_desc': '-amount',
        'amount_asc': 'amount',
        'title_asc': 'title',
    }
    order_field = valid_sorts.get(sort_by, '-date')
    tx_qs = tx_qs.order_by(order_field, '-created_at')

    # Aggregates for the current filtered list
    filtered_income = tx_qs.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    filtered_expense = tx_qs.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    filtered_net = filtered_income - filtered_expense

    # Pagination
    paginator = Paginator(tx_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.filter(Q(user=user) | Q(user__isnull=True)).order_by('type', 'name')
    tx_form = TransactionForm(user=user)

    context = {
        'page_obj': page_obj,
        'categories': categories,
        'payment_methods': Transaction.PAYMENT_METHOD_CHOICES,
        'filtered_income': filtered_income,
        'filtered_expense': filtered_expense,
        'filtered_net': filtered_net,
        'q': q,
        'tx_type': tx_type,
        'selected_category': category_id,
        'selected_payment_method': payment_method,
        'start_date': start_date,
        'end_date': end_date,
        'min_amount': min_amount,
        'max_amount': max_amount,
        'date_preset': date_preset,
        'sort_by': sort_by,
        'tx_form': tx_form,
        'csv_import_form': CSVImportForm(),
    }
    return render(request, 'tracker/transactions.html', context)


@login_required
def expenses_list_view(request):
    """Dedicated expenses view with category breakdowns and summaries."""
    user = request.user
    today = timezone.now().date()
    month_txs = Transaction.objects.filter(
        user=user, type='EXPENSE', date__year=today.year, date__month=today.month
    )
    month_expense = month_txs.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    # Top spending categories this month
    cat_breakdown = (
        month_txs.values('category__name', 'category__color', 'category__icon')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )

    # Highest single expense this month
    highest_expense = month_txs.order_by('-amount').first()

    # Reuse transactions view query logic for expenses
    request_copy = request.GET.copy()
    request_copy['type'] = 'EXPENSE'
    request.GET = request_copy

    tx_qs = Transaction.objects.filter(user=user, type='EXPENSE').select_related('category')
    q = request.GET.get('q', '').strip()
    if q:
        tx_qs = tx_qs.filter(Q(title__icontains=q) | Q(notes__icontains=q))

    cat_id = request.GET.get('category', '').strip()
    if cat_id:
        tx_qs = tx_qs.filter(category_id=cat_id)

    paginator = Paginator(tx_qs.order_by('-date', '-created_at'), 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = Category.objects.filter(
        (Q(user=user) | Q(user__isnull=True)) & Q(type='EXPENSE')
    ).order_by('name')

    tx_form = TransactionForm(user=user, initial={'type': 'EXPENSE'})

    context = {
        'page_obj': page_obj,
        'month_expense': month_expense,
        'cat_breakdown': cat_breakdown,
        'highest_expense': highest_expense,
        'categories': categories,
        'payment_methods': Transaction.PAYMENT_METHOD_CHOICES,
        'tx_form': tx_form,
        'current_month_name': today.strftime('%B %Y'),
    }
    return render(request, 'tracker/expenses.html', context)


@login_required
def income_list_view(request):
    """Dedicated income management view with salary and freelance tracking."""
    user = request.user
    today = timezone.now().date()
    month_txs = Transaction.objects.filter(
        user=user, type='INCOME', date__year=today.year, date__month=today.month
    )
    month_income = month_txs.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    # Category breakdown for income
    cat_breakdown = (
        month_txs.values('category__name', 'category__color', 'category__icon')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )

    tx_qs = Transaction.objects.filter(user=user, type='INCOME').select_related('category')
    q = request.GET.get('q', '').strip()
    if q:
        tx_qs = tx_qs.filter(Q(title__icontains=q) | Q(notes__icontains=q))

    cat_id = request.GET.get('category', '').strip()
    if cat_id:
        tx_qs = tx_qs.filter(category_id=cat_id)

    paginator = Paginator(tx_qs.order_by('-date', '-created_at'), 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = Category.objects.filter(
        (Q(user=user) | Q(user__isnull=True)) & Q(type='INCOME')
    ).order_by('name')

    tx_form = TransactionForm(user=user, initial={'type': 'INCOME'})

    context = {
        'page_obj': page_obj,
        'month_income': month_income,
        'cat_breakdown': cat_breakdown,
        'categories': categories,
        'payment_methods': Transaction.PAYMENT_METHOD_CHOICES,
        'tx_form': tx_form,
        'current_month_name': today.strftime('%B %Y'),
    }
    return render(request, 'tracker/income.html', context)


@login_required
def transaction_create_view(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            tx = form.save(commit=False)
            tx.user = request.user
            tx.save()

            # Automatic budget warning notification check if expense
            if tx.type == 'EXPENSE':
                month = tx.date.month
                year = tx.date.year
                # Check category budget
                if tx.category:
                    cat_budget = Budget.objects.filter(user=request.user, category=tx.category, month=month, year=year).first()
                    if cat_budget and cat_budget.is_exceeded():
                        Notification.objects.create(
                            user=request.user,
                            title=f"⚠️ Budget Exceeded: {tx.category.name}",
                            message=f"You have spent {cat_budget.get_percentage()}% of your {tx.category.name} budget for this month.",
                            type="DANGER",
                            link="/budgets/"
                        )
                    elif cat_budget and cat_budget.is_warning():
                        Notification.objects.create(
                            user=request.user,
                            title=f"Caution: {tx.category.name} Budget at {cat_budget.get_percentage()}%",
                            message=f"You have reached 80% or more of your {tx.category.name} budget.",
                            type="WARNING",
                            link="/budgets/"
                        )

                # Check overall budget
                overall_budget = Budget.objects.filter(user=request.user, category__isnull=True, month=month, year=year).first()
                if overall_budget and overall_budget.is_exceeded():
                    Notification.objects.create(
                        user=request.user,
                        title="🚨 Overall Monthly Budget Exceeded!",
                        message=f"Your total monthly expenses have surpassed your set limit.",
                        type="DANGER",
                        link="/budgets/"
                    )

            messages.success(request, f"{tx.get_type_display()} '{tx.title}' added successfully.")
            return redirect(request.META.get('HTTP_REFERER', 'transactions'))
        else:
            messages.error(request, "Please correct the form errors.")
            return redirect(request.META.get('HTTP_REFERER', 'transactions'))
    return redirect('transactions')


@login_required
def transaction_update_view(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)

    if request.method == 'POST':
        form = TransactionForm(request.POST, request.FILES, instance=tx, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Transaction '{tx.title}' updated successfully.")
            return redirect('transactions')
        else:
            messages.error(request, "Failed to update transaction.")
    else:
        form = TransactionForm(instance=tx, user=request.user)

    return render(request, 'tracker/transaction_form.html', {'form': form, 'transaction': tx, 'is_edit': True})


@login_required
def transaction_delete_view(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == 'POST':
        title = tx.title
        tx.delete()
        messages.success(request, f"Transaction '{title}' deleted successfully.")
        return redirect(request.META.get('HTTP_REFERER', 'transactions'))
    return render(request, 'tracker/transaction_confirm_delete.html', {'transaction': tx})


# ==============================================================================
# BUDGET MANAGEMENT VIEWS
# ==============================================================================

@login_required
def budgets_view(request):
    user = request.user
    today = timezone.now().date()

    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))

    budgets = Budget.objects.filter(user=user, month=month, year=year).select_related('category')
    overall_budget = budgets.filter(category__isnull=True).first()
    category_budgets = budgets.filter(category__isnull=False)

    budget_form = BudgetForm(user=user, initial={'month': month, 'year': year})

    # Available months/years for filter
    month_names = [(i, datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)]

    # 6-Month Budget Adherence History
    budget_history = []
    for i in range(1, 7):
        hist_date = today.replace(day=1) - relativedelta(months=i)
        hist_budgets = Budget.objects.filter(user=user, month=hist_date.month, year=hist_date.year)
        hist_overall = hist_budgets.filter(category__isnull=True).first()
        hist_spent = Transaction.objects.filter(
            user=user, type='EXPENSE', date__year=hist_date.year, date__month=hist_date.month
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

        allocated = hist_overall.amount if hist_overall else (hist_budgets.aggregate(t=Sum('amount'))['t'] or Decimal('0.00'))
        pct = (hist_spent / allocated * 100) if allocated > 0 else 0
        variance = allocated - hist_spent
        budget_history.append({
            'month_name': hist_date.strftime('%B'),
            'year': hist_date.year,
            'budget_cap': allocated,
            'allocated': allocated,
            'total_spent': hist_spent,
            'spent': hist_spent,
            'pct': round(float(pct), 1),
            'percentage': round(float(pct), 1),
            'is_exceeded': pct >= 100,
            'has_budget': allocated > 0,
            'savings': variance if variance > 0 else Decimal('0.00'),
            'overspent': abs(variance) if variance < 0 else Decimal('0.00'),
        })

    context = {
        'budgets': budgets,
        'overall_budget': overall_budget,
        'category_budgets': category_budgets,
        'budget_form': budget_form,
        'budget_history': budget_history,
        'selected_month': month,
        'selected_year': year,
        'selected_month_name': datetime.date(2000, month, 1).strftime('%B'),
        'month_names': month_names,
        'year_range': [year - 1, year, year + 1],
    }
    return render(request, 'tracker/budgets.html', context)


@login_required
def budget_create_view(request):
    if request.method == 'POST':
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            category = form.cleaned_data.get('category')
            month = form.cleaned_data.get('month')
            year = form.cleaned_data.get('year')
            amount = form.cleaned_data.get('amount')

            # Update existing or create new
            budget, created = Budget.objects.update_or_create(
                user=request.user,
                category=category,
                month=month,
                year=year,
                defaults={'amount': amount}
            )
            action_text = "created" if created else "updated"
            messages.success(request, f"Budget for {category.name if category else 'Overall Month'} {action_text} successfully.")
        else:
            messages.error(request, "Failed to save budget. Please check inputs.")
    return redirect('budgets')


@login_required
def budget_delete_view(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        cat_name = budget.category.name if budget.category else "Overall Monthly Budget"
        budget.delete()
        messages.success(request, f"Budget '{cat_name}' removed.")
    return redirect('budgets')


@login_required
def budget_reset_view(request):
    """Clones budgets from the previous month to the current month."""
    if request.method == 'POST':
        today = timezone.now().date()
        current_month = today.month
        current_year = today.year

        prev_date = today.replace(day=1) - relativedelta(days=1)
        prev_budgets = Budget.objects.filter(user=request.user, month=prev_date.month, year=prev_date.year)

        copied_count = 0
        for b in prev_budgets:
            _, created = Budget.objects.get_or_create(
                user=request.user,
                category=b.category,
                month=current_month,
                year=current_year,
                defaults={'amount': b.amount}
            )
            if created:
                copied_count += 1

        if copied_count > 0:
            messages.success(request, f"Successfully cloned {copied_count} budget(s) from last month.")
        else:
            messages.info(request, "No previous budgets to clone, or current month budgets are already present.")
    return redirect('budgets')


# ==============================================================================
# SAVINGS GOALS VIEWS
# ==============================================================================

@login_required
def savings_goals_view(request):
    user = request.user
    goals = SavingsGoal.objects.filter(user=user)

    total_target = goals.aggregate(t=Sum('target_amount'))['t'] or Decimal('0.00')
    total_saved = goals.aggregate(t=Sum('current_amount'))['t'] or Decimal('0.00')
    overall_progress = 0.0
    if total_target > Decimal('0.00'):
        overall_progress = min(round(float((total_saved / total_target) * Decimal('100.0')), 1), 100.0)

    goal_form = SavingsGoalForm()
    contribution_form = SavingsContributionForm()

    context = {
        'goals': goals,
        'total_target': total_target,
        'total_saved': total_saved,
        'overall_progress': overall_progress,
        'goal_form': goal_form,
        'contribution_form': contribution_form,
    }
    return render(request, 'tracker/goals.html', context)


@login_required
def savings_goal_create_view(request):
    if request.method == 'POST':
        form = SavingsGoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, f"Savings Goal '{goal.title}' created!")
        else:
            messages.error(request, "Failed to create savings goal. Please review fields.")
    return redirect('goals')


@login_required
def savings_goal_update_view(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = SavingsGoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            messages.success(request, f"Savings goal '{goal.title}' updated.")
            return redirect('goals')
    else:
        form = SavingsGoalForm(instance=goal)
    return render(request, 'tracker/goal_form.html', {'form': form, 'goal': goal})


@login_required
def savings_goal_delete_view(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        title = goal.title
        goal.delete()
        messages.success(request, f"Goal '{title}' deleted.")
    return redirect('goals')


@login_required
def savings_goal_contribute_view(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = SavingsContributionForm(request.POST)
        if form.is_valid():
            add_amount = form.cleaned_data['amount']
            goal.current_amount += add_amount

            # Check completion
            if goal.current_amount >= goal.target_amount:
                goal.status = 'COMPLETED'
                Notification.objects.create(
                    user=request.user,
                    title=f"🎉 Goal Achieved: {goal.title}!",
                    message=f"Congratulations! You reached your savings target of {goal.target_amount}.",
                    type="SUCCESS",
                    link="/goals/"
                )
            goal.save()
            messages.success(request, f"Added {add_amount} to '{goal.title}'. Keep it up!")
        else:
            messages.error(request, "Invalid contribution amount.")
    return redirect('goals')


# ==============================================================================
# RECURRING EXPENSES & SUBSCRIPTIONS
# ==============================================================================

@login_required
def recurring_transactions_view(request):
    user = request.user
    recurring_list = RecurringTransaction.objects.filter(user=user).select_related('category')
    total_monthly_committed = Decimal('0.00')

    for item in recurring_list:
        if item.is_active:
            if item.frequency == 'DAILY':
                total_monthly_committed += (item.amount * Decimal('30'))
            elif item.frequency == 'WEEKLY':
                total_monthly_committed += (item.amount * Decimal('4'))
            elif item.frequency == 'MONTHLY':
                total_monthly_committed += item.amount
            elif item.frequency == 'YEARLY':
                total_monthly_committed += (item.amount / Decimal('12'))

    form = RecurringTransactionForm(user=user)

    context = {
        'recurring_list': recurring_list,
        'total_monthly_committed': total_monthly_committed,
        'form': form,
    }
    return render(request, 'tracker/recurring.html', context)


@login_required
def recurring_create_view(request):
    if request.method == 'POST':
        form = RecurringTransactionForm(request.POST, user=request.user)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            messages.success(request, f"Recurring transaction '{item.title}' scheduled.")
        else:
            messages.error(request, "Error creating recurring item.")
    return redirect('recurring')


@login_required
def recurring_toggle_view(request, pk):
    item = get_object_or_404(RecurringTransaction, pk=pk, user=request.user)
    item.is_active = not item.is_active
    item.save()
    status_str = "activated" if item.is_active else "paused"
    messages.success(request, f"Recurring transaction '{item.title}' is now {status_str}.")
    return redirect('recurring')


@login_required
def recurring_delete_view(request, pk):
    item = get_object_or_404(RecurringTransaction, pk=pk, user=request.user)
    if request.method == 'POST':
        title = item.title
        item.delete()
        messages.success(request, f"Recurring schedule '{title}' removed.")
    return redirect('recurring')


@login_required
def process_recurring_view(request):
    """Processes recurring transactions due up to today and logs actual transactions."""
    if request.method == 'POST':
        today = timezone.now().date()
        due_items = RecurringTransaction.objects.filter(
            user=request.user, is_active=True, next_due_date__lte=today
        )
        processed_count = 0

        for item in due_items:
            Transaction.objects.create(
                user=request.user,
                category=item.category,
                type=item.type,
                title=f"{item.title} (Recurring)",
                amount=item.amount,
                date=item.next_due_date,
                payment_method=item.payment_method,
                notes=f"Auto-generated recurring payment. Scheduled start: {item.start_date}",
                is_recurring_instance=True,
            )
            # Advance next_due_date
            if item.frequency == 'DAILY':
                item.next_due_date += datetime.timedelta(days=1)
            elif item.frequency == 'WEEKLY':
                item.next_due_date += datetime.timedelta(weeks=1)
            elif item.frequency == 'MONTHLY':
                item.next_due_date += relativedelta(months=1)
            elif item.frequency == 'YEARLY':
                item.next_due_date += relativedelta(years=1)
            item.save()
            processed_count += 1

        if processed_count > 0:
            messages.success(request, f"Successfully processed {processed_count} recurring transaction(s).")
        else:
            messages.info(request, "No pending recurring transactions are due today.")
    return redirect('recurring')


# ==============================================================================
# ANALYTICS & CHARTS DATA API
# ==============================================================================

@login_required
def analytics_view(request):
    """Deep-dive financial analytics dashboard."""
    user = request.user
    today = timezone.now().date()

    # Yearly aggregate
    year_txs = Transaction.objects.filter(user=user, date__year=today.year)
    year_income = year_txs.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    year_expense = year_txs.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    year_savings = year_income - year_expense
    savings_rate = 0.0
    if year_income > Decimal('0.00'):
        savings_rate = round(float((year_savings / year_income) * Decimal('100.0')), 1)

    # Top 5 highest expenses this year
    top_expenses = year_txs.filter(type='EXPENSE').select_related('category').order_by('-amount')[:5]

    # Highest spending category this year
    highest_spending_category = (
        year_txs.filter(type='EXPENSE', category__isnull=False)
        .values('category__name', 'category__color', 'category__icon')
        .annotate(total=Sum('amount'))
        .order_by('-total')
        .first()
    )
    highest_cat_pct = 0.0
    if highest_spending_category and year_expense > Decimal('0.00'):
        highest_cat_pct = round(float((highest_spending_category['total'] / year_expense) * Decimal('100.0')), 1)

    # Current month budget utilization
    curr_overall_budget = Budget.objects.filter(user=user, category__isnull=True, month=today.month, year=today.year).first()
    curr_cat_budgets = Budget.objects.filter(user=user, category__isnull=False, month=today.month, year=today.year)
    
    total_budgeted = Decimal('0.00')
    if curr_overall_budget:
        total_budgeted = curr_overall_budget.amount
    elif curr_cat_budgets.exists():
        total_budgeted = curr_cat_budgets.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    month_txs = Transaction.objects.filter(user=user, type='EXPENSE', date__year=today.year, date__month=today.month)
    month_spent = month_txs.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    budget_utilization_pct = 0.0
    if total_budgeted > Decimal('0.00'):
        budget_utilization_pct = round(float((month_spent / total_budgeted) * Decimal('100.0')), 1)

    # Daily Average Spend
    day_of_month = max(today.day, 1)
    daily_avg_spend = round(month_spent / Decimal(day_of_month), 2)

    # Spending patterns: peak day of week
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_totals = {i: Decimal('0.00') for i in range(7)}
    for tx in year_txs.filter(type='EXPENSE'):
        weekday_totals[tx.date.weekday()] += tx.amount
    peak_weekday_idx = max(weekday_totals, key=weekday_totals.get) if any(weekday_totals.values()) else None
    peak_spending_day = day_names[peak_weekday_idx] if peak_weekday_idx is not None and weekday_totals[peak_weekday_idx] > 0 else "N/A"

    # Payment method breakdown
    payment_stats = (
        year_txs.filter(type='EXPENSE')
        .values('payment_method')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )

    context = {
        'year_income': year_income,
        'year_expense': year_expense,
        'year_savings': year_savings,
        'savings_rate': savings_rate,
        'top_expenses': top_expenses,
        'highest_spending_category': highest_spending_category,
        'highest_cat_pct': highest_cat_pct,
        'budget_utilization_pct': budget_utilization_pct,
        'total_budgeted': total_budgeted,
        'daily_avg_spend': daily_avg_spend,
        'peak_spending_day': peak_spending_day,
        'payment_stats': payment_stats,
        'current_year': today.year,
    }
    return render(request, 'tracker/analytics.html', context)


@login_required
def calculators_view(request):
    """Interactive personal finance toolkit: Loan EMI, Wealth SIP, and Bill Splitter."""
    user = request.user
    today = timezone.now().date()
    user_txs = Transaction.objects.filter(user=user)

    total_income_all = user_txs.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    total_expense_all = user_txs.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    total_balance = total_income_all - total_expense_all

    # 6-Month rolling average monthly expense for runway calculation
    six_months_ago = today - relativedelta(months=6)
    recent_expenses = user_txs.filter(type='EXPENSE', date__gte=six_months_ago)
    recent_expense_sum = recent_expenses.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    avg_monthly_expense = round(recent_expense_sum / Decimal('6'), 2)

    runway_months = 0.0
    if avg_monthly_expense > Decimal('0.00') and total_balance > Decimal('0.00'):
        runway_months = round(float(total_balance / avg_monthly_expense), 1)

    context = {
        'total_balance': total_balance,
        'avg_monthly_expense': avg_monthly_expense,
        'runway_months': runway_months,
    }
    return render(request, 'tracker/calculators.html', context)


@login_required
def reports_view(request):
    """Monthly financial statements and export hub."""
    user = request.user
    today = timezone.now().date()
    months_list = []

    for i in range(12):
        d = today.replace(day=1) - relativedelta(months=i)
        txs = Transaction.objects.filter(user=user, date__year=d.year, date__month=d.month)
        inc = txs.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        exp = txs.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        months_list.append({
            'year': d.year,
            'month': d.month,
            'month_name': d.strftime('%B %Y'),
            'income': inc,
            'expense': exp,
            'savings': inc - exp,
            'count': txs.count(),
        })

    return render(request, 'tracker/reports.html', {'months_list': months_list})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chart_data_api(request):
    """Returns dynamic data for Chart.js interactive charts."""
    user = request.user
    today = timezone.now().date()

    # 1. Last 6 Months Income vs Expenses Trend
    months_labels = []
    income_data = []
    expense_data = []

    for i in range(5, -1, -1):
        target_date = today.replace(day=1) - relativedelta(months=i)
        label = target_date.strftime('%b %Y')
        months_labels.append(label)

        m_txs = Transaction.objects.filter(user=user, date__year=target_date.year, date__month=target_date.month)
        inc = m_txs.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        exp = m_txs.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

        income_data.append(float(inc))
        expense_data.append(float(exp))

    # 2. Category-wise Expenses Breakdown (Current Month)
    current_month_txs = Transaction.objects.filter(
        user=user, type='EXPENSE', date__year=today.year, date__month=today.month
    )
    cat_agg = (
        current_month_txs.values('category__name', 'category__color')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    category_labels = []
    category_totals = []
    category_colors = []

    for c in cat_agg:
        c_name = c['category__name'] or 'Uncategorized'
        category_labels.append(c_name)
        category_totals.append(float(c['total']))
        category_colors.append(c['category__color'] or '#3B82F6')

    # 3. Weekly spending for current month (4 weeks)
    weekly_labels = ['Week 1', 'Week 2', 'Week 3', 'Week 4']
    weekly_spending = [0.0, 0.0, 0.0, 0.0]

    for tx in current_month_txs:
        day = tx.date.day
        if day <= 7:
            weekly_spending[0] += float(tx.amount)
        elif day <= 14:
            weekly_spending[1] += float(tx.amount)
        elif day <= 21:
            weekly_spending[2] += float(tx.amount)
        else:
            weekly_spending[3] += float(tx.amount)

    return Response({
        'monthly_trend': {
            'labels': months_labels,
            'income': income_data,
            'expenses': expense_data,
        },
        'category_breakdown': {
            'labels': category_labels,
            'totals': category_totals,
            'colors': category_colors,
        },
        'weekly_spending': {
            'labels': weekly_labels,
            'data': weekly_spending,
        },
        'savings_trend': {
            'labels': months_labels,
            'savings': [round(inc - exp, 2) for inc, exp in zip(income_data, expense_data)],
            'savings_rate': [round(((inc - exp) / inc * 100), 1) if inc > 0 else 0.0 for inc, exp in zip(income_data, expense_data)],
        }
    })


# ==============================================================================
# EXPORT AND REPORTING (CSV & PDF)
# ==============================================================================

@login_required
def export_csv_view(request):
    """Exports transactions to CSV with all current filters applied."""
    user = request.user
    tx_qs = Transaction.objects.filter(user=user).select_related('category')

    # Apply search and filters
    q = request.GET.get('q', '').strip()
    if q:
        tx_qs = tx_qs.filter(Q(title__icontains=q) | Q(notes__icontains=q))

    tx_type = request.GET.get('type', '').strip()
    if tx_type in ['EXPENSE', 'INCOME']:
        tx_qs = tx_qs.filter(type=tx_type)

    cat_id = request.GET.get('category', '').strip()
    if cat_id:
        tx_qs = tx_qs.filter(category_id=cat_id)

    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    if start_date:
        tx_qs = tx_qs.filter(date__gte=start_date)
    if end_date:
        tx_qs = tx_qs.filter(date__lte=end_date)

    tx_qs = tx_qs.order_by('-date', '-created_at')

    response = HttpResponse(content_type='text/csv')
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="FINORA_Transactions_{timestamp}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Date', 'Time', 'Type', 'Title', 'Category', 'Amount',
        'Currency', 'Payment Method', 'Notes', 'Recurring Instance'
    ])

    currency = user.profile.currency if hasattr(user, 'profile') else 'INR'
    for tx in tx_qs:
        writer.writerow([
            tx.id,
            tx.date.strftime('%Y-%m-%d'),
            tx.time.strftime('%H:%M:%S') if tx.time else '',
            tx.get_type_display(),
            tx.title,
            tx.category.name if tx.category else 'Uncategorized',
            f"{tx.amount:.2f}",
            currency,
            tx.get_payment_method_display(),
            tx.notes,
            'Yes' if tx.is_recurring_instance else 'No'
        ])

    return response


@login_required
def download_pdf_report_view(request, year, month):
    """Generates a professional financial statement in PDF format using reportlab."""
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    sym = profile.get_currency_symbol()

    tx_qs = Transaction.objects.filter(
        user=user, date__year=year, date__month=month
    ).select_related('category').order_by('date')

    income_total = tx_qs.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    expense_total = tx_qs.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    net_savings = income_total - expense_total
    savings_pct = (net_savings / income_total * 100) if income_total > 0 else 0

    month_name = datetime.date(year, month, 1).strftime('%B %Y')

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=14
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=12,
        spaceAfter=8
    )

    elements = []

    # Header
    elements.append(Paragraph("FINORA &bull; FINANCIAL STATEMENT", title_style))
    elements.append(Paragraph(
        f"Account Holder: <b>{user.get_full_name() or user.username}</b> &nbsp;|&nbsp; "
        f"Period: <b>{month_name}</b> &nbsp;|&nbsp; Generated on: {timezone.now().strftime('%d %b %Y, %H:%M')}",
        subtitle_style
    ))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#3B82F6'), spaceAfter=14))

    # Summary KPI Table
    summary_data = [
        ['Total Income', 'Total Expenses', 'Net Savings', 'Savings Rate'],
        [
            f"{sym}{income_total:,.2f}",
            f"{sym}{expense_total:,.2f}",
            f"{sym}{net_savings:,.2f}",
            f"{savings_pct:.1f}%"
        ]
    ]
    summary_table = Table(summary_data, colWidths=[135, 135, 135, 135])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#334155')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TEXTCOLOR', (0, 1), (0, 1), colors.HexColor('#10B981')),
        ('TEXTCOLOR', (1, 1), (1, 1), colors.HexColor('#EF4444')),
        ('TEXTCOLOR', (2, 1), (2, 1), colors.HexColor('#3B82F6')),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 11),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 18))

    # Transactions Table
    elements.append(Paragraph("Itemized Transactions", section_style))

    table_data = [['Date', 'Type', 'Title', 'Category', 'Method', 'Amount']]
    for tx in tx_qs:
        sign = "+" if tx.type == 'INCOME' else "-"
        date_str = tx.date.strftime('%d-%b-%Y')
        if tx.time:
            date_str += f"\n{tx.time.strftime('%H:%M')}"
        table_data.append([
            date_str,
            tx.get_type_display(),
            Paragraph(tx.title, styles['Normal']),
            tx.category.name if tx.category else 'General',
            tx.get_payment_method_display(),
            f"{sign} {sym}{tx.amount:,.2f}"
        ])

    if len(table_data) == 1:
        table_data.append(['No transactions recorded for this billing cycle.', '', '', '', '', ''])

    tx_table = Table(table_data, colWidths=[70, 60, 170, 95, 75, 70])
    tx_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (5, 0), (5, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(tx_table)

    # Footer note
    elements.append(Spacer(1, 24))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=8))
    elements.append(Paragraph(
        "Generated via FINORA Personal Financial Operating System &bull; Confidential &amp; Verified",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#94A3B8'), alignment=1)
    ))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="FINORA_Statement_{year}_{month:02d}.pdf"'
    return response


# ==============================================================================
# NOTIFICATIONS VIEWS
# ==============================================================================

@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user)
    unread_count = notifications.filter(is_read=False).count()
    return render(request, 'tracker/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })


@login_required
def mark_notification_read_view(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    return redirect(request.META.get('HTTP_REFERER', 'notifications'))


@login_required
def mark_all_notifications_read_view(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect(request.META.get('HTTP_REFERER', 'notifications'))


# ==============================================================================
# CSV IMPORT & DATA BACKUP / RESTORE
# ==============================================================================

@login_required
def import_csv_view(request):
    """Imports transactions from a user-uploaded CSV file."""
    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            try:
                # Read content safely
                file_data = csv_file.read()
                try:
                    decoded_file = file_data.decode('utf-8')
                except UnicodeDecodeError:
                    decoded_file = file_data.decode('latin-1')

                io_string = StringIO(decoded_file)
                reader = csv.reader(io_string)

                headers = [h.strip().lower() for h in next(reader, [])]
                if not headers:
                    messages.error(request, "The uploaded CSV file is empty.")
                    return redirect('transactions')

                # Column mapping lookup
                col_date = next((i for i, h in enumerate(headers) if 'date' in h), None)
                col_time = next((i for i, h in enumerate(headers) if 'time' in h), None)
                col_title = next((i for i, h in enumerate(headers) if 'title' in h or 'desc' in h or 'name' in h), None)
                col_amount = next((i for i, h in enumerate(headers) if 'amount' in h or 'total' in h), None)
                col_type = next((i for i, h in enumerate(headers) if 'type' in h), None)
                col_cat = next((i for i, h in enumerate(headers) if 'category' in h), None)
                col_method = next((i for i, h in enumerate(headers) if 'method' in h or 'pay' in h), None)
                col_notes = next((i for i, h in enumerate(headers) if 'note' in h or 'remark' in h), None)

                if col_title is None or col_amount is None:
                    messages.error(request, "CSV must contain at least 'Title' and 'Amount' columns.")
                    return redirect('transactions')

                imported_count = 0
                skipped_count = 0

                with db_transaction.atomic():
                    for row in reader:
                        if not row or not any(row):
                            continue
                        try:
                            # 1. Parse title
                            title = row[col_title].strip()
                            if not title:
                                skipped_count += 1
                                continue

                            # 2. Parse amount
                            raw_amount = row[col_amount].replace('₹', '').replace('$', '').replace('Rs.', '').replace(',', '').strip()
                            amount = Decimal(raw_amount)
                            if amount <= Decimal('0.00'):
                                skipped_count += 1
                                continue

                            # 3. Parse date & time
                            tx_date = timezone.now().date()
                            if col_date is not None and len(row) > col_date:
                                date_str = row[col_date].strip()
                                for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y', '%d-%b-%Y'):
                                    try:
                                        tx_date = datetime.datetime.strptime(date_str, fmt).date()
                                        break
                                    except ValueError:
                                        pass

                            tx_time = None
                            if col_time is not None and len(row) > col_time:
                                time_str = row[col_time].strip()
                                for t_fmt in ('%H:%M:%S', '%H:%M', '%I:%M %p', '%I:%M:%S %p'):
                                    try:
                                        tx_time = datetime.datetime.strptime(time_str, t_fmt).time()
                                        break
                                    except ValueError:
                                        pass

                            # 4. Parse type
                            tx_type = 'EXPENSE'
                            if col_type is not None and len(row) > col_type:
                                raw_type = row[col_type].strip().upper()
                                if 'INC' in raw_type or 'CREDIT' in raw_type or '+' in raw_type:
                                    tx_type = 'INCOME'

                            # 5. Parse Category
                            category_obj = None
                            if col_cat is not None and len(row) > col_cat:
                                cat_name = row[col_cat].strip()
                                if cat_name:
                                    category_obj = Category.objects.filter(
                                        (Q(user=request.user) | Q(user__isnull=True)),
                                        name__iexact=cat_name,
                                        type=tx_type
                                    ).first()
                                    if not category_obj:
                                        category_obj = Category.objects.create(
                                            user=request.user,
                                            name=cat_name,
                                            type=tx_type,
                                            icon='tag',
                                            color='#3B82F6'
                                        )

                            # 6. Parse Payment Method
                            pm = 'OTHER'
                            if col_method is not None and len(row) > col_method:
                                raw_pm = row[col_method].strip().upper()
                                for val, _ in Transaction.PAYMENT_METHOD_CHOICES:
                                    if val in raw_pm or raw_pm in val:
                                        pm = val
                                        break

                            notes = ''
                            if col_notes is not None and len(row) > col_notes:
                                notes = row[col_notes].strip()

                            Transaction.objects.create(
                                user=request.user,
                                title=title,
                                amount=amount,
                                type=tx_type,
                                date=tx_date,
                                time=tx_time,
                                category=category_obj,
                                payment_method=pm,
                                notes=notes
                            )
                            imported_count += 1
                        except Exception:
                            skipped_count += 1

                messages.success(request, f"Successfully imported {imported_count} transaction(s)! ({skipped_count} invalid/empty rows skipped).")
            except Exception as e:
                messages.error(request, f"Error processing CSV file: {str(e)}")
        else:
            messages.error(request, "Please choose a valid CSV file.")
    return redirect('transactions')


@login_required
def backup_data_view(request):
    """Exports all user financial data as a structured JSON backup archive."""
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    data = {
        'finora_backup_version': '2.0',
        'exported_at': timezone.now().isoformat(),
        'user': {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        },
        'profile': {
            'currency': profile.currency,
            'theme': profile.theme,
            'phone': profile.phone,
            'bio': profile.bio,
            'monthly_income_target': str(profile.monthly_income_target),
            'monthly_savings_target': str(profile.monthly_savings_target),
        },
        'categories': [
            {
                'name': c.name,
                'type': c.type,
                'icon': c.icon,
                'color': c.color,
                'is_default': c.is_default
            } for c in Category.objects.filter(user=user)
        ],
        'transactions': [
            {
                'type': tx.type,
                'title': tx.title,
                'amount': str(tx.amount),
                'date': tx.date.isoformat(),
                'time': tx.time.isoformat() if tx.time else None,
                'category_name': tx.category.name if tx.category else None,
                'payment_method': tx.payment_method,
                'notes': tx.notes,
                'is_recurring_instance': tx.is_recurring_instance,
            } for tx in Transaction.objects.filter(user=user).select_related('category')
        ],
        'budgets': [
            {
                'category_name': b.category.name if b.category else None,
                'month': b.month,
                'year': b.year,
                'amount': str(b.amount),
            } for b in Budget.objects.filter(user=user).select_related('category')
        ],
        'savings_goals': [
            {
                'title': g.title,
                'target_amount': str(g.target_amount),
                'current_amount': str(g.current_amount),
                'target_date': g.target_date.isoformat() if g.target_date else None,
                'status': g.status,
                'color': g.color,
                'notes': g.notes,
            } for g in SavingsGoal.objects.filter(user=user)
        ],
        'recurring_transactions': [
            {
                'title': r.title,
                'category_name': r.category.name if r.category else None,
                'type': r.type,
                'amount': str(r.amount),
                'frequency': r.frequency,
                'payment_method': r.payment_method,
                'start_date': r.start_date.isoformat(),
                'next_due_date': r.next_due_date.isoformat(),
                'is_active': r.is_active,
                'notes': r.notes,
            } for r in RecurringTransaction.objects.filter(user=user).select_related('category')
        ]
    }

    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="FINORA_Backup_{timestamp}.json"'
    return response


@login_required
def restore_data_view(request):
    """Restores user financial data from a verified JSON backup file."""
    if request.method == 'POST':
        form = DataRestoreForm(request.POST, request.FILES)
        if form.is_valid():
            backup_file = request.FILES['backup_file']
            try:
                content = json.loads(backup_file.read().decode('utf-8'))
                if content.get('finora_backup_version') != '2.0':
                    messages.error(request, "Invalid or unsupported backup archive format.")
                    return redirect('profile')

                with db_transaction.atomic():
                    # 1. Restore Profile Preferences
                    profile_data = content.get('profile', {})
                    profile, _ = UserProfile.objects.get_or_create(user=request.user)
                    profile.currency = profile_data.get('currency', profile.currency)
                    profile.theme = profile_data.get('theme', profile.theme)
                    profile.phone = profile_data.get('phone', profile.phone)
                    profile.bio = profile_data.get('bio', profile.bio)
                    if 'monthly_income_target' in profile_data:
                        profile.monthly_income_target = Decimal(profile_data['monthly_income_target'])
                    if 'monthly_savings_target' in profile_data:
                        profile.monthly_savings_target = Decimal(profile_data['monthly_savings_target'])
                    profile.save()

                    # 2. Restore Custom Categories
                    for c_data in content.get('categories', []):
                        Category.objects.get_or_create(
                            user=request.user,
                            name=c_data['name'],
                            type=c_data['type'],
                            defaults={
                                'icon': c_data.get('icon', 'tag'),
                                'color': c_data.get('color', '#3B82F6'),
                                'is_default': False
                            }
                        )

                    # 3. Restore Transactions
                    tx_count = 0
                    for tx_data in content.get('transactions', []):
                        cat_obj = None
                        if tx_data.get('category_name'):
                            cat_obj = Category.objects.filter(
                                (Q(user=request.user) | Q(user__isnull=True)),
                                name__iexact=tx_data['category_name'],
                                type=tx_data['type']
                            ).first()

                        t_time = datetime.time.fromisoformat(tx_data['time']) if tx_data.get('time') else None
                        Transaction.objects.get_or_create(
                            user=request.user,
                            title=tx_data['title'],
                            amount=Decimal(tx_data['amount']),
                            date=datetime.date.fromisoformat(tx_data['date']),
                            type=tx_data['type'],
                            defaults={
                                'time': t_time,
                                'category': cat_obj,
                                'payment_method': tx_data.get('payment_method', 'OTHER'),
                                'notes': tx_data.get('notes', ''),
                                'is_recurring_instance': tx_data.get('is_recurring_instance', False),
                            }
                        )
                        tx_count += 1

                    # 4. Restore Budgets
                    for b_data in content.get('budgets', []):
                        cat_obj = None
                        if b_data.get('category_name'):
                            cat_obj = Category.objects.filter(
                                (Q(user=request.user) | Q(user__isnull=True)),
                                name__iexact=b_data['category_name'],
                                type='EXPENSE'
                            ).first()

                        Budget.objects.update_or_create(
                            user=request.user,
                            category=cat_obj,
                            month=b_data['month'],
                            year=b_data['year'],
                            defaults={'amount': Decimal(b_data['amount'])}
                        )

                    # 5. Restore Goals
                    for g_data in content.get('savings_goals', []):
                        t_date = datetime.date.fromisoformat(g_data['target_date']) if g_data.get('target_date') else None
                        SavingsGoal.objects.get_or_create(
                            user=request.user,
                            title=g_data['title'],
                            defaults={
                                'target_amount': Decimal(g_data['target_amount']),
                                'current_amount': Decimal(g_data['current_amount']),
                                'target_date': t_date,
                                'status': g_data.get('status', 'IN_PROGRESS'),
                                'color': g_data.get('color', '#3B82F6'),
                                'notes': g_data.get('notes', ''),
                            }
                        )

                    Notification.objects.create(
                        user=request.user,
                        title="📥 Data Restored Successfully",
                        message=f"Restored workspace state and {tx_count} transaction record(s).",
                        type="SUCCESS",
                        link="/dashboard/"
                    )

                messages.success(request, f"Data restored successfully! ({tx_count} transactions imported).")
            except Exception as e:
                messages.error(request, f"Error restoring backup: {str(e)}")
        else:
            messages.error(request, "Please upload a valid JSON backup file.")
    return redirect('profile')


# ==============================================================================
# CUSTOM CATEGORY MANAGEMENT
# ==============================================================================

@login_required
def categories_view(request):
    """View and manage custom expense and income categories."""
    user = request.user
    user_cats = Category.objects.filter(user=user).annotate(tx_count=Count('transactions'))
    system_cats = Category.objects.filter(user__isnull=True).annotate(tx_count=Count('transactions'))

    form = CategoryForm()

    context = {
        'user_categories': user_cats,
        'system_categories': system_cats,
        'form': form,
    }
    return render(request, 'tracker/categories.html', context)


@login_required
def category_create_view(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.user = request.user
            cat.is_default = False
            cat.save()
            messages.success(request, f"Category '{cat.name}' created successfully!")
        else:
            messages.error(request, "Failed to create category. A category with this name and type may already exist.")
    return redirect('categories')


@login_required
def category_delete_view(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    if cat.is_default:
        messages.error(request, "Standard system categories cannot be deleted.")
    else:
        name = cat.name
        cat.delete()
        messages.success(request, f"Custom category '{name}' removed.")
    return redirect('categories')


# ==============================================================================
# REST API V1 ENDPOINTS & SYSTEM TELEMETRY
# ==============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def api_health_check(request):
    """System health check probe returning DB connectivity and API version."""
    from django.db import connection
    db_status = "connected"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    return Response({
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": "FINORA Financial Operating System",
        "version": "2.1.0",
        "database": db_status,
        "timestamp": timezone.now().isoformat()
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_transactions_list_create(request):
    """List or create transactions for the authenticated user via REST."""
    user = request.user
    if request.method == 'GET':
        qs = Transaction.objects.filter(user=user).select_related('category')
        tx_type = request.query_params.get('type')
        if tx_type in ['INCOME', 'EXPENSE']:
            qs = qs.filter(type=tx_type)

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(notes__icontains=search))

        limit = request.query_params.get('limit')
        if limit and limit.isdigit():
            qs = qs[:int(limit)]
        else:
            qs = qs[:100]

        serializer = TransactionSerializer(qs, many=True)
        return Response({
            "count": len(serializer.data),
            "results": serializer.data
        })

    elif request.method == 'POST':
        serializer = TransactionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_transaction_detail(request, pk):
    """Retrieve or delete a single transaction owned by the authenticated user."""
    try:
        tx = Transaction.objects.get(pk=pk, user=request.user)
    except Transaction.DoesNotExist:
        return Response({"detail": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = TransactionSerializer(tx)
        return Response(serializer.data)
    elif request.method == 'DELETE':
        tx.delete()
        return Response({"detail": "Transaction deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_categories_list(request):
    """List all categories available to the authenticated user."""
    categories = Category.objects.filter(Q(user=request.user) | Q(user__isnull=True))
    cat_type = request.query_params.get('type')
    if cat_type in ['INCOME', 'EXPENSE']:
        categories = categories.filter(type=cat_type)
    serializer = CategorySerializer(categories, many=True)
    return Response({"results": serializer.data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_budgets_list(request):
    """List budgets for current month for the authenticated user."""
    today = timezone.now().date()
    month = request.query_params.get('month', today.month)
    year = request.query_params.get('year', today.year)
    budgets = Budget.objects.filter(user=request.user, month=month, year=year).select_related('category')
    serializer = BudgetSerializer(budgets, many=True)
    return Response({
        "month": int(month),
        "year": int(year),
        "results": serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_goals_list(request):
    """List all savings goals for the authenticated user."""
    goals = SavingsGoal.objects.filter(user=request.user)
    serializer = SavingsGoalSerializer(goals, many=True)
    return Response({"results": serializer.data})
