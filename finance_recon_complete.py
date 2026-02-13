import streamlit as st
import requests
import json
from PIL import Image
import os
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from collections import defaultdict
import calendar

# --- 1. THEME & PAGE CONFIG ---
st.set_page_config(page_title="Finance Recon Pro", layout="wide", page_icon="💰")

# Custom CSS for better design
st.markdown("""
<style>
    /* Main theme */
    .stApp { 
        background: linear-gradient(135deg, #0E1117 0%, #1a1f2e 100%);
        color: #E0E0E0; 
    }
    
    /* Headers */
    h1 {
        background: linear-gradient(90deg, #00D9FF 0%, #7B2CBF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    
    h2, h3 {
        color: #00D9FF;
    }
    
    /* Metric cards */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }
    
    /* Custom cards */
    .custom-card {
        background: linear-gradient(145deg, #1e2530 0%, #252d3d 100%);
        padding: 20px;
        border-radius: 15px;
        border-left: 4px solid #00D9FF;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        margin: 10px 0;
    }
    
    .warning-card {
        background: linear-gradient(145deg, #3d2520 0%, #4d2d25 100%);
        border-left-color: #FF6B6B;
    }
    
    .success-card {
        background: linear-gradient(145deg, #203d25 0%, #254d2d 100%);
        border-left-color: #51CF66;
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #00D9FF 0%, #7B2CBF 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 600;
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0, 217, 255, 0.4);
    }
    
    /* Progress bars */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #00D9FF 0%, #7B2CBF 100%);
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1f2e 0%, #0E1117 100%);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #1e2530;
        border-radius: 10px;
        font-weight: 600;
    }
    
    /* Data tables */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
    }
    
    /* Divider */
    hr {
        border-color: #00D9FF;
        opacity: 0.3;
    }
    
    /* Login box */
    .login-box {
        max-width: 400px;
        margin: 100px auto;
        padding: 40px;
        background: linear-gradient(145deg, #1e2530 0%, #252d3d 100%);
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. MINDEE API CONFIGURATION ---
try:
    mindee_api_key = os.getenv("MINDEE_API_KEY") or st.secrets.get("MINDEE_API_KEY", "")
except:
    mindee_api_key = ""

# Receipt Model ID
RECEIPT_MODEL_ID = "ea052ba3-d02e-482b-af10-3aeba53c7146"

# Bank Statement Model ID
BANK_STATEMENT_MODEL_ID = "77d71fe3-2547-482e-94b3-a3a6c3d97028"

# Helper function to call Mindee API
import time

def analyze_with_mindee(image_bytes, filename, api_key, model_id):
    """Call Mindee API v2 with polling for async results"""
    # Step 1: Enqueue the document for processing
    enqueue_url = "https://api-v2.mindee.net/v2/products/extraction/enqueue"
    
    headers = {
        "Authorization": api_key
    }
    
    files = {
        "file": (filename, image_bytes, "image/jpeg")
    }
    
    data = {
        "model_id": model_id
    }
    
    response = requests.post(enqueue_url, headers=headers, files=files, data=data)
    
    if response.status_code not in [200, 201, 202]:
        raise Exception(f"API Error {response.status_code}: {response.text}")
    
    result = response.json()
    job = result.get('job', {})
    job_id = job.get('id')
    
    if not job_id:
        raise Exception("No job ID returned from API")
    
    # Step 2: Poll for job completion
    job_url = f"https://api-v2.mindee.net/v2/jobs/{job_id}"
    
    # Poll for up to 60 seconds
    for attempt in range(60):
        time.sleep(1)
        poll_response = requests.get(job_url, headers=headers, params={"redirect": "false"})
        
        if poll_response.status_code == 200:
            poll_data = poll_response.json()
            job_status = poll_data.get('job', {}).get('status')
            
            if job_status == 'Processed':
                # Get the result
                result_url = poll_data.get('job', {}).get('result_url')
                if result_url:
                    result_response = requests.get(result_url, headers=headers)
                    if result_response.status_code == 200:
                        return result_response.json()
                raise Exception("Result URL not available")
            elif job_status == 'Failed':
                error = poll_data.get('job', {}).get('error', {})
                raise Exception(f"Processing failed: {error}")
    
    raise Exception("Timeout waiting for results (60 seconds)")

def categorize_transaction(description):
    """Auto-categorize based on vendor name"""
    desc_lower = description.lower()
    
    # Groceries & Food
    if any(word in desc_lower for word in ['costco', 'walmart', 'vons', 'sprouts', 'trader', 'whole foods', 'aldi', 'safeway', 'kroger']):
        return "Groceries"
    # Dining Out
    elif any(word in desc_lower for word in ['restaurant', 'mcdonald', 'chick-fil-a', 'chipotle', 'shake shack', 'starbucks', 'coffee', 'donut', 'pizza', 'taco', 'burger', 'sonic', 'panda', 'wingstop', 'pollo', 'subway', 'kfc']):
        return "Dining Out"
    # Gas/Fuel
    elif any(word in desc_lower for word in ['gas', 'fuel', 'shell', 'chevron', 'exxon', 'mobil', '76', 'arco']):
        return "Gas/Fuel"
    # Home Improvement
    elif any(word in desc_lower for word in ['home depot', 'lowes', 'hardware', 'ace hardware']):
        return "Rent/Mortgage"
    # Entertainment
    elif any(word in desc_lower for word in ['netflix', 'cinema', 'movie', 'theater', 'spotify', 'hulu', 'disney']):
        return "Entertainment"
    # Personal Care
    elif any(word in desc_lower for word in ['ulta', 'sephora', 'salon', 'spa', 'marshalls', 'anthropologie', 'lululemon', 'target', 'tj maxx', 'ross']):
        return "Personal Care"
    # Healthcare
    elif any(word in desc_lower for word in ['kaiser', 'pharmacy', 'cvs', 'walgreens', 'medical', 'doctor', 'health']):
        return "Healthcare"
    # Utilities
    elif any(word in desc_lower for word in ['burrtec', 'waste', 'water', 'electric', 'utility', 'power', 'gas company', 'water district']):
        return "Utilities"
    # Tech/AI
    elif any(word in desc_lower for word in ['paypal', 'amazon', 'best buy', 'apple', 'microsoft', 'google']):
        return "Tech/AI"
    # Car/Insurance
    elif any(word in desc_lower for word in ['dmv', 'registration', 'towing', 'auto', 'insurance', 'geico', 'state farm']):
        return "Insurance"
    else:
        return "Groceries"  # Default

def detect_income(transactions):
    """Detect income from transactions"""
    income_sources = []
    
    for trans in transactions:
        desc = trans.get('description', '').lower()
        amount = trans.get('amount', 0)
        trans_type = trans.get('type', '')
        
        # Method 1: Keywords
        income_keywords = ['payroll', 'direct deposit', 'dd', 'salary', 'wages', 'paycheck', 'payment thank you', 'automatic payment']
        if any(keyword in desc for keyword in income_keywords):
            income_sources.append({
                'source': trans.get('description', 'Unknown'),
                'amount': amount,
                'type': 'Detected Income'
            })
        
        # Method 2: Large credits (likely paychecks)
        elif trans_type == 'Income' and amount > 1000:
            income_sources.append({
                'source': trans.get('description', 'Large Deposit'),
                'amount': amount,
                'type': 'Large Credit'
            })
    
    return income_sources

def calculate_monthly_stats(transactions):
    """Calculate monthly statistics from transactions"""
    monthly_data = defaultdict(lambda: {
        'income': 0,
        'expenses': 0,
        'by_category': defaultdict(float),
        'transaction_count': 0
    })
    
    for trans in transactions:
        # Parse date
        try:
            date_str = trans.get('Date', '')
            date_obj = datetime.strptime(date_str, "%m/%d/%Y")
            month_key = date_obj.strftime("%Y-%m")  # e.g., "2025-01"
        except:
            continue
        
        amount = trans.get('Amount', 0)
        trans_type = trans.get('Type', 'Expense')
        category = trans.get('Category', 'Other')
        
        monthly_data[month_key]['transaction_count'] += 1
        
        if trans_type == 'Income':
            monthly_data[month_key]['income'] += amount
        else:
            monthly_data[month_key]['expenses'] += amount
            monthly_data[month_key]['by_category'][category] += amount
    
    return dict(monthly_data)

# --- 3. LOGIN SYSTEM ---
MASTER_PASSWORD = "922626"

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'all_users_data' not in st.session_state:
    st.session_state.all_users_data = {}
if 'onboarding_complete' not in st.session_state:
    st.session_state.onboarding_complete = {}

def login_page():
    """Display login page"""
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    st.markdown("# 💰 Finance Recon Pro")
    st.markdown("### Welcome! Please login to continue")
    
    with st.form("login_form"):
        username = st.text_input("👤 Your Name", placeholder="Enter your name")
        password = st.text_input("🔐 Access Code", type="password", placeholder="Enter access code")
        
        col1, col2 = st.columns(2)
        with col1:
            login_button = st.form_submit_button("🔓 Login", use_container_width=True)
        with col2:
            new_user_button = st.form_submit_button("➕ New User", use_container_width=True)
        
        if login_button or new_user_button:
            if not username:
                st.error("Please enter your name")
            elif password != MASTER_PASSWORD:
                st.error("❌ Incorrect access code")
            else:
                # Successful login
                st.session_state.authenticated = True
                st.session_state.current_user = username
                
                # Create new user data if doesn't exist
                if username not in st.session_state.all_users_data:
                    st.session_state.all_users_data[username] = {
                        'bank_transactions': [],
                        'receipts': [],
                        'financial_goals': [],
                        'recurring_expenses': [],
                        'budget': {},
                        'income_sources': []
                    }
                    st.session_state.onboarding_complete[username] = False
                    st.success(f"✅ Welcome {username}! Let's set up your account.")
                else:
                    st.success(f"✅ Welcome back, {username}!")
                
                st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)

def onboarding_flow():
    """New user onboarding - upload 2 months of statements"""
    st.markdown("# 🎉 Welcome to Finance Recon Pro!")
    st.markdown(f"### Let's set up your account, {st.session_state.current_user}!")
    
    st.markdown("""
    To give you the best experience, please upload your **last 2 months** of financial statements:
    
    - 📄 Bank statements (checking/savings)
    - 💳 Credit card statements
    
    This helps us:
    - ✅ Detect your income automatically
    - ✅ Calculate your average spending
    - ✅ Suggest realistic budgets
    - ✅ Show you insights right away!
    """)
    
    st.divider()
    
    # File uploaders
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📅 Month 1 (Most Recent)")
        month1_bank = st.file_uploader("Bank Statement", type=['pdf', 'png', 'jpg', 'jpeg'], key="m1_bank")
        month1_cc = st.file_uploader("Credit Card Statement", type=['pdf', 'png', 'jpg', 'jpeg'], key="m1_cc")
    
    with col2:
        st.markdown("### 📅 Month 2 (Previous)")
        month2_bank = st.file_uploader("Bank Statement", type=['pdf', 'png', 'jpg', 'jpeg'], key="m2_bank")
        month2_cc = st.file_uploader("Credit Card Statement", type=['pdf', 'png', 'jpg', 'jpeg'], key="m2_cc")
    
    st.divider()
    
    # Skip option
    col_a, col_b = st.columns([3, 1])
    with col_a:
        if st.button("🚀 Analyze My Statements", type="primary", use_container_width=True, disabled=not mindee_api_key):
            if not mindee_api_key:
                st.error("⚠️ Mindee API key required!")
            else:
                # Collect uploaded files
                files_to_process = []
                if month1_bank: files_to_process.append(('Bank', month1_bank))
                if month1_cc: files_to_process.append(('Credit Card', month1_cc))
                if month2_bank: files_to_process.append(('Bank', month2_bank))
                if month2_cc: files_to_process.append(('Credit Card', month2_cc))
                
                if len(files_to_process) == 0:
                    st.warning("Please upload at least one statement to continue.")
                else:
                    # Process all statements
                    all_transactions = []
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, (stmt_type, file) in enumerate(files_to_process):
                        status_text.text(f"Processing {stmt_type} statement {idx+1}/{len(files_to_process)}...")
                        progress_bar.progress((idx + 1) / len(files_to_process))
                        
                        try:
                            result = analyze_with_mindee(file.getvalue(), file.name, mindee_api_key, BANK_STATEMENT_MODEL_ID)
                            
                            # Extract transactions
                            inference = result.get('inference', {})
                            result_data = inference.get('result', {})
                            fields = result_data.get('fields', {})
                            line_items_obj = fields.get('line_items', {})
                            line_items_array = line_items_obj.get('items', [])
                            
                            for item in line_items_array:
                                if isinstance(item, dict):
                                    item_fields = item.get('fields', {})
                                    desc = item_fields.get('description', {}).get('value', 'Unknown')
                                    amount = item_fields.get('total_price', {}).get('value', 0.0)
                                    
                                    if not desc or desc in ['PURCHASES', 'CASH ADVANCES', 'PAYMENTS'] or amount is None:
                                        continue
                                    
                                    category = categorize_transaction(desc)
                                    
                                    # Determine type
                                    desc_lower = desc.lower()
                                    trans_type = "Expense"
                                    if any(word in desc_lower for word in ['payment', 'thank you', 'automatic payment', 'direct deposit', 'payroll']):
                                        trans_type = "Income"
                                    
                                    all_transactions.append({
                                        'description': desc,
                                        'amount': abs(amount),
                                        'category': category,
                                        'type': trans_type
                                    })
                        
                        except Exception as e:
                            st.warning(f"Could not process {stmt_type} statement: {str(e)}")
                    
                    progress_bar.progress(1.0)
                    status_text.text("✅ Analysis complete!")
                    
                    # Detect income
                    income_sources = detect_income(all_transactions)
                    
                    # Calculate averages
                    category_totals = defaultdict(float)
                    total_income = 0
                    total_expenses = 0
                    
                    for trans in all_transactions:
                        if trans['type'] == 'Income':
                            total_income += trans['amount']
                        else:
                            total_expenses += trans['amount']
                            category_totals[trans['category']] += trans['amount']
                    
                    # Calculate monthly averages (divide by 2 months)
                    num_months = 2
                    avg_income = total_income / num_months
                    avg_category_spending = {cat: total / num_months for cat, total in category_totals.items()}
                    
                    # Show results
                    st.success(f"🎉 Analyzed {len(all_transactions)} transactions!")
                    
                    st.markdown("### 💡 Here's what we found:")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("💰 Avg Monthly Income", f"${avg_income:,.0f}")
                    with col2:
                        st.metric("💸 Avg Monthly Expenses", f"${total_expenses/num_months:,.0f}")
                    with col3:
                        savings_rate = ((avg_income - (total_expenses/num_months)) / avg_income * 100) if avg_income > 0 else 0
                        st.metric("📊 Savings Rate", f"{savings_rate:.1f}%")
                    
                    st.markdown("#### 📋 Detected Income Sources:")
                    if income_sources:
                        for source in income_sources[:5]:  # Show top 5
                            st.markdown(f"• **{source['source']}**: ${source['amount']:,.2f}")
                    else:
                        st.info("No automatic income detected. You can set it manually.")
                    
                    st.markdown("#### 💳 Average Monthly Spending by Category:")
                    for category, amount in sorted(avg_category_spending.items(), key=lambda x: x[1], reverse=True):
                        st.markdown(f"• **{category}**: ${amount:,.0f}/month")
                    
                    # Save to user data
                    user_data = st.session_state.all_users_data[st.session_state.current_user]
                    
                    # Add all transactions with dates
                    for trans in all_transactions:
                        user_data['bank_transactions'].append({
                            "Date": datetime.now().strftime("%m/%d/%Y"),
                            "Vendor": trans['description'],
                            "Amount": trans['amount'],
                            "Category": trans['category'],
                            "Type": trans['type'],
                            "Notes": "Imported during onboarding"
                        })
                    
                    # Save income sources
                    user_data['income_sources'] = income_sources
                    
                    # Save suggested budget
                    user_data['budget'] = avg_category_spending
                    
                    # Mark onboarding complete
                    if st.button("✅ Complete Setup & Start Tracking!", type="primary", use_container_width=True):
                        st.session_state.onboarding_complete[st.session_state.current_user] = True
                        st.success("🎉 Setup complete! Welcome to Finance Recon Pro!")
                        st.rerun()
    
    with col_b:
        if st.button("Skip for Now"):
            st.session_state.onboarding_complete[st.session_state.current_user] = True
            st.rerun()

# Show login page if not authenticated
if not st.session_state.authenticated:
    login_page()
    st.stop()

# Show onboarding if user hasn't completed it
current_user = st.session_state.current_user
if not st.session_state.onboarding_complete.get(current_user, False):
    onboarding_flow()
    st.stop()

# --- 4. GET CURRENT USER DATA ---
user_data = st.session_state.all_users_data[current_user]

# Calculate monthly stats
monthly_stats = calculate_monthly_stats(user_data['bank_transactions'])

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown(f"# 🎯 {current_user}'s Dashboard")
    
    # Logout button
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.rerun()
    
    st.divider()
    
    # Mindee API Key
    if not mindee_api_key:
        st.warning("⚠️ Set MINDEE_API_KEY")
        mindee_api_key = st.text_input("API Key:", type="password")
    
    st.divider()
    
    # Income Section
    st.markdown("### 💰 Income")
    suggested_income = sum([s['amount'] for s in user_data.get('income_sources', [])]) if user_data.get('income_sources') else 0
    total_income = st.number_input("Monthly Income", value=int(suggested_income) if suggested_income > 0 else 0, step=100)
    
    st.divider()
    
    # Budget Categories (use suggested values)
    st.markdown("### 📊 Budget")
    
    categories = {}
    suggested_budget = user_data.get('budget', {})
    
    with st.expander("🏠 Housing"):
        categories["Rent/Mortgage"] = st.slider("Rent/Mortgage", 0, 5000, int(suggested_budget.get("Rent/Mortgage", 0)), 50)
        categories["Utilities"] = st.slider("Utilities", 0, 500, int(suggested_budget.get("Utilities", 0)), 10)
        categories["Internet/Phone"] = st.slider("Internet/Phone", 0, 300, int(suggested_budget.get("Internet/Phone", 0)), 10)
    
    with st.expander("🚗 Transportation"):
        categories["Car Payment"] = st.slider("Car Payment", 0, 1000, int(suggested_budget.get("Car Payment", 0)), 25)
        categories["Gas/Fuel"] = st.slider("Gas/Fuel", 0, 500, int(suggested_budget.get("Gas/Fuel", 0)), 10)
        categories["Insurance"] = st.slider("Insurance", 0, 500, int(suggested_budget.get("Insurance", 0)), 10)
    
    with st.expander("🍎 Food"):
        categories["Groceries"] = st.slider("Groceries", 0, 1000, int(suggested_budget.get("Groceries", 0)), 25)
        categories["Dining Out"] = st.slider("Dining Out", 0, 500, int(suggested_budget.get("Dining Out", 0)), 25)
    
    with st.expander("💳 Debt & Savings"):
        categories["Credit Cards"] = st.slider("Credit Cards", 0, 1000, int(suggested_budget.get("Credit Cards", 0)), 25)
        categories["Loans"] = st.slider("Loans", 0, 1000, int(suggested_budget.get("Loans", 0)), 25)
        categories["Savings"] = st.slider("Savings", 0, 2000, int(suggested_budget.get("Savings", 0)), 50)
    
    with st.expander("🎯 Lifestyle"):
        categories["Entertainment"] = st.slider("Entertainment", 0, 300, int(suggested_budget.get("Entertainment", 0)), 10)
        categories["Tech/AI"] = st.slider("Tech/AI", 0, 300, int(suggested_budget.get("Tech/AI", 0)), 10)
        categories["Healthcare"] = st.slider("Healthcare", 0, 500, int(suggested_budget.get("Healthcare", 0)), 25)
        categories["Personal Care"] = st.slider("Personal Care", 0, 300, int(suggested_budget.get("Personal Care", 0)), 25)
    
    total_budgeted = sum(categories.values())
    remaining = total_income - total_budgeted
    
    st.divider()
    st.markdown("### 📈 Summary")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Income", f"${total_income:,.0f}")
    with col2:
        st.metric("Budgeted", f"${total_budgeted:,.0f}")
    
    if total_income > 0:
        st.progress(min(total_budgeted/total_income, 1.0))
    
    if remaining < 0:
        st.error(f"Over: ${abs(remaining):,.0f}")
    else:
        st.success(f"Left: ${remaining:,.0f}")

# --- 6. MAIN APP ---
st.markdown(f"# 💰 {current_user}'s Finance Dashboard")

# Top metrics
col1, col2, col3, col4 = st.columns(4)

total_spent = sum([t['Amount'] for t in user_data['bank_transactions'] if t['Type'] == 'Expense'])
total_earned = sum([t['Amount'] for t in user_data['bank_transactions'] if t['Type'] == 'Income'])
net_savings = total_earned - total_spent

with col1:
    st.metric("💰 Total Income", f"${total_earned:,.0f}")
with col2:
    st.metric("💸 Total Spent", f"${total_spent:,.0f}")
with col3:
    st.metric("📊 Net Savings", f"${net_savings:,.0f}", delta=f"{(net_savings/total_earned*100):.1f}%" if total_earned > 0 else "0%")
with col4:
    st.metric("📝 Transactions", len(user_data['bank_transactions']))

st.divider()

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Monthly Overview", "📈 Trends", "🏦 All Transactions"])

# TAB 1: MONTHLY OVERVIEW
with tab1:
    st.markdown("### 📅 Monthly Breakdown")
    
    if monthly_stats:
        # Sort months
        sorted_months = sorted(monthly_stats.keys(), reverse=True)
        
        for month_key in sorted_months:
            stats = monthly_stats[month_key]
            month_name = datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")
            
            with st.expander(f"📅 {month_name} - Income: ${stats['income']:,.0f} | Expenses: ${stats['expenses']:,.0f}", expanded=True):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("💰 Income", f"${stats['income']:,.0f}")
                with col2:
                    st.metric("💸 Expenses", f"${stats['expenses']:,.0f}")
                with col3:
                    net = stats['income'] - stats['expenses']
                    st.metric("💎 Net", f"${net:,.0f}", delta="Positive" if net > 0 else "Negative")
                
                # Category breakdown
                st.markdown("**Spending by Category:**")
                for cat, amount in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
                    budget_amt = categories.get(cat, 0)
                    pct = (amount / budget_amt * 100) if budget_amt > 0 else 0
                    
                    col_a, col_b, col_c = st.columns([2, 1, 1])
                    with col_a:
                        st.write(f"**{cat}**")
                    with col_b:
                        st.write(f"${amount:,.0f}")
                    with col_c:
                        if pct > 100:
                            st.error(f"⚠️ {pct:.0f}%")
                        elif pct > 80:
                            st.warning(f"⚡ {pct:.0f}%")
                        else:
                            st.success(f"✅ {pct:.0f}%")
    else:
        st.info("No monthly data yet. Upload statements or add transactions!")

# TAB 2: TRENDS
with tab2:
    st.markdown("### 📈 Spending Trends")
    
    if len(monthly_stats) >= 2:
        # Prepare data for charts
        months = sorted(monthly_stats.keys())
        income_data = [monthly_stats[m]['income'] for m in months]
        expense_data = [monthly_stats[m]['expenses'] for m in months]
        month_labels = [datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in months]
        
        # Line chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=month_labels, y=income_data, mode='lines+markers', name='Income', line=dict(color='#51CF66', width=3)))
        fig.add_trace(go.Scatter(x=month_labels, y=expense_data, mode='lines+markers', name='Expenses', line=dict(color='#FF6B6B', width=3)))
        fig.update_layout(
            title='Income vs Expenses Over Time',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#E0E0E0'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Insights
        if len(months) >= 2:
            latest_month = months[-1]
            prev_month = months[-2]
            
            latest_expenses = monthly_stats[latest_month]['expenses']
            prev_expenses = monthly_stats[prev_month]['expenses']
            
            change = latest_expenses - prev_expenses
            change_pct = (change / prev_expenses * 100) if prev_expenses > 0 else 0
            
            if change > 0:
                st.warning(f"📈 Spending increased by ${change:,.0f} ({change_pct:.1f}%) from last month")
            else:
                st.success(f"📉 Spending decreased by ${abs(change):,.0f} ({abs(change_pct):.1f}%) from last month")
    else:
        st.info("Need at least 2 months of data to show trends. Keep tracking!")

# TAB 3: ALL TRANSACTIONS
with tab3:
    st.markdown("### 🏦 All Transactions")
    
    if user_data['bank_transactions']:
        df = pd.DataFrame(user_data['bank_transactions'])
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        csv = df.to_csv(index=False)
        st.download_button("📥 Export CSV", csv, "transactions.csv", "text/csv")
    else:
        st.info("No transactions yet!")

# Footer
st.divider()
st.markdown(f"""
<div style='text-align: center; color: #666;'>
    <p>💰 Finance Recon Pro v4.0 | {current_user} | {len(user_data['bank_transactions'])} transactions</p>
</div>
""", unsafe_allow_html=True)
