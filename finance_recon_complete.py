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
import time

# Supabase client
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    st.error("⚠️ Supabase library not installed. Add 'supabase' to requirements.txt")

# --- PAGE CONFIG ---
st.set_page_config(page_title="D.E.V.I.N - Finance Tracker", layout="wide", page_icon="👍")

# Custom CSS
st.markdown("""
<style>
    .stApp { 
        background: linear-gradient(135deg, #0E1117 0%, #1a1f2e 100%);
        color: #E0E0E0; 
    }
    h1 {
        background: linear-gradient(90deg, #00D9FF 0%, #7B2CBF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    h2, h3 { color: #00D9FF; }
    [data-testid="stMetricValue"] { font-size: 2rem; font-weight: 700; }
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
    .login-box {
        max-width: 450px;
        margin: 80px auto;
        padding: 40px;
        background: linear-gradient(145deg, #1e2530 0%, #252d3d 100%);
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }
    .devin-logo {
        text-align: center;
        margin-bottom: 30px;
    }
    .devin-title {
        font-size: 3.5rem;
        font-weight: 900;
        background: linear-gradient(90deg, #00D9FF 0%, #7B2CBF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 0.5rem;
        margin: 10px 0 5px 0;
    }
    .devin-subtitle {
        font-size: 0.95rem;
        color: #888;
        font-weight: 500;
        letter-spacing: 0.1rem;
        margin: 0;
    }
    .thumbs-up-container {
        display: flex;
        justify-content: center;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

def render_devin_logo():
    """Render D.E.V.I.N logo with thumbs up SVG"""
    svg_thumbs_up = """
    <svg width="120" height="120" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
        <!-- Gradient definition -->
        <defs>
            <linearGradient id="thumbGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#00D9FF;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#7B2CBF;stop-opacity:1" />
            </linearGradient>
            <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
        </defs>
        
        <!-- Thumbs up hand -->
        <g transform="translate(60, 60)">
            <!-- Thumb -->
            <path d="M -15,-25 Q -20,-35 -10,-40 Q 0,-42 5,-35 L 10,-15 L 5,-10 L -15,-10 Z" 
                  fill="url(#thumbGradient)" filter="url(#glow)" stroke="#00D9FF" stroke-width="2"/>
            
            <!-- Palm/fingers base -->
            <rect x="-15" y="-10" width="25" height="35" rx="5" 
                  fill="url(#thumbGradient)" filter="url(#glow)" stroke="#00D9FF" stroke-width="2"/>
            
            <!-- Fingers -->
            <rect x="-12" y="25" width="5" height="15" rx="2.5" 
                  fill="url(#thumbGradient)" stroke="#00D9FF" stroke-width="1.5"/>
            <rect x="-5" y="25" width="5" height="18" rx="2.5" 
                  fill="url(#thumbGradient)" stroke="#00D9FF" stroke-width="1.5"/>
            <rect x="2" y="25" width="5" height="16" rx="2.5" 
                  fill="url(#thumbGradient)" stroke="#00D9FF" stroke-width="1.5"/>
            
            <!-- Shine effect -->
            <ellipse cx="-5" cy="0" rx="8" ry="12" fill="rgba(255,255,255,0.2)"/>
        </g>
        
        <!-- Sparkle effects -->
        <circle cx="25" cy="30" r="2" fill="#00D9FF" opacity="0.8">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite"/>
        </circle>
        <circle cx="90" cy="35" r="1.5" fill="#7B2CBF" opacity="0.8">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="2.5s" repeatCount="indefinite"/>
        </circle>
        <circle cx="70" cy="85" r="2" fill="#00D9FF" opacity="0.8">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="3s" repeatCount="indefinite"/>
        </circle>
    </svg>
    """
    
    logo_html = f"""
    <div class="devin-logo">
        <div class="thumbs-up-container">
            {svg_thumbs_up}
        </div>
        <h1 class="devin-title">D.E.V.I.N</h1>
        <p class="devin-subtitle">DAILY EXPENSE VERIFICATION INCOME NETWORK</p>
    </div>
    """
    
    st.markdown(logo_html, unsafe_allow_html=True)

# --- SUPABASE SETUP ---
@st.cache_resource
def init_supabase():
    """Initialize Supabase client"""
    if not SUPABASE_AVAILABLE:
        return None
    
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        st.error(f"Failed to connect to Supabase: {e}")
        return None

supabase = init_supabase()

# --- MINDEE CONFIG ---
try:
    mindee_api_key = os.getenv("MINDEE_API_KEY") or st.secrets.get("MINDEE_API_KEY", "")
except:
    mindee_api_key = ""

RECEIPT_MODEL_ID = "ea052ba3-d02e-482b-af10-3aeba53c7146"
BANK_STATEMENT_MODEL_ID = "77d71fe3-2547-482e-94b3-a3a6c3d97028"

# --- DATABASE FUNCTIONS ---
def get_or_create_user(username):
    """Get user ID or create new user"""
    if not supabase:
        return None
    
    # Check if user exists
    result = supabase.table('users').select('id').eq('username', username).execute()
    
    if result.data:
        return result.data[0]['id']
    else:
        # Create new user
        result = supabase.table('users').insert({'username': username}).execute()
        return result.data[0]['id']

def load_user_transactions(user_id):
    """Load all transactions for a user"""
    if not supabase or not user_id:
        return []
    
    result = supabase.table('transactions').select('*').eq('user_id', user_id).order('date', desc=True).execute()
    return result.data if result.data else []

def save_transaction(user_id, transaction):
    """Save a single transaction"""
    if not supabase or not user_id:
        return False
    
    data = {
        'user_id': user_id,
        'date': transaction['Date'],
        'vendor': transaction['Vendor'],
        'amount': float(transaction['Amount']),
        'category': transaction['Category'],
        'type': transaction['Type'],
        'notes': transaction.get('Notes', ''),
        'card_name': transaction.get('Card', '')
    }
    
    result = supabase.table('transactions').insert(data).execute()
    return bool(result.data)

def load_user_budget(user_id):
    """Load budget settings for a user"""
    if not supabase or not user_id:
        return {}
    
    result = supabase.table('budgets').select('*').eq('user_id', user_id).execute()
    
    if result.data:
        return {item['category']: float(item['amount']) for item in result.data}
    return {}

def save_user_budget(user_id, budget_dict):
    """Save budget settings for a user"""
    if not supabase or not user_id:
        return False
    
    # Delete existing budget
    supabase.table('budgets').delete().eq('user_id', user_id).execute()
    
    # Insert new budget
    data = [{'user_id': user_id, 'category': cat, 'amount': float(amt)} for cat, amt in budget_dict.items()]
    result = supabase.table('budgets').insert(data).execute()
    return bool(result.data)

# --- MINDEE API ---
def analyze_with_mindee(image_bytes, filename, api_key, model_id):
    """Call Mindee API v2"""
    enqueue_url = "https://api-v2.mindee.net/v2/products/extraction/enqueue"
    
    headers = {"Authorization": api_key}
    files = {"file": (filename, image_bytes, "image/jpeg")}
    data = {"model_id": model_id}
    
    response = requests.post(enqueue_url, headers=headers, files=files, data=data)
    
    if response.status_code not in [200, 201, 202]:
        raise Exception(f"API Error {response.status_code}: {response.text}")
    
    result = response.json()
    job_id = result.get('job', {}).get('id')
    
    if not job_id:
        raise Exception("No job ID returned")
    
    # Poll for results
    job_url = f"https://api-v2.mindee.net/v2/jobs/{job_id}"
    
    for attempt in range(60):
        time.sleep(1)
        poll_response = requests.get(job_url, headers=headers, params={"redirect": "false"})
        
        if poll_response.status_code == 200:
            poll_data = poll_response.json()
            job_status = poll_data.get('job', {}).get('status')
            
            if job_status == 'Processed':
                result_url = poll_data.get('job', {}).get('result_url')
                if result_url:
                    result_response = requests.get(result_url, headers=headers)
                    if result_response.status_code == 200:
                        return result_response.json()
                raise Exception("Result URL not available")
            elif job_status == 'Failed':
                error = poll_data.get('job', {}).get('error', {})
                raise Exception(f"Processing failed: {error}")
    
    raise Exception("Timeout (60s)")

def categorize_transaction(description):
    """Auto-categorize based on merchant"""
    desc_lower = description.lower()
    
    # EXCLUDE payments first
    payment_keywords = ['payment thank you', 'automatic payment', 'online payment', 'autopay', 'payment received']
    if any(kw in desc_lower for kw in payment_keywords):
        return 'PAYMENT_EXCLUDE'
    
    # Groceries
    if any(word in desc_lower for word in ['costco whse', 'walmart', 'target', 'vons', 'sprouts', 'trader joe', 'whole foods', 'aldi', 'safeway', 'stater bros']):
        return "Groceries"
    # Dining Out
    elif any(word in desc_lower for word in ['chipotle', 'chick-fil-a', 'shake shack', 'starbucks', 'mcdonald', 'in-n-out', 'panda express', 'wendy', 'p.f.chang', 'pizza', 'taco', 'burger', 'subway', 'restaurant', 'cafe']):
        return "Dining Out"
    # Gas
    elif any(word in desc_lower for word in ['gas', 'fuel', 'shell', 'chevron', 'exxon', 'mobil', 'costco gas', 'vons fuel']):
        return "Gas/Fuel"
    # Entertainment
    elif any(word in desc_lower for word in ['netflix', 'cinema', 'movie', 'theater', 'spotify', 'hulu']):
        return "Entertainment"
    # Home
    elif any(word in desc_lower for word in ['home depot', 'lowes', 'ace hardware']):
        return "Rent/Mortgage"
    # Healthcare
    elif any(word in desc_lower for word in ['pharmacy', 'cvs', 'walgreens', 'kaiser', 'medical']):
        return "Healthcare"
    else:
        return "Groceries"  # Default

# --- LOGIN ---
MASTER_PASSWORD = "922626"

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

def login_page():
    """Display login"""
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    
    # Render D.E.V.I.N logo
    render_devin_logo()
    
    st.markdown("### Welcome! Please login")
    
    with st.form("login_form"):
        username = st.text_input("👤 Your Name", placeholder="Enter your name")
        password = st.text_input("🔐 Access Code", type="password", placeholder="922626")
        
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
                # Get or create user
                user_id = get_or_create_user(username)
                
                if user_id:
                    st.session_state.authenticated = True
                    st.session_state.current_user = username
                    st.session_state.user_id = user_id
                    st.success(f"✅ Welcome, {username}!")
                    st.rerun()
                else:
                    st.error("Database connection failed")
    
    st.markdown("</div>", unsafe_allow_html=True)

if not st.session_state.authenticated:
    login_page()
    st.stop()

# --- MAIN APP ---
user_id = st.session_state.user_id
current_user = st.session_state.current_user

# Load data from Supabase
transactions = load_user_transactions(user_id)
saved_budget = load_user_budget(user_id)

# Convert transactions to list of dicts
transaction_list = []
for t in transactions:
    transaction_list.append({
        'Date': t['date'],
        'Vendor': t['vendor'],
        'Amount': float(t['amount']),
        'Category': t['category'],
        'Type': t['type'],
        'Notes': t['notes'],
        'Card': t.get('card_name', '')
    })

# Sidebar
with st.sidebar:
    st.markdown(f"# 🎯 {current_user}'s Dashboard")
    
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.session_state.user_id = None
        st.rerun()
    
    st.divider()
    
    if not mindee_api_key:
        st.warning("⚠️ Set MINDEE_API_KEY")
        mindee_api_key = st.text_input("API Key:", type="password")
    
    st.divider()
    st.markdown("### 💰 Income")
    total_income = st.number_input("Monthly Income", value=0, step=100)
    
    st.divider()
    st.markdown("### 📊 Budget")
    
    categories = {}
    
    with st.expander("🏠 Housing"):
        categories["Rent/Mortgage"] = st.slider("Rent/Mortgage", 0, 5000, saved_budget.get("Rent/Mortgage", 0), 50)
        categories["Utilities"] = st.slider("Utilities", 0, 500, saved_budget.get("Utilities", 0), 10)
    
    with st.expander("🚗 Transportation"):
        categories["Car Payment"] = st.slider("Car Payment", 0, 1000, saved_budget.get("Car Payment", 0), 25)
        categories["Gas/Fuel"] = st.slider("Gas/Fuel", 0, 500, saved_budget.get("Gas/Fuel", 0), 10)
        categories["Insurance"] = st.slider("Insurance", 0, 500, saved_budget.get("Insurance", 0), 10)
    
    with st.expander("🍎 Food"):
        categories["Groceries"] = st.slider("Groceries", 0, 1000, saved_budget.get("Groceries", 0), 25)
        categories["Dining Out"] = st.slider("Dining Out", 0, 500, saved_budget.get("Dining Out", 0), 25)
    
    with st.expander("💳 Debt & Savings"):
        categories["Credit Cards"] = st.slider("Credit Cards", 0, 1000, saved_budget.get("Credit Cards", 0), 25)
        categories["Savings"] = st.slider("Savings", 0, 2000, saved_budget.get("Savings", 0), 50)
    
    with st.expander("🎯 Lifestyle"):
        categories["Entertainment"] = st.slider("Entertainment", 0, 300, saved_budget.get("Entertainment", 0), 10)
        categories["Tech/AI"] = st.slider("Tech/AI", 0, 300, saved_budget.get("Tech/AI", 0), 10)
        categories["Healthcare"] = st.slider("Healthcare", 0, 500, saved_budget.get("Healthcare", 0), 25)
        categories["Personal Care"] = st.slider("Personal Care", 0, 300, saved_budget.get("Personal Care", 0), 25)
    
    # Save budget button
    if st.button("💾 Save Budget", use_container_width=True):
        if save_user_budget(user_id, categories):
            st.success("✅ Budget saved!")
        else:
            st.error("Failed to save budget")
    
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

# Main content
st.markdown(f"# 👍 D.E.V.I.N - {current_user}'s Dashboard")
st.markdown("*Daily Expense Verification Income Network* | Data persists forever! ✅")

# Metrics
total_spent = sum([t['Amount'] for t in transaction_list if t['Type'] == 'Expense'])
total_earned = sum([t['Amount'] for t in transaction_list if t['Type'] == 'Income'])
net_savings = total_earned - total_spent

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("💰 Total Income", f"${total_earned:,.0f}")
with col2:
    st.metric("💸 Total Spent", f"${total_spent:,.0f}")
with col3:
    st.metric("📊 Net Savings", f"${net_savings:,.0f}")
with col4:
    st.metric("📝 Transactions", len(transaction_list))

st.divider()

# Tabs
tab1, tab2, tab3 = st.tabs(["🏦 Transactions", "📊 Analytics", "📤 Upload Statement"])

with tab1:
    st.markdown("### 🏦 All Transactions")
    
    if transaction_list:
        df = pd.DataFrame(transaction_list)
        st.dataframe(df, use_container_width=True, hide_index=True, height=400)
        
        csv = df.to_csv(index=False)
        st.download_button("📥 Export CSV", csv, "transactions.csv", "text/csv")
    else:
        st.info("No transactions yet! Upload a statement to get started.")

with tab2:
    st.markdown("### 📊 Spending Analytics")
    
    if transaction_list:
        df = pd.DataFrame(transaction_list)
        expenses = df[df['Type'] == 'Expense']
        
        if not expenses.empty:
            category_totals = expenses.groupby('Category')['Amount'].sum().reset_index()
            
            fig = px.pie(category_totals, values='Amount', names='Category', title='💰 Spending by Category', hole=0.4)
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#E0E0E0')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Add transactions to see analytics!")

with tab3:
    st.markdown("### 📤 Upload Bank/Credit Card Statement")
    
    st.markdown("**Name this account:**")
    card_name = st.text_input("Account name (e.g., 'Wells Fargo Credit', 'Chase Sapphire')", "")
    
    uploaded_file = st.file_uploader("Upload statement", type=['pdf', 'png', 'jpg', 'jpeg'])
    
    if uploaded_file and card_name:
        if st.button("🤖 Analyze Statement", type="primary"):
            if not mindee_api_key:
                st.error("⚠️ Mindee API key required!")
            else:
                try:
                    with st.spinner("🔍 Analyzing..."):
                        result = analyze_with_mindee(uploaded_file.getvalue(), uploaded_file.name, mindee_api_key, BANK_STATEMENT_MODEL_ID)
                        
                        # Extract
                        inference = result.get('inference', {})
                        result_data = inference.get('result', {})
                        fields = result_data.get('fields', {})
                        line_items_obj = fields.get('line_items', {})
                        line_items_array = line_items_obj.get('items', [])
                        
                        parsed = []
                        
                        for item in line_items_array:
                            if isinstance(item, dict):
                                item_fields = item.get('fields', {})
                                desc = item_fields.get('description', {}).get('value', 'Unknown')
                                amount = item_fields.get('total_price', {}).get('value', 0.0)
                                
                                if not desc or amount is None:
                                    continue
                                
                                category = categorize_transaction(desc)
                                
                                # Skip payments
                                if category == 'PAYMENT_EXCLUDE':
                                    continue
                                
                                trans_type = "Expense"
                                
                                parsed.append({
                                    'description': desc,
                                    'amount': abs(amount),
                                    'category': category,
                                    'type': trans_type
                                })
                        
                        st.success(f"✅ Found {len(parsed)} transactions!")
                        
                        if parsed:
                            df_preview = pd.DataFrame(parsed)
                            st.dataframe(df_preview.head(20), use_container_width=True, hide_index=True)
                            
                            if st.button(f"💾 Save All {len(parsed)} Transactions to Database", type="primary"):
                                saved_count = 0
                                for trans in parsed:
                                    transaction = {
                                        "Date": datetime.now().strftime("%Y-%m-%d"),
                                        "Vendor": trans['description'],
                                        "Amount": trans['amount'],
                                        "Category": trans['category'],
                                        "Type": trans['type'],
                                        "Notes": f"Auto-imported from {card_name}",
                                        "Card": card_name
                                    }
                                    if save_transaction(user_id, transaction):
                                        saved_count += 1
                                
                                st.success(f"🎉 Saved {saved_count} transactions to database!")
                                st.balloons()
                                time.sleep(2)
                                st.rerun()
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# Footer
st.divider()
st.markdown(f"""
<div style='text-align: center; color: #666;'>
    <p>👍 <b>D.E.V.I.N</b> - Daily Expense Verification Income Network</p>
    <p style='font-size: 0.9em;'>{current_user} | {len(transaction_list)} transactions | 🗄️ Powered by Supabase & Mindee AI</p>
</div>
""", unsafe_allow_html=True)
