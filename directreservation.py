import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# Initialize Supabase client
try:
    supabase: Client = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
except KeyError as e:
    st.error(f"Missing Supabase secret: {e}. Please check Streamlit Cloud secrets configuration.")
    st.stop()

# [load_property_room_map, generate_booking_id, check_duplicate_guest, calculate_days, safe_int, safe_float, 
# load_reservations_from_supabase, save_reservation_to_supabase, update_reservation_in_supabase, 
# delete_reservation_in_supabase, show_confirmation_dialog, display_filtered_analysis, show_reservations, show_analytics]
# ... (unchanged functions from original code, omitted for brevity)

def show_new_reservation_form():
    """Display form for creating a new reservation with dynamic room assignments."""
    try:
        st.header("📝 Direct Reservations")
        form_key = "new_reservation"

        # CSS to minimize gaps and remove lines
        st.markdown("""
            <style>
            div[data-testid="stHorizontalBlock"] { margin: 0; padding: 0; }
            div[data-testid="stVerticalBlock"] > div { margin-bottom: 0.5rem; }
            </style>
        """, unsafe_allow_html=True)

        with st.container():
            # Row 1: Property Name, Guest Name, Mobile No, MOB
            row1 = st.columns(4)
            with row1[0]:
                property_options = sorted(load_property_room_map().keys())
                property_name = st.selectbox("Property Name", property_options, key=f"{form_key}_property")
            with row1[1]:
                guest_name = st.text_input("Guest Name", placeholder="Enter guest name", key=f"{form_key}_guest")
            with row1[2]:
                mobile_no = st.text_input("Mobile No", placeholder="Enter mobile number", key=f"{form_key}_mobile")
            with row1[3]:
                mob = st.selectbox("MOB (Mode of Booking)",
                                   ["Direct", "Online", "Agent", "Walk-in", "Phone", "Website", "Booking-Drt", "Social Media", "Stay-back", "TIE-Group", "Others"],
                                   key=f"{form_key}_mob")
                if mob == "Others":
                    custom_mob = st.text_input("Custom MOB", key=f"{form_key}_custom_mob")
                else:
                    custom_mob = None
                if mob == "Online":
                    online_source = st.selectbox("Online Source",
                                                 ["Booking.com", "Agoda Prepaid", "Agoda Booking.com", "Expedia", "MMT", "Cleartrip", "Others"],
                                                 key=f"{form_key}_online_source")
                    if online_source == "Others":
                        custom_online_source = st.text_input("Custom Online Source", key=f"{form_key}_custom_online_source")
                    else:
                        custom_online_source = None
                else:
                    online_source = None
                    custom_online_source = None

            # Row 2: Enquiry Date, Check In, Check Out, No of Days
            row2 = st.columns(4)
            with row2[0]:
                enquiry_date = st.date_input("Enquiry Date", value=date.today(), key=f"{form_key}_enquiry")
            with row2[1]:
                check_in = st.date_input("Check In", value=date.today(), key=f"{form_key}_checkin")
            with row2[2]:
                check_out = st.date_input("Check Out", value=date.today() + timedelta(days=1), key=f"{form_key}_checkout")
            with row2[3]:
                no_of_days = calculate_days(check_in, check_out)
                st.text_input("No of Days", value=str(no_of_days), disabled=True, help="Check-out - Check-in")

            # Row 3: No of Adults, No of Children, No of Infants, Breakfast
            row3 = st.columns(4)
            with row3[0]:
                adults = st.number_input("No of Adults", min_value=0, value=1, key=f"{form_key}_adults")
            with row3[1]:
                children = st.number_input("No of Children", min_value=0, value=0, key=f"{form_key}_children")
            with row3[2]:
                infants = st.number_input("No of Infants", min_value=0, value=0, key=f"{form_key}_infants")
            with row3[3]:
                breakfast = st.selectbox("Breakfast", ["CP", "EP"], key=f"{form_key}_breakfast")

            # Row 4: Total Pax, No of Days, Room Type, Room No
            row4 = st.columns(4)
            with row4[0]:
                total_pax = safe_int(adults) + safe_int(children) + safe_int(infants)
                st.text_input("Total Pax", value=str(total_pax), disabled=True, help="Adults + Children + Infants")
            with row4[1]:
                st.text_input("No of Days", value=str(no_of_days), disabled=True, help="Check-out - Check-in")
            with row4[2]:
                room_map = load_property_room_map()
                available_room_types = sorted(room_map.get(property_name, {}).keys())
                room_type_options = available_room_types + ["Other"] if "Other" not in available_room_types else available_room_types
                if not available_room_types:
                    st.warning("No room types available for this property. Use 'Other'.")
                room_type = st.selectbox("Room Type", room_type_options, key=f"{form_key}_roomtype")
                if room_type == "Other":
                    custom_room_type = st.text_input("Custom Room Type", key=f"{form_key}_custom_roomtype")
                else:
                    custom_room_type = None
            with row4[3]:
                available_rooms = sorted(room_map.get(property_name, {}).get(room_type, [])) if room_type != "Other" else []
                if available_rooms:
                    room_no = st.selectbox("Room No", available_rooms, key=f"{form_key}_room")
                else:
                    st.warning("No rooms available for this room type. Enter manually.")
                    room_no = st.text_input("Room No", placeholder="Enter room number", key=f"{form_key}_room")

            # Row 5: Tariff (per day), Advance Amount, Advance MOP
            row5 = st.columns(3)
            with row5[0]:
                tariff = st.number_input("Tariff (per day)", min_value=0.0, value=0.0, step=100.0, key=f"{form_key}_tariff")
            with row5[1]:
                advance_amount = st.number_input("Advance Amount", min_value=0.0, value=0.0, step=100.0, key=f"{form_key}_advance")
            with row5[2]:
                advance_mop = st.selectbox("Advance MOP",
                                           ["Cash", "Card", "UPI", "Bank Transfer", "ClearTrip", "TIE Management", "Booking.com", "Pending", "Other"],
                                           key=f"{form_key}_advmop")
                if advance_mop == "Other":
                    custom_advance_mop = st.text_input("Custom Advance MOP", key=f"{form_key}_custom_advmop")
                else:
                    custom_advance_mop = None

            # Row 6: Total Tariff, Balance Amount, Balance MOP
            row6 = st.columns(3)
            with row6[0]:
                total_tariff = safe_float(tariff) * max(0, no_of_days)
                st.text_input("Total Tariff", value=f"₹{total_tariff:.2f}", disabled=True, help="Tariff × No of Days")
            with row6[1]:
                balance_amount = max(0, total_tariff - safe_float(advance_amount))
                st.text_input("Balance Amount", value=f"₹{balance_amount:.2f}", disabled=True, help="Total Tariff - Advance Amount")
            with row6[2]:
                balance_mop = st.selectbox("Balance MOP",
                                           ["Cash", "Card", "UPI", "Bank Transfer", "Pending", "Other"],
                                           key=f"{form_key}_balmop")
                if balance_mop == "Other":
                    custom_balance_mop = st.text_input("Custom Balance MOP", key=f"{form_key}_custom_balmop")
                else:
                    custom_balance_mop = None

            # Row 7: Booking Date, Invoice No, Plan Status
            row7 = st.columns(3)
            with row7[0]:
                booking_date = st.date_input("Booking Date", value=date.today(), key=f"{form_key}_booking")
            with row7[1]:
                invoice_no = st.text_input("Invoice No", placeholder="Enter invoice number", key=f"{form_key}_invoice")
            with row7[2]:
                plan_status = st.selectbox("Plan Status", ["Confirmed", "Pending", "Cancelled", "Completed", "No Show"], key=f"{form_key}_status")

            # Row 8: Remarks
            row8 = st.columns(1)
            with row8[0]:
                remarks = st.text_area("Remarks", value="", key=f"{form_key}_remarks")

            # Row 9: Payment Status, Submitted By
            row9 = st.columns(2)
            with row9[0]:
                payment_status = st.selectbox("Payment Status", ["Fully Paid", "Partially Paid", "Not Paid"], index=2, key=f"{form_key}_payment_status")
            with row9[1]:
                submitted_by = st.text_input("Submitted By", placeholder="Enter submitter name", key=f"{form_key}_submitted_by")

            if st.button("💾 Save Reservation", use_container_width=True):
                if not all([property_name, room_no, guest_name, mobile_no]):
                    st.error("❌ Please fill in all required fields")
                elif check_out < check_in:
                    st.error("❌ Check-out date must be on or after check-in")
                elif no_of_days < 0:
                    st.error("❌ Number of days cannot be negative")
                else:
                    mob_value = custom_mob if mob == "Others" else mob
                    is_duplicate, existing_booking_id = check_duplicate_guest(guest_name, mobile_no, room_no, mob=mob_value)
                    if is_duplicate:
                        st.error(f"❌ Guest already exists! Booking ID: {existing_booking_id}")
                    else:
                        booking_id = generate_booking_id()
                        if not booking_id:
                            st.error("❌ Failed to generate a unique booking ID")
                            return
                        reservation = {
                            "Property Name": property_name,
                            "Room No": room_no,
                            "Guest Name": guest_name,
                            "Mobile No": mobile_no,
                            "No of Adults": safe_int(adults),
                            "No of Children": safe_int(children),
                            "No of Infants": safe_int(infants),
                            "Total Pax": total_pax,
                            "Check In": check_in,
                            "Check Out": check_out,
                            "No of Days": no_of_days,
                            "Tariff": safe_float(tariff),
                            "Total Tariff": total_tariff,
                            "Advance Amount": safe_float(advance_amount),
                            "Balance Amount": balance_amount,
                            "Advance MOP": custom_advance_mop if advance_mop == "Other" else advance_mop,
                            "Balance MOP": custom_balance_mop if balance_mop == "Other" else balance_mop,
                            "MOB": mob_value,
                            "Online Source": custom_online_source if online_source == "Others" else online_source,
                            "Invoice No": invoice_no,
                            "Enquiry Date": enquiry_date,
                            "Booking Date": booking_date,
                            "Booking ID": booking_id,
                            "Room Type": custom_room_type if room_type == "Other" else room_type,
                            "Breakfast": breakfast,
                            "Plan Status": plan_status,
                            "Submitted By": submitted_by,
                            "Modified By": "",
                            "Modified Comments": "",
                            "Remarks": remarks,
                            "Payment Status": payment_status
                        }
                        if save_reservation_to_supabase(reservation):
                            st.success(f"✅ Reservation {booking_id} created successfully!")
                            show_confirmation_dialog(booking_id)
                        else:
                            st.error("❌ Failed to save reservation")
    except Exception as e:
        st.error(f"Error rendering new reservation form: {e}")

