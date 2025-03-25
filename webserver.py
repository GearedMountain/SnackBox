countryName = "Columbia"
from datetime import datetime

current_year = datetime.now().year
sessionId = f'{countryName}{current_year}'
# also install psycopg2 dependency of flask_sqlalchemy
from flask import Flask, request, send_from_directory, render_template, session, Response
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy import text
import os
import random

app = Flask(__name__)
app.secret_key = "god_i_hate_python"

# Connect to postgres database
# Utilize environment variable with dotenv for production rollout 
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://gamer:6644@192.168.50.210/pikenet'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

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
ratingLogs = {}

# Name of the snack currently rating, set to 0 when finished for logic to see if still rating
currentlyRating = 0

# Playercount for votes expected, playersrated for how many have casted
playerCount = 0
playersRated = 0
# Class for all game data
availableRatings = {}

# Make the upload folder if it doesnt exist 
UPLOAD_FOLDER = 'uploads'  # Change this to your desired folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure folder exists

def generate_random_id():
	return str(random.randint(100000,999999))

@app.route('/start_game',methods=['POST'])
def start_game():
	global gameStarted
	global availableRatings
	global playerCount
	playerCount = 0
	gameStarted = True
	print ("initializing game")
	for i in active_sessions:
		availableRatings[i] = [0] * snackCount
		playerCount += 1
		for j in range(snackCount):
			availableRatings[i][j] = j+1
		print(availableRatings[i])
		
	print(f"Game Playercount: {playerCount}")
	
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
	global currentlyRating 
	global playersRated
	playersRated = 0
	currentlyRating = 0
	if len(snacks) == 0 :
		emit('snacks_finished',ratedSnacks,broadcast=True)

	else:
		emit('update_snacklist',snacks,broadcast=True)
		emit('next_snack_server',snacks,broadcast=True)
		#emit('update_available_ratings',{'availableRating':availableRatings[session['user']]})	


@socketio.on('snack_rated')
def snack_rated(data):
	global availableRatings
	global ratingLogs
	global playersRated
	global playerCount

	playersRated += 1

	if playersRated == playerCount:
		print("ALL PLAYERS HAVE VOTED")
		emit('all_players_voted',broadcast=True)
	rating = int(data['rating'])
	logMessage = f"{session['user']} rated {currentlyRating} a {data['rating']}"
	availableRatings[session['user']][rating-1] = 0
	print ( availableRatings[session['user']] )
	ratedSnacks[currentlyRating] += int(data['rating'])

	ratingLogs[session['user']] = [currentlyRating, data['rating']]
	emit('snack_rated_server',{ 'message' : logMessage, 'snacksRating' : ratedSnacks[currentlyRating]},broadcast=True)
	emit('update_available_ratings',{'availableRatings':availableRatings[session['user']]})	
	emit('update_rating_logs',ratingLogs)

@socketio.on('snack_selected')
def snack_selected(data):
	global snacks
	global currentlyRating
	global ratedSnacks
	global ratingLogs
	global playersRated
	playersRated = 0
	ratingLogs = {}

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
	

	try:
		oldname = snacks[int(data['id'])]
		print(f'snack {oldname} updated')
		query = text('UPDATE public.snacks SET name = :snackname WHERE name = :oldname')
		db.session.execute(query, {'snackname': data['newName'],'oldname': oldname})  
		result = db.session.commit()
		snacks[int(data['id'])] = data['newName']
	except:
		print("Name change failed")
	#emit('update_snacklist',snacks,broadcast=True)

@socketio.on('snack_added')
def add_snack(data):
	global snackCount
	global snacks
	global sessionId
		
	try:
		query = text('INSERT INTO public.snacks (name, "sessionId") VALUES (:snackname, :sessionId)')
		db.session.execute(query, {'snackname': data['name'],'sessionId': sessionId})  
		result = db.session.commit()

		snackCount += 1
		print (f"received snack: {data['name']} for a total of {snackCount}" )
		snacks[snackCount] = data['name']
	except:
		print("snack already exists")
	
	# Add snack to database
	
	emit('update_snacklist',snacks,broadcast=True)



