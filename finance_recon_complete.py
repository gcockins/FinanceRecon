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

# Try to import Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# --- PAGE CONFIG ---
st.set_page_config(page_title="D.E.V.I.N - Finance Tracker", layout="wide", page_icon="👍")

# Custom CSS
st.markdown("""
<style>
    /* Main theme - matching logo's light blue background */
    .stApp { 
        background: linear-gradient(135deg, #C8DCE8 0%, #E8F4F8 100%);
        color: #1a2332; 
    }
    
    /* Headers - Navy blue matching suit */
    h1 {
        color: #2C3E50;
        font-weight: 800;
    }
    
    h2, h3 { 
        color: #1a2332;
        font-weight: 700;
    }
    
    /* Metrics - Gold matching tie */
    [data-testid="stMetricValue"] { 
        font-size: 2rem; 
        font-weight: 700;
        color: #FFB84D;
    }
    
    [data-testid="stMetricLabel"] {
        color: #2C3E50;
        font-weight: 600;
    }
    
    /* Buttons - Gold gradient matching tie */
    .stButton>button {
        background: linear-gradient(90deg, #FFB84D 0%, #F4A460 100%);
        color: #1a2332;
        border: none;
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 700;
        transition: all 0.3s;
        box-shadow: 0 4px 6px rgba(44, 62, 80, 0.2);
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(255, 184, 77, 0.5);
        background: linear-gradient(90deg, #F4A460 0%, #FFB84D 100%);
    }
    
    /* Login box - Professional card on light background */
    .login-box {
        max-width: 500px;
        margin: 50px auto;
        padding: 40px;
        background: white;
        border-radius: 20px;
        box-shadow: 0 10px 40px rgba(44, 62, 80, 0.15);
        border: 2px solid rgba(255, 184, 77, 0.3);
    }
    
    /* Progress bars - Gold */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #FFB84D 0%, #F4A460 100%);
    }
    
    /* Sidebar - Navy blue matching suit */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2C3E50 0%, #34495e 100%);
        color: white;
    }
    
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] label {
        color: white !important;
    }
    
    /* Input fields - Light with navy border */
    .stTextInput input, .stNumberInput input {
        background-color: white;
        border: 2px solid #2C3E50;
        color: #1a2332;
    }
    
    /* Sliders */
    .stSlider > div > div > div > div {
        background-color: #FFB84D;
    }
    
    /* Tabs - Professional look */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: white;
        border-radius: 10px 10px 0 0;
        color: #2C3E50;
        font-weight: 600;
        border: 2px solid #E8F4F8;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #FFB84D 0%, #F4A460 100%);
        color: #1a2332;
        border-color: #FFB84D;
    }
    
    /* Cards/Containers */
    .element-container {
        background-color: transparent;
    }
    
    /* Dataframes */
    .stDataFrame {
        background-color: white;
        border-radius: 10px;
    }
    
    /* Warning/Info boxes */
    .stAlert {
        background-color: white;
        border-left: 4px solid #FFB84D;
        color: #1a2332;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        background-color: rgba(255, 184, 77, 0.1);
        border-radius: 10px;
        color: #2C3E50;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- SUPABASE SETUP ---
@st.cache_resource
def init_supabase():
    """Initialize Supabase client with fallback"""
    if not SUPABASE_AVAILABLE:
        return None
    
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
        client = create_client(supabase_url, supabase_key)
        return client
    except:
        return None

supabase = init_supabase()
USE_DATABASE = supabase is not None

# Show connection status in sidebar
if USE_DATABASE:
    st.sidebar.success("🗄️ Database Connected")
else:
    st.sidebar.warning("⚠️ Demo Mode (No Database)")

def render_devin_logo(size="large"):
    """Render D.E.V.I.N logo - full on login, small on dashboard"""
    import base64
    
    # Try multiple paths (GitHub repo, then uploads as fallback)
    logo_paths = ["Devin.png", "devin_logo.png", "/mnt/user-data/uploads/Devin.png"]
    logo_data = None
    
    for path in logo_paths:
        try:
            with open(path, "rb") as f:
                logo_data = base64.b64encode(f.read()).decode()
                break
        except:
            continue
    
    if not logo_data:
        # Fallback if image not found - show emoji version
        st.markdown("""
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="font-size: 4rem;">💼</div>
            <h1 style="font-size: 3.5rem; font-weight: 900; background: linear-gradient(90deg, #FFB84D 0%, #F4A460 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: 0.5rem; margin: 10px 0 5px 0;">D.E.V.I.N</h1>
            <p style="font-size: 0.95rem; color: #FFB84D; font-weight: 600; letter-spacing: 0.1rem; margin: 0;">DAILY EXPENSE VERIFICATION INCOME NETWORK</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    if size == "large":
        # Full logo for login page
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 30px;">
            <img src="data:image/png;base64,{logo_data}" style="width: 100%; max-width: 400px; height: auto; margin: 0 auto; display: block; border-radius: 15px; box-shadow: 0 8px 20px rgba(255, 184, 77, 0.3);">
        </div>
        """, unsafe_allow_html=True)
    else:
        # Small logo for dashboard
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="data:image/png;base64,{logo_data}" style="width: 150px; height: auto; margin: 0 auto; display: block; border-radius: 10px; box-shadow: 0 4px 10px rgba(255, 184, 77, 0.2);">
        </div>
        """, unsafe_allow_html=True)

