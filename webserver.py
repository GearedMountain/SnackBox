countryName = "Czechia"
from datetime import datetime

current_year = datetime.now().year
sessionId = f'{countryName}{current_year}'
# also install psycopg2 dependency of flask_sqlalchemy
from flask import Flask, request, send_from_directory, render_template, session, Response, redirect, url_for
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
GAMESTARTED = False

# Setup up SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Track users sessions in memory
SET_ACTIVESESSIONS = set()
SNACKCOUNT = 0
DICT_SNACKS = {}
DICT_RATEDSNACKS = {}
DICT_RATINGLOGS = {}

# Name of the snack currently rating, set to 0 when finished for logic to see if still rating
CURRENTLYRATING = 0

# PLAYERCOUNT for votes expected, PLAYERSRATED for how many have casted
PLAYERCOUNT = 0
PLAYERSRATED = 0
# Class for all game data
AVAILABLERATINGS = {}

# Make the upload folder if it doesnt exist 
UPLOAD_FOLDER = 'uploads'  # Change this to your desired folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure folder exists

# Grab all current snacks from the database using the current session ID
with app.app_context():
	result = db.session.execute(text('SELECT * FROM public.snacks WHERE "sessionId" = :sessionId'), {'sessionId' : sessionId})
	for row in result:
		id = row.id
		SNACKCOUNT += 1
		DICT_SNACKS[row.id] = row.name
		print(DICT_SNACKS) 

# Zero out variables for restarting the game
def setup_game_configurations():
	global SNACKCOUNT

	SNACKCOUNT = 0
	result = db.session.execute(text('SELECT * FROM public.snacks WHERE "sessionId" = :sessionId'), {'sessionId' : sessionId})
	for row in result:
		id = row.id
		SNACKCOUNT += 1
		DICT_SNACKS[row.id] = row.name
	print(f"Final snacklist: {DICT_SNACKS}") 

# SUPPORTING FUNCTIONS
def generate_random_id():
	return str(random.randint(100000,999999))

# USER ENTERS WEBSITE
@app.route('/')
def index():
	
	if 'user' in session:
		print ("session already created")
		return render_template('lobby.html',username=session['user'], nation=countryName)
	else:
		return render_template('index.html')

@app.route('/start_game',methods=['POST'])
def start_game():
	global GAMESTARTED
	global AVAILABLERATINGS
	global PLAYERCOUNT
	PLAYERCOUNT = 0
	GAMESTARTED = True
	print ("initializing game")
	for i in SET_ACTIVESESSIONS:
		AVAILABLERATINGS[i] = [0] * SNACKCOUNT
		PLAYERCOUNT += 1
		for j in range(SNACKCOUNT):
			AVAILABLERATINGS[i][j] = j+1
			
	socketio.emit('start_game',{'data':True})	
	#emit('update_playerlist', {'playerlist': ":".join(SET_ACTIVESESSIONS)}, broadcast=True)
	
	return render_template('snackbox.html')
	

@app.route('/snackbox')
def snackbox():
	global GAMESTARTED
	if GAMESTARTED:
		return render_template('snackbox.html')
	else:
		return redirect('/')
	
@socketio.on('next_snack')
def next_snack(data):
	global DICT_RATEDSNACKS
	global CURRENTLYRATING 
	global PLAYERSRATED
	PLAYERSRATED = 0
	CURRENTLYRATING = 0
	if len(DICT_SNACKS) == 0 :
		emit('snacks_finished',DICT_RATEDSNACKS,broadcast=True)

	else:
		emit('update_snacklist',DICT_SNACKS,broadcast=True)
		emit('next_snack_server',DICT_SNACKS,broadcast=True)