def show_edit_form(edit_index):
    """Display form for editing an existing reservation with dynamic room assignments."""
    try:
        reservation = st.session_state.reservations[edit_index]
        st.subheader(f"✏️ Editing Reservation: {reservation['Booking ID']}")
        form_key = f"edit_reservation_{edit_index}"

        # CSS to minimize gaps and remove lines
        st.markdown("""
            <style>
            div[data-testid="stHorizontalBlock"] { margin: 0; padding: 0; }
            div[data-testid="stVerticalBlock"] > div { margin-bottom: 0.5rem; }
            </style>
        """, unsafe_allow_html=True)

        with st.container():
            # Row 1: Property Name, Guest Name, Mobile No, MOB
            row1 = st.columns(4)
            with row1[0]:
                property_options = sorted(load_property_room_map().keys())
                if reservation["Property Name"] == "Property 16":
                    property_options = sorted(property_options + ["Property 16"])
                property_index = property_options.index(reservation["Property Name"]) if reservation["Property Name"] in property_options else 0
                property_name = st.selectbox("Property Name", property_options, index=property_index, key=f"{form_key}_property")
            with row1[1]:
                guest_name = st.text_input("Guest Name", value=reservation["Guest Name"], key=f"{form_key}_guest")
            with row1[2]:
                mobile_no = st.text_input("Mobile No", value=reservation["Mobile No"], key=f"{form_key}_mobile")
            with row1[3]:
                mob_options = ["Direct", "Online", "Agent", "Walk-in", "Phone", "Website", "Booking-Drt", "Social Media", "Stay-back", "TIE-Group", "Others"]
                mob_index = mob_options.index(reservation["MOB"]) if reservation["MOB"] in mob_options else len(mob_options) - 1
                mob = st.selectbox("MOB (Mode of Booking)", mob_options, index=mob_index, key=f"{form_key}_mob")
                if mob == "Others":
                    custom_mob = st.text_input("Custom MOB", value=reservation["MOB"] if mob_index == len(mob_options) - 1 else "", key=f"{form_key}_custom_mob")
                else:
                    custom_mob = None
                if mob == "Online":
                    online_source_options = ["Booking.com", "Agoda Prepaid", "Agoda Booking.com", "Expedia", "MMT", "Cleartrip", "Others"]
                    online_source_index = online_source_options.index(reservation["Online Source"]) if reservation["Online Source"] in online_source_options else len(online_source_options) - 1
                    online_source = st.selectbox("Online Source", online_source_options, index=online_source_index, key=f"{form_key}_online_source")
                    if online_source == "Others":
                        custom_online_source = st.text_input("Custom Online Source", value=reservation["Online Source"] if online_source_index == len(online_source_options) - 1 else "", key=f"{form_key}_custom_online_source")
                    else:
                        custom_online_source = None
                else:
                    online_source = None
                    custom_online_source = None

            # Row 2: Enquiry Date, Check In, Check Out, No of Days
            row2 = st.columns(4)
            with row2[0]:
                enquiry_date = st.date_input("Enquiry Date", value=reservation["Enquiry Date"], key=f"{form_key}_enquiry")
            with row2[1]:
                check_in = st.date_input("Check In", value=reservation["Check In"], key=f"{form_key}_checkin")
            with row2[2]:
                check_out = st.date_input("Check Out", value=reservation["Check Out"], key=f"{form_key}_checkout")
            with row2[3]:
                no_of_days = calculate_days(check_in, check_out)
                st.text_input("No of Days", value=str(no_of_days), disabled=True, help="Check-out - Check-in")

            # Row 3: No of Adults, No of Children, No of Infants, Breakfast
            row3 = st.columns(4)
            with row3[0]:
                adults = st.number_input("No of Adults", min_value=0, value=reservation["No of Adults"], key=f"{form_key}_adults")
            with row3[1]:
                children = st.number_input("No of Children", min_value=0, value=reservation["No of Children"], key=f"{form_key}_children")
            with row3[2]:
                infants = st.number_input("No of Infants", min_value=0, value=reservation["No of Infants"], key=f"{form_key}_infants")
            with row3[3]:
                breakfast = st.selectbox("Breakfast", ["CP", "EP"], index=["CP", "EP"].index(reservation["Breakfast"]), key=f"{form_key}_breakfast")

            # Row 4: Total Pax, No of Days, Room Type, Room No
            row4 = st.columns(4)
            with row4[0]:
                total_pax = safe_int(adults) + safe_int(children) + safe_int(infants)
                st.text_input("Total Pax", value=str(total_pax), disabled=True, help="Adults + Children + Infants")
            with row4[1]:
                st.text_input("No of Days", value=str(no_of_days), disabled=True, help="Check-out - Check-in")
            with row4[2]:
                room_map = load_property_room_map()
                available_room_types = sorted(room_map.get(property_name, {}).keys())
                is_custom_type = reservation["Room Type"] not in available_room_types or not reservation["Room Type"]
                room_type_options = available_room_types + ["Other"] if "Other" not in available_room_types else available_room_types
                room_type_index = room_type_options.index("Other" if is_custom_type else reservation["Room Type"])
                room_type = st.selectbox("Room Type", room_type_options, index=room_type_index, key=f"{form_key}_roomtype")
                if room_type == "Other":
                    custom_room_type = st.text_input("Custom Room Type", value=reservation["Room Type"] if is_custom_type else "", key=f"{form_key}_custom_roomtype")
                else:
                    custom_room_type = None
            with row4[3]:
                available_rooms = sorted(room_map.get(property_name, {}).get(room_type, [])) if room_type != "Other" else []
                existing_room_no = reservation["Room No"] or ""
                if existing_room_no and existing_room_no not in available_rooms:
                    available_rooms = sorted(set(available_rooms + [existing_room_no]))
                if available_rooms:
                    room_no_index = available_rooms.index(existing_room_no) if existing_room_no in available_rooms else 0
                    room_no = st.selectbox("Room No", available_rooms, index=room_no_index, key=f"{form_key}_room")
                else:
                    st.warning("No rooms available for this room type. Enter manually.")
                    room_no = st.text_input("Room No", value=existing_room_no, key=f"{form_key}_room")

            # Row 5: Tariff (per day), Advance Amount, Advance MOP
            row5 = st.columns(3)
            with row5[0]:
                tariff = st.number_input("Tariff (per day)", min_value=0.0, value=reservation["Tariff"], step=100.0, key=f"{form_key}_tariff")
            with row5[1]:
                advance_amount = st.number_input("Advance Amount", min_value=0.0, value=reservation["Advance Amount"], step=100.0, key=f"{form_key}_advance")
            with row5[2]:
                advance_mop_options = ["Cash", "Card", "UPI", "Bank Transfer", "ClearTrip", "TIE Management", "Booking.com", "Pending", "Other"]
                advance_mop_index = advance_mop_options.index(reservation["Advance MOP"]) if reservation["Advance MOP"] in advance_mop_options else len(advance_mop_options) - 1
                advance_mop = st.selectbox("Advance MOP", advance_mop_options, index=advance_mop_index, key=f"{form_key}_advmop")
                if advance_mop == "Other":
                    custom_advance_mop = st.text_input("Custom Advance MOP", value=reservation["Advance MOP"] if advance_mop_index == len(advance_mop_options) - 1 else "", key=f"{form_key}_custom_advmop")
                else:
                    custom_advance_mop = None

            # Row 6: Total Tariff, Balance Amount, Balance MOP
            row6 = st.columns(3)
            with row6[0]:
                total_tariff = safe_float(tariff) * max(0, no_of_days)
                st.text_input("Total Tariff", value=f"₹{total_tariff:.2f}", disabled=True, help="Tariff × No of Days")
            with row6[1]:
                balance_amount = max(0, total_tariff - safe_float(advance_amount))
                st.text_input("Balance Amount", value=f"₹{balance_amount:.2f}", disabled=True, help="Total Tariff - Advance Amount")
            with row6[2]:
                balance_mop_options = ["Cash", "Card", "UPI", "Bank Transfer", "Pending", "Other"]
                balance_mop_index = balance_mop_options.index(reservation["Balance MOP"]) if reservation["Balance MOP"] in balance_mop_options else len(balance_mop_options) - 1
                balance_mop = st.selectbox("Balance MOP", balance_mop_options, index=balance_mop_index, key=f"{form_key}_balmop")
                if balance_mop == "Other":
                    custom_balance_mop = st.text_input("Custom Balance MOP", value=reservation["Balance MOP"] if balance_mop_index == len(balance_mop_options) - 1 else "", key=f"{form_key}_custom_balmop")
                else:
                    custom_balance_mop = None

            # Row 7: Booking Date, Invoice No, Plan Status
            row7 = st.columns(3)
            with row7[0]:
                booking_date = st.date_input("Booking Date", value=reservation["Booking Date"], key=f"{form_key}_booking")
            with row7[1]:
                invoice_no = st.text_input("Invoice No", value=reservation["Invoice No"], key=f"{form_key}_invoice")
            with row7[2]:
                plan_status = st.selectbox("Plan Status", ["Confirmed", "Pending", "Cancelled", "Completed", "No Show"], index=["Confirmed", "Pending", "Cancelled", "Completed", "No Show"].index(reservation["Plan Status"]), key=f"{form_key}_status")

            # Row 8: Remarks
            row8 = st.columns(1)
            with row8[0]:
                remarks = st.text_area("Remarks", value=reservation["Remarks"], key=f"{form_key}_remarks")

            # Row 9: Payment Status, Submitted By
            row9 = st.columns(2)
            with row9[0]:
                payment_status_options = ["Fully Paid", "Partially Paid", "Not Paid"]
                payment_status_index = payment_status_options.index(reservation["Payment Status"]) if reservation["Payment Status"] in payment_status_options else 2
                payment_status = st.selectbox("Payment Status", payment_status_options, index=payment_status_index, key=f"{form_key}_payment_status")
            with row9[1]:
                submitted_by = st.text_input("Submitted By", value=reservation["Submitted By"], key=f"{form_key}_submitted_by")

            # Row 10: Modified By, Modified Comments
            row10 = st.columns(2)
            with row10[0]:
                modified_by = st.text_input("Modified By", value=reservation["Modified By"], key=f"{form_key}_modified_by")
            with row10[1]:
                modified_comments = st.text_area("Modified Comments", value=reservation["Modified Comments"], key=f"{form_key}_modified_comments")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("💾 Save Reservation", key=f"{form_key}_update", use_container_width=True):
                    if not all([property_name, room_no, guest_name, mobile_no]):
                        st.error("❌ Please fill in all required fields")
                    elif check_out < check_in:
                        st.error("❌ Check-out date must be on or after check-in")
                    elif no_of_days < 0:
                        st.error("❌ Number of days cannot be negative")
                    else:
                        mob_value = custom_mob if mob == "Others" else mob
                        is_duplicate, existing_booking_id = check_duplicate_guest(guest_name, mobile_no, room_no, exclude_booking_id=reservation["Booking ID"], mob=mob_value)
                        if is_duplicate:
                            st.error(f"❌ Guest already exists! Booking ID: {existing_booking_id}")
                        else:
                            updated_reservation = {
                                "Property Name": property_name,
                                "Room No": room_no,
                                "Guest Name": guest_name,
                                "Mobile No": mobile_no,
                                "No of Adults": safe_int(adults),
                                "No of Children": safe_int(children),
                                "No of Infants": safe_int(infants),
                                "Total Pax": total_pax,
                                "Check In": check_in,
                                "Check Out": check_out,
                                "No of Days": no_of_days,
                                "Tariff": safe_float(tariff),
                                "Total Tariff": total_tariff,
                                "Advance Amount": safe_float(advance_amount),
                                "Balance Amount": balance_amount,
                                "Advance MOP": custom_advance_mop if advance_mop == "Other" else advance_mop,
                                "Balance MOP": custom_balance_mop if balance_mop == "Other" else balance_mop,
                                "MOB": mob_value,
                                "Online Source": custom_online_source if online_source == "Others" else online_source,
                                "Invoice No": invoice_no,
                                "Enquiry Date": enquiry_date,
                                "Booking Date": booking_date,
                                "Booking ID": reservation["Booking ID"],
                                "Room Type": custom_room_type if room_type == "Other" else room_type,
                                "Breakfast": breakfast,
                                "Plan Status": plan_status,
                                "Submitted By": submitted_by,
                                "Modified By": modified_by,
                                "Modified Comments": modified_comments,
                                "Remarks": remarks,
                                "Payment Status": payment_status
                            }
                            if update_reservation_in_supabase(reservation["Booking ID"], updated_reservation):
                                st.session_state.reservations[edit_index] = updated_reservation
                                st.session_state.edit_mode = False
                                st.session_state.edit_index = None
                                st.success(f"✅ Reservation {reservation['Booking ID']} updated successfully!")
                                show_confirmation_dialog(reservation["Booking ID"], is_update=True)
                            else:
                                st.error("❌ Failed to update reservation")
            with col_btn2:
                if st.session_state.role == "Management":
                    if st.button("🗑️ Delete Reservation", key=f"{form_key}_delete", use_container_width=True):
                        if delete_reservation_in_supabase(reservation["Booking ID"]):
                            st.session_state.reservations.pop(edit_index)
                            st.session_state.edit_mode = False
                            st.session_state.edit_index = None
                            st.success(f"🗑️ Reservation {reservation['Booking ID']} deleted successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete reservation")
    except Exception as e:
        st.error(f"Error rendering edit form: {e}")

# ... (other unchanged functions: show_reservations, show_analytics, etc., omitted for brevity)

def show_reservations():
    """Display a list of reservations with an option to select one for editing."""
    try:
        st.header("📋 View Reservations")
        if not st.session_state.reservations:
            st.warning("No reservations available to view.")
            return
        booking_ids = [res["Booking ID"] for res in st.session_state.reservations]
        selected_booking = st.selectbox("Select Booking ID", booking_ids)
        if selected_booking:
            edit_index = booking_ids.index(selected_booking)
            st.session_state.edit_mode = True
            st.session_state.edit_index = edit_index
            show_edit_reservations(edit_index)
    except Exception as e:
        st.error(f"Error rendering reservations list: {e}")

def show_analytics():
    """Display reservation analysis with date range filtering."""
    try:
        st.header("📊 Reservation Analysis")
        df = pd.DataFrame(st.session_state.reservations)
        if df.empty:
            st.warning("No reservations available for analysis.")
            return
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=date.today() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date", value=date.today())
        display_filtered_analysis(df, start_date, end_date, view_mode=False)
    except Exception as e:
        st.error(f"Error rendering analytics: {e}")