# --- MINDEE CONFIG ---
try:
    mindee_api_key = os.getenv("MINDEE_API_KEY") or st.secrets.get("MINDEE_API_KEY", "")
except:
    mindee_api_key = ""

BANK_STATEMENT_MODEL_ID = "77d71fe3-2547-482e-94b3-a3a6c3d97028"

# --- DATABASE FUNCTIONS (Hybrid Mode) ---
def get_or_create_user(username):
    """Get/create user - works with or without database"""
    if USE_DATABASE:
        try:
            result = supabase.table('users').select('id').eq('username', username).execute()
            if result.data:
                return result.data[0]['id']
            else:
                result = supabase.table('users').insert({'username': username}).execute()
                return result.data[0]['id']
        except:
            pass
    return username  # Fallback to username as ID

def load_user_transactions(user_id):
    """Load transactions - database or session"""
    if USE_DATABASE:
        try:
            result = supabase.table('transactions').select('*').eq('user_id', user_id).order('date', desc=True).execute()
            if result.data:
                return [{'Date': t['date'], 'Vendor': t['vendor'], 'Amount': float(t['amount']), 
                        'Category': t['category'], 'Type': t['type'], 'Notes': t['notes'], 
                        'Card': t.get('card_name', '')} for t in result.data]
        except:
            pass
    return st.session_state.all_user_data.get(user_id, {}).get('transactions', [])

def save_transaction(user_id, transaction):
    """Save transaction - database or session"""
    if USE_DATABASE:
        try:
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
            supabase.table('transactions').insert(data).execute()
            return True
        except:
            pass
    
    # Fallback to session
    if user_id not in st.session_state.all_user_data:
        st.session_state.all_user_data[user_id] = {'transactions': [], 'budget': {}}
    st.session_state.all_user_data[user_id]['transactions'].append(transaction)
    return True

def load_user_budget(user_id):
    """Load budget - database or session"""
    if USE_DATABASE:
        try:
            result = supabase.table('budgets').select('*').eq('user_id', user_id).execute()
            if result.data:
                return {item['category']: float(item['amount']) for item in result.data}
        except:
            pass
    return st.session_state.all_user_data.get(user_id, {}).get('budget', {})

