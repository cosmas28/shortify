from flask import render_template, flash, redirect, session, url_for, request, g, jsonify
import short_url as sh_url
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy.sql import func, desc
import timeago, datetime
import urllib.request
from urllib.request import urlopen
from bs4 import BeautifulSoup
import ssl
from urllib.request import urlopen
import lxml.html
# from app import SITE_URL
from config import POSTS_PER_PAGE

from app import app
from forms.forms import UrlForm, LoginForm, UpdateUrlForm, RegisterForm
# from forms. import UrlForm, LoginForm, UpdateUrlForm, RegisterForm
# from models.models import User, UrlSchema
from functools import wraps
from models.models import User, UrlSchema, db


login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    #loads the user when needed for login.
    return User.query.get(int(user_id))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_anonymous:
            return redirect(url_for('create_short', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@app.route('/index/<int:page>', methods=['GET', 'POST'])
def create_short(page=1):
    '''creating a short url from a given long url'''
    login_form = LoginForm()
    update_form = UpdateUrlForm()
    register_form = RegisterForm()
    form = UrlForm()
    url = form.url.data 
    # print (url)
    custom_url = form.vanity_string.data
    current_id = current_user.get_id()
    
    #The Url variable holds the original url data which is passed to generate a short Url
    data = UrlSchema.query.filter_by(author_id=current_id).order_by(desc(UrlSchema.id)).paginate(page, POSTS_PER_PAGE, False)
    url_short = None

    if request.method=='POST'and form.validate_on_submit():
        new_long_url=UrlSchema(url) 
        # t = lxml.html.parse(urlopen(url))
        new_long_url.author_id = current_id
        #adding url title
        url_title = url.split("/")[2:3]
        # url_title =  (t.find(".//title").text)
        new_long_url.title = (', '.join(url_title))
        # last_id_in_db = db.session.query(UrlSchema.author_id, db.func.count(UrlSchema.author_id).label('count'))
        last_id_in_db =UrlSchema.query.count()
        new_long_url.short_url = custom_url if custom_url else sh_url.encode_url(last_id_in_db+1)
        url_short = new_long_url.short_url
        db.session.add(new_long_url)
        db.session.commit()
        form = UrlForm(formdata=None)

    # get frequent users
    frequent_users = get_frequent_users()
    #popular links i.e links with most clicks (above and equal to 3)
    pop_link = get_popular_links()
    #latest links added 
    recent_links = get_recent_links()
    return render_template('index.html', form=form, update_form=update_form, data=data, frequent_users=frequent_users, pop_link=pop_link, url_short=url_short, recent_links=recent_links, login_form=login_form, register_form=register_form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    '''This functionallows users to register. Heence will add users to the system.'''
    register_form = RegisterForm()
    username = register_form.username.data
    email = register_form.email.data
    password = register_form.password.data
    if request.method == 'POST' and register_form.validate_on_submit():
        new_user=User(username, email, password)
        db.session.add(new_user)
        db.session.commit()
        return redirect (url_for('create_short'))
    return render_template('register.html', register_form=register_form)


@app.route('/login', methods=['POST','GET'])
def login():
    login_form = LoginForm()
    if request.method =='POST' and login_form.validate():
        email = login_form.email.data
        password = login_form.password.data
        user = User.query.filter_by(email=email).first()
        
        if user and user.password == password:
            login_user(user)
            g.user = user
           
            return redirect (url_for('create_short'))
             #upon login, users will be directed to the url for 'create_short' with different priviledges
    return redirect (url_for('create_short'))


@app.route('/<url_short>')
def display(url_short):
    original_url = UrlSchema.query.filter_by(short_url=url_short).first()
    # db.session.query(UrlSchema).filter_by(short_url=url_short).first()
    print(original_url)
    original_url.clicks = original_url.clicks+1
    db.session.add(original_url)
    db.session.commit()
    if original_url.active:
        return redirect(original_url.long_url)
    else:
        return render_template('error-Inactive.html')

@app.route('/logout')
# @login_required
def logout():
    logout_user()
    flash("Logged Out Successfully.")
    return redirect (url_for('create_short'))

def get_frequent_users():
    results = db.session.query(UrlSchema.author_id, 
        db.func.count(UrlSchema.author_id).label('count')).filter(UrlSchema.author_id.isnot(None)).group_by(UrlSchema.author_id).all()
    data = []
    for result in results:
        user = User.query.filter_by(id=result.author_id).first()
        data.append({'name': user.username, 'count': result.count})
    return data

def get_popular_links():
     pop_link  = db.session.query(UrlSchema).filter(UrlSchema.clicks>=5).all()
     data = []
     for link in pop_link:
         data.append({'url': link.short_url, 'clicks': link.clicks, 'url_title':link.title})
     return data

def get_recent_links():
    now = datetime.datetime.now()
    recent_link = db.session.query(UrlSchema).order_by(desc(UrlSchema.id)).limit(5)
    data = []
    for link in recent_link:
        data.append({'rec_link': link.short_url, 'url_title': link.title, 'date_added': (timeago.format(link.timestamp)) })
    return data

@app.route('/delete/', methods=['GET','POST'])
def delete_link():
    id = request.form.get('link-id')
    url = UrlSchema.query.filter_by(id=id).first()
    db.session.delete(url)
    db.session.commit()
    return redirect(url_for('create_short'))

@app.route('/change-status/<url_id>')
def change_status(url_id):
    url = UrlSchema.query.filter_by(id=url_id).first()
    url.active = not url.active
    db.session.commit()
    return redirect(url_for('create_short'))

@app.route('/edit/', methods=['GET','POST'])
@login_required
def update():
    id = request.form.get('url-id')
    update_form = UpdateUrlForm()
    if request.method=='POST'and update_form.validate_on_submit():
        url = UrlSchema.query.filter_by(id=id).first()
        url.long_url = update_form.long_url.data
        db.session.commit()
        flash('Your changes have been saved.')
    return redirect (url_for('create_short'))
