from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from decimal import Decimal
from django.utils import timezone
import datetime

from .models import (
    UserProfile, Category, Transaction, Budget,
    SavingsGoal, RecurringTransaction, Notification
)

class FinoraCoreTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@finora.io',
            password='TestPassword123!',
            first_name='Test',
            last_name='User'
        )

    def test_signals_user_profile_and_categories_created(self):
        """Verify UserProfile, default categories, and welcome notification are created on user creation."""
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())
        profile = self.user.profile
        self.assertEqual(profile.currency, 'INR')
        self.assertEqual(profile.get_currency_symbol(), '₹')

        expense_cats = Category.objects.filter(user=self.user, type='EXPENSE')
        self.assertGreater(expense_cats.count(), 5)

        income_cats = Category.objects.filter(user=self.user, type='INCOME')
        self.assertGreater(income_cats.count(), 3)

        notif = Notification.objects.filter(user=self.user).first()
        self.assertIsNotNone(notif)
        self.assertIn("Welcome", notif.title)

    def test_authentication_login_logout(self):
        """Test authentication flow."""
        login_success = self.client.login(username='testuser', password='TestPassword123!')
        self.assertTrue(login_success)

        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)

    def test_transaction_creation_and_balance_calculations(self):
        """Test transaction math with DecimalField precision."""
        self.client.login(username='testuser', password='TestPassword123!')

        cat_salary = Category.objects.filter(user=self.user, type='INCOME', name__icontains='Salary').first()
        cat_food = Category.objects.filter(user=self.user, type='EXPENSE', name__icontains='Food').first()

        # Add Income $5,000.50
        tx_income = Transaction.objects.create(
            user=self.user,
            category=cat_salary,
            type='INCOME',
            title='Monthly Salary',
            amount=Decimal('5000.50'),
            date=timezone.now().date(),
            payment_method='BANK_TRANSFER'
        )

        # Add Expense $1,250.25
        tx_expense = Transaction.objects.create(
            user=self.user,
            category=cat_food,
            type='EXPENSE',
            title='Supermarket Groceries',
            amount=Decimal('1250.25'),
            date=timezone.now().date(),
            payment_method='CREDIT_CARD'
        )

        # Check dashboard context calculations
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_balance'], Decimal('3750.25'))
        self.assertEqual(response.context['month_income'], Decimal('5000.50'))
        self.assertEqual(response.context['month_expense'], Decimal('1250.25'))
        self.assertEqual(response.context['month_savings'], Decimal('3750.25'))
        self.assertAlmostEqual(response.context['savings_percentage'], 75.0, places=1)

    def test_budget_calculations_and_notifications(self):
        """Test category budget warning and exceeded triggers."""
        self.client.login(username='testuser', password='TestPassword123!')
        today = timezone.now().date()

        cat_food = Category.objects.filter(user=self.user, type='EXPENSE', name__icontains='Food').first()
        budget = Budget.objects.create(
            user=self.user,
            category=cat_food,
            month=today.month,
            year=today.year,
            amount=Decimal('500.00')
        )

        # Initially 0%
        self.assertEqual(budget.get_spent_amount(), Decimal('0.00'))
        self.assertEqual(budget.get_percentage(), 0.0)
        self.assertFalse(budget.is_warning())
        self.assertFalse(budget.is_exceeded())

        # Spend $420 (84% -> warning)
        response = self.client.post(reverse('transaction_create'), {
            'type': 'EXPENSE',
            'title': 'Restaurant Dinner',
            'amount': '420.00',
            'date': today.strftime('%Y-%m-%d'),
            'category': cat_food.id,
            'payment_method': 'CREDIT_CARD',
            'notes': 'Team dinner',
        })
        self.assertEqual(response.status_code, 302)

        budget.refresh_from_db()
        self.assertEqual(budget.get_spent_amount(), Decimal('420.00'))
        self.assertEqual(budget.get_percentage(), 84.0)
        self.assertTrue(budget.is_warning())
        self.assertFalse(budget.is_exceeded())

        # Verify warning notification was created
        notif = Notification.objects.filter(user=self.user, title__icontains='Caution').first()
        self.assertIsNotNone(notif)

        # Spend additional $100 (total $520 -> 104% -> exceeded)
        self.client.post(reverse('transaction_create'), {
            'type': 'EXPENSE',
            'title': 'Cafe',
            'amount': '100.00',
            'date': today.strftime('%Y-%m-%d'),
            'category': cat_food.id,
            'payment_method': 'UPI',
        })
        self.assertTrue(budget.is_exceeded())
        notif_exceeded = Notification.objects.filter(user=self.user, title__icontains='Exceeded').first()
        self.assertIsNotNone(notif_exceeded)

    def test_savings_goal_contribute_and_completion(self):
        """Test savings goals calculations and completion notification."""
        self.client.login(username='testuser', password='TestPassword123!')

        goal = SavingsGoal.objects.create(
            user=self.user,
            title='MacBook Pro M3',
            target_amount=Decimal('2000.00'),
            current_amount=Decimal('1500.00'),
            status='IN_PROGRESS'
        )
        self.assertEqual(goal.get_percentage(), 75.0)
        self.assertEqual(goal.get_remaining(), Decimal('500.00'))

        # Add $500 contribution
        response = self.client.post(reverse('goal_contribute', kwargs={'pk': goal.pk}), {
            'amount': '500.00'
        })
        self.assertEqual(response.status_code, 302)

        goal.refresh_from_db()
        self.assertEqual(goal.current_amount, Decimal('2000.00'))
        self.assertEqual(goal.status, 'COMPLETED')
        self.assertEqual(goal.get_percentage(), 100.0)

        notif = Notification.objects.filter(user=self.user, title__icontains='Goal Achieved').first()
        self.assertIsNotNone(notif)

    def test_recurring_transaction_processing(self):
        """Test processing due recurring subscriptions."""
        self.client.login(username='testuser', password='TestPassword123!')
        today = timezone.now().date()

        cat_bills = Category.objects.filter(user=self.user, type='EXPENSE').first()
        recurring = RecurringTransaction.objects.create(
            user=self.user,
            title='Fiber Internet',
            category=cat_bills,
            type='EXPENSE',
            amount=Decimal('60.00'),
            frequency='MONTHLY',
            start_date=today - datetime.timedelta(days=35),
            next_due_date=today,
            is_active=True
        )

        response = self.client.post(reverse('recurring_process'))
        self.assertEqual(response.status_code, 302)

        tx = Transaction.objects.filter(user=self.user, title__icontains='Fiber Internet').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, Decimal('60.00'))
        self.assertTrue(tx.is_recurring_instance)

        recurring.refresh_from_db()
        self.assertGreater(recurring.next_due_date, today)

    def test_csv_export(self):
        """Test CSV export endpoint."""
        self.client.login(username='testuser', password='TestPassword123!')
        Transaction.objects.create(
            user=self.user,
            type='EXPENSE',
            title='Flight Ticket',
            amount=Decimal('350.00'),
            date=timezone.now().date()
        )
        response = self.client.get(reverse('export_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('Flight Ticket', response.content.decode('utf-8'))

    def test_pdf_report_download(self):
        """Test PDF financial statement generation."""
        self.client.login(username='testuser', password='TestPassword123!')
        today = timezone.now().date()
        Transaction.objects.create(
            user=self.user,
            type='EXPENSE',
            title='Monthly Grocery',
            amount=Decimal('180.00'),
            date=today
        )
        response = self.client.get(reverse('download_pdf_report', kwargs={'year': today.year, 'month': today.month}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertGreater(len(response.content), 1000)

    def test_user_data_isolation(self):
        """Ensure User A cannot see User B's transactions or budgets."""
        user_b = User.objects.create_user(
            username='userb',
            email='userb@finora.io',
            password='Password123!'
        )
        tx_b = Transaction.objects.create(
            user=user_b,
            type='INCOME',
            title='User B Secret Salary',
            amount=Decimal('9999.00'),
            date=timezone.now().date()
        )

        # Logged in as User A (self.user)
        self.client.login(username='testuser', password='TestPassword123!')
        response = self.client.get(reverse('transactions'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('User B Secret Salary', response.content.decode('utf-8'))

        # Attempt to delete User B's transaction as User A -> Should return 404
        response = self.client.post(reverse('transaction_delete', kwargs={'pk': tx_b.pk}))
        self.assertEqual(response.status_code, 404)

    def test_csv_import(self):
        """Test importing transactions from a CSV file."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.login(username='testuser', password='TestPassword123!')

        csv_content = (
            "Date,Title,Amount,Type,Category,Payment Method,Notes\n"
            "2026-11-01,Freelance Design Project,15000.00,INCOME,Freelance,BANK_TRANSFER,Website redesign\n"
            "2026-11-05,Office Chair,4500.50,EXPENSE,Shopping,CREDIT_CARD,Ergonomic chair\n"
        ).encode('utf-8')

        uploaded_csv = SimpleUploadedFile(
            "import_sample.csv",
            csv_content,
            content_type="text/csv"
        )

        response = self.client.post(reverse('import_csv'), {
            'csv_file': uploaded_csv
        })
        self.assertEqual(response.status_code, 302)

        # Verify transactions imported
        tx_freelance = Transaction.objects.filter(user=self.user, title='Freelance Design Project').first()
        self.assertIsNotNone(tx_freelance)
        self.assertEqual(tx_freelance.amount, Decimal('15000.00'))
        self.assertEqual(tx_freelance.type, 'INCOME')

        tx_chair = Transaction.objects.filter(user=self.user, title='Office Chair').first()
        self.assertIsNotNone(tx_chair)
        self.assertEqual(tx_chair.amount, Decimal('4500.50'))
        self.assertEqual(tx_chair.type, 'EXPENSE')

    def test_data_backup_and_restore(self):
        """Test full JSON data backup export and subsequent restore."""
        import json
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.login(username='testuser', password='TestPassword123!')

        # Create sample transaction
        Transaction.objects.create(
            user=self.user,
            type='EXPENSE',
            title='Airfare to Bengaluru',
            amount=Decimal('6200.00'),
            date=timezone.now().date(),
            payment_method='UPI'
        )

        # 1. Test Backup Export
        response = self.client.get(reverse('backup_data'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        backup_dict = json.loads(response.content.decode('utf-8'))
        self.assertEqual(backup_dict['finora_backup_version'], '2.0')
        self.assertTrue(any(t['title'] == 'Airfare to Bengaluru' for t in backup_dict['transactions']))

        # 2. Test Restore
        backup_file = SimpleUploadedFile(
            "finora_backup.json",
            response.content,
            content_type="application/json"
        )
        # Clear existing transactions to test pristine restoration
        Transaction.objects.filter(user=self.user).delete()
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 0)

        restore_response = self.client.post(reverse('restore_data'), {
            'backup_file': backup_file
        })
        self.assertEqual(restore_response.status_code, 302)
        restored_tx = Transaction.objects.filter(user=self.user, title='Airfare to Bengaluru').first()
        self.assertIsNotNone(restored_tx)
        self.assertEqual(restored_tx.amount, Decimal('6200.00'))

    def test_custom_category_management(self):
        """Test creating and managing user-defined categories."""
        self.client.login(username='testuser', password='TestPassword123!')

        # Create custom category
        response = self.client.post(reverse('category_create'), {
            'name': 'Cloud Hosting',
            'type': 'EXPENSE',
            'icon': 'server',
            'color': '#8B5CF6'
        })
        self.assertEqual(response.status_code, 302)

        custom_cat = Category.objects.filter(user=self.user, name='Cloud Hosting').first()
        self.assertIsNotNone(custom_cat)
        self.assertFalse(custom_cat.is_default)

        # Delete custom category
        delete_resp = self.client.post(reverse('category_delete', kwargs={'pk': custom_cat.pk}))
        self.assertEqual(delete_resp.status_code, 302)
        self.assertFalse(Category.objects.filter(user=self.user, name='Cloud Hosting').exists())

    def test_amount_range_filter(self):
        """Test min_amount and max_amount filtering on transactions list."""
        self.client.login(username='testuser', password='TestPassword123!')
        today = timezone.now().date()

        Transaction.objects.create(user=self.user, type='EXPENSE', title='Chai', amount=Decimal('20.00'), date=today)
        Transaction.objects.create(user=self.user, type='EXPENSE', title='Books', amount=Decimal('450.00'), date=today)
        Transaction.objects.create(user=self.user, type='EXPENSE', title='Laptop', amount=Decimal('85000.00'), date=today)

        # Filter between ₹100 and ₹1,000
        response = self.client.get(reverse('transactions'), {
            'min_amount': '100',
            'max_amount': '1000'
        })
        self.assertEqual(response.status_code, 200)
        items = list(response.context['page_obj'])
        titles = [item.title for item in items]
        self.assertIn('Books', titles)
        self.assertNotIn('Chai', titles)
        self.assertNotIn('Laptop', titles)

    def test_transaction_form_validations_and_duplicate_prevention(self):
        """Test that invalid amounts and rapid duplicate submissions are rejected."""
        from tracker.forms import TransactionForm

        # Negative amount
        form_neg = TransactionForm(data={
            'type': 'EXPENSE',
            'title': 'Test Item',
            'amount': '-50.00',
            'date': timezone.now().date(),
        }, user=self.user)
        self.assertFalse(form_neg.is_valid())
        self.assertIn('amount', form_neg.errors)

        # Zero amount
        form_zero = TransactionForm(data={
            'type': 'EXPENSE',
            'title': 'Test Item',
            'amount': '0.00',
            'date': timezone.now().date(),
        }, user=self.user)
        self.assertFalse(form_zero.is_valid())
        self.assertIn('amount', form_zero.errors)

        # Valid creation
        today = timezone.now().date()
        tx = Transaction.objects.create(
            user=self.user,
            type='EXPENSE',
            title='Duplicate Check',
            amount=Decimal('500.00'),
            date=today
        )

        # Immediate duplicate attempt
        form_dup = TransactionForm(data={
            'type': 'EXPENSE',
            'title': 'Duplicate Check',
            'amount': '500.00',
            'date': today,
        }, user=self.user)
        self.assertFalse(form_dup.is_valid())
        self.assertTrue(any('duplicate' in err.lower() for err in form_dup.non_field_errors()))

    def test_budget_history_and_analytics_computations(self):
        """Test budget adherence calculation and advanced analytics telemetry."""
        self.client.login(username='testuser', password='TestPassword123!')
        today = timezone.now().date()

        cat = Category.objects.filter(user=self.user, type='EXPENSE').first()
        Transaction.objects.create(
            user=self.user,
            type='EXPENSE',
            category=cat,
            title='Analytics Expense',
            amount=Decimal('1200.00'),
            date=today,
            payment_method='UPI'
        )

        # Test Analytics View
        response = self.client.get(reverse('analytics'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['highest_spending_category']['category__name'], cat.name)
        self.assertGreater(response.context['highest_cat_pct'], 0)
        self.assertGreater(response.context['daily_avg_spend'], Decimal('0.00'))

        # Test Budgets View (Verifying budget_history keys)
        b_resp = self.client.get(reverse('budgets'))
        self.assertEqual(b_resp.status_code, 200)
        history = b_resp.context['budget_history']
        self.assertEqual(len(history), 6)
        first_hist = history[0]
        self.assertIn('budget_cap', first_hist)
        self.assertIn('total_spent', first_hist)
        self.assertIn('pct', first_hist)
        self.assertIn('savings', first_hist)

