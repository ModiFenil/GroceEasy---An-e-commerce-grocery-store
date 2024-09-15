from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename  # Import secure_filename
import razorpay
import datetime
import logging
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MongoDB Configuration
app.config['MONGO_URI'] = "mongodb+srv://fenilmodi088:fenil_modi@cluster0.oyzoc.mongodb.net/user_info?retryWrites=true&w=majority"
mongo = PyMongo(app)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Razorpay Configuration
razorpay_client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))
# Logging Configuration
# logging.basicConfig(filename='app.log', level=logging.ERROR)

# Index Route (Redirects to home or signup)
@app.route('/', methods=['GET'])
def index():
    if 'username' in session:
        return redirect(url_for('home'))
    else:
        return redirect(url_for('signup'))

# Signup Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'username' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        phone = request.form['phone']
        profile_picture = request.files.get('profile_picture')
        hashed_password = generate_password_hash(password)
        profile_picture_url = None

        if profile_picture and allowed_file(profile_picture.filename):
            filename = secure_filename(profile_picture.filename)
            profile_picture.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            profile_picture_url = url_for('static', filename='uploads/' + filename)

        existing_user = mongo.db.users.find_one({'username': username})

        if existing_user is None:
            mongo.db.users.insert_one({
                'username': username,
                'password': hashed_password,
                'email': email,
                'phone': phone,
                'profile_picture': profile_picture_url
            })
            flash('You have successfully signed up! Please log in.')
            return redirect(url_for('login'))
        else:
            flash('User already exists! Please log in instead.')

    return render_template('signup.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = mongo.db.users.find_one({'username': username})

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            flash('Logged in successfully!')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials!')

    return render_template('login.html')

@app.before_request
def initialize_cart():
    if 'cart' not in session:
        session['cart'] = []

# Route to handle adding products to the cart
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product = request.json
    session['cart'].append(product)
    session.modified = True
    return jsonify({'success': True})

# Route to display the cart
@app.route('/cart')
def cart():
    if 'cart' in session:
        return render_template('cart.html', cart=session['cart'])
    else:
        flash('Your cart is empty!')
        return redirect(url_for('products'))

@app.route('/products')
def products():
    if 'username' not in session:
        flash('Please log in or sign up to view products!')
        return redirect(url_for('home'))
    return render_template('products.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# User Profile Route
@app.route('/user')
def user():
    if 'username' in session:
        user_data = mongo.db.users.find_one({'username': session['username']})
        return render_template('user.html', user=user_data)
    else:
        flash('Please login first!')
        return redirect(url_for('login'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'username' in session:
        username = session['username']
        email = request.form.get('email')
        phone = request.form.get('phone')
        profile_picture = request.files.get('profile_picture')

        updates = {
            'email': email,
            'phone': phone
        }

        if profile_picture and allowed_file(profile_picture.filename):
            filename = secure_filename(profile_picture.filename)
            profile_picture.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            profile_picture_url = url_for('static', filename='uploads/' + filename)
            updates['profile_picture'] = profile_picture_url

        mongo.db.users.update_one({'username': username}, {'$set': updates})

        flash('Profile updated successfully!')
        return redirect(url_for('user'))
    else:
        flash('Please log in first!')
        return redirect(url_for('login'))

# Home Route
@app.route('/home')
def home():
    if 'username' in session:
        orders = mongo.db.orders.find({'user': session['username']}).sort('order_date', -1)
        return render_template('home.html', username=session['username'], orders=orders)
    else:
        flash('Please log in or sign up to access product pages.')
        return redirect(url_for('signup'))

# Logout Route
@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out!')
    return redirect(url_for('login'))

# Checkout Route
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        if 'username' in session:
            name = request.form['name']
            address = request.form['address']
            city = request.form['city']
            postal_code = request.form['postal_code']

            cart_total = sum(item['price'] for item in session['cart'])

            order = razorpay_client.order.create({
                'amount': cart_total * 100,
                'currency': 'INR',
                'payment_capture': '1'
            })

            session['order_id'] = order['id']
            session['delivery_info'] = {
                'name': name,
                'address': address,
                'city': city,
                'postal_code': postal_code
            }

            return jsonify({'success': True, 'order_id': order['id'], 'cart_total': cart_total})

        else:
            flash('Please login first!')
            return redirect(url_for('login'))

    cart_total = sum(item['price'] for item in session['cart'])
    return render_template('checkout.html', cart_total=cart_total)

@app.route('/purchase_history')
def purchase_history():
    if 'username' in session:
        username = session['username']
        orders = mongo.db.orders.find({'user': username}).sort('order_date', -1)
        return render_template('history.html', orders=orders)
    else:
        flash('Please login first!')
        return redirect(url_for('login'))

# Route to handle removing items from the cart
@app.route('/remove_item', methods=['POST'])
def remove_item():
    data = request.get_json()
    item_id = data.get('itemId')
    cart = session.get('cart', [])
    updated_cart = [item for item in cart if item['id'] != item_id]
    session['cart'] = updated_cart
    total = sum(item['price'] for item in updated_cart)
    return jsonify({'success': True, 'cart': updated_cart, 'total': total})

# Route to handle payment success
@app.route('/payment_success', methods=['POST'])
def payment_success():
    if 'order_id' in session:
        order_id = session['order_id']
        delivery_info = session['delivery_info']
        cart_items = session['cart']
        total_amount = sum(item['price'] for item in cart_items)
        mongo.db.orders.insert_one({
            'order_id': order_id,
            'user': session['username'],
            'delivery_info': delivery_info,
            'items': cart_items,
            'order_date': datetime.datetime.now(),
            'total_amount': total_amount
        })
        session.pop('cart', None)
        return render_template('payment_success.html', order_id=order_id, items=cart_items, total_amount=total_amount)

    return redirect(url_for('home'))

# Error Handlers
# @app.errorhandler(404)
# def not_found_error(error):
#     return render_template('404.html'), 404

# @app.errorhandler(500)
# def internal_error(error):
#     return render_template('500.html'), 500

# @app.errorhandler(TemplateNotFound)
# def template_not_found_error(error):
#     logging.error(f'Template not found: {error}')
#     return render_template('404.html'), 404

# @app.errorhandler(Exception)
# def handle_exception(error):
#     logging.error(f'Unhandled exception: {error}')
#     return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
