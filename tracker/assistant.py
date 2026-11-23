import datetime
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q
from dateutil.relativedelta import relativedelta
from .models import Transaction, Category, Budget, SavingsGoal, RecurringTransaction, UserProfile, AIChatMessage


def get_financial_context(user):
    """
    Computes real financial telemetry for the user from actual database records.
    """
    today = timezone.now().date()
    profile, _ = UserProfile.objects.get_or_create(user=user)
    sym = profile.get_currency_symbol()

    # Current month transactions
    month_txs = Transaction.objects.filter(user=user, date__year=today.year, date__month=today.month)
    month_income = month_txs.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    month_expense = month_txs.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    month_savings = month_income - month_expense
    savings_pct = round(float((month_savings / month_income) * Decimal('100.0')), 1) if month_income > Decimal('0.00') else 0.0

    # All-time transactions
    all_txs = Transaction.objects.filter(user=user)
    all_income = all_txs.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    all_expense = all_txs.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    net_balance = all_income - all_expense

    # Previous month transactions
    prev_date = today.replace(day=1) - relativedelta(days=1)
    prev_txs = Transaction.objects.filter(user=user, date__year=prev_date.year, date__month=prev_date.month)
    prev_income = prev_txs.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    prev_expense = prev_txs.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    # Category breakdown for current month
    cat_expenses = (
        month_txs.filter(type='EXPENSE')
        .values('category__name', 'category__color')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )
    categories_list = list(cat_expenses)
    highest_cat = categories_list[0] if categories_list else None

    # Average transaction size
    avg_expense = month_txs.filter(type='EXPENSE').aggregate(avg=Avg('amount'))['avg'] or Decimal('0.00')

    # Largest expense this month
    largest_expense = month_txs.filter(type='EXPENSE').order_by('-amount').first()

    # Budgets for current month
    overall_budget = Budget.objects.filter(user=user, category__isnull=True, month=today.month, year=today.year).first()
    category_budgets = list(Budget.objects.filter(user=user, category__isnull=False, month=today.month, year=today.year).select_related('category'))

    # Recurring active subscriptions
    recurring_txs = list(RecurringTransaction.objects.filter(user=user, is_active=True))
    total_recurring_monthly = Decimal('0.00')
    for r in recurring_txs:
        if r.frequency == 'DAILY':
            total_recurring_monthly += r.amount * Decimal('30')
        elif r.frequency == 'WEEKLY':
            total_recurring_monthly += r.amount * Decimal('4.33')
        elif r.frequency == 'MONTHLY':
            total_recurring_monthly += r.amount
        elif r.frequency == 'YEARLY':
            total_recurring_monthly += r.amount / Decimal('12')

    return {
        'sym': sym,
        'today': today,
        'month_name': today.strftime('%B %Y'),
        'month_income': month_income,
        'month_expense': month_expense,
        'month_savings': month_savings,
        'savings_pct': savings_pct,
        'net_balance': net_balance,
        'all_income': all_income,
        'all_expense': all_expense,
        'prev_income': prev_income,
        'prev_expense': prev_expense,
        'categories_list': categories_list,
        'highest_cat': highest_cat,
        'avg_expense': avg_expense,
        'largest_expense': largest_expense,
        'overall_budget': overall_budget,
        'category_budgets': category_budgets,
        'recurring_txs': recurring_txs,
        'total_recurring_monthly': round(total_recurring_monthly, 2),
        'month_txs': month_txs,
    }


