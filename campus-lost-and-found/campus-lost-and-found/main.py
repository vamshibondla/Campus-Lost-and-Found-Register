"""Terminal UI, interactive menu loop, and report export for Campus Lost-and-Found Register."""

from models import ItemRecord, CATEGORIES, RECORD_TYPES
from storage import load_records, save_records, export_to_csv, import_from_csv
from validators import get_non_empty_string, get_choice, get_valid_date, get_valid_contact
from engine import (
    generate_next_id, find_potential_matches, search_records,
    mark_as_claimed, compute_summary, is_overdue
)
from visualizer import generate_charts

YELLOW = "\033[93m"
RESET = "\033[0m"

def print_table(records: list[ItemRecord]) -> None:
    if not records:
        print("\n  No matching records found.")
        return
    header = f"{'ID':<10} | {'TYPE':<6} | {'ITEM NAME':<20} | {'CATEGORY':<22} | {'LOCATION':<16} | {'DATE':<10} | {'STATUS':<15}"
    print("\n" + "-" * len(header))
    print(header)
    print("-" * len(header))
    for r in records:
        overdue_flag = is_overdue(r)
        status_text = f"{r.status} [OVERDUE]" if overdue_flag else r.status
        row = f"{r.record_id:<10} | {r.record_type:<6} | {r.item_name[:20]:<20} | {r.category[:22]:<22} | {r.location[:16]:<16} | {r.date_reported:<10} | {status_text:<15}"
        print(f"{YELLOW}{row}{RESET}" if overdue_flag else row)
    print("-" * len(header))

def export_markdown_report(records: list[ItemRecord], summary: dict, filepath: str = "campus_report.md") -> None:
    open_items = [r for r in records if r.status == "OPEN"]
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Campus Lost-and-Found Executive Report\n\n")
        f.write(f"- **Total Records:** {summary['total']} (Lost: {summary['lost']} | Found: {summary['found']})\n")
        f.write(f"- **Recovery Rate:** {summary['claim_rate']}% ({summary['claimed']} Claimed, {summary['open']} Open)\n")
        f.write(f"- **Overdue Open Items (>14 days):** {summary['overdue']}\n")
        f.write(f"- **Average Resolution Time:** {summary['avg_resolution_days']} days\n\n")
        f.write("## Currently Open Items\n\n")
        f.write("| ID | Type | Item Name | Category | Location | Date Reported |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in open_items:
            f.write(f"| {r.record_id} | {r.record_type} | {r.item_name} | {r.category} | {r.location} | {r.date_reported} |\n")

def handle_add_record(records: list[ItemRecord]) -> None:
    print("\n--- Log New Lost / Found Item ---")
    rec_type = get_choice("Record Type: ", RECORD_TYPES)
    name = get_non_empty_string("Item Name: ")
    category = get_choice("Category: ", CATEGORIES)
    location = get_non_empty_string("Campus Location: ")
    date_str = get_valid_date()
    desc = input("Description (optional): ").strip()
    contact = get_valid_contact()

    new_id = generate_next_id(records, rec_type)
    new_record = ItemRecord(new_id, rec_type, name, category, location, date_str, desc, contact)
    records.append(new_record)
    save_records(records)
    print(f"\n[Success] Logged record {new_id}!")

    matches = find_potential_matches(new_record, records[:-1])
    if matches:
        print(f"\n[!] ALERT: Found {len(matches)} potential match(es):")
        print_table(matches)

def main() -> None:
    records = load_records()
    while True:
        print("\n==========================================")
        print("   CAMPUS LOST-AND-FOUND REGISTER (CLI)   ")
        print("==========================================")
        print("1. Log Lost or Found Item")
        print("2. View All Records")
        print("3. Search / Filter Records")
        print("4. Mark Item as Claimed")
        print("5. Executive Summary, Charts & MD Report")
        print("6. Export / Import CSV")
        print("7. Exit")

        choice = input("\nSelect an option (1-7): ").strip()

        if choice == "1":
            handle_add_record(records)
        elif choice == "2":
            print_table(records)
        elif choice == "3":
            kw = input("Keyword (leave blank for all): ").strip()
            status = input("Status filter (OPEN/CLAIMED or blank): ").strip()
            print_table(search_records(records, keyword=kw, status=status))
        elif choice == "4":
            rec_id = input("Enter Record ID to mark CLAIMED (e.g., LST-0001): ").strip()
            if mark_as_claimed(records, rec_id):
                save_records(records)
                print(f"[Success] Record {rec_id.upper()} updated to CLAIMED.")
            else:
                print("[!] Record not found or already claimed.")
        elif choice == "5":
            summary = compute_summary(records)
            print("\n--- Executive Summary ---")
            print(f"Total Records   : {summary['total']} (Lost: {summary['lost']} | Found: {summary['found']})")
            print(f"Status          : Open: {summary['open']} ({summary['overdue']} overdue) | Claimed: {summary['claimed']} ({summary['claim_rate']}%)")
            print(f"Avg Claim Time  : {summary['avg_resolution_days']} days")
            print(f"Top Hotspots    : {summary['top_locations']}")
            if generate_charts(summary):
                print("[Success] Charts saved to 'campus_summary_charts.png'.")
            export_markdown_report(records, summary)
            print("[Success] Markdown report saved to 'campus_report.md'.")
        elif choice == "6":
            sub = input("Type 'E' to Export CSV or 'I' to Import CSV: ").strip().upper()
            if sub == "E":
                export_to_csv(records)
                print("[Success] Exported all records to 'records_export.csv'.")
            elif sub == "I":
                path = input("Enter CSV filename (e.g., records_export.csv): ").strip()
                imported, errors = import_from_csv(path)
                existing_ids = {r.record_id for r in records}
                added = [r for r in imported if r.record_id not in existing_ids]
                records.extend(added)
                save_records(records)
                print(f"[Success] Imported {len(added)} new record(s).")
                for err in errors:
                    print(f"  [Row Warning] {err}")
        elif choice == "7":
            print("Saving state and exiting. Goodbye!")
            break
        else:
            print("[!] Invalid choice. Enter a number from 1 to 7.")

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting Campus Lost-and-Found Register cleanly.")