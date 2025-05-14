from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from typing import List
# Import your forms from the forms.py
from forms import CreatePostForm, LoginForm, CommentForm, RegisterForm


'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap5(app)


gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# TODO: Configure Flask-Login


# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(250), nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="posts")
    comments: Mapped[List["Comments"]] = relationship(back_populates="post")

# TODO: Create a User table for all your registered users.
class User(UserMixin,db.Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password: Mapped[str]  = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    posts: Mapped[List["BlogPost"]] = relationship(back_populates="user") 
    comments: Mapped[List["Comments"]] = relationship(back_populates="user")


class Comments(db.Model):
    __tablename__ =  'comments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey('user.id'))
    user: Mapped["User"] = relationship(back_populates="comments")
    text: Mapped[String] = mapped_column(String, nullable=False)
    post_id: Mapped[int] = mapped_column(ForeignKey('blog_posts.id'))
    post: Mapped["BlogPost"] = relationship(back_populates="comments")

    def to_dict(self):
        return {column.name: getattr(self, column.name)  for column in self.__table__.columns}

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

def admin_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.id != 1:
            return abort(401)
        else:
            return func(*args, **kwargs)
    
    return wrapper


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods = ["POST", "GET"])
def register():

    form = RegisterForm()
    if form.validate_on_submit():
        new_user = User(
            name = form.name.data,
            email = form.email.data,
            password = generate_password_hash(form.password.data, method="pbkdf2", salt_length=16)
        )

        try: 
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
        except Exception:
            flash("User already Exist")
            return redirect(url_for('login'))
        else:
            return redirect(url_for('get_blog_posts'))

    return render_template("register.html", form = form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods = ["POST", "GET"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for('get_all_posts'))

    form  = LoginForm()
    if form.validate_on_submit():

        try:
            email = form.email.data
            password = form.password.data

            res = db.session.execute(db.select(User).where(User.email == email)).scalar_one_or_none()
            
            if check_password_hash(res.password, password):
                login_user(res)
            else:
                flash("Wrong Password!")

        except AttributeError:
            flash("User not found")
            return redirect(url_for('login'))
             
        return redirect(url_for('login'))

    return render_template("login.html", form = form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, logged_in = current_user.is_authenticated)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):

    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if form.validate_on_submit():
        if current_user.is_authenticated:
            print(current_user.id)
            comment = Comments(
                author_id = current_user.id,
                text = form.body.data,
                post_id = post_id
            )

            db.session.add(comment)
            db.session.commit()
        else:
            flash("You must login or register first to be able to comment.")
            return redirect(url_for("login"))



    requested_comment = db.session.execute(db.select(Comments).where(Comments.post_id == requested_post.id)).scalars().all()
    return render_template("post.html", post=requested_post, comments=requested_comment, form = form, logged_in = current_user.is_authenticated)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()

    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", logged_in = current_user.is_authenticated)


@app.route("/contact")
def contact():
    return render_template("contact.html", logged_in = current_user.is_authenticated)

if __name__ == "__main__":
    app.run(debug=True, port=5002)