def generate_spending_summary(ctx):
    sym = ctx['sym']
    inc = ctx['month_income']
    exp = ctx['month_expense']
    sav = ctx['month_savings']
    pct = ctx['savings_pct']
    highest = ctx['highest_cat']
    month = ctx['month_name']

    growth_str = ""
    if ctx['prev_expense'] > Decimal('0.00'):
        diff = exp - ctx['prev_expense']
        growth = round(float((diff / ctx['prev_expense']) * Decimal('100.0')), 1)
        if growth > 0:
            growth_str = f" This is an increase of **+{growth}%** compared to last month ({sym}{ctx['prev_expense']:,.2f})."
        else:
            growth_str = f" That is a decrease of **{growth}%** compared to last month ({sym}{ctx['prev_expense']:,.2f})."

    top_cat_str = ""
    if highest:
        cat_pct = round(float((highest['total'] / exp) * Decimal('100.0')), 1) if exp > Decimal('0.00') else 0.0
        top_cat_str = f"\n- **Top Outflow Category:** {highest['category__name']} accounted for **{sym}{highest['total']:,.2f}** ({cat_pct}% of total spending)."

    categories_breakdown = ""
    if len(ctx['categories_list']) > 1:
        categories_breakdown = "\n- **Spending by Category:**\n"
        for c in ctx['categories_list'][:5]:
            c_name = c['category__name'] or 'General'
            c_pct = round(float((c['total'] / exp) * Decimal('100.0')), 1) if exp > Decimal('0.00') else 0.0
            categories_breakdown += f"  • {c_name}: **{sym}{c['total']:,.2f}** ({c_pct}%)\n"

    budget_status = ""
    if ctx['overall_budget']:
        b = ctx['overall_budget']
        b_pct = b.get_percentage()
        b_rem = b.get_remaining()
        if b.is_exceeded():
            budget_status = f"\n- ⚠️ **Budget Alert:** You have exceeded your overall monthly budget limit of {sym}{b.amount:,.2f} by {sym}{abs(b_rem):,.2f} ({b_pct}% used)."
        else:
            budget_status = f"\n- 🛡️ **Budget Status:** You have used **{b_pct}%** of your {sym}{b.amount:,.2f} monthly budget. Remaining cushion: **{sym}{b_rem:,.2f}**."

    return (
        f"### 📊 Monthly Financial Summary ({month})\n\n"
        f"Here is your real-time spending and cash flow telemetry for **{month}**:\n\n"
        f"- **Total Inflow (Income):** **{sym}{inc:,.2f}**\n"
        f"- **Total Outflow (Expenses):** **{sym}{exp:,.2f}**{growth_str}\n"
        f"- **Net Savings:** **{sym}{sav:,.2f}** (Savings rate: **{pct}%**)\n"
        f"- **Available Liquid Balance:** **{sym}{ctx['net_balance']:,.2f}**\n"
        f"{top_cat_str}"
        f"{categories_breakdown}"
        f"{budget_status}\n\n"
        f"*💡 Quick tip: Ask 'Give me savings suggestions' or 'Detect unusual spending' for deeper analysis.*"
    )


def generate_highest_spending_category(ctx):
    sym = ctx['sym']
    highest = ctx['highest_cat']
    exp = ctx['month_expense']

    if not highest or exp <= Decimal('0.00'):
        return (
            f"### 🏆 Highest Spending Category\n\n"
            f"You have not recorded any expense transactions for **{ctx['month_name']}** yet. "
            f"Once you log your transactions, I will analyze your largest spending category and provide category-specific optimization suggestions."
        )

    cat_name = highest['category__name'] or 'General'
    amount = highest['total']
    count = highest['count']
    pct = round(float((amount / exp) * Decimal('100.0')), 1)

    breakdown_text = ""
    if len(ctx['categories_list']) > 1:
        breakdown_text = "\n\n**How other categories compare:**\n"
        for c in ctx['categories_list'][1:5]:
            other_name = c['category__name'] or 'General'
            other_pct = round(float((c['total'] / exp) * Decimal('100.0')), 1)
            breakdown_text += f"- **{other_name}:** {sym}{c['total']:,.2f} ({other_pct}%)\n"

    return (
        f"### 🏆 Highest Spending Category ({ctx['month_name']})\n\n"
        f"Your highest spending category this month is **{cat_name}**:\n\n"
        f"- **Total Spent:** **{sym}{amount:,.2f}**\n"
        f"- **Share of Total Expenses:** **{pct}%** of all outgoing funds\n"
        f"- **Transaction Count:** **{count}** logged entries\n"
        f"- **Average per Transaction:** **{sym}{(amount / count):,.2f}**"
        f"{breakdown_text}\n"
        f"**Recommendation:** Because {cat_name} consumes {pct}% of your outflow, setting a dedicated budget cap for it in the **Budgets** section will protect your savings margin."
    )


