import streamlit as st
import pandas as pd
import requests
import json

st.set_page_config(page_title="Cloud Persistent Splitter", layout="wide")

st.title("📊 Persistent Group Expense Splitter")
st.caption("All data is synchronized securely with Google Sheets via API.")

# -----------------------------------------------------------------------------
# 1. API DATA FETCH FUNCTIONS
# -----------------------------------------------------------------------------
SCRIPT_URL = st.secrets["script_url"]

@st.cache_data(ttl=2)
def load_data_from_api():
    try:
        response = requests.get(f"{SCRIPT_URL}?action=read")
        data = response.json()
        
        # Parse Trips
        trips_raw = data.get("trips", [])
        if len(trips_raw) > 1:
            trips_df = pd.DataFrame(trips_raw[1:], columns=trips_raw[0])
        else:
            trips_df = pd.DataFrame(columns=["Trip Name", "Members"])
            
        # Parse Expenses
        exp_raw = data.get("expenses", [])
        if len(exp_raw) > 1:
            expenses_df = pd.DataFrame(exp_raw[1:], columns=exp_raw[0])
        else:
            expenses_df = pd.DataFrame(columns=["Trip Name", "Description", "Amount", "Payer", "Shared With"])
            
        return trips_df.dropna(how='all'), expenses_df.dropna(how='all')
    except Exception as e:
        return pd.DataFrame(columns=["Trip Name", "Members"]), pd.DataFrame(columns=["Trip Name", "Description", "Amount", "Payer", "Shared With"])

trips_df, expenses_df = load_data_from_api()

# -----------------------------------------------------------------------------
# 2. STATE MANAGER
# -----------------------------------------------------------------------------
if "trips" not in st.session_state or st.sidebar.button("🔄 Force Refresh Sync"):
    st.session_state.trips = {}
    
    for _, row in trips_df.iterrows():
        t_name = str(row["Trip Name"]).strip()
        m_list = [m.strip().upper() for m in str(row["Members"]).split(",") if m.strip()]
        if t_name and t_name != "nan":
            st.session_state.trips[t_name] = {"members": m_list, "expenses": []}
            
    for _, row in expenses_df.iterrows():
        t_name = str(row["Trip Name"]).strip()
        if t_name in st.session_state.trips:
            sw_list = [m.strip().upper() for m in str(row["Shared With"]).split(",") if m.strip()]
            st.session_state.trips[t_name]["expenses"].append({
                "description": str(row["Description"]),
                "amount": float(row["Amount"]) if row["Amount"] else 0.0,
                "payer": str(row["Payer"]).strip().upper(),
                "shared_with": sw_list
            })

if not st.session_state.trips:
    st.session_state.trips = {
        "DEFAULT TRIP": {"members": ["KASSAS", "SAEID", "ZIAD", "HESHAM"], "expenses": []}
    }

if "current_trip" not in st.session_state or st.session_state.current_trip not in st.session_state.trips:
    st.session_state.current_trip = list(st.session_state.trips.keys())[0]

# -----------------------------------------------------------------------------
# 3. SIDEBAR: TRIP NAVIGATION
# -----------------------------------------------------------------------------
st.sidebar.header("✈️ Trip Management")
trip_options = list(st.session_state.trips.keys())
selected_trip = st.sidebar.selectbox("Select Active Trip:", options=trip_options, index=trip_options.index(st.session_state.current_trip))
st.session_state.current_trip = selected_trip

st.sidebar.markdown("---")
st.sidebar.subheader("➕ Create New Trip")
with st.sidebar.form("new_trip_form", clear_on_submit=True):
    new_trip_name = st.text_input("Trip Name:")
    raw_members = st.text_area("Members List (Comma Separated):", placeholder="KASSAS, SAEID, ZIAD")
    if st.form_submit_button("Create & Sync Trip"):
        clean_name = new_trip_name.strip().upper()
        if clean_name and clean_name not in st.session_state.trips and raw_members.strip():
            m_list = list(dict.fromkeys([n.strip().upper() for n in raw_members.split(",") if n.strip()]))
            
            # Send payload to script web app
            payload = {"action": "add_trip", "tripName": clean_name, "members": ",".join(m_list)}
            headers = {"Content-Type": "application/json"}
            requests.post(SCRIPT_URL, data=json.dumps(payload), headers=headers, allow_redirects=True)
            
            st.session_state.current_trip = clean_name
            st.cache_data.clear()
            st.rerun()

