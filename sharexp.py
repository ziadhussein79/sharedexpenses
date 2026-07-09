import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Cloud Persistent Splitter", layout="wide")

st.title("📊 Persistent Group Expense Splitter")
st.caption("All data is being saved and synchronized in real-time to your Google Sheet.")

# -----------------------------------------------------------------------------
# 1. ESTABLISH GOOGLE SHEETS CONNECTION
# -----------------------------------------------------------------------------
# Establish the live public sheet link connection
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5)  # Cache data for 5 seconds to reduce API overhead
def load_data():
    try:
        # Read the two tabs from the public spreadsheet URL
        trips_df = conn.read(worksheet="Trips_Members", ttl=0)
        expenses_df = conn.read(worksheet="Expenses", ttl=0)
    except Exception:
        # Fallbacks if sheet is completely empty initially
        trips_df = pd.DataFrame(columns=["Trip Name", "Members"])
        expenses_df = pd.DataFrame(columns=["Trip Name", "Description", "Amount", "Payer", "Shared With"])
    
    # Drop completely empty row artifacts
    trips_df = trips_df.dropna(how='all')
    expenses_df = expenses_df.dropna(how='all')
    return trips_df, expenses_df

trips_df, expenses_df = load_data()

# -----------------------------------------------------------------------------
# 2. SYNC SHEETS WITH MEMORY SESSION STATE
# -----------------------------------------------------------------------------
# Transform tabular sheet structure into our app's working dictionary format
if "trips" not in st.session_state or st.sidebar.button("🔄 Force Refresh Sync"):
    st.session_state.trips = {}
    
    # Re-populate trips and member lists
    for _, row in trips_df.iterrows():
        t_name = str(row["Trip Name"]).strip()
        m_string = str(row["Members"])
        m_list = [m.strip().upper() for m in m_string.split(",") if m.strip()]
        if t_name and t_name != "nan":
            st.session_state.trips[t_name] = {"members": m_list, "expenses": []}
            
    # Re-populate expenses into their correct corresponding trips
    for _, row in expenses_df.iterrows():
        t_name = str(row["Trip Name"]).strip()
        if t_name in st.session_state.trips:
            sw_string = str(row["Shared With"])
            sw_list = [m.strip().upper() for m in sw_string.split(",") if m.strip()]
            st.session_state.trips[t_name]["expenses"].append({
                "description": str(row["Description"]),
                "amount": float(row["Amount"]),
                "payer": str(row["Payer"]).strip().upper(),
                "shared_with": sw_list
            })

# Inject standard fallback trip if Google Sheet is completely fresh/blank
if not st.session_state.trips:
    st.session_state.trips = {
        "Default Trip": {
            "members": ["KASSAS", "SAEID", "ZIAD", "HESHAM"],
            "expenses": []
        }
    }

# Handle active navigation tracker
if "current_trip" not in st.session_state or st.session_state.current_trip not in st.session_state.trips:
    st.session_state.current_trip = list(st.session_state.trips.keys())[0]

# -----------------------------------------------------------------------------
# 3. SIDEBAR: TRIP MANAGEMENT
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
    submit_trip = st.form_submit_button("Create & Sync Trip")
    
    if submit_trip:
        clean_name = new_trip_name.strip()
        if clean_name and clean_name not in st.session_state.trips and raw_members.strip():
            m_list = list(dict.fromkeys([n.strip().upper() for n in raw_members.split(",") if n.strip()]))
            
            # 1. Update working app state
            st.session_state.trips[clean_name] = {"members": m_list, "expenses": []}
            st.session_state.current_trip = clean_name
            
            # 2. Append new trip row dynamically into Google Sheet
            new_trip_row = pd.DataFrame([{"Trip Name": clean_name, "Members": ",".join(m_list)}])
            updated_trips_df = pd.concat([trips_df, new_trip_row], ignore_index=True)
            conn.update(worksheet="Trips_Members", data=updated_trips_df)
            
            st.success("New trip saved to cloud sheet!")
            st.cache_data.clear()
            st.rerun()