def save_user_budget(user_id, budget_dict):
    """Save budget - database or session"""
    if USE_DATABASE:
        try:
            supabase.table('budgets').delete().eq('user_id', user_id).execute()
            data = [{'user_id': user_id, 'category': cat, 'amount': float(amt)} for cat, amt in budget_dict.items()]
            supabase.table('budgets').insert(data).execute()
            return True
        except:
            pass
    
    # Fallback
    if user_id not in st.session_state.all_user_data:
        st.session_state.all_user_data[user_id] = {'transactions': [], 'budget': {}}
    st.session_state.all_user_data[user_id]['budget'] = budget_dict
    return True

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
if 'all_user_data' not in st.session_state:
    st.session_state.all_user_data = {}

def login_page():
    """Display login"""
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    
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
                st.session_state.authenticated = True
                st.session_state.current_user = username
                st.session_state.user_id = get_or_create_user(username)
                
                # Create user data if doesn't exist (for fallback mode)
                if username not in st.session_state.all_user_data:
                    st.session_state.all_user_data[username] = {
                        'transactions': [],
                        'budget': {}
                    }
                
                st.success(f"✅ Welcome, {username}!")
                st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.info("⚠️ Demo Mode: Data clears when you close the browser")

if not st.session_state.authenticated:
    login_page()
    st.stop()

# --- MAIN APP ---
current_user = st.session_state.current_user
user_id = st.session_state.user_id
user_data = st.session_state.all_user_data.get(current_user, {'transactions': [], 'budget': {}})

# Load from database if available
transactions = load_user_transactions(user_id)
saved_budget = load_user_budget(user_id)

# Sidebar
with st.sidebar:
    st.markdown(f"# 🎯 {current_user}'s Dashboard")
    
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.current_user = None
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
    
    # Save budget
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
render_devin_logo("small")
st.markdown(f"# {current_user}'s Financial Dashboard")
st.markdown("*Daily Expense Verification Income Network*")

if not USE_DATABASE:
    st.warning("⚠️ Demo Mode: Data is temporary and will be lost when you close the browser")
else:
    st.info("✅ Connected to Database: Your data is saved permanently!")

# Metrics
total_spent = sum([t['Amount'] for t in transactions if t['Type'] == 'Expense'])
total_earned = sum([t['Amount'] for t in transactions if t['Type'] == 'Income'])
net_savings = total_earned - total_spent

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("💰 Total Income", f"${total_earned:,.0f}")
with col2:
    st.metric("💸 Total Spent", f"${total_spent:,.0f}")
with col3:
    st.metric("📊 Net Savings", f"${net_savings:,.0f}")
with col4:
    st.metric("📝 Transactions", len(transactions))

st.divider()

# Tabs
tab1, tab2, tab3 = st.tabs(["🏦 Transactions", "📊 Analytics", "📤 Upload Statement"])

with tab1:
    st.markdown("### 🏦 All Transactions")
    
    if transactions:
        df = pd.DataFrame(transactions)
        st.dataframe(df, use_container_width=True, hide_index=True, height=400)
        
        csv = df.to_csv(index=False)
        st.download_button("📥 Export CSV", csv, "transactions.csv", "text/csv")
    else:
        st.info("No transactions yet! Upload a statement to get started.")

with tab2:
    st.markdown("### 📊 Spending Analytics")
    
    if transactions:
        df = pd.DataFrame(transactions)
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
                            
                            if st.button(f"💾 Add All {len(parsed)} Transactions", type="primary"):
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
                                
                                st.success(f"🎉 Added {saved_count} transactions!")
                                st.balloons()
                                time.sleep(2)
                                st.rerun()
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# Footer
st.divider()
st.markdown(f"""
<div style='text-align: center; color: #FFB84D;'>
    <p style='font-weight: 700; font-size: 1.1rem;'>💼 <b>D.E.V.I.N</b> - Daily Expense Verification Income Network</p>
    <p style='font-size: 0.9em; color: #95a5a6;'>{current_user} | {len(transactions)} transactions | 🤖 Powered by Mindee AI</p>
</div>
""", unsafe_allow_html=True)
