import streamlit as st
import pandas as pd

st.set_page_config(page_title="Multi-Trip Expense Splitter", layout="wide")

st.title("📊 Multi-Trip Expense Splitter & Settlement Tool")
st.caption("Manage multiple trips, customize member lists per trip, and calculate optimized settlements.")

# -----------------------------------------------------------------------------
# 1. INITIALIZE GLOBAL DATA STRUCTURES
# -----------------------------------------------------------------------------
# We store everything inside a dictionary of trips in the session state
if "trips" not in st.session_state:
    st.session_state.trips = {
        "Default Template Trip": {
            "members": ["KASSAS", "SAEID", "ZIAD", "HESHAM"],
            "expenses": [
                {"description": "Playstaion", "amount": 1000.0, "payer": "HESHAM", "shared_with": ["ZIAD"]},
                {"description": "ddddd", "amount": 100.0, "payer": "SAEID", "shared_with": ["KASSAS", "ZIAD"]}
            ]
        }
    }

# Track which trip is currently selected
if "current_trip" not in st.session_state:
    st.session_state.current_trip = "Default Template Trip"

# -----------------------------------------------------------------------------
# 2. SIDEBAR: TRIP MANAGEMENT
# -----------------------------------------------------------------------------
st.sidebar.header("✈️ Trip Management")

# Dropdown to switch between existing trips
trip_options = list(st.session_state.trips.keys())
selected_trip = st.sidebar.selectbox(
    "Select Active Trip:", 
    options=trip_options, 
    index=trip_options.index(st.session_state.current_trip) if st.session_state.current_trip in trip_options else 0
)
st.session_state.current_trip = selected_trip

st.sidebar.markdown("---")

# Section to create a brand new trip
st.sidebar.subheader("➕ Create New Trip")
with st.sidebar.form("new_trip_form", clear_on_submit=True):
    new_trip_name = st.text_input("Trip Name:", placeholder="e.g., Dahab Vacation")
    
    st.write("👉 **Add Initial Members:**")
    st.caption("Enter names separated by commas (e.g., Alice, Bob, Charlie)")
    raw_members = st.text_area("Members List:", placeholder="Name1, Name2, Name3")
    
    submit_trip = st.form_submit_button("Create Trip")
    
    if submit_trip:
        clean_trip_name = new_trip_name.strip()
        if not clean_trip_name:
            st.error("Please enter a valid trip name.")
        elif clean_trip_name in st.session_state.trips:
            st.error("A trip with this name already exists.")
        elif not raw_members.strip():
            st.error("Please add at least one member to the trip.")
        else:
            # Parse commas and clean up names
            member_list = [name.strip().upper() for name in raw_members.split(",") if name.strip()]
            # Remove duplicates while preserving order
            member_list = list(dict.fromkeys(member_list))
            
            # Initialize the new trip structure
            st.session_state.trips[clean_trip_name] = {
                "members": member_list,
                "expenses": []
            }
            # Switch view to the newly created trip
            st.session_state.current_trip = clean_trip_name
            st.success(f"Trip '{clean_trip_name}' created successfully!")
            st.rerun()

# Display current trip info in sidebar
st.sidebar.markdown("---")
st.sidebar.write(f"### 📍 Current Trip: **{st.session_state.current_trip}**")
active_members = st.session_state.trips[st.session_state.current_trip]["members"]
st.sidebar.write("**Trip Members:**", ", ".join(active_members))

# Dynamic Quick-Add for single members to the current active trip
st.sidebar.markdown("---")
add_single_member = st.sidebar.text_input("Add single member to active trip:").strip().upper()
if st.sidebar.button("Quick Add Member") and add_single_member:
    if add_single_member not in active_members:
        st.session_state.trips[st.session_state.current_trip]["members"].append(add_single_member)
        st.rerun()

# -----------------------------------------------------------------------------
# 3. TRANSACTION ENTRY FOR CURRENT TRIP
# -----------------------------------------------------------------------------
st.header(f"📝 Add Expense for: {st.session_state.current_trip}")

# Local references to make code cleaner
current_data = st.session_state.trips[st.session_state.current_trip]
trip_members = current_data["members"]
trip_expenses = current_data["expenses"]

if not trip_members:
    st.warning("Please add members to this trip before logging expenses.")
