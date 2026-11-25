import os
import tempfile
from datetime import date, timedelta

import streamlit as st

from engine import (
    compute_summary,
    find_potential_matches,
    generate_next_id,
    mark_as_claimed,
    search_records,
)
from models import CATEGORIES, RECORD_TYPES, ItemRecord
from storage import load_records, save_records
from validators import (
    validate_contact,
    validate_date,
    validate_non_empty_string,
)
from visualizer import generate_charts


DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "records.json")

st.set_page_config(
    page_title="Campus Lost & Found",
    page_icon="🌷",
    layout="wide",
)

st.markdown(
    """
    <style>
    :root {
        --buttercream: #FFFDF5;
        --cream: #FAF0D7;
        --lilac: #9D7CD8;
        --lavender: #E6D9F8;
        --charcoal: #2D2638;
    }
    .stApp {
        background: linear-gradient(135deg, #FFFDF5 0%, #FDF6E3 100%);
        color: var(--charcoal);
    }
    [data-testid="stHeader"] { background: rgba(255, 253, 245, 0.88); }
    [data-testid="stSidebar"] { background: #FAF0D7; }
    h1 { color: #8B5CF6; }
    h2, h3 { color: #2D2638; }
    [data-testid="stMetric"] {
        background: #FAF0D7;
        border: 1px solid #E6D9F8;
        border-radius: 16px;
        padding: 16px 18px;
    }
    div[data-testid="stForm"] {
        background: #FAF0D7;
        border: 1px solid #E6D9F8;
        border-radius: 18px;
        padding: 22px;
    }
    .stButton > button, .stFormSubmitButton > button {
        background: #9D7CD8;
        color: #2D2638;
        border: 1px solid #8B5CF6;
        border-radius: 10px;
        font-weight: 650;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover {
        background: #E6D9F8;
        color: #2D2638;
        border-color: #8B5CF6;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #2D2638;
        border-bottom-color: #8B5CF6;
    }
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        border: 1px solid #E6D9F8;
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def create_demo_records() -> list[ItemRecord]:
    today = date.today()
    samples = [
        ("LOST", "Wireless Earbuds", "Electronics", "Central Library", 2, False),
        ("FOUND", "Blue Earbud Case", "Electronics", "Central Library", 1, False),
        ("LOST", "Student ID Card", "ID & Cards", "Main Cafeteria", 5, False),
        ("FOUND", "Water Bottle", "Keys & Bottles", "Sports Complex", 3, True),
        ("LOST", "Engineering Textbook", "Books & Stationery", "Block C Lab", 18, False),
        ("FOUND", "Silver Keychain", "Keys & Bottles", "Admin Block", 4, True),
        ("LOST", "Black Hoodie", "Clothing & Accessories", "Auditorium", 8, False),
        ("FOUND", "USB-C Charger", "Electronics", "Central Library", 7, True),
        ("LOST", "Canvas Pencil Case", "Books & Stationery", "Block C Lab", 1, False),
        ("FOUND", "Lunch Box", "Other", "Main Cafeteria", 12, False),
    ]
    records = []
    for rec_type, name, category, location, days_ago, claimed in samples:
        reported = today - timedelta(days=days_ago)
        records.append(
            ItemRecord(
                record_id=generate_next_id(records, rec_type),
                record_type=rec_type,
                item_name=name,
                category=category,
                location=location,
                date_reported=reported.isoformat(),
                description=f"Demo report for {name.lower()}.",
                contact="demo@campus.edu",
                status="CLAIMED" if claimed else "OPEN",
                date_claimed=(reported + timedelta(days=1)).isoformat() if claimed else None,
            )
        )
    return records


def show_record_table(records: list[ItemRecord]) -> None:
    rows = [
        {
            "ID": record.record_id,
            "Type": record.record_type.title(),
            "Item": record.item_name,
            "Category": record.category,
            "Location": record.location,
            "Reported": record.date_reported,
            "Status": record.status.title(),
        }
        for record in records
    ]
    st.dataframe(rows, hide_index=True, use_container_width=True)


records = load_records(DATA_FILE)

with st.sidebar:
    st.markdown("## Campus register")
    st.caption("A friendly home for lost things and found things.")
    st.metric("Items in register", len(records))
    if not records:
        if st.button("Load Demo Data", width="stretch"):
            records = create_demo_records()
            save_records(records, DATA_FILE)
            st.rerun()
    else:
        st.caption("Your saved register is ready to explore.")

st.title("Campus Lost & Found")
st.markdown(
    "### A little easier to find what matters."
    "\nLog reports, search campus records, and see recovery trends in one place."
)

log_tab, browse_tab, insights_tab = st.tabs(
    ["Log an item", "Search & resolve", "Insights"]
)

with log_tab:
    st.subheader("Log a lost or found item")
    with st.form("new_record_form"):
        rec_type = st.selectbox("Report type", RECORD_TYPES, format_func=str.title)
        item_name = st.text_input("Item name", placeholder="e.g. Blue water bottle")
        category = st.selectbox("Category", CATEGORIES)
        location = st.text_input("Campus location", placeholder="e.g. Central Library")
        report_date = st.date_input("Date reported", value=date.today(), max_value=date.today())
        description = st.text_area("Description (optional)", max_chars=500)
        contact = st.text_input("Contact email or 10-digit phone")
        submitted = st.form_submit_button("Save report")

    if submitted:
        errors = []
        if not validate_non_empty_string(item_name):
            errors.append("Item name must be at least 2 characters.")
        if not validate_non_empty_string(location):
            errors.append("Campus location must be at least 2 characters.")
        date_error = validate_date(report_date.isoformat())
        if date_error:
            errors.append(date_error)
        if not validate_contact(contact):
            errors.append("Enter a valid email address or 10-digit phone number.")

        if errors:
            for error in errors:
                st.error(error)
        else:
            new_record = ItemRecord(
                record_id=generate_next_id(records, rec_type),
                record_type=rec_type,
                item_name=item_name.strip(),
                category=category,
                location=location.strip(),
                date_reported=report_date.isoformat(),
                description=description.strip(),
                contact=contact.strip(),
            )
            matches = find_potential_matches(new_record, records)
            records.append(new_record)
            save_records(records, DATA_FILE)
            st.success(f"Report {new_record.record_id} saved.")
            if matches:
                st.info(f"{len(matches)} possible matching report(s) found:")
                show_record_table(matches)

with browse_tab:
    st.subheader("Search the register")
    filter_cols = st.columns([2, 1, 1, 1])
    keyword = filter_cols[0].text_input("Search by item, description, or location")
    selected_category = filter_cols[1].selectbox("Category", ["All"] + CATEGORIES)
    selected_status = filter_cols[2].selectbox("Status", ["All", "OPEN", "CLAIMED"])
    selected_type = filter_cols[3].selectbox("Type", ["All"] + RECORD_TYPES)

    results = search_records(
        records,
        keyword=keyword.strip(),
        category="" if selected_category == "All" else selected_category,
        status="" if selected_status == "All" else selected_status,
    )
    if selected_type != "All":
        results = [record for record in results if record.record_type == selected_type]

    st.caption(f"{len(results)} matching report(s)")
    if results:
        show_record_table(results)
        open_results = [record for record in results if record.status == "OPEN"]
        if open_results:
            selected_id = st.selectbox(
                "Choose an open report to resolve",
                [record.record_id for record in open_results],
            )
            selected_record = next(
                record for record in open_results if record.record_id == selected_id
            )
            with st.expander(f"{selected_record.item_name} · {selected_record.record_id}"):
                st.write(selected_record.description or "No additional description.")
                st.write(f"**Location:** {selected_record.location}")
                st.write(f"**Contact:** {selected_record.contact}")
            if st.button("Mark as claimed / resolved", key="claim_record"):
                if mark_as_claimed(records, selected_id):
                    save_records(records, DATA_FILE)
                    st.success(f"{selected_id} marked as claimed.")
                    st.rerun()
                else:
                    st.warning("This report was already resolved or could not be found.")
    else:
        st.info("No reports match these filters.")

with insights_tab:
    st.subheader("Live campus snapshot")
    summary = compute_summary(records)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Total reports", summary["total"])
    metric_cols[1].metric("Open", summary["open"])
    metric_cols[2].metric("Resolved", summary["claimed"])
    metric_cols[3].metric("Recovery rate", f'{summary["claim_rate"]}%')

    detail_cols = st.columns(3)
    detail_cols[0].metric("Lost", summary["lost"])
    detail_cols[1].metric("Found", summary["found"])
    detail_cols[2].metric("Overdue open items", summary["overdue"])
    st.caption(f'Average time to resolution: {summary["avg_resolution_days"]} days')

    if summary["total"]:
        with tempfile.TemporaryDirectory() as temp_dir:
            chart_path = os.path.join(temp_dir, "campus_summary_charts.png")
            if generate_charts(summary, chart_path):
                with open(chart_path, "rb") as chart_file:
                    st.image(chart_file.read(), caption="Live report analytics")
            else:
                st.info("Charts will appear once there are records to visualize.")
    else:
        st.info("Add a report or load demo data to see live charts and statistics.")
