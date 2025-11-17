from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from .models import User, ParkingLot, ParkingSpot, Reservation

from . import db
from sqlalchemy import text
from datetime import datetime, timedelta 
import traceback



bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        
        if user:
            login_user(user)
            flash('Login successful!', "success")
            return redirect(url_for('main.user_dashboard'))
        else:
            flash('Invalid credentials!', "danger")
    return render_template('user_login.html')

@bp.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST': 
        username = request.form['username']
        password = request.form['password']
        admin = User.query.filter_by(username=username, password=password, role='admin').first()
        if admin:
            login_user(admin)
            flash('Admin login successful!', "success")
            return redirect(url_for('main.admin_dashboard'))
        else:
            flash('Invalid admin credentials!', "danger")
            return redirect(url_for('main.admin_login'))
    return render_template('admin_login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', "info")
            return redirect(url_for('main.register'))
        user = User(username=username, password=password, role='user')
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', "success")
        return redirect(url_for('main.user_login'))
    return render_template('register.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.user_login'))


@bp.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))
    lots = ParkingLot.query.all()
    return render_template('admin_dashboard.html', lots=lots)

@bp.route('/user')
@login_required
def user_dashboard():
    if current_user.role != 'user':
        return redirect(url_for('main.index'))
    lots = ParkingLot.query.all()

    lot_data = []
    for lot in lots:
        total_spots = lot.max_spots
        booked_spots = sum(1 for spot in lot.spots if spot.status == 'O')
        available_spots = total_spots - booked_spots

        occupied_count = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()

        user_spots = db.session.query(ParkingSpot).join(Reservation).filter(
            Reservation.user_id == current_user.id,
            ParkingSpot.lot_id == lot.id
        ).all()        
        # Route logic:
        lot_data.append({
            'lot': lot,
            'total_spots': total_spots,
            'booked_spots': occupied_count,
            'user_booked_spots': user_spots,
            'user_reservations': len(user_spots)
            
        })


    return render_template('user_dashboard.html', lots=lot_data)

@bp.route('/admin/add_lot', methods = ["GET", "POST"])
@login_required
def add_lot():
    # Checking role first
    if current_user.role != 'admin':
        flash("Please login as Admin")
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        try:
            Lot_Name = request.form['name']
            Address = request.form['address']
            PinCode = request.form['pincode']
            Price = float(request.form['price'])
            Spots = int(request.form['max_spots'])
            # DB logic
            new_lot = ParkingLot(
                name = Lot_Name,
                address = Address,
                pincode = PinCode,
                price_per_hour = Price,
                max_spots = Spots,
            )
            db.session.add(new_lot)
            db.session.commit()
            db.session.flush()

            flash("Parking lot added Successfully!")
            return redirect(url_for('main.admin_dashboard'))
        except KeyError as e:
            flash(f"Missing fields : {e}")

    return render_template('add_lot.html')


@bp.route('/admin/edit_lot/<int:lot_id>', methods=["GET", "POST"])
@login_required
def edit_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)

    if request.method == 'POST':
        lot.name = request.form['name']
        lot.address = request.form['address']
        lot.pincode = request.form['pincode']
        lot.price_per_hour = request.form['price']
        lot.max_spots = request.form['max_spots']
        db.session.commit()
        flash("Parking lot updated successfully!")
        return redirect(url_for('main.admin_dashboard'))

    return render_template('add_lot.html', lot=lot)

@bp.route('/admin/delete_lot/<int:lot_id>', methods=["GET","POST"])
@login_required
def delete_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)

    # Only admin can delete
    if current_user.role != 'admin':
        flash("Unauthorized access")
        return redirect(url_for('main.admin_dashboard'))

    db.session.delete(lot)
    db.session.commit()
    flash("Parking lot deleted successfully!")
    return redirect(url_for('main.admin_dashboard'))


@bp.route('/admin/parking_spots', methods=["GET", "POST"])
@login_required
def view_parking_spot():
    return render_template('parking_spots.html')

@bp.route('/user/book/<int:lot_id>', methods=["GET", "POST"])
@login_required
def book_spot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)

    if request.method == "POST":
        # Find or create available spot
        spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()

        if not spot:
            spot = ParkingSpot(
                lot_id=lot_id,
                status='O',
                booked_by=current_user.id
            )
            db.session.add(spot)
            db.session.flush()
        else:
            spot.status = 'O'
            spot.booked_by = current_user.id

        # Create reservation
        name = request.form.get('name')
        vehicle_number = request.form.get('vehicle_number')
        phone_number = request.form.get('phone')

        now = datetime.now()
        leaving_time = now + timedelta(hours=2)
        total_cost = 2 * lot.price_per_hour

        reservation = Reservation(
            user_id=current_user.id,
            user_name=name,
            spot_id=spot.id,
            parking_time=now,
            leaving_time=leaving_time,
            cost=total_cost,
            vehicle_number=vehicle_number,
            phone_number=phone_number
        )

        db.session.add(reservation)
        db.session.commit()

        # Return same page with confirmation popup
        return render_template("booking_form.html", spot=spot, lot_id=lot_id)

    # If request GET - just show form
    return render_template('booking_form.html', lot_id=lot_id)


@bp.route('/release/<int:spot_id>', methods=['POST'])
@login_required
def release_spot(spot_id):
    # Fetch the spot
    spot = ParkingSpot.query.get_or_404(spot_id)

    # Ensure current user owns this spot
    if spot.booked_by != current_user.id:
        flash("You cannot release someone else's spot!", "danger")
        return redirect(url_for('main.user_dashboard'))

    # Update spot status
    spot.status = 'A'
    spot.booked_by = None

    # Optional: Delete reservation if tied
    Reservation.query.filter_by(spot_id=spot.id, user_id=current_user.id).delete()

    db.session.commit()
    flash("Spot released successfully!", "success")
    return redirect(url_for('main.user_dashboard'))


# Routes for checking Reservation data 

@bp.route('/admin/reservation_data/reservations')
@login_required
def show_reservations():
    reservations = db.session.execute(text("SELECT * FROM reservation")).fetchall()
    return render_template('reservation_data.html', reservations=reservations)

@bp.route('/admin/reservation_data/reservation/edit/<int:reservation_id>', methods=['GET', 'POST'])
def edit_reservation(reservation_id):
    # Fetch, update, and save reservation
    ...

@bp.route('/admin/reservation_data/reservation/delete/<int:reservation_id>', methods=['GET'])
def delete_reservation(reservation_id):
    db.session.execute(text("DELETE FROM reservation WHERE id = :id"), {"id": reservation_id})
    db.session.commit()
    return redirect(url_for('main.show_reservations'))

# Routes for checking Parking spots

@bp.route('/admin/available_parking_data/parking_slot_data')
@login_required
def show_parkingspotdata():
    parking_data = ParkingSpot.query.all()
#    parking_data = db.session.execute(text("SELECT * from parking_spot")).fetchall()
    return render_template('parking_spot_data.html', parking_data = parking_data)

@bp.route('/admin/available_parking_data/parking_spot_data/delete/<int:parking_spot_id>', methods = ['GET'])
@login_required
def delete_parking_spot(parking_spot_id):
    db.session.execute(text('DELETE FROM parking_spot WHERE id = :id'), {"id": parking_spot_id})
    db.session.commit()
    return redirect(url_for('main.show_parkingspotdata'))