def generate_savings_suggestions(ctx):
    sym = ctx['sym']
    inc = ctx['month_income']
    exp = ctx['month_expense']
    sav = ctx['month_savings']
    highest = ctx['highest_cat']
    recurr = ctx['total_recurring_monthly']

    suggestions = []

    # 1. 50/30/20 rule analysis
    if inc > Decimal('0.00'):
        savings_ratio = float(sav / inc)
        if savings_ratio < 0.20:
            target_sav = inc * Decimal('0.20')
            shortfall = target_sav - sav
            suggestions.append(
                f"**1. Target the 20% Wealth Rule:**\n"
                f"Your current savings rate is **{ctx['savings_pct']}%** ({sym}{sav:,.2f}). To hit the standard 20% savings benchmark ({sym}{target_sav:,.2f}), "
                f"aim to reduce discretionary spending by **{sym}{shortfall:,.2f}** before the end of the billing cycle."
            )
        else:
            suggestions.append(
                f"**1. Outstanding Savings Rate:**\n"
                f"You are saving **{ctx['savings_pct']}%** of your income this month ({sym}{sav:,.2f}), which exceeds the standard 20% benchmark! "
                f"Consider allocating a portion of this surplus into an active **Savings Goal** or emergency fund."
            )

    # 2. Highest category reduction
    if highest and exp > Decimal('0.00'):
        h_name = highest['category__name']
        h_amt = highest['total']
        h_reduction = h_amt * Decimal('0.15')
        suggestions.append(
            f"**2. Trim 15% from {h_name}:**\n"
            f"Your spending in **{h_name}** is {sym}{h_amt:,.2f}. If you shave just 15% off this category ({sym}{h_reduction:,.2f}), "
            f"you will retain an extra **{sym}{h_reduction:,.2f}** in monthly cash flow."
        )

    # 3. Recurring subscriptions audit
    if recurr > Decimal('0.00'):
        suggestions.append(
            f"**3. Audit Fixed Subscriptions:**\n"
            f"You have committed **{sym}{recurr:,.2f}** per month in recurring bills and subscriptions ({len(ctx['recurring_txs'])} active items). "
            f"Review your recurring schedules and cancel memberships you haven't utilized recently."
        )

    # 4. Daily discretionary cap
    day_count = max(ctx['today'].day, 1)
    daily_avg = exp / Decimal(day_count)
    suggestions.append(
        f"**4. Daily Spend Guardrail:**\n"
        f"Your current daily burn rate is **{sym}{daily_avg:,.2f}/day**. Setting a personal daily ceiling of **{sym}{(daily_avg * Decimal('0.85')):,.2f}** "
        f"will build a substantial safety reserve."
    )

    return (
        f"### 💡 Personalized Savings Strategies\n\n"
        f"Based on your actual {ctx['month_name']} transaction ledger:\n\n"
        + "\n\n".join(suggestions) +
        f"\n\n*Targeting any of these changes will directly increase your net monthly liquidity.*"
    )


def generate_unusual_spending_patterns(ctx):
    sym = ctx['sym']
    month_txs = ctx['month_txs']
    avg_exp = ctx['avg_expense']
    exp = ctx['month_expense']

    anomalies = []

    # 1. Transactions > 2.5x average transaction size
    if avg_exp > Decimal('0.00'):
        spike_threshold = avg_exp * Decimal('2.5')
        spikes = month_txs.filter(type='EXPENSE', amount__gte=spike_threshold).order_by('-amount')[:4]
        if spikes.exists():
            spike_list = []
            for s in spikes:
                c_name = s.category.name if s.category else 'General'
                spike_list.append(f"  • **{s.title}** ({c_name}): **{sym}{s.amount:,.2f}** on {s.date.strftime('%d %b %Y')}")
            anomalies.append(
                f"**High-Value Transactions (> 2.5x your average of {sym}{avg_exp:,.2f}):**\n" +
                "\n".join(spike_list)
            )

    # 2. Check for category jumps compared to previous month
    if ctx['prev_expense'] > Decimal('0.00'):
        prev_date = ctx['today'].replace(day=1) - relativedelta(days=1)
        prev_month_txs = Transaction.objects.filter(
            user=month_txs.first().user if month_txs.exists() else None,
            date__year=prev_date.year,
            date__month=prev_date.month,
            type='EXPENSE'
        )
        for c in ctx['categories_list'][:3]:
            cat_name = c['category__name']
            current_amt = c['total']
            prev_amt = prev_month_txs.filter(category__name=cat_name).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
            if prev_amt > Decimal('0.00'):
                cat_growth = ((current_amt - prev_amt) / prev_amt) * Decimal('100.0')
                if cat_growth >= Decimal('40.0'):
                    anomalies.append(
                        f"**Category Surge in {cat_name}:**\n"
                        f"Spending in **{cat_name}** jumped by **+{round(float(cat_growth), 1)}%** compared to last month ({sym}{current_amt:,.2f} vs {sym}{prev_amt:,.2f})."
                    )

    # 3. Check for single transaction consuming > 25% of monthly budget/expenses
    if exp > Decimal('0.00') and ctx['largest_expense']:
        largest = ctx['largest_expense']
        largest_pct = (largest.amount / exp) * Decimal('100.0')
        if largest_pct >= Decimal('25.0'):
            anomalies.append(
                f"**Single Outlier Purchase:**\n"
                f"**{largest.title}** ({sym}{largest.amount:,.2f}) consumed **{round(float(largest_pct), 1)}%** of your total expenses this month alone."
            )

    if not anomalies:
        return (
            f"### 🛡️ Unusual Spending Pattern Analysis\n\n"
            f"No major anomalies or high-risk spending spikes detected in **{ctx['month_name']}**! "
            f"Your expense distributions and transaction amounts fall within regular, healthy baseline parameters."
        )

    return (
        f"### ⚠️ Unusual Spending Patterns Detected ({ctx['month_name']})\n\n"
        f"I analyzed your transaction history and detected the following outliers:\n\n"
        + "\n\n".join(f"- {a}" for a in anomalies) +
        f"\n\n*Reviewing these outliers helps prevent unplanned budget leakages.*"
    )


