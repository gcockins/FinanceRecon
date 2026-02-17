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
import calendar
from PyPDF2 import PdfReader, PdfWriter

# Try to import Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# --- PAGE CONFIG ---
st.set_page_config(page_title="D.E.V.I.N - Finance Advisor", layout="wide", page_icon="💼")

# Custom CSS matching logo
st.markdown("""
<style>
    .stApp { 
        background: #F8FAFB;
        color: #1a2332; 
    }
    h1 { color: #2C3E50; font-weight: 800; }
    h2, h3 { color: #1a2332; font-weight: 700; }
    [data-testid="stMetricValue"] { font-size: 2rem; font-weight: 700; color: #FFB84D; }
    [data-testid="stMetricLabel"] { color: #2C3E50; font-weight: 600; }
    
    .stButton>button {
        background: linear-gradient(90deg, #FFB84D 0%, #F4A460 100%);
        color: #1a2332;
        border: none;
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 700;
        box-shadow: 0 4px 6px rgba(44, 62, 80, 0.2);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(255, 184, 77, 0.5);
    }
    
    .wizard-step {
        background: white;
        padding: 30px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(44, 62, 80, 0.1);
        margin: 20px 0;
        border-left: 5px solid #FFB84D;
    }
    
    .alert-warning {
        background: #FFF3CD;
        border-left: 4px solid #FFA500;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    
    .alert-danger {
        background: #FFE5E5;
        border-left: 4px solid #FF4444;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    
    .alert-success {
        background: #E5F5E5;
        border-left: 4px solid #44FF44;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    
    .progress-bar {
        background: #E0E0E0;
        border-radius: 10px;
        height: 20px;
        overflow: hidden;
    }
    
    .progress-fill {
        background: linear-gradient(90deg, #FFB84D 0%, #F4A460 100%);
        height: 100%;
        transition: width 0.3s;
    }
    
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
    
    /* Chart containers - white background for clarity */
    .js-plotly-plot, .plotly {
        background: white !important;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    /* DataFrame styling */
    .stDataFrame {
        background: white;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab"] {
        background: white;
        color: #2C3E50;
        border-radius: 8px 8px 0 0;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #FFB84D 0%, #F4A460 100%);
        color: #1a2332 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- SUPABASE SETUP ---
@st.cache_resource
def init_supabase():
    if not SUPABASE_AVAILABLE:
        return None
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
        return create_client(supabase_url, supabase_key)
    except:
        return None

supabase = init_supabase()
USE_DATABASE = supabase is not None

# --- CONSTANTS ---
AZURE_ENDPOINT = st.secrets.get("AZURE_ENDPOINT", "")
AZURE_KEY = st.secrets.get("AZURE_KEY", "")
MASTER_PASSWORD = "922626"

# --- SESSION STATE INIT ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'onboarding_complete' not in st.session_state:
    st.session_state.onboarding_complete = {}
if 'onboarding_step' not in st.session_state:
    st.session_state.onboarding_step = 4  # Start at Step 4
if 'onboarding_data' not in st.session_state:
    # Calculate which months to request
    today = datetime.now()
    
    # If we're in the first 2 weeks of the month, assume current month data isn't available yet
    if today.day <= 14:
        # Ask for previous 3 complete months
        months_to_request = []
        for i in range(1, 4):  # 1, 2, 3 months ago
            month_date = today - timedelta(days=today.day + 30*i)
            months_to_request.append({
                'date': month_date,
                'name': month_date.strftime("%B %Y"),
                'short_name': month_date.strftime("%b %Y")
            })
    else:
        # Current month is mostly complete, include it
        months_to_request = []
        for i in range(0, 3):  # 0, 1, 2 months ago
            month_date = today - timedelta(days=30*i)
            months_to_request.append({
                'date': month_date,
                'name': month_date.strftime("%B %Y"),
                'short_name': month_date.strftime("%b %Y")
            })
    
    st.session_state.onboarding_data = {
        'months_uploaded': {},
        'family_size': {'adults': 1, 'children': 0},
        'all_transactions': [],
        'requested_months': months_to_request,
        'signup_date': today.strftime("%Y-%m-%d")
    }
if 'all_user_data' not in st.session_state:
    st.session_state.all_user_data = {}

# --- LOGO FUNCTION ---
def render_devin_logo(size="large"):
    import base64
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
        st.markdown("""
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="font-size: 4rem;">💼</div>
            <h1 style="font-size: 3.5rem;">D.E.V.I.N</h1>
            <p style="color: #FFB84D;">DAILY EXPENSE VERIFICATION INCOME NETWORK</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    if size == "large":
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 30px;">
            <img src="data:image/png;base64,{logo_data}" style="width: 100%; max-width: 400px; border-radius: 15px; box-shadow: 0 8px 20px rgba(255, 184, 77, 0.3);">
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="data:image/png;base64,{logo_data}" style="width: 150px; border-radius: 10px; box-shadow: 0 4px 10px rgba(255, 184, 77, 0.2);">
        </div>
        """, unsafe_allow_html=True)

# --- DATABASE FUNCTIONS ---
def get_or_create_user(username):
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
    return username

def save_transaction(user_id, transaction):
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
    
    if user_id not in st.session_state.all_user_data:
        st.session_state.all_user_data[user_id] = {'transactions': [], 'budget': {}, 'goals': []}
    st.session_state.all_user_data[user_id]['transactions'].append(transaction)
    return True

def load_user_transactions(user_id):
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

def save_user_budget(user_id, budget_dict):
    if USE_DATABASE:
        try:
            supabase.table('budgets').delete().eq('user_id', user_id).execute()
            data = [{'user_id': user_id, 'category': cat, 'amount': float(amt)} for cat, amt in budget_dict.items()]
            supabase.table('budgets').insert(data).execute()
            return True
        except:
            pass
    
    if user_id not in st.session_state.all_user_data:
        st.session_state.all_user_data[user_id] = {'transactions': [], 'budget': {}, 'goals': []}
    st.session_state.all_user_data[user_id]['budget'] = budget_dict
    return True

def load_user_budget(user_id):
    if USE_DATABASE:
        try:
            result = supabase.table('budgets').select('*').eq('user_id', user_id).execute()
            if result.data:
                return {item['category']: float(item['amount']) for item in result.data}
        except:
            pass
    return st.session_state.all_user_data.get(user_id, {}).get('budget', {})

# --- AZURE DOCUMENT INTELLIGENCE API ---
def analyze_with_azure(pdf_bytes, filename):
    """
    Analyze PDF using Azure Document Intelligence
    Returns structured transaction data
    """
    if not AZURE_ENDPOINT or not AZURE_KEY:
        raise Exception("Azure credentials not configured in secrets")
    
    # Azure Document Intelligence endpoint
    analyze_url = f"{AZURE_ENDPOINT}/formrecognizer/documentModels/prebuilt-invoice:analyze?api-version=2023-07-31"
    
    headers = {
        "Content-Type": "application/pdf",
        "Ocp-Apim-Subscription-Key": AZURE_KEY
    }
    
    # Start analysis
    response = requests.post(analyze_url, headers=headers, data=pdf_bytes)
    
    if response.status_code != 202:
        raise Exception(f"Azure API Error {response.status_code}: {response.text}")
    
    # Get operation location for polling
    operation_location = response.headers.get("Operation-Location")
    if not operation_location:
        raise Exception("No operation location in response")
    
    # Poll for results (Azure processes async)
    poll_headers = {"Ocp-Apim-Subscription-Key": AZURE_KEY}
    
    for _ in range(60):  # Max 60 seconds
        time.sleep(2)
        poll_response = requests.get(operation_location, headers=poll_headers)
        
        if poll_response.status_code == 200:
            result = poll_response.json()
            status = result.get("status")
            
            if status == "succeeded":
                return result
            elif status == "failed":
                raise Exception(f"Azure analysis failed: {result.get('error', {}).get('message', 'Unknown error')}")
            # Status is "running" or "notStarted", continue polling
        else:
            raise Exception(f"Polling error {poll_response.status_code}")
    
    raise Exception("Azure analysis timeout after 60 seconds")

def extract_transactions_from_azure(azure_result):
    """
    Extract transactions from Azure Document Intelligence result
    Returns list of transaction dictionaries
    """
    transactions = []
    
    try:
        # Azure returns data in analyzeResult.documents[0].fields
        analyze_result = azure_result.get("analyzeResult", {})
        documents = analyze_result.get("documents", [])
        
        if not documents:
            # Try reading as generic document (line items)
            pages = analyze_result.get("pages", [])
            for page in pages:
                lines = page.get("lines", [])
                for line in lines:
                    content = line.get("content", "")
                    # Simple transaction detection
                    if content and any(char.isdigit() for char in content):
                        transactions.append({
                            'description': content,
                            'amount': 0.0,  # Will try to extract below
                            'category': 'Other'
                        })
        else:
            # Extract from structured invoice/receipt format
            doc = documents[0]
            fields = doc.get("fields", {})
            
            # Try to get line items
            items = fields.get("Items", {}).get("valueArray", [])
            
            for item in items:
                item_fields = item.get("valueObject", {})
                
                description = ""
                amount = 0.0
                
                # Try different field names Azure might use
                desc_field = item_fields.get("Description") or item_fields.get("ProductName") or item_fields.get("Item")
                if desc_field:
                    description = desc_field.get("content", "Unknown")
                
                amount_field = item_fields.get("Amount") or item_fields.get("Total") or item_fields.get("Price")
                if amount_field:
                    try:
                        amount = float(amount_field.get("content", "0").replace("$", "").replace(",", ""))
                    except:
                        amount = 0.0
                
                if description:
                    category = categorize_transaction(description)
                    if category != 'PAYMENT_EXCLUDE':
                        transactions.append({
                            'description': description,
                            'amount': abs(amount),
                            'category': category
                        })
        
    except Exception as e:
        st.error(f"Error extracting transactions: {str(e)}")
    
    return transactions

def categorize_transaction(description):
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in ['payment thank you', 'automatic payment', 'online payment']):
        return 'PAYMENT_EXCLUDE'
    if any(w in desc_lower for w in ['costco whse', 'walmart', 'target', 'vons', 'sprouts', 'trader joe', 'whole foods', 'aldi']):
        return "Groceries"
    elif any(w in desc_lower for w in ['chipotle', 'chick-fil-a', 'shake shack', 'starbucks', 'mcdonald', 'restaurant']):
        return "Dining Out"
    elif any(w in desc_lower for w in ['gas', 'fuel', 'shell', 'chevron']):
        return "Gas/Fuel"
    elif any(w in desc_lower for w in ['netflix', 'cinema', 'movie']):
        return "Entertainment"
    elif any(w in desc_lower for w in ['home depot', 'lowes']):
        return "Home"
    else:
        return "Other"

# --- PDF PAGE DETECTION ---
def find_transaction_pages(pdf_bytes):
    """
    Scan PDF to find pages with transactions, skip disclosure/info pages.
    Returns: list of page numbers (0-indexed)
    """
    try:
        pdf = PdfReader(BytesIO(pdf_bytes))
        transaction_pages = []
        
        # Keywords that indicate transaction pages
        transaction_keywords = [
            "PURCHASES",
            "TRANSACTIONS", 
            "PAYMENTS AND OTHER CREDITS",
            "FEES CHARGED",
            "TOTAL PURCHASES",
            "BEGINNING BALANCE",
            "ENDING BALANCE",
            "ACCOUNT ACTIVITY"
        ]
        
        # Keywords that indicate pages to skip
        skip_keywords = [
            "IMPORTANT DISCLOSURES",
            "PRIVACY NOTICE",
            "QUESTIONS?",
            "CUSTOMER SERVICE",
            "HOW TO CONTACT US",
            "TERMS AND CONDITIONS",
            "NOTICE TO CALIFORNIA RESIDENTS",
            "INTEREST CHARGES",
            "YOUR RIGHTS"
        ]
        
        st.info(f"📄 Scanning {len(pdf.pages)} pages for transactions...")
        
        for page_num, page in enumerate(pdf.pages):
            try:
                text = page.extract_text().upper()
                
                # Skip if it's a disclosure/info page
                skip_count = sum(1 for keyword in skip_keywords if keyword in text)
                transaction_count = sum(1 for keyword in transaction_keywords if keyword in text)
                
                # Keep page if it has transaction keywords and minimal skip keywords
                if transaction_count > 0 and skip_count <= 1:
                    transaction_pages.append(page_num)
                    st.success(f"✅ Page {page_num + 1}: Found transactions ({transaction_count} keywords)")
                else:
                    st.info(f"⏭️ Page {page_num + 1}: Skipping (likely disclosure/info page)")
                    
            except Exception as e:
                # If we can't read the page, include it to be safe
                st.warning(f"⚠️ Page {page_num + 1}: Could not scan, including anyway")
                transaction_pages.append(page_num)
        
        # If we didn't find any pages, return all pages (safe fallback)
        if not transaction_pages:
            st.warning("⚠️ No transaction pages detected - processing all pages")
            return list(range(len(pdf.pages)))
        
        return transaction_pages
        
    except Exception as e:
        st.error(f"❌ PDF scan error: {str(e)}")
        # Fallback: return None to process full PDF
        return None

def extract_pages(pdf_bytes, page_numbers):
    """
    Extract only specific pages into a new PDF
    Returns: bytes of the filtered PDF
    """
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        writer = PdfWriter()
        
        for page_num in page_numbers:
            if page_num < len(reader.pages):
                writer.add_page(reader.pages[page_num])
        
        output = BytesIO()
        writer.write(output)
        output.seek(0)
        return output.getvalue()
        
    except Exception as e:
        st.error(f"❌ Page extraction error: {str(e)}")
        # Fallback: return original PDF
        return pdf_bytes

# --- SMART RECOMMENDATIONS ---
def generate_recommendations(transactions, budget):
    """Generate money-saving recommendations based on spending patterns"""
    recommendations = []
    
    # Analyze spending by category
    category_spending = defaultdict(float)
    for t in transactions:
        if t['Type'] == 'Expense':
            category_spending[t['Category']] += t['Amount']
    
    # Dining Out recommendations
    if category_spending.get('Dining Out', 0) > 300:
        savings = category_spending['Dining Out'] * 0.5
        recommendations.append({
            'category': 'Dining Out',
            'current': category_spending['Dining Out'],
            'suggestion': f"Reduce dining out by 50% - cook at home 3-4 days/week",
            'potential_savings': savings,
            'difficulty': 'Medium'
        })
    
    # Groceries recommendations
    if category_spending.get('Groceries', 0) > 600:
        savings = category_spending['Groceries'] * 0.2
        recommendations.append({
            'category': 'Groceries',
            'current': category_spending['Groceries'],
            'suggestion': f"Meal prep and use store brands - save 20%",
            'potential_savings': savings,
            'difficulty': 'Easy'
        })
    
    # Entertainment
    if category_spending.get('Entertainment', 0) > 150:
        savings = 50
        recommendations.append({
            'category': 'Entertainment',
            'current': category_spending['Entertainment'],
            'suggestion': f"Share streaming services with family - save on subscriptions",
            'potential_savings': savings,
            'difficulty': 'Easy'
        })
    
    return recommendations

# --- ALERT SYSTEM ---
def check_budget_alerts(transactions, budget):
    """Check for budget alerts and warnings"""
    alerts = []
    
    # Get current month spending
    current_month = datetime.now().strftime("%Y-%m")
    month_spending = defaultdict(float)
    
    for t in transactions:
        if t['Type'] == 'Expense':
            try:
                trans_month = datetime.strptime(t['Date'], "%Y-%m-%d").strftime("%Y-%m")
                if trans_month == current_month:
                    month_spending[t['Category']] += t['Amount']
            except:
                pass
    
    # Check each budget category
    for category, budget_amount in budget.items():
        if budget_amount > 0:
            spent = month_spending.get(category, 0)
            percent = (spent / budget_amount) * 100
            
            if percent >= 100:
                alerts.append({
                    'level': 'danger',
                    'category': category,
                    'message': f"🔴 {category}: ${spent:,.0f}/${budget_amount:,.0f} ({percent:.0f}%) - OVER BUDGET!",
                    'percent': percent
                })
            elif percent >= 80:
                alerts.append({
                    'level': 'warning',
                    'category': category,
                    'message': f"⚠️ {category}: ${spent:,.0f}/${budget_amount:,.0f} ({percent:.0f}%) - Getting close!",
                    'percent': percent
                })
    
    # Check if we're 2 weeks from month end
    today = datetime.now()
    days_left = calendar.monthrange(today.year, today.month)[1] - today.day
    
    if days_left <= 14:
        # Project month-end spending
        days_elapsed = today.day
        for category, spent in month_spending.items():
            budget_amount = budget.get(category, 0)
            if budget_amount > 0:
                projected = (spent / days_elapsed) * calendar.monthrange(today.year, today.month)[1]
                if projected > budget_amount * 1.1:  # Projected to be 10% over
                    alerts.append({
                        'level': 'warning',
                        'category': category,
                        'message': f"📊 {category}: Projected to overspend by ${projected - budget_amount:,.0f} this month",
                        'percent': (projected / budget_amount) * 100
                    })
    
    return sorted(alerts, key=lambda x: x['percent'], reverse=True)

# --- LOGIN PAGE ---
def login_page():
    # Add custom CSS for professional split-screen login
    st.markdown("""
    <style>
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Split screen container */
    .login-container {
        display: flex;
        min-height: 100vh;
        align-items: center;
        justify-content: center;
        padding: 20px;
    }
    
    .login-card {
        display: flex;
        background: white;
        border-radius: 20px;
        overflow: hidden;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        max-width: 1000px;
        width: 100%;
        min-height: 500px;
    }
    
    /* Left side - Image/Brand */
    .login-left {
        flex: 1;
        background: linear-gradient(135deg, #2C3E50 0%, #34495E 100%);
        padding: 60px 40px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        color: white;
    }
    
    .login-left img {
        width: 80%;
        max-width: 400px;
        border-radius: 15px;
        margin-bottom: 30px;
        box-shadow: 0 10px 30px rgba(255, 184, 77, 0.3);
    }
    
    .login-left h1 {
        font-size: 3rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: 2px;
        background: linear-gradient(135deg, #FFB84D 0%, #F4A460 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .login-left .tagline {
        font-size: 1.2rem;
        color: #C8DCE8;
        margin-top: 15px;
        font-weight: 300;
        letter-spacing: 1px;
    }
    
    .login-left .features {
        margin-top: 40px;
        text-align: left;
        width: 100%;
        max-width: 350px;
    }
    
    .feature-item {
        display: flex;
        align-items: center;
        margin: 15px 0;
        font-size: 0.95rem;
        color: #E8EDF2;
    }
    
    .feature-item::before {
        content: "✓";
        display: inline-block;
        width: 24px;
        height: 24px;
        background: #FFB84D;
        border-radius: 50%;
        margin-right: 12px;
        text-align: center;
        line-height: 24px;
        font-weight: bold;
        color: #2C3E50;
        flex-shrink: 0;
    }
    
    /* Right side - Form */
    .login-right {
        flex: 1;
        padding: 60px 50px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    .login-right h2 {
        font-size: 2rem;
        color: #2C3E50;
        margin: 0 0 10px 0;
        font-weight: 700;
    }
    
    .login-right .subtitle {
        color: #7F8C8D;
        font-size: 1rem;
        margin-bottom: 40px;
    }
    
    /* Form styling */
    .stTextInput > div > div > input {
        border: 2px solid #E8EDF2;
        border-radius: 10px;
        padding: 15px 20px;
        font-size: 1rem;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #FFB84D;
        box-shadow: 0 0 0 3px rgba(255, 184, 77, 0.1);
    }
    
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #FFB84D 0%, #F4A460 100%);
        color: #2C3E50;
        font-weight: 700;
        font-size: 1.1rem;
        padding: 15px;
        border: none;
        border-radius: 10px;
        transition: all 0.3s ease;
        margin-top: 10px;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(255, 184, 77, 0.3);
    }
    
    .login-footer {
        text-align: center;
        margin-top: 30px;
        color: #7F8C8D;
        font-size: 0.9rem;
    }
    
    .login-footer a {
        color: #FFB84D;
        text-decoration: none;
        font-weight: 600;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .login-card {
            flex-direction: column;
        }
        .login-left {
            padding: 40px 20px;
        }
        .login-right {
            padding: 40px 20px;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create split-screen layout
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    
    # LEFT SIDE - Branding
    st.markdown('<div class="login-left">', unsafe_allow_html=True)
    
    # Try to load logo
    import base64
    logo_paths = ["Devin.png", "devin_logo.png", "/mnt/user-data/uploads/Devin.png"]
    logo_data = None
    
    for path in logo_paths:
        try:
            with open(path, "rb") as f:
                logo_data = base64.b64encode(f.read()).decode()
                break
        except:
            continue
    
    if logo_data:
        st.markdown(f'<img src="data:image/png;base64,{logo_data}" alt="D.E.V.I.N Logo">', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size: 5rem; margin-bottom: 30px;">💼</div>', unsafe_allow_html=True)
    
    st.markdown('<h1>D.E.V.I.N</h1>', unsafe_allow_html=True)
    st.markdown('<div class="tagline">Your Financial Blueprint</div>', unsafe_allow_html=True)
    
    st.markdown('''
    <div class="features">
        <div class="feature-item">Smart Budget Tracking</div>
        <div class="feature-item">AI-Powered Insights</div>
        <div class="feature-item">Goal Planning Tools</div>
        <div class="feature-item">Secure & Private</div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # RIGHT SIDE - Login Form
    st.markdown('<div class="login-right">', unsafe_allow_html=True)
    
    # Use columns to control form width in Streamlit
    col1, col2, col3 = st.columns([0.1, 1, 0.1])
    
    with col2:
        st.markdown('<h2>Welcome Back</h2>', unsafe_allow_html=True)
        st.markdown('<div class="subtitle">Sign in to continue to your financial dashboard</div>', unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("", placeholder="👤 Enter your name", label_visibility="collapsed", key="username_input")
            password = st.text_input("", type="password", placeholder="🔐 Access code", label_visibility="collapsed", key="password_input")
            
            col_a, col_b = st.columns([1, 1])
            
            with col_a:
                login_button = st.form_submit_button("🔓 LOGIN SECURELY", type="primary", use_container_width=True)
            
            with col_b:
                new_user_button = st.form_submit_button("➕ NEW USER", use_container_width=True)
            
            if login_button or new_user_button:
                if not username:
                    st.error("👤 Please enter your name")
                elif password != MASTER_PASSWORD:
                    st.error("❌ Incorrect access code")
                else:
                    st.session_state.authenticated = True
                    st.session_state.current_user = username
                    st.session_state.user_id = get_or_create_user(username)
                    
                    # Check if onboarding is complete
                    if username not in st.session_state.onboarding_complete:
                        st.session_state.onboarding_complete[username] = False
                    
                    st.success(f"✅ Welcome, {username}!")
                    time.sleep(0.5)
                    st.rerun()
        
        st.markdown('''
        <div class="login-footer">
            Don't have an account? Click <a href="#">NEW USER</a> to get started
        </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

if not st.session_state.authenticated:
    login_page()
    st.stop()

# Check if onboarding is needed
current_user = st.session_state.current_user
user_id = st.session_state.user_id

if not st.session_state.onboarding_complete.get(current_user, False):
    # ONBOARDING WIZARD
    render_devin_logo("small")
    st.markdown("# 🎯 Welcome to D.E.V.I.N!")
    st.markdown("*Let's set up your financial profile in just a few minutes*")
    
    # Progress bar
    total_steps = 6
    current_step = st.session_state.onboarding_step
    # Adjust progress to account for skipped steps
    adjusted_progress = ((current_step - 3) / 3) * 100 if current_step >= 4 else 0
    
    st.markdown(f"""
    <div style="margin: 20px 0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
            <span><b>Step {current_step - 3} of 3</b></span>
            <span>{adjusted_progress:.0f}% Complete</span>
        </div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {adjusted_progress}%"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # Get requested months from onboarding data
    requested_months = st.session_state.onboarding_data.get('requested_months', [])
    
    # STEPS 4-6 are now STEPS 1-3 (Upload months)
    if current_step in [4, 5, 6]:
        month_index = current_step - 4  # 0, 1, 2
        month_info = requested_months[month_index] if month_index < len(requested_months) else {'name': 'Unknown Month', 'short_name': 'Unknown'}
        
        step_label = current_step - 3  # Display as Step 1, 2, 3
        
        st.markdown(f"## Step {step_label}: Upload {month_info['name']} 📤")
        
        st.markdown(f"""
        <div class="wizard-step">
        <h3>📅 Upload statements for {month_info['name']}</h3>
        <p>Add all accounts you used during this period</p>
        <p><i>💡 This is one of your last 3 complete months of financial data</i></p>
        </div>
        """, unsafe_allow_html=True)
        
        # Account uploader
        if f'month_{month_index}_accounts' not in st.session_state.onboarding_data:
            st.session_state.onboarding_data[f'month_{month_index}_accounts'] = []
        
        num_accounts = len(st.session_state.onboarding_data[f'month_{month_index}_accounts'])
        
        # Add account button
        if st.button("➕ Add Another Account"):
            st.session_state.onboarding_data[f'month_{month_index}_accounts'].append({
                'name': '',
                'type': 'Bank Account',
                'file': None
            })
            st.rerun()
        
        # Show account upload forms
        for idx in range(num_accounts):
            with st.expander(f"📊 Account #{idx + 1}", expanded=True):
                col1, col2 = st.columns([2, 1])
                with col1:
                    account_name = st.text_input(
                        "Account Name", 
                        value=st.session_state.onboarding_data[f'month_{month_index}_accounts'][idx].get('name', ''),
                        placeholder="e.g., Wells Fargo Checking",
                        key=f"name_{month_index}_{idx}"
                    )
                with col2:
                    account_type = st.selectbox(
                        "Type",
                        ["Bank Account", "Credit Card", "PayPal", "Venmo", "Cash App", "Other"],
                        key=f"type_{month_index}_{idx}"
                    )
                
                uploaded_file = st.file_uploader(
                    "Upload Statement", 
                    type=['pdf', 'png', 'jpg', 'jpeg'],
                    key=f"file_{month_index}_{idx}"
                )
                
                if account_name:
                    st.session_state.onboarding_data[f'month_{month_index}_accounts'][idx]['name'] = account_name
                    st.session_state.onboarding_data[f'month_{month_index}_accounts'][idx]['type'] = account_type
                    st.session_state.onboarding_data[f'month_{month_index}_accounts'][idx]['file'] = uploaded_file
        
        st.divider()
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            if current_step > 4:  # Only show back button after first month
                if st.button("⬅️ Back"):
                    st.session_state.onboarding_step -= 1
                    st.rerun()
        
        with col2:
            if current_step < 6:  # Not the last month
                skip_text = "⏭️ Skip this month" if num_accounts == 0 else f"Next: {requested_months[month_index + 1]['short_name']} →"
                if st.button(skip_text, type="primary" if num_accounts > 0 else "secondary", use_container_width=True):
                    if num_accounts == 0:
                        st.warning("⚠️ Skipping this month will reduce accuracy of your budget analysis!")
                        time.sleep(1)
                    st.session_state.onboarding_step += 1
                    st.rerun()
            else:  # Last month - go to family info
                if st.button("Continue to Family Info →", type="primary", use_container_width=True, disabled=num_accounts == 0):
                    st.session_state.onboarding_step = 7  # Changed from 5 to 7
                    st.rerun()
        
        with col3:
            pass  # Empty column for spacing
    
    # STEP 7: Family Info (was Step 5)
    elif current_step == 7:
        st.markdown("## Step 3: Family Information 👨‍👩‍👧‍👦")
        
        st.markdown("""
        <div class="wizard-step">
        <h3>Help us personalize your budget</h3>
        <p>Family size helps us suggest appropriate budgets for groceries, utilities, and other household expenses.</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            adults = st.number_input("Number of Adults", min_value=1, max_value=10, value=1, step=1)
        with col2:
            children = st.number_input("Number of Children", min_value=0, max_value=10, value=0, step=1)
        
        st.session_state.onboarding_data['family_size'] = {'adults': adults, 'children': children}
        
        st.info(f"💡 Household size: {adults + children} people ({adults} adults, {children} children)")
        
        st.divider()
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("⬅️ Back"):
                st.session_state.onboarding_step = 6
                st.rerun()
        with col2:
            if st.button("Analyze My Finances →", type="primary", use_container_width=True):
                st.session_state.onboarding_step = 8  # Changed from 6 to 8
                st.rerun()
    
    # STEP 8: Analysis (was Step 6)
    elif current_step == 8:
        requested_months = st.session_state.onboarding_data.get('requested_months', [])
        signup_date = st.session_state.onboarding_data.get('signup_date', datetime.now().strftime("%Y-%m-%d"))
        
        st.markdown("## Final Step: Analyzing Your Finances 🔍")
        
        # Show which months were analyzed
        month_names = [m['name'] for m in requested_months]
        st.info(f"📅 **Analyzing:** {', '.join(month_names)}")
        
        with st.spinner("🤖 Processing your statements with AI..."):
            all_transactions = []
            
            # Process all uploaded statements
            for month_idx in range(3):
                accounts = st.session_state.onboarding_data.get(f'month_{month_idx}_accounts', [])
                for account in accounts:
                    if account.get('file'):
                        try:
                            # STEP 1: Detect transaction pages
                            pdf_bytes = account['file'].getvalue()
                            
                            st.markdown(f"### 📄 Processing: {account['name']}")
                            transaction_pages = find_transaction_pages(pdf_bytes)
                            
                            # STEP 2: Extract only transaction pages
                            if transaction_pages:
                                filtered_pdf = extract_pages(pdf_bytes, transaction_pages)
                                st.success(f"✅ Extracted {len(transaction_pages)} pages with transactions")
                            else:
                                filtered_pdf = pdf_bytes
                                st.info("📄 Processing full document")
                            
                            # STEP 3: Send to Azure Document Intelligence
                            result = analyze_with_azure(filtered_pdf, account['file'].name)
                            
                            # Extract transactions from Azure result
                            parsed_transactions = extract_transactions_from_azure(result)
                            
                            st.info(f"🔍 Processing {account['name']}: Found {len(parsed_transactions)} transactions")
                            
                            for trans in parsed_transactions:
                                all_transactions.append({
                                    'Date': datetime.now().strftime("%Y-%m-%d"),
                                    'Vendor': trans['description'],
                                    'Amount': trans['amount'],
                                    'Category': trans['category'],
                                    'Type': 'Expense',
                                    'Notes': f"From {account['name']}",
                                    'Card': account['name']
                                })
                        except Exception as e:
                            st.error(f"❌ Error processing {account['name']}: {str(e)}")
        
        # Show results
        st.success(f"✅ Analyzed {len(all_transactions)} transactions!")
        
        # Calculate insights
        total_spending = sum([t['Amount'] for t in all_transactions])
        avg_monthly = total_spending / 3
        
        category_totals = defaultdict(float)
        for t in all_transactions:
            category_totals[t['Category']] += t['Amount']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Analyzed", f"${total_spending:,.0f}")
        with col2:
            st.metric("Avg Monthly Spending", f"${avg_monthly:,.0f}")
        with col3:
            st.metric("Transactions", len(all_transactions))
        
        st.markdown("### 📊 Spending Breakdown")
        for cat, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            monthly_avg = amount / 3
            st.write(f"**{cat}:** ${monthly_avg:,.0f}/month")
        
        # Save transactions
        if st.button("🎉 Complete Setup & Start Tracking!", type="primary", use_container_width=True):
            # Save all transactions
            for trans in all_transactions:
                save_transaction(user_id, trans)
            
            # Mark onboarding complete
            st.session_state.onboarding_complete[current_user] = True
            st.balloons()
            st.success("🎉 Setup complete! Redirecting to your dashboard...")
            time.sleep(2)
            st.rerun()

else:
    # ====== MAIN APP (after onboarding) ======
    
    # Load user data
    transactions = load_user_transactions(user_id)
    saved_budget = load_user_budget(user_id)
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"# 🎯 {current_user}")
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.current_user = None
            st.rerun()
        
        if USE_DATABASE:
            st.success("🗄️ Database Connected")
        else:
            st.warning("⚠️ Demo Mode")
        
        st.divider()
        
        # Income
        st.markdown("### 💰 Income")
        total_income = st.number_input("Monthly Income", value=0, step=100)
        
        st.divider()
        
        # Budget
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
            categories["Other"] = st.slider("Other", 0, 500, saved_budget.get("Other", 0), 25)
        
        if st.button("💾 Save Budget", use_container_width=True):
            if save_user_budget(user_id, categories):
                st.success("✅ Saved!")
        
        total_budgeted = sum(categories.values())
        remaining = total_income - total_budgeted
        
        st.divider()
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
    
    if USE_DATABASE:
        st.info("✅ Your data is saved permanently!")
    
    # ===== ALERTS SECTION =====
    alerts = check_budget_alerts(transactions, categories)
    
    if alerts:
        st.markdown("## 🚨 Budget Alerts")
        
        for alert in alerts[:5]:  # Show top 5 alerts
            if alert['level'] == 'danger':
                st.markdown(f"""
                <div class="alert-danger">
                    <b>{alert['message']}</b>
                </div>
                """, unsafe_allow_html=True)
            elif alert['level'] == 'warning':
                st.markdown(f"""
                <div class="alert-warning">
                    <b>{alert['message']}</b>
                </div>
                """, unsafe_allow_html=True)
    
    st.divider()
    
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Overview", "💡 Recommendations", "🎯 Goals", "🔮 Future Planner", "📤 Upload"])
    
    # TAB 1: Overview
    with tab1:
        st.markdown("### 📊 Spending Overview")
        
        if transactions:
            df = pd.DataFrame(transactions)
            expenses = df[df['Type'] == 'Expense']
            
            if not expenses.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Pie chart
                    category_totals = expenses.groupby('Category')['Amount'].sum().reset_index()
                    fig = px.pie(category_totals, values='Amount', names='Category', 
                                title='Spending by Category', hole=0.4)
                    fig.update_layout(
                        plot_bgcolor='white', 
                        paper_bgcolor='white',
                        font=dict(color='#1a2332')
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Bar chart - Budget vs Actual
                    budget_data = []
                    for cat, budget_amt in categories.items():
                        actual = expenses[expenses['Category'] == cat]['Amount'].sum() if cat in expenses['Category'].values else 0
                        budget_data.append({
                            'Category': cat,
                            'Budgeted': budget_amt,
                            'Actual': actual
                        })
                    
                    budget_df = pd.DataFrame(budget_data)
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(name='Budgeted', x=budget_df['Category'], y=budget_df['Budgeted'], marker_color='#FFB84D'))
                    fig2.add_trace(go.Bar(name='Actual', x=budget_df['Category'], y=budget_df['Actual'], marker_color='#2C3E50'))
                    fig2.update_layout(
                        title='Budget vs Actual', 
                        barmode='group', 
                        plot_bgcolor='white', 
                        paper_bgcolor='white',
                        font=dict(color='#1a2332')
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                
                # Recent transactions
                st.markdown("### 📋 Recent Transactions")
                st.dataframe(df.head(10), use_container_width=True, hide_index=True)
        else:
            st.info("No transactions yet! Upload a statement to get started.")
    
    # TAB 2: Recommendations
    with tab2:
        st.markdown("### 💡 Smart Money-Saving Recommendations")
        
        if transactions:
            recommendations = generate_recommendations(transactions, categories)
            
            if recommendations:
                total_potential_savings = sum([r['potential_savings'] for r in recommendations])
                
                st.success(f"💰 **Potential Monthly Savings: ${total_potential_savings:,.0f}**")
                
                for rec in recommendations:
                    difficulty_color = {'Easy': '🟢', 'Medium': '🟡', 'Hard': '🔴'}
                    
                    st.markdown(f"""
                    <div class="wizard-step">
                        <h4>{difficulty_color.get(rec['difficulty'], '🟡')} {rec['category']}</h4>
                        <p><b>Current Spending:</b> ${rec['current']:,.0f}/month</p>
                        <p><b>Recommendation:</b> {rec['suggestion']}</p>
                        <p><b>Potential Savings:</b> <span style="color: #FFB84D; font-weight: bold;">${rec['potential_savings']:,.0f}/month</span></p>
                        <p><b>Difficulty:</b> {rec['difficulty']}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Your spending looks good! Keep tracking to get personalized recommendations.")
        else:
            st.info("Upload transactions to get personalized money-saving tips!")
    
    # TAB 3: Savings Goals
    with tab3:
        st.markdown("### 🎯 Savings Goals")
        
        # Initialize goals in session state
        if 'savings_goals' not in st.session_state:
            st.session_state.savings_goals = []
        
        # Add new goal
        with st.expander("➕ Add New Savings Goal", expanded=len(st.session_state.savings_goals) == 0):
            with st.form("new_goal"):
                goal_name = st.text_input("Goal Name", placeholder="e.g., Emergency Fund, New Car, Vacation")
                col1, col2 = st.columns(2)
                with col1:
                    target_amount = st.number_input("Target Amount ($)", min_value=0, value=1000, step=100)
                with col2:
                    current_amount = st.number_input("Current Savings ($)", min_value=0, value=0, step=100)
                
                target_date = st.date_input("Target Date", value=datetime.now() + timedelta(days=365))
                
                if st.form_submit_button("💾 Create Goal", use_container_width=True):
                    st.session_state.savings_goals.append({
                        'name': goal_name,
                        'target': target_amount,
                        'current': current_amount,
                        'date': target_date.strftime("%Y-%m-%d"),
                        'created': datetime.now().strftime("%Y-%m-%d")
                    })
                    st.success(f"✅ Goal '{goal_name}' created!")
                    st.rerun()
        
        # Display goals
        if st.session_state.savings_goals:
            for idx, goal in enumerate(st.session_state.savings_goals):
                progress = (goal['current'] / goal['target']) * 100 if goal['target'] > 0 else 0
                remaining = goal['target'] - goal['current']
                
                days_left = (datetime.strptime(goal['date'], "%Y-%m-%d") - datetime.now()).days
                monthly_needed = remaining / (days_left / 30) if days_left > 0 else 0
                
                st.markdown(f"""
                <div class="wizard-step">
                    <h4>🎯 {goal['name']}</h4>
                    <p><b>Target:</b> ${goal['target']:,.0f} by {goal['date']}</p>
                    <p><b>Current:</b> ${goal['current']:,.0f} ({progress:.0f}% complete)</p>
                    <p><b>Remaining:</b> ${remaining:,.0f}</p>
                    {f"<p><b>Monthly Needed:</b> ${monthly_needed:,.0f}/month ({days_left} days left)</p>" if days_left > 0 else "<p><b>Status:</b> Goal date passed!</p>"}
                </div>
                """, unsafe_allow_html=True)
                
                # Progress bar
                st.progress(min(progress / 100, 1.0))
                
                # Update goal
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    new_amount = st.number_input(f"Update savings", min_value=0, value=int(goal['current']), step=50, key=f"update_{idx}")
                with col2:
                    if st.button("💾 Update", key=f"save_{idx}"):
                        st.session_state.savings_goals[idx]['current'] = new_amount
                        st.success("Updated!")
                        st.rerun()
                with col3:
                    if st.button("🗑️ Delete", key=f"del_{idx}"):
                        st.session_state.savings_goals.pop(idx)
                        st.rerun()
                
                st.divider()
        else:
            st.info("💡 Set a savings goal to track your progress!")
    
    # TAB 4: Future Purchase Planner
    with tab4:
        st.markdown("### 🔮 Future Purchase Simulator")
        st.markdown("*Plan major purchases and see how they'll impact your budget*")
        
        with st.form("future_purchase"):
            st.markdown("#### What are you planning to buy?")
            
            purchase_name = st.text_input("Purchase Description", placeholder="e.g., New Car, Home Renovation, Dream Vacation")
            
            col1, col2 = st.columns(2)
            with col1:
                total_cost = st.number_input("Total Cost ($)", min_value=0, value=5000, step=100)
                down_payment = st.number_input("Down Payment ($)", min_value=0, value=0, step=100)
            
            with col2:
                purchase_month = st.selectbox("Purchase Month", 
                    ["This Month", "Next Month", "2 Months", "3 Months", "4 Months", "5 Months", "6 Months"])
                finance_months = st.number_input("Finance Over (months)", min_value=0, max_value=60, value=0, step=1)
            
            if st.form_submit_button("📊 Analyze Impact", use_container_width=True):
                # Calculate impact
                remaining_cost = total_cost - down_payment
                monthly_payment = remaining_cost / finance_months if finance_months > 0 else remaining_cost
                
                st.markdown("---")
                st.markdown("### 📊 Financial Impact Analysis")
                
                # Summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Cost", f"${total_cost:,.0f}")
                with col2:
                    st.metric("Down Payment", f"${down_payment:,.0f}")
                with col3:
                    st.metric("Monthly Payment", f"${monthly_payment:,.0f}")
                
                # Affordability check
                current_savings_capacity = total_income - total_budgeted
                
                if down_payment > net_savings:
                    st.markdown(f"""
                    <div class="alert-danger">
                        <b>⚠️ Down Payment Alert:</b> You need ${down_payment:,.0f} but only have ${net_savings:,.0f} saved.
                        <br><b>Shortfall:</b> ${down_payment - net_savings:,.0f}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="alert-success">
                        <b>✅ Down Payment:</b> You have enough saved! (${net_savings:,.0f} available)
                    </div>
                    """, unsafe_allow_html=True)
                
                if monthly_payment > current_savings_capacity:
                    st.markdown(f"""
                    <div class="alert-danger">
                        <b>⚠️ Monthly Budget Impact:</b> This payment (${monthly_payment:,.0f}/month) exceeds your available budget (${current_savings_capacity:,.0f}/month)
                        <br><b>Monthly Shortfall:</b> ${monthly_payment - current_savings_capacity:,.0f}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Recommendations
                    st.markdown("#### 💡 Recommendations to Make This Work:")
                    st.markdown(f"""
                    <div class="wizard-step">
                        <ol>
                            <li><b>Increase down payment</b> to ${down_payment + (monthly_payment - current_savings_capacity) * finance_months:,.0f} (reduces monthly to ${current_savings_capacity:,.0f})</li>
                            <li><b>Extend financing</b> to {int((remaining_cost / current_savings_capacity)):} months (makes payment affordable)</li>
                            <li><b>Reduce spending</b> by ${monthly_payment - current_savings_capacity:,.0f}/month in other categories</li>
                            <li><b>Wait {int((down_payment - net_savings) / current_savings_capacity) + 1} months</b> to save more down payment</li>
                        </ol>
                    </div>
                    """, unsafe_allow_html=True)
                elif monthly_payment > 0:
                    st.markdown(f"""
                    <div class="alert-success">
                        <b>✅ Monthly Payment:</b> Affordable! You have ${current_savings_capacity:,.0f}/month available, payment is ${monthly_payment:,.0f}/month
                        <br><b>Buffer:</b> ${current_savings_capacity - monthly_payment:,.0f}/month remaining
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    if down_payment <= net_savings:
                        st.markdown(f"""
                        <div class="alert-success">
                            <b>🎉 You can afford this purchase!</b> Pay in full with savings.
                        </div>
                        """, unsafe_allow_html=True)
    
    # TAB 5: Upload More Statements
    with tab5:
        st.markdown("### 📤 Upload Additional Statements")
        
        account_name = st.text_input("Account Name", placeholder="e.g., Chase Sapphire")
        uploaded_file = st.file_uploader("Upload Statement", type=['pdf', 'png', 'jpg', 'jpeg'])
        
        if uploaded_file and account_name:
            if st.button("🤖 Analyze & Add Transactions", type="primary"):
                try:
                    with st.spinner("🔍 Processing..."):
                        # STEP 1: Detect transaction pages
                        pdf_bytes = uploaded_file.getvalue()
                        
                        st.markdown(f"### 📄 Processing: {account_name}")
                        transaction_pages = find_transaction_pages(pdf_bytes)
                        
                        # STEP 2: Extract only transaction pages
                        if transaction_pages:
                            filtered_pdf = extract_pages(pdf_bytes, transaction_pages)
                            st.success(f"✅ Extracted {len(transaction_pages)} pages with transactions")
                        else:
                            filtered_pdf = pdf_bytes
                            st.info("📄 Processing full document")
                        
                        # STEP 3: Send to Azure Document Intelligence
                        result = analyze_with_azure(filtered_pdf, uploaded_file.name)
                        
                        # Extract transactions from Azure result
                        parsed = extract_transactions_from_azure(result)
                        
                        st.success(f"✅ Found {len(parsed)} transactions!")
                        
                        if parsed:
                            df_preview = pd.DataFrame(parsed)
                            st.dataframe(df_preview.head(20), use_container_width=True, hide_index=True)
                            
                            if st.button(f"💾 Add All {len(parsed)} Transactions", type="primary"):
                                for trans in parsed:
                                    transaction = {
                                        "Date": datetime.now().strftime("%Y-%m-%d"),
                                        "Vendor": trans['description'],
                                        "Amount": trans['amount'],
                                        "Category": trans['category'],
                                        "Type": "Expense",
                                        "Notes": f"From {account_name}",
                                        "Card": account_name
                                    }
                                    save_transaction(user_id, transaction)
                                
                                st.success("🎉 Added!")
                                st.balloons()
                                time.sleep(2)
                                st.rerun()
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
