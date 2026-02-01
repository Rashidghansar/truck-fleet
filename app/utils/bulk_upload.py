"""Bulk booking upload CSV template and processing"""
import csv
import io
from datetime import datetime
from typing import List, Dict, Any


BULK_BOOKING_CSV_HEADERS = [
    "container_number",
    "consignment_type",
    "weight",
    "truck_type",
    "truck_capacity",
    "destination_address",
    "gate_in_time",  # Format: YYYY-MM-DD HH:MM
    "published_rate",
    "payment_terms",
    "special_instructions",
]


def generate_csv_template() -> str:
    """Generate CSV template with headers and example row"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(BULK_BOOKING_CSV_HEADERS)
    
    # Write example row
    writer.writerow([
        "CONT123456",
        "Import Container",
        "25000",
        "40ft Container Truck",
        "40ft",
        "Mumbai Port, Gate 3",
        "2024-01-25 10:00",
        "15000",
        "immediate",
        "Handle with care, fragile items"
    ])
    
    return output.getvalue()


def parse_csv_bookings(csv_content: str) -> List[Dict[str, Any]]:
    """Parse CSV content and return list of booking dictionaries"""
    bookings = []
    errors = []
    
    csv_file = io.StringIO(csv_content)
    reader = csv.DictReader(csv_file)
    
    for idx, row in enumerate(reader, start=2):  # Start from 2 (row 1 is header)
        try:
            # Parse gate_in_time
            gate_in_time = None
            if row.get("gate_in_time"):
                try:
                    gate_in_time = datetime.strptime(row["gate_in_time"], "%Y-%m-%d %H:%M")
                except ValueError:
                    errors.append(f"Row {idx}: Invalid date format. Use YYYY-MM-DD HH:MM")
                    continue
            
            # Parse weight
            weight = None
            if row.get("weight"):
                try:
                    weight = float(row["weight"])
                except ValueError:
                    errors.append(f"Row {idx}: Invalid weight value")
                    continue
            
            # Parse published_rate
            published_rate = None
            if row.get("published_rate"):
                try:
                    published_rate = float(row["published_rate"])
                except ValueError:
                    errors.append(f"Row {idx}: Invalid rate value")
                    continue
            
            # Validate required fields
            if not row.get("consignment_type"):
                errors.append(f"Row {idx}: consignment_type is required")
                continue
            
            if not row.get("truck_type"):
                errors.append(f"Row {idx}: truck_type is required")
                continue
            
            if not row.get("destination_address"):
                errors.append(f"Row {idx}: destination_address is required")
                continue
            
            booking_data = {
                "container_number": row.get("container_number"),
                "consignment_type": row["consignment_type"],
                "weight": weight,
                "truck_type": row["truck_type"],
                "truck_capacity": row.get("truck_capacity"),
                "destination_address": row["destination_address"],
                "gate_in_time": gate_in_time,
                "published_rate": published_rate,
                "payment_terms": row.get("payment_terms", "immediate"),
                "special_instructions": row.get("special_instructions"),
                "is_negotiable": False,
                "quantity": 1
            }
            
            bookings.append(booking_data)
            
        except Exception as e:
            errors.append(f"Row {idx}: Error - {str(e)}")
    
    return bookings, errors