st.sidebar.write(f"### 📍 Active: **{st.session_state.current_trip}**")
active_members = st.session_state.trips[st.session_state.current_trip]["members"]
st.sidebar.write("**Members:**", ", ".join(active_members))

# -----------------------------------------------------------------------------
# 4. EXPENSE FORM
# -----------------------------------------------------------------------------
st.header(f"_Trip Instance: {st.session_state.current_trip}_")
current_data = st.session_state.trips[st.session_state.current_trip]
trip_members = current_data["members"]
trip_expenses = current_data["expenses"]

with st.form("expense_input_form", clear_on_submit=True):
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1: desc = st.text_input("Expense Description")
    with col2: amt = st.number_input("Amount Paid", min_value=0.0, step=10.0, format="%.2f")
    with col3: paid_by = st.selectbox("Who Paid?", options=trip_members)
    
    st.write("**Who shares in this expense?**")
    checkbox_cols = st.columns(max(2, len(trip_members)))
    shared_status = {}
    for idx, member in enumerate(trip_members):
        with checkbox_cols[idx % len(checkbox_cols)]:
            shared_status[member] = st.checkbox(member, value=True, key=f"share_{member}")
            
    if st.form_submit_button("Commit Transaction to Cloud"):
        who_shares = [m for m, checked in shared_status.items() if checked]
        if desc and amt > 0 and who_shares:
            payload = {
                "action": "add_expense",
                "tripName": st.session_state.current_trip,
                "description": desc,
                "amount": amt,
                "payer": paid_by,
                "sharedWith": ",".join(who_shares)
            }
            headers = {"Content-Type": "application/json"}
            requests.post(SCRIPT_URL, data=json.dumps(payload), headers=headers, allow_redirects=True)
            st.success("Transaction pushed successfully!")
            st.cache_data.clear()
            st.rerun()

# -----------------------------------------------------------------------------
# 5. TABLES & CALCULATIONS
# -----------------------------------------------------------------------------
st.header("📋 Shared Expenses Ledger")
if trip_expenses:
    matrix_rows = []
    for exp in trip_expenses:
        row = {"Description": exp["description"], "Amount": exp["amount"], "Who Paid?": exp["payer"], "# Shared": len(exp["shared_with"])}
        for m in trip_members: row[m] = "x" if m in exp["shared_with"] else ""
        matrix_rows.append(row)
    st.dataframe(pd.DataFrame(matrix_rows), use_container_width=True)
else:
    st.info("No active logs found for this trip.")

st.header("🔄 Settlement Calculations")
if trip_expenses and len(trip_members) > 1:
    net_balances = {m: 0.0 for m in trip_members}
    for exp in trip_expenses:
        if exp["payer"] in net_balances: net_balances[exp["payer"]] += exp["amount"]
        split_share = exp["amount"] / len(exp["shared_with"])
        for p in exp["shared_with"]:
            if p in net_balances: net_balances[p] -= split_share

    bal_cols = st.columns(min(len(trip_members), 4))
    for idx, (m, val) in enumerate(net_balances.items()):
        with bal_cols[idx % 4]:
            if val > 0.01: st.metric(label=m, value=f"+${val:,.2f}", delta="Owed Money")
            elif val < -0.01: st.metric(label=m, value=f"${val:,.2f}", delta="Owes Money", delta_color="inverse")
            else: st.metric(label=m, value="$0.00", delta="Settled")

    debtors = [[n, v] for n, v in net_balances.items() if v < -0.01]
    creditors = [[n, v] for n, v in net_balances.items() if v > 0.01]
    debtors.sort(key=lambda x: x[1])
    creditors.sort(key=lambda x: x[1], reverse=True)
    
    settlement_steps = []
    while debtors and creditors:
        trans_amt = min(abs(debtors[0][1]), creditors[0][1])
        settlement_steps.append({"From (Debtor)": debtors[0][0], "To (Creditor)": creditors[0][0], "Amount": round(trans_amt, 2)})
        debtors[0][1] += trans_amt
        creditors[0][1] -= trans_amt
        if abs(debtors[0][1]) < 0.01: debtors.pop(0)
        if abs(creditors[0][1]) < 0.01: creditors.pop(0)

    st.subheader("Optimized Settlement Schedule")
    if settlement_steps:
        st.table(pd.DataFrame(settlement_steps))
        for step in settlement_steps:
            st.markdown(f"💸 **{step['From (Debtor)']}** pays **{step['To (Creditor)']}** 👉 **${step['Amount']:,.2f}**")
