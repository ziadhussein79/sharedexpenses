import streamlit as st
import pandas as pd

st.set_page_config(page_title="Excel Tactics Expense Splitter", layout="wide")

st.title("📊 Group Expense Splitter & Settlement Tool")
st.caption("Replicating the workflow logic from 'Excel-Tactics-Shared-Expense.xlsx'")

# 1. Initialize State for Members and Expenses
if "members" not in st.session_state:
    # Pre-loading names found in your template
    st.session_state.members = ["KASSAS", "SAEID", "ZIAD", "HESHAM"]
if "expenses" not in st.session_state:
    # Pre-loading the example items from your spreadsheet for demonstration
    st.session_state.expenses = [
        {"description": "Playstaion", "amount": 1000.0, "payer": "HESHAM", "shared_with": ["ZIAD"]},
        {"description": "ddddd", "amount": 100.0, "payer": "SAEID", "shared_with": ["KASSAS", "ZIAD"]}
    ]

# Sidebar: Manage Group Members
st.sidebar.header("👥 Manage Group Members")
new_member = st.sidebar.text_input("Add New Member Name:").strip().upper()
if st.sidebar.button("Add Member") and new_member:
    if new_member not in st.session_state.members:
        st.session_state.members.append(new_member)
        st.rerun()

st.sidebar.write("### Current Active Group:")
for m in st.session_state.members:
    st.sidebar.text(f"• {m}")

if st.sidebar.button("Reset All Data", type="primary"):
    st.session_state.expenses = []
    st.rerun()

# 2. Add New Transaction Input UI
st.header("📝 Add New Shared Expense")
with st.form("expense_input_form", clear_on_submit=True):
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        desc = st.text_input("Expense Description", placeholder="e.g., Dinner, Uber, Tickets")
    with col2:
        amt = st.number_input("Amount Paid", min_value=0.0, step=10.0, format="%.2f")
    with col3:
        paid_by = st.selectbox("Who Paid?", options=st.session_state.members)
    
    st.write("**Who is shared in this amount?**")
    checkbox_cols = st.columns(max(2, len(st.session_state.members)))
    shared_status = {}
    for idx, member in enumerate(st.session_state.members):
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
            st.session_state.expenses.append({
                "description": desc,
                "amount": amt,
                "payer": paid_by,
                "shared_with": who_shares
            })
            st.success(f"Added: {desc}")
            st.rerun()

# 3. Dynamic Expenses Ledger Table
st.header("📋 Shared Expenses Ledger")
if st.session_state.expenses:
    # Build a matrix representation similar to your sheet
    matrix_rows = []
    for exp in st.session_state.expenses:
        row = {
            "Description": exp["description"],
            "Amount": exp["amount"],
            "Who Paid?": exp["payer"],
            "# Shared": len(exp["shared_with"])
        }
        # Mark an 'x' for those who share
        for m in st.session_state.members:
            row[m] = "x" if m in exp["shared_with"] else ""
        matrix_rows.append(row)
        
    df_ledger = pd.DataFrame(matrix_rows)
    st.dataframe(df_ledger, use_container_width=True)
else:
    st.info("No transaction entries logged yet.")

# 4. Math Settlement Engine (Matching Debts to Credits)
st.header("🔄 Settlement Calculations")

if st.session_state.expenses and len(st.session_state.members) > 1:
    # Calculate initial net balances
    net_balances = {m: 0.0 for m in st.session_state.members}
    
    for exp in st.session_state.expenses:
        payer = exp["payer"]
        amt = exp["amount"]
        sharers = exp["shared_with"]
        
        # Credit the person who paid
        if payer in net_balances:
            net_balances[payer] += amt
            
        # Debit the calculated split share from participants
        split_share = amt / len(sharers)
        for participant in sharers:
            if participant in net_balances:
                net_balances[participant] -= split_share

    # Display Net Positions
    st.subheader("Current Net Balances")
    bal_cols = st.columns(len(st.session_state.members))
    for idx, (m, val) in enumerate(net_balances.items()):
        with bal_cols[idx]:
            if val > 0.01:
                st.metric(label=m, value=f"+${val:,.2f}", delta="Owed Money")
            elif val < -0.01:
                st.metric(label=m, value=f"${val:,.2f}", delta="Owes Money", delta_color="inverse")
            else:
                st.metric(label=m, value="$0.00", delta="Settled")

    # Greedy Settlement Optimization Algorithm
    debtors = [[name, val] for name, val in net_balances.items() if val < -0.01]
    creditors = [[name, val] for name, val in net_balances.items() if val > 0.01]
    
    # Sort to optimize resolution paths
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
        
        # Adjust running tallies
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
        
        # Readable summary text
        for step in settlement_steps:
            st.markdown(f"💸 **{step['Debtor (Who Pays)']}** needs to pay **{step['Recipient (Who Gets Paid)']}** 👉 **${step['Amount']:,.2f}**")
    else:
        st.success("Everyone is settled! No transactions necessary.")
else:
    st.info("Log a few transactions involving group members to calculate automatic settlement instructions.")
