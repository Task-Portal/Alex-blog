from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, request, abort, g
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreateCommentForm, CreatePostForm, RegisterUser, LoginUser
from flask_gravatar import Gravatar
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import InputRequired, Email
from flask_wtf import FlaskForm
from flask_ckeditor import CKEditorField
from wtforms.validators import DataRequired


app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)
Bootstrap(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
login_manager = LoginManager()
login_manager.init_app(app)
db = SQLAlchemy(app)

# region Classes
# CONFIGURE TABLES


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(110))
    name = db.Column(db.String(1000))
    # This will act like a List of BlogPost objects attached to each User.
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    # Create reference to the User object, the "posts" refers to the posts property in the User class.

    comment_author = relationship("User", back_populates="comments")


db.create_all()


# endregion
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if current_user.get_id() != "1":
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    is_admin = False

    if current_user.is_authenticated and current_user.get_id() == "1":
        is_admin = True

    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated, is_admin=is_admin)


@app.route('/register', methods=["POST", "GET"])
def register():
    form = RegisterUser()
    if form.validate_on_submit():
        email = request.form['email']
        password = request.form['password']
        hashed_pass = generate_password_hash(
            password=password, method='pbkdf2:sha256', salt_length=8)
        name = request.form['name']

        user = User.query.filter_by(email=email).first()
        if user:
            flash("You have already registered with the email, please log in.")
            return redirect(url_for('login'))
        else:
            user = User(email=email, password=hashed_pass, name=name)
            db.session.add(user)
            db.session.commit()

            flash("Please log in.")
            return redirect(url_for('login'))

    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginUser()
    if form.validate_on_submit():
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password=password):
            login_user(user)
            return redirect(url_for('get_all_posts'))

        flash("Password or email is not correct.", category="error")

    return render_template("login.html", form=form, logged_in=current_user.is_authenticated)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
@login_required
def show_post(post_id):
    form = CreateCommentForm()
    requested_post = BlogPost.query.get(post_id)

    if form.validate_on_submit():

        comment = Comment(text=form.body.data,
                          comment_author=current_user,
                          parent_post=requested_post
                          )
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))

    return render_template("post.html", form=form, post=requested_post,logged_in=current_user.is_authenticated,)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_required
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


@app.route("/edit-post/<int:post_id>")
@admin_required
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
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
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_required
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='127.0.0.5', port=5000, debug=1)