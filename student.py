from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    url_for,
    request,
    jsonify,
)
# from face_recognition_utils import process_face_image
from utils import login_required
from datetime import datetime, timedelta, timezone
from config import db, users
from bson import ObjectId
import traceback
import calendar
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from dateutil.tz import tzutc


student_bp = Blueprint("student", __name__)


@student_bp.route("/student_dashboard")
@login_required
def student_dashboard():
    if session["user"]["role"] != "student":
        return redirect(url_for("index"))
    user_id = ObjectId(session["user"]["_id"])
    user = users.find_one({"_id": user_id})
    active_tab = request.args.get('active_tab', 'dashboard')
    return render_template("student_dashboard.html", user=user, active_tab=active_tab)

@student_bp.route("/student/capture_face", methods=["POST"])
@login_required
def capture_face():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        image_data = request.json.get("image_data")
        student_id = session["user"]["_id"]

        # Process the image and extract face encoding
        # # face_encoding = process_face_image(image_data)

        # if face_encoding is None:
        #     return jsonify({"success": False, "message": "No face detected in the image"}), 400

        # # Save face encoding to the database
        # users.update_one(
        #     {"_id": ObjectId(student_id)},
        #     {"$set": {"face_encoding": face_encoding.tolist()}}
        # )

        return jsonify({"success": True, "message": "Face captured successfully"})
    except Exception as e:
        print(f"Error capturing face: {str(e)}")
        return jsonify({"success": False, "message": "An error occurred while capturing the face"}), 500
    
@student_bp.route("/student/check_face_encoding", methods=["GET"])
@login_required
def check_face_encoding():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        student_id = session["user"]["_id"]
        student = users.find_one({"_id": ObjectId(student_id)})

        has_face_encoding = "face_encoding" in student and student["face_encoding"] is not None

        return jsonify({"success": True, "has_face_encoding": has_face_encoding})
    except Exception as e:
        print(f"Error checking face encoding: {str(e)}")
        return jsonify({"success": False, "message": "An error occurred while checking face encoding"}), 500
    
@student_bp.route("/student/submit_complaint", methods=["POST"])
@login_required
def student_submit_complaint():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        data = request.json
        subject = data.get("subject")
        description = data.get("description")

        if not all([subject, description]):
            return (
                jsonify({"success": False, "message": "Missing required fields"}),
                400,
            )

        complaint = {
            "user_id": session["user"]["username"],
            "user_role": "student",
            "subject": subject,
            "description": description,
            "status": "pending",
            "timestamp": datetime.utcnow(),
            "admin_comment": "",
        }

        result = db.complaints.insert_one(complaint)

        if result.inserted_id:
            return jsonify(
                {"success": True, "message": "Complaint submitted successfully"}
            )
        else:
            return (
                jsonify({"success": False, "message": "Failed to submit complaint"}),
                500,
            )

    except Exception as e:
        print(f"Error submitting complaint: {str(e)}")  # Log the error
        return (
            jsonify(
                {
                    "success": False,
                    "message": "An error occurred while submitting the complaint",
                }
            ),
            500,
        )


@student_bp.route("/student/get_user_complaints", methods=["GET"])
@login_required
def student_get_user_complaints():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    complaints = list(db.complaints.find({"user_id": session["user"]["username"]}))
    for complaint in complaints:
        complaint["_id"] = str(complaint["_id"])
        complaint["timestamp"] = complaint["timestamp"].isoformat()

    return jsonify({"success": True, "complaints": complaints})


@student_bp.route("/student/get_blocks", methods=["GET"])
@login_required
def get_blocks():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    blocks = list(db.blocks.find({}, {"name": 1}))
    for block in blocks:
        block["_id"] = str(block["_id"])
    return jsonify({"success": True, "blocks": blocks})


@student_bp.route("/student/get_current_room_info", methods=["GET"])
@login_required
def get_current_room_info():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        student_id = session["user"].get("_id")
        if not student_id:
            print("Student ID not found in session")
            print("Session user data:", session["user"])
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Student ID not found in session. Please log out and log in again.",
                    }
                ),
                400,
            )

        print(f"Searching for room assignment with student_id: {student_id}")
        room_assignment = db.room_assignments.find_one({"student_id": str(student_id)})

        if room_assignment:
            room_assignment["_id"] = str(room_assignment["_id"])
            print(f"Room assignment found: {room_assignment}")
            return jsonify({"success": True, "room_info": room_assignment})
        else:
            print("No room assignment found")
            return jsonify(
                {"success": True, "message": "No room assigned", "room_info": None}
            )
    except Exception as e:
        print(f"Error in get_current_room_info: {str(e)}")
        print(traceback.format_exc())
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"An error occurred while fetching room information: {str(e)}",
                }
            ),
            500,
        )