def handle_category_query(ctx, user, query_lower):
    sym = ctx['sym']
    categories = Category.objects.filter(Q(user=user) | Q(user__isnull=True))

    matched_cat = None
    # 1. Exact or substring match
    for c in categories:
        c_low = c.name.lower()
        if c_low in query_lower:
            matched_cat = c
            break

    # 2. Word-level token match (e.g. "food" matches "Food & Dining")
    if not matched_cat:
        stop_words = {'and', '&', 'expense', 'expenses', 'income', 'spend', 'spent', 'how', 'much', 'did', 'i', 'on', 'my', 'the', 'for', 'in', 'a', 'an'}
        q_tokens = [w.strip('?,.! ') for w in query_lower.split() if w.strip('?,.! ') not in stop_words and len(w.strip('?,.! ')) >= 3]
        for c in categories:
            c_tokens = [w.strip('?,.& ') for w in c.name.lower().split() if w.strip('?,.& ') not in stop_words and len(w.strip('?,.& ')) >= 3]
            for token in q_tokens:
                if any(ct and (token == ct or token in ct or ct in token) for ct in c_tokens):
                    matched_cat = c
                    break
            if matched_cat:
                break

    if not matched_cat:
        return None

    # Filter transactions for this category
    c_txs = Transaction.objects.filter(user=user, category=matched_cat)
    total_spent = c_txs.filter(type='EXPENSE').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    total_income = c_txs.filter(type='INCOME').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    tx_count = c_txs.count()
    recent = list(c_txs[:3])

    recent_str = ""
    if recent:
        recent_str = "\n\n**Recent entries in this category:**\n"
        for r in recent:
            sign = "+" if r.type == 'INCOME' else "-"
            recent_str += f"- {r.date.strftime('%d %b %Y')}: **{r.title}** ({sign}{sym}{r.amount:,.2f})\n"

    type_text = f"- **Total Spent:** **{sym}{total_spent:,.2f}**" if total_spent > Decimal('0.00') else f"- **Total Income:** **{sym}{total_income:,.2f}**"

    return (
        f"### 🏷️ Category Analysis: {matched_cat.name}\n\n"
        f"{type_text}\n"
        f"- **Total Transactions:** **{tx_count}**\n"
        f"- **Type:** {matched_cat.get_type_display()}"
        f"{recent_str}"
    )


