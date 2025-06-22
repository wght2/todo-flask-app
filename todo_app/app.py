from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3?check_same_thread=False&timeout=10'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'supersecretkey'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Таблица связи задач и тегов
task_tags = db.Table('task_tags',
    db.Column('task_id', db.Integer, db.ForeignKey('task.id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'))
)

# Модель пользователя
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

# Модель тега
class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True)

# Модель задачи
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    deadline = db.Column(db.Date)
    priority = db.Column(db.String(10))
    status = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    tags = db.relationship('Tag', secondary=task_tags, backref='tasks')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            return 'Пользователь уже существует'
        
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect('/')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect('/')
        return 'Неверный логин или пароль'
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

@app.route('/')
@login_required
def index():
    status = request.args.get('status')
    priority = request.args.get('priority')
    tag = request.args.get('tag')

    tasks_query = Task.query.filter_by(user_id=current_user.id)
    filtered_query = tasks_query

    if status:
        filtered_query = filtered_query.filter_by(status=status)
    if priority:
        filtered_query = filtered_query.filter_by(priority=priority)
    if tag:
        filtered_query = filtered_query.join(Task.tags).filter(Tag.name == tag)

    tasks = filtered_query.all()

    total = tasks_query.count()
    done = tasks_query.filter_by(status='done').count()
    in_progress = tasks_query.filter_by(status='in_progress').count()
    new = tasks_query.filter_by(status='new').count()
    percent_done = round((done / total) * 100) if total > 0 else 0

    return render_template('index.html',
        tasks=tasks,
        total=total,
        done=done,
        in_progress=in_progress,
        new=new,
        percent_done=percent_done
    )

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['description']
        deadline = datetime.strptime(request.form['deadline'], '%Y-%m-%d')
        priority = request.form['priority']
        tags_str = request.form['tags']

        tag_objs = []
        for tag in [t.strip() for t in tags_str.split(',') if t.strip()]:
            existing = Tag.query.filter_by(name=tag).first()
            if not existing:
                existing = Tag(name=tag)
                db.session.add(existing)
            tag_objs.append(existing)

        task = Task(
            title=title,
            description=desc,
            deadline=deadline,
            priority=priority,
            status='new',
            user_id=current_user.id,
            tags=tag_objs
        )
        db.session.add(task)
        db.session.commit()
        return redirect('/')
    return render_template('form.html')

@app.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        return 'Нет доступа'
    db.session.delete(task)
    db.session.commit()
    return redirect('/')

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        return 'Нет доступа'

    if request.method == 'POST':
        task.title = request.form['title']
        task.description = request.form['description']
        task.deadline = datetime.strptime(request.form['deadline'], '%Y-%m-%d')
        task.priority = request.form['priority']
        task.status = request.form['status']

        task.tags.clear()
        tags_str = request.form['tags']
        for tag in [t.strip() for t in tags_str.split(',') if t.strip()]:
            existing = Tag.query.filter_by(name=tag).first()
            if not existing:
                existing = Tag(name=tag)
                db.session.add(existing)
            task.tags.append(existing)

        db.session.commit()
        return redirect('/')

    tags_string = ', '.join(tag.name for tag in task.tags)
    return render_template('edit.html', task=task, tags_string=tags_string)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
