import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from tracker.models import (
    UserProfile, Category, Transaction, Budget,
    SavingsGoal, RecurringTransaction, Notification
)

class Command(BaseCommand):
    help = 'Seeds FINORA with rich, realistic INR financial data.'

    def handle(self, *args, **options):
        self.stdout.write("Initializing FINORA dataset with INR currency...")

        user = User.objects.filter(is_active=True).first()
        if not user:
            user = User.objects.create_user(
                username='alex',
                email='alex@finora.io',
                first_name='Alex',
                last_name='Vance',
                is_staff=True,
                is_superuser=True,
            )
            user.set_password('finora123')
            user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.currency = 'INR'
        profile.theme = 'dark'
        profile.monthly_income_target = Decimal('185000.00')
        profile.monthly_savings_target = Decimal('75000.00')
        profile.bio = "Software Engineer & Wealth Builder."
        profile.save()

        # Fetch categories
        cat_map = {c.name: c for c in Category.objects.filter(user=user)}

        today = timezone.now().date()

        # Clear existing transactions to re-seed cleanly in INR
        Transaction.objects.filter(user=user).delete()
        Budget.objects.filter(user=user).delete()
        SavingsGoal.objects.filter(user=user).delete()
        RecurringTransaction.objects.filter(user=user).delete()
        Notification.objects.filter(user=user).delete()

        # Seed 6 months of historical transactions in INR
        for i in range(5, -1, -1):
            m_date = today.replace(day=1) - relativedelta(months=i)
            # Monthly Tech Salary
            Transaction.objects.create(
                user=user,
                category=cat_map.get('Salary'),
                type='INCOME',
                title='Primary Tech Salary',
                amount=Decimal('145000.00'),
                date=m_date.replace(day=1),
                payment_method='BANK_TRANSFER',
                notes='Direct company payroll credit'
            )
            # Monthly Consulting / Freelance
            Transaction.objects.create(
                user=user,
                category=cat_map.get('Freelance'),
                type='INCOME',
                title='Architecture Consulting Retainer',
                amount=Decimal('38500.00'),
                date=m_date.replace(day=15),
                payment_method='UPI',
                notes='Sprint consulting milestone'
            )
            # Rent / Utilities
            Transaction.objects.create(
                user=user,
                category=cat_map.get('Bills & Utilities'),
                type='EXPENSE',
                title='Apartment Lease & Society Maintenance',
                amount=Decimal('34000.00'),
                date=m_date.replace(day=2),
                payment_method='NET_BANKING',
                notes='Monthly rent & building dues'
            )
            # Groceries & Dining
            Transaction.objects.create(
                user=user,
                category=cat_map.get('Food & Dining'),
                type='EXPENSE',
                title='Supermarket & Household Provisions',
                amount=Decimal('9200.00'),
                date=m_date.replace(day=6),
                payment_method='UPI'
            )
            Transaction.objects.create(
                user=user,
                category=cat_map.get('Food & Dining'),
                type='EXPENSE',
                title='Weekend Dinner & Cafe Outing',
                amount=Decimal('3450.00'),
                date=m_date.replace(day=18),
                payment_method='CREDIT_CARD'
            )
            # Shopping & Gadgets
            Transaction.objects.create(
                user=user,
                category=cat_map.get('Shopping'),
                type='EXPENSE',
                title='Desk Setup & Peripherals',
                amount=Decimal('6800.00'),
                date=m_date.replace(day=10),
                payment_method='CREDIT_CARD'
            )
            # Transport
            Transaction.objects.create(
                user=user,
                category=cat_map.get('Transport'),
                type='EXPENSE',
                title='Fuel & Metro Card Recharge',
                amount=Decimal('3600.00'),
                date=m_date.replace(day=22),
                payment_method='UPI'
            )

        # Current Month Real-Time Transactions
        Transaction.objects.create(
            user=user,
            category=cat_map.get('Entertainment'),
            type='EXPENSE',
            title='Concert Tickets & IMAX Movie',
            amount=Decimal('2800.00'),
            date=today,
            payment_method='UPI',
            notes='Weekend entertainment'
        )
        Transaction.objects.create(
            user=user,
            category=cat_map.get('Healthcare'),
            type='EXPENSE',
            title='Annual Health Checkup & Pharmacy',
            amount=Decimal('2450.00'),
            date=today - datetime.timedelta(days=3),
            payment_method='DEBIT_CARD'
        )

        # Budgets in INR for current month
        Budget.objects.create(
            user=user,
            category=None, # Overall
            month=today.month,
            year=today.year,
            amount=Decimal('85000.00')
        )
        if cat_map.get('Food & Dining'):
            Budget.objects.create(
                user=user,
                category=cat_map.get('Food & Dining'),
                month=today.month,
                year=today.year,
                amount=Decimal('18000.00')
            )
        if cat_map.get('Shopping'):
            Budget.objects.create(
                user=user,
                category=cat_map.get('Shopping'),
                month=today.month,
                year=today.year,
                amount=Decimal('15000.00')
            )
        if cat_map.get('Transport'):
            Budget.objects.create(
                user=user,
                category=cat_map.get('Transport'),
                month=today.month,
                year=today.year,
                amount=Decimal('6000.00')
            )

        # Savings Goals in INR
        SavingsGoal.objects.create(
            user=user,
            title='Emergency Liquidity Reserve (6 Months)',
            target_amount=Decimal('500000.00'),
            current_amount=Decimal('345000.00'),
            target_date=today + datetime.timedelta(days=120),
            status='IN_PROGRESS',
            color='#10B981',
            notes='High-yield deposit safety net'
        )
        SavingsGoal.objects.create(
            user=user,
            title='Apple M3 Max MacBook Pro',
            target_amount=Decimal('220000.00'),
            current_amount=Decimal('175000.00'),
            target_date=today + datetime.timedelta(days=45),
            status='IN_PROGRESS',
            color='#3B82F6',
            notes='Hardware upgrade for development'
        )
        SavingsGoal.objects.create(
            user=user,
            title='International Vacation Fund',
            target_amount=Decimal('180000.00'),
            current_amount=Decimal('72000.00'),
            target_date=today + datetime.timedelta(days=210),
            status='IN_PROGRESS',
            color='#8B5CF6',
            notes='Flights, bullet train & hotel stays'
        )

        # Recurring Subscriptions in INR
        RecurringTransaction.objects.create(
            user=user,
            title='AWS Cloud Infrastructure',
            category=cat_map.get('Bills & Utilities'),
            type='EXPENSE',
            amount=Decimal('4200.00'),
            frequency='MONTHLY',
            payment_method='CREDIT_CARD',
            start_date=today - datetime.timedelta(days=90),
            next_due_date=today + datetime.timedelta(days=12),
            is_active=True,
            notes='Cloud servers and dev environments'
        )
        RecurringTransaction.objects.create(
            user=user,
            title='Airtel Xstream Fiber Broadband',
            category=cat_map.get('Bills & Utilities'),
            type='EXPENSE',
            amount=Decimal('1199.00'),
            frequency='MONTHLY',
            payment_method='UPI',
            start_date=today - datetime.timedelta(days=180),
            next_due_date=today + datetime.timedelta(days=5),
            is_active=True
        )
        RecurringTransaction.objects.create(
            user=user,
            title='Spotify Premium Family Plan',
            category=cat_map.get('Entertainment'),
            type='EXPENSE',
            amount=Decimal('179.00'),
            frequency='MONTHLY',
            payment_method='CREDIT_CARD',
            start_date=today - datetime.timedelta(days=150),
            next_due_date=today + datetime.timedelta(days=9),
            is_active=True
        )

        # System Notifications
        Notification.objects.create(
            user=user,
            title="✨ FINORA Configured in INR (₹)",
            message="Your operating system is configured with Indian Rupee (₹) denomination, category budgets, and savings goals.",
            type="SUCCESS",
            link="/dashboard/"
        )
        Notification.objects.create(
            user=user,
            title="💡 Monthly Savings Milestone",
            message="You are currently saving over 50% of your total net inflow this month. Excellent discipline!",
            type="INFO",
            link="/analytics/"
        )

        self.stdout.write(self.style.SUCCESS("INR dataset successfully populated!"))