def process_assistant_query(user, query_text):
    """
    Main dispatch function: analyzes user query and returns structured, intelligent insights.
    """
    q = query_text.strip().lower()
    ctx = get_financial_context(user)
    sym = ctx['sym']

    # 1. Check for specific category questions first (e.g. "how much did I spend on food?", "shopping expense")
    if not any(k in q for k in ['overall', 'total spending', 'entire', 'all categories', 'summar', 'overview']):
        cat_res = handle_category_query(ctx, user, q)
        if cat_res:
            return cat_res, 'category_detail'

    # 2. Monthly spending summary
    if any(k in q for k in ['summar', 'monthly spending', 'overview', 'how much did i spend', 'cash flow', 'cashflow', 'spending summary']):
        return generate_spending_summary(ctx), 'spending_summary'

    # 2. Highest spending category
    if any(k in q for k in ['highest', 'top spending', 'top categor', 'biggest categor', 'most expensive category', 'where did my money go']):
        return generate_highest_spending_category(ctx), 'highest_category'

    # 3. Savings suggestions
    if any(k in q for k in ['saving', 'save', 'suggestion', 'tip', 'advice', 'how can i save', 'cut cost', 'reduce spend']):
        return generate_savings_suggestions(ctx), 'savings_suggestions'

    # 4. Unusual spending patterns / anomalies
    if any(k in q for k in ['unusual', 'anomal', 'spike', 'irregular', 'suspicious', 'outlier', 'pattern']):
        return generate_unusual_spending_patterns(ctx), 'unusual_patterns'

    # 5. Budget status queries
    if any(k in q for k in ['budget', 'limit', 'cap', 'am i within budget', 'over budget']):
        b = ctx['overall_budget']
        if not b:
            return (
                f"### 🛡️ Budget Status ({ctx['month_name']})\n\n"
                f"You haven't set an overall monthly budget limit for **{ctx['month_name']}** yet. "
                f"Your total expenses so far are **{sym}{ctx['month_expense']:,.2f}**.\n\n"
                f"You can establish overall and category-specific budget limits in the **Budgets** section.",
                'budget_status'
            )
        rem = b.get_remaining()
        spent = b.get_spent_amount()
        pct = b.get_percentage()
        status_word = "EXCEEDED" if b.is_exceeded() else ("WARNING" if b.is_warning() else "ON TRACK")
        return (
            f"### 🛡️ Budget Telemetry ({ctx['month_name']})\n\n"
            f"- **Status:** **{status_word}**\n"
            f"- **Allocated Limit:** **{sym}{b.amount:,.2f}**\n"
            f"- **Spent So Far:** **{sym}{spent:,.2f}**\n"
            f"- **Remaining Buffer:** **{sym}{rem:,.2f}**\n"
            f"- **Consumption:** **{pct}%** of allocated cap\n\n"
            f"*Check the Budgets page for category-specific limits.*",
            'budget_status'
        )

    # 6. Largest purchase query
    if any(k in q for k in ['largest', 'biggest purchase', 'biggest expense', 'maximum spend']):
        largest = ctx['largest_expense']
        if largest:
            cat_name = largest.category.name if largest.category else 'General'
            return (
                f"### 💳 Largest Recorded Outflow\n\n"
                f"Your biggest single purchase this month was:\n\n"
                f"- **Title:** **{largest.title}**\n"
                f"- **Amount:** **{sym}{largest.amount:,.2f}**\n"
                f"- **Category:** {cat_name}\n"
                f"- **Date:** {largest.date.strftime('%d %B %Y')}\n"
                f"- **Payment Method:** {largest.get_payment_method_display()}",
                'largest_expense'
            )
        else:
            return (f"No expense transactions recorded for {ctx['month_name']}.", 'largest_expense')

    # 7. Check for specific category questions (e.g. food, shopping, travel, salary)
    cat_res = handle_category_query(ctx, user, q)
    if cat_res:
        return cat_res, 'category_detail'

    # 8. Total balance or liquidity query
    if any(k in q for k in ['balance', 'how much money', 'net worth', 'liquidity', 'income']):
        return (
            f"### 💰 Net Available Liquidity\n\n"
            f"- **Total Net Balance:** **{sym}{ctx['net_balance']:,.2f}**\n"
            f"- **All-Time Income:** **{sym}{ctx['all_income']:,.2f}**\n"
            f"- **All-Time Expenses:** **{sym}{ctx['all_expense']:,.2f}**\n"
            f"- **This Month's Inflow:** **{sym}{ctx['month_income']:,.2f}**\n"
            f"- **This Month's Net Savings:** **{sym}{ctx['month_savings']:,.2f}**",
            'balance_inquiry'
        )

    # 9. Default helpful response with actionable guidance
    return (
        f"### 🤖 FINORA Intelligent Assistant\n\n"
        f"I can analyze your personal finances in real time using your recorded database records. "
        f"Your current available balance is **{sym}{ctx['net_balance']:,.2f}**, and you've spent **{sym}{ctx['month_expense']:,.2f}** in {ctx['month_name']}.\n\n"
        f"**Try asking me:**\n"
        f"- *'Summarize my monthly spending'*\n"
        f"- *'What is my highest spending category?'*\n"
        f"- *'Give me savings suggestions'*\n"
        f"- *'Detect unusual spending patterns'*\n"
        f"- *'How much did I spend on Food?'* (or any category name)\n"
        f"- *'What was my largest purchase?'*\n"
        f"- *'Am I within my budget?'*",
        'general_inquiry'
    )