st.sidebar.write(f"### 📍 Active: **{st.session_state.current_trip}**")
active_members = st.session_state.trips[st.session_state.current_trip]["members"]
st.sidebar.write("**Members:**", ", ".join(active_members))

# -----------------------------------------------------------------------------
# 4. TRANSACTION ENTRY & PUSH
# -----------------------------------------------------------------------------
st.header(f"_Trip Instance: {st.session_state.current_trip}_")
current_data = st.session_state.trips[st.session_state.current_trip]
trip_members = current_data["members"]
trip_expenses = current_data["expenses"]

with st.form("expense_input_form", clear_on_submit=True):
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        desc = st.text_input("Expense Description", placeholder="e.g., Dinner, Fuel")
    with col2:
        amt = st.number_input("Amount Paid", min_value=0.0, step=10.0, format="%.2f")
    with col3:
        paid_by = st.selectbox("Who Paid?", options=trip_members)
    
    st.write("**Who shares in this expense?**")
    checkbox_cols = st.columns(max(2, len(trip_members)))
    shared_status = {}
    for idx, member in enumerate(trip_members):
        with checkbox_cols[idx % len(checkbox_cols)]:
            shared_status[member] = st.checkbox(member, value=True, key=f"share_{member}")
            
    if st.form_submit_button("Commit Transaction to Cloud"):
        who_shares = [m for m, checked in shared_status.items() if checked]
        if desc and amt > 0 and who_shares:
            # 1. Update running session state memory
            trip_expenses.append({"description": desc, "amount": amt, "payer": paid_by, "shared_with": who_shares})
            
            # 2. Append directly onto global table dataframe & overwrite Google Sheet worksheet
            new_exp_row = pd.DataFrame([{
                "Trip Name": st.session_state.current_trip,
                "Description": desc,
                "Amount": amt,
                "Payer": paid_by,
                "Shared With": ",".join(who_shares)
            }])
            updated_exp_df = pd.concat([expenses_df, new_exp_row], ignore_index=True)
            conn.update(worksheet="Expenses", data=updated_exp_df)
            
            st.success(f"Successfully committed '{desc}' directly to database sheet!")
            st.cache_data.clear()
            st.rerun()

# -----------------------------------------------------------------------------
# 5. RENDER EXPENSES LEDGER
# -----------------------------------------------------------------------------
st.header("📋 Shared Expenses Ledger")
if trip_expenses:
    matrix_rows = []
    for exp in trip_expenses:
        row = {"Description": exp["description"], "Amount": exp["amount"], "Who Paid?": exp["payer"], "# Shared": len(exp["shared_with"])}
        for m in trip_members:
            row[m] = "x" if m in exp["shared_with"] else ""
        matrix_rows.append(row)
    st.dataframe(pd.DataFrame(matrix_rows), use_container_width=True)
else:
    st.info("No active logs found for this trip.")

# -----------------------------------------------------------------------------
# 6. CALCULATE SETTLEMENT DIRECTIONS
# -----------------------------------------------------------------------------
st.header("🔄 Settlement Calculations")
if trip_expenses and len(trip_members) > 1:
    net_balances = {m: 0.0 for m in trip_members}
    for exp in trip_expenses:
        if exp["payer"] in net_balances: net_balances[exp["payer"]] += exp["amount"]
        split_share = exp["amount"] / len(exp["shared_with"])
        for p in exp["shared_with"]:
            if p in net_balances: net_balances[p] -= split_share

    # Display Net Metric Cards
    bal_cols = st.columns(min(len(trip_members), 4))
    for idx, (m, val) in enumerate(net_balances.items()):
        with bal_cols[idx % 4]:
            if val > 0.01: st.metric(label=m, value=f"+${val:,.2f}", delta="Owed Money")
            elif val < -0.01: st.metric(label=m, value=f"${val:,.2f}", delta="Owes Money", delta_color="inverse")
            else: st.metric(label=m, value="$0.00", delta="Settled")

    # Flow reduction matching logic
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
    else:
        st.success("Perfectly balanced.")