@student_bp.route("/student/get_floors/<block_id>", methods=["GET"])
@login_required
def get_floors(block_id):
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    block = db.blocks.find_one({"_id": ObjectId(block_id)})
    if not block:
        return jsonify({"success": False, "message": "Block not found"}), 404

    floors = [{"index": i, "number": i + 1} for i in range(len(block["floors"]))]
    return jsonify({"success": True, "floors": floors})


@student_bp.route(
    "/student/get_available_rooms/<block_id>/<int:floor_index>", methods=["GET"]
)
@login_required
def get_available_rooms(block_id, floor_index):
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    block = db.blocks.find_one({"_id": ObjectId(block_id)})
    if not block or floor_index >= len(block["floors"]):
        return jsonify({"success": False, "message": "Block or floor not found"}), 404

    floor = block["floors"][floor_index]
    rooms = []
    for room_type in ["single", "double", "triple"]:
        capacity = 1 if room_type == "single" else (2 if room_type == "double" else 3)

        for is_attached in [True, False]:
            room_numbers = floor[
                f"{room_type}{'Attached' if is_attached else 'NonAttached'}RoomNumbers"
            ]
            for room_number in room_numbers:
                occupancy = db.room_assignments.count_documents(
                    {
                        "block_id": str(block_id),
                        "floor_index": floor_index,
                        "room_number": room_number,
                    }
                )
                if occupancy < capacity:
                    rooms.append(
                        {
                            "number": room_number,
                            "type": room_type,
                            "attached": is_attached,
                            "available_beds": capacity - occupancy,
                        }
                    )

    return jsonify({"success": True, "rooms": rooms})


@student_bp.route("/student/request_room_change", methods=["POST"])
@login_required
def request_room_change():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    data = request.json
    student_id = session["user"]["_id"]
    student_name = session["user"].get(
        "username", "Unknown"
    )  # Use username instead of full_name

    room_change_request = {
        "student_id": str(student_id),
        "student_name": student_name,
        "block_id": data["blockId"],
        "floor_index": int(data["floorIndex"]),
        "room_number": data["roomNumber"],
        "reason": data["reason"],
        "status": "pending",
        "created_at": datetime.utcnow(),
    }

    result = db.room_change_requests.insert_one(room_change_request)
    if result.inserted_id:
        return jsonify(
            {"success": True, "message": "Room change request submitted successfully"}
        )
    else:
        return jsonify(
            {"success": False, "message": "Error submitting room change request"}
        )


@student_bp.route("/student/get_room_change_status", methods=["GET"])
@login_required
def get_room_change_status():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    student_id = session["user"]["_id"]
    request = db.room_change_requests.find_one(
        {
            "student_id": str(student_id),
            "status": {"$in": ["pending", "approved", "rejected"]},
        },
        sort=[("created_at", -1)],
    )

    if request:
        request["_id"] = str(request["_id"])
        request["created_at"] = request["created_at"].isoformat()
        block = db.blocks.find_one({"_id": ObjectId(request["block_id"])})
        request["block_name"] = block["name"] if block else "Unknown"
        return jsonify({"success": True, "request": request})
    else:
        return jsonify({"success": True, "request": None})


@student_bp.route("/student/submit_gatepass", methods=["POST"])
@login_required
def submit_gatepass():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        data = request.json
        reason = data.get("reason")
        departure_time = data.get("departureTime")
        return_time = data.get("returnTime")

        missing_fields = []
        if not reason:
            missing_fields.append("reason")
        if not departure_time:
            missing_fields.append("departureTime")
        if not return_time:
            missing_fields.append("returnTime")

        if missing_fields:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Missing required fields: {', '.join(missing_fields)}",
                    }
                ),
                400,
            )

        gatepass = {
            "student_id": session["user"]["_id"],
            "student_name": session["user"]["username"],
            "reason": reason,
            "departure_time": datetime.fromisoformat(departure_time),
            "return_time": datetime.fromisoformat(return_time),
            "status": "pending",
            "submitted_at": datetime.utcnow(),
        }

        result = db.gatepasses.insert_one(gatepass)

        if result.inserted_id:
            return jsonify(
                {"success": True, "message": "Gatepass submitted successfully"}
            )
        else:
            return (
                jsonify({"success": False, "message": "Failed to submit gatepass"}),
                500,
            )

    except Exception as e:
        print(f"Error submitting gatepass: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"An error occurred while submitting the gatepass: {str(e)}",
                }
            ),
            500,
        )