else:
    with st.form("expense_input_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            desc = st.text_input("Expense Description", placeholder="e.g., Hotel Booking, Dinner, Fuel")
        with col2:
            amt = st.number_input("Amount Paid", min_value=0.0, step=10.0, format="%.2f")
        with col3:
            paid_by = st.selectbox("Who Paid?", options=trip_members)
        
        st.write("**Who is shared in this amount?**")
        checkbox_cols = st.columns(max(2, len(trip_members)))
        shared_status = {}
        for idx, member in enumerate(trip_members):
            with checkbox_cols[idx % len(checkbox_cols)]:
                shared_status[member] = st.checkbox(member, value=True, key=f"share_{member}")
                
        submitted = st.form_submit_button("Log Transaction")
        if submitted:
            who_shares = [m for m, checked in shared_status.items() if checked]
            if not desc:
                st.error("Please provide a description.")
            elif amt <= 0:
                st.error("Amount must be greater than 0.")
            elif not who_shares:
                st.error("At least one person must be selected as sharing this expense.")
            else:
                trip_expenses.append({
                    "description": desc,
                    "amount": amt,
                    "payer": paid_by,
                    "shared_with": who_shares
                })
                st.success(f"Added: {desc} to {st.session_state.current_trip}")
                st.rerun()

# -----------------------------------------------------------------------------
# 4. EXPENSES LEDGER TABLE
# -----------------------------------------------------------------------------
st.header("📋 Shared Expenses Ledger")
if trip_expenses:
    matrix_rows = []
    for exp in trip_expenses:
        row = {
            "Description": exp["description"],
            "Amount": exp["amount"],
            "Who Paid?": exp["payer"],
            "# Shared": len(exp["shared_with"])
        }
        for m in trip_members:
            row[m] = "x" if m in exp["shared_with"] else ""
        matrix_rows.append(row)
        
    df_ledger = pd.DataFrame(matrix_rows)
    st.dataframe(df_ledger, use_container_width=True)
else:
    st.info(f"No transactions logged yet for '{st.session_state.current_trip}'.")

# -----------------------------------------------------------------------------
# 5. SETTLEMENT ENGINE
# -----------------------------------------------------------------------------
st.header("🔄 Settlement Calculations")

if trip_expenses and len(trip_members) > 1:
    # Calculate net balances
    net_balances = {m: 0.0 for m in trip_members}
    
    for exp in trip_expenses:
        payer = exp["payer"]
        amt = exp["amount"]
        sharers = exp["shared_with"]
        
        if payer in net_balances:
            net_balances[payer] += amt
            
        split_share = amt / len(sharers)
        for participant in sharers:
            if participant in net_balances:
                net_balances[participant] -= split_share

    # Display Net Positions
    st.subheader("Current Net Balances")
    bal_cols = st.columns(min(len(trip_members), 4))
    for idx, (m, val) in enumerate(net_balances.items()):
        with bal_cols[idx % 4]:
            if val > 0.01:
                st.metric(label=m, value=f"+${val:,.2f}", delta="Owed Money")
            elif val < -0.01:
                st.metric(label=m, value=f"${val:,.2f}", delta="Owes Money", delta_color="inverse")
            else:
                st.metric(label=m, value="$0.00", delta="Settled")

    # Greedy Settlement Optimization Algorithm
    debtors = [[name, val] for name, val in net_balances.items() if val < -0.01]
    creditors = [[name, val] for name, val in net_balances.items() if val > 0.01]
    
    debtors.sort(key=lambda x: x[1])
    creditors.sort(key=lambda x: x[1], reverse=True)
    
    settlement_steps = []
    
    while debtors and creditors:
        debtor_name, debtor_amt = debtors[0]
        creditor_name, creditor_amt = creditors[0]
        
        transfer_amt = min(abs(debtor_amt), creditor_amt)
        
        settlement_steps.append({
            "Debtor (Who Pays)": debtor_name,
            "Recipient (Who Gets Paid)": creditor_name,
            "Amount": round(transfer_amt, 2)
        })
        
        debtors[0][1] += transfer_amt
        creditors[0][1] -= transfer_amt
        
        if abs(debtors[0][1]) < 0.01:
            debtors.pop(0)
        if abs(creditors[0][1]) < 0.01:
            creditors.pop(0)

    st.subheader("Optimized Settlement Schedule")
    if settlement_steps:
        df_settle = pd.DataFrame(settlement_steps)
        st.table(df_settle)
        
        for step in settlement_steps:
            st.markdown(f"💸 **{step['Debtor (Who Pays)']}** needs to pay **{step['Recipient (Who Gets Paid)']}** 👉 **${step['Amount']:,.2f}**")
    else:
        st.success("Everyone is settled! No transactions necessary.")
else:
    st.info("Log a few transactions to calculate automatic settlement instructions.")

        
