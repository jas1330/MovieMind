from flask import Flask, render_template, request, flash, redirect, url_for,session
# from flask_mail import Mail, Message
# from config import mail_username,mail_password
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, ValidationError
import bcrypt
from flask_mysqldb import MySQL
import email_validator
import os
import pickle
import requests



# # Generate a secure secret key
# secret_key = os.urandom(24)
# print(secret_key)

app = Flask(__name__)
# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'user_name'
app.config['MYSQL_PASSWORD'] = 'password'
app.config['MYSQL_DB'] = 'database_name'
app.secret_key = 'your_secret_key_here'

mysql = MySQL(app)

class Signup(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Signup")

    def validate_email(self, field):
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s", (field.data,))
        user = cursor.fetchone()
        cursor.close()
        if user:
            raise ValidationError('Email Already Taken')

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

# Load pre-trained data
movies = pickle.load(open('movie_list.pkl', 'rb'))
similarity = pickle.load(open('similarity.pkl', 'rb'))

def fetch_movie_details(movie_id):
    api_key = 'your_api_key'
    movie_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}&language=en-US"
    provider_url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers?api_key={api_key}"
    credits_url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={api_key}&language=en-US"

    # Make the API requests
    movie_response = requests.get(movie_url,timeout=10)
    provider_response = requests.get(provider_url,timeout=10)
    credits_response = requests.get(credits_url,timeout=10)

    # Check if the requests were successful
    if movie_response.status_code != 200 or provider_response.status_code != 200 or credits_response.status_code != 200:
        # Handle error in API response
        return None

    # Parse the JSON data
    movie_data = movie_response.json()
    provider_data = provider_response.json()
    credits_data = credits_response.json()

    # Get the top 5 cast members
    top_cast = [cast_member['name'] for cast_member in credits_data.get('cast', [])[:5]]

    # Get the streaming link if available
    streaming_link = None
    if 'results' in provider_data and 'US' in provider_data['results']:
        streaming_link = provider_data['results']['US'].get('link')

    # Safely access movie details with .get() to avoid NoneType errors
    movie_details = {
        'poster_path': "https://image.tmdb.org/t/p/w500/" + movie_data.get('poster_path', ''),
        'title': movie_data.get('title', 'Title not available'),
        'overview': movie_data.get('overview', 'No overview available'),
        'release_date': movie_data.get('release_date', 'N/A'),
        'rating': movie_data.get('vote_average', 'N/A'),
        'streaming_link': streaming_link or f"https://www.example.com/watch/{movie_id}",  # Fallback link
        'top_cast': top_cast  # Adding top cast members
    }

    return movie_details


def recommend(movie):
    index = movies[movies['title'] == movie].index[0]
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
    recommended_movie_details = []
    
    for i in distances[1:7]:
        movie_id = movies.iloc[i[0]].movie_id
        recommended_movie_details.append(fetch_movie_details(movie_id))

    return recommended_movie_details

@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'user_id' in session:
        user_id = session['user_id']

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE userid=%s", (user_id,))
        user = cursor.fetchone()
        cursor.close()

        if user:
            movie_list = movies['title'].values

            if request.method == 'POST':
                selected_movie = request.form.get('movie')
                if selected_movie:
                    recommended_movies = recommend(selected_movie)
                    return render_template('index.html', movie_list=movie_list, recommended_movies=recommended_movies, user=user)

            return render_template('index.html', movie_list=movie_list, user=user)
    else:
        return redirect(url_for('login'))


@app.route('/recommendation', methods=['POST'])
def recommendation():
    selected_movie = request.form.get('movie')
    if selected_movie:
        recommended_movies = recommend(selected_movie)
        return render_template('recommendation.html', recommended_movies=recommended_movies)
    return redirect('/index')
@app.route('/')
def home():
    return render_template("home.html")
@app.route('/about')
def about():
    return render_template('about.html')
@app.route('/mission')
def mission():
    return render_template("mission.html")
@app.route('/team')
def team():
    return render_template("team.html")
@app.route('/technology')
def technology():
    return render_template("technology.html")




# Route for the contact form
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    return render_template('contact.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    form =LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()

        # The following line prevents the IndexError
        if user and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            session['user_id'] = user[0]
            return redirect(url_for('index'))
        else:
            flash("Login failed. Please check your email and password.")
            return redirect(url_for('login'))

    return render_template('login.html', form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form =Signup()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        password = form.password.data

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed_password))
        mysql.connection.commit()
        cursor.close()

        return redirect(url_for('login'))

    return render_template('signup.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out successfully.")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True,port=5002)