@student_bp.route("/student/get_student_gatepasses", methods=["GET"])
@login_required
def get_student_gatepasses():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    gatepasses = list(db.gatepasses.find({"student_id": session["user"]["_id"]}))
    for gatepass in gatepasses:
        gatepass["_id"] = str(gatepass["_id"])
        gatepass["departure_time"] = gatepass["departure_time"].isoformat()
        gatepass["return_time"] = gatepass["return_time"].isoformat()
        gatepass["submitted_at"] = gatepass["submitted_at"].isoformat()

    return jsonify({"success": True, "gatepasses": gatepasses})


@student_bp.route("/student/get_fee_info", methods=["GET"])
@login_required
def get_fee_info():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        student_id = session["user"]["_id"]
        print(f"Fetching fee info for student ID: {student_id}")  # Debug log

        student = users.find_one({"_id": ObjectId(student_id)})
        if not student:
            print(f"Student not found for ID: {student_id}")  # Debug log
            return jsonify({"success": False, "message": "Student not found"}), 404

        fee_settings = db.fee_settings.find_one()
        if not fee_settings:
            print("Fee settings not found")  # Debug log
            return jsonify({"success": False, "message": "Fee settings not found"}), 404

        join_date = student.get("join_date")
        if not join_date:
            print(f"Join date not found for student ID: {student_id}")  # Debug log
            return jsonify({"success": False, "message": "Student join date not found"}), 404

        # Ensure join_date is timezone-aware
        if isinstance(join_date, datetime):
            if join_date.tzinfo is None:
                join_date = join_date.replace(tzinfo=timezone.utc)
        else:
            # If it's a string, parse it and make it timezone-aware
            join_date = datetime.fromisoformat(join_date).replace(tzinfo=timezone.utc)

        print(f"Student join date: {join_date}")  # Debug log

        current_date = datetime.now(timezone.utc)
        print(f"Current date: {current_date}")  # Debug log

        upcoming_payments = []

        if join_date <= current_date:
            approved_reductions = list(db.mess_fee_reductions.find({
                "student_id": ObjectId(student_id),
                "status": "approve"
            }))
            print(f"Approved reductions: {approved_reductions}")  # Debug log

            for i in range(0, 12):  # Check current month and up to 11 previous months
                mess_fee_due_date = get_next_mess_fee_due_date(current_date, fee_settings["messFeeDay"], -i)
                if mess_fee_due_date < join_date:
                    break

                mess_fee_amount = fee_settings["messFee"]
                month_name = mess_fee_due_date.strftime("%B %Y")
                description = f"Mess Fee {month_name}"

                print(f"Checking mess fee for {month_name}")  # Debug log
                print(f"Mess fee due date: {mess_fee_due_date}")  # Debug log

                # Check for applicable reduction
                applicable_reduction = next((r for r in approved_reductions if 
                    r["end_date"].replace(tzinfo=timezone.utc).date() >= mess_fee_due_date.replace(day=1).date() and
                    r["end_date"].replace(tzinfo=timezone.utc).date() <= (mess_fee_due_date.replace(day=1) + relativedelta(months=1) - relativedelta(days=1)).date()
                ), None)
                print(f"Applicable reduction found: {applicable_reduction}")  # Debug log

                if applicable_reduction:
                    print(f"Applying reduction for {month_name}: {applicable_reduction['reduced_amount']}")  # Debug log
                    mess_fee_amount -= applicable_reduction["reduced_amount"]
                    print(f"Reduced mess fee amount: {mess_fee_amount}")  # Debug log

                if not is_payment_made(student_id, description, mess_fee_due_date):
                    mess_fee_late_amount = calculate_late_fee(mess_fee_due_date, current_date, fee_settings["messFeeLateFee"])
                    upcoming_payments.append({
                        "dueDate": mess_fee_due_date.isoformat(),
                        "description": description,
                        "amount": mess_fee_amount,
                        "lateAmount": mess_fee_late_amount,
                        "status": "Overdue" if current_date > mess_fee_due_date else "Pending"
                    })
                    print(f"Added upcoming payment for {month_name}: {mess_fee_amount}")  # Debug log

            # Calculate hostel rent (unchanged)
            rent_due_date = fee_settings["rentDueDate"].replace(year=current_date.year, tzinfo=timezone.utc)
            if rent_due_date < current_date:
                rent_due_date = rent_due_date.replace(year=current_date.year + 1)
            
            if join_date <= rent_due_date:
                rent_fee_amount = fee_settings["rentFee"]
                rent_fee_late_amount = calculate_late_fee(rent_due_date, current_date, fee_settings["rentFeeLateFee"])
                
                description = f"Hostel Rent {rent_due_date.year}"
                
                if not is_payment_made(student_id, description, rent_due_date):
                    upcoming_payments.append({
                        "dueDate": rent_due_date.isoformat(),
                        "description": description,
                        "amount": rent_fee_amount,
                        "lateAmount": rent_fee_late_amount,
                        "status": "Overdue" if current_date > rent_due_date else "Pending"
                    })
                    print(f"Added upcoming payment for rent: {rent_fee_amount}")  # Debug log

        fee_info = {
            "joinDate": join_date.isoformat(),
            "messFeeDay": fee_settings["messFeeDay"],
            "messFee": fee_settings["messFee"],
            "rentDueDate": fee_settings["rentDueDate"].strftime("%B %d"),
            "rentFee": fee_settings["rentFee"],
            "upcomingPayments": upcoming_payments
        }

        print(f"Final fee info: {fee_info}")  # Debug log

        return jsonify({"success": True, "feeInfo": fee_info})
    except Exception as e:
        print(f"Error in get_fee_info: {str(e)}")
        print(traceback.format_exc())  # Print the full traceback for debugging
        return jsonify({"success": False, "message": f"An error occurred: {str(e)}"}), 500