@socketio.on('snack_rated')
def snack_rated(data):
	global AVAILABLERATINGS
	global DICT_RATINGLOGS
	global PLAYERSRATED
	global PLAYERCOUNT

	PLAYERSRATED += 1

	if PLAYERSRATED == PLAYERCOUNT:
		print("ALL PLAYERS HAVE VOTED")
		emit('all_players_voted',broadcast=True)
	rating = int(data['rating'])
	logMessage = f"{session['user']} rated {data['rating']}"
	AVAILABLERATINGS[session['user']][rating-1] = 0
	DICT_RATEDSNACKS[CURRENTLYRATING] += int(data['rating'])

	DICT_RATINGLOGS[session['user']] = [CURRENTLYRATING, data['rating']]
	emit('snack_rated_server',{ 'message' : logMessage, 'snacksRating' : DICT_RATEDSNACKS[CURRENTLYRATING]},broadcast=True)
	emit('update_available_ratings',{'AVAILABLERATINGS':AVAILABLERATINGS[session['user']]})	
	emit('update_rating_logs',DICT_RATINGLOGS)

@socketio.on('snack_selected')
def snack_selected(data):
	global DICT_SNACKS
	global CURRENTLYRATING
	global DICT_RATEDSNACKS
	global DICT_RATINGLOGS
	global PLAYERSRATED
	PLAYERSRATED = 0
	DICT_RATINGLOGS = {}

	selected = data['id']
	selectedName = DICT_SNACKS[int(selected)]
	CURRENTLYRATING = selectedName
	DICT_RATEDSNACKS[CURRENTLYRATING] = 0
	pop = DICT_SNACKS.pop(int(selected))
	
	print(f"Snack selected: {selectedName}" )
	emit('snack_selected_server', {'snackSelected' : selectedName} ,broadcast=True)
	emit('update_snacklist',DICT_SNACKS,broadcast=True)

@socketio.on('fetch_snack_image_from_id')
def fetch_snack_image_from_id(data):
	global DICT_SNACKS
	selected = data['id']
	selectedName = DICT_SNACKS[int(selected)]
	emit('translate_id_to_name', {'snackSelected' : selectedName})

@socketio.on('snack_updated')
def change_snack(data):
	global DICT_SNACKS

	try:
		oldname = DICT_SNACKS[int(data['id'])]
		print(f'snack {oldname} updated')
		query = text('UPDATE public.snacks SET name = :snackname WHERE name = :oldname')
		db.session.execute(query, {'snackname': data['newName'],'oldname': oldname})  
		result = db.session.commit()
		DICT_SNACKS[int(data['id'])] = data['newName']
		emit('update_snacklist',DICT_SNACKS,broadcast=True)

	except:
		print("Name change failed")
	#emit('update_snacklist',snacks,broadcast=True)

@socketio.on('snack_added')
def add_snack(data):
	global SNACKCOUNT
	global DICT_SNACKS
	global sessionId
		
	try:
		query = text('INSERT INTO public.snacks (name, "sessionId") VALUES (:snackname, :sessionId)')
		db.session.execute(query, {'snackname': data['name'],'sessionId': sessionId})  
		result = db.session.commit()

		SNACKCOUNT += 1
		print (f"received snack: {data['name']} for a total of {SNACKCOUNT}" )
		DICT_SNACKS[SNACKCOUNT] = data['name']
	except:
		print("snack already exists")
	
	# Add snack to database
	emit('update_snacklist',DICT_SNACKS,broadcast=True)

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
		fetched = result.fetchone()
		# Store the file in the local server storage
		global UPLOAD_FOLDER
		print(f"ADDING IMAGE TO DATABASE FOR ENTRY: {str(fetched[0])}")
		file_path = os.path.join(UPLOAD_FOLDER,str(fetched[0]))
		file.save(file_path)
		
        # Using db.session.execute() to run the raw SQL query
		
		#socketio.emit('refresh_lobby', room=request.sid)
		socketio.emit('update_snacklist',DICT_SNACKS)
		
	return Response(status=302, headers={"Location": "/"})

		#return render_template('lobby.html',username=session['user'])
	return "File not allowed"

