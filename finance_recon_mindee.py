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
import hashlib

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

# --- 3. LOGIN SYSTEM ---
MASTER_PASSWORD = "922626"

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'all_users_data' not in st.session_state:
    st.session_state.all_users_data = {}

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
                        'recurring_expenses': []
                    }
                    st.success(f"✅ Welcome {username}! New account created.")
                else:
                    st.success(f"✅ Welcome back, {username}!")
                
                st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("<div style='text-align: center; color: #666;'>", unsafe_allow_html=True)
    st.markdown("*Secure login with access code 🔒*")
    st.markdown("</div>", unsafe_allow_html=True)

# Show login page if not authenticated
if not st.session_state.authenticated:
    login_page()
    st.stop()

# --- 4. GET CURRENT USER DATA ---
current_user = st.session_state.current_user
user_data = st.session_state.all_users_data[current_user]

# --- 5. SIDEBAR - BUDGET CATEGORIES ---
with st.sidebar:
    st.markdown(f"# 🎯 {current_user}'s Dashboard")
    
    # Logout button
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.rerun()
    
    st.divider()
    
    # Mindee API Key Input
    if not mindee_api_key:
        st.warning("⚠️ Please set your MINDEE_API_KEY")
        mindee_api_key = st.text_input("Mindee API Key:", type="password")
    
    st.divider()
    
    # Income Section
    st.markdown("### 💰 Income Sources")
    p1 = st.number_input("💼 Paycheck A", value=0, step=100, help="Primary income source")
    p2 = st.number_input("💼 Paycheck B", value=0, step=100, help="Secondary income source")
    other_income = st.number_input("💵 Other Income", value=0, step=50, help="Side gigs, investments, etc.")
    total_income = p1 + p2 + other_income
    
    st.divider()
    
    # 15 Budget Categories
    st.markdown("### 📊 Budget Categories")
    
    categories = {}
    
    with st.expander("🏠 Housing & Utilities", expanded=False):
        categories["Rent/Mortgage"] = st.slider("Rent/Mortgage", 0, 5000, 0, 50)
        categories["Utilities"] = st.slider("Utilities", 0, 500, 0, 10)
        categories["Internet/Phone"] = st.slider("Internet/Phone", 0, 300, 0, 10)
    
    with st.expander("🚗 Transportation", expanded=False):
        categories["Car Payment"] = st.slider("Car Payment", 0, 1000, 0, 25)
        categories["Gas/Fuel"] = st.slider("Gas/Fuel", 0, 500, 0, 10)
        categories["Insurance"] = st.slider("Insurance", 0, 500, 0, 10)
    
    with st.expander("🍎 Food & Dining", expanded=False):
        categories["Groceries"] = st.slider("Groceries", 0, 1000, 0, 25)
        categories["Dining Out"] = st.slider("Dining Out", 0, 500, 0, 25)
    
    with st.expander("💳 Debt & Savings", expanded=False):
        categories["Credit Cards"] = st.slider("Credit Card Payments", 0, 1000, 0, 25)
        categories["Loans"] = st.slider("Loans", 0, 1000, 0, 25)
        categories["Savings"] = st.slider("Savings Goal", 0, 2000, 0, 50)
    
    with st.expander("🎯 Lifestyle", expanded=False):
        categories["Entertainment"] = st.slider("Entertainment", 0, 300, 0, 10)
        categories["Tech/AI"] = st.slider("Tech/AI", 0, 300, 0, 10)
        categories["Healthcare"] = st.slider("Healthcare", 0, 500, 0, 25)
        categories["Personal Care"] = st.slider("Personal Care", 0, 300, 0, 25)
    
    # Calculate totals
    total_budgeted = sum(categories.values())
    remaining = total_income - total_budgeted
    
    st.divider()
    
    # Financial Summary
    st.markdown("### 📈 Monthly Summary")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("💵 Income", f"${total_income:,.0f}")
        st.metric("📊 Budgeted", f"${total_budgeted:,.0f}")
    with col2:
        delta_color = "normal" if remaining >= 0 else "inverse"
        st.metric("💰 Remaining", f"${remaining:,.0f}", 
                 delta=f"{(remaining/total_income)*100:.1f}%" if total_income > 0 else "0%")
        budget_pct = (total_budgeted/total_income)*100 if total_income > 0 else 0
        if total_income > 0:
            st.progress(min(budget_pct/100, 1.0))
    
    # Budget health indicator
    if remaining < 0:
        st.error(f"⚠️ Over budget by ${abs(remaining):,.0f}")
    elif remaining < total_income * 0.1 and total_income > 0:
        st.warning(f"⚡ Tight budget: ${remaining:,.0f} buffer")
    elif total_income > 0:
        st.success(f"✅ Healthy budget: ${remaining:,.0f} buffer")