def get_next_mess_fee_due_date(current_date, due_day, months_ahead=0):
    next_date = current_date.replace(day=1, tzinfo=timezone.utc) + relativedelta(months=months_ahead)
    next_date = next_date.replace(
        day=min(due_day, calendar.monthrange(next_date.year, next_date.month)[1])
    )
    return next_date


def calculate_late_fee(due_date, current_date, daily_late_fee):
    if current_date <= due_date:
        return 0
    days_late = (current_date - due_date).days
    return min(days_late * daily_late_fee, 500)  # Cap the late fee at 500 Rs


def is_payment_made(student_id, description, due_date):
    payment = db.payments.find_one(
        {
            "student_id": student_id,
            "description": description,
            "payment_date": {
                "$gte": due_date - timedelta(days=30),
                "$lte": datetime.now(timezone.utc),
            },
        }
    )
    return payment is not None


@student_bp.route("/student/get_notices", methods=["GET"])
@login_required
def get_notices():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    notices = list(db.notices.find({"$or": [{"target": "all"}, {"target": "students"}]}).sort("posted_date", -1))
    for notice in notices:
        notice["_id"] = str(notice["_id"])
        notice["posted_date"] = notice["posted_date"].isoformat()

    return jsonify({"success": True, "notices": notices})

@student_bp.route("/profile")
@login_required
def profile():
    user_id = ObjectId(session["user"]["_id"])
    user = users.find_one({"_id": user_id})
    return render_template("student/profile.html", user=user)

@student_bp.route("/student/submit_meal_feedback", methods=["POST"])
@login_required
def submit_meal_feedback():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    data = request.json
    feedback = {
        "student_id": session["user"]["_id"],
        "student_name": session["user"]["username"],
        "feedback": data["feedback"],
        "submitted_at": datetime.utcnow()
    }

    result = db.meal_feedback.insert_one(feedback)
    if result.inserted_id:
        return jsonify({"success": True, "message": "Feedback submitted successfully"})
    else:
        return jsonify({"success": False, "message": "Failed to submit feedback"}), 500
    
    
@student_bp.route("/student/get_attendance", methods=["GET"])
@login_required
def get_student_attendance():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        student_id = session["user"]["_id"]
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not start_date or not end_date:
            return jsonify({"success": False, "message": "Start and end dates are required"}), 400

        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        attendance_records = list(db.attendance.find({
            "student_id": str(student_id),
            "date": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            }
        }))

        calendar_data = []
        current_date = start_date
        while current_date <= end_date:
            is_present = any(record["date"] == current_date.isoformat() for record in attendance_records)
            calendar_data.append({
                "date": current_date.isoformat(),
                "status": "present" if is_present else "absent"
            })
            current_date += timedelta(days=1)

        return jsonify({
            "success": True,
            "attendance": calendar_data
        })
    except Exception as e:
        print(f"Error fetching student attendance: {str(e)}")
        return jsonify({"success": False, "message": "An error occurred while fetching attendance"}), 500
    
    
