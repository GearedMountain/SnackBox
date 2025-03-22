# also install psycopg2 dependency of flask_sqlalchemy
from flask import Flask, request, send_from_directory, render_template, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy import text
import random

app = Flask(__name__)
app.secret_key = "god_i_hate_python"

# Connect to postgres database
# Utilize environment variable with dotenv for production rollout 
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://gamer:6644@192.168.50.210/pikenet'

db = SQLAlchemy(app)

# GAME VARIABLES
gameStarted = False

# Setup up SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Track users sessions in memory
active_sessions = set()
snackCount = 0
snacks = {}
ratedSnacks = {}

currentlyRating = ""

# Class for all game data
availableRatings = {}



def generate_random_id():
	return str(random.randint(100000,999999))

@app.route('/start_game',methods=['POST'])
def start_game():
	global gameStarted
	global availableRatings
	gameStarted = True
	print ("initializing game")
	for i in active_sessions:
		availableRatings[i] = [0] * snackCount
		for j in range(snackCount):
			availableRatings[i][j] = j+1
		print(availableRatings[i])

	socketio.emit('start_game',{'data':True})	

	
	#emit('update_playerlist', {'playerlist': ":".join(active_sessions)}, broadcast=True)
	
	return render_template('snackbox.html')
	

@app.route('/snackbox')
def snackbox():
	global gameStarted
	if gameStarted:
		return render_template('snackbox.html')
	else:
		return "game hasn't started"
	
@socketio.on('next_snack')
def next_snack(data):
	global ratedSnacks
	if len(snacks) == 0 :
		print("finished")
		emit('snacks_finished',ratedSnacks,broadcast=True)

	else:
		emit('update_snacklist',snacks,broadcast=True)
		emit('next_snack_server',snacks,broadcast=True)
		emit('update_available_ratings',{'availableRating':availableRatings[session['user']]})	


@socketio.on('snack_rated')
def snack_rated(data):
	global availableRatings
	rating = int(data['rating'])
	logMessage = f"{session['user']} rated {currentlyRating} a {data['rating']}"
	availableRatings[session['user']][rating-1] = 0
	print ( availableRatings[session['user']] )
	ratedSnacks[currentlyRating] += int(data['rating'])
	emit('snack_rated_server',{ 'message' : logMessage, 'snacksRating' : ratedSnacks[currentlyRating]},broadcast=True)
	emit('update_available_ratings',{'availableRating':availableRatings[session['user']]})	


@socketio.on('snack_selected')
def snack_selected(data):
	global snacks
	global currentlyRating
	global ratedSnacks
	selected = data['id']
	selectedName = snacks[int(selected)]
	currentlyRating = selectedName
	ratedSnacks[currentlyRating] = 0
	print(f"Snack selected: {selectedName}" )
	pop = snacks.pop(int(selected))
	# = data['ID']
	emit('snack_selected_server', {'snackSelected' : selectedName} ,broadcast=True)
	emit('update_snacklist',snacks,broadcast=True)


@socketio.on('snack_updated')
def change_snack(data):
	global snacks
	snacks[data['id']] = data['newName']
	emit('update_snacklist',snacks,broadcast=True)
	
	
@socketio.on('snack_added')
def add_snack(data):
	global snackCount
	global snacks
	snackCount += 1
	print (f"received snack: {data['name']} for a total of {snackCount}" )
	snacks[snackCount] = data['name']
	emit('update_snacklist',snacks,broadcast=True)

@app.route('/')
def index():
#	if 'user_id' not in session:
#		session['user_id'] = generate_random_id()
#		active_sessions.add(session['user_id'])	
#		print ("New Player ID Created")
	if 'user' in session:
		print ("session already created")
		return render_template('lobby.html',username=session['user'])
	else:
		return render_template('index.html')

# Receive users username they choose
@app.route('/submit_username', methods=['POST'])
def username_selected():
	if 'user' not in session:
		username = request.form['username']
		session['user'] = username
		print ("username selected: " + request.form['username']) 
	else:
		print ("user already has session")
	return render_template('lobby.html', username=session['user'])

@socketio.on('connect')
def socket_connected():
	global gameStarted
	if gameStarted:
		print(availableRatings[session['user']])
		socketio.emit('update_available_ratings',{'availableRating':availableRatings[session['user']]})	
	
	if 'user' in session:
		username = session['user']
		active_sessions.add(username)
	print (session['user'])
	result = db.session.execute(text('SELECT * FROM public."users" WHERE "username" = :username'), {'username': session['user']})

	user = result.fetchone()

	if user:
		print (f"{user[1]} has user id: {user[0]}")
	else:
		print ("user not found")
    # Check if the user was found
    

	print (f"Client Joined, current count: {len(active_sessions)}")
	emit('update_playerlist', {'playerlist': ":".join(active_sessions)}, broadcast=True)
	emit('update_snacklist',snacks)


@socketio.on('disconnect')
def socket_disconnected():
	username = session['user']
	print (f"Player {username} leaving")
	#user = session.get('user')
	if username in active_sessions:
		active_sessions.remove(username)
	print (f" {username} Removed From Playerlist")	
	emit('update_playerlist', {'playerlist': ":".join(active_sessions)}, broadcast=True)	

	#session.pop(username,None)

@app.route('/reset')
def reset():
	session.clear()
	active_sessions.clear()
	print ("reset")
	return "reset"

# Static image return
@app.route('/images/<filename>')
def serve_image(filename):
		return send_from_directory('images',filename)

@app.route('/styles/<filename>')
def serve_style(filename):
		return send_from_directory('styles',filename)

if __name__ == '__main__':
	socketio.run(app, debug=True)