# --- 6. MAIN DASHBOARD ---
st.markdown(f"# 💰 {current_user}'s Finance Recon Pro")
st.markdown("*AI-Powered Receipt & Bank Statement Analysis*")

# Top-level metrics
col1, col2, col3, col4 = st.columns(4)

total_spent = sum([t['Amount'] for t in user_data['bank_transactions']])
avg_transaction = total_spent / len(user_data['bank_transactions']) if user_data['bank_transactions'] else 0

with col1:
    st.metric("📊 Total Spent", f"${total_spent:,.2f}", delta=f"-{(total_spent/total_budgeted*100):.1f}% of budget" if total_budgeted > 0 else "")
with col2:
    st.metric("📝 Transactions", len(user_data['bank_transactions']))
with col3:
    st.metric("💳 Avg Transaction", f"${avg_transaction:,.2f}")
with col4:
    days_left = (datetime(2025, 3, 1) - datetime.now()).days
    st.metric("📅 Days Left", f"{days_left} days", delta="Until month end")

st.divider()

# --- 7. TABS FOR DIFFERENT SECTIONS ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏦 Transactions", "📊 Analytics", "🎯 Goals", "🔄 Recurring", "📸 Receipts", "🏛️ Bank Statements"])

# ===== TAB 1: TRANSACTIONS =====
with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🏦 Transaction Ledger")
        
        if user_data['bank_transactions']:
            # Filter options
            filter_col1, filter_col2, filter_col3 = st.columns(3)
            with filter_col1:
                filter_category = st.selectbox("Filter by Category", ["All"] + list(categories.keys()))
            with filter_col2:
                filter_type = st.selectbox("Filter by Type", ["All", "Expense", "Income"])
            with filter_col3:
                sort_by = st.selectbox("Sort by", ["Date", "Amount", "Vendor"])
            
            # Filter transactions
            df = pd.DataFrame(user_data['bank_transactions'])
            if filter_category != "All":
                df = df[df['Category'] == filter_category]
            if filter_type != "All":
                df = df[df['Type'] == filter_type]
            
            # Sort
            if sort_by == "Date":
                df = df.sort_values('Date', ascending=False)
            elif sort_by == "Amount":
                df = df.sort_values('Amount', ascending=False)
            else:
                df = df.sort_values('Vendor')
            
            # Display
            st.dataframe(df, use_container_width=True, height=400, hide_index=True)
            
            # Export button
            csv = df.to_csv(index=False)
            st.download_button("📥 Export to CSV", csv, "transactions.csv", "text/csv", key='download-csv')
        else:
            st.info("📝 No transactions yet. Add your first transaction or upload a receipt!")
    
    with col2:
        st.markdown("### ➕ Add Transaction")
        
        with st.form("add_transaction", clear_on_submit=True):
            new_date = st.date_input("Date", datetime.now())
            new_vendor = st.text_input("Vendor/Description")
            new_amount = st.number_input("Amount ($)", min_value=0.01, step=0.01, format="%.2f")
            new_category = st.selectbox("Category", list(categories.keys()))
            new_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
            new_notes = st.text_area("Notes (optional)", max_chars=200)
            
            if st.form_submit_button("✅ Add", use_container_width=True):
                if new_vendor:
                    user_data['bank_transactions'].append({
                        "Date": new_date.strftime("%m/%d/%Y"),
                        "Vendor": new_vendor,
                        "Amount": new_amount,
                        "Category": new_category,
                        "Type": new_type,
                        "Notes": new_notes
                    })
                    st.success(f"✅ Added: {new_vendor} - ${new_amount:.2f}")
                    st.rerun()
        
        # Quick stats
        if user_data['bank_transactions']:
            st.markdown("### 📊 Quick Stats")
            df_stats = pd.DataFrame(user_data['bank_transactions'])
            category_totals = df_stats.groupby('Category')['Amount'].sum().sort_values(ascending=False).head(3)
            
            st.markdown("**Top 3 Categories:**")
            for cat, amount in category_totals.items():
                st.markdown(f"• {cat}: **${amount:.2f}**")