@student_bp.route("/student/request_visitor_pass", methods=["POST"])
@login_required
def request_visitor_pass():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        data = request.json
        visitor_name = data.get("visitorName")
        relation = data.get("relation")
        visit_date = data.get("visitDate")
        visit_time = data.get("visitTime")
        purpose = data.get("purpose")

        if not all([visitor_name, relation, visit_date, visit_time, purpose]):
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        visitor_pass = {
            "student_id": session["user"]["_id"],
            "student_name": session["user"]["username"],
            "visitor_name": visitor_name,
            "relation": relation,
            "visit_date": datetime.fromisoformat(visit_date),
            "visit_time": visit_time,
            "purpose": purpose,
            "status": "pending_parent",
            "parent_approval": None,
            "admin_approval": None,
            "submitted_at": datetime.utcnow(),
        }

        result = db.visitor_passes.insert_one(visitor_pass)

        if result.inserted_id:
            return jsonify({"success": True, "message": "Visitor pass request submitted successfully"})
        else:
            return jsonify({"success": False, "message": "Failed to submit visitor pass request"}), 500

    except Exception as e:
        print(f"Error submitting visitor pass request: {str(e)}")
        return jsonify({"success": False, "message": f"An error occurred: {str(e)}"}), 500

@student_bp.route("/student/get_visitor_passes", methods=["GET"])
@login_required
def get_visitor_passes():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        visitor_passes = list(db.visitor_passes.find({"student_id": session["user"]["_id"]}))
        for pass_ in visitor_passes:
            pass_["_id"] = str(pass_["_id"])
            pass_["visit_date"] = pass_["visit_date"].isoformat()
            pass_["submitted_at"] = pass_["submitted_at"].isoformat()

        return jsonify({"success": True, "visitorPasses": visitor_passes})
    except Exception as e:
        print(f"Error fetching visitor passes: {str(e)}")
        return jsonify({"success": False, "message": f"An error occurred: {str(e)}"}), 500
    
@student_bp.route("/student/submit_mess_fee_reduction", methods=["POST"])
@login_required
def submit_mess_fee_reduction():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        data = request.json
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        reason = data.get("reason")

        print(f"Received data: start_date={start_date}, end_date={end_date}, reason={reason}")  # Debug log

        if not all([start_date, end_date, reason]):
            missing_fields = [field for field in ["start_date", "end_date", "reason"] if not data.get(field)]
            return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing_fields)}"}), 400

        try:
            start_date = datetime.fromisoformat(start_date)
            end_date = datetime.fromisoformat(end_date)
        except ValueError as e:
            return jsonify({"success": False, "message": f"Invalid date format: {str(e)}"}), 400

        if end_date <= start_date:
            return jsonify({"success": False, "message": "End date must be after start date"}), 400

        if (end_date - start_date).days < 10:
            return jsonify({"success": False, "message": "Leave must be for at least 10 days"}), 400

        reduction_request = {
            "student_id": ObjectId(session["user"]["_id"]),
            "student_name": session["user"]["username"],
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
            "status": "pending",
            "submitted_at": datetime.utcnow()
        }

        result = db.mess_fee_reductions.insert_one(reduction_request)

        if result.inserted_id:
            return jsonify({"success": True, "message": "Mess fee reduction request submitted successfully"})
        else:
            return jsonify({"success": False, "message": "Failed to submit mess fee reduction request"}), 500
    except Exception as e:
            print(f"Error in submit_mess_fee_reduction: {str(e)}")
            print(traceback.format_exc())  # Print the full traceback for debugging
            return jsonify({"success": False, "message": f"An error occurred: {str(e)}"}), 500

from bson import ObjectId

@student_bp.route("/student/get_mess_fee_reductions", methods=["GET"])
@login_required
def get_mess_fee_reductions():
    if session["user"]["role"] != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        student_id = ObjectId(session["user"]["_id"])
        reductions = list(db.mess_fee_reductions.find({"student_id": student_id}))
        
        for reduction in reductions:
            reduction["_id"] = str(reduction["_id"])
            reduction["student_id"] = str(reduction["student_id"])
            reduction["start_date"] = reduction["start_date"].isoformat()
            reduction["end_date"] = reduction["end_date"].isoformat()
            reduction["submitted_at"] = reduction["submitted_at"].isoformat()

        return jsonify({"success": True, "reductions": reductions})
    except Exception as e:
        print(f"Error in get_mess_fee_reductions: {str(e)}")
        print(traceback.format_exc())  # Print the full traceback for debugging
        return jsonify({"success": False, "message": f"An error occurred: {str(e)}"}), 500