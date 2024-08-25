from flask import Flask, request, render_template, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
import json
from queue import Queue
from threading import Lock

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
db = SQLAlchemy(app)

clients = []
clients_lock = Lock()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)

    def __init__(self, username):
        self.username = username


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    user = db.relationship(User, backref=db.backref('messages', lazy=True))

    def __init__(self, content, user_id):
        self.content = content
        self.user_id = user_id


@app.route('/init')
def create_tables():
    db.create_all()
    if User.query.count() == 0:
        user1 = User(username="User1")
        user2 = User(username="User2")
        db.session.add_all([user1, user2])
        db.session.commit()
    return "Tables created"


@app.route('/')
def index():
    users = User.query.all()
    messages = Message.query.all()
    return render_template('index.html', users=users, messages=messages)


@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    user_id = data['user_id']
    content = data['content']
    message = Message(content=content, user_id=user_id)
    db.session.add(message)
    db.session.commit()

    # Notify all clients with the latest message
    notify_clients(message)

    return jsonify({"status": "success"})


def notify_clients(latest_message):
    message_data = {
        'username': latest_message.user.username,
        'content': latest_message.content,
        'timestamp': latest_message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    }
    data = json.dumps(message_data)
    with clients_lock:
        for client in clients:
            client.put(data)


@app.route('/stream')
def stream():

    def event_stream():
        q = Queue()
        with clients_lock:
            clients.append(q)
        try:
            while True:
                data = q.get()
                yield f"data: {data}\n\n"
        except GeneratorExit:
            with clients_lock:
                clients.remove(q)

    return Response(event_stream(), mimetype="text/event-stream")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