# ===== TAB 2: ANALYTICS =====
with tab2:
    st.markdown("### 📊 Spending Analytics")
    
    if user_data['bank_transactions']:
        df_analytics = pd.DataFrame(user_data['bank_transactions'])
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Pie chart
            category_spending = df_analytics[df_analytics['Type'] == 'Expense'].groupby('Category')['Amount'].sum().reset_index()
            
            if not category_spending.empty:
                fig_pie = px.pie(category_spending, values='Amount', names='Category', title='💰 Spending by Category', hole=0.4, color_discrete_sequence=px.colors.sequential.Plasma)
                fig_pie.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#E0E0E0')
                st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # Bar chart
            budget_vs_actual = []
            for cat, budget in categories.items():
                actual = df_analytics[df_analytics['Category'] == cat]['Amount'].sum()
                if actual > 0:
                    budget_vs_actual.append({'Category': cat, 'Budgeted': budget, 'Actual': actual})
            
            if budget_vs_actual:
                df_budget = pd.DataFrame(budget_vs_actual)
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(name='Budgeted', x=df_budget['Category'], y=df_budget['Budgeted'], marker_color='#00D9FF'))
                fig_bar.add_trace(go.Bar(name='Actual', x=df_budget['Category'], y=df_budget['Actual'], marker_color='#7B2CBF'))
                fig_bar.update_layout(title='📊 Budget vs Actual', barmode='group', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#E0E0E0', xaxis_tickangle=-45)
                st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("📊 Add some transactions to see analytics!")

# ===== TAB 3: FINANCIAL GOALS =====
with tab3:
    st.markdown("### 🎯 Financial Goals")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if user_data['financial_goals']:
            for goal in user_data['financial_goals']:
                progress = (goal['Current'] / goal['Target'] * 100) if goal['Target'] > 0 else 0
                
                st.markdown(f"#### {goal['Goal']}")
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.progress(min(progress / 100, 1.0))
                    st.markdown(f"${goal['Current']:,.0f} / ${goal['Target']:,.0f} ({progress:.1f}%)")
                with col_b:
                    st.markdown(f"**Deadline:** {goal['Deadline']}")
                
                st.divider()
        else:
            st.info("🎯 No goals yet. Add your first financial goal!")
    
    with col2:
        st.markdown("### ➕ Add New Goal")
        
        with st.form("add_goal"):
            goal_name = st.text_input("Goal Name")
            goal_target = st.number_input("Target Amount ($)", min_value=1, step=100)
            goal_current = st.number_input("Current Amount ($)", min_value=0, step=50)
            goal_deadline = st.date_input("Deadline", datetime.now() + timedelta(days=365))
            
            if st.form_submit_button("✅ Add Goal", use_container_width=True):
                if goal_name:
                    user_data['financial_goals'].append({
                        "Goal": goal_name,
                        "Target": goal_target,
                        "Current": goal_current,
                        "Deadline": goal_deadline.strftime("%m/%d/%Y")
                    })
                    st.success(f"✅ Added goal: {goal_name}")
                    st.rerun()

# ===== TAB 4: RECURRING EXPENSES =====
with tab4:
    st.markdown("### 🔄 Recurring Expenses")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if user_data['recurring_expenses']:
            df_recurring = pd.DataFrame(user_data['recurring_expenses'])
            monthly_recurring = df_recurring[df_recurring['Frequency'] == 'Monthly']['Amount'].sum()
            
            st.metric("📅 Monthly Recurring Total", f"${monthly_recurring:,.2f}")
            st.dataframe(df_recurring, use_container_width=True, hide_index=True, height=300)
        else:
            st.info("🔄 No recurring expenses set up yet.")
    
    with col2:
        st.markdown("### ➕ Add Recurring Expense")
        
        with st.form("add_recurring"):
            rec_name = st.text_input("Name")
            rec_amount = st.number_input("Amount ($)", min_value=0.01, step=1.00)
            rec_frequency = st.selectbox("Frequency", ["Monthly", "Weekly", "Yearly"])
            rec_category = st.selectbox("Category", list(categories.keys()))
            rec_next_due = st.date_input("Next Due Date", datetime.now() + timedelta(days=30))
            
            if st.form_submit_button("✅ Add", use_container_width=True):
                if rec_name:
                    user_data['recurring_expenses'].append({
                        "Name": rec_name,
                        "Amount": rec_amount,
                        "Frequency": rec_frequency,
                        "Category": rec_category,
                        "Next_Due": rec_next_due.strftime("%m/%d/%Y")
                    })
                    st.success(f"✅ Added: {rec_name}")
                    st.rerun()

# ===== TAB 5: RECEIPTS =====
with tab5:
    st.markdown("### 📸 AI Receipt Scanner (Powered by Mindee)")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 📤 Upload & Analyze Receipt")
        uploaded_file = st.file_uploader("Upload receipt image", type=['png', 'jpg', 'jpeg', 'pdf'], help="Upload a photo or PDF of your receipt")
        
        if uploaded_file:
            if uploaded_file.type != "application/pdf":
                img = Image.open(uploaded_file)
                st.image(img, caption="Receipt Preview", use_container_width=True)
            else:
                st.info("📄 PDF uploaded - Ready to analyze!")
            
            if st.button("🤖 Analyze Receipt with AI", type="primary", use_container_width=True):
                if not mindee_api_key:
                    st.error("⚠️ Please provide your Mindee API key first!")
                else:
                    try:
                        with st.spinner("🔍 Analyzing receipt with AI..."):
                            result = analyze_with_mindee(uploaded_file.getvalue(), uploaded_file.name, mindee_api_key, RECEIPT_MODEL_ID)
                            
                            # Extract data
                            inference = result.get('inference', {})
                            result_data = inference.get('result', {})
                            fields = result_data.get('fields', {})
                            
                            vendor = fields.get('supplier_name', {}).get('value', 'Unknown')
                            total = float(fields.get('total_amount', {}).get('value', 0.0) or 0.0)
                            date_str = fields.get('date', {}).get('value')
                            
                            # Date formatting
                            if date_str:
                                try:
                                    date_obj = datetime.strptime(str(date_str), "%Y-%m-%d")
                                    date_formatted = date_obj.strftime("%m/%d/%Y")
                                except:
                                    date_formatted = datetime.now().strftime("%m/%d/%Y")
                                    date_obj = datetime.now()
                            else:
                                date_formatted = datetime.now().strftime("%m/%d/%Y")
                                date_obj = datetime.now()
                            
                            # Extract line items
                            items = []
                            if 'line_items' in fields:
                                line_items_obj = fields['line_items']
                                line_items_array = line_items_obj.get('items', [])
                                
                                for item in line_items_array:
                                    if isinstance(item, dict):
                                        item_fields = item.get('fields', {})
                                        desc = item_fields.get('description', {}).get('value', 'Item')
                                        price = item_fields.get('total_price', {}).get('value') or item_fields.get('unit_price', {}).get('value', 0.0)
                                        qty = item_fields.get('quantity', {}).get('value', 1)
                                        if desc:
                                            items.append(f"{desc} (x{qty}): ${float(price):.2f}")
                            
                            # Display results
                            st.success("✅ Receipt analyzed successfully!")
                            st.markdown("### 🎯 Extracted Information:")
                            
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.metric("🏪 Vendor", vendor)
                                st.metric("📅 Date", date_formatted)
                            with col_b:
                                st.metric("💰 Total", f"${total:.2f}")
                            
                            if items:
                                st.markdown("**📝 Items:**")
                                for item in items:
                                    st.markdown(f"• {item}")
                            
                            # Category suggestion
                            suggested_category = "Groceries"
                            vendor_lower = vendor.lower() if vendor else ""
                            if any(word in vendor_lower for word in ['amazon', 'best buy', 'apple', 'target']):
                                suggested_category = "Tech/AI"
                            elif any(word in vendor_lower for word in ['shell', 'chevron', 'gas']):
                                suggested_category = "Gas/Fuel"
                            
                            # Save form
                            st.markdown("### ✍️ Confirm & Save")
                            with st.form("save_receipt"):
                                final_vendor = st.text_input("Vendor", value=vendor)
                                final_amount = st.number_input("Total ($)", value=float(total), step=0.01)
                                final_date = st.date_input("Date", value=date_obj)
                                final_category = st.selectbox("Category", list(categories.keys()), index=list(categories.keys()).index(suggested_category) if suggested_category in categories else 0)
                                
                                if st.form_submit_button("💾 Save to Transactions", use_container_width=True):
                                    user_data['bank_transactions'].append({
                                        "Date": final_date.strftime("%m/%d/%Y"),
                                        "Vendor": final_vendor,
                                        "Amount": final_amount,
                                        "Category": final_category,
                                        "Type": "Expense",
                                        "Notes": f"Auto-scanned - {len(items)} items"
                                    })
                                    
                                    # Save receipt
                                    if uploaded_file.type != "application/pdf":
                                        buffered = BytesIO()
                                        img.save(buffered, format="JPEG")
                                        img_bytes = buffered.getvalue()
                                    else:
                                        img_bytes = uploaded_file.getvalue()
                                    
                                    user_data['receipts'].append({
                                        "vendor": final_vendor,
                                        "amount": final_amount,
                                        "date": final_date.strftime("%m/%d/%Y"),
                                        "category": final_category,
                                        "items": items,
                                        "image": img_bytes,
                                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                                    })
                                    
                                    st.success("✅ Receipt saved!")
                                    st.rerun()
                    
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
    
    with col2:
        st.markdown("#### 📚 Saved Receipts")
        
        if user_data['receipts']:
            for receipt in reversed(user_data['receipts']):
                with st.expander(f"🧾 {receipt['vendor']} - ${receipt['amount']:.2f} ({receipt['date']})"):
                    try:
                        img_display = Image.open(BytesIO(receipt['image']))
                        st.image(img_display, use_container_width=True)
                    except:
                        st.info("📄 PDF receipt")
                    
                    st.markdown(f"**Category:** {receipt['category']}")
                    if receipt.get('items'):
                        st.markdown("**Items:**")
                        for item in receipt['items']:
                            st.markdown(f"• {item}")
        else:
            st.info("📸 No receipts yet. Upload one to get started!")

# ===== TAB 6: BANK STATEMENTS =====
with tab6:
    st.markdown("### 🏛️ Bank Statement Analyzer (Powered by Mindee)")
    
    st.markdown("""
    Upload your bank statement and let AI extract all transactions automatically!
    
    **Supported formats:** PDF, PNG, JPG
    """)
    
    uploaded_statement = st.file_uploader("Upload Bank Statement", type=['png', 'jpg', 'jpeg', 'pdf'], help="Upload your bank statement")
    
    if uploaded_statement:
        st.info(f"📄 {uploaded_statement.name} uploaded - Ready to analyze!")
        
        if st.button("🤖 Analyze Bank Statement", type="primary", use_container_width=True):
            if not mindee_api_key:
                st.error("⚠️ Please provide your Mindee API key first!")
            else:
                try:
                    with st.spinner("🔍 Analyzing bank statement with AI... This may take a moment."):
                        result = analyze_with_mindee(uploaded_statement.getvalue(), uploaded_statement.name, mindee_api_key, BANK_STATEMENT_MODEL_ID)
                        
                        st.success("✅ Bank statement analyzed!")
                        
                        # DEBUG - Show what we got
                        with st.expander("🔍 See Raw Data"):
                            st.json(result)
                        
                        st.info("💡 Bank statement data extracted! Review the fields above to see what was found.")
                        st.markdown("""
                        **Next steps:**
                        1. Check the raw data above
                        2. I'll help you parse transactions from it
                        3. We'll auto-add them to your ledger
                        """)
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# --- 8. FOOTER ---
st.divider()
st.markdown("---")
st.markdown(f"""
<div style='text-align: center; color: #666;'>
    <p>💡 <b>Logged in as:</b> {current_user} | <b>Transactions:</b> {len(user_data['bank_transactions'])}</p>
    <p style='font-size: 0.9em;'>💰 Finance Recon Pro v3.0 | Powered by Mindee AI</p>
    <p style='font-size: 0.8em;'>🔐 Your data is stored locally in this session</p>
</div>
""", unsafe_allow_html=True)