# Retrieve uploaded photo
@app.route('/image/<string:snackname>')
def get_image(snackname):
    # Open a new session to query the database
	
	try:
        # Query the database for the image data using SQLAlchemy
		result = db.session.execute(text("SELECT id FROM public.snacks WHERE name = :name"), {'name': snackname})

		snack = result.fetchone()
		print("fetching: " + str(snack[0]))
		if result and snack[0]:
            # The image is stored in a bytea column, so we return the raw bytes
			return send_from_directory('uploads',str(snack[0]))
			#return Response(snack[0], mimetype='image/jpeg')  # Adjust mimetype if different
		else:
			return "Image not found", 404
	finally:
		print("Image Fetched")


# USERS SELECT THEIR USERNAME : TO BE USED BY GUESTS ONLY ONCE IMPLEMENTED
@app.route('/submit_username', methods=['POST'])
def username_selected():
	if 'user' not in session:
		username = request.form['username']
		session['user'] = username
	else:
		print ("user already has session")
	return redirect('/')

# CONNECT & DISCONNECT STATEMENTS
@socketio.on('connect')
def socket_connected():
	global GAMESTARTED
	global DICT_RATINGLOGS
	global CURRENTLYRATING
	global PLAYERSRATED
	global PLAYERCOUNT
	global DICT_SNACKS
	global AVAILABLERATINGS
	
	socketio.emit('whats_my_name',session['user'], room=request.sid)
	if GAMESTARTED:
		if CURRENTLYRATING != 0:
			socketio.emit('snack_selected_server', {'snackSelected' : CURRENTLYRATING}, room=request.sid)
			socketio.emit('update_rating_logs',DICT_RATINGLOGS, room=request.sid)
		if PLAYERSRATED == PLAYERCOUNT:
			# If everyone has voted, give relog the next snack button if lost
			socketio.emit('all_players_voted', room=request.sid)
			
		print(AVAILABLERATINGS[session['user']])

		
		socketio.emit('update_available_ratings',{'AVAILABLERATINGS':AVAILABLERATINGS[session['user']]}, room=request.sid)	
	
	if 'user' in session:
		username = session['user']
		SET_ACTIVESESSIONS.add(username)
	print (f"Current player count: {len(SET_ACTIVESESSIONS)}")
	emit('update_playerlist', {'playerlist': ":".join(SET_ACTIVESESSIONS)}, broadcast=True)
	emit('update_snacklist',DICT_SNACKS)

	if len(DICT_SNACKS) == 0 :
		emit('snacks_finished',DICT_RATEDSNACKS,room=request.sid)


@socketio.on('disconnect')
def socket_disconnected():
	try:
		username = session['user']
	#user = session.get('user')
		if username in SET_ACTIVESESSIONS:
		
			print (f"Player {username} leaving")
			SET_ACTIVESESSIONS.remove(username)
	except:
		print("disconnected user failed")
	emit('update_playerlist', {'playerlist': ":".join(SET_ACTIVESESSIONS)}, broadcast=True)	

# DELETE AFTER IMPLEMENTED PROPERLY
@app.route('/reset')
def reset():
	global GAMESTARTED
	
	GAMESTARTED = False
	setup_game_configurations()
	session.clear()
	
	
	SET_ACTIVESESSIONS.clear()
	print ("reset")
	return "reset"

# STATIC LOCATION RETURN
@app.route('/images/<filename>')
def serve_image(filename):
		#print(f"Fetching image {filename}")
		return send_from_directory('images',filename)

@app.route('/sounds/<filename>')
def serve_sound(filename):
		#print(f"Fetching sound {filename}")
		return send_from_directory('sounds',filename)

@app.route('/styles/<filename>')
def serve_style(filename):
		return send_from_directory('styles',filename)

if __name__ == '__main__':
	socketio.run(app)


### Documentation for naming schemes


## Javascript / Python
# Function Names : FirstSecond()
# Local Variables : firstSecond
# Arrays : arr_firstSecond 
# Lists : list_firstSecond
# Dictionaries : dict_firstSecond
# Global Variables : FIRSTSECOND (caps everything in the name including ARR_FIRSTSECOND)


## HTML 
# Element ID : firstSecond

## CSS
# Class Name : first-second