# Uploaded a photo of the snack

# Helper function to check extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/upload', methods=['POST'])
def upload_file():
    
	file = request.files['file']
	snackname = request.form['snackname']
	print("receive image for the following snack: ")
	print(snackname)
	if file and allowed_file(file.filename): 
        # Read the image as binary data
		result = db.session.execute(text("SELECT id FROM public.snacks WHERE name = :name"), {'name': snackname})
		print(result.fetchone())
        # Insert file info and binary photo into the PostgreSQL database using raw SQL with SQLAlchemy

		# Store the file in the local server storage
		global UPLOAD_FOLDER
		file_path = os.path.join(UPLOAD_FOLDER, "1234")
		file.save(file_path)
		
        # Using db.session.execute() to run the raw SQL query
		
		#socketio.emit('refresh_lobby', room=request.sid)
		socketio.emit('update_snacklist',snacks)
		
	return Response(status=302, headers={"Location": "/"})

		#return render_template('lobby.html',username=session['user'])


	return "File not allowed"

# Retrieve uploaded photo
@app.route('/image/<string:snackname>')
def get_image(snackname):
    # Open a new session to query the database
	
	try:
        # Query the database for the image data using SQLAlchemy
		result = db.session.execute(text("SELECT photo FROM public.snacks WHERE name = :name"), {'name': snackname})

		snack = result.fetchone()
		print("Fetching image")
		print(snack[0])
		if result and snack[0]:
            # The image is stored in a bytea column, so we return the raw bytes
			return Response(snack[0], mimetype='image/jpeg')  # Adjust mimetype if different
		else:
			return "Image not found", 404
	finally:
		print("finished")

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
	global ratingLogs
	global currentlyRating
	global playersRated
	global playerCount

	socketio.emit('whats_my_name',session['user'], room=request.sid)
	if gameStarted:
		if currentlyRating != 0:
			socketio.emit('snack_selected_server', {'snackSelected' : currentlyRating}, room=request.sid)
			socketio.emit('update_rating_logs',ratingLogs, room=request.sid)
		if playersRated == playerCount:
			# If everyone has voted, give relog the next snack button if lost
			socketio.emit('all_players_voted', room=request.sid)
			
		print(availableRatings[session['user']])

		
		socketio.emit('update_available_ratings',{'availableRatings':availableRatings[session['user']]}, room=request.sid)	
	
	if 'user' in session:
		username = session['user']
		active_sessions.add(username)
	print (session['user'])
	#result = db.session.execute(text('SELECT * FROM public."users" WHERE "username" = :username'), {'username': session['user']})

	#user = result.fetchone()

	#if user:
	#	print (f"{user[1]} has user id: {user[0]}")
	#else:
	#	print ("user not found")
    # Check if the user was found
    

	print (f"Client Joined, current count: {len(active_sessions)}")
	emit('update_playerlist', {'playerlist': ":".join(active_sessions)}, broadcast=True)
	emit('update_snacklist',snacks)


@socketio.on('disconnect')
def socket_disconnected():
	try:
		username = session['user']
	#user = session.get('user')
		if username in active_sessions:
		
			print (f"Player {username} leaving")
			active_sessions.remove(username)
		print (f" {username} Removed From Playerlist")	
	except:
		print("disconnected user failed")

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
		print(f"Fetching image {filename}")
		return send_from_directory('images',filename)

@app.route('/styles/<filename>')
def serve_style(filename):
		return send_from_directory('styles',filename)

if __name__ == '__main__':
	#if not os.path.exists(app.config['UPLOAD_FOLDER']):
	#	os.makedirs(app.config['UPLOAD_FOLDER'])

	socketio.run(app, debug=True)
